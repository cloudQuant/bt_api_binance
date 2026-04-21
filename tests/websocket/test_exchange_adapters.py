from __future__ import annotations

from bt_api_py.websocket.exchange_adapters import ExchangeType, WebSocketAdapterFactory

from bt_api_binance.websocket.exchange_adapters import BinanceWebSocketAdapter


def test_plugin_binance_websocket_adapter_imports_directly():
    adapter = BinanceWebSocketAdapter(exchange_type=ExchangeType.SWAP)

    assert "wss://dstream.binance.com" in adapter.get_endpoints("wss://example.com")


def test_core_factory_loads_plugin_binance_websocket_adapter():
    adapter = WebSocketAdapterFactory.create_adapter("BINANCE___SWAP")

    assert isinstance(adapter, BinanceWebSocketAdapter)
    assert adapter.exchange_type == ExchangeType.SWAP
