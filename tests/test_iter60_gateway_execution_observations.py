"""Iteration 60: Binance USDⓈ-M Gateway execution observations (fake transport only).

The provider reads per-fill rows (``/fapi/v1/userTrades``) and order rows
(``allOrders`` window, symbol ``openOrders``, ``order`` query) through signed
GETs of the fixed Demo origin and hands typed Base observations to the Gateway
worker. Evidence: UNIT/FAKE. No network, account or venue is contacted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import random
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from bt_api_base.account_protocol import AccountKey
from bt_api_base.execution_row_observation_protocol import (
    AccountExecutionOrderObservation,
    AccountExecutionTradeObservation,
    execution_observation_fact_digest,
    execution_observation_fact_id,
)

import bt_api_binance.gateway_execution_observations as execution_module
from bt_api_binance.account_session_provider import (
    BinanceUsdMAccountSessionProvider,
    BinanceUsdMApiCredentials,
    BinanceUsdMExecutionScope,
    BinanceUsdMProviderError,
)

SECRET = "fixture-api-secret"
NOW_MS = 1_800_000_000_000
GEN = "generation-01"


class FakeIssuer:
    """Stand-in for the SDK's durable issuer: keyed digest, stable across instances."""

    def __init__(self, key: bytes = b"k" * 32) -> None:
        self.key = key
        self.identities: list[str] = []

    def _digest(self, kind, provider_name, environment, account_ref, identity):
        self.identities.append(identity)
        material = json.dumps([kind, provider_name, environment, account_ref, identity])
        return hmac.new(self.key, material.encode(), hashlib.sha256).hexdigest()

    def issue_order_observation_id(self, provider_name, environment, account_ref, identity):
        return "sdk-order-observation-v1-" + self._digest(
            "order", provider_name, environment, account_ref, identity
        )

    def issue_trade_observation_id(self, provider_name, environment, account_ref, identity):
        return "sdk-trade-observation-v1-" + self._digest(
            "trade", provider_name, environment, account_ref, identity
        )


def order_row(order_id, *, symbol="BTCUSDT", status="FILLED", qty="0.010", executed=None,
              client="client-1", side="BUY", position_side="LONG", price="40000.00",
              time_ms=NOW_MS - 60_000, order_type="LIMIT"):
    if executed is None:
        executed = qty if status == "FILLED" else "0"
    return {
        "symbol": symbol,
        "orderId": order_id,
        "clientOrderId": client,
        "side": side,
        "positionSide": position_side,
        "origType": order_type,
        "type": order_type,
        "status": status,
        "origQty": qty,
        "executedQty": executed,
        "price": price,
        "avgPrice": price,
        "reduceOnly": False,
        "closePosition": False,
        "time": time_ms,
        "updateTime": time_ms + 1_000,
    }


def trade_row(trade_id, order_id, *, symbol="BTCUSDT", qty="0.010", price="40000.10",
              commission="0.02000000", asset="USDT", side="BUY", position_side="LONG",
              time_ms=NOW_MS - 50_000):
    row = {
        "symbol": symbol,
        "id": trade_id,
        "orderId": order_id,
        "side": side,
        "price": price,
        "qty": qty,
        "realizedPnl": "0",
        "quoteQty": "400.001",
        "commission": commission,
        "commissionAsset": asset,
        "time": time_ms,
        "positionSide": position_side,
        "buyer": side == "BUY",
        "maker": False,
        "marginAsset": "USDT",
    }
    if commission is None:
        del row["commission"]
    return row


