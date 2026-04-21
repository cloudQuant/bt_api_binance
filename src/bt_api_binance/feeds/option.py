from __future__ import annotations

from typing import Any

from bt_api_base.logging_factory import get_logger

from bt_api_binance.exchange_data import BinanceExchangeDataOption

from .account_wss_base import BinanceAccountWssData
from .market_wss_base import BinanceMarketWssData
from .request_base import BinanceRequestData


class BinanceRequestDataOption(BinanceRequestData):
    """Binance options request data handler."""

    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """Initialize Binance options request data handler.

        Args:
            data_queue: Queue for storing data.
            **kwargs: Additional keyword arguments including:
                - asset_type: Asset type (default: "OPTION")
                - logger_name: Logger name (default: "binance_option_feed.log")

        """
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "OPTION")
        self.logger_name = kwargs.get("logger_name", "binance_option_feed.log")
        self._params = BinanceExchangeDataOption()
        self.request_logger = get_logger("binance_option_feed")
        self.async_logger = get_logger("binance_option_feed")


class BinanceMarketWssDataOption(BinanceMarketWssData):
    """Binance options market WebSocket data handler."""

    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """Initialize Binance options market WebSocket data handler.

        Args:
            data_queue: Queue for storing data.
            **kwargs: Additional keyword arguments including:
                - asset_type: Asset type (default: "OPTION")

        """
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "OPTION")
        self._params = BinanceExchangeDataOption()


class BinanceAccountWssDataOption(BinanceAccountWssData):
    """Binance options account WebSocket data handler."""

    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """Initialize Binance options account WebSocket data handler.

        Args:
            data_queue: Queue for storing data.
            **kwargs: Additional keyword arguments.

        """
        super().__init__(data_queue, **kwargs)
        self._params = BinanceExchangeDataOption()
