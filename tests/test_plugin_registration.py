from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from bt_api_base.gateway.registrar import GatewayRuntimeRegistrar
from bt_api_base.plugins.loader import PluginLoader
from bt_api_base.plugins.protocol import PluginInfo
from bt_api_base.registry import ExchangeRegistry
from bt_api_py.testing import create_isolated_exchange_registry, reset_gateway_runtime_registrar

from bt_api_binance.gateway.adapter import BinanceGatewayAdapter
from bt_api_binance.feeds.spot import BinanceRequestDataSpot
from bt_api_binance.feeds.swap import BinanceRequestDataSwap
from bt_api_binance.plugin import register_plugin


@dataclass
class _EntryPoint:
    name: str = "binance"
    module: str = "bt_api_binance.plugin"

    def load(self) -> Any:
        module = import_module(self.module)
        return module.register_plugin


class _RuntimeFactory:
    def __init__(self) -> None:
        self.adapters: dict[str, type[Any]] = {}

    def register_adapter(self, exchange_type: str, adapter_cls: type[Any]) -> None:
        self.adapters[exchange_type] = adapter_cls


def setup_function() -> None:
    ExchangeRegistry.clear()
    reset_gateway_runtime_registrar()


def test_register_plugin_returns_plugin_info():
    runtime_factory = _RuntimeFactory()
    registry = create_isolated_exchange_registry()
    info = register_plugin(registry, runtime_factory)

    assert isinstance(info, PluginInfo)
    assert info.name == "bt_api_binance"
    assert info.version == "2.0.0"
    assert info.supported_exchanges == ("BINANCE___SPOT", "BINANCE___SWAP")
    assert info.supported_asset_types == ("SPOT", "SWAP")
    assert registry.get_feed_class("BINANCE___SPOT") is BinanceRequestDataSpot
    assert registry.get_feed_class("BINANCE___SWAP") is BinanceRequestDataSwap
    assert runtime_factory.adapters["BINANCE"] is BinanceGatewayAdapter


def test_plugin_loader_loads_binance_plugin(monkeypatch):
    loader = PluginLoader(ExchangeRegistry, GatewayRuntimeRegistrar)
    monkeypatch.setattr(loader, "_discover_entry_points", lambda group: [_EntryPoint()])

    loader.load_all()

    assert "bt_api_binance" in loader.loaded
    assert loader.loaded["bt_api_binance"].plugin_module == "bt_api_binance.plugin"
    assert ExchangeRegistry.get_feed_class("BINANCE___SPOT") is BinanceRequestDataSpot
    assert ExchangeRegistry.get_feed_class("BINANCE___SWAP") is BinanceRequestDataSwap
    assert GatewayRuntimeRegistrar.get_adapter("BINANCE") is BinanceGatewayAdapter
