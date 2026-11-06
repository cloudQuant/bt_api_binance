"""Binance USDⓈ-M public ``bookTicker`` + ``aggTrade`` as a neutral tick stream.

Iteration 62.  The session hosts the existing route-bound Binance market WSS
(on the route's environment host: ``demo-fstream.binance.com`` for demo)
inside the SDK's direct ``MarketStreamPort`` owner and projects every
``bookTicker`` and ``aggTrade`` push into a neutral
:class:`~bt_api_base.market_tick_protocol.MarketTickPayload`.

Facts and their provenance:

* A ``bookTicker`` push is a quote tick: bid/ask and sizes (``b``/``B``/``a``/
  ``A``), ``delta_volume`` 0 (no trade carried), last = the latest ``aggTrade``
  price of the same epoch (``None`` before the first one).
* An ``aggTrade`` push is a trade tick: last = ``p``, ``delta_volume`` = ``q``
  (base asset), bid/ask from the latest ``bookTicker`` of the same epoch.
* Volume accounting (delta semantics): the first aggregate trade after
  subscribe or resync is the baseline (delta 0, ``volume_quality="baseline"``,
  ``volume_complete=False``).  An ``a`` that follows the previous ``a`` by one
  (aggregate trade ids are consecutive per symbol) is ``continuous``/complete.
  Any larger ``a`` is a trade-id jump: that push alone is ``discontinuous``/
  incomplete (its own ``q`` is still reported, nothing is invented for the ids
  in between) and the accounting continues from it.  A repeated or older ``a``
  is ignored.  Quote ticks are complete once the accounting is anchored,
  otherwise ``baseline``.
* Trade-id jumps are counted per binding (:meth:`BinanceTickMarketStreamSession.
  trade_id_jumps`) and per session (``counters["trade_id_jump"]``), counts
  only.  The first jump of an instrument is logged as a warning with the
  instrument and the jump size (``a - (previous + 1)``); later ones at most
  once a minute per instrument, with the number suppressed.
* ``provider_event_time_utc`` is each push's event time ``E`` (venue
  milliseconds, ``provider_reported``); ``received_at_utc`` /
  ``received_monotonic_ns`` are taken when the WSS frame is received.
* Clock qualities stay UNKNOWN and freshness UNAVAILABLE; the SDK qualifies
  ticks separately (venue clock cross-check via ``server_time_observation``).
* ``continuity_status`` means the tick belongs to the binding's connection
  and epoch with no locally known lost push (D62-38, iteration 62).  It is
  ``gap`` only for the tick after a dropped or malformed frame, otherwise
  ``continuous``:

  - The first tick of a binding (after subscribe or a resync) is
    ``continuous``: a ``bookTicker`` is the complete best bid/ask and an
    ``aggTrade`` a complete trade, so its price stands on its own and its
    freshness is judged by the SDK from ``E``.  Only its volume is a baseline.
    A resync is bound only after the SDK owner acknowledged the data loss, and
    it starts a new epoch on the current connection with an empty ingress.
  - A trade-id jump on an uninterrupted connection is not evidence of a lost
    push (user decision 3, iteration 62, following OKX 6bd5958): Binance
    ``aggTrade`` ids are not proven gapless on the stream (not checked against
    the ``f``/``l`` trade ids), so only the volume of that push is incomplete.
  - Connection loss and ingress overflow (below) remain the loss signals.

A reconnect (new WSS generation) or an ingress overflow marks the channel
recovery-required: ``poll`` raises once so the SDK owner moves the channel to
RECOVERY_REQUIRED, and ``resync`` binds a new source epoch (and a new volume
baseline) on the current connection.  Every session call must happen on the
opening thread.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from uuid import uuid4

from bt_api_base.market_protocol import MarketSourceDescriptor, MarketSubscriptionKey
from bt_api_base.market_stream_protocol import MarketStreamRequest
from bt_api_base.market_stream_provider_protocol import (
    MarketStreamProviderChannelBinding,
    MarketStreamProviderContractError,
    SelectedMarketStreamRoute,
)
from bt_api_base.market_tick_protocol import (
    MarketClockQuality,
    MarketEventCursor,
    MarketFreshnessStatus,
    MarketTickEvent,
    MarketTickPayload,
    bind_market_tick_event,
)

from bt_api_binance.market_stream_provider import (
    _BoundedIngressQueue,
    _RouteBoundBinanceMarketWss,
    _validate_selected_route,
    _websocket_url,
)

BINANCE_TICK_SOURCE_REF = "binance-usdm-public-tick-v1"
BINANCE_TICK_ENTITLEMENT_REF = "binance-public-market-data"
BINANCE_TICK_SOURCE = "binance-usdm-wss-bookticker-aggtrade"
_CLOCK_DOMAIN = "unix-epoch-milliseconds-utc"
_CLOCK_SOURCE = "binance-reported-event-time"
_FRESHNESS_REASONS = (
    "BINANCE_SOURCE_CLOCK_UNCALIBRATED",
    "BINANCE_RECEIVE_CLOCK_UNQUALIFIED",
)
_CONNECT_TIMEOUT_SECONDS = 30.0
_MAX_PROVIDER_BATCH = 4096
_MAX_POLL_TIMEOUT_MS = 60_000
_LOGGER_NAME = "binance_market_tick"
_TRADE_ID_JUMP_LOG_INTERVAL_SECONDS = 60.0


def _invalid(code: str = "MARKET_STREAM_PROVIDER_SESSION_INVALID") -> MarketStreamProviderContractError:
    return MarketStreamProviderContractError(code)


@dataclass(frozen=True)
class _TickFrame:
    """One raw bookTicker/aggTrade push with its frame receipt clocks."""

    content: Mapping[str, Any]
    received_ns: Optional[int]
    received_monotonic_ns: Optional[int]


class _RouteBoundBinanceTickWss(_RouteBoundBinanceMarketWss):
    """The route-bound Binance market WSS subscribed to bookTicker + aggTrade."""

    def __init__(self, ingress: _BoundedIngressQueue, route: SelectedMarketStreamRoute) -> None:
        environment = route.instrument.environment
        super().__init__(
            ingress, route.client, route.instrument, environment, _websocket_url(environment)
        )
        self._params.wss_paths = {
            "book_ticker": {"params": ["<symbol>@bookTicker"], "method": "SUBSCRIBE", "id": 1},
            "agg_trade": {"params": ["<symbol>@aggTrade"], "method": "SUBSCRIBE", "id": 1},
        }
        symbol = route.instrument.native_symbol
        self.topics = [
            {"topic": "book_ticker", "symbol": symbol},
            {"topic": "agg_trade", "symbol": symbol},
        ]
        self._message_receipt: Optional[tuple[int, int]] = None

    def on_message(self, websocket: object, message: str) -> None:
        # Receipt time of the frame before parsing (same WSS callback thread).
        self._message_receipt = (time.time_ns(), time.monotonic_ns())
        super().on_message(websocket, message)

    def handle_data(self, content: dict[str, Any]) -> None:
        if not isinstance(content, dict) or content.get("e") not in ("bookTicker", "aggTrade"):
            return
        receipt = self._message_receipt or (None, None)
        self._ingress.put(_TickFrame(content, receipt[0], receipt[1]))


def _venue_number(value: Any, *, positive: bool) -> Optional[float]:
    if value is None or value == "":
        return None
    if type(value) is not str:
        raise ValueError("binance_tick_number_invalid")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError("binance_tick_number_invalid") from None
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError("binance_tick_number_invalid")
    return float(number)


def _utc_from_ms(value: Any) -> Optional[str]:
    if type(value) is not int or not 0 < value <= 253402300799999:
        return None
    return (
        datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _utc_from_ns(value: Any) -> Optional[str]:
    if type(value) is not int or value <= 0:
        return None
    seconds, nanoseconds = divmod(value, 1_000_000_000)
    moment = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(
        microsecond=nanoseconds // 1000
    )
    return moment.isoformat(timespec="microseconds").replace("+00:00", "Z")


@dataclass
class _TickChannel:
    binding: MarketStreamProviderChannelBinding
    subscription_epoch: int
    cursor: int = 0
    # Set by a dropped or malformed frame: the next tick follows a lost push.
    # A new binding has lost nothing (D62-38, iteration 62).
    gap_pending: bool = False
    recovery_required: bool = False
    quote: Optional[tuple[Optional[float], Optional[float], Optional[float], Optional[float]]] = None
    last_price: Optional[float] = None
    # Aggregate trade id ``a`` anchoring the delta-volume accounting of this epoch.
    trade_anchor: Optional[int] = None
    # Trade-id jumps seen on this binding, and the size of the latest one.
    trade_id_jumps: int = 0
    last_trade_id_jump: int = 0


def trade_volume(channel: _TickChannel, trade_id: int, quantity: float):
    """Delta-volume facts of one aggregate trade, or ``None`` for a repeated/older id.

    Returns ``(delta, complete, volume_quality, jump)``.  ``jump`` is 0 unless
    the id is not the previous one plus one; then it is ``a - (previous + 1)``
    (the number of ids skipped) and the push's volume is incomplete.  A jump
    is not a continuity gap.
    """

    anchor = channel.trade_anchor
    if anchor is None:
        channel.trade_anchor = trade_id
        return 0.0, False, "baseline", 0
    if trade_id <= anchor:
        return None
    channel.trade_anchor = trade_id
    jump = trade_id - (anchor + 1)
    if jump == 0:
        return quantity, True, "continuous", 0
    channel.last_trade_id_jump = jump
    return quantity, False, "discontinuous", jump


def project_binance_tick(
    content: Mapping[str, Any],
    channel: _TickChannel,
    *,
    sequence: int,
    received_ns: Optional[int],
    received_monotonic_ns: Optional[int],
) -> Optional[MarketTickPayload]:
    """Project one push and update the channel's quote/last/volume state.

    Returns ``None`` for an aggregate trade whose id was already accounted.
    """

    source = channel.binding.source
    instrument = source.key.instrument
    if content.get("s") != instrument.native_symbol:
        raise ValueError("binance_tick_instrument_mismatch")
    event = content.get("e")
    if event == "bookTicker":
        quote = (
            _venue_number(content.get("b"), positive=True),
            _venue_number(content.get("a"), positive=True),
            _venue_number(content.get("B"), positive=False),
            _venue_number(content.get("A"), positive=False),
        )
        last_price = channel.last_price
        anchored = channel.trade_anchor is not None
        delta, complete = 0.0, anchored
        volume_quality = "continuous" if anchored else "baseline"
    elif event == "aggTrade":
        trade_id = content.get("a")
        if type(trade_id) is not int or trade_id < 0:
            raise ValueError("binance_tick_trade_id_invalid")
        last_price = _venue_number(content.get("p"), positive=True)
        quantity = _venue_number(content.get("q"), positive=True)
        if last_price is None or quantity is None:
            raise ValueError("binance_tick_trade_values_missing")
        volume = trade_volume(channel, trade_id, quantity)
        if volume is None:
            return None
        delta, complete, volume_quality, _jump = volume
        quote = channel.quote
    else:
        raise ValueError("binance_tick_event_unsupported")
    event_time = _utc_from_ms(content.get("E"))
    bid, ask, bid_size, ask_size = quote if quote is not None else (None, None, None, None)
    payload = MarketTickPayload(
        instrument=instrument,
        last_price=last_price,
        bid_price=bid,
        ask_price=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        lower_limit=None,
        upper_limit=None,
        turnover=None,
        open_interest=None,
        delta_volume=delta,
        cumulative_volume=None,
        volume_complete=complete,
        volume_quality=volume_quality,
        # Only a lost push breaks continuity; neither a new binding nor a
        # trade-id jump does (D62-38 / user decision 3, iteration 62).
        continuity_status="gap" if channel.gap_pending else "continuous",
        trading_date=None,
        event_session_date=None,
        provider_event_time_utc=event_time,
        event_time_provenance="provider_reported" if event_time is not None else "unavailable",
        received_at_utc=_utc_from_ns(received_ns),
        received_monotonic_ns=(
            received_monotonic_ns
            if type(received_monotonic_ns) is int and received_monotonic_ns >= 0
            else None
        ),
        provider_source=source.source,
        quality_contract_ref=None,
        provider_connection_generation=source.connection_generation,
        provider_sequence=sequence,
        provider_subscription_epoch=channel.subscription_epoch,
        clock_domain_id=source.clock_domain_id,
        clock_source_session_id=source.clock_source_session_id,
        clock_source=source.clock_source,
        source_clock_quality=MarketClockQuality.UNKNOWN,
        receive_clock_quality=MarketClockQuality.UNKNOWN,
        source_clock_error_ms=None,
        receive_clock_error_ms=None,
        freshness_status=MarketFreshnessStatus.UNAVAILABLE,
        freshness_reason_codes=_FRESHNESS_REASONS,
        execution_eligible=False,
        quality_flags=(),
    )
    channel.quote = quote
    channel.last_price = last_price
    return payload


class BinanceTickMarketStreamSession:
    """One Binance USDⓈ-M public WSS tick source for one route/instrument."""

    def __init__(
        self,
        route: SelectedMarketStreamRoute,
        *,
        wake_callback: Callable[[], None],
        stream_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        _validate_selected_route(route)
        if not callable(wake_callback):
            raise _invalid()
        self._route = route
        self._wake_callback = wake_callback
        self._stream_factory = stream_factory or _RouteBoundBinanceTickWss
        self._owner_thread = threading.get_ident()
        self._ingress = _BoundedIngressQueue(wake_callback)
        self._stream: Any = None
        self._channels: dict[object, _TickChannel] = {}
        self._session_ref = uuid4().hex[:16]
        self._epoch_ordinal = 0
        self._ingest_sequence = 0
        self._raise_pending = False
        self._closed = False
        self._cleanup_unverified = False
        self.counters: dict[str, int] = {}
        # Trade-id jump warnings: logger created on the first jump; per
        # instrument (next allowed monotonic time, warnings suppressed since).
        self._logger: Any = None
        self._log_clock: Callable[[], float] = time.monotonic
        self._jump_log_state: dict[str, tuple[float, int]] = {}

    # -- MarketStreamProviderSession ----------------------------------------
    def subscribe(self, request: MarketStreamRequest, /) -> MarketStreamProviderChannelBinding:
        self._check_owner()
        self._validate_request(request)
        if self._closed or self._cleanup_unverified:
            raise _invalid()
        if any(channel.binding.request == request for channel in self._channels.values()):
            raise _invalid("MARKET_STREAM_PROVIDER_BINDING_INVALID")
        self._start_if_needed(request.queue_capacity)
        generation = self._current_generation()
        if generation is None:
            raise _invalid()
        binding, epoch = self._new_binding(request, generation)
        self._channels[binding.token] = _TickChannel(binding, epoch)
        return binding

    def poll(self, *, timeout_ms: int, max_events: int) -> tuple[MarketTickEvent, ...]:
        self._check_owner()
        if (
            type(timeout_ms) is not int
            or not 0 <= timeout_ms <= _MAX_POLL_TIMEOUT_MS
            or type(max_events) is not int
            or not 1 <= max_events <= _MAX_PROVIDER_BATCH
        ):
            raise _invalid("MARKET_STREAM_PROVIDER_EVENT_INVALID")
        if self._closed or self._cleanup_unverified:
            raise _invalid()
        self._raise_if_pending()
        if not self._channels or self._stream is None:
            return ()
        self._check_connection()
        events: list[MarketTickEvent] = []
        deadline = time.monotonic() + timeout_ms / 1000.0
        while not self._raise_pending and len(events) < max_events:
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
            try:
                records = self._ingress.take(
                    max_events - len(events), 0 if events else min(remaining_ms, 50)
                )
            except Exception:
                self._recover_all("queue_overflow")
                self._force_reconnect()
                break
            for record in records:
                self._process(record, events)
            if events or remaining_ms <= 0:
                break
        if self._raise_pending and not events:
            self._raise_if_pending()
        return tuple(events)

    def resync(
        self,
        binding: MarketStreamProviderChannelBinding,
        *,
        acknowledge_data_loss: bool,
    ) -> MarketStreamProviderChannelBinding:
        """Bind a new source epoch on the current connection after a loss."""

        self._check_owner()
        if acknowledge_data_loss is not True:
            raise _invalid("MARKET_STREAM_PROVIDER_BINDING_INVALID")
        channel = self._channel_for(binding)
        if not channel.recovery_required or self._closed or self._cleanup_unverified:
            raise _invalid("MARKET_STREAM_PROVIDER_BINDING_INVALID")
        if self._stream is None:
            self._start_if_needed(binding.request.queue_capacity)
        deadline = time.monotonic() + _CONNECT_TIMEOUT_SECONDS
        generation = self._current_generation()
        while generation is None:
            if time.monotonic() >= deadline:
                raise _invalid()
            time.sleep(0.05)
            generation = self._current_generation()
        # Everything queued before this point belongs to the lost epoch.
        self._ingress.configure(binding.request.queue_capacity, reset=True)
        self._raise_pending = False
        new_binding, epoch = self._new_binding(binding.request, generation)
        del self._channels[binding.token]
        self._channels[new_binding.token] = _TickChannel(new_binding, epoch)
        return new_binding

    def unsubscribe(self, binding: MarketStreamProviderChannelBinding, /) -> bool:
        self._check_owner()
        channel = self._channels.get(getattr(binding, "token", None))
        if channel is None or channel.binding is not binding:
            return False
        del self._channels[binding.token]
        if self._channels:
            return True
        return self._stop_stream()

    def trade_id_jumps(self, binding: MarketStreamProviderChannelBinding, /) -> int:
        """Trade-id jumps counted on ``binding`` (a count; no ids, prices or sizes)."""

        self._check_owner()
        return self._channel_for(binding).trade_id_jumps

    def close(self) -> bool:
        self._check_owner()
        self._channels.clear()
        closed = self._stop_stream()
        if closed:
            self._closed = True
            self._cleanup_unverified = False
        else:
            self._cleanup_unverified = True
        return closed

    # -- internals ----------------------------------------------------------
    def _bump(self, name: str) -> None:
        self.counters[name] = self.counters.get(name, 0) + 1

    def _record_trade_id_jump(self, channel: _TickChannel) -> None:
        """Count one trade-id jump; warn on the first, then once a minute per instrument."""

        channel.trade_id_jumps += 1
        self._bump("trade_id_jump")
        try:
            instrument = channel.binding.source.key.instrument.native_symbol
            now = self._log_clock()
            next_at, suppressed = self._jump_log_state.get(instrument, (None, 0))
            if next_at is not None and now < next_at:
                self._jump_log_state[instrument] = (next_at, suppressed + 1)
                return
            self._jump_log_state[instrument] = (now + _TRADE_ID_JUMP_LOG_INTERVAL_SECONDS, 0)
            if self._logger is None:
                from bt_api_base.logging_factory import get_logger

                self._logger = get_logger(_LOGGER_NAME)
            self._logger.warning(
                "Binance aggTrade id jump on an uninterrupted connection: instrument=%s "
                "jump=%d binding_jumps=%d suppressed=%d; continuity kept, row volume incomplete",
                instrument,
                channel.last_trade_id_jump,
                channel.trade_id_jumps,
                suppressed,
            )
        except Exception:
            # Diagnostics must never stop the stream; the count above stands.
            self._bump("trade_id_jump_log_failed")

    def _raise_if_pending(self) -> None:
        if self._raise_pending:
            self._raise_pending = False
            raise _invalid("MARKET_STREAM_PROVIDER_EVENT_INVALID")

    def _recover_all(self, reason: str) -> None:
        for channel in self._channels.values():
            if not channel.recovery_required:
                channel.recovery_required = True
                self._raise_pending = True
                self._bump(f"recovery:{reason}")

    def _check_connection(self) -> None:
        stream = self._stream
        generation = getattr(stream, "_connection_generation", None)
        stop_event = getattr(stream, "_stop_event", None)
        stopped = stop_event is None or stop_event.is_set()
        for channel in tuple(self._channels.values()):
            if channel.recovery_required:
                continue
            if stopped:
                self._recover_all("stream_stopped")
            elif generation != channel.binding.source.connection_generation:
                self._recover_all("connection_changed")

    def _process(self, record: Any, events: list[MarketTickEvent]) -> None:
        frame = getattr(record, "item", None)
        generation = getattr(record, "generation", None)
        if type(frame) is not _TickFrame or not isinstance(frame.content, Mapping):
            self._bump("non_tick_frame_ignored")
            return
        for channel in self._channels.values():
            if channel.recovery_required:
                self._bump("tick_dropped_recovery_required")
                continue
            if generation != channel.binding.source.connection_generation:
                self._recover_all("connection_changed")
                continue
            try:
                payload = project_binance_tick(
                    frame.content,
                    channel,
                    sequence=self._ingest_sequence + 1,
                    received_ns=frame.received_ns,
                    received_monotonic_ns=frame.received_monotonic_ns,
                )
            except Exception:
                channel.gap_pending = True  # a lost push: the next tick is not continuous
                self._bump("tick_frame_invalid")
                continue
            if payload is None:
                self._bump("trade_repeated_or_out_of_order")
                continue
            if payload.volume_quality == "discontinuous":
                self._record_trade_id_jump(channel)
            self._ingest_sequence += 1
            source = channel.binding.source
            channel.cursor += 1
            channel.gap_pending = False
            events.append(
                bind_market_tick_event(
                    payload, source, MarketEventCursor(source.stream_id, source.epoch, channel.cursor)
                )
            )

    def _new_binding(
        self, request: MarketStreamRequest, generation: int
    ) -> tuple[MarketStreamProviderChannelBinding, int]:
        self._epoch_ordinal += 1
        key = MarketSubscriptionKey(
            source_ref=BINANCE_TICK_SOURCE_REF,
            entitlement_ref=BINANCE_TICK_ENTITLEMENT_REF,
            instrument=request.instrument,
            channel="tick",
            depth=None,
            timeframe=None,
        )
        epoch = f"binance-tick-{self._session_ref}-g{generation}-e{self._epoch_ordinal}"
        source = MarketSourceDescriptor(
            key=key,
            stream_id=key.stream_id,
            epoch=epoch,
            provider="binance",
            source=BINANCE_TICK_SOURCE,
            connection_generation=generation,
            clock_domain_id=_CLOCK_DOMAIN,
            clock_source_session_id=epoch,
            clock_source=_CLOCK_SOURCE,
        )
        binding = MarketStreamProviderChannelBinding(
            token=object(),
            request=request,
            key=key,
            source=source,
            initial_cursor=None,
            initial_events=(),
            recovery_required=False,
        )
        return binding, self._epoch_ordinal

    def _current_generation(self) -> Optional[int]:
        stream = self._stream
        generation = getattr(stream, "_connection_generation", None)
        stop_event = getattr(stream, "_stop_event", None)
        if (
            type(generation) is not int
            or generation <= 0
            or getattr(stream, "_running_flag", False) is not True
            or stop_event is None
            or stop_event.is_set()
        ):
            return None
        return generation

    def _start_if_needed(self, queue_capacity: int) -> None:
        if self._stream is not None:
            return
        try:
            self._verify_environment()
            self._ingress.configure(max(1, min(int(queue_capacity), 65536)), reset=True)
            stream = self._stream_factory(self._ingress, self._route)
            self._stream = stream
            stream.start(connect_timeout=_CONNECT_TIMEOUT_SECONDS)
            if self._current_generation() is None:
                raise RuntimeError("binance_tick_stream_not_ready")
        except Exception:
            if self._stream is not None and not self._stop_stream():
                self._cleanup_unverified = True
            raise _invalid() from None

    def _verify_environment(self) -> None:
        try:
            info = self._route.client.get_environment_info()
        except Exception:
            raise _invalid("MARKET_STREAM_PROVIDER_ROUTE_INVALID") from None
        environment = self._route.instrument.environment
        if (
            type(info) is not dict
            or info.get("verified") is not True
            or info.get("environment") != environment
            or info.get("simulated") is not (environment != "production")
        ):
            raise _invalid("MARKET_STREAM_PROVIDER_ROUTE_INVALID")

    def _force_reconnect(self) -> None:
        ws = getattr(self._stream, "ws", None)
        if ws is not None:
            try:
                ws.close()
            except Exception:
                self._bump("reconnect_close_failed")

    def _stop_stream(self) -> bool:
        stream = self._stream
        if stream is None:
            return True
        try:
            stream.stop()
        except Exception:
            return False
        workers = tuple(
            getattr(stream, name, None)
            for name in (
                "process",
                "_restart_process",
                "_watchdog_process",
                "_readiness_watchdog_process",
            )
        )
        if any(worker is not None and worker.is_alive() for worker in workers) or getattr(
            stream, "ws", None
        ) is not None:
            return False
        self._stream = None
        return True

    def _validate_request(self, request: object) -> None:
        if (
            type(request) is not MarketStreamRequest
            or request.exchange_name != self._route.exchange_name
            or request.instrument != self._route.instrument
            or request.channel != "tick"
            or request.depth is not None
        ):
            raise _invalid("MARKET_STREAM_PROVIDER_CHANNEL_UNAVAILABLE")

    def _channel_for(self, binding: object) -> _TickChannel:
        channel = self._channels.get(getattr(binding, "token", None))
        if channel is None or channel.binding is not binding:
            raise _invalid("MARKET_STREAM_PROVIDER_BINDING_INVALID")
        return channel

    def _check_owner(self) -> None:
        if threading.get_ident() != self._owner_thread:
            raise _invalid()



__all__ = [
    "BINANCE_TICK_ENTITLEMENT_REF",
    "BINANCE_TICK_SOURCE",
    "BINANCE_TICK_SOURCE_REF",
    "BinanceTickMarketStreamSession",
    "project_binance_tick",
    "trade_volume",
]
