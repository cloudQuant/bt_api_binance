"""Module-level docstring."""
from __future__ import annotations

import json

from bt_api_binance.containers.trades.binance_trade import (
    BinanceAggTradeData,
    BinanceRequestTradeData,
    BinanceSpotWssTradeData,
    BinanceSwapWssTradeData,
)


class TestBinanceAggTradeData:
    """Tests for BinanceAggTradeData."""

    def test_init(self):
        """Test initialization."""
        data = {"e": "aggTrade", "E": 123456789, "s": "BTCUSDT"}
        trade = BinanceAggTradeData(data, "BTC-USDT", "SWAP", True)

        assert trade.exchange_name == "BINANCE"
        assert trade.symbol_name == "BTC-USDT"
        assert trade.asset_type == "SWAP"
        assert trade.event == "AggTradeUpdate"

    def test_init_data_with_json_string(self):
        """Test init_data with JSON string."""
        data = '{"e": "aggTrade", "E": 123456789, "s": "ETHUSDT", "a": 123, "p": "3000", "q": "1", "f": 1, "l": 2, "T": 123456780, "m": false}'
        trade = BinanceAggTradeData(data, "ETH-USDT", "SWAP", False)
        trade.init_data()

        assert trade.trade_symbol_name == "ETHUSDT"
        assert trade.trade_price == 3000.0
        assert trade.trade_volume == 1.0
        assert trade.trade_type == "taker"

    def test_init_data_idempotent(self):
        """Test init_data is idempotent."""
        data = {
            "e": "aggTrade",
            "E": 123,
            "s": "BTCUSDT",
            "a": 1,
            "p": "50000",
            "q": "1",
            "f": 1,
            "l": 2,
            "T": 100,
            "m": True,
        }
        trade = BinanceAggTradeData(data, "BTC-USDT", "SWAP", True)

        trade.init_data()
        first_price = trade.trade_price

        trade.init_data()
        assert trade.trade_price == first_price

    def test_get_all_data(self):
        """Test get_all_data method."""
        data = {
            "e": "aggTrade",
            "E": 123,
            "s": "BTCUSDT",
            "a": 1,
            "p": "50000",
            "q": "1",
            "f": 1,
            "l": 2,
            "T": 100,
            "m": True,
        }
        trade = BinanceAggTradeData(data, "BTC-USDT", "SWAP", True)

        result = trade.get_all_data()

        assert result["symbol_name"] == "BTC-USDT"
        assert result["trade_price"] == 50000.0

    def test_str_representation(self):
        """Test __str__ method."""
        data = {
            "e": "aggTrade",
            "E": 123,
            "s": "BTCUSDT",
            "a": 1,
            "p": "50000",
            "q": "1",
            "f": 1,
            "l": 2,
            "T": 100,
            "m": True,
        }
        trade = BinanceAggTradeData(data, "BTC-USDT", "SWAP", True)

        result = str(trade)
        parsed = json.loads(result)

        assert parsed["trade_symbol_name"] == "BTCUSDT"

    def test_maker_trade_type(self):
        """Test maker trade type detection."""
        data = {
            "e": "aggTrade",
            "E": 123,
            "s": "BTCUSDT",
            "a": 1,
            "p": "50000",
            "q": "1",
            "f": 1,
            "l": 2,
            "T": 100,
            "m": True,
        }
        trade = BinanceAggTradeData(data, "BTC-USDT", "SWAP", True)
        trade.init_data()

        assert trade.trade_type == "maker"

    def test_taker_trade_type(self):
        """Test taker trade type detection."""
        data = {
            "e": "aggTrade",
            "E": 123,
            "s": "BTCUSDT",
            "a": 1,
            "p": "50000",
            "q": "1",
            "f": 1,
            "l": 2,
            "T": 100,
            "m": False,
        }
        trade = BinanceAggTradeData(data, "BTC-USDT", "SWAP", True)
        trade.init_data()

        assert trade.trade_type == "taker"

    def test_all_getter_methods(self):
        """Test all getter methods."""
        data = {
            "e": "aggTrade",
            "E": 123,
            "s": "BTCUSDT",
            "a": 1,
            "p": "50000",
            "q": "1",
            "f": 1,
            "l": 2,
            "T": 100,
            "m": True,
        }
        trade = BinanceAggTradeData(data, "BTC-USDT", "SWAP", True)
        trade.init_data()

        assert trade.get_exchange_name() == "BINANCE"
        assert trade.get_asset_type() == "SWAP"
        assert trade.get_server_time() == 123.0
        assert trade.get_local_update_time() > 0
        assert trade.get_trade_id() == "1"
        assert trade.get_first_trade_id() == "1"
        assert trade.get_last_trade_id() == "2"
        assert trade.get_trade_symbol_name() == "BTCUSDT"
        assert trade.get_symbol_name() == "BTC-USDT"
        assert trade.get_trade_price() == 50000.0
        assert trade.get_trade_volume() == 1.0
        assert trade.get_trade_type() == "maker"
        assert trade.get_trade_time() == 100.0


