"""Module-level docstring."""
from __future__ import annotations

from bt_api_binance.containers.fundingrates.binance_funding_rate import (
    BinanceRequestFundingRateData,
    BinanceWssFundingRateData,
)


def test_binance_request_funding_rate():
    """test_binance_request_funding_rate function"""
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
    bf = BinanceRequestFundingRateData(data, "BTC-USDT", "SWAP", True)
    bf.init_data()
    assert bf.get_pre_funding_rate() is None
    assert bf.get_next_funding_rate() is None
    assert bf.get_pre_funding_time() is None
    assert bf.get_next_funding_time() == 1597392000000.0
    assert bf.get_current_funding_time() is None
    assert bf.get_current_funding_rate() == 0.00038246
    assert bf.get_server_time() == 1597370495002.0
    assert bf.get_event_type() == "FundingEvent"
    assert bf.get_symbol_name() == "BTC-USDT"
    assert bf.get_funding_rate_symbol_name() == "BTCUSDT"


def test_binance_funding_rate():
    """test_binance_funding_rate function"""
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
    bf = BinanceWssFundingRateData(data, "BTC-USDT", "PERPETUAL", True)
    bf.init_data()
    assert bf.get_pre_funding_rate() is None
    assert bf.get_current_funding_rate() == 0.00038167
    assert bf.get_pre_funding_time() is None
    assert bf.get_next_funding_time() == 1562306400000.0
    assert bf.get_server_time() == 1562305380000.0
    assert bf.get_event_type() == "FundingEvent"


if __name__ == "__main__":
    test_binance_request_funding_rate()
