"""Iteration 62: Binance USDⓈ-M direct write provider (fakes only, no network).

Every test drives a real ``BinanceRequestDataSwap`` whose ``request`` is
replaced by a scripted venue and whose HTTP layer raises if anything tries to
reach the network.  Evidence level: UNIT/FAKE (the coordinator test is
INTEGRATION_SIM against the in-process SDK coordinator).
"""

from __future__ import annotations

import time
import tomllib
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from bt_api_base.containers.requestdatas.request_data import RequestData
from bt_api_base.direct_write_protocol import (
    DirectExecutionEventKind,
    DirectOrderStatus,
    DirectWriteError,
    NativeOrderIdentity,
    SettlementStatus,
    WriteAdmissionDenied,
    WriteGrant,
    WriteOperation,
)
from bt_api_base.error import ServerError
from bt_api_base.exceptions import RequestTimeoutError
from bt_api_binance.direct_write_provider import (
    BinanceDirectOutcomeUnknown,
    BinanceDirectWriteProvider,
    create_binance_direct_write_provider,
)
from bt_api_binance.feeds.spot import BinanceRequestDataSpot
from bt_api_binance.feeds.swap import BinanceRequestDataSwap

ROUTE = "BINANCE___SWAP"
SYMBOL = "BTCUSDT"
ORDER_ID = 4611875134427365377
API_KEY = "unit-binance-key-9d41"
API_SECRET = "unit-binance-secret-2a7f"
CID = "bt0a1b2c3d4e5fs1"
WALL = datetime(2026, 11, 6, 3, 0, tzinfo=timezone.utc).timestamp()
DAY_START_MS = int(datetime(2026, 11, 6, tzinfo=timezone.utc).timestamp() * 1000)
PLACE = "POST /fapi/v1/order"
CANCEL = "DELETE /fapi/v1/order"
QUERY = "GET /fapi/v1/order"
TRADES = "GET /fapi/v1/userTrades"
OPEN = "GET /fapi/v1/openOrders"
ALL = "GET /fapi/v1/allOrders"
ACCOUNT = "GET /fapi/v2/account"
SERVER_TIME = "GET /fapi/v1/time"


def _no_network(*_args, **_kwargs):
    raise AssertionError("network access is forbidden in these tests")


def _feed(**credentials) -> BinanceRequestDataSwap:
    values = {"public_key": API_KEY, "private_key": API_SECRET}
    values.update(credentials)
    feed = BinanceRequestDataSwap(None, environment="demo", **values)
    feed.http_request = _no_network
    return feed


class Venue:
    """Scripted Binance signed REST replies; records every call in ``calls``."""

    def __init__(self, feed, calls):
        self.feed = feed
        self.calls = calls
        self.handlers: dict[str, object] = {}
        feed.request = self.request

    def on(self, route, *replies):
        self.handlers[route] = deque(replies)

    def request(self, path, params=None, body=None, extra_data=None, timeout=10, is_sign=True,
                **kwargs):
        assert is_sign is (path != SERVER_TIME)  # only the public clock read is unsigned
        self.calls.append(("request", path, dict(params or {})))
        replies = self.handlers.get(path)
        if not replies:
            raise AssertionError(f"unexpected request {path}")
        reply = replies.popleft() if len(replies) > 1 else replies[0]
        if callable(reply):
            reply = reply(dict(params or {}))
        if isinstance(reply, BaseException):
            raise reply
        if isinstance(reply, dict) and isinstance(reply.get("code"), int) and reply["code"] < 0:
            raise self.feed.translate_error(reply)
        return RequestData(reply, extra_data)


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class Verifier:
    def __init__(self, calls, deny=False):
        self.calls = calls
        self.deny = deny

    def consume(self, grant, *, exchange_name, operation, session_generation):
        self.calls.append(("consume", exchange_name, operation, session_generation))
        if self.deny:
            raise WriteAdmissionDenied("write_grant_invalid_or_consumed")


def _grant(operation=WriteOperation.PLACE):
    return WriteGrant(ROUTE, operation, 1, "grant-unit", 1)


