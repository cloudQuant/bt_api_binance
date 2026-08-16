"""Module-level docstring."""
from __future__ import annotations

import json
import time

from bt_api_base.containers.incomes.income import IncomeData
from bt_api_base.functions.utils import from_dict_get_float, from_dict_get_string


class BinanceIncomeData(IncomeData):
    """"""

    def __init__(self, income_info, exchange_name, symbol_name, asset_type, has_been_json_encoded):
        """__init__ method"""
        super().__init__(income_info, has_been_json_encoded)
        self.exchange_name = exchange_name
        self.symbol_name = symbol_name
        self.asset_type = asset_type
        self.local_update_time = time.time()
        self.income_data = income_info if has_been_json_encoded else None
        self.income_asset = None
        self.income_value = None
        self.income_type = None
        self.server_time = None
        self.all_data = None
        self.has_been_init_data = False

    def init_data(self):
        """init_data method"""
        if not self.has_been_json_encoded:
            self.income_data = json.loads(self.income_info)["data"][0]
            self.has_been_json_encoded = True
        if self.has_been_init_data:
            return self
        self.server_time = from_dict_get_float(self.income_data, "time")
        self.income_type = from_dict_get_string(self.income_data, "incomeType")
        self.income_value = from_dict_get_float(self.income_data, "income")
        self.income_asset = from_dict_get_string(self.income_data, "asset")
        self.has_been_init_data = True
        return self

    def get_all_data(self):
        """get_all_data method"""
        if self.all_data is None:
            self.all_data = {
                "server_time": self.server_time,
                "income_type": self.income_type,
                "income_value": self.income_value,
                "income_asset": self.income_asset,
                "exchange_name": self.exchange_name,
                "symbol_name": self.symbol_name,
                "asset_type": self.asset_type,
                "local_update_time": self.local_update_time,
            }
        return self.all_data

    def __str__(self):
        self.init_data()
        return json.dumps(self.get_all_data())

    def __repr__(self):
        return self.__str__()

    def get_exchange_name(self):
        """get_exchange_name method"""
        return self.exchange_name

    def get_server_time(self):
        """get_server_time method"""
        return self.server_time

    def get_local_update_time(self):
        """get_local_update_time method"""
        return self.local_update_time

    def get_symbol_name(self):
        """get_symbol_name method"""
        return self.symbol_name

    def get_income_type(self):
        """get_income_type method"""
        return self.income_type

    def get_income_value(self):
        """get_income_value method"""
        return self.income_value

    def get_income_asset(self):
        """get_income_asset method"""
        return self.income_asset
