"""Current-endpoint verification for Binance execution environments."""

from __future__ import annotations

import pytest

from bt_api_binance.feeds.swap import BinanceRequestDataSwap


@pytest.mark.parametrize(
    "feed_type,environment,expected_environment,simulated",
    [
        (BinanceRequestDataSwap, "demo", "demo", True),
        (BinanceRequestDataSwap, "production", "production", False),
    ],
)
def test_current_official_endpoints_are_verified(
    feed_type, environment: str, expected_environment: str, simulated: bool
) -> None:
    feed = feed_type(None, environment=environment)
    try:
        assert feed.get_environment_info() == {
            "environment": expected_environment,
            "simulated": simulated,
            "verified": True,
        }
    finally:
        feed._http_client.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("rest_url", "https://fapi.binance.com"),
        ("rest_url", "https://demo-fapi.binance.com.evil.invalid"),
        ("rest_url", "https://demo-fapi.binance.com:8443"),
        ("rest_url", "https://demo-fapi.binance.com/evil"),
        ("rest_url", "https://demo-fapi.binance.com?signature=fixture"),
        ("rest_url", "https://demo-fapi.binance.com#fragment"),
        ("rest_url", "http://demo-fapi.binance.com"),
        ("wss_url", "wss://fstream.binance.com/ws"),
        ("wss_url", "wss://demo-fstream.binance.com:8443/ws"),
        ("wss_url", "wss://demo-fstream.binance.com/evil"),
        ("wss_url", "wss://demo-fstream.binance.com/ws?listenKey=fixture"),
        ("acct_wss_url", "wss://demo-fstream.binance.com.evil.invalid/ws"),
    ],
)
def test_mutated_demo_endpoint_invalidates_environment_proof(field: str, value: str) -> None:
    feed = BinanceRequestDataSwap(None, environment="demo")
    try:
        setattr(feed._params, field, value)
        assert feed.get_environment_info() == {
            "environment": "demo",
            "simulated": True,
            "verified": False,
        }
    finally:
        feed._http_client.close()


def test_demo_rest_non_default_port_is_rejected_during_configuration() -> None:
    with pytest.raises(ValueError, match="Invalid rest_url"):
        BinanceRequestDataSwap(
            None,
            environment="demo",
            rest_url="https://demo-fapi.binance.com:8443",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("rest_url", "https://demo-fapi.binance.com/evil"),
        ("rest_url", "https://demo-fapi.binance.com?signature=fixture"),
        ("wss_url", "wss://demo-fstream.binance.com:8443/ws"),
        ("wss_url", "wss://demo-fstream.binance.com/ws?listenKey=fixture"),
        ("acct_wss_url", "wss://demo-fstream.binance.com/ws#fragment"),
    ],
)
def test_demo_endpoint_path_query_fragment_and_port_are_rejected(
    field: str, value: str
) -> None:
    with pytest.raises(ValueError, match=f"Invalid {field}"):
        BinanceRequestDataSwap(None, environment="demo", **{field: value})


def test_production_override_cannot_change_official_host() -> None:
    with pytest.raises(ValueError, match="rest_url conflicts"):
        BinanceRequestDataSwap(
            None,
            environment="production",
            rest_url="https://example.invalid",
        )