def _req(**overrides):
    values = dict(
        symbol=SYMBOL,
        side=SimpleNamespace(value="buy"),
        order_type=SimpleNamespace(value="limit"),
        quantity=Decimal("0.002"),
        price=Decimal("60000"),
        time_in_force="GTC",
        reduce_only=False,
        quantity_unit="base",
        position_side=None,
        offset=None,
        position_id=None,
        position_mode=None,
        client_order_id=CID,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _order(status="NEW", executed="0", cid=CID, order_id=ORDER_ID, position_side="LONG",
           reduce_only=False, side="BUY", qty="0.002"):
    return {
        "orderId": order_id,
        "symbol": SYMBOL,
        "status": status,
        "clientOrderId": cid,
        "price": "60000",
        "avgPrice": "0",
        "origQty": qty,
        "executedQty": executed,
        "type": "LIMIT",
        "timeInForce": "GTC",
        "reduceOnly": reduce_only,
        "side": side,
        "positionSide": position_side,
        "time": DAY_START_MS + 3_600_000,
        "updateTime": DAY_START_MS + 3_600_000,
    }


def _trade(trade_id, qty, order_id=ORDER_ID, position_side="LONG", side="BUY", offset_ms=0):
    return {
        "id": trade_id,
        "orderId": order_id,
        "symbol": SYMBOL,
        "side": side,
        "positionSide": position_side,
        "price": "60001.5",
        "qty": qty,
        "time": DAY_START_MS + 3_700_000 + offset_ms,
    }


@pytest.fixture
def env():
    calls: list = []
    feed = _feed()
    venue = Venue(feed, calls)
    clock = Clock()
    provider = BinanceDirectWriteProvider(feed, clock=clock, wall_clock=lambda: WALL)
    yield SimpleNamespace(feed=feed, venue=venue, calls=calls, clock=clock, provider=provider)
    feed._http_client.close()


def _requests(calls):
    return [call for call in calls if call[0] == "request"]


# ----------------------------------------------------------------- factory


def test_factory_wraps_only_the_exact_swap_feed():
    feed = _feed()
    try:
        assert isinstance(create_binance_direct_write_provider(feed), BinanceDirectWriteProvider)
    finally:
        feed._http_client.close()
    spot = BinanceRequestDataSpot(None, environment="demo")
    try:
        for wrong in (object(), spot):
            with pytest.raises(DirectWriteError) as info:
                create_binance_direct_write_provider(wrong)
            assert info.value.code == "binance_direct_write_feed_invalid"
    finally:
        spot._http_client.close()


def test_entry_point_is_declared_for_the_swap_route():
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    group = pyproject["project"]["entry-points"]["bt_api.direct_write_providers"]
    assert group == {
        ROUTE: "bt_api_binance.direct_write_provider:create_binance_direct_write_provider"
    }


def test_session_trading_day_and_settlement(env):
    assert env.provider.session_generation() == 1
    assert env.provider.trading_day() == "20261106"
    assert env.provider.settlement_status() is SettlementStatus.CONFIRMED
    bare = _feed(private_key=None)
    try:
        provider = BinanceDirectWriteProvider(bare)
        assert provider.session_generation() is None
        with pytest.raises(DirectWriteError) as info:
            provider.reserve_order(_req())
        assert info.value.code == "binance_direct_session_unavailable"
        assert provider._reservations == {}
    finally:
        bare._http_client.close()


# ----------------------------------------------------------------- reserve


def test_reserve_binds_client_order_id_symbol_and_utc_day(env):
    reservation = env.provider.reserve_order(_req())
    identity = reservation.identity
    assert identity.exchange_name == ROUTE and identity.client_order_id == CID
    assert dict(identity.fields) == {"symbol": SYMBOL, "trading_day": "20261106"}
    assert identity.session_generation == 1 and reservation.symbol == SYMBOL
    assert env.calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"quantity_unit": "contracts"},
        {"quantity_unit": "lots"},
        {"symbol": "BTC-USDT"},  # not the native symbol
        {"symbol": "btcusdt"},
        {"time_in_force": "GFD"},
        {"time_in_force": "GTD"},  # needs goodTillDate, not representable
        {"time_in_force": "post_only"},
        {"offset": "close_today", "reduce_only": True, "side": SimpleNamespace(value="sell")},
        {"position_id": "ticket-1"},
        {"price": None},  # limit without a price
        {"position_mode": "dual_side"},
    ],
)
def test_unrepresentable_request_fails_before_any_reservation(env, overrides):
    with pytest.raises(DirectWriteError) as info:
        env.provider.reserve_order(_req(**overrides))
    assert info.value.code == "binance_direct_request_unrepresentable"
    assert env.provider._reservations == {}
    assert env.calls == []


@pytest.mark.parametrize("bad", ["has space", "x" * 37, "café", "", "a+b", "a#b"])
def test_client_order_id_rules_refuse_instead_of_rewriting(env, bad):
    with pytest.raises(DirectWriteError) as info:
        env.provider.reserve_order(_req(client_order_id=bad))
    assert info.value.code == "binance_direct_client_order_id_invalid"
    assert env.provider._reservations == {}


