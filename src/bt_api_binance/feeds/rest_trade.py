"""Binance 交易 REST 方法集合（mixin）。

从 request_base.py 拆分，供 BinanceRequestData 混入。
"""

from __future__ import annotations

from bt_api_base.functions.utils import update_extra_data


class RestTradeMixin:
    """交易 REST 方法集合。"""

    def _make_order(
        self,
        symbol,
        vol,
        price=None,
        order_type="buy-limit",
        offset="open",
        post_only=False,
        client_order_id=None,
        extra_data=None,
        **kwargs,
    ):


        request_symbol = self._params.get_symbol(symbol)
        request_type = "make_order"
        path = self._params.get_rest_path(request_type)
        side, order_type = order_type.split("-")
        side = side.upper()
        time_in_force = kwargs.get("time_in_force", "GTC")
        position_side = (
            kwargs.get("position_side")
            or kwargs.get("positionSide")
            or kwargs.get("posSide")
        )
        reduce_only = kwargs.get("reduceOnly")
        if reduce_only in (None, ""):
            reduce_only = kwargs.get("reduce_only")
        params = {
            "symbol": request_symbol,
            "side": side,
            "quantity": vol,
            "price": price,
            "type": order_type.upper(),
            "timeInForce": time_in_force,
        }
        if self.asset_type == "SWAP":
            params["reduceOnly"] = (
                str(reduce_only).lower()
                if reduce_only not in (None, "")
                else "false" if offset == "open" else "true" if offset == "close" else None
            )
        if client_order_id is not None:
            params["newClientOrderId"] = client_order_id
        if order_type == "market":
            params.pop("timeInForce", None)
            params.pop("price", None)
        if position_side not in (None, ""):
            params["positionSide"] = str(position_side).upper()
            params.pop("reduceOnly", None)
        elif self.asset_type != "SWAP":
            params.pop("reduceOnly", None)

        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "post_only": post_only,
                "normalize_function": self._make_order_normalize_function,
            },
        )
        # if kwargs is not None:
        #     extra_data.update(kwargs)
        return path, params, extra_data

    # noinspection PyBroadException
    def make_order(
        self,
        symbol,
        vol,
        price=None,
        order_type="buy-limit",
        offset="open",
        post_only=False,
        client_order_id=None,
        extra_data=None,
        **kwargs,
    ):
        """make_order method"""
        path, params, extra_data = self._make_order(
            symbol, vol, price, order_type, offset, post_only, client_order_id, extra_data, **kwargs
        )
        # print("params = ", params)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _cancel_order(self, symbol, order_id=None, extra_data=None, **kwargs):
        """Cancel order by order_id using async
        :param symbol: default None, get all the currency, can be string, e.g. "BTC-USDT".
        :param order_id: order_id, default is None, can be a string passed by user
        :param extra_data: extra_data, default is None, can be a dict passed by user
        :param kwargs: pass key-worded, variable-length arguments.
        :return: RequestData
        :return:
        """
        request_symbol = self._params.get_symbol(symbol)
        # request_symbol = symbol
        request_type = "cancel_order"
        path = self._params.get_rest_path(request_type)
        # update params
        params = {
            "symbol": request_symbol,
        }
        if order_id:
            params["orderId"] = order_id
        if "client_order_id" in kwargs:
            params["origClientOrderId"] = kwargs["client_order_id"]
        # update params
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": request_symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": self._cancel_order_normalize_function,
            },
        )
        return path, params, extra_data

    def cancel_order(self, symbol, order_id=None, extra_data=None, **kwargs):
        """cancel_order method"""
        path, params, extra_data = self._cancel_order(symbol, order_id, extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    # noinspection PyBroadException
    def _query_order(self, symbol, order_id=None, extra_data=None, **kwargs):
        request_symbol = self._params.get_symbol(symbol)
        request_type = "query_order"
        path = self._params.get_rest_path(request_type)
        # path = path.replace("<instrument_id>", symbol)
        # path = path.replace("<order_id>", str(order_id))
        # update params
        params = {
            "symbol": request_symbol,
        }
        if order_id is not None:
            params["orderId"] = order_id
        if "client_order_id" in kwargs:
            params["origClientOrderId"] = kwargs["client_order_id"]
        # update extra_data
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": self._query_order_normalize_function,
            },
        )
        return path, params, extra_data

    # noinspection PyBroadException
    def query_order(self, symbol, order_id=None, extra_data=None, **kwargs):
        """query_order method"""
        path, params, extra_data = self._query_order(symbol, order_id, extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _modify_order(
        self,
        symbol,
        order_id=None,
        orig_client_order_id=None,
        side=None,
        quantity=None,
        price=None,
        extra_data=None,
        **kwargs,
    ):
        request_type = "modify_order"
        request_symbol = self._params.get_symbol(symbol)
        params = {"symbol": request_symbol}
        if order_id is not None:
            params["orderId"] = order_id
        if orig_client_order_id is not None:
            params["origClientOrderId"] = orig_client_order_id
        if side is not None:
            params["side"] = side.upper()
        if quantity is not None:
            params["quantity"] = quantity
        if price is not None:
            params["price"] = price
        path = self._params.get_rest_path(request_type)
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": self._make_order_normalize_function,
            },
        )
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def modify_order(
        self,
        symbol,
        order_id=None,
        orig_client_order_id=None,
        side=None,
        quantity=None,
        price=None,
        extra_data=None,
        **kwargs,
    ):
        """modify_order method"""
        path, params, extra_data = self._modify_order(
            symbol, order_id, orig_client_order_id, side, quantity, price, extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _cancel_orders(
        self, symbol, order_id_list=None, client_order_id_list=None, extra_data=None, **kwargs
    ):
        request_type = "cancel_orders"
        request_symbol = self._params.get_symbol(symbol)
        params = {"symbol": request_symbol}
        if order_id_list is not None:
            params["orderIdList"] = str(order_id_list)
        if client_order_id_list is not None:
            params["origClientOrderIdList"] = str(client_order_id_list)
        path = self._params.get_rest_path(request_type)
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": self._cancel_order_normalize_function,
            },
        )
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def cancel_orders(
        self, symbol, order_id_list=None, client_order_id_list=None, extra_data=None, **kwargs
    ):
        """cancel_orders method"""
        path, params, extra_data = self._cancel_orders(
            symbol, order_id_list, client_order_id_list, extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _cancel_all_orders(self, symbol, extra_data=None, **kwargs):
        request_type = "cancel_all"
        request_symbol = self._params.get_symbol(symbol)
        params = {"symbol": request_symbol}
        path = self._params.get_rest_path(request_type)
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
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def cancel_all_orders(self, symbol, extra_data=None, **kwargs):
        """cancel_all_orders method"""
        path, params, extra_data = self._cancel_all_orders(symbol, extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_all_orders(
        self,
        symbol,
        order_id=None,
        start_time=None,
        end_time=None,
        count=500,
        extra_data=None,
        **kwargs,
    ):
        request_type = "get_all_orders"
        request_symbol = self._params.get_symbol(symbol)
        params = {"symbol": request_symbol, "limit": count}
        if order_id is not None:
            params["orderId"] = order_id
        if start_time is not None:
            if isinstance(start_time, str):
                start_time = int(datetime2timestamp(start_time) * 1000)
            params["startTime"] = start_time
        if end_time is not None:
            if isinstance(end_time, str):
                end_time = int(datetime2timestamp(end_time) * 1000)
            params["endTime"] = end_time
        path = self._params.get_rest_path(request_type)
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": self._query_order_normalize_function,
            },
        )
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def get_all_orders(
        self,
        symbol,
        order_id=None,
        start_time=None,
        end_time=None,
        count=500,
        extra_data=None,
        **kwargs,
    ):
        """get_all_orders method"""
        path, params, extra_data = self._get_all_orders(
            symbol, order_id, start_time, end_time, count, extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data







    def set_mode(self):
        """set_mode method"""
        params = {"posMode": "long_short_mode"}
        path = self._params.get_rest_path("set_mode")
        data = self.request(path, body=params)
        return data

    def set_lever(self, symbol):
        """set_lever method"""
        symbol = self._params.get_symbol(symbol)
        params = {"symbol": symbol, "lever": 10, "mgnMode": "cross"}
        path = self._params.get_rest_path("set_lever")
        data = self.request(path, body=params)
        return data




    def get_config(self, extra_data=None):
        """get_config method"""
        params: dict[str, Any] = {}
        path = self._params.get_rest_path("get_config")
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": "get_config",
                "symbol_name": "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        data = self.request(path, params=params, extra_data=extra_data)
        return data


    def _change_leverage(self, symbol, leverage, extra_data=None, **kwargs):
        request_type = "change_leverage"
        request_symbol = self._params.get_symbol(symbol)
        params = {
            "symbol": request_symbol,
            "leverage": leverage,
        }
        path = self._params.get_rest_path(request_type)
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
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def change_leverage(self, symbol, leverage, extra_data=None, **kwargs):
        """change_leverage method"""
        path, params, extra_data = self._change_leverage(symbol, leverage, extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _change_margin_type(self, symbol, margin_type, extra_data=None, **kwargs):
        request_type = "change_margin_type"
        request_symbol = self._params.get_symbol(symbol)
        params = {
            "symbol": request_symbol,
            "marginType": margin_type,
        }
        path = self._params.get_rest_path(request_type)
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
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def change_margin_type(self, symbol, margin_type, extra_data=None, **kwargs):
        """change_margin_type method"""
        path, params, extra_data = self._change_margin_type(
            symbol, margin_type, extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_leverage_bracket(self, symbol=None, extra_data=None, **kwargs):
        request_type = "get_leverage_bracket"
        params: dict[str, Any] = {}
        if symbol is not None:
            params["symbol"] = self._params.get_symbol(symbol)
        path = self._params.get_rest_path(request_type)
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
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def get_leverage_bracket(self, symbol=None, extra_data=None, **kwargs):
        """get_leverage_bracket method"""
        path, params, extra_data = self._get_leverage_bracket(symbol, extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_position_mode(self, extra_data=None, **kwargs):
        request_type = "get_position_mode"
        params: dict[str, Any] = {}
        path = self._params.get_rest_path(request_type)
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
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def get_position_mode(self, extra_data=None, **kwargs):
        """get_position_mode method"""
        path, params, extra_data = self._get_position_mode(extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_income(
        self,
        symbol=None,
        income_type=None,
        start_time=None,
        end_time=None,
        count=100,
        extra_data=None,
        **kwargs,
    ):
        request_type = "get_income"
        params = {"limit": count}
        if symbol is not None:
            params["symbol"] = self._params.get_symbol(symbol)
        if income_type is not None:
            params["incomeType"] = income_type
        if start_time is not None:
            if isinstance(start_time, str):
                start_time = int(datetime2timestamp(start_time) * 1000)
            params["startTime"] = start_time
        if end_time is not None:
            if isinstance(end_time, str):
                end_time = int(datetime2timestamp(end_time) * 1000)
            params["endTime"] = end_time
        path = self._params.get_rest_path(request_type)
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
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def get_income(
        self,
        symbol=None,
        income_type=None,
        start_time=None,
        end_time=None,
        count=100,
        extra_data=None,
        **kwargs,
    ):
        """get_income method"""
        path, params, extra_data = self._get_income(
            symbol, income_type, start_time, end_time, count, extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data





    def _get_fee(self, symbol, extra_data=None, **kwargs):
        request_type = "get_fee"
        request_symbol = self._params.get_symbol(symbol)
        params = {"symbol": request_symbol}
        path = self._params.get_rest_path(request_type)
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
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def get_fee(self, symbol, extra_data=None, **kwargs):
        """get_fee method"""
        path, params, extra_data = self._get_fee(symbol, extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