class FakeUsdmVenue:
    """A deterministic USDⓈ-M Demo venue answering only signed read routes."""

    def __init__(self, *, now_ms=NOW_MS, isolated=(), clock=None):
        self.now_ms = now_ms
        self.clock = clock  # when set, the venue clock follows the shared test clock
        self.orders: dict[tuple[str, int], dict] = {}
        self.trades: list[dict] = []
        self.isolated = set(isolated)
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.trade_page_hook = None
        self.order_page_hook = None
        self.extra_order_rows: list[dict] = []

    def add_order(self, row):
        self.orders[(row["symbol"], row["orderId"])] = dict(row)

    def __call__(self, method, url, headers, timeout, max_bytes):
        assert method == "GET" and timeout > 0
        parsed = urlsplit(url)
        assert parsed.scheme == "https" and parsed.netloc == "demo-fapi.binance.com"
        params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        if parsed.path != "/fapi/v1/time":
            raw = parsed.query
            unsigned, signature = raw.rsplit("&signature=", 1)
            expected = hmac.new(SECRET.encode(), unsigned.encode(), hashlib.sha256).hexdigest()
            assert hmac.compare_digest(signature, expected)
            assert headers["X-MBX-APIKEY"] == "fixture-api-key"
            params.pop("signature")
            assert params.pop("recvWindow") == "5000" and params.pop("timestamp")
        self.calls.append((parsed.path, params))
        return json.dumps(self._answer(parsed.path, params)).encode()

    def _answer(self, path, params):
        if path == "/fapi/v1/time":
            return {"serverTime": int(self.clock.wall * 1000) if self.clock else self.now_ms}
        if path == "/fapi/v2/account":
            symbols = {symbol for symbol, _ in self.orders} | {"BTCUSDT", "ETHUSDT"}
            return {
                "multiAssetsMargin": False,
                "assets": [{"asset": "USDT", "crossWalletBalance": "100", "availableBalance": "90"}],
                "positions": [
                    {
                        "symbol": symbol,
                        "positionSide": "BOTH",
                        "positionAmt": "0",
                        "isolated": symbol in self.isolated,
                        "entryPrice": "0",
                    }
                    for symbol in sorted(symbols)
                ],
            }
        if path == "/fapi/v1/openOrders":
            rows = [
                row for row in self.orders.values()
                if row["status"] in {"NEW", "PARTIALLY_FILLED"}
                and ("symbol" not in params or row["symbol"] == params["symbol"])
            ]
            return sorted(rows, key=lambda row: row["orderId"])
        if path == "/fapi/v1/openAlgoOrders":
            return []
        if path == "/fapi/v1/allOrders":
            start, end = int(params["startTime"]), int(params["endTime"])
            rows = [
                row for row in self.orders.values()
                if row["symbol"] == params["symbol"] and start <= row["time"] <= end
            ]
            rows = sorted(rows, key=lambda row: row["orderId"])[: int(params["limit"])]
            rows = rows + [dict(row) for row in self.extra_order_rows]
            return self.order_page_hook(rows) if self.order_page_hook else rows
        if path == "/fapi/v1/userTrades":
            rows = [row for row in self.trades if row["symbol"] == params["symbol"]]
            if "fromId" in params:
                assert "startTime" not in params and "endTime" not in params
                rows = [row for row in rows if row["id"] >= int(params["fromId"])]
            else:
                start, end = int(params["startTime"]), int(params["endTime"])
                rows = [row for row in rows if start <= row["time"] <= end]
            rows = sorted(rows, key=lambda row: row["id"])[: int(params["limit"])]
            rows = [dict(row) for row in rows]
            return self.trade_page_hook(rows) if self.trade_page_hook else rows
        if path == "/fapi/v1/order":
            return dict(self.orders[(params["symbol"], int(params["orderId"]))])
        raise AssertionError(f"unexpected route {path}")


def account_key(account_id="configured-account"):
    return AccountKey(provider="binance", venue="binance", environment="demo", account_id=account_id)


class Clock:
    def __init__(self, wall=NOW_MS / 1000, mono=10.0):
        self.wall = wall
        self.mono = mono

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds


def scope(issuer, symbols=("BTCUSDT",), lookback=3_600, interval=0.0):
    return BinanceUsdMExecutionScope(
        symbols=symbols,
        lookback_seconds=lookback,
        observation_issuer=issuer,
        poll_interval_seconds=interval,
    )


def provider(venue, issuer, *, clock=None, generation=GEN, read_account=True, **scope_kwargs):
    clock = clock or Clock()
    built = BinanceUsdMAccountSessionProvider(
        BinanceUsdMApiCredentials("fixture-api-key", SECRET),
        transport=venue,
        wall_clock=lambda: clock.wall,
        monotonic_clock=lambda: clock.mono,
        execution=scope(issuer, **scope_kwargs),
    )
    built.connect(account_key=account_key(), generation=generation, timeout=2.0)
    if read_account:
        built.read_account(generation=generation, timeout=2.0)
    return built


def read(built, limit=1000, generation=GEN):
    return built.read_execution_observations(generation=generation, timeout=2.0, limit=limit)


def facts(items):
    return [(execution_observation_fact_id(i), execution_observation_fact_digest(i)) for i in items]