def test_client_order_id_is_sent_unchanged_and_not_reused(env):
    cid = "A.b:c/d_e-f" + "9" * 25  # 36 characters from the permitted set
    env.venue.on(PLACE, _order(cid=cid))
    reservation = env.provider.reserve_order(_req(client_order_id=cid))
    with pytest.raises(DirectWriteError) as info:
        env.provider.reserve_order(_req(client_order_id=cid))
    assert info.value.code == "binance_direct_client_order_id_in_use"
    result = env.provider.submit_order(
        reservation, _req(client_order_id=cid), _grant(), Verifier(env.calls)
    )
    assert result.sent is True
    (_, path, params) = _requests(env.calls)[0]
    assert path == PLACE and params["newClientOrderId"] == cid and params["symbol"] == SYMBOL
    assert params["quantity"] == "0.002" and params["price"] == "60000"
    assert params["type"] == "LIMIT" and params["timeInForce"] == "GTC"


# ------------------------------------------------------------------ submit


def test_verifier_is_consumed_immediately_before_the_single_send(env):
    env.venue.on(PLACE, _order())
    reservation = env.provider.reserve_order(_req())
    result = env.provider.submit_order(reservation, _req(), _grant(), Verifier(env.calls))
    assert [call[0] for call in env.calls] == ["consume", "request"]
    assert env.calls[0][1:] == (ROUTE, WriteOperation.PLACE, 1)
    assert result.sent is True and result.identity.fields["order_id"] == str(ORDER_ID)


def test_denied_grant_never_reaches_the_venue(env):
    env.venue.on(PLACE, _order())
    reservation = env.provider.reserve_order(_req())
    with pytest.raises(WriteAdmissionDenied):
        env.provider.submit_order(reservation, _req(), _grant(), Verifier(env.calls, deny=True))
    assert _requests(env.calls) == []
    assert env.provider.watched_count == 0


def test_request_changed_after_reservation_is_not_sent(env):
    reservation = env.provider.reserve_order(_req())
    with pytest.raises(DirectWriteError) as info:
        env.provider.submit_order(
            reservation, _req(quantity=Decimal("1")), _grant(), Verifier(env.calls)
        )
    assert info.value.code == "binance_direct_reservation_request_mismatch"
    assert env.calls == []


def test_definite_venue_rejection_is_not_sent(env):
    env.venue.on(PLACE, {"code": -2019, "msg": "Margin is insufficient."})
    reservation = env.provider.reserve_order(_req())
    result = env.provider.submit_order(reservation, _req(), _grant(), Verifier(env.calls))
    assert result.sent is False
    assert result.error_code == "binance_order_rejected" and result.detail == "-2019"
    assert env.provider.watched_count == 0


@pytest.mark.parametrize(
    "failure",
    [
        RequestTimeoutError(ROUTE, timeout=10),
        ServerError(venue=ROUTE, status=503, response={"code": -2019}),
        {"code": -1007, "msg": "Timeout waiting for response from backend server."},
        ConnectionResetError("reset after write"),
    ],
)
def test_failure_after_send_is_an_unknown_outcome(env, failure):
    env.venue.on(PLACE, failure)
    reservation = env.provider.reserve_order(_req())
    with pytest.raises(BinanceDirectOutcomeUnknown) as info:
        env.provider.submit_order(reservation, _req(), _grant(), Verifier(env.calls))
    assert info.value.code == "binance_direct_submit_outcome_unknown"
    assert not isinstance(info.value, DirectWriteError)
    assert env.provider.watched_count == 1


