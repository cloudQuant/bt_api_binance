"""Binance Portfolio Margin API - .

 Binance  REST API ，：
- 
- 
- 
"""

from __future__ import annotations

from typing import Any

from bt_api_base.functions.utils import update_extra_data
from bt_api_base.logging_factory import get_logger

from bt_api_binance.exchange_data import BinanceExchangeDataPortfolio

from .request_base import BinanceRequestData


class BinanceRequestDataPortfolio(BinanceRequestData):
    """Binance Portfolio Margin API .

    。
    """

    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """__init__ method"""
        kwargs.setdefault("exchange_data", BinanceExchangeDataPortfolio())
        kwargs.setdefault("exchange_name", "binance_portfolio")
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "PORTFOLIO")
        self.logger_name = kwargs.get("logger_name", "binance_portfolio_feed.log")
        self._params = kwargs["exchange_data"]
        self.request_logger = get_logger("binance_portfolio_feed")
        self.async_logger = get_logger("binance_portfolio_feed")

    # ====================  ====================

    def _get_portfolio_account(self, extra_data=None, **kwargs):
        """.

        Args: extra_data:
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_portfolio_account"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_portfolio_account(self, extra_data=None, **kwargs) -> Any:
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_portfolio_account(extra_data=extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_portfolio_collateral_rate(self, asset_type=None, extra_data=None, **kwargs):
        """.

        Args: asset_type:  (: USDT)
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_portfolio_collateral_rate"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if asset_type is not None:
            params["assetType"] = asset_type
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": asset_type or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_portfolio_collateral_rate(self, asset_type=None, extra_data=None, **kwargs) -> Any:
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_portfolio_collateral_rate(
            asset_type=asset_type, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _portfolio_transfer(self, asset, amount, transfer_type, extra_data=None, **kwargs):
        """.

        Args: asset:
            amount: 
            transfer_type:  (SPOT_TO_PORTFOLIO, PORTFOLIO_TO_SPOT)
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "portfolio_transfer"
        path = self._params.get_rest_path(request_type)
        params = {
            "asset": asset,
            "amount": amount,
            "type": transfer_type,
        }
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": asset,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def portfolio_transfer(self, asset, amount, transfer_type, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._portfolio_transfer(
            asset=asset, amount=amount, transfer_type=transfer_type, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data
