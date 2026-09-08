"""Module-level docstring."""
from __future__ import annotations

from typing import Any

from bt_api_base.logging_factory import get_logger

from bt_api_binance.environment import verify_environment
from bt_api_binance.exchange_data import BinanceExchangeDataSwap

from .account_wss_base import BinanceAccountWssData
from .market_wss_base import BinanceMarketWssData
from .request_base import BinanceRequestData


class BinanceRequestDataSwap(BinanceRequestData):
    """Class BinanceRequestDataSwap"""
    def __init__(self, data_queue: Any = None, **kwargs: Any) -> None:
        """__init__ method"""
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "SWAP")
        self.logger_name = kwargs.get("logger_name", "binance_swap_feed.log")
        self._params = self._configure_exchange_data(BinanceExchangeDataSwap())
        self.request_logger = get_logger("binance_swap_feed")
        self.async_logger = get_logger("binance_swap_feed")

    def get_environment_info(self):
        """Return the plugin's current endpoint proof without credentials."""
        return verify_environment(self._params)


class BinanceMarketWssDataSwap(BinanceMarketWssData):
    """Class BinanceMarketWssDataSwap"""
    def __init__(self, data_queue: Any = None, **kwargs: Any) -> None:
        """__init__ method"""
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "SWAP")
        self._params = self._configure_exchange_data(BinanceExchangeDataSwap())


class BinanceAccountWssDataSwap(BinanceAccountWssData):
    """Class BinanceAccountWssDataSwap"""