def test_sdk_coordinator_reports_sent_true_false_and_unknown():
    direct_write = pytest.importorskip("bt_api_py.direct_write")
    write_admission = pytest.importorskip("bt_api_py.write_admission")
    calls: list = []
    feed = _feed()
    try:
        venue = Venue(feed, calls)
        provider = BinanceDirectWriteProvider(feed, clock=Clock(), wall_clock=lambda: WALL)
        coordinator = direct_write.DirectWriteCoordinator(
            write_admission.WriteAdmission({ROUTE: True}), lambda _name: provider
        )
        port = SimpleNamespace(commit=lambda record: f"marker-{record.identity.client_order_id}")
        venue.on(PLACE, RequestTimeoutError(ROUTE, timeout=10))
        unknown = coordinator.place(ROUTE, _req(client_order_id="u1"), commit_port=port, host_scope="t")
        assert unknown.sent is None and unknown.error_code == "direct_submit_outcome_unknown"
        venue.on(PLACE, {"code": -2019, "msg": "Margin is insufficient."})
        rejected = coordinator.place(ROUTE, _req(client_order_id="r1"), commit_port=port, host_scope="t")
        assert rejected.sent is False and rejected.error_code == "binance_order_rejected"
        venue.on(PLACE, _order(cid="s1"))
        sent = coordinator.place(ROUTE, _req(client_order_id="s1"), commit_port=port, host_scope="t")
        assert sent.sent is True and sent.identity.fields["order_id"] == str(ORDER_ID)
        venue.on(QUERY, lambda params: (
            _order(cid="s1")
            if params.get("orderId") == str(ORDER_ID)
            else {"code": -2013, "msg": "Order does not exist."}
        ))
        polled = coordinator.poll_events(ROUTE)
        assert len(polled) == 1
        assert polled[0].matched is True and polled[0].marker_id == "marker-s1"
        assert polled[0].event.status is DirectOrderStatus.ACCEPTED
    finally:
        feed._http_client.close()


# ------------------------------------------------------------------ cancel


def _target(**fields):
    base = {"symbol": SYMBOL, "trading_day": "20261106"}
    base.update(fields)
    return NativeOrderIdentity(ROUTE, CID, base, 1)


def test_cancel_uses_the_venue_order_id_when_known_else_the_client_id(env):
    env.venue.on(CANCEL, _order(status="CANCELED"))
    result = env.provider.cancel_order(
        _target(order_id=str(ORDER_ID)), SYMBOL, _grant(WriteOperation.CANCEL), Verifier(env.calls)
    )
    assert result.sent is True
    assert [call[0] for call in env.calls] == ["consume", "request"]
    assert env.calls[0][2] is WriteOperation.CANCEL
    assert env.calls[1][2] == {"symbol": SYMBOL, "orderId": str(ORDER_ID)}
    env.calls.clear()
    env.provider.cancel_order(_target(), SYMBOL, _grant(WriteOperation.CANCEL), Verifier(env.calls))
    assert env.calls[1][2] == {"symbol": SYMBOL, "origClientOrderId": CID}


def test_cancel_refusals_happen_before_consume(env):
    cases = [
        (NativeOrderIdentity(ROUTE, None, {"symbol": SYMBOL}), SYMBOL,
         "binance_direct_cancel_identity_incomplete"),
        (_target(), "ETHUSDT", "binance_direct_cancel_symbol_mismatch"),
        (NativeOrderIdentity("OKX___SWAP", "1", {}), SYMBOL, "binance_direct_cancel_identity_foreign"),
    ]
    for target, symbol, code in cases:
        with pytest.raises(DirectWriteError) as info:
            env.provider.cancel_order(target, symbol, _grant(WriteOperation.CANCEL), Verifier(env.calls))
        assert info.value.code == code
    assert env.calls == []
    with pytest.raises(WriteAdmissionDenied):
        env.provider.cancel_order(
            _target(), SYMBOL, _grant(WriteOperation.CANCEL), Verifier(env.calls, deny=True)
        )
    assert _requests(env.calls) == []


def test_cancel_outcomes(env):
    env.venue.on(CANCEL, {"code": -2011, "msg": "Unknown order sent."})
    rejected = env.provider.cancel_order(
        _target(), SYMBOL, _grant(WriteOperation.CANCEL), Verifier(env.calls)
    )
    assert rejected.sent is False and rejected.error_code == "binance_cancel_rejected"
    env.venue.on(CANCEL, RequestTimeoutError(ROUTE, timeout=10))
    with pytest.raises(BinanceDirectOutcomeUnknown) as info:
        env.provider.cancel_order(_target(), SYMBOL, _grant(WriteOperation.CANCEL), Verifier(env.calls))
    assert info.value.code == "binance_direct_cancel_outcome_unknown"


# ----------------------------------------------------------------- returns


def _place(env, cid=CID, order_id=ORDER_ID, **overrides):
    env.venue.on(PLACE, _order(cid=cid, order_id=order_id))
    reservation = env.provider.reserve_order(_req(client_order_id=cid, **overrides))
    return env.provider.submit_order(
        reservation, _req(client_order_id=cid, **overrides), _grant(), Verifier(env.calls)
    )


