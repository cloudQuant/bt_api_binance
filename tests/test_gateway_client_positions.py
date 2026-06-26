from __future__ import annotations

from bt_api_binance import client as client_module


class _FakeResult:
    def __init__(self, data):
        self._data = data

    def get_data(self):
        return self._data


class _LazyPosition:
    def __init__(self) -> None:
        self.initialized = False

    def init_data(self):
        self.initialized = True
        return self

    def get_all_data(self):
        if not self.initialized:
            return {"position_symbol_name": None}
        return {
            "position_symbol_name": "BTCUSDT",
            "position_volume": 1.0,
            "position_side": "LONG",
            "avg_price": 60000.0,
            "mark_price": 60005.0,
            "liquidation_price": 55000.0,
            "position_notional": 60005.0,
            "notional": 60005.0,
            "market_value": 60005.0,
            "isolated_margin": 3000.0,
            "position_initial_margin": 3000.0,
            "position_unrealized_pnl": 5.0,
        }


class _LazyOrder:
    def __init__(self) -> None:
        self.initialized = False

    def init_data(self):
        self.initialized = True
        return self

    def get_all_data(self):
        if not self.initialized:
            return {"order_id": None}
        return {
            "symbol": "BTCUSDT",
            "orderId": "order-1",
            "clientOrderId": "client-1",
            "status": "NEW",
            "origQty": "0.5",
            "executedQty": "0.1",
        }


class _FakeFeed:
    def get_position(self):
        return _FakeResult([_LazyPosition()])


class _TradeFeed(_FakeFeed):
    def get_deals(self, symbol=None, count=100):
        assert symbol == "BTC-USDT"
        assert count == 50
        return _FakeResult(
            {
                "data": [
                    {
                        "symbol": "BTCUSDT",
                        "id": "fill-1",
                        "side": "BUY",
                        "qty": "0.02",
                        "price": "60000",
                        "commission": "0.5",
                        "commissionAsset": "USDT",
                        "time": 1710000000000,
                    }
                ]
            }
        )


class _OpenOrdersFeed(_FakeFeed):
    def get_open_orders(self):
        return _FakeResult(
            [
                _LazyOrder(),
                {
                    "symbol": "ETHUSDT",
                    "orderId": "order-2",
                    "clientOrderId": "client-2",
                    "status": "PARTIALLY_FILLED",
                    "origQty": "1",
                    "executedQty": "0.25",
                },
            ]
        )


def test_get_positions_initializes_position_containers(monkeypatch) -> None:
    monkeypatch.setattr(client_module, "_create_feed", lambda _queue, _kwargs: _FakeFeed())
    client = client_module.BinanceDirectClient(asset_type="SWAP")
    client._ensure_account_stream = lambda: None

    positions = client.get_positions()

    assert positions == [
        {
            "position_symbol_name": "BTCUSDT",
            "position_volume": 1.0,
            "position_side": "LONG",
            "avg_price": 60000.0,
            "mark_price": 60005.0,
            "liquidation_price": 55000.0,
            "position_notional": 60005.0,
            "notional": 60005.0,
            "market_value": 60005.0,
            "isolated_margin": 3000.0,
            "position_initial_margin": 3000.0,
            "position_unrealized_pnl": 5.0,
        }
    ]


def test_get_trades_reads_binance_deals(monkeypatch) -> None:
    monkeypatch.setattr(client_module, "_create_feed", lambda _queue, _kwargs: _TradeFeed())
    client = client_module.BinanceDirectClient(asset_type="SWAP")

    trades = client.get_trades(symbol="BTC-USDT", limit=50)

    assert trades == [
        {
            "symbol": "BTCUSDT",
            "id": "fill-1",
            "side": "BUY",
            "qty": "0.02",
            "price": "60000",
            "commission": "0.5",
            "commissionAsset": "USDT",
            "time": 1710000000000,
        }
    ]