class TestBinanceRequestTradeData:
    """Tests for BinanceRequestTradeData."""

    def test_init_data_with_json_string(self):
        """Test init_data with JSON string."""
        data = '{"id": 123, "symbol": "BTCUSDT", "orderId": 456, "side": "BUY", "price": "50000", "qty": "1", "time": 1700000000000, "maker": true, "commission": "0.1", "commissionAsset": "USDT"}'
        trade = BinanceRequestTradeData(data, "BTC-USDT", "SPOT", False)
        trade.init_data()

        assert trade.trade_symbol_name == "BTCUSDT"
        assert trade.trade_price == 50000.0
        assert trade.trade_type == "maker"

    def test_init_data_idempotent(self):
        """Test init_data is idempotent."""
        data = {
            "id": 123,
            "symbol": "BTCUSDT",
            "orderId": 456,
            "side": "BUY",
            "price": "50000",
            "qty": "1",
            "time": 1700000000000,
            "maker": False,
        }
        trade = BinanceRequestTradeData(data, "BTC-USDT", "SPOT", True)

        trade.init_data()
        first_price = trade.trade_price

        trade.init_data()
        assert trade.trade_price == first_price

    def test_str_representation(self):
        """Test __str__ method."""
        data = {
            "id": 123,
            "symbol": "BTCUSDT",
            "orderId": 456,
            "side": "BUY",
            "price": "50000",
            "qty": "1",
            "time": 1700000000000,
            "maker": False,
        }
        trade = BinanceRequestTradeData(data, "BTC-USDT", "SPOT", True)

        result = str(trade)
        parsed = json.loads(result)

        assert parsed["trade_symbol_name"] == "BTCUSDT"


class TestBinanceSwapWssTradeData:
    """Tests for BinanceSwapWssTradeData."""

    def test_init_data_with_json_string(self):
        """Test init_data with JSON string."""
        data = '{"E": 1700000000000, "o": {"s": "BTCUSDT", "c": "test", "i": 123, "L": "50000", "l": "1", "z": "1", "m": false, "T": 1700000000000, "n": "0.1", "N": "USDT", "ps": "LONG"}}'
        trade = BinanceSwapWssTradeData(data, "BTC-USDT", "SWAP", False)
        trade.init_data()

        assert trade.trade_symbol_name == "BTCUSDT"
        assert trade.trade_price == 50000.0
        assert trade.trade_side == "LONG"

    def test_init_data_idempotent(self):
        """Test init_data is idempotent."""
        data = {
            "E": 1700000000000,
            "o": {
                "s": "BTCUSDT",
                "c": "test",
                "i": 123,
                "L": "50000",
                "l": "1",
                "z": "1",
                "m": False,
                "T": 1700000000000,
                "n": "0.1",
                "N": "USDT",
                "ps": "LONG",
            },
        }
        trade = BinanceSwapWssTradeData(data, "BTC-USDT", "SWAP", True)

        trade.init_data()
        first_price = trade.trade_price

        trade.init_data()
        assert trade.trade_price == first_price


