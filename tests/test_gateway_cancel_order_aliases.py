from __future__ import annotations

import queue

from bt_api_binance.client import BinanceDirectClient
from bt_api_binance.feeds.swap import BinanceRequestDataSwap


class _FakeFeed:
    def __init__(self) -> None:
        self.cancel_calls: list[dict[str, object]] = []
        self.order_calls: list[dict[str, object]] = []

    def cancel_order(self, symbol=None, order_id=None, **kwargs):
        self.cancel_calls.append(
            {"symbol": symbol, "order_id": order_id, "kwargs": dict(kwargs)}
        )
        return {"status": "ok", "order_id": order_id}

    def make_order(self, **kwargs):
        self.order_calls.append(dict(kwargs))
        return {"status": "ok", "order_id": "binance-order-1"}


class _FakeLogger:
    @staticmethod
    def info(_message):
        return None


def test_cancel_order_accepts_gateway_order_ref_and_instrument_alias() -> None:
    client = BinanceDirectClient.__new__(BinanceDirectClient)
    feed = _FakeFeed()
    client.feed = feed
    client._ensure_account_stream = lambda: None

    result = client.cancel_order({"instrument": "BTC-USDT", "order_ref": "987654"})

    assert result == {"status": "ok", "order_id": "987654"}
    assert feed.cancel_calls == [
        {"symbol": "BTC-USDT", "order_id": "987654", "kwargs": {}}
    ]


def test_place_order_forwards_position_side_reduce_only_and_time_in_force() -> None:
    client = BinanceDirectClient.__new__(BinanceDirectClient)
    feed = _FakeFeed()
    client.feed = feed
    client._ensure_account_stream = lambda: None

    result = client.place_order(
        {
            "symbol": "BTC-USDT",
            "size": "0.2",
            "side": "sell",
            "order_type": "market",
            "offset": "close",
            "position_side": "LONG",
            "reduce_only": True,
            "time_in_force": "IOC",
        }
    )

    assert result == {"status": "ok", "order_id": "binance-order-1"}
    assert feed.order_calls == [
        {
            "symbol": "BTC-USDT",
            "vol": 0.2,
            "price": None,
            "order_type": "sell-market",
            "offset": "close",
            "client_order_id": None,
            "position_side": "LONG",
            "reduceOnly": True,
            "time_in_force": "IOC",
        }
    ]


def test_swap_order_defaults_to_one_way_reduce_only_without_position_side() -> None:
    request_data = BinanceRequestDataSwap(
        queue.Queue(),
        public_key="test_key",
        private_key="test_secret",
    )

    _path, params, _extra_data = request_data._make_order(
        symbol="BTC-USDT",
        vol="0.2",
        price=None,
        order_type="sell-market",
        offset="close",
    )

    assert params["symbol"] == "BTCUSDT"
    assert params["side"] == "SELL"
    assert params["type"] == "MARKET"
    assert params["reduceOnly"] == "true"
    assert "positionSide" not in params
    assert "price" not in params
    assert "timeInForce" not in params


def test_swap_order_uses_explicit_position_side_for_hedge_mode() -> None:
    request_data = BinanceRequestDataSwap(
        queue.Queue(),
        public_key="test_key",
        private_key="test_secret",
    )

    _path, params, _extra_data = request_data._make_order(
        symbol="BTC-USDT",
        vol="0.2",
        price="61000",
        order_type="sell-limit",
        offset="close",
        position_side="LONG",
    )

    assert params["symbol"] == "BTCUSDT"
    assert params["side"] == "SELL"
    assert params["type"] == "LIMIT"
    assert params["price"] == "61000"
    assert params["positionSide"] == "LONG"
    assert "reduceOnly" not in params


class _FakeTicker:
    def init_data(self):
        return self

    @staticmethod
    def get_symbol_name():
        return "BTCUSDT"

    @staticmethod
    def get_server_time():
        return 1700000000000

    @staticmethod
    def get_bid_price():
        return 60999.0

    @staticmethod
    def get_ask_price():
        return 61001.0

    @staticmethod
    def get_last_price():
        return 61000.5

    @staticmethod
    def get_bid_volume():
        return 1.0

    @staticmethod
    def get_ask_volume():
        return 2.0

    @staticmethod
    def get_volume_24h():
        return 100.0

    @staticmethod
    def get_turnover_24h():
        return 6100000.0

    @staticmethod
    def get_high_price():
        return 62000.0

    @staticmethod
    def get_low_price():
        return 60000.0

    @staticmethod
    def get_open_price():
        return 60500.0

    @staticmethod
    def get_prev_close():
        return 60400.0


def test_emit_ticker_updates_latest_price_cache() -> None:
    client = BinanceDirectClient.__new__(BinanceDirectClient)
    events: list[tuple[str, dict[str, object]]] = []
    client.asset_type = "SWAP"
    client.last_price = {}
    client._latest_ticks = {}
    client.emit = lambda channel, payload: events.append((channel, payload))

    client._emit_ticker(_FakeTicker())

    assert client.last_price["BTCUSDT"] == 61000.5
    assert client._latest_ticks["BTCUSDT"]["price"] == 61000.5
    assert client._latest_ticks["BTCUSDT"]["last_price"] == 61000.5
    assert events[0][1]["price"] == 61000.5


def test_disconnect_clears_latest_price_cache() -> None:
    client = BinanceDirectClient.__new__(BinanceDirectClient)
    client.running = True
    client.thread = None
    client.market_stream = object()
    client.account_stream = object()
    client.aliases = {"BTCUSDT": {"BTCUSDT"}}
    client.last_price = {"BTCUSDT": 61000.5}
    client._latest_ticks = {"BTCUSDT": {"price": 61000.5}}
    client.logger = _FakeLogger()

    client.disconnect()

    assert client.last_price == {}
    assert client._latest_ticks == {}
