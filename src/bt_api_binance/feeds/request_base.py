"""Module documentation"""

from __future__ import annotations

import hmac
import time
from typing import Any

# import threading
# from urllib import parse
from urllib.parse import urlencode

from bt_api_base.containers.requestdatas.request_data import RequestData
from bt_api_base.exceptions import ConfigurationError, QueueNotInitializedError
from bt_api_base.feeds.capability import Capability
from bt_api_base.feeds.feed import Feed
from bt_api_base.functions.utils import update_extra_data
from bt_api_base.logging_factory import get_logger
from bt_api_base.rate_limiter import RateLimiter, RateLimitRule, RateLimitScope, RateLimitType

from bt_api_binance.environment import configure_environment
from bt_api_binance.errors.binance_translator import BinanceErrorTranslator
from bt_api_binance.exchange_data import (
    BinanceExchangeDataSwap,
)
from bt_api_binance.feeds.async_rest import AsyncRestMixin
from bt_api_binance.feeds.normalize import NormalizeMixin
from bt_api_binance.feeds.rest_derivatives import RestDerivativesMixin
from bt_api_binance.feeds.rest_market import RestMarketMixin
from bt_api_binance.feeds.rest_trade import RestTradeMixin


def strict_credential_alias(parameters, names):
    supplied = []
    for name in names:
        if name not in parameters or parameters[name] is None:
            continue
        value = parameters[name]
        if value == "":
            continue
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ConfigurationError("Binance credentials must be non-empty trimmed strings")
        supplied.append(value)
    if len(set(supplied)) > 1:
        raise ConfigurationError("Binance credential aliases conflict")
    return supplied[0] if supplied else None


# session = requests.Session()
# session.keep_alive = False
# adapter = requests.adapters.HTTPAdapter(
#     max_retries=5, #
#     pool_connections=100, #
#     pool_maxsize=100, #
#     pool_block=True, # )
# session.mount('http://', adapter)
# session.mount('https://', adapter)


