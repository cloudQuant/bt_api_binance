"""Binance USDⓈ-M adapter for the neutral market-stream port.

Iteration 62 advertises the ``tick`` channel (public ``bookTicker`` +
``aggTrade`` pushes, see :mod:`bt_api_binance.market_tick_stream`). The order
book session below stays implemented but unadvertised.

This module keeps the existing Binance diff-depth reconstruction and REST
snapshot bridge inside the Binance SDK package. It binds those observations to
the exact selected ``BinanceRequestDataSwap`` object supplied by ``BtApi``;
it does not create another REST client or infer clock quality from timestamps.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections import deque
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from bt_api_base.containers.auto_init_mixin import container_class
from bt_api_base.feeds.my_websocket_app import MyWebsocketApp
from bt_api_base.logging_factory import get_logger
from bt_api_base.market_orderbook_protocol import MarketOrderBookEvent, MarketOrderBookLevel
from bt_api_base.market_protocol import (
    MarketInstrumentKey,
    MarketSourceDescriptor,
    MarketSubscriptionKey,
)
from bt_api_base.market_stream_protocol import MarketStreamRequest
from bt_api_base.market_stream_provider_protocol import (
    MarketStreamChannelCapability,
    MarketStreamProviderBinding,
    MarketStreamProviderChannelBinding,
    MarketStreamProviderRegistryPort,
    SelectedMarketStreamRoute,
)
from bt_api_base.market_tick_protocol import (
    DataClockBinding,
    MarketClockQuality,
    MarketEventCursor,
    MarketFreshnessStatus,
)

from bt_api_binance.containers.orderbooks.binance_orderbook import BinanceWssOrderBookData
from bt_api_binance.exchange_data import BinanceExchangeData
from bt_api_binance.feeds.market_wss_base import BinanceMarketWssData
from bt_api_binance.feeds.swap import BinanceRequestDataSwap

_ROUTE = "BINANCE___SWAP"
_PROVIDER = "binance"
_VENUE = "BINANCE"
_PRODUCT_TYPE = "USDM_PERPETUAL"
_SOURCE_REF = "binance-usdm-public-depth-v1"
_ENTITLEMENT_REF = "binance-public-market-data"
_SOURCE_NAME = "binance-usdm-diff-depth-wss"
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{3,40}$")
_MAX_DEPTH = 1_000
_DEFAULT_INGRESS_CAPACITY = 1_024
_MAX_INGRESS_CAPACITY = 65_536
_MAX_POLL_EVENTS = 4_096
_SNAPSHOT_TIMEOUT_SECONDS = 15.0
_CONNECT_TIMEOUT_SECONDS = 30.0
_SHUTDOWN_TIMEOUT_SECONDS = 5.0
_SOURCE_EPOCH_LOCK = threading.Lock()
_SOURCE_EPOCH_ORDINAL = 0
_FRESHNESS_REASONS = (
    "BINANCE_SOURCE_CLOCK_UNCALIBRATED",
    "BINANCE_RECEIVE_CLOCK_UNQUALIFIED",
)
_SNAPSHOT_FAILED = object()


def _next_source_epoch_ordinal() -> int:
    """Allocate a local epoch identity only after a real WSS on-open callback."""
    global _SOURCE_EPOCH_ORDINAL
    with _SOURCE_EPOCH_LOCK:
        _SOURCE_EPOCH_ORDINAL += 1
        return _SOURCE_EPOCH_ORDINAL


class BinanceMarketStreamProviderError(RuntimeError):
    """Finite, value-free failure from the Binance market-stream adapter."""

    _CODES = frozenset(
        {
            "BINANCE_MARKET_STREAM_ROUTE_UNAVAILABLE",
            "BINANCE_MARKET_STREAM_CHANNEL_UNAVAILABLE",
            "BINANCE_MARKET_STREAM_DUPLICATE_CHANNEL",
            "BINANCE_MARKET_STREAM_START_UNVERIFIED",
            "BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE",
            "BINANCE_MARKET_STREAM_POLL_INVALID",
            "BINANCE_MARKET_STREAM_POLL_FAILED",
            "BINANCE_MARKET_STREAM_EVENT_INVALID",
            "BINANCE_MARKET_STREAM_SOURCE_CHANGED",
            "BINANCE_MARKET_STREAM_RECOVERY_REQUIRED",
            "BINANCE_MARKET_STREAM_RESYNC_ACK_REQUIRED",
            "BINANCE_MARKET_STREAM_RESYNC_UNVERIFIED",
            "BINANCE_MARKET_STREAM_CLOSE_UNVERIFIED",
        }
    )

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if type(code) is str and code in self._CODES
            else "BINANCE_MARKET_STREAM_POLL_FAILED"
        )
        super().__init__(self.code)


@dataclass(frozen=True)
class _IngressRecord:
    generation: int
    websocket: object = field(repr=False, compare=False)
    item: object = field(repr=False, compare=False)


class _BoundedIngressQueue:
    """Bounded WSS handoff preserving the exact callback connection identity."""

    def __init__(self, wake_callback) -> None:
        self._items: deque[_IngressRecord] = deque()
        self._condition = threading.Condition()
        self._local = threading.local()
        self._capacity = _DEFAULT_INGRESS_CAPACITY
        self._overflowed = False
        self._wake_callback = wake_callback

    def configure(self, capacity: int, *, reset: bool) -> None:
        if type(capacity) is not int or not 1 <= capacity <= _MAX_INGRESS_CAPACITY:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_POLL_INVALID")
        with self._condition:
            if self._items and not reset:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_START_UNVERIFIED")
            if reset:
                self._items.clear()
                self._overflowed = False
            self._capacity = capacity

    @contextmanager
    def source_context(self, generation: int, websocket: object) -> Iterator[None]:
        previous = getattr(self._local, "source", None)
        self._local.source = (generation, websocket)
        try:
            yield
        finally:
            self._local.source = previous

    def current_source(self) -> tuple[int, object] | None:
        return getattr(self._local, "source", None)

    def put(self, item: object, block: bool = True, timeout: float | None = None) -> None:
        del block, timeout
        source = self.current_source()
        generation, websocket = source if source is not None else (0, None)
        wake = False
        with self._condition:
            if self._overflowed:
                return
            if len(self._items) >= self._capacity:
                self._items.clear()
                self._overflowed = True
                self._condition.notify_all()
                wake = True
            else:
                self._items.append(_IngressRecord(generation, websocket, item))
                self._condition.notify_all()
                wake = True
        if wake:
            with suppress(Exception):
                self._wake_callback()

    def take(self, limit: int, timeout_ms: int) -> tuple[_IngressRecord, ...]:
        if (
            type(limit) is not int
            or not 1 <= limit <= _MAX_POLL_EVENTS
            or type(timeout_ms) is not int
            or not 0 <= timeout_ms <= 60_000
        ):
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_POLL_INVALID")
        deadline = time.monotonic() + timeout_ms / 1_000.0
        with self._condition:
            while not self._items and not self._overflowed and timeout_ms:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
            if self._overflowed:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_POLL_FAILED")
            count = min(limit, len(self._items))
            return tuple(self._items.popleft() for _ in range(count))


class _RouteBoundBinanceMarketWss(BinanceMarketWssData):
    """Existing Binance depth engine with selected-route REST snapshot access."""

    def __init__(
        self,
        ingress: _BoundedIngressQueue,
        route_client: BinanceRequestDataSwap,
        instrument: MarketInstrumentKey,
        environment: str,
        websocket_url: str,
    ) -> None:
        params = BinanceExchangeData.__new__(BinanceExchangeData)
        BinanceExchangeData.__init__(params)
        params.exchange_name = _ROUTE
        params.environment = environment
        params.wss_url = websocket_url
        params.rest_url = ""
        params.acct_wss_url = ""
        params.wss_paths = {
            "depth": {
                "params": ["<symbol>@depth@100ms"],
                "method": "SUBSCRIBE",
                "id": 1,
            }
        }

        # Deliberately initialize only the WSS base. BinanceMarketWssData's
        # normal constructor also creates an HTTP client; REST snapshots below
        # use the exact BtApi-selected route client instead.
        MyWebsocketApp.__init__(
            self,
            ingress,
            exchange_data=params,
            wss_url=websocket_url,
            wss_name="bt_api_binance_market_stream",
            readiness_timeout=_CONNECT_TIMEOUT_SECONDS,
            shutdown_timeout=_SHUTDOWN_TIMEOUT_SECONDS,
        )
        self.topics: list[dict[str, str]] = []
        self.asset_type = "SWAP"
        self.exchange_name = _ROUTE
        self.logger = get_logger("binance_market_stream")
        self._next_subscription_id = 0
        self._pending_subscription_ids: set[int] = set()
        self._depth_sequences: dict[str, int] = {}
        self._depth_gaps: set[str] = set()
        self._depth_books: dict[str, dict[str, Any]] = {}
        self._depth_buffers: dict[str, list[dict[str, Any]]] = {}
        self._depth_lock = threading.RLock()
        self._depth_seed_inflight: set[str] = set()
        self._depth_stale_emitted: set[str] = set()
        self._ingress = ingress
        self._route_client = route_client
        self._instrument = instrument
        self._environment = environment
        self._connection_lock = threading.Lock()
        self._connection_by_id: dict[int, tuple[object, int]] = {}
        self._snapshot_boundary_generation = 0
        self._source_epoch_ordinal = 0
        self._snapshot_bid_floor: Decimal | None = None
        self._snapshot_ask_ceiling: Decimal | None = None
        self._depth_snapshot_workers: set[threading.Thread] = set()
        self._depth_worker_lock = threading.Lock()

    def open_rsp(self) -> bool:
        self._snapshot_boundary_generation = self._connection_generation
        self._source_epoch_ordinal = _next_source_epoch_ordinal()
        self._snapshot_bid_floor = None
        self._snapshot_ask_ceiling = None
        return super().open_rsp()

    def on_open(self, websocket: object) -> None:
        super().on_open(websocket)
        with self._connection_lock:
            self._connection_by_id[id(websocket)] = (websocket, self._connection_generation)

    def on_message(self, websocket: object, message: str) -> None:
        with self._connection_lock:
            entry = self._connection_by_id.get(id(websocket))
            generation = entry[1] if entry is not None and entry[0] is websocket else 0
        with self._ingress.source_context(generation, websocket):
            super().on_message(websocket, message)

    def on_close(self, websocket: object, status_code: object, message: object) -> None:
        try:
            super().on_close(websocket, status_code, message)
        finally:
            with self._connection_lock:
                entry = self._connection_by_id.get(id(websocket))
                if entry is not None and entry[0] is websocket:
                    self._connection_by_id.pop(id(websocket), None)

    def stop(self) -> None:
        super().stop()
        deadline = time.monotonic() + _SHUTDOWN_TIMEOUT_SECONDS
        current = threading.current_thread()
        with self._depth_worker_lock:
            workers = tuple(self._depth_snapshot_workers)
        for worker in workers:
            if worker is current:
                continue
            worker.join(timeout=max(0.0, deadline - time.monotonic()))
            if worker.is_alive():
                raise RuntimeError("Binance depth snapshot worker did not stop")

    def _schedule_depth_snapshot(self, symbol: str) -> None:
        source = self._ingress.current_source()
        if source is None:
            return
        generation, websocket = source
        if type(generation) is not int or generation <= 0 or websocket is None:
            return
        lock = self._get_depth_lock()
        with lock:
            inflight = getattr(self, "_depth_seed_inflight", None)
            if inflight is None:
                inflight = self._depth_seed_inflight = set()
            if symbol in inflight:
                return
            inflight.add(symbol)
        worker = threading.Thread(
            target=self._run_route_depth_snapshot,
            args=(symbol, generation, websocket),
            daemon=True,
            name="binance-market-depth-snapshot",
        )
        with self._depth_worker_lock:
            self._depth_snapshot_workers.add(worker)
        try:
            worker.start()
        except Exception:
            with self._depth_worker_lock:
                self._depth_snapshot_workers.discard(worker)
            with lock:
                self._depth_seed_inflight.discard(symbol)
            raise

    def _run_route_depth_snapshot(self, symbol: str, generation: int, websocket: object) -> None:
        try:
            self._verify_selected_route()
            result = self._route_client.get_depth(symbol, count=_MAX_DEPTH)
            self._verify_selected_route()
            if hasattr(result, "get_input_data"):
                result = result.get_input_data()
            if type(result) is str:
                result = json.loads(result)
            snapshot = _validate_rest_snapshot(result)
            if not self._connection_is_current(generation, websocket):
                return
            bid_floor = min(price for price, _ in snapshot["bids"])
            ask_ceiling = max(price for price, _ in snapshot["asks"])
            with self._ingress.source_context(generation, websocket), self._get_depth_lock():
                if not self._connection_is_current(generation, websocket):
                    return
                self._snapshot_boundary_generation = generation
                self._snapshot_bid_floor = bid_floor
                self._snapshot_ask_ceiling = ask_ceiling
                accepted = BinanceMarketWssData.seed_depth_snapshot(
                    self,
                    symbol,
                    snapshot["lastUpdateId"],
                    bids=snapshot["raw_bids"],
                    asks=snapshot["raw_asks"],
                    publish=False,
                )
                if accepted:
                    state = self._depth_books[symbol]
                    self._publish_depth_book(
                        symbol,
                        {
                            "e": "depthSnapshot",
                            "s": symbol,
                            "U": snapshot["lastUpdateId"],
                            "u": state["last_update_id"],
                        },
                        "snapshot",
                    )
                else:
                    self._ingress.put(_SNAPSHOT_FAILED)
        except Exception:
            # Do not log response text or an exception that may contain a URL,
            # header, or provider response. The stream owner observes no book
            # and fails bootstrap/poll closed with a finite code.
            if self._connection_is_current(generation, websocket):
                with self._ingress.source_context(generation, websocket):
                    self._ingress.put(_SNAPSHOT_FAILED)
            return
        finally:
            if self._connection_generation == generation:
                with self._get_depth_lock():
                    self._depth_seed_inflight.discard(symbol)
            with self._depth_worker_lock:
                self._depth_snapshot_workers.discard(threading.current_thread())

    def _connection_is_current(self, generation: int, websocket: object) -> bool:
        return (
            type(generation) is int
            and generation > 0
            and self._connection_generation == generation
            and self.ws is websocket
            and self._running_flag is True
            and not self._stop_event.is_set()
        )

    def _verify_selected_route(self) -> None:
        info = self._route_client.get_environment_info()
        if (
            not isinstance(info, Mapping)
            or set(info) != {"environment", "simulated", "verified"}
            or type(info.get("environment")) is not str
            or info.get("environment") != self._environment
            or type(info.get("verified")) is not bool
            or info.get("verified") is not True
            or type(info.get("simulated")) is not bool
            or info.get("simulated") is not (self._environment != "production")
        ):
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_ROUTE_UNAVAILABLE")


class BinanceMarketStreamAdapter:
    """Pure route-bound Binance order-book provider adapter."""

    def __init__(self, route: SelectedMarketStreamRoute) -> None:
        _validate_selected_route(route)
        self._route = route

    def capabilities(self) -> tuple[MarketStreamChannelCapability, ...]:
        """Declare the public tick channel only (no I/O).

        The order-book source (diff depth + REST snapshot bridge) stays
        unadvertised: its production WSS endpoint and native-source
        assumptions are pending independent verification.
        """
        return (MarketStreamChannelCapability(channel="tick", max_depth=None),)

    def open_session(self, *, wake_callback: Callable[[], None]) -> Any:
        """Create an unstarted tick session shell; the first subscribe starts WSS."""
        from bt_api_binance.market_tick_stream import BinanceTickMarketStreamSession

        if not callable(wake_callback):
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_ROUTE_UNAVAILABLE")
        return BinanceTickMarketStreamSession(self._route, wake_callback=wake_callback)


class BinanceMarketStreamSession:
    """One WSS depth source, with bounded feed-to-owner handoff and resync."""

    def __init__(
        self,
        route: SelectedMarketStreamRoute,
        *,
        wake_callback: Callable[[], None],
    ) -> None:
        _validate_selected_route(route)
        self._route = route
        self._owner_thread_id = threading.get_ident()
        self._lock = threading.RLock()
        self._ingress = _BoundedIngressQueue(wake_callback)
        self._stream: _RouteBoundBinanceMarketWss | None = None
        self._binding: MarketStreamProviderChannelBinding | None = None
        self._source: MarketSourceDescriptor | None = None
        self._request: MarketStreamRequest | None = None
        self._connection_generation = 0
        self._connection_object: object | None = None
        self._cursor_sequence = 0
        self._last_provider_sequence: int | None = None
        self._recovery_required = False
        self._closed = False
        self._cleanup_unverified = False

    def subscribe(self, request: MarketStreamRequest, /) -> MarketStreamProviderChannelBinding:
        with self._lock:
            self._check_owner()
            if self._closed or self._cleanup_unverified:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_CLOSE_UNVERIFIED")
            if (
                type(request) is not MarketStreamRequest
                or request.exchange_name != self._route.exchange_name
                or request.instrument != self._route.instrument
                or request.channel != "orderbook"
                or type(request.depth) is not int
                or not 1 <= request.depth <= _MAX_DEPTH
            ):
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_CHANNEL_UNAVAILABLE")
            if self._binding is not None:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_DUPLICATE_CHANNEL")
            self._verify_selected_route()
            self._ingress.configure(request.queue_capacity, reset=True)
            self._request = request
            self._stream = self._new_stream()
            try:
                self._stream.topics = [
                    {"topic": "depth", "symbol": request.instrument.native_symbol}
                ]
                self._stream.start(connect_timeout=_CONNECT_TIMEOUT_SECONDS)
                event, source = self._wait_for_bootstrap(recovery=False)
                self._source = source
                self._connection_generation = source.connection_generation
                self._connection_object = self._stream.ws
                self._cursor_sequence = 1
                self._last_provider_sequence = event.provider_sequence
                binding = MarketStreamProviderChannelBinding(
                    token=object(),
                    request=request,
                    key=source.key,
                    source=source,
                    initial_cursor=event.cursor,
                    initial_events=(event,),
                    recovery_required=False,
                )
                self._binding = binding
                return binding
            except BinanceMarketStreamProviderError:
                self._stop_after_failed_start()
                raise
            except Exception:
                self._stop_after_failed_start()
                raise BinanceMarketStreamProviderError(
                    "BINANCE_MARKET_STREAM_START_UNVERIFIED"
                ) from None

    def poll(self, *, timeout_ms: int, max_events: int) -> tuple[MarketOrderBookEvent, ...]:
        with self._lock:
            self._check_owner()
            request = self._request
            binding = self._binding
            source = self._source
            stream = self._stream
            if (
                self._closed
                or self._cleanup_unverified
                or request is None
                or binding is None
                or source is None
                or stream is None
            ):
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_POLL_FAILED")
            if self._recovery_required:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_RECOVERY_REQUIRED")
            if (
                type(timeout_ms) is not int
                or not 0 <= timeout_ms <= 60_000
                or type(max_events) is not int
                or not 1 <= max_events <= _MAX_POLL_EVENTS
            ):
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_POLL_INVALID")
            if not self._stream_matches_source():
                self._recovery_required = True
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SOURCE_CHANGED")
            try:
                self._verify_selected_route()
                records = self._ingress.take(max_events, timeout_ms)
                events = []
                for record in records:
                    if (
                        record.generation != self._connection_generation
                        or record.websocket is not self._connection_object
                    ):
                        raise BinanceMarketStreamProviderError(
                            "BINANCE_MARKET_STREAM_SOURCE_CHANGED"
                        )
                    if self._is_initial_snapshot_notice(record.item):
                        continue
                    if record.item is _SNAPSHOT_FAILED:
                        raise BinanceMarketStreamProviderError(
                            "BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE"
                        )
                    event = self._project_record(record, source, request, recovery=False)
                    events.append(event)
                    self._cursor_sequence = event.cursor.sequence
                    self._last_provider_sequence = event.provider_sequence
                return tuple(events)
            except BinanceMarketStreamProviderError:
                self._recovery_required = True
                raise
            except Exception:
                self._recovery_required = True
                raise BinanceMarketStreamProviderError(
                    "BINANCE_MARKET_STREAM_POLL_FAILED"
                ) from None

    def resync(
        self,
        binding: MarketStreamProviderChannelBinding,
        *,
        acknowledge_data_loss: bool,
    ) -> MarketStreamProviderChannelBinding:
        with self._lock:
            self._check_owner()
            if type(acknowledge_data_loss) is not bool or not acknowledge_data_loss:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_RESYNC_ACK_REQUIRED")
            if (
                self._binding is None
                or binding is not self._binding
                or not self._recovery_required
                or self._request is None
                or self._stream is None
            ):
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_RESYNC_UNVERIFIED")
            previous_generation = self._connection_generation
            try:
                self._stop_stream()
            except Exception:
                self._cleanup_unverified = True
                raise BinanceMarketStreamProviderError(
                    "BINANCE_MARKET_STREAM_CLOSE_UNVERIFIED"
                ) from None
            self._ingress.configure(self._request.queue_capacity, reset=True)
            self._source = None
            self._connection_object = None
            self._cursor_sequence = 0
            self._last_provider_sequence = None
            self._recovery_required = False
            try:
                self._verify_selected_route()
                self._stream.topics = [
                    {"topic": "depth", "symbol": self._request.instrument.native_symbol}
                ]
                self._stream.start(connect_timeout=_CONNECT_TIMEOUT_SECONDS)
                event, source = self._wait_for_bootstrap(recovery=True)
                if source.connection_generation <= previous_generation:
                    raise BinanceMarketStreamProviderError(
                        "BINANCE_MARKET_STREAM_RESYNC_UNVERIFIED"
                    )
                self._source = source
                self._connection_generation = source.connection_generation
                self._connection_object = self._stream.ws
                self._cursor_sequence = 1
                self._last_provider_sequence = event.provider_sequence
                next_binding = MarketStreamProviderChannelBinding(
                    token=object(),
                    request=self._request,
                    key=source.key,
                    source=source,
                    initial_cursor=event.cursor,
                    initial_events=(event,),
                    recovery_required=False,
                )
                self._binding = next_binding
                return next_binding
            except BinanceMarketStreamProviderError:
                self._recovery_required = True
                self._stop_after_failed_start()
                raise
            except Exception:
                self._recovery_required = True
                self._stop_after_failed_start()
                raise BinanceMarketStreamProviderError(
                    "BINANCE_MARKET_STREAM_RESYNC_UNVERIFIED"
                ) from None

    def unsubscribe(self, binding: MarketStreamProviderChannelBinding, /) -> bool:
        with self._lock:
            self._check_owner()
            if self._binding is None or binding is not self._binding:
                return False
            try:
                self._stop_stream()
            except Exception:
                self._cleanup_unverified = True
                return False
            self._binding = None
            self._source = None
            self._request = None
            self._connection_object = None
            self._closed = True
            self._ingress.configure(_DEFAULT_INGRESS_CAPACITY, reset=True)
            return True

    def close(self) -> bool:
        with self._lock:
            if self._closed:
                return True
            if self._binding is not None:
                return False
            if self._cleanup_unverified:
                return False
            if self._stream is not None:
                try:
                    self._stop_stream()
                except Exception:
                    self._cleanup_unverified = True
                    return False
            self._closed = True
            return True

    def _new_stream(self) -> _RouteBoundBinanceMarketWss:
        route = self._route
        environment = route.instrument.environment
        websocket_url = _websocket_url(environment)
        return _RouteBoundBinanceMarketWss(
            self._ingress,
            route.client,
            route.instrument,
            environment,
            websocket_url,
        )

    def _wait_for_bootstrap(
        self, *, recovery: bool
    ) -> tuple[MarketOrderBookEvent, MarketSourceDescriptor]:
        stream = self._stream
        request = self._request
        if stream is None or request is None:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_START_UNVERIFIED")
        generation = stream._connection_generation
        websocket = stream.ws
        if (
            type(generation) is not int
            or generation <= 0
            or websocket is None
            or stream._running_flag is not True
        ):
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_START_UNVERIFIED")
        epoch_ordinal = stream._source_epoch_ordinal
        if type(epoch_ordinal) is not int or epoch_ordinal <= 0:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_START_UNVERIFIED")
        source = _source_descriptor(request, generation, epoch_ordinal)
        deadline = time.monotonic() + _SNAPSHOT_TIMEOUT_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE")
            records = self._ingress.take(1, min(1_000, max(1, int(remaining * 1_000))))
            if stream._connection_generation != generation or stream.ws is not websocket:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SOURCE_CHANGED")
            if not records:
                if stream._running_flag is not True or stream._stop_event.is_set():
                    raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_START_UNVERIFIED")
                continue
            record = records[0]
            if record.generation != generation or record.websocket is not websocket:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SOURCE_CHANGED")
            if self._is_initial_snapshot_notice(record.item):
                continue
            if record.item is _SNAPSHOT_FAILED:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE")
            event = self._project_record(
                record,
                source,
                request,
                recovery=recovery,
                sequence=1,
                previous_provider_sequence=None,
            )
            if event.snapshot_or_delta != "snapshot":
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE")
            return event, source

    def _project_record(
        self,
        record: _IngressRecord,
        source: MarketSourceDescriptor,
        request: MarketStreamRequest,
        *,
        recovery: bool,
        sequence: int | None = None,
        previous_provider_sequence: int | None = None,
    ) -> MarketOrderBookEvent:
        # Exact class, also for a published (frozen) container.
        if container_class(record.item) is not BinanceWssOrderBookData:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
        item = record.item
        try:
            item.init_data()
        except Exception:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID") from None
        raw = item.order_book_data
        if (
            not isinstance(raw, Mapping)
            or raw.get("s") != request.instrument.native_symbol
            or item.get_exchange_name() != _VENUE
            or item.get_asset_type() != "SWAP"
            or item.get_symbol_name() != request.instrument.native_symbol
            or item.stale is not False
            or item.continuity_status not in {"snapshot", "continuous"}
            or self._stream is None
            or self._stream._snapshot_boundary_generation != source.connection_generation
            or self._stream._snapshot_bid_floor is None
            or self._stream._snapshot_ask_ceiling is None
        ):
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
        provider_sequence = _positive_int(raw.get("u"))
        if provider_sequence is None:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
        native_previous = _optional_nonnegative_int(raw.get("pu"))
        continuity = item.continuity_status
        snapshot_or_delta = "snapshot" if continuity == "snapshot" else "delta"
        if snapshot_or_delta == "delta":
            if native_previous is None:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
            expected_previous = (
                previous_provider_sequence
                if previous_provider_sequence is not None
                else self._last_provider_sequence
            )
            if expected_previous is None or native_previous != expected_previous:
                raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SOURCE_CHANGED")
        elif sequence is None and self._last_provider_sequence is not None:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SOURCE_CHANGED")

        bids = _project_levels(raw.get("b"), request.depth, reverse=True)
        asks = _project_levels(raw.get("a"), request.depth, reverse=False)
        if (
            len(bids) != request.depth
            or len(asks) != request.depth
            or bids[-1].price < self._stream._snapshot_bid_floor
            or asks[-1].price > self._stream._snapshot_ask_ceiling
        ):
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
        if bids[0].price >= asks[0].price:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")

        if sequence is None:
            self._cursor_sequence += 1
            sequence = self._cursor_sequence
        else:
            self._cursor_sequence = sequence
        cursor = MarketEventCursor(source.stream_id, source.epoch, sequence)
        event_clock = _clock_binding(
            source, cursor, item, snapshot=(snapshot_or_delta == "snapshot")
        )
        return MarketOrderBookEvent(
            source=source,
            cursor=cursor,
            instrument=request.instrument,
            clock=event_clock,
            bids=bids,
            asks=asks,
            provider_sequence=provider_sequence,
            provider_previous_sequence=native_previous if snapshot_or_delta == "delta" else None,
            snapshot_or_delta=snapshot_or_delta,
            continuity_status=continuity,
            stale=False,
            stale_reason="",
            recovery_snapshot=recovery and snapshot_or_delta == "snapshot",
            complete_state=True,
        )

    @staticmethod
    def _is_initial_snapshot_notice(item: object) -> bool:
        return (
            isinstance(item, Mapping)
            and item.get("kind") == "orderbook"
            and item.get("stale") is True
            and item.get("stale_reason") == "snapshot_required"
        )

    def _stream_matches_source(self) -> bool:
        stream = self._stream
        return (
            stream is not None
            and stream._running_flag is True
            and not stream._stop_event.is_set()
            and stream._connection_generation == self._connection_generation
            and stream.ws is self._connection_object
        )

    def _verify_selected_route(self) -> None:
        if type(self._route.client) is not BinanceRequestDataSwap:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_ROUTE_UNAVAILABLE")
        info = self._route.client.get_environment_info()
        if (
            not isinstance(info, Mapping)
            or set(info) != {"environment", "simulated", "verified"}
            or type(info.get("environment")) is not str
            or info.get("environment") != self._route.instrument.environment
            or type(info.get("verified")) is not bool
            or info.get("verified") is not True
            or type(info.get("simulated")) is not bool
            or info.get("simulated") is not (self._route.instrument.environment != "production")
        ):
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_ROUTE_UNAVAILABLE")

    def _stop_stream(self) -> None:
        stream = self._stream
        if stream is None:
            return
        stream.stop()
        if (
            stream.process is not None
            and stream.process.is_alive()
            or stream._restart_process is not None
            and stream._restart_process.is_alive()
            or stream._watchdog_process is not None
            and stream._watchdog_process.is_alive()
            or stream._readiness_watchdog_process is not None
            and stream._readiness_watchdog_process.is_alive()
            or stream.ws is not None
        ):
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_CLOSE_UNVERIFIED")

    def _stop_after_failed_start(self) -> None:
        try:
            self._stop_stream()
        except Exception:
            self._cleanup_unverified = True

    def _check_owner(self) -> None:
        if threading.get_ident() != self._owner_thread_id:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_POLL_FAILED")


def register_binance_market_stream_provider(
    registry: MarketStreamProviderRegistryPort,
) -> None:
    """Register the exact Binance USDⓈ-M provider route."""
    if not callable(getattr(registry, "register", None)):
        raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_ROUTE_UNAVAILABLE")
    registry.register(_ROUTE, _create_binance_market_stream_binding)


def _create_binance_market_stream_binding(
    route: SelectedMarketStreamRoute,
) -> MarketStreamProviderBinding:
    _validate_selected_route(route)
    return MarketStreamProviderBinding(
        instrument=route.instrument,
        adapter=BinanceMarketStreamAdapter(route),
    )


def _validate_selected_route(route: SelectedMarketStreamRoute) -> None:
    if (
        type(route) is not SelectedMarketStreamRoute
        or route.exchange_name != _ROUTE
        or type(route.client) is not BinanceRequestDataSwap
        or type(route.instrument) is not MarketInstrumentKey
        or route.instrument.provider != _PROVIDER
        or route.instrument.venue != _VENUE
        or route.instrument.environment not in {"production", "demo"}
        or route.instrument.product_type != _PRODUCT_TYPE
        or route.instrument.instrument_id != route.instrument.native_symbol
        or _SYMBOL_PATTERN.fullmatch(route.instrument.native_symbol) is None
        or type(route.environment) is not str
        or route.environment != route.instrument.environment
        or not callable(getattr(route.client, "get_depth", None))
        or not callable(getattr(route.client, "get_environment_info", None))
    ):
        raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_ROUTE_UNAVAILABLE")


def _websocket_url(environment: str) -> str:
    if environment == "production":
        return "wss://fstream.binance.com/ws"
    if environment == "demo":
        return "wss://demo-fstream.binance.com/ws"
    raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_ROUTE_UNAVAILABLE")


def _source_descriptor(
    request: MarketStreamRequest, generation: int, epoch_ordinal: int
) -> MarketSourceDescriptor:
    key = MarketSubscriptionKey(
        source_ref=_SOURCE_REF,
        entitlement_ref=_ENTITLEMENT_REF,
        instrument=request.instrument,
        channel="orderbook",
        depth=request.depth,
        timeframe=None,
    )
    # The SDK ordinal prevents a new WSS object (whose own generation resets)
    # from reusing an earlier epoch. The descriptor generation stays the
    # exact counter read from this live WSS object.
    epoch = f"binance-usdm-wss-open-{epoch_ordinal}-generation-{generation}"
    return MarketSourceDescriptor(
        key=key,
        stream_id=key.stream_id,
        epoch=epoch,
        provider=_PROVIDER,
        source=_SOURCE_NAME,
        connection_generation=generation,
        clock_domain_id="unavailable",
        clock_source_session_id=epoch,
        clock_source="unqualified",
    )


def _validate_rest_snapshot(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE")
    last_update_id = _positive_int(value.get("lastUpdateId"))
    raw_bids = value.get("bids")
    raw_asks = value.get("asks")
    bids = _parse_snapshot_side(raw_bids)
    asks = _parse_snapshot_side(raw_asks)
    if (
        last_update_id is None
        or not bids
        or not asks
        or len(bids) > _MAX_DEPTH
        or len(asks) > _MAX_DEPTH
        or max(price for price, _ in bids) >= min(price for price, _ in asks)
    ):
        raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE")
    return {
        "lastUpdateId": last_update_id,
        "raw_bids": raw_bids,
        "raw_asks": raw_asks,
        "bids": bids,
        "asks": asks,
    }


def _parse_snapshot_side(value: object) -> tuple[tuple[Decimal, Decimal], ...]:
    if type(value) not in (list, tuple):
        raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE")
    parsed = []
    seen = set()
    for row in value:
        if type(row) not in (list, tuple) or len(row) != 2:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE")
        if type(row[0]) is not str or type(row[1]) is not str:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE")
        try:
            price = Decimal(row[0])
            quantity = Decimal(row[1])
        except Exception:
            raise BinanceMarketStreamProviderError(
                "BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE"
            ) from None
        if (
            not price.is_finite()
            or not quantity.is_finite()
            or price <= 0
            or quantity <= 0
            or price in seen
        ):
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_SNAPSHOT_UNAVAILABLE")
        seen.add(price)
        parsed.append((price, quantity))
    return tuple(parsed)


def _project_levels(
    value: object, depth: int, *, reverse: bool
) -> tuple[MarketOrderBookLevel, ...]:
    if type(value) not in (list, tuple) or type(depth) is not int:
        raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
    parsed = []
    seen = set()
    for row in value:
        if type(row) not in (list, tuple) or len(row) != 2:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
        if type(row[0]) is not str or type(row[1]) is not str:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
        try:
            price = Decimal(row[0])
            quantity = Decimal(row[1])
        except Exception:
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID") from None
        if (
            not price.is_finite()
            or not quantity.is_finite()
            or price <= 0
            or quantity <= 0
            or price in seen
        ):
            raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
        seen.add(price)
        parsed.append((price, quantity))
    parsed.sort(key=lambda pair: pair[0], reverse=reverse)
    if len(parsed) < depth:
        raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
    return tuple(MarketOrderBookLevel(price, quantity) for price, quantity in parsed[:depth])


def _clock_binding(
    source: MarketSourceDescriptor,
    cursor: MarketEventCursor,
    item: BinanceWssOrderBookData,
    *,
    snapshot: bool,
) -> DataClockBinding:
    raw = item.order_book_data
    provider_time = _provider_time(raw.get("E")) if isinstance(raw, Mapping) else None
    received_at = None
    received_monotonic = None
    if not snapshot:
        received = getattr(item, "local_update_time", None)
        if isinstance(received, datetime) and received.tzinfo is not None:
            received_at = (
                received.astimezone(timezone.utc)
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
            )
        monotonic = getattr(item, "received_monotonic_ns", None)
        if type(monotonic) is int and monotonic >= 0:
            received_monotonic = monotonic
    return DataClockBinding(
        source=source,
        cursor=cursor,
        provider_event_time_utc=provider_time,
        received_at_utc=received_at,
        received_monotonic_ns=received_monotonic,
        source_clock_quality=MarketClockQuality.UNKNOWN,
        receive_clock_quality=MarketClockQuality.UNKNOWN,
        source_clock_error_ms=None,
        receive_clock_error_ms=None,
        freshness_status=MarketFreshnessStatus.UNAVAILABLE,
        freshness_reason_codes=_FRESHNESS_REASONS,
    )


def _provider_time(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID")
    try:
        return (
            datetime.fromtimestamp(value / 1_000.0, tz=timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError):
        raise BinanceMarketStreamProviderError("BINANCE_MARKET_STREAM_EVENT_INVALID") from None


def _positive_int(value: object) -> int | None:
    return value if type(value) is int and value > 0 else None


def _optional_nonnegative_int(value: object) -> int | None:
    if value is None:
        return None
    return value if type(value) is int and value >= 0 else None


__all__ = [
    "BinanceMarketStreamAdapter",
    "BinanceMarketStreamProviderError",
    "BinanceMarketStreamSession",
    "register_binance_market_stream_provider",
]
