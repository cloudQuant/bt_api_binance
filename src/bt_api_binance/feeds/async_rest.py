"""Binance 异步 REST 方法集合（mixin）。

从 request_base.py 拆分，供 BinanceRequestData 混入。
"""

from __future__ import annotations


class AsyncRestMixin:
    """异步 REST 方法集合。"""

    def async_get_server_time(self, extra_data=None, **kwargs):
        """async_get_server_time method"""
        path, params, extra_data = self._get_server_time(extra_data, **kwargs)
        self.submit(
            self.async_request(path, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_account(self, symbol=None, extra_data=None, **kwargs):
        """async_get_account method"""
        path, params, extra_data = self._get_account(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_get_balance(self, symbol=None, extra_data=None, **kwargs):
        """async_get_balance method"""
        path, params, extra_data = self._get_balance(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_sub_account(self, extra_data=None):
        """async_sub_account method"""
        path = self._params.get_rest_path("sub_account")
        params = {"subAcct": "xxx"}
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data),
            callback=self.async_callback,
        )

    def async_get_position(self, symbol, extra_data=None, **kwargs):
        """Get position info from okx by symbol using async
        :param symbol: default None, get all the currency, can be string, e.g. "BTC-USDT".
        :param extra_data: extra_data, default is None, can be a dict passed by user
        :param kwargs: pass key-worded, variable-length arguments.
        :return: RequestData.
        """
        path, params, extra_data = self._get_position(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_get_tick(self, symbol, extra_data=None, **kwargs):
        """async_get_tick method"""
        path, params, extra_data = self._get_tick(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_depth(self, symbol, size=20, extra_data=None, **kwargs):
        """async_get_depth method"""
        path, params, extra_data = self._get_depth(symbol, size, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    # noinspection PyMethodMayBeStatic
    def async_get_kline(
        self, symbol, period, count=100, start_time=None, end_time=None, extra_data=None, **kwargs
    ):
        """async_get_kline method"""
        path, params, extra_data = self._get_kline(
            symbol, period, count, start_time, end_time, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_funding_rate(self, symbol, extra_data=None, **kwargs):
        """async_get_funding_rate method"""
        path, params, extra_data = self._get_funding_rate(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data),
            callback=self.async_callback,
        )

    def async_get_mark_price(self, symbol, extra_data=None, **kwargs):
        """async_get_mark_price method"""
        path, params, extra_data = self._get_mark_price(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data),
            callback=self.async_callback,
        )

    def async_get_config(self, extra_data=None):
        """async_get_config method"""
        params = {
            # "posMode":"long_short_mode"
        }
        data_type = "get_config"
        path = self._params.get_rest_path(data_type)
        self.submit(
            self.async_request(path, body=params, extra_data=extra_data),
            callback=self.async_callback,
        )
        # data = self.request(path, body=params)

    def async_set_lever(self, symbol, extra_data=None):
        """async_set_lever method"""
        symbol = self._params.get_symbol(symbol)
        params = {"symbol": symbol, "lever": 10, "mgnMode": "cross"}
        data_type = "set_lever"
        path = self._params.get_rest_path(data_type)
        self.submit(
            self.async_request(path, body=params, extra_data=extra_data),
            callback=self.async_callback,
        )

    # noinspection PyBroadException
    def async_make_order(
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
        """async_make_order method"""
        path, params, extra_data = self._make_order(
            symbol, vol, price, order_type, offset, post_only, client_order_id, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_cancel_order(self, symbol, order_id=None, extra_data=None, **kwargs):
        """async_cancel_order method"""
        path, params, extra_data = self._cancel_order(symbol, order_id, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_query_order(self, symbol, order_id=None, extra_data=None, **kwargs):
        """async_query_order method"""
        path, params, extra_data = self._query_order(symbol, order_id, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    # noinspection PyBroadException
    def async_get_open_orders(self, symbol=None, extra_data=None, **kwargs):
        """async_get_open_orders method"""
        path, params, extra_data = self._get_open_orders(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_get_deals(
        self, symbol=None, count=100, start_time="", end_time="", extra_data=None, **kwargs
    ):
        """async_get_deals method"""
        path, params, extra_data = self._get_deals(
            symbol, count, start_time, end_time, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_get_clear_price(self, symbol, extra_data=None, **kwargs):
        """async_get_clear_price method"""
        data_type = "get_clear_price"
        path = self._params.get_rest_path(data_type)
        params = {"symbol": self._params.get_symbol(symbol)}
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data),
            callback=self.async_callback,
        )

    def async_get_agg_trades(
        self,
        symbol,
        from_id=None,
        start_time=None,
        end_time=None,
        count=500,
        extra_data=None,
        **kwargs,
    ):
        """async_get_agg_trades method"""
        path, params, extra_data = self._get_agg_trades(
            symbol, from_id, start_time, end_time, count, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_open_interest(self, symbol, extra_data=None, **kwargs):
        """async_get_open_interest method"""
        path, params, extra_data = self._get_open_interest(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_continuous_kline(
        self,
        pair,
        period,
        contract_type="PERPETUAL",
        count=100,
        start_time=None,
        end_time=None,
        extra_data=None,
        **kwargs,
    ):
        """async_get_continuous_kline method"""
        path, params, extra_data = self._get_continuous_kline(
            pair, period, contract_type, count, start_time, end_time, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_index_price_kline(
        self, pair, period, count=100, start_time=None, end_time=None, extra_data=None, **kwargs
    ):
        """async_get_index_price_kline method"""
        path, params, extra_data = self._get_index_price_kline(
            pair, period, count, start_time, end_time, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_mark_price_kline(
        self, symbol, period, count=100, start_time=None, end_time=None, extra_data=None, **kwargs
    ):
        """async_get_mark_price_kline method"""
        path, params, extra_data = self._get_mark_price_kline(
            symbol, period, count, start_time, end_time, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_funding_info(self, extra_data=None, **kwargs):
        """async_get_funding_info method"""
        path, params, extra_data = self._get_funding_info(extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_long_short_ratio(
        self,
        symbol,
        period="5m",
        count=30,
        start_time=None,
        end_time=None,
        extra_data=None,
        **kwargs,
    ):
        """async_get_long_short_ratio method"""
        path, params, extra_data = self._get_long_short_ratio(
            symbol, period, count, start_time, end_time, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_taker_buy_sell_volume(
        self,
        symbol,
        period="5m",
        count=30,
        start_time=None,
        end_time=None,
        extra_data=None,
        **kwargs,
    ):
        """async_get_taker_buy_sell_volume method"""
        path, params, extra_data = self._get_taker_buy_sell_volume(
            symbol, period, count, start_time, end_time, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=False),
            callback=self.async_callback,
        )

    def async_get_all_orders(
        self,
        symbol,
        order_id=None,
        start_time=None,
        end_time=None,
        count=500,
        extra_data=None,
        **kwargs,
    ):
        """async_get_all_orders method"""
        path, params, extra_data = self._get_all_orders(
            symbol, order_id, start_time, end_time, count, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_modify_order(
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
        """async_modify_order method"""
        path, params, extra_data = self._modify_order(
            symbol, order_id, orig_client_order_id, side, quantity, price, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_cancel_orders(
        self, symbol, order_id_list=None, client_order_id_list=None, extra_data=None, **kwargs
    ):
        """async_cancel_orders method"""
        path, params, extra_data = self._cancel_orders(
            symbol, order_id_list, client_order_id_list, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_cancel_all_orders(self, symbol, extra_data=None, **kwargs):
        """async_cancel_all_orders method"""
        path, params, extra_data = self._cancel_all_orders(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_get_leverage_bracket(self, symbol=None, extra_data=None, **kwargs):
        """async_get_leverage_bracket method"""
        path, params, extra_data = self._get_leverage_bracket(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_get_position_mode(self, extra_data=None, **kwargs):
        """async_get_position_mode method"""
        path, params, extra_data = self._get_position_mode(extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_get_income(
        self,
        symbol=None,
        income_type=None,
        start_time=None,
        end_time=None,
        count=100,
        extra_data=None,
        **kwargs,
    ):
        """async_get_income method"""
        path, params, extra_data = self._get_income(
            symbol, income_type, start_time, end_time, count, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_change_leverage(self, symbol, leverage, extra_data=None, **kwargs):
        """async_change_leverage method"""
        path, params, extra_data = self._change_leverage(symbol, leverage, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_change_margin_type(self, symbol, margin_type, extra_data=None, **kwargs):
        """async_change_margin_type method"""
        path, params, extra_data = self._change_margin_type(
            symbol, margin_type, extra_data, **kwargs
        )
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

    def async_get_fee(self, symbol, extra_data=None, **kwargs):
        """async_get_fee method"""
        path, params, extra_data = self._get_fee(symbol, extra_data, **kwargs)
        self.submit(
            self.async_request(path, params=params, extra_data=extra_data, is_sign=True),
            callback=self.async_callback,
        )

