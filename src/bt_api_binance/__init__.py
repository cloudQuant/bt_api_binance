from __future__ import annotations

from bt_api_binance.client import BinanceDirectClient

__version__ = "2.0.1"

BinanceApi = BinanceDirectClient

__all__ = ["BinanceApi", "BinanceDirectClient", "__version__"]
