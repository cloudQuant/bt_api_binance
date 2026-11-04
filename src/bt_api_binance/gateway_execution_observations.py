"""Gateway execution observations for the USDⓈ-M Demo provider (iteration 60).

``BinanceUsdMAccountSessionProvider`` uses this reader to implement the
optional Gateway account-session capability ``read_execution_observations`` /
``confirm_execution_observations``. Everything here is read-only and comes from
the provider's signed ``GET`` routes for the explicitly configured symbols:

* **Fills** come only from ``/fapi/v1/userTrades`` rows (one row, one fill),
  paged forward with a ``fromId`` cursor. An order's cumulative quantity is
  never turned into a fill.
* **Orders** come from a recent ``/fapi/v1/allOrders`` window, the symbol's
  ``/fapi/v1/openOrders`` set and ``/fapi/v1/order`` (query one order whose fill
  arrived first, or that left the open set). The first observation of an order
  in a session is queued before any of its fills, so the Gateway can route the
  fill by its order; later status changes follow the fills of the same poll.
* **Identity.** ``order_id``/``trade_id`` are opaque ids issued by the injected
  observation issuer (the SDK's durable ``DurableOrderCorrelationIssuer`` is a
  ``bt_api_base`` ``ManagedOrderObservationIssuer``) from a transient private
  identity bound to the account; the same venue fact has the same id in every
  read and after a restart with the same issuer, so Base fact ids are stable
  and the Gateway journal deduplicates redeliveries. Native ids stay here.
* **Fees.** ``commission``/``commissionAsset`` of a fill is its fee when the
  commission is non-negative. A negative commission (a rebate) cannot be
  represented by the Base contract: the fee is unknown (``None``) and counted.
* **Scope.** Rows of another symbol, of a symbol the latest account read
  reported as isolated margin, or that cannot be represented are refused with
  a finite counter code; malformed rows fail the read closed instead.

A reader belongs to one provider ``connect`` generation; the queue is never
shared across generations. Nothing is confirmed until the worker confirms it;
unconfirmed observations are returned again, byte-for-byte the same facts.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from itertools import islice
from types import MappingProxyType
from typing import Any

from bt_api_base.account_protocol import AccountKey, AccountResourceKey
from bt_api_base.execution_query_protocol import ExecutionOrderRecord, ExecutionTradeRecord
from bt_api_base.execution_row_observation_protocol import (
    AccountExecutionOrderObservation,
    AccountExecutionTradeObservation,
    execution_observation_fact_digest,
    execution_observation_fact_id,
)
from bt_api_base.market_protocol import MarketInstrumentKey

PROVIDER_NAME = "binance"
PRODUCT_TYPE = "usdm_perpetual"
RESOURCE = AccountResourceKey(product_type=PRODUCT_TYPE, margin_pool="cross")
# Binance USDⓈ-M order and fill quantities are base-asset amounts (the same
# unit the provider's account positions declare).
QTY_UNIT = "base_asset"

PAGE_LIMIT = 500
MAX_PENDING = 8192
MAX_SYMBOLS = 10
MAX_TRACKED_ORDERS_PER_SYMBOL = 256
MAX_LOOKUPS_PER_SYMBOL = 32
WINDOW_OVERLAP_MS = 60_000
MIN_LOOKBACK_SECONDS = 60
# Binance refuses time windows longer than seven days.
MAX_LOOKBACK_SECONDS = 6 * 86_400
MAX_POLL_INTERVAL_SECONDS = 300.0
_MAX_REMEMBERED = 65_536

COUNTER_CODES = frozenset(
    {
        "EXECUTION_ROW_INSTRUMENT_OUT_OF_SCOPE",
        "EXECUTION_ROW_MARGIN_POOL_OUT_OF_SCOPE",
        "EXECUTION_ORDER_UNREPRESENTABLE",
        "EXECUTION_FEE_REBATE_UNREPRESENTABLE",
        "EXECUTION_FEE_UNAVAILABLE",
        "EXECUTION_MARGIN_POOL_UNVERIFIED",
        "EXECUTION_POLL_INTERRUPTED",
    }
)

_ORDER_ID = re.compile(r"sdk-order-observation-v1-[0-9a-f]{64}\Z", re.ASCII)
_TRADE_ID = re.compile(r"sdk-trade-observation-v1-[0-9a-f]{64}\Z", re.ASCII)
_VENUE_DECIMAL = re.compile(r"-?[0-9]{1,40}(?:\.[0-9]{1,40})?\Z", re.ASCII)
_ORDER_TYPE = re.compile(r"[A-Z][A-Z_]{0,31}\Z", re.ASCII)
_TERMINAL = frozenset(
    {
        "filled",
        "canceled",
        "partially_filled_canceled",
        "partially_filled_terminal",
        "rejected",
        "terminal_unfilled",
    }
)


class ExecutionReadIssue(Exception):
    """Internal finite failure; the provider re-raises it as its own error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _Refused(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _invalid() -> ExecutionReadIssue:
    return ExecutionReadIssue("EXECUTION_ROW_INVALID")


def _native_id(value: Any) -> int:
    if type(value) is int and 0 <= value <= 2**63 - 1:
        return value
    raise _invalid()


def _decimal_text(value: Any, *, positive: bool = False, signed: bool = False) -> str:
    if type(value) is not str or not _VENUE_DECIMAL.fullmatch(value):
        raise _invalid()
    if value.startswith("-") and not signed:
        raise _invalid()
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise _invalid() from None
    if positive and number <= 0:
        raise _invalid()
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        text = "0"
    return text


def _utc_from_ms(value: Any) -> str:
    if type(value) is not int or not 0 < value <= 253402300799999:
        raise _invalid()
    return (
        datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _side(value: Any) -> str:
    if value == "BUY":
        return "buy"
    if value == "SELL":
        return "sell"
    raise _invalid()


def _position(value: Any, side: str) -> tuple[str, str | None]:
    # One-way mode (BOTH) cannot state whether a row opened or closed.
    if value == "BOTH":
        return "unavailable", None
    if value == "LONG":
        return ("open" if side == "buy" else "close"), "long"
    if value == "SHORT":
        return ("open" if side == "sell" else "close"), "short"
    raise _invalid()


def _status(value: Any, filled_positive: bool) -> str:
    if value == "NEW":
        return "open"
    if value == "PARTIALLY_FILLED":
        return "partially_filled"
    if value == "FILLED":
        return "filled"
    if value == "CANCELED":
        return "partially_filled_canceled" if filled_positive else "canceled"
    if value == "REJECTED":
        return "partially_filled_terminal" if filled_positive else "rejected"
    if value in {"EXPIRED", "EXPIRED_IN_MATCH"}:
        return "partially_filled_terminal" if filled_positive else "terminal_unfilled"
    raise _invalid()


def _client_order_id(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if (
        type(value) is not str
        or len(value) > 64
        or value != value.strip()
        or not value.isascii()
        or not value.isprintable()
    ):
        raise _invalid()
    return value


def _row(value: Any) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise _invalid()
    return value


def _rows(value: Any, limit: int) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) > limit:
        raise _invalid()
    return [_row(item) for item in value]


def _private_identity(kind: str, **fields: str) -> str:
    return json.dumps(
        {"schema": f"bt_api_binance.usdm_{kind}_observation_identity.v1", **fields},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass
class _SymbolCursor:
    initialized: bool = False
    order_window_start_ms: int | None = None
    trade_from_id: int | None = None
    trade_window_start_ms: int | None = None
    tracked: dict[int, None] = field(default_factory=dict)


@dataclass
class _OrderView:
    native: int
    observation: AccountExecutionOrderObservation | None
    terminal: bool
    refusal: str | None = None
    filled: Decimal = Decimal(0)


@dataclass
class _SymbolBatch:
    first_orders: list[AccountExecutionOrderObservation]
    fills: list[AccountExecutionTradeObservation]
    later_orders: list[AccountExecutionOrderObservation]
    known: set[int]
    tracked: dict[int, None]
    cursor: _SymbolCursor
    counts: dict[str, int]

    @property
    def items(self) -> list[Any]:
        return [*self.first_orders, *self.fills, *self.later_orders]


class BinanceUsdMExecutionReader:
    """Pending execution observations of one provider generation."""

    def __init__(
        self,
        *,
        account_key: AccountKey,
        symbols: tuple[str, ...],
        lookback_seconds: int,
        poll_interval_seconds: float,
        observation_issuer: Any,
        request: Callable[[str, Mapping[str, str], float], Any],
        exchange_now_ms: Callable[[float], int],
        utc_now: Callable[[], str],
        monotonic: Callable[[], float],
        margin_pools: Callable[[], Mapping[str, bool] | None],
    ) -> None:
        self._account_key = account_key
        self._symbols = symbols
        self._lookback_ms = lookback_seconds * 1000
        self._poll_interval = float(poll_interval_seconds)
        self._issuer = observation_issuer
        self._request = request
        self._exchange_now_ms = exchange_now_ms
        self._utc_now = utc_now
        self._monotonic = monotonic
        self._margin_pools = margin_pools
        self._pending: deque[Any] = deque()
        self._outstanding = 0
        self._next_poll: float | None = None
        self._rotation = 0
        self._cursors = {symbol: _SymbolCursor() for symbol in symbols}
        self._queued: OrderedDict[str, str] = OrderedDict()
        self._known: OrderedDict[tuple[str, int], None] = OrderedDict()
        self._refused: OrderedDict[tuple[str, ...], None] = OrderedDict()
        self._counters: dict[str, int] = {}

    @property
    def counters(self) -> Mapping[str, int]:
        return MappingProxyType(dict(self._counters))

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def read(self, *, limit: int, deadline: float) -> tuple[Any, ...]:
        if type(limit) is not int or not 1 <= limit <= MAX_PENDING:
            raise ExecutionReadIssue("INVALID_LIMIT")
        self._outstanding = 0
        if not self._pending:
            now = self._monotonic()
            if self._next_poll is None or now >= self._next_poll:
                self._next_poll = now + self._poll_interval
                self._poll(deadline)
        items = tuple(islice(self._pending, limit))
        self._outstanding = len(items)
        return items

    def confirm(self, count: int) -> None:
        if type(count) is not int or not 1 <= count <= self._outstanding:
            raise ExecutionReadIssue("EXECUTION_CONFIRM_INVALID")
        for _ in range(count):
            self._pending.popleft()
        self._outstanding -= count

    # -- polling --------------------------------------------------------------

    def _poll(self, deadline: float) -> None:
        margins = self._margin_pools()
        if margins is None:
            # No successful account read in this generation: the symbols'
            # margin mode, and so the resource of their rows, is unproven.
            raise ExecutionReadIssue("EXECUTION_MARGIN_POOL_UNVERIFIED")
        now_ms = self._exchange_now_ms(deadline)
        observed = self._utc_now()
        count = len(self._symbols)
        start = self._rotation
        self._rotation = (start + 1) % count
        for offset in range(count):
            symbol = self._symbols[(start + offset) % count]
            isolated = margins.get(symbol)
            if type(isolated) is not bool:
                self._bump("EXECUTION_MARGIN_POOL_UNVERIFIED")
                continue
            try:
                batch = self._poll_symbol(
                    symbol, isolated=isolated, now_ms=now_ms, observed=observed, deadline=deadline
                )
            except Exception:
                if self._pending:
                    self._bump("EXECUTION_POLL_INTERRUPTED")
                    return
                raise
            if len(self._pending) + len(batch.items) > MAX_PENDING:
                return
            self._commit(symbol, batch)

    def _commit(self, symbol: str, batch: _SymbolBatch) -> None:
        for item in batch.items:
            self._remember(self._queued, execution_observation_fact_id(item), _digest(item))
            self._pending.append(item)
        for native in batch.known:
            self._remember(self._known, (symbol, native), None)
        self._cursors[symbol] = batch.cursor
        batch.cursor.tracked = batch.tracked
        for code, amount in batch.counts.items():
            self._counters[code] = self._counters.get(code, 0) + amount

    def _poll_symbol(
        self, symbol: str, *, isolated: bool, now_ms: int, observed: str, deadline: float
    ) -> _SymbolBatch:
        cursor = self._cursors[symbol]
        counts: dict[str, int] = {}
        refused_now: set[tuple[str, ...]] = set()

        def refuse(code: str, key: tuple[str, ...]) -> None:
            if key in self._refused or key in refused_now:
                return
            refused_now.add(key)
            self._remember(self._refused, key, None)
            counts[code] = counts.get(code, 0) + 1

        lookback_start = now_ms - self._lookback_ms
        window_start = cursor.order_window_start_ms if cursor.initialized else lookback_start
        assert window_start is not None
        recent = _rows(
            self._request(
                "all_orders",
                {
                    "symbol": symbol,
                    "startTime": str(window_start),
                    "endTime": str(now_ms),
                    "limit": str(PAGE_LIMIT),
                },
                deadline,
            ),
            PAGE_LIMIT,
        )
        if len(recent) >= PAGE_LIMIT:
            # A full time-window page cannot prove the window is complete.
            raise ExecutionReadIssue("EXECUTION_LOOKBACK_TRUNCATED")
        open_rows = _rows(
            self._request("open_orders", {"symbol": symbol}, deadline),
            MAX_TRACKED_ORDERS_PER_SYMBOL + 1,
        )
        if len(open_rows) > MAX_TRACKED_ORDERS_PER_SYMBOL:
            raise ExecutionReadIssue("EXECUTION_TRACKED_ORDERS_EXCEEDED")
        if cursor.trade_from_id is None:
            trade_start = cursor.trade_window_start_ms
            if trade_start is None:
                trade_start = lookback_start
            fills = _rows(
                self._request(
                    "user_trades",
                    {
                        "symbol": symbol,
                        "startTime": str(trade_start),
                        "endTime": str(now_ms),
                        "limit": str(PAGE_LIMIT),
                    },
                    deadline,
                ),
                PAGE_LIMIT,
            )
            if len(fills) >= PAGE_LIMIT:
                raise ExecutionReadIssue("EXECUTION_LOOKBACK_TRUNCATED")
        else:
            trade_start = None
            fills = _rows(
                self._request(
                    "user_trades",
                    {
                        "symbol": symbol,
                        "fromId": str(cursor.trade_from_id),
                        "limit": str(PAGE_LIMIT),
                    },
                    deadline,
                ),
                PAGE_LIMIT,
            )

        views: list[_OrderView] = []
        for row in [*recent, *open_rows]:
            views.append(self._order_view(row, symbol, isolated, observed))
        present = {view.native for view in views}
        lookups = MAX_LOOKUPS_PER_SYMBOL
        for native in list(cursor.tracked):
            if native in present:
                continue
            if lookups == 0:
                break
            lookups -= 1
            views.append(self._lookup(symbol, native, isolated, observed, deadline))
            present.add(native)

        # Fills: in-scope rows in trade-id order; out-of-order or duplicate
        # rows give the same facts as an ordered page.
        parsed: list[tuple[int, int, dict[str, Any]]] = []
        for row in fills:
            if row.get("symbol") != symbol:
                trade_key = repr(row.get("id"))
                refuse("EXECUTION_ROW_INSTRUMENT_OUT_OF_SCOPE", ("trade", symbol, trade_key))
                continue
            parsed.append((_native_id(row.get("id")), _native_id(row.get("orderId")), row))
        parsed.sort(key=lambda entry: (entry[0], entry[1]))
        trades: list[tuple[AccountExecutionTradeObservation, str | None]] = []
        next_from = cursor.trade_from_id
        stopped_at: int | None = None
        for trade_native, order_native, row in parsed:
            if isolated:
                refuse(
                    "EXECUTION_ROW_MARGIN_POOL_OUT_OF_SCOPE",
                    ("trade", symbol, str(order_native), str(trade_native)),
                )
                continue
            if (symbol, order_native) not in self._known and order_native not in present:
                if lookups == 0:
                    stopped_at = trade_native
                    break
                lookups -= 1
                views.append(self._lookup(symbol, order_native, isolated, observed, deadline))
                present.add(order_native)
            trades.append(self._trade(row, symbol, trade_native, order_native, observed))
        if stopped_at is not None:
            next_from = stopped_at
        elif parsed:
            next_from = max(entry[0] for entry in parsed) + 1
        if cursor.trade_from_id is not None and next_from is not None:
            # A venue page below the cursor never moves it backwards.
            next_from = max(next_from, cursor.trade_from_id)

        # Orders: dedupe within the poll and against facts already queued in
        # this session; the most advanced view decides tracking.
        views.sort(key=lambda view: (view.native, view.terminal, view.filled))
        first_orders: list[AccountExecutionOrderObservation] = []
        later_orders: list[AccountExecutionOrderObservation] = []
        seen_facts: set[str] = set()
        tracked = dict(cursor.tracked)
        known: set[int] = set()
        first_seen: set[int] = set()
        for view in views:
            known.add(view.native)
            if view.refusal is not None:
                refuse(view.refusal, ("order", symbol, str(view.native)))
                tracked.pop(view.native, None)
                continue
            if view.terminal:
                tracked.pop(view.native, None)
            elif view.native not in tracked:
                tracked[view.native] = None
            observation = view.observation
            assert observation is not None
            fact = execution_observation_fact_id(observation)
            digest = _digest(observation)
            if fact in seen_facts or self._queued.get(fact) == digest:
                continue
            seen_facts.add(fact)
            # Only the first observation of an order new to this session goes
            # ahead of the fills (it carries the route); the rest follow them.
            if (symbol, view.native) in self._known or view.native in first_seen:
                later_orders.append(observation)
            else:
                first_seen.add(view.native)
                first_orders.append(observation)
        if len(tracked) > MAX_TRACKED_ORDERS_PER_SYMBOL:
            raise ExecutionReadIssue("EXECUTION_TRACKED_ORDERS_EXCEEDED")
        trade_facts: set[str] = set()
        unique_trades = []
        for trade, fee_note in trades:
            fact = execution_observation_fact_id(trade)
            if fact in trade_facts or self._queued.get(fact) == _digest(trade):
                continue
            trade_facts.add(fact)
            unique_trades.append(trade)
            if fee_note is not None:
                counts[fee_note] = counts.get(fee_note, 0) + 1

        next_cursor = _SymbolCursor(
            initialized=True,
            order_window_start_ms=max(window_start, now_ms - WINDOW_OVERLAP_MS),
            trade_from_id=next_from,
            trade_window_start_ms=(
                None if next_from is not None or trade_start is None
                else max(trade_start, now_ms - WINDOW_OVERLAP_MS)
            ),
        )
        return _SymbolBatch(
            first_orders, unique_trades, later_orders, known, tracked, next_cursor, counts
        )

    def _lookup(
        self, symbol: str, native: int, isolated: bool, observed: str, deadline: float
    ) -> _OrderView:
        row = self._request("order", {"symbol": symbol, "orderId": str(native)}, deadline)
        view = self._order_view(_row(row), symbol, isolated, observed)
        if view.native != native:
            raise _invalid()
        return view

    # -- projection -----------------------------------------------------------

    def _order_view(
        self, row: dict[str, Any], symbol: str, isolated: bool, observed: str
    ) -> _OrderView:
        native = _native_id(row.get("orderId"))
        if row.get("symbol") != symbol:
            return _OrderView(native, None, True, "EXECUTION_ROW_INSTRUMENT_OUT_OF_SCOPE")
        if isolated:
            return _OrderView(native, None, True, "EXECUTION_ROW_MARGIN_POOL_OUT_OF_SCOPE")
        side = _side(row.get("side"))
        effect, position_side = _position(row.get("positionSide"), side)
        order_type = row.get("origType") if "origType" in row else row.get("type")
        if type(order_type) is not str or not _ORDER_TYPE.fullmatch(order_type):
            raise _invalid()
        quantity = _decimal_text(row.get("origQty"))
        filled = _decimal_text(row.get("executedQty"))
        if Decimal(quantity) <= 0:
            # e.g. a close-all order: the Base record needs a positive quantity.
            return _OrderView(native, None, True, "EXECUTION_ORDER_UNREPRESENTABLE")
        if Decimal(filled) > Decimal(quantity):
            raise _invalid()
        status = _status(row.get("status"), Decimal(filled) > 0)
        price = _decimal_text(row.get("price"))
        client = _client_order_id(row.get("clientOrderId"))
        try:
            record = ExecutionOrderRecord(
                resource=RESOURCE,
                instrument=self._instrument(symbol),
                order_id=self._order_id(symbol, native),
                client_order_id=client,
                intent_binding="unresolved" if client is None else "verified",
                side=side,
                position_effect=effect,
                position_side=position_side,
                position_side_status="unavailable" if position_side is None else "verified",
                order_type=order_type.lower(),
                status=status,
                quantity=quantity,
                filled_quantity=filled,
                qty_unit=QTY_UNIT,
                limit_price=None if Decimal(price) == 0 else price,
                price_currency=None,
                price_currency_status="unavailable",
                created_at_utc=_utc_from_ms(row.get("time")),
                created_at_status="verified",
                observed_at_utc=observed,
            )
            observation = AccountExecutionOrderObservation(self._account_key, record)
        except (TypeError, ValueError):
            raise _invalid() from None
        return _OrderView(native, observation, status in _TERMINAL, filled=Decimal(filled))

    def _trade(
        self,
        row: dict[str, Any],
        symbol: str,
        trade_native: int,
        order_native: int,
        observed: str,
    ) -> tuple[AccountExecutionTradeObservation, str | None]:
        side = _side(row.get("side"))
        buyer = row.get("buyer")
        if buyer is not None and (type(buyer) is not bool or buyer != (side == "buy")):
            raise _invalid()
        effect, position_side = _position(row.get("positionSide"), side)
        quantity = _decimal_text(row.get("qty"), positive=True)
        price = _decimal_text(row.get("price"), positive=True)
        fee: str | None = None
        currency: str | None = None
        note: str | None = None
        commission = row.get("commission")
        asset = row.get("commissionAsset")
        if commission in (None, "") or asset in (None, ""):
            note = "EXECUTION_FEE_UNAVAILABLE"
        else:
            amount = _decimal_text(commission, signed=True)
            if type(asset) is not str or not re.fullmatch(r"[A-Z0-9]{1,16}", asset):
                raise _invalid()
            if Decimal(amount) < 0:
                note = "EXECUTION_FEE_REBATE_UNREPRESENTABLE"
            else:
                fee, currency = amount, asset
        try:
            record = ExecutionTradeRecord(
                resource=RESOURCE,
                instrument=self._instrument(symbol),
                trade_id=self._trade_id(symbol, order_native, trade_native),
                order_id=self._order_id(symbol, order_native),
                order_binding="provider_order_identity",
                side=side,
                position_effect=effect,
                position_side=position_side,
                position_side_status="unavailable" if position_side is None else "verified",
                quantity=quantity,
                qty_unit=QTY_UNIT,
                price=price,
                price_currency=None,
                price_currency_status="unavailable",
                traded_at_utc=_utc_from_ms(row.get("time")),
                traded_at_status="verified",
                observed_at_utc=observed,
            )
            observation = AccountExecutionTradeObservation(self._account_key, record, fee, currency)
        except (TypeError, ValueError):
            raise _invalid() from None
        return observation, note

    def _instrument(self, symbol: str) -> MarketInstrumentKey:
        key = self._account_key
        return MarketInstrumentKey(
            provider=key.provider,
            venue=key.venue,
            environment=key.environment,
            product_type=PRODUCT_TYPE,
            instrument_id=symbol,
            native_symbol=symbol,
        )

    def _order_id(self, symbol: str, native: int) -> str:
        identity = _private_identity("order", symbol=symbol, order_id=str(native))
        return self._issue("issue_order_observation_id", identity, _ORDER_ID)

    def _trade_id(self, symbol: str, order_native: int, trade_native: int) -> str:
        identity = _private_identity(
            "trade", symbol=symbol, order_id=str(order_native), trade_id=str(trade_native)
        )
        return self._issue("issue_trade_observation_id", identity, _TRADE_ID)

    def _issue(self, method: str, identity: str, pattern: re.Pattern[str]) -> str:
        key = self._account_key
        try:
            issued = getattr(self._issuer, method)(
                PROVIDER_NAME, key.environment, key.account_key_id, identity
            )
        except Exception:
            raise ExecutionReadIssue("EXECUTION_IDENTITY_UNAVAILABLE") from None
        if type(issued) is not str or not pattern.fullmatch(issued):
            raise ExecutionReadIssue("EXECUTION_IDENTITY_UNAVAILABLE")
        return issued

    def _bump(self, code: str) -> None:
        self._counters[code] = self._counters.get(code, 0) + 1

    @staticmethod
    def _remember(store: OrderedDict, key: Any, value: Any) -> None:
        store[key] = value
        store.move_to_end(key)
        while len(store) > _MAX_REMEMBERED:
            store.popitem(last=False)


def _digest(observation: Any) -> str:
    return execution_observation_fact_digest(observation)


__all__ = [
    "BinanceUsdMExecutionReader",
    "COUNTER_CODES",
    "ExecutionReadIssue",
    "MAX_SYMBOLS",
    "MAX_LOOKBACK_SECONDS",
    "MAX_POLL_INTERVAL_SECONDS",
    "MIN_LOOKBACK_SECONDS",
    "PAGE_LIMIT",
]