def test_polling_projects_orders_and_fills_once_and_stops_at_terminal(env):
    _place(env)
    env.venue.on(QUERY, _order("NEW", "0"))
    (accepted,) = env.provider.drain_execution_events(10)
    assert accepted.kind is DirectExecutionEventKind.ORDER
    assert accepted.status is DirectOrderStatus.ACCEPTED and accepted.offset == "open"
    assert accepted.identity.client_order_id == CID
    assert accepted.exchange_order_id == str(ORDER_ID) and accepted.order_qty == 0.002

    queries = len(_requests(env.calls))
    assert env.provider.drain_execution_events(10) == ()
    assert len(_requests(env.calls)) == queries

    env.clock.now += 1.0
    env.venue.on(QUERY, _order("PARTIALLY_FILLED", "0.001"))
    env.venue.on(TRADES, [_trade(701, "0.001")])
    trade, partial = env.provider.drain_execution_events(10)
    assert trade.kind is DirectExecutionEventKind.TRADE
    assert (trade.trade_id, trade.trade_qty, trade.trade_price) == ("701", 0.001, 60001.5)
    assert trade.side == "buy" and trade.offset == "open"
    assert partial.status is DirectOrderStatus.PARTIALLY_FILLED
    fills_call = [c for c in _requests(env.calls) if c[1] == TRADES][-1]
    assert fills_call[2]["orderId"] == str(ORDER_ID) and fills_call[2]["symbol"] == SYMBOL

    env.clock.now += 1.0
    assert env.provider.drain_execution_events(10) == ()

    env.clock.now += 1.0
    env.venue.on(QUERY, _order("FILLED", "0.002"))
    env.venue.on(TRADES, [_trade(701, "0.001"), _trade(702, "0.001", offset_ms=5)])
    second, filled = env.provider.drain_execution_events(10)
    assert second.trade_id == "702" and filled.status is DirectOrderStatus.FILLED
    assert env.provider.watched_count == 0
    assert len({e.dedup_key() for e in (accepted, trade, partial, second, filled)}) == 5
    env.clock.now += 10.0
    before = len(_requests(env.calls))
    assert env.provider.drain_execution_events(10) == ()
    assert len(_requests(env.calls)) == before


@pytest.mark.parametrize(
    "status,expected",
    [
        ("EXPIRED", DirectOrderStatus.CANCELLED),
        ("EXPIRED_IN_MATCH", DirectOrderStatus.CANCELLED),
        ("CANCELED", DirectOrderStatus.CANCELLED),
        ("REJECTED", DirectOrderStatus.REJECTED),
        ("NEW_INSURANCE", DirectOrderStatus.UNKNOWN),
    ],
)
def test_status_mapping(env, status, expected):
    _place(env)
    env.venue.on(QUERY, _order(status, "0"))
    (event,) = env.provider.drain_execution_events(10)
    assert event.status is expected and event.raw_status == status
    terminal = status != "NEW_INSURANCE"
    assert env.provider.watched_count == (0 if terminal else 1)


def test_offset_comes_from_position_side_or_reduce_only_never_guessed(env):
    _place(env)
    env.venue.on(QUERY, _order("PARTIALLY_FILLED", "0.001", position_side="BOTH"))
    env.venue.on(TRADES, [_trade(701, "0.001", position_side="BOTH")])
    events = env.provider.drain_execution_events(10)
    assert len(events) == 2 and {event.offset for event in events} == {None}
    _place(env, cid="reduce1", order_id=7, side=SimpleNamespace(value="sell"), reduce_only=True)
    env.venue.on(QUERY, _order("NEW", "0", cid="reduce1", order_id=7, position_side="BOTH",
                               reduce_only=True, side="SELL"))
    env.clock.now += 1.0
    events = [e for e in env.provider.drain_execution_events(10) if e.identity.client_order_id == "reduce1"]
    assert len(events) == 1 and events[0].offset == "close" and events[0].side == "sell"
    sell_close = env.provider._order_event(
        _order(position_side="LONG", side="SELL"), events[0].identity, None
    )
    assert sell_close.offset == "close"


def test_unknown_outcome_not_found_keeps_watching_without_inventing_events(env):
    env.venue.on(PLACE, RequestTimeoutError(ROUTE, timeout=10))
    reservation = env.provider.reserve_order(_req())
    with pytest.raises(BinanceDirectOutcomeUnknown):
        env.provider.submit_order(reservation, _req(), _grant(), Verifier(env.calls))
    env.venue.on(QUERY, {"code": -2013, "msg": "Order does not exist."})
    assert env.provider.drain_execution_events(10) == ()
    assert env.provider.watched_count == 1
    assert env.provider.counters["order_not_found"] == 1
    query = _requests(env.calls)[-1]
    assert query[1] == QUERY and query[2] == {"symbol": SYMBOL, "origClientOrderId": CID}


