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


class BinanceRequestDataWallet(BinanceRequestData):
    """Binance Wallet API .

    ，、、、。
    """

    def __init__(self, data_queue: Any = None, **kwargs: Any) -> None:
        """__init__ method"""
        kwargs.setdefault("exchange_data", BinanceExchangeDataWallet())
        kwargs.setdefault("exchange_name", "binance_wallet")
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "WALLET")
        self.logger_name = kwargs.get("logger_name", "binance_wallet_feed.log")
        self._params = kwargs["exchange_data"]
        self.request_logger = get_logger("binance_wallet_feed")
        self.async_logger = get_logger("binance_wallet_feed")

    # ====================  ====================

    def _get_wallet_balance(self, extra_data=None, **kwargs):
        """.

        Args: extra_data:
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_wallet_balance"
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

    def get_wallet_balance(self, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_wallet_balance(extra_data=extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_asset_detail(self, extra_data=None, **kwargs):
        """.

        Args: extra_data:
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_asset_detail"
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

    def get_asset_detail(self, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_asset_detail(extra_data=extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_asset_ledger(
        self, asset=None, startTime=None, endTime=None, limit=None, extra_data=None, **kwargs
    ):
        """.

        Args: asset:
            startTime: 
            endTime: 
            limit: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_asset_ledger"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if asset is not None:
            params["asset"] = asset
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit
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

    def get_asset_ledger(
        self, asset=None, startTime=None, endTime=None, limit=None, extra_data=None, **kwargs
    ):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_asset_ledger(
            asset=asset,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_asset_dividend(
        self, asset=None, startTime=None, endTime=None, limit=None, extra_data=None, **kwargs
    ):
        """.

        Args: asset:
            startTime: 
            endTime: 
            limit: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_asset_dividend"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if asset is not None:
            params["asset"] = asset
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit
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

    def get_asset_dividend(
        self, asset=None, startTime=None, endTime=None, limit=None, extra_data=None, **kwargs
    ):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_asset_dividend(
            asset=asset,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    # ====================  ====================

    def _asset_transfer(
        self,
        transfer_type,
        asset,
        amount,
        from_symbol=None,
        to_symbol=None,
        extra_data=None,
        **kwargs,
    ):
        """.

        Args: transfer_type:  (SPOT, UM, CM, MARGIN, ISOLATED_MARGIN, etc.)
            asset: 
            amount: 
            from_symbol:  ( ISOLATED_MARGIN)
            to_symbol:  ( ISOLATED_MARGIN)
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "asset_transfer"
        path = self._params.get_rest_path(request_type)
        params = {
            "type": transfer_type,
            "asset": asset,
            "amount": amount,
        }
        if from_symbol is not None:
            params["fromSymbol"] = from_symbol
        if to_symbol is not None:
            params["toSymbol"] = to_symbol
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

    def asset_transfer(
        self,
        transfer_type,
        asset,
        amount,
        from_symbol=None,
        to_symbol=None,
        extra_data=None,
        **kwargs,
    ):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._asset_transfer(
            transfer_type=transfer_type,
            asset=asset,
            amount=amount,
            from_symbol=from_symbol,
            to_symbol=to_symbol,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_asset_transfer(
        self,
        transfer_type=None,
        startTime=None,
        endTime=None,
        limit=None,
        extra_data=None,
        **kwargs,
    ):
        """.

        Args: transfer_type:
            startTime: 
            endTime: 
            limit: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_asset_transfer"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if transfer_type is not None:
            params["type"] = transfer_type
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit
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

    def get_asset_transfer(
        self,
        transfer_type=None,
        startTime=None,
        endTime=None,
        limit=None,
        extra_data=None,
        **kwargs,
    ):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_asset_transfer(
            transfer_type=transfer_type,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _transfer_to_futures_main(self, asset, amount, extra_data=None, **kwargs):
        """.

        Args: asset:
            amount: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "transfer_to_futures_main"
        path = self._params.get_rest_path(request_type)
        params = {
            "asset": asset,
            "amount": amount,
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

    def transfer_to_futures_main(self, asset, amount, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._transfer_to_futures_main(
            asset=asset, amount=amount, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _transfer_to_futures_sub(self, email, asset, amount, extra_data=None, **kwargs):
        """.

        Args: email:
            asset: 
            amount: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "transfer_to_futures_sub"
        path = self._params.get_rest_path(request_type)
        params = {
            "email": email,
            "asset": asset,
            "amount": amount,
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

    def transfer_to_futures_sub(self, email, asset, amount, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._transfer_to_futures_sub(
            email=email, asset=asset, amount=amount, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _transfer_to_um(self, asset, amount, extra_data=None, **kwargs):
        """U.

        Args: asset:
            amount: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "transfer_to_um"
        path = self._params.get_rest_path(request_type)
        params = {
            "asset": asset,
            "amount": amount,
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

    def transfer_to_um(self, asset, amount, extra_data=None, **kwargs):
        """U.

        Returns: RequestData:

        """
        path, params, extra_data = self._transfer_to_um(
            asset=asset, amount=amount, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _transfer_to_isolated_margin(self, asset, symbol, amount, extra_data=None, **kwargs):
        """.

        Args: asset:
            symbol: 
            amount: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "transfer_to_isolated_margin"
        path = self._params.get_rest_path(request_type)
        params = {
            "asset": asset,
            "symbol": symbol,
            "amount": amount,
        }
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def transfer_to_isolated_margin(self, asset, symbol, amount, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._transfer_to_isolated_margin(
            asset=asset, symbol=symbol, amount=amount, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    # ====================  ====================

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
