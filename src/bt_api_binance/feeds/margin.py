"""Module-level docstring."""
from __future__ import annotations

from typing import Any

from bt_api_base.functions.utils import update_extra_data
from bt_api_base.logging_factory import get_logger

from bt_api_binance.containers.accounts.binance_account import BinanceSpotWssAccountData
from bt_api_binance.containers.orders.binance_order import BinanceSpotWssOrderData
from bt_api_binance.containers.trades.binance_trade import BinanceSpotWssTradeData
from bt_api_binance.exchange_data import BinanceExchangeDataMargin

from .account_wss_base import BinanceAccountWssData
from .market_wss_base import BinanceMarketWssData
from .request_base import BinanceRequestData


class BinanceRequestDataMargin(BinanceRequestData):
    """Class BinanceRequestDataMargin"""
    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """__init__ method"""
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "MARGIN")
        self.logger_name = kwargs.get("logger_name", "binance_margin_feed.log")
        self._params = BinanceExchangeDataMargin()
        self.request_logger = get_logger("binance_margin_feed")
        self.async_logger = get_logger("binance_margin_feed")

    # ====================  ====================

    def _get_cross_margin_data(self, extra_data=None, **kwargs):
        """.

        Args: extra_data:
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_cross_margin_data"
        path = self._params.get_rest_path(request_type)
        params: dict[str, object] = {}
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

    def get_cross_margin_data(self, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_cross_margin_data(extra_data=extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_isolated_margin_data(self, symbols=None, extra_data=None, **kwargs):
        """.

        Args: symbols:  ()
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_isolated_margin_data"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if symbols is not None:
            params["symbols"] = symbols
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbols or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_isolated_margin_data(self, symbols=None, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_isolated_margin_data(
            symbols=symbols, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_capital_flow(
        self, asset=None, start_time=None, end_time=None, limit=None, extra_data=None, **kwargs
    ):
        """.

        Args: asset:
            start_time: 
            end_time: 
            limit: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_capital_flow"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if asset is not None:
            params["asset"] = asset
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
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

    def get_capital_flow(
        self, asset=None, start_time=None, end_time=None, limit=None, extra_data=None, **kwargs
    ):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_capital_flow(
            asset=asset,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    # ==================== BNB ====================

    def _get_bnb_burn(self, extra_data=None, **kwargs):
        """BNB.

        Args: extra_data:
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_bnb_burn"
        path = self._params.get_rest_path(request_type)
        params: dict[str, object] = {}
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": "BNB",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_bnb_burn(self, extra_data=None, **kwargs):
        """BNB.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_bnb_burn(extra_data=extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _toggle_bnb_burn(self, extra_data=None, **kwargs):
        """BNB.

        Args: extra_data:
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "toggle_bnb_burn"
        path = self._params.get_rest_path(request_type)
        params: dict[str, object] = {}
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": "BNB",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def toggle_bnb_burn(self, extra_data=None, **kwargs):
        """BNB.

        Returns: RequestData:

        """
        path, params, extra_data = self._toggle_bnb_burn(extra_data=extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    # ====================  ====================

    def _manual_liquidation(self, symbol=None, extra_data=None, **kwargs):
        """.

        Args: symbol:
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "manual_liquidation"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if symbol is not None:
            request_symbol = self._params.get_symbol(symbol)
            params["symbol"] = request_symbol
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbol or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def manual_liquidation(self, symbol=None, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._manual_liquidation(
            symbol=symbol, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _exchange_small_liability(self, asset_names=None, extra_data=None, **kwargs):
        """.

        Args: asset_names:  ()
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "exchange_small_liability"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if asset_names is not None:
            params["assetNames"] = asset_names
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": asset_names or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def exchange_small_liability(self, asset_names=None, extra_data=None, **kwargs):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._exchange_small_liability(
            asset_names=asset_names, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_small_liability_history(
        self, asset=None, start_time=None, end_time=None, limit=None, extra_data=None, **kwargs
    ):
        """.

        Args: asset:
            start_time: 
            end_time: 
            limit: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_small_liability_history"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if asset is not None:
            params["asset"] = asset
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
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

    def get_small_liability_history(
        self, asset=None, start_time=None, end_time=None, limit=None, extra_data=None, **kwargs
    ):
        """.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_small_liability_history(
            asset=asset,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _set_max_leverage(self, max_leverage, extra_data=None, **kwargs):
        """.

        Args: max_leverage:  (1-125)
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "set_max_leverage"
        path = self._params.get_rest_path(request_type)
        params = {
            "maxLeverage": max_leverage,
        }
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

    def set_max_leverage(self, max_leverage, extra_data=None, **kwargs):
        """.

        Args: max_leverage:  (1-125)

        Returns: RequestData:

        """
        path, params, extra_data = self._set_max_leverage(
            max_leverage=max_leverage, extra_data=extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data


class BinanceMarketWssDataMargin(BinanceMarketWssData):
    """Class BinanceMarketWssDataMargin"""
    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """__init__ method"""
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "MARGIN")
        self._params = BinanceExchangeDataMargin()


class BinanceAccountWssDataMargin(BinanceAccountWssData):
    """Class BinanceAccountWssDataMargin"""
    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """__init__ method"""
        super().__init__(data_queue, **kwargs)
        self._params = BinanceExchangeDataMargin()

    def handle_data(self, content):
        """ WebSocket .

        :
        - executionReport: 
        - outboundAccountPosition: 
        - balanceUpdate:  ()
        """
        event = content.get("e", None)
        if event is not None:
            #  ()
            if event == "executionReport" and content.get("x", None) != "TRADE":
                self.push_order(content)
            # 
            if event == "outboundAccountPosition":
                self.push_account(content)
            # 
            if event == "executionReport" and content.get("x", None) == "TRADE":
                self.push_trade(content)
            #  ()
            if event == "balanceUpdate":
                self.push_balance(content)

    def push_account(self, content):
        """."""
        symbol = "ALL"
        account_data = BinanceSpotWssAccountData(content, symbol, self.asset_type, True)
        self.data_queue.put(account_data)

    def push_order(self, content):
        """."""
        symbol = content["s"]
        order_data = BinanceSpotWssOrderData(content, symbol, self.asset_type, True)
        self.data_queue.put(order_data)

    def push_trade(self, content):
        """."""
        symbol = content["s"]
        trade_data = BinanceSpotWssTradeData(content, symbol, self.asset_type, True)
        self.data_queue.put(trade_data)

    def push_balance(self, content):
        """ ()."""
        # balanceUpdate : {e: "balanceUpdate", E: 1573200697114, s: "BTC", u: "15896533547050558808", B: "500.00000000"}
        #  Spot ，
        symbol = content.get("s", "ALL")
        balance_data = BinanceSpotWssAccountData(content, symbol, self.asset_type, True)
        self.data_queue.put(balance_data)