class BinanceRequestData(
    NormalizeMixin, AsyncRestMixin, RestMarketMixin, RestTradeMixin, RestDerivativesMixin, Feed
):
    """Class BinanceRequestData"""

    @classmethod
    def _capabilities(cls) -> set[Capability]:
        return {
            Capability.GET_TICK,
            Capability.GET_DEPTH,
            Capability.GET_KLINE,
            Capability.GET_FUNDING_RATE,
            Capability.GET_MARK_PRICE,
            Capability.MAKE_ORDER,
            Capability.CANCEL_ORDER,
            Capability.QUERY_ORDER,
            Capability.QUERY_OPEN_ORDERS,
            Capability.GET_DEALS,
            Capability.GET_BALANCE,
            Capability.GET_ACCOUNT,
            Capability.GET_POSITION,
            Capability.MARKET_STREAM,
            Capability.ACCOUNT_STREAM,
            Capability.CROSS_MARGIN,
            Capability.ISOLATED_MARGIN,
            Capability.HEDGE_MODE,
            Capability.BATCH_ORDER,
            Capability.OCO_ORDER,
            Capability.GET_EXCHANGE_INFO,
            Capability.GET_SERVER_TIME,
        }

    def __init__(self, data_queue: Any = None, **kwargs: Any) -> None:
        """__init__ method"""
        self._environment_options = dict(kwargs)
        super().__init__(data_queue, **kwargs)
        self.data_queue = data_queue
        self.public_key = strict_credential_alias(kwargs, ("public_key", "api_key"))
        self.private_key = strict_credential_alias(
            kwargs, ("private_key", "secret_key", "api_secret")
        )
        self.exchange_name = kwargs.get("exchange_name", "BINANCE___SWAP")
        self.asset_type = kwargs.get("asset_type", "SWAP")
        self.logger_name = kwargs.get("logger_name", "binance_swap_feed.log")
        self._params = self._configure_exchange_data(
            kwargs.get("exchange_data") or BinanceExchangeDataSwap()
        )
        self.request_logger = get_logger("binance_swap_feed")
        self.async_logger = get_logger("binance_swap_feed")
        self._error_translator = BinanceErrorTranslator()
        self._rate_limiter = kwargs.get("rate_limiter", self._create_default_rate_limiter())
        # self.start_loop()  #

    def get_exchange_info(self, symbol=None, extra_data=None, **kwargs):
        """Return public exchangeInfo with symbols, filters and rate limits intact."""
        # USD-M exchangeInfo does not accept a symbol filter.
        params = (
            {"symbol": self._params.get_symbol(symbol)}
            if symbol and self.asset_type == "SPOT"
            else {}
        )
        return self.request(
            self._params.get_rest_path("get_contract"),
            params=params,
            extra_data=extra_data,
            is_sign=False,
        )

    def _configure_exchange_data(self, params):
        return configure_environment(params, self._environment_options)

    @staticmethod
    def _create_default_rate_limiter():
        rules = [
            RateLimitRule(
                name="binance_request_weight",
                limit=2400,
                interval=60,
                type=RateLimitType.SLIDING_WINDOW,
                scope=RateLimitScope.GLOBAL,
            ),
            RateLimitRule(
                name="binance_order_rate",
                limit=300,
                interval=10,
                type=RateLimitType.SLIDING_WINDOW,
                scope=RateLimitScope.ENDPOINT,
                endpoint="/fapi/v1/order*",
            ),
        ]
        return RateLimiter(rules)

    def translate_error(self, raw_response):
        """Binance API  UnifiedError（）， None."""
        if isinstance(raw_response, dict):
            code = raw_response.get("code")
            if code is not None and int(code) < 0:
                return self._error_translator.translate(raw_response, self.exchange_name)
        return None

    def _raise_if_error(self, raw_response):
        """API 响应含错误(code<0)时抛出翻译后的 UnifiedError，否则静默返回。"""
        error = self.translate_error(raw_response)
        if error is not None:
            raise error

    def push_data_to_queue(self, data):
        """push_data_to_queue method"""
        if self.data_queue is not None:
            self.data_queue.put(data)
        else:
            raise QueueNotInitializedError("data_queue not initialized")

    # noinspection PyMethodMayBeStatic
    # def signature(self, timestamp, method, request_path, secret_key, body=None):
    #     if body is None:
    #         body = ''
    #     else:
    #         body = str(body)
    #     message = str(timestamp) + str.upper(method) + request_path + body
    #     mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    #     d = mac.digest()
    #     return base64.b64encode(d).decode()

    def sign(self, content):
        """.

        Args: content (TYPE): Description

        """
        if self.private_key is None:
            raise ConfigurationError("private key is required for signed requests")
        pk = self.private_key
        sign = hmac.new(
            pk.encode("utf-8"), (content or "").encode("utf-8"), digestmod="sha256"
        ).hexdigest()

        return sign

    def _require_private_credentials(self):
        """Reject partial private credentials before constructing any request."""
        if (
            not isinstance(self.public_key, str)
            or not self.public_key.strip()
            or not isinstance(self.private_key, str)
            or not self.private_key.strip()
        ):
            raise ConfigurationError("Binance private requests require both API key and secret")

    # set request header
    # noinspection PyMethodMayBeStatic
    def request(self, path, params=None, body=None, extra_data=None, timeout=10, is_sign=True):
        """Http request function
        Args: path (TYPE): request url
            params (dict, optional): in url
            body (dict, optional): in request body
            extra_data(dict,None): extra_data, generate by user
            timeout (int, optional): request timeout(s)
            is_sign (bool, optional): is need signature.
        """
        if params is None:
            params: dict[str, Any] = {}
        if extra_data is None:
            extra_data = {}
        # if body is None:
        #     body = {}
        method, path = path.split(" ", 1)
        if is_sign is False:
            req = params
        else:
            self._require_private_credentials()
            req = {
                "recvWindow": 60000,
                "timestamp": int(time.time() * 1000),
            }
            req.update(params)
            sign = urlencode(req)
            req["signature"] = self.sign(sign)
            # req['signature'] = self.sign(str(req))
        req = urlencode(req)
        url = f"{self._params.rest_url}{path}?{req}"
        headers = {"X-MBX-APIKEY": self.public_key} if self.public_key else {}
        # print("url ", url)
        # print("headers ", headers)
        # print("method ", method)
        # print("body ", body)
        # print("request_type", request_type)
        # print(f"self.public_key:{self.public_key}")
        # print(f"self.private_key:{self.private_key}")
        if method.upper() == "GET":
            res = self.http_request(method, url, headers, body, timeout)
        else:
            res = self.http_request(method, url, headers, body, timeout, max_retries=1)
        self._raise_if_error(res)
        # print("res", res)
        # data_factory = self._params.request_data_dict.get(request_type)
        return RequestData(res, extra_data)

    def _get_account(self, symbol=None, extra_data=None, **kwargs):
        """Get account info using async
        :param symbol: default None, get all the currency, can be string, e.g. "BTC-USDT".
        :param extra_data: extra_data, default is None, can be a dict passed by user
        :param kwargs: pass key-worded, variable-length arguments.
        :return: RequestData.
        """
        request_type = "get_account"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": BinanceRequestData._get_account_normalize_function,
            },
        )
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def get_account(self, symbol=None, extra_data=None, **kwargs):
        """get_account method"""
        path, params, extra_data = self._get_account(symbol, extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_balance(self, symbol=None, extra_data=None, **kwargs):
        """Get balance info using async
        :param symbol: default None, get all the currency, can be string, e.g. "BTC-USDT".
        :param extra_data: extra_data, default is None, can be a dict passed by user
        :param kwargs: pass key-worded, variable-length arguments.
        :return: RequestData.
        """
        request_type = "get_balance"
        # request_symbol = self._params.get_symbol(symbol)
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": BinanceRequestData._get_balance_normalize_function,
            },
        )
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def get_balance(self, symbol=None, extra_data=None, **kwargs):
        """get_balance method"""
        path, params, extra_data = self._get_balance(symbol, extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_position(self, symbol=None, extra_data=None, **kwargs):
        """Get position info from okx by symbol
        :param symbol: default None, get all the currency, can be string, e.g. "BTC-USDT".
        :param extra_data: extra_data, default is None, can be a dict passed by user
        :param kwargs: pass key-worded, variable-length arguments.
        :return: RequestData.
        """
        request_symbol = self._params.get_symbol(symbol) if symbol else None
        request_type = "get_position"
        path = self._params.get_rest_path(request_type)
        params = {"symbol": request_symbol} if request_symbol else {}
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": BinanceRequestData._get_position_normalize_function,
            },
        )
        if kwargs is not None:
            extra_data.update(kwargs)
        return path, params, extra_data

    def get_position(self, symbol: Any = None, extra_data: Any = None, **kwargs: Any) -> Any:
        """Get position info from okx by symbol
        :param symbol: default None, get all the currency, can be string, e.g. "BTC-USDT".
        :param extra_data: extra_data, default is None, can be a dict passed by user
        :param kwargs: pass key-worded, variable-length arguments.
        :return: RequestData.
        """
        path, params, extra_data = self._get_position(symbol, extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data)
        return data

    def _get_server_time(self, extra_data=None, **kwargs):
        request_symbol = "ALL"
        request_type = "get_server_time"
        path = self._params.get_rest_path(request_type)
        if extra_data is None:
            extra_data = kwargs
        else:
            extra_data.update(kwargs)
        params: dict[str, Any] = {}
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": request_symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_server_time(self, extra_data=None, **kwargs):
        """get_server_time method"""
        path, params, extra_data = self._get_server_time(extra_data=extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=False)
        return data

    def _get_open_orders(self, symbol=None, extra_data=None, **kwargs):
        """Get open orders by symbol using async
        :param symbol: default None, get all the currency, can be string, e.g. "BTC-USDT".
        :param extra_data: extra_data, default is None, can be a dict passed by user
        :param kwargs: pass key-worded, variable-length arguments.
        :return: RequestData.
        """
        if symbol is not None:
            request_symbol = self._params.get_symbol(symbol)
            params = {"symbol": request_symbol}
        else:
            request_symbol = ""
            params: dict[str, Any] = {}
        request_type = "get_open_orders"
        if "recv_window" in kwargs:
            params["recvWindow"] = kwargs["recv_window"]
        path = self._params.get_rest_path(request_type)
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": request_symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": BinanceRequestData._get_open_orders_normalize_function,
            },
        )
        return path, params, extra_data

    # noinspection PyBroadException
    def get_open_orders(self, symbol=None, extra_data=None, **kwargs):
        """get_open_orders method"""
        path, params, extra_data = self._get_open_orders(symbol, extra_data, **kwargs)
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_deals(
        self, symbol=None, count=100, start_time="", end_time="", extra_data=None, **kwargs
    ):
        """Get history trade records from okx
        :param symbol: , btc/usdt
        :param count: , 100, 100
        :param start_time: ,
        :param end_time: ,
        :param extra_data:
        :return:
        """
        # params = {'instType': instType, 'uly': uly, 'symbol': symbol,
        #           'ordId': ordId, 'after': after, 'before': before,
        #           'limit': limit, 'instFamily': instFamily}
        if symbol is not None:
            request_symbol = self._params.get_symbol(symbol)
            params = {"symbol": request_symbol}
        else:
            request_symbol = ""
            params: dict[str, Any] = {}
        request_type = "get_deals"
        if count:
            params["limit"] = count
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        if "from_id" in kwargs:
            params["fromId"] = kwargs["from_id"]
        path = self._params.get_rest_path(request_type)
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": request_symbol,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": BinanceRequestData._get_deals_normalize_function,
            },
        )
        return path, params, extra_data

    # noinspection PyBroadException
    def get_deals(
        self, symbol=None, count=100, start_time="", end_time="", extra_data=None, **kwargs
    ):
        """get_deals method"""
        path, params, extra_data = self._get_deals(
            symbol, count, start_time, end_time, extra_data, **kwargs
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    # ===== New market data methods =====

    # ===== New trade methods =====

    # ===== New account query methods =====

    # ====================  ====================

    def async_callback(self, future):
        """Callback function for async_get_tick, push tickerData to data_queue
        :param future: asyncio future object
        :return: None.
        """
        try:
            result = future.result()
            self.push_data_to_queue(result)
        except Exception as e:
            import traceback

            from bt_api_base.feeds.transport_safety import sanitize_text

            sensitive_values = (
                getattr(self, "public_key", None),
                getattr(self, "private_key", None),
            )
            message = sanitize_text(e, sensitive_values=sensitive_values)
            safe_traceback = sanitize_text(
                traceback.format_exc(), sensitive_values=sensitive_values
            )
            self.async_logger.warning(f"async_callback::{message}\n{safe_traceback}")

    # ===== Async methods for new market data endpoints =====

    # ===== Async methods for new trade endpoints =====

    # ===== Async methods for new account endpoints =====
