from __future__ import annotations

from importlib.util import find_spec

import bt_api_binance.gateway as gateway


def test_gateway_package_keeps_direct_client_but_drops_legacy_adapter() -> None:
    assert gateway.BinanceDirectClient.__module__ == "bt_api_binance.client"
    assert not hasattr(gateway, "BinanceGatewayAdapter")
    assert find_spec("bt_api_binance.gateway.adapter") is None


def test_gateway_package_keeps_account_session_provider_exports() -> None:
    assert gateway.BinanceUsdMAccountSessionProvider.__module__ == (
        "bt_api_binance.account_session_provider"
    )
    assert callable(gateway.make_binance_usdm_demo_provider)