def test_get_open_orders_initializes_and_normalizes_order_containers(monkeypatch) -> None:
    monkeypatch.setattr(client_module, "_create_feed", lambda _queue, _kwargs: _OpenOrdersFeed())
    client = client_module.BinanceDirectClient(asset_type="SWAP")

    orders = client.get_open_orders()

    assert orders[0]["order_id"] == "order-1"
    assert orders[0]["external_order_id"] == "order-1"
    assert orders[0]["client_order_id"] == "client-1"
    assert orders[0]["remaining"] == 0.4
    assert orders[1]["order_id"] == "order-2"
    assert orders[1]["client_order_id"] == "client-2"
    assert orders[1]["remaining"] == 0.75


class _Params:
    @staticmethod
    def get_symbol(symbol):
        return symbol.replace("-", "")


class _SymbolFeed:
    _params = _Params()

    @staticmethod
    def get_config():
        return _FakeResult(
            {
                "symbols": [
                    {
                        "symbol": "BTCUSDT",
                        "contractType": "PERPETUAL",
                        "requiredMarginPercent": "5.0000",
                        "filters": [
                            {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                            {
                                "filterType": "LOT_SIZE",
                                "minQty": "0.001",
                                "maxQty": "1000",
                                "stepSize": "0.001",
                            },
                        ],
                    }
                ]
            }
        )

    @staticmethod
    def get_fee(symbol):
        assert symbol == "BTC-USDT"
        return {
            "makerCommissionRate": "0.00018",
            "takerCommissionRate": "0.00045",
        }


def test_get_symbol_info_merges_binance_fee_rates() -> None:
    client = client_module.BinanceDirectClient.__new__(client_module.BinanceDirectClient)
    client.asset_type = "SWAP"
    client.feed = _SymbolFeed()
    client.logger = client_module.get_logger("test")

    spec = client.get_symbol_info("BTC-USDT")

    assert spec["symbol"] == "BTCUSDT"
    assert spec["commission_rate"] == 0.00045
    assert spec["open_commission_rate"] == 0.00045
    assert spec["maker_commission_rate"] == 0.00018
    assert spec["taker_commission_rate"] == 0.00045
    assert spec["margin_rate"] == 0.05
    assert spec["required_margin_percent"] == 0.05
    assert spec["fee_source"] == "binance_get_fee"


class _FeeFailingSymbolFeed(_SymbolFeed):
    @staticmethod
    def get_fee(symbol):
        raise RuntimeError("fee unavailable")


def test_get_symbol_info_keeps_exchange_info_when_fee_lookup_fails() -> None:
    client = client_module.BinanceDirectClient.__new__(client_module.BinanceDirectClient)
    client.asset_type = "SWAP"
    client.feed = _FeeFailingSymbolFeed()
    client.logger = client_module.get_logger("test")

    spec = client.get_symbol_info("BTC-USDT")

    assert spec["symbol"] == "BTCUSDT"
    assert "commission_rate" not in spec


class _FakeTrade:
    def init_data(self):
        return self

    @staticmethod
    def get_symbol_name():
        return "BTCUSDT"

    @staticmethod
    def get_trade_id():
        return "trade-1"

    @staticmethod
    def get_order_id():
        return "order-1"

    @staticmethod
    def get_trade_price():
        return 60000.0

    @staticmethod
    def get_trade_volume():
        return 0.01

    @staticmethod
    def get_trade_side():
        return "buy"

    @staticmethod
    def get_trade_type():
        return "maker"

    @staticmethod
    def get_trade_fee():
        return 0.123

    @staticmethod
    def get_trade_fee_symbol():
        return "USDT"


def test_emit_trade_includes_fee_and_liquidity_role() -> None:
    client = client_module.BinanceDirectClient.__new__(client_module.BinanceDirectClient)
    client.output_queue = client_module.queue.Queue()
    client.logger = client_module.get_logger("test")

    client._emit_trade(_FakeTrade())
    channel, payload = client.poll_output()

    assert channel == client_module.CHANNEL_EVENT
    assert payload["kind"] == "trade"
    assert payload["trade_fee"] == 0.123
    assert payload["trade_commission"] == 0.123
    assert payload["fee"] == 0.123
    assert payload["fee_currency"] == "USDT"
    assert payload["trade_type"] == "maker"
    assert payload["liquidity"] == "maker"
