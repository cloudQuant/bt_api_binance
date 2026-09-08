"""USD-M futures account configuration uses the dedicated signed endpoint."""

from unittest.mock import Mock

from bt_api_binance.feeds.swap import BinanceRequestDataSwap


def test_account_config_is_a_signed_read_only_request(monkeypatch):
    feed = BinanceRequestDataSwap(None, environment="demo")
    request = Mock(return_value={"canTrade": True})
    monkeypatch.setattr(feed, "request", request)
    try:
        assert feed.get_account_config() == {"canTrade": True}
        assert request.call_args.args == ("GET /fapi/v1/accountConfig",)
        params = request.call_args.kwargs["params"]
        extra_data = request.call_args.kwargs["extra_data"]
        assert params == {}
        assert extra_data["request_type"] == "get_account_config"
        assert request.call_args.kwargs["is_sign"] is True
    finally:
        feed._http_client.close()


def test_symbol_config_is_a_signed_read_only_request(monkeypatch):
    feed = BinanceRequestDataSwap(None, environment="demo")
    request = Mock(return_value=[{"symbol": "BTCUSDT", "leverage": 10}])
    monkeypatch.setattr(feed, "request", request)
    try:
        result = feed.get_symbol_config("BTCUSDT")
        assert result == [{"symbol": "BTCUSDT", "leverage": 10}]
        assert request.call_args.args == ("GET /fapi/v1/symbolConfig",)
        assert request.call_args.kwargs["params"] == {"symbol": "BTCUSDT"}
        assert request.call_args.kwargs["extra_data"]["request_type"] == "get_symbol_config"
        assert request.call_args.kwargs["is_sign"] is True
    finally:
        feed._http_client.close()
