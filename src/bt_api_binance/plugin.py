from __future__ import annotations

from typing import Any

from bt_api_base.plugins.protocol import PluginInfo
from bt_api_base.registry import ExchangeRegistry

from bt_api_binance import __version__
from bt_api_binance.gateway.adapter import BinanceGatewayAdapter
from bt_api_binance.registry_registration import register_binance


def register_plugin(registry: ExchangeRegistry, runtime_factory: Any) -> PluginInfo:
    register_binance(registry)
    runtime_factory.register_adapter("BINANCE", BinanceGatewayAdapter)

    return PluginInfo(
        name="bt_api_binance",
        version=__version__,
        core_requires=">=0.15,<1.0",
        supported_exchanges=("BINANCE___SPOT", "BINANCE___SWAP"),
        supported_asset_types=("SPOT", "SWAP"),
    )