def test_queries_per_drain_are_bounded(env):
    for index in range(6):
        _place(env, cid=f"c{index}", order_id=100 + index)
    env.venue.on(QUERY, lambda params: _order(
        "NEW", "0", cid=f"c{int(params['orderId']) - 100}", order_id=int(params["orderId"])
    ))
    before = len(_requests(env.calls))
    env.provider.drain_execution_events(100)
    assert len(_requests(env.calls)) - before == 4


# ----------------------------------------------------------- account facts


def _script_account(venue):
    venue.on(ACCOUNT, {
        "multiAssetsMargin": False,
        "assets": [
            {"asset": "BNB", "marginBalance": "1"},
            {"asset": "USDT", "marginBalance": "1000.5", "availableBalance": "800",
             "positionInitialMargin": "150", "openOrderInitialMargin": "50",
             "unrealizedProfit": "3.5"},
        ],
        "positions": [
            {"symbol": SYMBOL, "positionSide": "LONG", "positionAmt": "0.003"},
            {"symbol": SYMBOL, "positionSide": "SHORT", "positionAmt": "-0.001"},
            {"symbol": "ETHUSDT", "positionSide": "BOTH", "positionAmt": "-0.5"},
            {"symbol": "SOLUSDT", "positionSide": "BOTH", "positionAmt": "0.000"},
        ],
    })
    venue.on(OPEN, [_order("NEW", "0", cid="w1", order_id=11)])
    venue.on(ALL, lambda params: [
        _order("CANCELED", "0", cid="h1", order_id=12),
        _order("NEW", "0", cid="w1", order_id=11),
    ] if params["symbol"] == SYMBOL else [])
    venue.on(TRADES, lambda params: [_trade(901, "0.001", order_id=12)]
             if params["symbol"] == SYMBOL else [])


def test_account_facts_complete_with_explicit_symbol_scope(env):
    _script_account(env.venue)
    facts = env.provider.account_facts(trades=True, all_orders=True, symbols=[SYMBOL], timeout=30)
    assert facts.complete is True and facts.blockers == ()
    assert facts.trading_day == "20261106" and facts.session_generation == 1
    assert [(p.symbol, p.side, p.total) for p in facts.positions] == [
        (SYMBOL, "long", 0.003),
        (SYMBOL, "short", 0.001),
        ("ETHUSDT", "net", -0.5),
    ]
    (working,) = facts.active_orders
    assert working.identity.client_order_id == "w1"
    assert {e.exchange_order_id for e in facts.orders} == {"11", "12"}
    (trade,) = facts.trades
    assert trade.trade_id == "901" and trade.identity.client_order_id == "h1"
    assert trade.identity.fields["trading_day"] == "20261106"
    assert facts.balance.currency == "USDT" and facts.balance.balance == 1000.5
    assert facts.balance.available == 800.0 and facts.balance.margin == 150.0
    queried = sorted({c[2]["symbol"] for c in _requests(env.calls) if c[1] == ALL})
    assert queried == [SYMBOL, "ETHUSDT"]  # explicit scope plus position symbols
    first_all = [c for c in _requests(env.calls) if c[1] == ALL][0]
    assert first_all[2]["startTime"] == DAY_START_MS
    assert env.provider.watched_count == 1


def test_account_facts_without_symbol_scope_is_not_complete(env):
    _script_account(env.venue)
    facts = env.provider.account_facts(trades=True, all_orders=True)
    assert facts.complete is False
    assert facts.blockers == (
        "all_orders_symbol_scope_unproven",
        "trades_symbol_scope_unproven",
    )
    assert facts.orders is not None and facts.trades is not None  # observed, not complete
    plain = env.provider.account_facts()
    assert plain.complete is True  # positions, working orders, balance need no scope


def test_account_facts_incomplete_sections_are_named(env):
    _script_account(env.venue)
    env.venue.on(TRADES, RequestTimeoutError(ROUTE, timeout=5))
    facts = env.provider.account_facts(trades=True, symbols=[SYMBOL])
    assert facts.complete is False and facts.blockers == ("trades_query_incomplete",)
    env.venue.on(ACCOUNT, {"multiAssetsMargin": True, "assets": [], "positions": []})
    facts = env.provider.account_facts()
    assert facts.complete is False
    assert facts.blockers == ("balance_multi_asset_semantics_unavailable",)
    assert facts.balance is None and facts.positions == ()


