"""Binance Mining API - .

 Binance  REST API ，：
- 
- 
- 
"""

from __future__ import annotations

from typing import Any

from bt_api_base.functions.utils import update_extra_data
from bt_api_base.logging_factory import get_logger

from bt_api_binance.exchange_data import BinanceExchangeDataMining

from .request_base import BinanceRequestData


class BinanceRequestDataMining(BinanceRequestData):
    """Binance Mining API .

    。
    """

    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """__init__ method"""
        kwargs.setdefault("exchange_data", BinanceExchangeDataMining())
        kwargs.setdefault("exchange_name", "binance_mining")
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "MINING")
        self.logger_name = kwargs.get("logger_name", "binance_mining_feed.log")
        self._params = kwargs["exchange_data"]
        self.request_logger = get_logger("binance_mining_feed")
        self.async_logger = get_logger("binance_mining_feed")

    # ====================  ====================

    def _get_mining_algo_list(self, extra_data=None, **kwargs):
        """.

        Args: extra_data:
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_mining_algo_list"
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

    def get_mining_algo_list(self, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_mining_algo_list(extra_data=extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=False)
        return data

    def _get_mining_worker_list(self, algo, user_name, extra_data=None, **kwargs):
        """.

        Args: algo:  (: sha256)
            user_name: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_mining_worker_list"
        path = self._params.get_rest_path(request_type)
        params = {
            "algo": algo,
            "userName": user_name,
        }
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": algo,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_mining_worker_list(self, algo, user_name, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_mining_worker_list(
            algo=algo, user_name=user_name, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_mining_statistics(self, algo, user_name, extra_data=None, **kwargs):
        """.

        Args: algo:  (: sha256)
            user_name: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_mining_statistics"
        path = self._params.get_rest_path(request_type)
        params = {
            "algo": algo,
            "userName": user_name,
        }
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": algo,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_mining_statistics(self, algo, user_name, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_mining_statistics(
            algo=algo, user_name=user_name, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data
