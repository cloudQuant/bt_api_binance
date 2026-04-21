from __future__ import annotations

from typing import Any

from bt_api_base.logging_factory import get_logger

from bt_api_binance.exchange_data import BinanceExchangeDataSwap

from .account_wss_base import BinanceAccountWssData
from .market_wss_base import BinanceMarketWssData
from .request_base import BinanceRequestData


class BinanceRequestDataSwap(BinanceRequestData):
    def __init__(self, data_queue: Any = None, **kwargs: Any) -> None:
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "SWAP")
        self.logger_name = kwargs.get("logger_name", "binance_swap_feed.log")
        self._params = BinanceExchangeDataSwap()
        self.request_logger = get_logger("binance_swap_feed")
        self.async_logger = get_logger("binance_swap_feed")


class BinanceMarketWssDataSwap(BinanceMarketWssData):
    def __init__(self, data_queue: Any = None, **kwargs: Any) -> None:
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "SWAP")
        self._params = BinanceExchangeDataSwap()


class BinanceAccountWssDataSwap(BinanceAccountWssData):
    pass