def basic_venue():
    venue = FakeUsdmVenue()
    venue.add_order(order_row(1001, client="s1234abcd-0001"))
    venue.trades.append(trade_row(5001, 1001))
    return venue


# -- projection ---------------------------------------------------------------------


def test_fill_and_terminal_order_are_projected_from_documented_rows():
    venue, issuer = basic_venue(), FakeIssuer()
    built = provider(venue, issuer)
    items = read(built)
    assert [type(item) for item in items] == [
        AccountExecutionOrderObservation,
        AccountExecutionTradeObservation,
    ]
    order, fill = items[0].order, items[1].trade
    assert items[0].account_key == items[1].account_key == account_key()
    assert (order.status, order.quantity, order.filled_quantity, order.qty_unit) == (
        "filled", "0.01", "0.01", "base_asset"
    )
    assert (order.client_order_id, order.intent_binding) == ("s1234abcd-0001", "verified")
    assert (order.side, order.position_effect, order.position_side) == ("buy", "open", "long")
    assert (order.order_type, order.limit_price, order.created_at_utc) == (
        "limit", "40000", "2027-01-15T07:59:00.000Z"
    )
    assert order.resource.product_type == "usdm_perpetual" and order.resource.margin_pool == "cross"
    assert order.instrument.instrument_id == order.instrument.native_symbol == "BTCUSDT"
    assert (fill.quantity, fill.price, fill.order_binding) == ("0.01", "40000.1", "provider_order_identity")
    assert fill.order_id == order.order_id and fill.traded_at_utc == "2027-01-15T07:59:10.000Z"
    assert (items[1].fee, items[1].fee_currency) == ("0.02", "USDT")
    # Opaque ids from the issuer; native ids never appear in them.
    assert re.fullmatch(r"sdk-order-observation-v1-[0-9a-f]{64}", order.order_id)
    assert re.fullmatch(r"sdk-trade-observation-v1-[0-9a-f]{64}", fill.trade_id)
    assert "1001" not in order.order_id + fill.trade_id and "5001" not in fill.trade_id
    # Read-only signed GETs on the route table only; an explicit symbol scope.
    paths = [path for path, _ in venue.calls]
    assert set(paths) <= {
        "/fapi/v1/time", "/fapi/v2/account", "/fapi/v1/openOrders", "/fapi/v1/openAlgoOrders",
        "/fapi/v1/allOrders", "/fapi/v1/userTrades",
    }
    trade_calls = [params for path, params in venue.calls if path == "/fapi/v1/userTrades"]
    assert trade_calls[0]["symbol"] == "BTCUSDT"
    assert int(trade_calls[0]["endTime"]) - int(trade_calls[0]["startTime"]) == 3_600_000


def test_fee_present_absent_and_negative_commission():
    venue, issuer = FakeUsdmVenue(), FakeIssuer()
    venue.add_order(order_row(1001, qty="0.03"))
    venue.trades += [
        trade_row(5001, 1001, commission="0"),
        trade_row(5002, 1001, commission=None),
        trade_row(5003, 1001, commission="-0.00500000"),
    ]
    built = provider(venue, issuer)
    fills = [item for item in read(built) if type(item) is AccountExecutionTradeObservation]
    assert [(item.fee, item.fee_currency) for item in fills] == [
        ("0", "USDT"),  # an explicit zero commission is a known fee
        (None, None),  # absent: unknown, never zero
        (None, None),  # a rebate cannot be a non-negative fee: unknown, counted
    ]
    assert built.execution_counters["EXECUTION_FEE_UNAVAILABLE"] == 1
    assert built.execution_counters["EXECUTION_FEE_REBATE_UNREPRESENTABLE"] == 1


def test_fills_never_come_from_order_quantities():
    venue, issuer = FakeUsdmVenue(), FakeIssuer()
    venue.add_order(order_row(1001, status="PARTIALLY_FILLED", qty="1", executed="0.4"))
    built = provider(venue, issuer)
    items = read(built)
    assert [item.order.status for item in items] == ["partially_filled"]
    assert not any(type(item) is AccountExecutionTradeObservation for item in items)


