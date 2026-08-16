"""Module-level docstring."""
from __future__ import annotations

from bt_api_base.containers.orders.order import OrderStatus

from bt_api_binance.containers.orders.binance_order import (
    BinanceForceOrderData,
    BinanceRequestOrderData,
    BinanceSpotWssOrderData,
    BinanceSwapWssOrderData,
)


def test_binance_force_order_data():
    """test_binance_force_order_data function"""
    data = {
        "e": "forceOrder",
        "E": 1568014460893,
        "o": {
            "s": "BTCUSDT",
            "S": "SELL",
            "o": "LIMIT",
            "f": "IOC",
            "q": "0.014",
            "p": "9910",
            "ap": "9910",
            "X": "FILLED",
            "l": "0.014",
            "z": "0.014",
            "T": 1568014460893,
        },
    }
    fo = BinanceForceOrderData(data, "BTC-USDT", "SWAP", True)
    fo.init_data()
    assert fo.get_trade_time() == 1568014460893
    assert fo.get_order_time_in_force() == "IOC"
    assert fo.get_asset_type() == "SWAP"
    assert fo.get_last_trade_volume() == 0.014
    assert fo.get_total_trade_volume() == 0.014
    assert fo.get_symbol_name() == "BTC-USDT"
    assert fo.get_order_side() == "SELL"
    assert fo.get_order_type() == "LIMIT"
    assert fo.get_order_price() == 9910
    assert fo.get_order_qty() == 0.014
    assert fo.get_order_avg_price() == 9910
    assert fo.get_order_status() == OrderStatus.COMPLETED


def test_binance_spot_wss_order():
    """test_binance_spot_wss_order function"""
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
    spot_wss_data = BinanceSpotWssOrderData(data, data["s"], "SPOT", True)
    spot_wss_data.init_data()
    assert spot_wss_data is not None
    assert spot_wss_data.get_order_id() == "1110157667"
    assert spot_wss_data.get_server_time() == 1709103527340.0
    assert spot_wss_data.get_trade_id() == -1.0
    assert spot_wss_data.get_client_order_id() == "quYaDMgXvQGpI0M2Uztcdl"
    assert spot_wss_data.get_executed_qty() == 0.0
    assert spot_wss_data.get_order_size() == 2.0
    assert spot_wss_data.get_asset_type() == "SPOT"
    assert spot_wss_data.get_order_price() == 3.379
    assert spot_wss_data.get_reduce_only() is None
    assert spot_wss_data.get_order_side() == "BUY"
    assert spot_wss_data.get_order_status() == OrderStatus.CANCELED
    assert spot_wss_data.get_order_symbol_name() == "OPUSDT"
    assert spot_wss_data.get_order_time_in_force() == "GTC"
    assert spot_wss_data.get_order_type() == "LIMIT"


def test_binance_wss_order():
    """test_binance_wss_order function"""
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
    bo = BinanceSwapWssOrderData(data, "BTC-USDT", "PERPETUAL", True)
    bo.init_data()
    assert bo.get_server_time() == 1568879465651.0
    assert bo.get_exchange_name() == "BINANCE"
    assert bo.get_trade_id() == 0
    assert bo.get_client_order_id() == "TEST"
    assert bo.get_cum_quote() is None
    assert bo.get_executed_qty() == 0.0
    assert bo.get_order_id() == "8886774"
    assert bo.get_order_size() == 0.001
    assert bo.get_order_price() == 0.0
    assert bo.get_reduce_only() is False
    assert bo.get_order_status() == OrderStatus.ACCEPTED
    assert bo.get_trailing_stop_price() == 7103.04
    assert bo.get_trailing_stop_trigger_price() == 7476.89
    assert bo.get_trailing_stop_callback_rate() == 5.0
    assert bo.get_order_symbol_name() == "BTCUSDT"
    assert bo.get_order_time_in_force() == "GTC"
    assert bo.get_order_type() == "TRAILING_STOP_MARKET"
    assert bo.get_trailing_stop_trigger_price_type() == "CONTRACT_PRICE"
    assert bo.get_order_avg_price() == 0.0
    assert bo.get_origin_order_type() == "TRAILING_STOP_MARKET"
    assert bo.get_position_side() == "LONG"
    assert bo.get_close_position() is False


def test_binance_req_order():
    """test_binance_req_order function"""
    data = {
        "clientOrderId": "testOrder",  # 
        "cumQty": "0",
        "cumQuote": "0",  # 
        "executedQty": "0",  # 
        "orderId": 22542179,  # 
        "avgPrice": "0.00000",  # 
        "origQty": "10",  # 
        "price": "0",  # 
        "reduceOnly": "false",  # 
        "side": "SELL",  # 
        "positionSide": "SHORT",  # 
        "status": "NEW",  # 
        "stopPrice": "0",  # ，`TRAILING_STOP_MARKET`
        "closePosition": "false",  # 
        "symbol": "BTCUSDT",  # 
        "timeInForce": "GTD",  # 
        "type": "TRAILING_STOP_MARKET",  # 
        "origType": "TRAILING_STOP_MARKET",  # 
        "activatePrice": "9020",  # , `TRAILING_STOP_MARKET` 
        "priceRate": "0.3",  # , `TRAILING_STOP_MARKET` 
        "updateTime": 1566818724722,  # 
        "workingType": "CONTRACT_PRICE",  # 
        "priceProtect": "false",  # 
        "priceMatch": "NONE",  # 
        "selfTradePreventionMode": "NONE",  # 
        "goodTillDate": 1693207680000,  # TIFGTD
    }
    bo = BinanceRequestOrderData(data, "BTC-USDT", "PERPETUAL", True)
    bo.init_data()
    assert bo.get_server_time() == 1566818724722.0
    assert bo.get_exchange_name() == "BINANCE"
    assert bo.get_trade_id() is None
    assert bo.get_client_order_id() == "testOrder"
    assert bo.get_cum_quote() == 0.0
    assert bo.get_executed_qty() == 0.0
    assert bo.get_order_id() == "22542179"
    assert bo.get_order_size() == 10.0
    assert bo.get_order_price() == 0.0
    assert bo.get_reduce_only() is False
    assert bo.get_order_status() == OrderStatus.ACCEPTED
    assert bo.get_trailing_stop_price() == 0.0
    assert bo.get_trailing_stop_trigger_price() == 9020
    assert bo.get_trailing_stop_callback_rate() == 0.3
    assert bo.get_order_symbol_name() == "BTCUSDT"
    assert bo.get_order_time_in_force() == "GTD"
    assert bo.get_order_type() == "TRAILING_STOP_MARKET"
    assert bo.get_trailing_stop_trigger_price_type() == "CONTRACT_PRICE"
    assert bo.get_order_avg_price() == 0.0
    assert bo.get_origin_order_type() == "TRAILING_STOP_MARKET"
    assert bo.get_position_side() == "SHORT"
    assert bo.get_close_position() is False


if __name__ == "__main__":
    test_binance_wss_order()
    test_binance_req_order()
