"""Compatibility gateway adapter backed by the core plugin bridge."""

from __future__ import annotations

from bt_api_base.gateway.adapters.plugin_adapter import PluginGatewayAdapter

from bt_api_binance.client import BinanceDirectClient


class BinanceGatewayAdapter(PluginGatewayAdapter):
    direct_client_cls = BinanceDirectClient