@pytest.mark.parametrize(
    ("status", "executed", "expected"),
    [
        ("CANCELED", "0", "canceled"),
        ("CANCELED", "0.004", "partially_filled_canceled"),
        ("EXPIRED", "0", "terminal_unfilled"),
        ("EXPIRED_IN_MATCH", "0.004", "partially_filled_terminal"),
        ("REJECTED", "0", "rejected"),
        ("NEW", "0", "open"),
    ],
)
def test_order_status_mapping(status, executed, expected):
    venue, issuer = FakeUsdmVenue(), FakeIssuer()
    venue.add_order(order_row(1001, status=status, executed=executed, position_side="BOTH"))
    (item,) = read(provider(venue, issuer))
    assert item.order.status == expected
    # One-way mode cannot state open/close.
    assert (item.order.position_effect, item.order.position_side) == ("unavailable", None)


# -- dedupe, order and paging --------------------------------------------------------


def _many_fills_venue():
    venue = FakeUsdmVenue()
    venue.add_order(order_row(1001, qty="0.05"))
    venue.add_order(order_row(1002, qty="0.02", side="SELL", position_side="LONG"))
    venue.trades += [trade_row(5000 + n, 1001, qty="0.01", time_ms=NOW_MS - 40_000 + n) for n in range(5)]
    venue.trades += [trade_row(5100 + n, 1002, qty="0.01", side="SELL") for n in range(2)]
    return venue


def test_duplicate_and_out_of_order_pages_give_the_same_facts():
    ordered = read(provider(_many_fills_venue(), FakeIssuer()))
    shuffled_venue = _many_fills_venue()

    def shuffle_and_duplicate(rows):
        rows = rows + [dict(rows[1]), dict(rows[3])]
        random.Random(7).shuffle(rows)
        return rows

    shuffled_venue.trade_page_hook = shuffle_and_duplicate
    shuffled_venue.order_page_hook = lambda rows: list(reversed(rows + [dict(rows[0])]))
    shuffled = read(provider(shuffled_venue, FakeIssuer()))
    assert facts(shuffled) == facts(ordered)
    assert len(ordered) == 2 + 7


def test_cursor_paging_delivers_each_fill_once(monkeypatch):
    monkeypatch.setattr(execution_module, "PAGE_LIMIT", 3)
    venue, issuer, clock = FakeUsdmVenue(), FakeIssuer(), Clock()
    venue.add_order(order_row(1001, qty="1", status="PARTIALLY_FILLED", executed="0.02"))
    venue.trades += [trade_row(5001, 1001), trade_row(5002, 1001)]
    built = provider(venue, issuer, clock=clock)
    first = read(built)
    built.confirm_execution_observations(generation=GEN, count=len(first))
    venue.trades += [trade_row(5003 + n, 1001, time_ms=NOW_MS + n) for n in range(5)]
    delivered = [item for item in first if type(item) is AccountExecutionTradeObservation]
    from_ids = []
    for _ in range(4):
        items = read(built)
        from_ids += [p["fromId"] for path, p in venue.calls if path == "/fapi/v1/userTrades" and "fromId" in p][len(from_ids):]
        delivered += [item for item in items if type(item) is AccountExecutionTradeObservation]
        if items:
            built.confirm_execution_observations(generation=GEN, count=len(items))
    assert from_ids[:3] == ["5003", "5006", "5008"]
    trade_ids = [item.trade.trade_id for item in delivered]
    assert len(trade_ids) == 7 == len(set(trade_ids))


def test_a_full_initial_window_fails_closed(monkeypatch):
    monkeypatch.setattr(execution_module, "PAGE_LIMIT", 3)
    venue, issuer = FakeUsdmVenue(), FakeIssuer()
    venue.add_order(order_row(1001, qty="1", status="PARTIALLY_FILLED", executed="0.03"))
    venue.trades += [trade_row(5001 + n, 1001) for n in range(3)]
    built = provider(venue, issuer)
    with pytest.raises(BinanceUsdMProviderError) as error:
        read(built)
    assert error.value.code == "EXECUTION_LOOKBACK_TRUNCATED"


def test_malformed_rows_fail_closed_and_leave_the_cursor(monkeypatch):
    venue, issuer = basic_venue(), FakeIssuer()
    venue.trades[0]["qty"] = "1e-3"
    built = provider(venue, issuer)
    with pytest.raises(BinanceUsdMProviderError) as error:
        read(built)
    assert error.value.code == "EXECUTION_ROW_INVALID"
    venue.trades[0]["qty"] = "0.010"
    assert len(read(built)) == 2  # nothing was lost by the failed poll


# -- generations, confirm, restart ---------------------------------------------------