def test_account_facts_without_session_is_incomplete_and_sends_nothing():
    calls: list = []
    feed = _feed(public_key=None)
    try:
        Venue(feed, calls)
        facts = BinanceDirectWriteProvider(feed).account_facts()
        assert facts.complete is False and facts.blockers == ("session_unavailable",)
        assert calls == []
    finally:
        feed._http_client.close()


def test_account_reference_is_a_stable_hash_without_key_material(env):
    reference = env.provider.account_reference()
    assert reference == env.provider.account_reference()
    assert len(reference) == 16 and all(ch in "0123456789abcdef" for ch in reference)
    for secret in (API_KEY, API_SECRET):
        assert secret not in reference and secret[:6] not in reference
    other = _feed(public_key="unit-binance-key-other")
    try:
        assert BinanceDirectWriteProvider(other).account_reference() != reference
    finally:
        other._http_client.close()


# ------------------------------------------- fills after FILLED (demo regression)


def _close_req(**overrides):
    values = dict(
        side=SimpleNamespace(value="sell"),
        position_side="long",
        position_mode="dual_side",
        offset="close",
    )
    values.update(overrides)
    return _req(**values)


def test_fills_follow_an_order_already_filled_at_its_first_poll(env):
    # Demo: marketable hedge-mode orders were FILLED at the first poll and no
    # TRADE followed.  Fills must follow any executed quantity.
    _place(env, position_side="long", position_mode="dual_side")
    env.venue.on(QUERY, _order("FILLED", "0.002"))
    env.venue.on(TRADES, [_trade(701, "0.0015"), _trade(702, "0.0005", offset_ms=3)])
    filled, first, second = env.provider.drain_execution_events(10)
    assert filled.kind is DirectExecutionEventKind.ORDER and filled.status is DirectOrderStatus.FILLED
    assert [t.trade_id for t in (first, second)] == ["701", "702"]
    assert all(t.kind is DirectExecutionEventKind.TRADE for t in (first, second))
    assert (first.trade_price, first.trade_qty, first.side, first.offset) == (
        60001.5, 0.0015, "buy", "open"
    )
    assert env.provider.watched_count == 0

    env.venue.on(PLACE, _order(cid="close1", order_id=8, side="SELL"))
    reservation = env.provider.reserve_order(_close_req(client_order_id="close1"))
    env.provider.submit_order(
        reservation, _close_req(client_order_id="close1"), _grant(), Verifier(env.calls)
    )
    env.venue.on(QUERY, _order("FILLED", "0.002", cid="close1", order_id=8, side="SELL"))
    env.venue.on(TRADES, [_trade(801, "0.002", order_id=8, side="SELL")])
    _filled, trade = env.provider.drain_execution_events(10)
    assert (trade.trade_id, trade.side, trade.offset) == ("801", "sell", "close")
    assert trade.identity.client_order_id == "close1"


def test_fills_lagging_behind_filled_keep_being_polled_beyond_the_old_grace(env):
    _place(env)
    env.venue.on(QUERY, _order("FILLED", "0.002"))
    env.venue.on(TRADES, [])
    (filled,) = env.provider.drain_execution_events(10)
    assert filled.status is DirectOrderStatus.FILLED
    for _ in range(8):  # well past 60 s; userTrades still empty
        env.clock.now += 31.0
        assert env.provider.drain_execution_events(10) == ()
    assert env.provider.watched_count == 1
    order_queries = [c for c in _requests(env.calls) if c[1] == QUERY]
    assert len(order_queries) == 1  # terminal status is not re-queried, only fills
    env.clock.now += 31.0
    env.venue.on(TRADES, [_trade(701, "0.002")])
    (trade,) = env.provider.drain_execution_events(10)
    assert trade.trade_id == "701" and trade.trade_qty == 0.002
    assert env.provider.watched_count == 0


def test_fills_do_not_depend_on_the_order_id_filter(env):
    _place(env)
    env.venue.on(QUERY, _order("FILLED", "0.002"))
    other = _trade(990, "0.5", order_id=999)
    env.venue.on(TRADES, lambda params: (
        [] if "orderId" in params else [other, _trade(701, "0.002")]
    ))
    _filled, trade = env.provider.drain_execution_events(10)
    assert trade.trade_id == "701" and trade.exchange_order_id == str(ORDER_ID)
    window = [c for c in _requests(env.calls) if c[1] == TRADES and "orderId" not in c[2]]
    assert window and window[0][2]["startTime"] == DAY_START_MS + 3_600_000 - 1_000
    assert env.provider.counters["fills_from_window_query"] == 1
    assert env.provider.watched_count == 0


