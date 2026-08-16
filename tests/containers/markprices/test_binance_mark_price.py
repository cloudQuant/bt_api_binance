# import json
"""Module-level docstring."""
from __future__ import annotations

from bt_api_binance.containers.markprices.binance_mark_price import (
    BinanceRequestMarkPriceData,
    BinanceWssMarkPriceData,
)


def test_binance_request_mark_price():
    """test_binance_request_mark_price function"""
    data = {
        "symbol": "BTCUSDT",  # 
        "markPrice": "11793.63104562",  # 
        "indexPrice": "11781.80495970",  # 
        "estimatedSettlePrice": "11781.16138815",  # ,
        "lastFundingRate": "0.00038246",  # 
        "nextFundingTime": 1597392000000,  # 
        "interestRate": "0.00010000",  # 
        "time": 1597370495002,  # 
    }
    bp = BinanceRequestMarkPriceData(data, "BTC-USDT", "SWAP", True)
    bp.init_data()
    assert bp.get_server_time() == 1597370495002.0
    assert bp.get_exchange_name() == "BINANCE"
    assert bp.get_symbol_name() == "BTC-USDT"
    assert bp.get_mark_price() == 11793.63104562
    assert bp.get_index_price() == 11781.80495970
    assert bp.get_settlement_price() == 11781.16138815
    assert bp.get_event() == "MarkPriceEvent"


def test_binance_mark_price():
    """test_binance_mark_price function"""
    data = {
        "e": "markPriceUpdate",  # 
        "E": 1562305380000,  # 
        "s": "BTCUSDT",  # 
        "p": "11794.15000000",  # 
        "i": "11784.62659091",  # 
        "P": "11784.25641265",  # ,
        "r": "0.00038167",  # 
        "T": 1562306400000,  # 
    }
    bp = BinanceWssMarkPriceData(data, "BTC-USDT", "PERPETUAL", True)
    bp.init_data()
    assert bp.get_server_time() == 1562305380000.0
    assert bp.get_exchange_name() == "BINANCE"
    assert bp.get_symbol_name() == "BTC-USDT"
    assert bp.get_mark_price_symbol_name() == "BTCUSDT"
    assert bp.get_mark_price() == 11794.15000000
    assert bp.get_index_price() == 11784.62659091
    assert bp.get_settlement_price() == 11784.25641265
    assert bp.get_event() == "MarkPriceEvent"


if __name__ == "__main__":
    test_binance_mark_price()