class TestBinanceSpotWssTradeData:
    """Tests for BinanceSpotWssTradeData."""

    def test_init_data(self):
        """Test init_data with dict data."""
        data = {
            "E": 1700000000000,
            "s": "BTCUSDT",
            "c": "test",
            "i": 123,
            "L": "50000",
            "l": "1",
            "z": "1",
            "m": False,
            "T": 1700000000000,
            "n": "0.1",
            "N": "USDT",
            "t": 456,
        }
        trade = BinanceSpotWssTradeData(data, "BTC-USDT", "SPOT", True)
        trade.init_data()

        assert trade.trade_symbol_name == "BTCUSDT"
        assert trade.trade_price == 50000.0

    def test_init_data_idempotent(self):
        """Test init_data is idempotent."""
        data = {
            "E": 1700000000000,
            "s": "BTCUSDT",
            "c": "test",
            "i": 123,
            "L": "50000",
            "l": "1",
            "z": "1",
            "m": False,
            "T": 1700000000000,
            "n": "0.1",
            "N": "USDT",
            "t": 456,
        }
        trade = BinanceSpotWssTradeData(data, "BTC-USDT", "SPOT", True)

        trade.init_data()
        first_price = trade.trade_price

        trade.init_data()
        assert trade.trade_price == first_price


def test_binance_agg_trade():
    """test_binance_agg_trade function"""
    data = {
        "e": "aggTrade",
        "E": 123456789,
        "s": "BNBUSDT",
        "a": 5933014,
        "p": "0.001",
        "q": "100",
        "f": 100,
        "l": 105,
        "T": 123456785,
        "m": True,
    }
    agg_trade = BinanceAggTradeData(data, "BNB-USDT", "SWAP", True)
    agg_trade.init_data()
    assert agg_trade.get_first_trade_id() == "100"
    assert agg_trade.get_last_trade_id() == "105"
    assert agg_trade.get_server_time() == 123456789
    assert agg_trade.get_trade_id() == "5933014"
    assert agg_trade.get_trade_price() == 0.001
    assert agg_trade.get_trade_volume() == 100
    assert agg_trade.get_trade_time() == 123456785
    assert agg_trade.get_trade_symbol_name() == "BNBUSDT"
    assert agg_trade.get_symbol_name() == "BNB-USDT"


def test_binance_spot_wss_trade():
    """test_binance_spot_wss_trade function"""
    data = {
        "e": "executionReport",
        "E": 1709103527340,
        "s": "OPUSDT",
        "c": "quYaDMgXvQGpI0M2Uztcdl",
        "S": "BUY",
        "o": "LIMIT",
        "f": "GTC",
        "q": "2.00000000",
        "p": "3.37900000",
        "P": "0.00000000",
        "F": "0.00000000",
        "g": -1,
        "C": "784164848349476186",
        "x": "CANCELED",
        "X": "CANCELED",
        "r": "NONE",
        "i": 1110157667,
        "l": "0.00000000",
        "z": "0.00000000",
        "L": "0.00000000",
        "n": "0",
        "N": None,
        "T": 1709103527340,
        "t": -1,
        "I": 2284358278,
        "w": False,
        "m": False,
        "M": False,
        "O": 1709103527220,
        "Z": "0.00000000",
        "Y": "0.00000000",
        "Q": "0.00000000",
        "W": 1709103527220,
        "V": "EXPIRE_MAKER",
    }
    spot_wss_trade = BinanceSpotWssTradeData(data, data["s"], "SPOT", True)
    spot_wss_trade.init_data()
    assert spot_wss_trade.get_trade_id() == "-1"
    assert spot_wss_trade.get_trade_price() == 0.0
    assert spot_wss_trade.get_trade_volume() == 0.0
    assert spot_wss_trade.get_trade_accumulate_volume() == 0.0


