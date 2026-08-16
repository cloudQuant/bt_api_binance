"""Module-level docstring."""
from __future__ import annotations

from bt_api_base.websocket.exchange_adapters import ExchangeType, WebSocketAdapterFactory

from bt_api_binance.websocket.exchange_adapters import BinanceWebSocketAdapter


def test_plugin_binance_websocket_adapter_imports_directly():
    """test_plugin_binance_websocket_adapter_imports_directly function"""
    adapter = BinanceWebSocketAdapter(exchange_type=ExchangeType.SWAP)

    assert "wss://dstream.binance.com" in adapter.get_endpoints("wss://example.com")


def test_core_factory_loads_plugin_binance_websocket_adapter():
    """test_core_factory_loads_plugin_binance_websocket_adapter function"""
    adapter = WebSocketAdapterFactory.create_adapter("BINANCE___SWAP")

    assert isinstance(adapter, BinanceWebSocketAdapter)
    assert adapter.exchange_type == ExchangeType.SWAP
