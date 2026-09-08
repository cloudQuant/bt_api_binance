"""Public Binance funding-schedule reads must not require account credentials."""

from unittest.mock import Mock, call

from bt_api_binance.feeds.swap import BinanceRequestDataSwap


def test_funding_info_and_history_use_unsigned_market_data_requests(monkeypatch):
    feed = BinanceRequestDataSwap()
    responses = [object(), object()]
    request = Mock(side_effect=responses)
    monkeypatch.setattr(feed, "request", request)

    assert feed.get_funding_info() is responses[0]
    assert feed.get_history_funding_rate("BTC-USDT", count=2) is responses[1]

    assert request.call_args_list == [
        call(
            "GET /fapi/v1/fundingInfo",
            params={},
            extra_data={
                "request_type": "get_funding_info",
                "symbol_name": "ALL",
                "asset_type": "SWAP",
                "exchange_name": "BINANCE___SWAP",
                "normalize_function": None,
            },
            is_sign=False,
        ),
        call(
            "GET /fapi/v1/fundingRate",
            params={"symbol": "BTCUSDT", "limit": 2},
            extra_data={
                "request_type": "get_history_funding_rate",
                "symbol_name": "BTC-USDT",
                "asset_type": "SWAP",
                "exchange_name": "BINANCE___SWAP",
                "normalize_function": feed._get_history_funding_rate_normalize_function,
            },
            is_sign=False,
        ),
    ]
