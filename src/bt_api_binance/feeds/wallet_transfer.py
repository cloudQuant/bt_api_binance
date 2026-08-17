"""Binance Wallet API - .

 Binance  REST API ，：
-  (、、、)
-  (、、)
-  (、)
-  (、、)
-  (Dust)
"""

from __future__ import annotations

from typing import Any

from bt_api_base.functions.utils import update_extra_data
from bt_api_base.logging_factory import get_logger

from bt_api_binance.exchange_data import BinanceExchangeDataWallet

from .request_base import BinanceRequestData




class WalletTransferMixin:
    """钱包充提/流水方法集合。"""

    def _withdraw(
        self,
        coin,
        address,
        amount,
        network=None,
        addressTag=None,
        name=None,
        extra_data=None,
        **kwargs,
    ):
        """.

        Args: coin:
            address: 
            amount: 
            network: 
            addressTag: 
            name: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "withdraw"
        path = self._params.get_rest_path(request_type)
        params = {
            "coin": coin,
            "address": address,
            "amount": amount,
        }
        if network is not None:
            params["network"] = network
        if addressTag is not None:
            params["addressTag"] = addressTag
        if name is not None:
            params["name"] = name
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": coin,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def withdraw(
        self,
        coin,
        address,
        amount,
        network=None,
        addressTag=None,
        name=None,
        extra_data=None,
        **kwargs,
    ):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._withdraw(
            coin=coin,
            address=address,
            amount=amount,
            network=network,
            addressTag=addressTag,
            name=name,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_withdraw_history(
        self,
        coin=None,
        startTime=None,
        endTime=None,
        limit=None,
        offset=None,
        extra_data=None,
        **kwargs,
    ):
        """.

        Args: coin:
            startTime: 
            endTime: 
            limit: 
            offset: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_withdraw_history"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if coin is not None:
            params["coin"] = coin
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": coin or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_withdraw_history(
        self,
        coin=None,
        startTime=None,
        endTime=None,
        limit=None,
        offset=None,
        extra_data=None,
        **kwargs,
    ):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_withdraw_history(
            coin=coin,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
            offset=offset,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_deposit_address(self, coin, network=None, extra_data=None, **kwargs):
        """.

        Args: coin:
            network: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_deposit_address"
        path = self._params.get_rest_path(request_type)
        params = {
            "coin": coin,
        }
        if network is not None:
            params["network"] = network
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": coin,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_deposit_address(self, coin, network=None, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_deposit_address(
            coin=coin, network=network, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_deposit_history(
        self,
        coin=None,
        startTime=None,
        endTime=None,
        limit=None,
        offset=None,
        extra_data=None,
        **kwargs,
    ):
        """.

        Args: coin:
            startTime: 
            endTime: 
            limit: 
            offset: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_deposit_history"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if coin is not None:
            params["coin"] = coin
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": coin or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_deposit_history(
        self,
        coin=None,
        startTime=None,
        endTime=None,
        limit=None,
        offset=None,
        extra_data=None,
        **kwargs,
    ):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_deposit_history(
            coin=coin,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
            offset=offset,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    # ====================  ====================





    def _get_withdraw_address(self, coin=None, extra_data=None, **kwargs):
        """.

        Args: coin:
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_withdraw_address"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if coin is not None:
            params["coin"] = coin
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": coin or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_withdraw_address(self, coin=None, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_withdraw_address(
            coin=coin, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    # ====================  ====================

    def _get_dust(self, extra_data=None, **kwargs):
        """.

        Args: extra_data:
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_dust"
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

    def get_dust(self, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_dust(extra_data=extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _dust_transfer(self, assets, extra_data=None, **kwargs):
        """BTC.

        Args: assets:  ()
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "dust_transfer"
        path = self._params.get_rest_path(request_type)
        params = {
            "asset": assets if isinstance(assets, str) else ",".join(assets),
        }
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": "DUST",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def dust_transfer(self, assets, extra_data=None, **kwargs):
        """BTC.

        Returns: RequestData:

        """
        path, params, extra_data = self._dust_transfer(
            assets=assets, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