def test_trade_rows_are_attributed_by_the_request_scope(env):
    _place(env)
    env.venue.on(QUERY, _order("FILLED", "0.002"))
    bare = {key: value for key, value in _trade(701, "0.001").items() if key != "symbol"}
    foreign = dict(_trade(702, "0.001"), symbol="ETHUSDT")
    env.venue.on(TRADES, lambda params: [bare, foreign] if "orderId" in params else [])
    _filled, trade = env.provider.drain_execution_events(10)
    assert trade.trade_id == "701" and trade.symbol == SYMBOL
    assert env.provider.watched_count == 1  # 0.001 still owed; ETHUSDT row never attributed


@pytest.mark.parametrize(
    "failure,reason",
    [
        ({"code": -1021, "msg": "Timestamp outside recvWindow"}, "-1021"),
        (RequestTimeoutError(ROUTE, timeout=3), "RequestTimeoutError"),
    ],
)
def test_fill_query_failures_are_counted_with_a_finite_reason(env, failure, reason):
    _place(env)
    env.venue.on(QUERY, _order("FILLED", "0.002"))
    env.venue.on(TRADES, failure)
    env.provider.drain_execution_events(10)
    assert env.provider.counters["fills_query_failed"] == 1
    assert env.provider.counters[f"fills_query_failed:{reason}"] == 1
    assert env.provider.watched_count == 1


def test_terminal_order_outside_the_fill_window_is_released_after_grace(env):
    env.provider.watch_order(_target(order_id=str(ORDER_ID)), SYMBOL)
    old = dict(_order("FILLED", "0.002"), time=DAY_START_MS - 8 * 86_400_000)
    env.venue.on(QUERY, old)
    env.venue.on(TRADES, [])
    env.provider.drain_execution_events(10)
    env.clock.now += 61.0
    env.provider.drain_execution_events(10)
    assert env.provider.watched_count == 0
    assert env.provider.counters["fills_incomplete_outside_window"] == 1


# -------------------------------------------------------------- venue clock


class Ns:
    def __init__(self):
        self.value = 1_794_020_400_000_000_000

    def __call__(self):
        self.value += 5_000_000
        return self.value


def test_server_time_observation_is_bracketed_cached_and_fails_closed():
    calls: list = []
    feed = _feed()
    try:
        venue = Venue(feed, calls)
        clock, ns = Clock(), Ns()
        provider = BinanceDirectWriteProvider(feed, clock=clock, wall_clock=lambda: WALL, time_ns=ns)
        venue.on(SERVER_TIME, {"serverTime": 1794020400123})
        observation = provider.server_time_observation()
        assert observation == {
            "venue_epoch_ms": 1794020400123,
            "local_sent_ns": 1_794_020_400_005_000_000,
            "local_received_ns": 1_794_020_400_010_000_000,
            "granularity_ms": 1,
        }
        assert feed._params.rest_url == "https://demo-fapi.binance.com"  # demo host via the feed
        clock.now += 59.0
        assert provider.server_time_observation() == observation
        assert len(_requests(calls)) == 1  # cached for 60 s
        clock.now += 2.0
        venue.on(SERVER_TIME, RequestTimeoutError(ROUTE, timeout=3))
        assert provider.server_time_observation() is None
        clock.now += 1.0
        assert provider.server_time_observation() is None
        assert len(_requests(calls)) == 2  # failure retried only after 5 s
        clock.now += 5.0
        for bad in ({"serverTime": "1794020400123"}, {"serverTime": 12}, {"code": -1000}):
            venue.on(SERVER_TIME, bad)
            assert provider.server_time_observation() is None
            clock.now += 5.0
        venue.on(SERVER_TIME, {"serverTime": 1794020460000})
        assert provider.server_time_observation()["venue_epoch_ms"] == 1794020460000
    finally:
        feed._http_client.close()


def test_server_time_local_stamps_default_to_the_wall_clock():
    calls: list = []
    feed = _feed()
    try:
        venue = Venue(feed, calls)
        venue.on(SERVER_TIME, lambda *_args: {"serverTime": int(time.time() * 1000)})
        before = time.time_ns()
        observation = BinanceDirectWriteProvider(feed).server_time_observation()
        after = time.time_ns()
        assert before <= observation["local_sent_ns"] <= observation["local_received_ns"] <= after
    finally:
        feed._http_client.close()
