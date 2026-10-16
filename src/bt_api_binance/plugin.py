"""Module-level docstring."""
from __future__ import annotations

from typing import TYPE_CHECKING

from bt_api_base.plugins.protocol import PluginInfo

from bt_api_binance import __version__
from bt_api_binance.registry_registration import register_binance

if TYPE_CHECKING:
    from bt_api_base.registry import ExchangeRegistry


def register_plugin(registry: ExchangeRegistry) -> PluginInfo:
    """register_plugin function"""
    register_binance(registry)
    return PluginInfo(
        name="bt_api_binance",
        version=__version__,
        core_requires=">=0.15,<1.0",
        supported_exchanges=("BINANCE___SPOT", "BINANCE___SWAP"),
        supported_asset_types=("SPOT", "SWAP"),
    )
