"""Private Binance transports reject incomplete credentials before I/O."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from bt_api_base.exceptions import ConfigurationError

from bt_api_binance import registry_registration as registry
from bt_api_binance.feeds.swap import BinanceAccountWssDataSwap, BinanceRequestDataSwap


@pytest.mark.parametrize(
    "credentials",
    [{}, {"api_key": "fixture-key"}, {"api_secret": "fixture-secret"}],
)
def test_private_rest_requires_key_and_secret_before_sync_or_async_network(credentials):
    feed = BinanceRequestDataSwap(None, environment="demo", **credentials)
    sync_network = Mock(side_effect=AssertionError("network must not run"))
    async_network = AsyncMock(side_effect=AssertionError("network must not run"))
    feed.http_request = sync_network
    feed.async_http_request = async_network

    with pytest.raises(ConfigurationError):
        feed.request("GET /fapi/v2/account", params={}, is_sign=True)
    with pytest.raises(ConfigurationError):
        asyncio.run(feed.async_request("GET /fapi/v2/account", params={}, is_sign=True))
    sync_network.assert_not_called()
    async_network.assert_not_awaited()
    feed._http_client.close()


@pytest.mark.parametrize(
    "credentials",
    [{}, {"api_key": "fixture-key"}, {"api_secret": "fixture-secret"}],
)
def test_private_websocket_requires_key_and_secret_before_construction(credentials):
    with pytest.raises(ValueError, match="both API key and secret"):
        BinanceAccountWssDataSwap(None, environment="demo", **credentials)


def test_partial_registry_credentials_fail_before_market_stream_construction(monkeypatch):
    market = Mock(side_effect=AssertionError("market transport must not be constructed"))
    monkeypatch.setattr(registry, "BinanceMarketWssDataSwap", market)
    api = type("Api", (), {"_subscription_flags": {}, "event_bus": None})()

    with pytest.raises(ValueError, match="both API key and secret"):
        registry._binance_swap_subscribe_handler(
            None, {"environment": "demo", "api_key": "fixture-key"}, [], api
        )
    market.assert_not_called()


@pytest.mark.parametrize(
    "credentials",
    [
        {"api_key": "   ", "api_secret": "fixture-secret"},
        {
            "api_key": "fixture-key-a",
            "public_key": "fixture-key-b",
            "api_secret": "fixture-secret",
        },
    ],
)
def test_malformed_or_conflicting_registry_credentials_are_zero_transport(monkeypatch, credentials):
    market = Mock(side_effect=AssertionError("market transport must not be constructed"))
    monkeypatch.setattr(registry, "BinanceMarketWssDataSwap", market)
    api = type("Api", (), {"_subscription_flags": {}, "event_bus": None})()
    with pytest.raises(ValueError):
        registry._binance_swap_subscribe_handler(
            None, {"environment": "demo", **credentials}, [], api
        )
    market.assert_not_called()
