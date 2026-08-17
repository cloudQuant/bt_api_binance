"""Binance 响应归一化函数集合（@staticmethod mixin）。

从 request_base.py 拆分，供 BinanceRequestData 混入；各 normalize 函数
将原始交易所响应转换为 bt_api_binance 容器类型。
"""

from __future__ import annotations

from typing import Any

from bt_api_binance.containers.accounts.binance_account import (
    BinanceSpotRequestAccountData,
    BinanceSwapRequestAccountData,
)
from bt_api_binance.containers.balances.binance_balance import (
    BinanceSwapRequestBalanceData,
)  # , BinanceSpotRequestBalanceData
from bt_api_binance.containers.bars.binance_bar import BinanceRequestBarData
from bt_api_binance.containers.fundingrates.binance_funding_rate import (
    BinanceRequestFundingRateData,
    BinanceRequestHistoryFundingRateData,
)
from bt_api_binance.containers.markprices.binance_mark_price import (
    BinanceRequestMarkPriceData,
)
from bt_api_binance.containers.orderbooks.binance_orderbook import (
    BinanceRequestOrderBookData,
)
from bt_api_binance.containers.orders.binance_order import (
    BinanceRequestOrderData,
)
from bt_api_binance.containers.positions.binance_position import (
    BinanceRequestPositionData,
)
from bt_api_binance.containers.tickers.binance_ticker import (
    BinanceRequestTickerData,
)
from bt_api_binance.containers.trades.binance_trade import (
    BinanceRequestTradeData,
)


class NormalizeMixin:
    """响应归一化静态方法集合。"""

    @staticmethod
    def _get_account_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if len(input_data) > 0:
            if asset_type == "SPOT":
                data_list = [
                    BinanceSpotRequestAccountData(input_data, symbol_name, asset_type, True)
                ]
            else:
                    data_list = [
                    BinanceSwapRequestAccountData(input_data, symbol_name, asset_type, True)
                ]
            data = data_list
        else:
            data = []
        return data, status

    @staticmethod
    def _get_balance_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list) and asset_type == "SWAP":
            data = [
                BinanceSwapRequestBalanceData(i, symbol_name, asset_type, True) for i in input_data
            ]
        elif isinstance(input_data, dict) and asset_type == "SWAP":
            data = [BinanceSwapRequestBalanceData(input_data, symbol_name, asset_type, True)]
        elif isinstance(input_data, list) and asset_type == "SPOT":
            data: list[Any] = [
                BinanceSpotRequestAccountData(i, symbol_name, asset_type, True) for i in input_data
            ]
        elif isinstance(input_data, dict) and asset_type == "SPOT":
            data = [BinanceSpotRequestAccountData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _get_position_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list) and isinstance(input_data[0], dict):
            data = [
                BinanceRequestPositionData(i, symbol_name, asset_type, True) for i in input_data
            ]
        else:
            data = []
        return data, status

    @staticmethod
    def _get_tick_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list):
            data = [BinanceRequestTickerData(i, symbol_name, asset_type, True) for i in input_data]
        elif isinstance(input_data, dict):
            data = [BinanceRequestTickerData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _get_depth_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list):
            data = [
                BinanceRequestOrderBookData(i, symbol_name, asset_type, True) for i in input_data
            ]
        elif isinstance(input_data, dict):
            data = [BinanceRequestOrderBookData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _get_kline_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list):
            data = [BinanceRequestBarData(i, symbol_name, asset_type, True) for i in input_data]
        elif isinstance(input_data, dict):
            data = [BinanceRequestBarData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _get_funding_rate_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        # print('input_data', input_data)
        if isinstance(input_data, list):
            data = [
                BinanceRequestFundingRateData(i, symbol_name, asset_type, True) for i in input_data
            ]
        elif isinstance(input_data, dict):
            data = [BinanceRequestFundingRateData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _get_history_funding_rate_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        # print('input_data', input_data)
        if isinstance(input_data, list):
            data = [
                BinanceRequestHistoryFundingRateData(i, symbol_name, asset_type, True)
                for i in input_data
            ]
        elif isinstance(input_data, dict):
            data = [BinanceRequestHistoryFundingRateData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _get_mark_price_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list):
            data = [
                BinanceRequestMarkPriceData(i, symbol_name, asset_type, True) for i in input_data
            ]
        elif isinstance(input_data, dict):
            data = [BinanceRequestMarkPriceData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _make_order_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list):
            data = [BinanceRequestOrderData(i, symbol_name, asset_type, True) for i in input_data]
        elif isinstance(input_data, dict):
            data = [BinanceRequestOrderData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _cancel_order_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list):
            data = [BinanceRequestOrderData(i, symbol_name, asset_type, True) for i in input_data]
        elif isinstance(input_data, dict):
            data = [BinanceRequestOrderData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _query_order_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list):
            data = [BinanceRequestOrderData(i, symbol_name, asset_type, True) for i in input_data]
        elif isinstance(input_data, dict):
            data = [BinanceRequestOrderData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _get_open_orders_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list):
            data = [BinanceRequestOrderData(i, symbol_name, asset_type, True) for i in input_data]
        elif isinstance(input_data, dict):
            data = [BinanceRequestOrderData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    @staticmethod
    def _get_deals_normalize_function(input_data, extra_data):
        status = input_data is not None
        symbol_name = extra_data["symbol_name"]
        asset_type = extra_data["asset_type"]
        if isinstance(input_data, list):
            data = [BinanceRequestTradeData(i, symbol_name, asset_type, True) for i in input_data]
        elif isinstance(input_data, dict):
            data = [BinanceRequestTradeData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status