def test_stale_generation_and_closed_session_are_refused():
    built = provider(basic_venue(), FakeIssuer())
    read(built)
    for call in (
        lambda: read(built, generation="generation-00"),
        lambda: built.confirm_execution_observations(generation="generation-00", count=1),
    ):
        with pytest.raises(BinanceUsdMProviderError) as error:
            call()
        assert error.value.code == "PROVIDER_GENERATION_MISMATCH"
    built.close()
    with pytest.raises(BinanceUsdMProviderError) as closed:
        read(built)
    assert closed.value.code == "PROVIDER_SESSION_CLOSED"
    # The provider is one-shot: a closed instance never opens a new generation,
    # so its unconfirmed queue cannot be confirmed under another one.
    with pytest.raises(BinanceUsdMProviderError) as again:
        built.connect(account_key=account_key(), generation="generation-02", timeout=2.0)
    assert again.value.code == "PROVIDER_SESSION_CLOSED"


def test_unconfirmed_items_are_redelivered_and_partial_confirm_keeps_the_rest():
    venue, issuer = _many_fills_venue(), FakeIssuer()
    built = provider(venue, issuer)
    first = read(built, limit=4)
    assert len(first) == 4
    calls = len(venue.calls)
    assert facts(read(built, limit=4)) == facts(first)  # redelivered, no venue query
    assert len(venue.calls) == calls
    with pytest.raises(BinanceUsdMProviderError) as too_many:
        built.confirm_execution_observations(generation=GEN, count=5)
    assert too_many.value.code == "EXECUTION_CONFIRM_INVALID"
    built.confirm_execution_observations(generation=GEN, count=3)
    rest = read(built)
    assert facts(rest)[0] == facts(first)[3] and len(rest) == 9 - 3
    built.confirm_execution_observations(generation=GEN, count=len(rest))
    with pytest.raises(BinanceUsdMProviderError) as nothing_out:
        built.confirm_execution_observations(generation=GEN, count=1)
    assert nothing_out.value.code == "EXECUTION_CONFIRM_INVALID"
    assert read(built) == ()  # nothing new at the venue


def test_reconnect_with_a_new_generation_redelivers_unconfirmed_facts():
    venue, issuer = basic_venue(), FakeIssuer()
    old = provider(venue, issuer, generation="generation-01")
    unconfirmed = read(old, generation="generation-01")
    old.close()
    new = provider(venue, issuer, generation="generation-02")
    with pytest.raises(BinanceUsdMProviderError) as stale:
        new.confirm_execution_observations(generation="generation-01", count=1)
    assert stale.value.code == "PROVIDER_GENERATION_MISMATCH"
    with pytest.raises(BinanceUsdMProviderError) as fresh:
        new.confirm_execution_observations(generation="generation-02", count=1)
    assert fresh.value.code == "EXECUTION_CONFIRM_INVALID"  # fresh queue, nothing handed out
    assert facts(read(new, generation="generation-02")) == facts(unconfirmed)


def test_restart_reproduces_identical_facts_and_reports_fee_changes_as_is():
    venue = basic_venue()
    first = read(provider(venue, FakeIssuer()))
    restarted = read(provider(venue, FakeIssuer()))  # new instance, same issuer key
    assert facts(restarted) == facts(first)
    venue.trades[0]["commission"] = "0.03"  # the venue now reports a higher fee
    corrected = read(provider(venue, FakeIssuer()))
    assert facts(corrected)[0] == facts(first)[0]  # the order fact is unchanged
    assert corrected[1].trade.trade_id == first[1].trade.trade_id
    assert facts(corrected)[1] != facts(first)[1] and corrected[1].fee == "0.03"
    venue.trades[0]["commission"] = "0.01"  # lower: reported, the Gateway refuses it
    lowered = read(provider(venue, FakeIssuer()))
    assert lowered[1].fee == "0.01" and lowered[1].trade.trade_id == first[1].trade.trade_id


def test_another_issuer_key_gives_other_ids():
    first = read(provider(basic_venue(), FakeIssuer()))
    other = read(provider(basic_venue(), FakeIssuer(b"x" * 32)))
    assert first[0].order.order_id != other[0].order.order_id


# -- scope ---------------------------------------------------------------------------


