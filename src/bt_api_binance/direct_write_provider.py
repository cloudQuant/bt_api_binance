"""Binance USDⓈ-M SWAP direct write provider (iteration 62, no execution session).

Registered for ``bt_api.direct_write_providers`` / ``BINANCE___SWAP``.  The SDK
(``bt_api_py.direct_write``) owns write admission and the pre-dispatch commit
ordering; this module owns only Binance facts and native REST calls:

* **Identity.**  The native identity is the request's ``client_order_id`` sent
  unchanged as ``newClientOrderId`` (Binance rule ``^[.A-Z:/a-z0-9_-]{1,36}$``)
  plus the native ``symbol``.  An id that violates the rule is refused, never
  rewritten.  ``fields`` carry ``symbol``, ``trading_day`` (UTC date of the
  reservation) and, once the venue returns it, ``order_id``.
* **Requests.**  The request is validated and mapped *before* any reservation
  by the provider-owned ``map_order_request``, the provider-declared quantity
  unit validator and the feed's own ``_make_order`` builder (no network).  Only
  native symbols (``BTCUSDT``) are accepted; USDⓈ-M quantities are base-asset
  amounts.
* **Sends.**  ``submit_order``/``cancel_order`` consume the SDK one-shot grant
  immediately before the single signed request (one HTTP attempt).  A venue
  error code that the provider classification marks as a definite rejection
  returns ``sent=False``; every other failure after the grant was consumed
  (timeouts, HTTP 5xx, ``-1007``/``-1006``, unclassified codes) raises
  :class:`BinanceDirectOutcomeUnknown`, deliberately *not* a
  ``DirectWriteError``, so the SDK coordinator reports the outcome as unknown.
* **Returns.**  Polled: on ``drain_execution_events`` each watched order is
  queried at most once per ``poll_interval`` (bounded per drain), and its fills
  (``/fapi/v1/userTrades`` rows with their trade ``id``) are read when the
  executed quantity grows.  Events are emitted only on change; terminal orders
  stop being watched once their fills are complete.
* **Account facts.**  Positions and balance come from one signed
  ``/fapi/v2/account`` read; working orders from ``/fapi/v1/openOrders``.
  ``allOrders`` and ``userTrades`` require a symbol, so the day's orders and
  fills are complete only for an explicit ``symbols`` scope.

Binance has no settlement-confirmation step; nothing here decides admission,
and credentials are never logged or returned (``account_reference`` is a hash).
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Mapping, Optional
from uuid import uuid4

from bt_api_base.direct_write_protocol import (
    DirectAccountFacts,
    DirectBalanceFact,
    DirectExecutionEvent,
    DirectExecutionEventKind,
    DirectOrderReservation,
    DirectOrderStatus,
    DirectPositionFact,
    DirectSubmitResult,
    DirectWriteError,
    NativeOrderIdentity,
    SettlementStatus,
    WriteGrant,
    WriteGrantVerifier,
    WriteOperation,
)

from bt_api_binance.provider_configuration_registration import EXCHANGE_NAME

__all__ = (
    "BINANCE_DIRECT_WRITE_EXCHANGE",
    "BinanceDirectOutcomeUnknown",
    "BinanceDirectWriteProvider",
    "create_binance_direct_write_provider",
    "register_binance_direct_write_provider",
)

BINANCE_DIRECT_WRITE_EXCHANGE = EXCHANGE_NAME
_SESSION_GENERATION = 1
_CLIENT_ORDER_ID = re.compile(r"[.A-Z:/a-z0-9_-]{1,36}\Z", re.ASCII)
_NATIVE_SYMBOL = re.compile(r"[A-Z0-9]{2,32}\Z", re.ASCII)
_VENUE_ID = re.compile(r"[0-9]{1,24}\Z", re.ASCII)
_ORDER_TYPES = frozenset({"LIMIT", "MARKET"})
_STATUS = {
    "NEW": DirectOrderStatus.ACCEPTED,
    "PARTIALLY_FILLED": DirectOrderStatus.PARTIALLY_FILLED,
    "FILLED": DirectOrderStatus.FILLED,
    "CANCELED": DirectOrderStatus.CANCELLED,
    "EXPIRED": DirectOrderStatus.CANCELLED,
    "EXPIRED_IN_MATCH": DirectOrderStatus.CANCELLED,
    "REJECTED": DirectOrderStatus.REJECTED,
}
_TERMINAL_STATES = frozenset({"FILLED", "CANCELED", "EXPIRED", "EXPIRED_IN_MATCH", "REJECTED"})
_SIDES = {"BUY": "buy", "SELL": "sell"}
_ORDER_NOT_FOUND_CODE = "-2013"
_PAGE_LIMIT = 1000
_MAX_PAGES = 5
_MAX_EVENTS = 50_000
_MAX_NOT_FOUND_BACKOFF = 30.0
_TERMINAL_FILL_GRACE = 60.0
# GET /fapi/v1/userTrades serves the last 7 days; a startTime window may not
# exceed 7 days either.
_FILLS_WINDOW_MS = 7 * 86_400_000
_FILL_RETRY_FAST = 5
_MAX_FILL_BACKOFF = 30.0
_SERVER_TIME_PATH = "GET /fapi/v1/time"
_SERVER_TIME_TTL = 60.0
_SERVER_TIME_RETRY = 5.0
_MAX_AUTO_WATCHED = 64
_MAX_FACTS_TIMEOUT = 10.0
_ENVIRONMENTS = frozenset({"production", "demo", "testnet"})


class BinanceDirectOutcomeUnknown(RuntimeError):
    """The signed request may have reached Binance; whether it took effect is unknown.

    Not a ``DirectWriteError`` on purpose: the SDK coordinator maps every
    ``DirectWriteError`` outside its unknown-outcome code set to "not sent",
    and maps any other exception to an unknown outcome.  ``code`` is one of
    ``binance_direct_submit_outcome_unknown`` /
    ``binance_direct_cancel_outcome_unknown``.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


class _OrderNotFound(Exception):
    pass


# ---------------------------------------------------------------------------
# small pure helpers
# ---------------------------------------------------------------------------
def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        value = repr(value)
    if type(value) is not str:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _float(value: Any) -> Optional[float]:
    number = _decimal(value)
    return None if number is None else float(number)


def _text(value: Any) -> Optional[str]:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def _venue_id(value: Any) -> Optional[str]:
    if isinstance(value, bool):
        return None
    text = _text(value)
    return text if text is not None and _VENUE_ID.fullmatch(text) else None


def _utc_day(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).strftime("%Y%m%d")


def _utc_day_start_ms(epoch_seconds: float) -> int:
    moment = datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
    start = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp() * 1000)


def _ms(value: Any) -> Optional[int]:
    text = _venue_id(value)
    return None if text is None else int(text)