def test_binance_req_trade():
    """test_binance_req_trade function"""
    data = {
        "buyer": "false",  # 
        "commission": "-0.07819010",  # 
        "commissionAsset": "USDT",  # 
        "id": 698759,  # ID
        "maker": "false",  # 
        "orderId": 25851813,  # 
        "price": "7819.01",  # 
        "qty": "0.002",  # 
        "quoteQty": "15.63802",  # 
        "realizedPnl": "-0.91539999",  # 
        "side": "SELL",  # 
        "positionSide": "SHORT",  # 
        "symbol": "BTCUSDT",  # 
        "time": 1569514978020,  # 
    }
    bo = BinanceRequestTradeData(data, "BTC-USDT", "PERPETUAL", True)
    bo.init_data()
    assert bo.get_server_time() == 1569514978020.0
    assert bo.get_exchange_name() == "BINANCE"
    assert bo.get_asset_type() == "PERPETUAL"
    assert bo.get_trade_id() == "698759"
    assert bo.get_trade_symbol_name() == "BTCUSDT"
    assert bo.get_order_id() == "25851813"
    assert bo.get_client_order_id() is None
    assert bo.get_trade_side() == "SELL"
    assert bo.get_trade_offset() is None
    assert bo.get_trade_price() == 7819.01
    assert bo.get_trade_volume() == 0.002
    assert bo.get_trade_accumulate_volume() is None
    assert bo.get_trade_type() == "taker"
    assert bo.get_trade_time() == 1569514978020.0
    assert bo.get_trade_fee() == -0.07819010
    assert bo.get_trade_fee_symbol() == "USDT"


def test_binance_wss_trade():
    """test_binance_wss_trade function"""
    data = {
        "e": "ORDER_TRADE_UPDATE",  # 
        "E": 1568879465651,  # 
        "T": 1568879465650,  # 
        "o": {
            "s": "BTCUSDT",  # 
            "c": "TEST",  # ID
            # ID:
            # "autoclose-": 
            # "adl_autoclose": ADL
            # "settlement_autoclose-": 
            "S": "SELL",  # 
            "o": "TRAILING_STOP_MARKET",  # 
            "f": "GTC",  # 
            "q": "0.001",  # 
            "p": "0",  # 
            "ap": "0",  # 
            "sp": "7103.04",  # ，
            "x": "NEW",  # 
            "X": "NEW",  # 
            "i": 8886774,  # ID
            "l": "0",  # 
            "z": "0",  # 
            "L": "0",  # 
            "N": "USDT",  # 
            "n": "0",  # 
            "T": 1568879465650,  # 
            "t": 0,  # ID
            "b": "0",  # 
            "a": "9.91",  # 
            "m": False,  # ？
            "R": False,  # 
            "wt": "CONTRACT_PRICE",  # 
            "ot": "TRAILING_STOP_MARKET",  # 
            "ps": "LONG",  # 
            "cp": False,  # ; 
            "AP": "7476.89",  # , 
            "cr": "5.0",  # , 
            "pP": False,  # 
            "si": 0,  # 
            "ss": 0,  # 
            "rp": "0",  # 
            "V": "EXPIRE_TAKER",  # 
            "pm": "OPPONENT",  # 
            "gtd": 0,  # TIFGTD
        },
    }
    bo = BinanceSwapWssTradeData(data, "BTCUSDT", "PERPETUAL", True)
    bo.init_data()
    assert bo.get_server_time() == 1568879465651.0
    assert bo.get_exchange_name() == "BINANCE"
    assert bo.get_asset_type() == "PERPETUAL"
    assert bo.get_trade_id() == "0"
    assert bo.get_trade_symbol_name() == "BTCUSDT"
    assert bo.get_order_id() == "8886774"
    assert bo.get_client_order_id() == "TEST"
    assert bo.get_trade_side() == "LONG"
    assert bo.get_trade_offset() is None
    assert bo.get_trade_price() == 0.0
    assert bo.get_trade_volume() == 0.0
    assert bo.get_trade_accumulate_volume() == 0.0
    assert bo.get_trade_type() == "taker"
    assert bo.get_trade_time() == 1568879465650.0
    assert bo.get_trade_fee() == 0.0
    assert bo.get_trade_fee_symbol() == "USDT"


if __name__ == "__main__":
    test_binance_wss_trade()
    test_binance_req_trade()