def test_rows_outside_the_scope_are_refused_and_counted():
    venue, issuer = basic_venue(), FakeIssuer()
    venue.trades.append(trade_row(7001, 9001, symbol="ETHUSDT"))
    venue.trade_page_hook = lambda rows: rows + [trade_row(7001, 9001, symbol="ETHUSDT")]
    venue.extra_order_rows = [order_row(9001, symbol="ETHUSDT")]
    built = provider(venue, issuer)
    items = read(built)
    assert len(items) == 2 and all(item.account_key == account_key() for item in items)
    assert {item.order.instrument.instrument_id for item in items[:1]} == {"BTCUSDT"}
    assert built.execution_counters["EXECUTION_ROW_INSTRUMENT_OUT_OF_SCOPE"] == 2


def test_isolated_margin_symbols_are_refused():
    venue, issuer = basic_venue(), FakeIssuer()
    venue.isolated.add("BTCUSDT")
    built = provider(venue, issuer)
    assert read(built) == ()
    assert built.execution_counters["EXECUTION_ROW_MARGIN_POOL_OUT_OF_SCOPE"] == 2


def test_configuration_and_proof_requirements_fail_closed():
    venue, issuer = basic_venue(), FakeIssuer()
    plain = BinanceUsdMAccountSessionProvider(
        BinanceUsdMApiCredentials("fixture-api-key", SECRET),
        transport=venue,
        wall_clock=lambda: NOW_MS / 1000,
        monotonic_clock=lambda: 10.0,
    )
    plain.connect(account_key=account_key(), generation=GEN, timeout=2.0)
    with pytest.raises(BinanceUsdMProviderError) as unconfigured:
        read(plain)
    assert unconfigured.value.code == "EXECUTION_OBSERVATIONS_NOT_CONFIGURED"
    with pytest.raises(BinanceUsdMProviderError) as unverified:
        read(provider(venue, issuer, read_account=False))
    assert unverified.value.code == "EXECUTION_MARGIN_POOL_UNVERIFIED"
    for bad in (
        dict(symbols=()),
        dict(symbols=("btcusdt",)),
        dict(symbols=("BTCUSDT", "BTCUSDT")),
        dict(lookback=10),
        dict(lookback=8 * 86_400),
        dict(interval=-1.0),
    ):
        with pytest.raises(BinanceUsdMProviderError) as invalid:
            scope(issuer, **bad)
        assert invalid.value.code == "INVALID_EXECUTION_SCOPE"
    with pytest.raises(BinanceUsdMProviderError):
        scope(object())

    class EchoIssuer(FakeIssuer):
        def issue_order_observation_id(self, provider_name, environment, account_ref, identity):
            return identity  # would expose the native identity

    with pytest.raises(BinanceUsdMProviderError) as untrusted:
        read(provider(basic_venue(), EchoIssuer()))
    assert untrusted.value.code == "EXECUTION_IDENTITY_UNAVAILABLE"
    with pytest.raises(BinanceUsdMProviderError) as bad_limit:
        read(provider(basic_venue(), FakeIssuer()), limit=0)
    assert bad_limit.value.code == "INVALID_LIMIT"


def test_limit_is_honored():
    built = provider(_many_fills_venue(), FakeIssuer())
    assert len(read(built, limit=1)) == 1


# -- order routes and terminal detection ---------------------------------------------


def test_a_fill_of_an_order_outside_the_window_queues_its_order_first():
    venue, issuer = FakeUsdmVenue(), FakeIssuer()
    venue.add_order(order_row(1001, time_ms=NOW_MS - 10 * 3_600_000))  # before the lookback
    venue.trades.append(trade_row(5001, 1001))
    built = provider(venue, issuer)
    items = read(built)
    assert [type(item) for item in items] == [
        AccountExecutionOrderObservation,
        AccountExecutionTradeObservation,
    ]
    assert items[0].order.order_id == items[1].trade.order_id
    assert ("/fapi/v1/order", {"symbol": "BTCUSDT", "orderId": "1001"}) in venue.calls


def test_an_open_order_that_terminates_later_is_queried_and_reported():
    venue, issuer, clock = FakeUsdmVenue(), FakeIssuer(), Clock()
    venue.add_order(order_row(1001, status="NEW", time_ms=NOW_MS - 10 * 3_600_000))
    built = provider(venue, issuer, clock=clock)
    first = read(built)
    assert [item.order.status for item in first] == ["open"]
    built.confirm_execution_observations(generation=GEN, count=1)
    assert read(built) == ()  # still open: the same fact is not queued again
    venue.orders[("BTCUSDT", 1001)]["status"] = "CANCELED"
    later = read(built)
    assert [item.order.status for item in later] == ["canceled"]
    assert later[0].order.order_id == first[0].order.order_id