def _iso_from_ms(value: Any) -> Optional[str]:
    milliseconds = _ms(value)
    if milliseconds is None or not 0 < milliseconds <= 253402300799999:
        return None
    return (
        datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _day_from_ms(value: Any) -> Optional[str]:
    milliseconds = _ms(value)
    if milliseconds is None or not 0 < milliseconds <= 253402300799999:
        return None
    return _utc_day(milliseconds / 1000)


def _detail(exc: BaseException) -> str:
    detail = getattr(exc, "detail", None)
    text = detail if isinstance(detail, str) and detail else str(exc)
    return text[:200]


def _offset(position_side: Optional[str], side: Optional[str], reduce_only: Optional[bool]) -> Optional[str]:
    """Open/close as Binance states it; ``None`` when the venue does not say.

    Hedge mode: ``positionSide`` with the side decides.  One-way mode
    (``BOTH``) cannot state whether a fill opened or closed, except for
    reduce-only orders, which Binance only lets reduce a position.
    """

    if position_side == "LONG" and side in ("buy", "sell"):
        return "open" if side == "buy" else "close"
    if position_side == "SHORT" and side in ("buy", "sell"):
        return "open" if side == "sell" else "close"
    if reduce_only is True:
        return "close"
    return None


def _reduce_only(value: Any) -> Optional[bool]:
    if value is True or value == "true":
        return True
    if value is False or value == "false":
        return False
    return None


def _payload(result: Any) -> Any:
    getter = getattr(result, "get_input_data", None)
    return getter() if callable(getter) else None


def _object(result: Any) -> dict[str, Any]:
    payload = _payload(result)
    # Successful USDⓈ-M object replies never carry ``code``; error bodies do.
    if type(payload) is not dict or "code" in payload:
        raise ValueError("binance_response_shape_invalid")
    return payload


def _list(result: Any) -> list[dict[str, Any]]:
    payload = _payload(result)
    if type(payload) is not list or any(type(row) is not dict for row in payload):
        raise ValueError("binance_response_shape_invalid")
    return payload


def _native_error_code(exc: BaseException) -> Optional[str]:
    """Binance error code carried by a translated venue error, if any."""

    try:
        raw = getattr(exc, "raw_response", None)
    except Exception:
        return None
    if not isinstance(raw, Mapping):
        return None
    code = raw.get("code")
    if isinstance(code, bool) or not isinstance(code, (int, str)):
        return None
    text = _text(code)
    return text if text is not None and re.fullmatch(r"-[0-9]{1,6}", text) else None


def _definite_reject_code(exc: BaseException) -> Optional[str]:
    """Native code when Binance definitely refused the request, else ``None``.

    Only a translated venue reply whose code the provider classification
    (:mod:`bt_api_binance.error_classification`) marks as a definite rejection
    qualifies.  HTTP 5xx, timeouts, transport errors and unclassified codes
    (including ``-1007`` "send status unknown") leave the outcome unknown.
    """

    from bt_api_base.error import ServerError, UnifiedError

    from bt_api_binance.error_classification import classify_error

    if isinstance(exc, ServerError) or not isinstance(exc, UnifiedError):
        return None
    code = _native_error_code(exc)
    if code is None:
        return None
    _category, _environment, definite = classify_error(code)
    return code if definite is True else None


@dataclass
class _Reserved:
    reservation: DirectOrderReservation
    path: str
    params: dict[str, Any]
    extra_data: dict[str, Any]
    reduce_only: Optional[bool]


@dataclass
class _Watch:
    identity: NativeOrderIdentity
    symbol: str
    client_order_id: Optional[str]
    order_id: Optional[str]
    reduce_only: Optional[bool]
    fills_since_ms: Optional[int]
    origin: str
    next_due: float = 0.0
    last_key: Optional[tuple[Any, ...]] = None
    trade_ids: set[str] = field(default_factory=set)
    trade_qty: Decimal = Decimal(0)
    not_found: int = 0
    terminal_since: Optional[float] = None
    terminal_state: Optional[str] = None
    terminal_filled: Optional[Decimal] = None
    created_ms: Optional[int] = None
    fill_attempts: int = 0


class BinanceDirectWriteProvider:
    """Direct write port for one ``BINANCE___SWAP`` route (one ``BinanceRequestDataSwap``)."""

    def __init__(
        self,
        feed: Any,
        *,
        poll_interval: float = 1.0,
        max_queries_per_drain: int = 4,
        drain_time_budget: float = 2.0,
        query_timeout: float = 3.0,
        submit_timeout: float = 10.0,
        settlement_currency: str = "USDT",
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        time_ns: Callable[[], int] = time.time_ns,
    ) -> None:
        from bt_api_binance.feeds.swap import BinanceRequestDataSwap

        if (
            type(feed) is not BinanceRequestDataSwap
            or getattr(feed, "exchange_name", None) != EXCHANGE_NAME
            or getattr(feed, "asset_type", None) != "SWAP"
        ):
            raise DirectWriteError("binance_direct_write_feed_invalid")
        for value in (poll_interval, drain_time_budget, query_timeout, submit_timeout):
            if type(value) not in (int, float) or not 0 < value <= 60:
                raise DirectWriteError("binance_direct_write_config_invalid")
        if type(max_queries_per_drain) is not int or not 1 <= max_queries_per_drain <= 64:
            raise DirectWriteError("binance_direct_write_config_invalid")
        if type(settlement_currency) is not str or not re.fullmatch(
            r"[A-Z0-9]{1,16}", settlement_currency
        ):
            raise DirectWriteError("binance_direct_write_config_invalid")
        self._feed = feed
        self._poll_interval = float(poll_interval)
        self._max_queries = max_queries_per_drain
        self._drain_budget = float(drain_time_budget)
        self._query_timeout = float(query_timeout)
        self._submit_timeout = float(submit_timeout)
        self._settlement_currency = settlement_currency
        self._clock = clock
        self._wall_clock = wall_clock
        self._lock = threading.RLock()
        self._events_lock = threading.Lock()
        self._events: deque[DirectExecutionEvent] = deque()
        self._sequence = 0
        self._dropped_events = 0
        self._reservations: dict[str, _Reserved] = {}
        self._watches: list[_Watch] = []
        self._counters: dict[str, int] = {}
        self._time_ns = time_ns
        self._time_lock = threading.Lock()
        self._server_time: Optional[tuple[float, dict[str, int]]] = None
        self._server_time_failed_at: Optional[float] = None

    # ------------------------------------------------------------------
    # session
    # ------------------------------------------------------------------
    def _environment(self) -> Optional[str]:
        try:
            proof = self._feed.get_environment_info()
        except Exception:
            return None
        if type(proof) is not dict or proof.get("verified") is not True:
            return None
        environment = proof.get("environment")
        if environment not in _ENVIRONMENTS:
            return None
        if proof.get("simulated") is not (environment != "production"):
            return None
        return environment

    def _credentials_present(self) -> bool:
        binding = getattr(self._feed, "_credential_binding", None)
        values = (getattr(binding, "public_key", None), getattr(binding, "private_key", None))
        return all(isinstance(value, str) and value.strip() for value in values)

    def session_generation(self) -> Optional[int]:
        """``1`` while the signed REST route is usable, else ``None``.

        Binance REST is stateless and the feed's credentials are fixed at
        construction, so one route has one session generation.
        """

        if not self._credentials_present() or self._environment() is None:
            return None
        return _SESSION_GENERATION

    def trading_day(self) -> Optional[str]:
        """UTC calendar date ``YYYYMMDD`` (USDⓈ-M perpetuals trade continuously)."""

        return _utc_day(self._wall_clock())

    def settlement_status(self) -> SettlementStatus:
        """Binance has no settlement-statement confirmation step."""

        return SettlementStatus.CONFIRMED

    def confirm_settlement(
        self, grant: WriteGrant, verifier: WriteGrantVerifier
    ) -> SettlementStatus:
        del grant, verifier  # never sends: there is nothing to confirm
        return SettlementStatus.CONFIRMED

    # ------------------------------------------------------------------
    # venue clock (public REST server time)
    # ------------------------------------------------------------------
    def server_time_observation(self) -> Optional[dict[str, int]]:
        """One venue server-time observation for SDK clock cross-checks.

        ``{"venue_epoch_ms", "local_sent_ns", "local_received_ns",
        "granularity_ms"}`` from the public ``GET /fapi/v1/time`` on the feed's
        configured (demo or production) host.  ``local_*`` are wall-clock
        ``time.time_ns()`` taken immediately before the request and right after
        the reply.  A success is cached for 60 s; any failure returns ``None``
        (retried after 5 s).
        """

        now = self._clock()
        with self._time_lock:
            cached = self._server_time
            if cached is not None and 0 <= now - cached[0] < _SERVER_TIME_TTL:
                return dict(cached[1])
            failed = self._server_time_failed_at
            if failed is not None and 0 <= now - failed < _SERVER_TIME_RETRY:
                return None
            try:
                observation = self._read_server_time()
            except Exception:
                observation = None
            if observation is None:
                self._server_time_failed_at = now
                return None
            self._server_time = (now, observation)
            self._server_time_failed_at = None
            return dict(observation)

    def _read_server_time(self) -> Optional[dict[str, int]]:
        if self._environment() is None:
            return None
        path, params, extra_data = self._feed._get_server_time()
        if path != _SERVER_TIME_PATH or params:
            return None
        sent_ns = self._time_ns()
        result = self._feed.request(
            path,
            params=params,
            extra_data=extra_data,
            timeout=self._query_timeout,
            is_sign=False,
            _max_retries=1,
        )
        received_ns = self._time_ns()
        venue_ms = _object(result).get("serverTime")
        if (
            type(venue_ms) is not int
            or not 10**12 <= venue_ms < 10**14
            or type(sent_ns) is not int
            or type(received_ns) is not int
            or received_ns < sent_ns
        ):
            return None
        return {
            "venue_epoch_ms": venue_ms,
            "local_sent_ns": sent_ns,
            "local_received_ns": received_ns,
            "granularity_ms": 1,
        }

    # ------------------------------------------------------------------
    # request validation and mapping (no network)
    # ------------------------------------------------------------------
    def _build_order(
        self, request: Any
    ) -> tuple[str, dict[str, Any], dict[str, Any], Optional[bool]]:
        from bt_api_base.order_quantity_units import validate_generic_order_quantity_units

        from bt_api_binance.order_request_mapping import map_order_request

        client_order_id = getattr(request, "client_order_id", None)
        if type(client_order_id) is not str or not _CLIENT_ORDER_ID.fullmatch(client_order_id):
            raise DirectWriteError(
                "binance_direct_client_order_id_invalid",
                "newClientOrderId must match ^[.A-Z:/a-z0-9_-]{1,36}$",
            )
        try:
            # The validator Binance declares for BINANCE___SWAP order units.
            validate_generic_order_quantity_units(EXCHANGE_NAME, request)
            mapped = map_order_request(request)
            symbol = mapped["symbol"]
            if (
                type(symbol) is not str
                or not _NATIVE_SYMBOL.fullmatch(symbol)
                or self._feed._params.get_symbol(symbol) != symbol
            ):
                raise ValueError("symbol must be the native Binance symbol (for example BTCUSDT)")
            positional = (
                "symbol",
                "vol",
                "price",
                "order_type",
                "offset",
                "post_only",
                "client_order_id",
            )
            options = {key: value for key, value in mapped.items() if key not in positional}
            path, params, extra_data = self._feed._make_order(
                symbol,
                mapped["vol"],
                mapped["price"],
                mapped["order_type"],
                mapped["offset"],
                mapped["post_only"],
                mapped["client_order_id"],
                None,
                **options,
            )
        except DirectWriteError:
            raise
        except Exception as exc:
            raise DirectWriteError("binance_direct_request_unrepresentable", _detail(exc)) from None
        if (
            params.get("newClientOrderId") != client_order_id
            or params.get("symbol") != symbol
            or params.get("quantity") != mapped["vol"]
            or params.get("type") not in _ORDER_TYPES
            or (params.get("type") == "LIMIT" and not params.get("price"))
            or any(value is None for value in params.values())
        ):
            raise DirectWriteError("binance_direct_request_unrepresentable", "native_params_invalid")
        return path, params, extra_data, _reduce_only(params.get("reduceOnly"))

    # ------------------------------------------------------------------
    # orders
    # ------------------------------------------------------------------
    def reserve_order(self, request: Any) -> DirectOrderReservation:
        # Unrepresentable requests fail here, before any identity or host marker.
        path, params, extra_data, reduce_only = self._build_order(request)
        with self._lock:
            generation = self.session_generation()
            if generation is None:
                raise DirectWriteError("binance_direct_session_unavailable")
            client_order_id = params["newClientOrderId"]
            if any(
                held.reservation.identity.client_order_id == client_order_id
                for held in self._reservations.values()
            ) or self._find_watch(client_order_id, None) is not None:
                raise DirectWriteError("binance_direct_client_order_id_in_use")
            identity = NativeOrderIdentity(
                exchange_name=EXCHANGE_NAME,
                client_order_id=client_order_id,
                fields={"symbol": params["symbol"], "trading_day": self.trading_day()},
                session_generation=generation,
            )
            reservation = DirectOrderReservation(
                identity=identity, symbol=params["symbol"], reservation_id=uuid4().hex
            )
            self._reservations[reservation.reservation_id] = _Reserved(
                reservation, path, params, extra_data, reduce_only
            )
            return reservation

    def release_reservation(self, reservation: DirectOrderReservation) -> None:
        with self._lock:
            self._reservations.pop(reservation.reservation_id, None)

    def _signed(self, path: str, params: dict[str, Any], extra_data: dict[str, Any], timeout: float) -> Any:
        return self._feed.request(
            path, params=params, extra_data=extra_data, timeout=timeout, is_sign=True
        )

    def submit_order(
        self,
        reservation: DirectOrderReservation,
        request: Any,
        grant: WriteGrant,
        verifier: WriteGrantVerifier,
    ) -> DirectSubmitResult:
        with self._lock:
            held = self._reservations.pop(reservation.reservation_id, None)
            if held is None or held.reservation != reservation:
                raise DirectWriteError("binance_direct_reservation_unknown")
            path, params, extra_data, reduce_only = self._build_order(request)
            if path != held.path or params != held.params:
                raise DirectWriteError("binance_direct_reservation_request_mismatch")
            generation = self.session_generation()
            if generation is None or generation != reservation.identity.session_generation:
                raise DirectWriteError("binance_direct_reservation_session_changed")
            verifier.consume(
                grant,
                exchange_name=EXCHANGE_NAME,
                operation=WriteOperation.PLACE,
                session_generation=generation,
            )
            watch = self._add_watch(
                reservation.identity,
                symbol=params["symbol"],
                order_id=None,
                reduce_only=reduce_only,
                fills_since_ms=None,
                origin="placed",
            )
            try:
                result = self._signed(path, params, extra_data, self._submit_timeout)
            except Exception as exc:
                code = _definite_reject_code(exc)
                if code is not None:
                    self._drop_watch(watch)
                    return DirectSubmitResult(
                        sent=False,
                        identity=reservation.identity,
                        error_code="binance_order_rejected",
                        detail=code,
                    )
                watch.next_due = 0.0
                raise BinanceDirectOutcomeUnknown(
                    "binance_direct_submit_outcome_unknown", type(exc).__name__
                ) from None
            order_id = self._ack_order_id(result, params["newClientOrderId"], params["symbol"])
            if order_id is None:
                watch.next_due = 0.0
                raise BinanceDirectOutcomeUnknown(
                    "binance_direct_submit_outcome_unknown", "acknowledgement_invalid"
                )
            watch.order_id = order_id
            watch.next_due = 0.0
            fields = dict(reservation.identity.fields)
            fields["order_id"] = order_id
            identity = NativeOrderIdentity(
                exchange_name=EXCHANGE_NAME,
                client_order_id=reservation.identity.client_order_id,
                fields=fields,
                session_generation=reservation.identity.session_generation,
            )
            watch.identity = identity
            return DirectSubmitResult(sent=True, identity=identity)

    @staticmethod
    def _ack_order_id(result: Any, client_order_id: Optional[str], symbol: str) -> Optional[str]:
        try:
            row = _object(result)
        except ValueError:
            return None
        order_id = _venue_id(row.get("orderId"))
        if (
            order_id is None
            or row.get("symbol") != symbol
            or (client_order_id is not None and row.get("clientOrderId") != client_order_id)
        ):
            return None
        return order_id

    def cancel_order(
        self,
        target: NativeOrderIdentity,
        symbol: str,
        grant: WriteGrant,
        verifier: WriteGrantVerifier,
    ) -> DirectSubmitResult:
        with self._lock:
            if type(target) is not NativeOrderIdentity or target.exchange_name != EXCHANGE_NAME:
                raise DirectWriteError("binance_direct_cancel_identity_foreign")
            fields = target.fields
            native = _text(fields.get("symbol")) or _text(symbol)
            if (
                native is None
                or native != symbol
                or not _NATIVE_SYMBOL.fullmatch(native)
                or self._feed._params.get_symbol(native) != native
            ):
                raise DirectWriteError("binance_direct_cancel_symbol_mismatch")
            order_id = _text(fields.get("order_id"))
            client_order_id = target.client_order_id
            if order_id is not None and _venue_id(order_id) is None:
                raise DirectWriteError("binance_direct_cancel_identity_incomplete")
            if client_order_id is not None and not _CLIENT_ORDER_ID.fullmatch(client_order_id):
                raise DirectWriteError("binance_direct_cancel_identity_incomplete")
            if order_id is None and client_order_id is None:
                raise DirectWriteError("binance_direct_cancel_identity_incomplete")
            generation = self.session_generation()
            if generation is None:
                raise DirectWriteError("binance_direct_session_unavailable")
            # One identity only: the venue order id when known, else the client id.
            if order_id is not None:
                path, params, extra_data = self._feed._cancel_order(native, order_id)
            else:
                path, params, extra_data = self._feed._cancel_order(
                    native, None, client_order_id=client_order_id
                )
            verifier.consume(
                grant,
                exchange_name=EXCHANGE_NAME,
                operation=WriteOperation.CANCEL,
                session_generation=generation,
            )
            watch = self._find_watch(client_order_id, order_id)
            if watch is None:
                watch = self._add_watch(
                    target,
                    symbol=native,
                    order_id=order_id,
                    reduce_only=None,
                    fills_since_ms=_utc_day_start_ms(self._wall_clock()),
                    origin="cancel_target",
                )
            try:
                result = self._signed(path, params, extra_data, self._submit_timeout)
            except Exception as exc:
                code = _definite_reject_code(exc)
                if code is not None:
                    return DirectSubmitResult(
                        sent=False,
                        identity=target,
                        error_code="binance_cancel_rejected",
                        detail=code,
                    )
                watch.next_due = 0.0
                raise BinanceDirectOutcomeUnknown(
                    "binance_direct_cancel_outcome_unknown", type(exc).__name__
                ) from None
            watch.next_due = 0.0
            if self._ack_order_id(result, None, native) is None:
                raise BinanceDirectOutcomeUnknown(
                    "binance_direct_cancel_outcome_unknown", "acknowledgement_invalid"
                )
            return DirectSubmitResult(sent=True, identity=target)

    # ------------------------------------------------------------------
    # watched orders (returns by bounded polling)
    # ------------------------------------------------------------------
    def _find_watch(self, client_order_id: Optional[str], order_id: Optional[str]) -> Optional[_Watch]:
        for watch in self._watches:
            if client_order_id is not None and watch.client_order_id == client_order_id:
                return watch
            if order_id is not None and watch.order_id == order_id:
                return watch
        return None

    def _add_watch(
        self,
        identity: NativeOrderIdentity,
        *,
        symbol: str,
        order_id: Optional[str],
        reduce_only: Optional[bool],
        fills_since_ms: Optional[int],
        origin: str,
    ) -> _Watch:
        watch = _Watch(
            identity=identity,
            symbol=symbol,
            client_order_id=identity.client_order_id,
            order_id=order_id,
            reduce_only=reduce_only,
            fills_since_ms=fills_since_ms,
            origin=origin,
        )
        self._watches.append(watch)
        return watch

    def _drop_watch(self, watch: _Watch) -> None:
        try:
            self._watches.remove(watch)
        except ValueError:
            pass

    def watch_order(self, identity: NativeOrderIdentity, symbol: str) -> None:
        """Watch an order this provider did not place (restored host marker).

        Only fills from the current UTC day are returned for such an order, the
        same horizon as a trading-day replay.
        """

        if type(identity) is not NativeOrderIdentity or identity.exchange_name != EXCHANGE_NAME:
            raise DirectWriteError("binance_direct_watch_identity_invalid")
        native = _text(identity.fields.get("symbol")) or _text(symbol)
        order_id = _text(identity.fields.get("order_id"))
        if native is None or (identity.client_order_id is None and order_id is None):
            raise DirectWriteError("binance_direct_watch_identity_invalid")
        with self._lock:
            if self._find_watch(identity.client_order_id, order_id) is None:
                self._add_watch(
                    identity,
                    symbol=native,
                    order_id=order_id,
                    reduce_only=None,
                    fills_since_ms=_utc_day_start_ms(self._wall_clock()),
                    origin="restored",
                )

    @property
    def watched_count(self) -> int:
        with self._lock:
            return len(self._watches)

    @property
    def counters(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)

    @property
    def dropped_events(self) -> int:
        return self._dropped_events

    def _bump(self, name: str) -> None:
        self._counters[name] = self._counters.get(name, 0) + 1

    def _enqueue(self, events: Iterable[DirectExecutionEvent]) -> None:
        with self._events_lock:
            for event in events:
                if len(self._events) >= _MAX_EVENTS:
                    self._events.popleft()
                    self._dropped_events += 1
                self._events.append(event)

    def _next_sequence(self) -> int:
        with self._events_lock:
            self._sequence += 1
            return self._sequence

    def drain_execution_events(self, max_events: int) -> tuple[DirectExecutionEvent, ...]:
        """Return queued returns; poll due watched orders when the queue is short.

        Polling performs bounded signed ``GET`` reads: at most
        ``max_queries_per_drain`` orders, each at most once per
        ``poll_interval``, within ``drain_time_budget`` seconds.
        """

        limit = max(1, int(max_events))
        with self._events_lock:
            short = len(self._events) < limit
        if short:
            with self._lock:
                self._poll_due()
        out: list[DirectExecutionEvent] = []
        with self._events_lock:
            while self._events and len(out) < limit:
                out.append(self._events.popleft())
        return tuple(out)

    def _poll_due(self) -> None:
        start = self._clock()
        due = [watch for watch in self._watches if watch.next_due <= start]
        due.sort(key=lambda watch: watch.next_due)
        for watch in due[: self._max_queries]:
            remaining = self._drain_budget - (self._clock() - start)
            if remaining <= 0:
                break
            self._poll_watch(watch, min(self._query_timeout, remaining))

    def _query_order_row(self, watch: _Watch, timeout: float) -> dict[str, Any]:
        if watch.order_id is not None:
            path, params, extra_data = self._feed._query_order(watch.symbol, watch.order_id)
        else:
            path, params, extra_data = self._feed._query_order(
                watch.symbol, None, client_order_id=watch.client_order_id
            )
        try:
            result = self._feed.request(
                path,
                params=params,
                extra_data=extra_data,
                timeout=timeout,
                is_sign=True,
                _max_retries=1,
            )
        except Exception as exc:
            if _native_error_code(exc) == _ORDER_NOT_FOUND_CODE:
                raise _OrderNotFound() from None
            raise
        return _object(result)

    def _fail(self, name: str, exc: BaseException) -> None:
        """Count a failed read with a finite reason (native code or error class)."""

        self._bump(name)
        reason = _native_error_code(exc) or type(exc).__name__
        self._bump(f"{name}:{reason[:64]}")

    def _poll_watch(self, watch: _Watch, timeout: float) -> None:
        now = self._clock()
        watch.next_due = now + self._poll_interval
        first = False
        order_event: Optional[DirectExecutionEvent] = None
        if watch.terminal_state is not None:
            # Terminal status never changes: only the fills are still owed.
            state, filled = watch.terminal_state, watch.terminal_filled
        else:
            try:
                row = self._query_order_row(watch, timeout)
            except _OrderNotFound:
                # Not (yet) known to Binance: keep watching with backoff; an
                # unknown send outcome is never turned into a rejection here.
                watch.not_found += 1
                backoff = self._poll_interval * (2 ** min(watch.not_found, 5))
                watch.next_due = now + min(backoff, _MAX_NOT_FOUND_BACKOFF)
                self._bump("order_not_found")
                return
            except Exception as exc:
                self._fail("order_query_failed", exc)
                return
            client_order_id = _text(row.get("clientOrderId"))
            order_id = _venue_id(row.get("orderId"))
            if (
                order_id is None
                or row.get("symbol") != watch.symbol
                or (watch.client_order_id is not None and client_order_id != watch.client_order_id)
                or (watch.order_id is not None and order_id != watch.order_id)
            ):
                self._bump("order_identity_mismatch")
                return
            if watch.order_id is None:
                watch.order_id = order_id
                fields = dict(watch.identity.fields)
                fields["order_id"] = order_id
                watch.identity = NativeOrderIdentity(
                    exchange_name=EXCHANGE_NAME,
                    client_order_id=watch.identity.client_order_id,
                    fields=fields,
                    session_generation=watch.identity.session_generation,
                )
            watch.not_found = 0
            created = _ms(row.get("time"))
            if created is not None:
                watch.created_ms = created
            reduce_only = _reduce_only(row.get("reduceOnly"))
            if reduce_only is not None:
                watch.reduce_only = reduce_only
            state = _text(row.get("status"))
            filled = _decimal(row.get("executedQty"))
            first = watch.last_key is None
            key = (state, filled)
            if key != watch.last_key:
                order_event = self._order_event(row, watch.identity, watch.reduce_only)
                watch.last_key = key
            if state in _TERMINAL_STATES:
                watch.terminal_state, watch.terminal_filled = state, filled
                watch.terminal_since = now
        trades: list[DirectExecutionEvent] = []
        # Fills follow ANY executed quantity not yet covered by emitted trades,
        # including an order already FILLED at its first observation.
        if filled is not None and filled > watch.trade_qty:
            try:
                trades = self._new_fills(watch, timeout, filled)
            except Exception as exc:
                self._fail("fills_query_failed", exc)
        events: list[DirectExecutionEvent] = []
        if order_event is not None and first:
            events.append(order_event)
        events.extend(trades)
        if order_event is not None and not first:
            events.append(order_event)
        self._enqueue(events)
        if watch.terminal_state is None:
            return
        if filled is None or watch.trade_qty >= filled:
            self._drop_watch(watch)
            return
        # Terminal with fills still owed: keep polling the fills (they lag the
        # order status).  Only an order older than the venue fill window, whose
        # fills can no longer be read, is released after a grace period.
        watch.fill_attempts += 1
        now_ms = int(self._wall_clock() * 1000)
        outside = watch.created_ms is not None and now_ms - watch.created_ms > _FILLS_WINDOW_MS
        if outside and now - (watch.terminal_since or now) >= _TERMINAL_FILL_GRACE:
            self._bump("fills_incomplete_outside_window")
            self._drop_watch(watch)
            return
        if watch.fill_attempts > _FILL_RETRY_FAST:
            backoff = self._poll_interval * (2 ** min(watch.fill_attempts - _FILL_RETRY_FAST, 5))
            watch.next_due = now + min(backoff, _MAX_FILL_BACKOFF)

    def _scoped_trade(
        self, row: Any, watch: _Watch, *, order_scoped: bool
    ) -> Optional[tuple[str, Decimal, dict[str, Any]]]:
        """``(trade id, qty, row)`` of one fill of ``watch`` or ``None``.

        The request already scopes ``symbol`` (and ``orderId`` when
        ``order_scoped``), so a row that omits those fields is attributed by
        the request; a row that states a different value is never attributed.
        """

        if type(row) is not dict:
            return None
        trade_id = _venue_id(row.get("id"))
        quantity = _decimal(row.get("qty"))
        if trade_id is None or quantity is None or quantity <= 0:
            return None
        row_order = row.get("orderId")
        if row_order is None:
            if not order_scoped:
                return None
        elif _venue_id(row_order) != watch.order_id:
            return None
        if row.get("symbol") not in (None, watch.symbol):
            return None
        scoped = dict(row)
        scoped["orderId"] = watch.order_id
        scoped["symbol"] = watch.symbol
        return trade_id, quantity, scoped

    def _new_fills(
        self, watch: _Watch, timeout: float, filled: Decimal
    ) -> list[DirectExecutionEvent]:
        path, params, extra_data = self._feed._get_deals(watch.symbol, _PAGE_LIMIT)
        params = dict(params)
        params["orderId"] = watch.order_id
        rows = _list(self._get(path, params, extra_data, timeout))
        if len(rows) >= _PAGE_LIMIT:
            raise ValueError("binance_fill_page_full")
        found: dict[str, tuple[int, Decimal, dict[str, Any]]] = {}
        for row in rows:
            scoped = self._scoped_trade(row, watch, order_scoped=True)
            if scoped is not None:
                trade_id, quantity, data = scoped
                found[trade_id] = (_ms(data.get("time")) or 0, quantity, data)
        covered = watch.trade_qty + sum(
            (item[1] for trade_id, item in found.items() if trade_id not in watch.trade_ids),
            Decimal(0),
        )
        now_ms = int(self._wall_clock() * 1000)
        if (
            covered < filled
            and watch.created_ms is not None
            and now_ms - watch.created_ms < _FILLS_WINDOW_MS - 60_000
        ):
            # Fallback that does not rely on the orderId filter: the symbol's
            # fills since the order was created, attributed by orderId here.
            extra = 0
            start_ms = max(watch.created_ms - 1_000, 0)
            for row in self._user_trades(watch.symbol, start_ms, timeout):
                scoped = self._scoped_trade(row, watch, order_scoped=False)
                if scoped is not None and scoped[0] not in found:
                    trade_id, quantity, data = scoped
                    found[trade_id] = (_ms(data.get("time")) or 0, quantity, data)
                    extra += 1
            if extra and any(trade_id not in watch.trade_ids for trade_id in found):
                self._bump("fills_from_window_query")
        fresh = sorted(
            (
                (timestamp, trade_id, data, quantity)
                for trade_id, (timestamp, quantity, data) in found.items()
                if trade_id not in watch.trade_ids
            ),
            key=lambda item: (item[0], int(item[1])),
        )
        events = []
        for timestamp, trade_id, row, quantity in fresh:
            watch.trade_ids.add(trade_id)
            watch.trade_qty += quantity
            if watch.fills_since_ms is not None and timestamp < watch.fills_since_ms:
                continue  # before this watch's horizon: counted, not replayed
            events.append(self._trade_event(row, watch.identity, watch.reduce_only))
        return events

    # ------------------------------------------------------------------
    # projection
    # ------------------------------------------------------------------
    def _order_event(
        self, row: Mapping[str, Any], identity: NativeOrderIdentity, reduce_only: Optional[bool]
    ) -> DirectExecutionEvent:
        state = _text(row.get("status"))
        side = _SIDES.get(_text(row.get("side")) or "")
        size = _decimal(row.get("origQty"))
        filled = _decimal(row.get("executedQty"))
        price = _decimal(row.get("price"))
        return DirectExecutionEvent(
            kind=DirectExecutionEventKind.ORDER,
            exchange_name=EXCHANGE_NAME,
            symbol=_text(row.get("symbol")) or "",
            identity=identity,
            exchange_order_id=_venue_id(row.get("orderId")),
            status=_STATUS.get(state or "", DirectOrderStatus.UNKNOWN),
            side=side,
            offset=_offset(_text(row.get("positionSide")), side, reduce_only),
            order_qty=None if size is None else float(size),
            filled_qty=None if filled is None else float(filled),
            remaining_qty=(
                None if size is None or filled is None else float(max(size - filled, Decimal(0)))
            ),
            limit_price=None if price is None or price <= 0 else float(price),
            trading_day=identity.fields.get("trading_day"),
            raw_status=state,
            session_generation=identity.session_generation,
            sequence=self._next_sequence(),
        )

    def _trade_event(
        self, row: Mapping[str, Any], identity: NativeOrderIdentity, reduce_only: Optional[bool]
    ) -> DirectExecutionEvent:
        side = _SIDES.get(_text(row.get("side")) or "")
        return DirectExecutionEvent(
            kind=DirectExecutionEventKind.TRADE,
            exchange_name=EXCHANGE_NAME,
            symbol=_text(row.get("symbol")) or "",
            identity=identity,
            exchange_order_id=_venue_id(row.get("orderId")),
            side=side,
            offset=_offset(_text(row.get("positionSide")), side, reduce_only),
            trade_id=_venue_id(row.get("id")),
            trade_price=_float(row.get("price")),
            trade_qty=_float(row.get("qty")),
            trade_time=_iso_from_ms(row.get("time")),
            trading_day=_day_from_ms(row.get("time")),
            session_generation=identity.session_generation,
            sequence=self._next_sequence(),
        )

    def _row_identity(
        self, row: Mapping[str, Any], client_order_id: Optional[str], day: Optional[str]
    ) -> NativeOrderIdentity:
        if client_order_id is not None and not _CLIENT_ORDER_ID.fullmatch(client_order_id):
            client_order_id = None
        order_id = _venue_id(row.get("orderId"))
        watch = self._find_watch(client_order_id, order_id)
        if watch is not None and watch.order_id in (None, order_id):
            fields = dict(watch.identity.fields)
            if order_id is not None:
                fields["order_id"] = order_id
            return NativeOrderIdentity(
                exchange_name=EXCHANGE_NAME,
                client_order_id=watch.identity.client_order_id,
                fields=fields,
                session_generation=watch.identity.session_generation,
            )
        fields: dict[str, Any] = {"symbol": _text(row.get("symbol"))}
        if day is not None:
            fields["trading_day"] = day
        if order_id is not None:
            fields["order_id"] = order_id
        return NativeOrderIdentity(
            exchange_name=EXCHANGE_NAME,
            client_order_id=client_order_id,
            fields=fields,
            session_generation=_SESSION_GENERATION,
        )

    # ------------------------------------------------------------------
    # read-only account facts (D62-05/13/16/22)
    # ------------------------------------------------------------------
    def _get(self, path: str, params: dict[str, Any], extra_data: dict[str, Any], timeout: float) -> Any:
        return self._feed.request(
            path,
            params=params,
            extra_data=extra_data,
            timeout=timeout,
            is_sign=True,
            _max_retries=1,
        )

    def account_facts(
        self,
        *,
        positions: bool = True,
        active_orders: bool = True,
        trades: bool = False,
        balance: bool = True,
        all_orders: bool = False,
        timeout: float = 5.0,
        symbols: Optional[Iterable[str]] = None,
    ) -> DirectAccountFacts:
        """One read-only observation of the USDⓈ-M account (never raises for reads).

        ``allOrders`` and ``userTrades`` require a symbol.  ``orders`` and
        ``trades`` are therefore read for the explicit ``symbols`` scope plus
        every symbol with a working order, a position or a watched order; they
        are complete only when ``symbols`` is given (otherwise the blockers
        ``all_orders_symbol_scope_unproven`` / ``trades_symbol_scope_unproven``
        are reported, because a symbol traded earlier today and now flat could
        be missed).
        """

        bounded = float(timeout) if type(timeout) in (int, float) and timeout > 0 else 5.0
        bounded = min(bounded, _MAX_FACTS_TIMEOUT)
        now = self._wall_clock()
        day = _utc_day(now)
        day_start_ms = _utc_day_start_ms(now)
        observed = (
            datetime.fromtimestamp(now, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        blockers: list[str] = []
        generation = self.session_generation()
        scope_given: Optional[set[str]] = None
        if symbols is not None:
            try:
                scope_given = {str(item) for item in symbols}
            except TypeError:
                scope_given = None
            if scope_given is not None and any(
                not _NATIVE_SYMBOL.fullmatch(item) for item in scope_given
            ):
                scope_given = None
                blockers.append("symbol_scope_invalid")
        if generation is None:
            return DirectAccountFacts(
                exchange_name=EXCHANGE_NAME,
                trading_day=day,
                session_generation=None,
                observed_at_utc=observed,
                positions=None,
                active_orders=None,
                trades=None,
                balance=None,
                complete=False,
                blockers=("session_unavailable",),
                orders=None,
            )

        with self._lock:
            account: Optional[dict[str, Any]] = None
            if positions or balance:
                try:
                    path, params, extra_data = self._feed._get_account()
                    account = _object(self._get(path, params, extra_data, bounded))
                    if (
                        type(account.get("assets")) is not list
                        or type(account.get("positions")) is not list
                        or type(account.get("multiAssetsMargin")) is not bool
                    ):
                        raise ValueError("binance_account_shape_invalid")
                except Exception:
                    account = None
                    blockers.append("account_query_incomplete")

            position_facts: Optional[tuple[DirectPositionFact, ...]] = None
            if positions and account is not None:
                try:
                    position_facts = self._position_facts(account["positions"])
                except Exception:
                    blockers.append("positions_query_incomplete")

            balance_fact: Optional[DirectBalanceFact] = None
            if balance and account is not None:
                if account["multiAssetsMargin"] is not False:
                    blockers.append("balance_multi_asset_semantics_unavailable")
                else:
                    try:
                        balance_fact = self._balance_fact(account["assets"])
                        if balance_fact is None:
                            blockers.append("balance_currency_absent")
                    except Exception:
                        blockers.append("balance_projection_invalid")

            working: Optional[list[dict[str, Any]]] = None
            if active_orders or all_orders:
                try:
                    path, params, extra_data = self._feed._get_open_orders(None)
                    working = _list(self._get(path, params, extra_data, bounded))
                except Exception:
                    blockers.append("orders_query_incomplete")
            order_facts: Optional[tuple[DirectExecutionEvent, ...]] = None
            if active_orders and working is not None:
                try:
                    order_facts = tuple(self._account_order_events(working, watch_working=True))
                except Exception:
                    blockers.append("orders_projection_invalid")

            scope: set[str] = set(scope_given or ())
            scope.update(row.get("symbol") for row in working or () if type(row.get("symbol")) is str)
            scope.update(fact.symbol for fact in position_facts or ())
            scope.update(watch.symbol for watch in self._watches)
            scope = {item for item in scope if _NATIVE_SYMBOL.fullmatch(item)}

            order_index: dict[str, tuple[Optional[str], Optional[str], Optional[bool]]] = {}

            def _index(rows: Iterable[dict[str, Any]]) -> None:
                for row in rows:
                    order_id = _venue_id(row.get("orderId"))
                    if order_id is not None:
                        order_index[order_id] = (
                            _text(row.get("clientOrderId")),
                            _day_from_ms(row.get("time")),
                            _reduce_only(row.get("reduceOnly")),
                        )

            _index(working or ())
            every_order: Optional[tuple[DirectExecutionEvent, ...]] = None
            if all_orders:
                if scope_given is None:
                    blockers.append("all_orders_symbol_scope_unproven")
                if working is not None:
                    try:
                        merged: dict[str, dict[str, Any]] = {}
                        for symbol in sorted(scope):
                            for row in self._all_orders(symbol, day_start_ms, bounded):
                                merged[str(row.get("orderId"))] = row
                        for row in working:
                            merged[str(row.get("orderId"))] = row  # the open row is newer
                        _index(merged.values())
                        every_order = tuple(
                            self._account_order_events(merged.values(), watch_working=False)
                        )
                    except Exception:
                        blockers.append("orders_history_query_incomplete")

            trade_facts: Optional[tuple[DirectExecutionEvent, ...]] = None
            if trades:
                if scope_given is None:
                    blockers.append("trades_symbol_scope_unproven")
                try:
                    projected: list[DirectExecutionEvent] = []
                    for symbol in sorted(scope):
                        projected.extend(
                            self._account_trade_events(
                                self._user_trades(symbol, day_start_ms, bounded), order_index
                            )
                        )
                    trade_facts = tuple(projected)
                except Exception:
                    blockers.append("trades_query_incomplete")

        return DirectAccountFacts(
            exchange_name=EXCHANGE_NAME,
            trading_day=day,
            session_generation=generation,
            observed_at_utc=observed,
            positions=position_facts,
            active_orders=order_facts,
            trades=trade_facts,
            balance=balance_fact,
            complete=not blockers,
            blockers=tuple(blockers),
            orders=every_order,
        )

    def _all_orders(self, symbol: str, day_start_ms: int, timeout: float) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        next_id: Optional[int] = None
        for _page in range(_MAX_PAGES):
            if next_id is None:
                path, params, extra_data = self._feed._get_all_orders(
                    symbol, None, day_start_ms, None, _PAGE_LIMIT
                )
            else:
                path, params, extra_data = self._feed._get_all_orders(
                    symbol, next_id, None, None, _PAGE_LIMIT
                )
            page = _list(self._get(path, params, extra_data, timeout))
            rows.extend(page)
            if len(page) < _PAGE_LIMIT:
                return rows
            ids = [_ms(row.get("orderId")) for row in page]
            if any(item is None for item in ids):
                raise ValueError("binance_order_page_cursor_invalid")
            next_id = max(ids) + 1  # type: ignore[type-var]
        raise ValueError("binance_order_page_limit_exceeded")

    def _user_trades(self, symbol: str, day_start_ms: int, timeout: float) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        from_id: Optional[int] = None
        for _page in range(_MAX_PAGES):
            if from_id is None:
                path, params, extra_data = self._feed._get_deals(
                    symbol, _PAGE_LIMIT, day_start_ms
                )
            else:
                # fromId cannot be combined with startTime.
                path, params, extra_data = self._feed._get_deals(
                    symbol, _PAGE_LIMIT, from_id=from_id
                )
            page = _list(self._get(path, params, extra_data, timeout))
            rows.extend(page)
            if len(page) < _PAGE_LIMIT:
                return rows
            ids = [_ms(row.get("id")) for row in page]
            if any(item is None for item in ids):
                raise ValueError("binance_trade_page_cursor_invalid")
            from_id = max(ids) + 1  # type: ignore[type-var]
        raise ValueError("binance_trade_page_limit_exceeded")

    @staticmethod
    def _position_facts(rows: list[Any]) -> tuple[DirectPositionFact, ...]:
        totals: dict[tuple[str, str], Decimal] = {}
        for row in rows:
            if type(row) is not dict:
                raise ValueError("binance_position_row_invalid")
            symbol = _text(row.get("symbol"))
            position_side = _text(row.get("positionSide"))
            quantity = _decimal(row.get("positionAmt"))
            if symbol is None or quantity is None:
                raise ValueError("binance_position_row_invalid")
            if quantity == 0:
                continue
            if position_side in ("LONG", "SHORT"):
                key = (symbol, position_side.lower())
                totals[key] = totals.get(key, Decimal(0)) + abs(quantity)
            elif position_side == "BOTH":
                key = (symbol, "net")
                totals[key] = totals.get(key, Decimal(0)) + quantity  # signed: + long, - short
            else:
                raise ValueError("binance_position_side_invalid")
        return tuple(
            DirectPositionFact(symbol=symbol, venue=None, side=side, total=float(total))
            for (symbol, side), total in sorted(totals.items())
            if total != 0
        )

    def _balance_fact(self, assets: list[Any]) -> Optional[DirectBalanceFact]:
        matches = [
            row
            for row in assets
            if type(row) is dict and row.get("asset") == self._settlement_currency
        ]
        if len(matches) > 1:
            raise ValueError("binance_balance_currency_duplicated")
        if not matches:
            return None
        row = matches[0]
        return DirectBalanceFact(
            currency=self._settlement_currency,
            balance=_float(row.get("marginBalance")),
            available=_float(row.get("availableBalance")),
            margin=_float(row.get("positionInitialMargin")),
            frozen=_float(row.get("openOrderInitialMargin")),
            position_profit=_float(row.get("unrealizedProfit")),
        )

    def _account_order_events(
        self, rows: Iterable[dict[str, Any]], *, watch_working: bool
    ) -> list[DirectExecutionEvent]:
        events = []
        auto = sum(1 for watch in self._watches if watch.origin == "account_facts")
        for row in rows:
            symbol = _text(row.get("symbol"))
            order_id = _venue_id(row.get("orderId"))
            if symbol is None or order_id is None:
                raise ValueError("binance_order_row_invalid")
            identity = self._row_identity(
                row, _text(row.get("clientOrderId")), _day_from_ms(row.get("time"))
            )
            reduce_only = _reduce_only(row.get("reduceOnly"))
            events.append(self._order_event(row, identity, reduce_only))
            if (
                watch_working
                and _text(row.get("status")) not in _TERMINAL_STATES
                and self._find_watch(identity.client_order_id, order_id) is None
            ):
                if auto >= _MAX_AUTO_WATCHED:
                    self._bump("auto_watch_overflow")
                    continue
                watch = self._add_watch(
                    identity,
                    symbol=symbol,
                    order_id=order_id,
                    reduce_only=reduce_only,
                    fills_since_ms=_utc_day_start_ms(self._wall_clock()),
                    origin="account_facts",
                )
                watch.last_key = (_text(row.get("status")), _decimal(row.get("executedQty")))
                watch.created_ms = _ms(row.get("time"))
                watch.next_due = self._clock() + self._poll_interval
                auto += 1
        return events

    def _account_trade_events(
        self,
        rows: Iterable[dict[str, Any]],
        orders: Mapping[str, tuple[Optional[str], Optional[str], Optional[bool]]],
    ) -> list[DirectExecutionEvent]:
        """Project fills; ``orders`` maps orderId to (client id, creation day, reduceOnly).

        ``userTrades`` rows carry no client id, so it comes from an order row
        read in the same observation, or from a watched order; otherwise the
        identity has the venue order id only.
        """

        events = []
        for row in rows:
            order_id = _venue_id(row.get("orderId"))
            if _venue_id(row.get("id")) is None or order_id is None:
                raise ValueError("binance_trade_row_invalid")
            watch = self._find_watch(None, order_id)
            client_order_id, day, reduce_only = orders.get(order_id, (None, None, None))
            if watch is not None:
                client_order_id = client_order_id or watch.client_order_id
                if watch.reduce_only is not None:
                    reduce_only = watch.reduce_only
            identity = self._row_identity(row, client_order_id, day)
            events.append(self._trade_event(row, identity, reduce_only))
        return events

    def account_reference(self) -> Optional[str]:
        """Secret-free account reference: a hash of the environment and API key.

        Never the key itself; the secret is not used.
        """

        binding = getattr(self._feed, "_credential_binding", None)
        api_key = getattr(binding, "public_key", None)
        environment = self._environment()
        if not isinstance(api_key, str) or not api_key.strip() or environment is None:
            return None
        material = f"binance-direct-account-reference.v1|{environment}|{api_key}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    def close(self) -> None:
        with self._lock:
            self._watches.clear()
            self._reservations.clear()


def create_binance_direct_write_provider(feed: Any) -> BinanceDirectWriteProvider:
    """Factory for ``bt_api.direct_write_providers``: wrap the selected USDⓈ-M feed."""

    return BinanceDirectWriteProvider(feed)


def register_binance_direct_write_provider(registry: Any) -> None:
    """Register the Binance USDⓈ-M direct write provider factory."""

    register = getattr(registry, "register", None)
    if not callable(register):
        raise TypeError("registry must expose register(exchange_name, factory)")
    register(BINANCE_DIRECT_WRITE_EXCHANGE, create_binance_direct_write_provider)
