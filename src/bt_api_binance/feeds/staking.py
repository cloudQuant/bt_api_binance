"""Binance Staking API - .

 Binance  REST API ，：
- Staking 
- Staking 
- Staking 
- Staking 
- Staking 
"""

from __future__ import annotations

from typing import Any

from bt_api_base.functions.utils import update_extra_data
from bt_api_base.logging_factory import get_logger

from bt_api_binance.exchange_data import BinanceExchangeDataStaking

from .request_base import BinanceRequestData


class BinanceRequestDataStaking(BinanceRequestData):
    """Binance Staking API .

    。
    """

    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """__init__ method"""
        kwargs.setdefault("exchange_data", BinanceExchangeDataStaking())
        kwargs.setdefault("exchange_name", "binance_staking")
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "STAKING")
        self.logger_name = kwargs.get("logger_name", "binance_staking_feed.log")
        self._params = kwargs["exchange_data"]
        self.request_logger = get_logger("binance_staking_feed")
        self.async_logger = get_logger("binance_staking_feed")

    # ==================== Staking  ====================

    def _get_staking_products(
        self, product_type, asset=None, size=None, current=None, extra_data=None, **kwargs
    ):
        """ Staking .

        Args: product_type:  (STAKING, F_DEFI, L_DEFI)
            asset: 
            size: 
            current: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_staking_products"
        path = self._params.get_rest_path(request_type)
        params = {
            "type": product_type,
        }
        if asset is not None:
            params["asset"] = asset
        if size is not None:
            params["size"] = size
        if current is not None:
            params["current"] = current
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": asset or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_staking_products(
        self, product_type, asset=None, size=None, current=None, extra_data=None, **kwargs
    ):
        """ Staking .

        Returns: RequestData:

        """
        path, params, extra_data = self._get_staking_products(
            product_type=product_type,
            asset=asset,
            size=size,
            current=current,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _staking_purchase(self, product_id, amount, auto_renew=None, extra_data=None, **kwargs):
        """ Staking .

        Args: product_id: ID
            amount: 
            auto_renew: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "staking_purchase"
        path = self._params.get_rest_path(request_type)
        params = {
            "productId": product_id,
            "amount": amount,
        }
        if auto_renew is not None:
            params["renew"] = auto_renew
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": str(product_id),
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def staking_purchase(self, product_id, amount, auto_renew=None, extra_data=None, **kwargs):
        """ Staking .

        Returns: RequestData:

        """
        path, params, extra_data = self._staking_purchase(
            product_id=product_id,
            amount=amount,
            auto_renew=auto_renew,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _staking_redeem(self, product_id, amount, position_id=None, extra_data=None, **kwargs):
        """ Staking .

        Args: product_id: ID
            amount: 
            position_id: ID ()
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "staking_redeem"
        path = self._params.get_rest_path(request_type)
        params = {
            "productId": product_id,
            "amount": amount,
        }
        if position_id is not None:
            params["positionId"] = position_id
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": str(product_id),
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def staking_redeem(self, product_id, amount, position_id=None, extra_data=None, **kwargs):
        """ Staking .

        Returns: RequestData:

        """
        path, params, extra_data = self._staking_redeem(
            product_id=product_id,
            amount=amount,
            position_id=position_id,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_staking_position(
        self, product_type=None, asset=None, size=None, current=None, extra_data=None, **kwargs
    ):
        """ Staking .

        Args: product_type:  (STAKING, F_DEFI, L_DEFI)
            asset: 
            size: 
            current: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_staking_position"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if product_type is not None:
            params["type"] = product_type
        if asset is not None:
            params["asset"] = asset
        if size is not None:
            params["size"] = size
        if current is not None:
            params["current"] = current
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": asset or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_staking_position(
        self, product_type=None, asset=None, size=None, current=None, extra_data=None, **kwargs
    ):
        """ Staking .

        Returns: RequestData:

        """
        path, params, extra_data = self._get_staking_position(
            product_type=product_type,
            asset=asset,
            size=size,
            current=current,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_staking_history(
        self,
        product_type=None,
        asset=None,
        start_time=None,
        end_time=None,
        size=None,
        current=None,
        extra_data=None,
        **kwargs,
    ):
        """ Staking .

        Args: product_type:  (STAKING, F_DEFI, L_DEFI)
            asset: 
            start_time: 
            end_time: 
            size: 
            current: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_staking_history"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if product_type is not None:
            params["type"] = product_type
        if asset is not None:
            params["asset"] = asset
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if size is not None:
            params["size"] = size
        if current is not None:
            params["current"] = current
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": asset or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_staking_history(
        self,
        product_type=None,
        asset=None,
        start_time=None,
        end_time=None,
        size=None,
        current=None,
        extra_data=None,
        **kwargs,
    ):
        """ Staking .

        Returns: RequestData:

        """
        path, params, extra_data = self._get_staking_history(
            product_type=product_type,
            asset=asset,
            start_time=start_time,
            end_time=end_time,
            size=size,
            current=current,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data
