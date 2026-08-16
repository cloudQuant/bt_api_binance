"""Module-level docstring."""
from __future__ import annotations

import json
import time

from bt_api_base.containers.balances.balance import BalanceData
from bt_api_base.functions.utils import from_dict_get_float, from_dict_get_string


class BinanceWssBalanceData:
    """Backward-compatible container for Binance account update payloads."""

    def __init__(self, balance_info, asset_type, has_been_json_encoded=False):
        """__init__ method"""
        self.balance_info = balance_info
        self.asset_type = asset_type
        self.has_been_json_encoded = has_been_json_encoded
        self.balance_data = balance_info if has_been_json_encoded else None
        self.accounts = []

    def init_balance_data(self):
        """init_balance_data method"""
        if not self.has_been_json_encoded:
            self.balance_data = json.loads(self.balance_info)
            self.has_been_json_encoded = True

        balances = (self.balance_data or {}).get("a", {}).get("B", [])
        self.accounts = [
            {
                "asset": from_dict_get_string(item, "a"),
                "free": from_dict_get_float(item, "f"),
                "locked": from_dict_get_float(item, "l"),
                "asset_type": self.asset_type,
            }
            for item in balances
        ]
        return self

    def init_data(self):
        """init_data method"""
        return self.init_balance_data()

    def get_data(self):
        """get_data method"""
        return self.accounts


class BinanceSpotRequestBalanceData(BalanceData):
    """Class BinanceSpotRequestBalanceData"""
    def __init__(self, balance_info, symbol_name, asset_type, has_been_json_encoded=False):
        """__init__ method"""
        super().__init__(balance_info, has_been_json_encoded)
        self.exchange_name = "BINANCE"
        self.account_type = "SPOT"
        self.symbol_name = symbol_name
        self.local_update_time = time.time()  # 
        self.asset_type = asset_type
        self.balance_data = balance_info if has_been_json_encoded else None
        self.available_margin = None
        self.used_margin = None
        self.position_initial_margin = None
        self.all_data = None
        self.has_been_init_data = False

    def init_data(self):
        """init_data method"""
        if not self.has_been_json_encoded:
            self.balance_data = json.loads(self.balance_info)
            self.has_been_json_encoded = True
        if self.has_been_init_data:
            return self
        data = self.balance_data or {}
        self.symbol_name = from_dict_get_string(data, "asset")
        self.used_margin = from_dict_get_float(data, "locked")
        self.available_margin = from_dict_get_float(data, "free")
        self.has_been_init_data = True
        return self

    def get_all_data(self):
        """get_all_data method"""
        if self.all_data is None:
            self.all_data = {
                "exchange_name": self.exchange_name,
                "account_type": self.account_type,
                "symbol_name": self.symbol_name,
                "local_update_time": self.local_update_time,
                "available_margin": self.available_margin,
                "used_margin": self.used_margin,
            }
        return self.all_data

    def __str__(self):
        self.init_data()
        return json.dumps(self.get_all_data())

    def __repr__(self):
        return self.__str__()

    def get_exchange_name(self):
        """# """
        return self.exchange_name

    def get_symbol_name(self):
        """# """
        return self.symbol_name

    def get_asset_type(self):
        """# """
        return self.asset_type

    def get_server_time(self):
        """# """
        return

    def get_local_update_time(self):
        """# """
        return self.local_update_time

    def get_account_id(self):
        """# id"""
        return

    def get_account_type(self):
        """# """
        return self.account_type

    def get_fee_tier(self):
        """# """
        return

    def get_max_withdraw_amount(self):
        """# """
        return

    def get_margin(self):
        """# """
        return self.get_used_margin() + self.get_available_margin()

    def get_used_margin(self):
        """# """
        return self.used_margin

    def get_maintain_margin(self):
        """# """
        return

    def get_available_margin(self):
        """# """
        return self.available_margin

    def get_open_order_initial_margin(self):
        """# """
        return

    def get_position_initial_margin(self):
        """# """
        return self.position_initial_margin
        # return None

    def get_unrealized_profit(self):
        """# """
        return

    def get_interest(self):
        """# """
        return


class BinanceSwapRequestBalanceData(BalanceData):
    """Class BinanceSwapRequestBalanceData"""
    def __init__(self, balance_info, symbol_name, asset_type, has_been_json_encoded=False):
        """__init__ method"""
        super().__init__(balance_info, has_been_json_encoded)
        self.exchange_name = "BINANCE"
        self.symbol_name = symbol_name
        self.local_update_time = time.time()  # 
        self.asset_type = asset_type
        self.balance_data = balance_info if has_been_json_encoded else None
        self.unrealized_profit = None
        self.position_initial_margin = None
        self.open_order_initial_margin = None
        self.available_margin = None
        self.maintain_margin = None
        self.margin = None
        self.max_withdraw_amount = None
        self.account_type = None
        self.account_id = None
        self.server_time = None
        self.all_data = None
        self.has_been_init_data = False

    def init_data(self):
        """init_data method"""
        if not self.has_been_json_encoded:
            self.balance_data = json.loads(self.balance_info)
            self.has_been_json_encoded = True
        if self.has_been_init_data:
            return self
        data = self.balance_data or {}
        self.server_time = from_dict_get_float(data, "updateTime")
        self.account_id = from_dict_get_string(data, "accountAlias")
        self.account_type = from_dict_get_string(data, "asset")
        self.max_withdraw_amount = from_dict_get_float(data, "maxWithdrawAmount")
        self.margin = (
            from_dict_get_float(data, "marginBalance")
            if "marginBalance" in data
            else from_dict_get_float(data, "balance")
        )
        self.maintain_margin = from_dict_get_float(data, "maintMargin")
        self.available_margin = from_dict_get_float(data, "availableBalance")
        self.open_order_initial_margin = from_dict_get_float(data, "openOrderInitialMargin")
        self.position_initial_margin = from_dict_get_float(data, "positionInitialMargin")
        self.unrealized_profit = from_dict_get_float(data, "crossUnPnl")
        self.has_been_init_data = True
        return self

    def get_all_data(self):
        """get_all_data method"""
        if self.all_data is None:
            self.all_data = {
                "exchange_name": self.exchange_name,
                "symbol_name": self.symbol_name,
                "local_update_time": self.local_update_time,
                "server_time": self.server_time,
                "asset_type": self.asset_type,
                "account_type": self.account_type,
                "account_id": self.account_id,
                "max_withdraw_amount": self.max_withdraw_amount,
                "margin": self.margin,
                "maintain_margin": self.maintain_margin,
                "available_margin": self.available_margin,
                "position_initial_margin": self.position_initial_margin,
                "open_order_initial_margin": self.open_order_initial_margin,
                "unrealized_profit": self.unrealized_profit,
            }
        return self.all_data

    def __str__(self):
        self.init_data()
        self.all_data = self.get_all_data()
        return str(self.all_data)

    def __repr__(self):
        return self.__str__()

    def get_exchange_name(self):
        """# """
        return self.exchange_name

    def get_symbol_name(self):
        """# """
        return self.symbol_name

    def get_asset_type(self):
        """# """
        return self.asset_type

    def get_server_time(self):
        """# """
        return self.server_time

    def get_local_update_time(self):
        """# """
        return self.local_update_time

    def get_account_id(self):
        """# id"""
        return self.account_id

    def get_account_type(self):
        """# """
        return self.account_type

    def get_fee_tier(self):
        """# """
        return

    def get_max_withdraw_amount(self):
        """# """
        return self.max_withdraw_amount

    def get_margin(self):
        """# """
        return self.margin

    def get_used_margin(self):
        """# """
        return self.get_margin() - self.get_available_margin()

    def get_maintain_margin(self):
        """# """
        return self.maintain_margin

    def get_available_margin(self):
        """# """
        return self.available_margin

    def get_open_order_initial_margin(self):
        """# """
        return self.open_order_initial_margin

    def get_position_initial_margin(self):
        """# """
        return self.position_initial_margin

    def get_unrealized_profit(self):
        """# """
        return self.unrealized_profit

    def get_interest(self):
        """# """
        return


class BinanceSwapWssBalanceData(BalanceData):
    """Class BinanceSwapWssBalanceData"""
    def __init__(self, balance_info, symbol_name, asset_type, has_been_json_encoded=False):
        """__init__ method"""
        super().__init__(balance_info, has_been_json_encoded)
        self.exchange_name = "BINANCE"
        self.symbol_name = symbol_name
        self.local_update_time = time.time()  # 
        self.asset_type = asset_type
        self.balance_data = balance_info if has_been_json_encoded else None
        self.margin = None
        self.account_type = None
        self.position_initial_margin = None
        self.all_data = None
        self.has_been_init_data = False

    def init_data(self):
        """init_data method"""
        if not self.has_been_json_encoded:
            self.balance_data = json.loads(self.balance_info)
            self.has_been_json_encoded = True
        if self.has_been_init_data:
            return self
        data = self.balance_data or {}
        self.account_type = from_dict_get_string(data, "a")
        self.margin = from_dict_get_float(data, "wb")
        self.has_been_init_data = True
        return self

    def get_all_data(self):
        """get_all_data method"""
        if self.all_data is None:
            self.all_data = {
                "exchange_name": self.exchange_name,
                "symbol_name": self.symbol_name,
                "asset_type": self.asset_type,
                "local_update_time": self.local_update_time,
                "account_type": self.account_type,
                "margin": self.margin,
            }
        return self.all_data

    def __str__(self):
        self.init_data()
        return json.dumps(self.get_all_data())

    def __repr__(self):
        return self.__str__()

    def get_exchange_name(self):
        """# """
        return self.exchange_name

    def get_symbol_name(self):
        """# """
        return self.symbol_name

    def get_asset_type(self):
        """# """
        return self.asset_type

    def get_server_time(self):
        """# """
        return

    def get_local_update_time(self):
        """# """
        return self.local_update_time

    def get_account_id(self):
        """# id"""
        return

    def get_account_type(self):
        """# """
        return self.account_type

    def get_fee_tier(self):
        """# """
        return

    def get_max_withdraw_amount(self):
        """# """
        return

    def get_margin(self):
        """# """
        return self.margin

    def get_used_margin(self):
        """# """
        return

    def get_maintain_margin(self):
        """# """
        return

    def get_available_margin(self):
        """# """
        return

    def get_open_order_initial_margin(self):
        """# """
        return

    def get_position_initial_margin(self):
        """# """
        return self.position_initial_margin
        # return None

    def get_unrealized_profit(self):
        """# """
        return

    def get_interest(self):
        """# """
        return


class BinanceSpotWssBalanceData(BalanceData):
    """Class BinanceSpotWssBalanceData"""
    def __init__(self, balance_info, symbol_name, asset_type, has_been_json_encoded=False):
        """__init__ method"""
        super().__init__(balance_info, has_been_json_encoded)
        self.exchange_name = "BINANCE"
        self.symbol_name = symbol_name
        self.local_update_time = time.time()  # 
        self.asset_type = asset_type
        self.balance_data = balance_info if has_been_json_encoded else None
        self.available_margin = None
        self.used_margin = None
        self.server_time = None
        self.position_initial_margin = None
        self.all_data = None
        self.has_been_init_data = False

    def init_data(self):
        """init_data method"""
        if not self.has_been_json_encoded:
            self.balance_data = json.loads(self.balance_info)
            self.has_been_json_encoded = True
        if self.has_been_init_data:
            return self
        data = self.balance_data or {}
        self.server_time = from_dict_get_float(data, "E")
        self.used_margin = from_dict_get_float(data, "l")
        self.available_margin = from_dict_get_float(data, "f")
        self.has_been_init_data = True
        return self

    def get_all_data(self):
        """get_all_data method"""
        if self.all_data is None:
            self.all_data = {
                "exchange_name": self.exchange_name,
                "symbol_name": self.symbol_name,
                "local_update_time": self.local_update_time,
                "server_time": self.server_time,
                "used_margin": self.used_margin,
                "available_margin": self.available_margin,
            }
        return self.all_data

    def __str__(self):
        self.init_data()
        return json.dumps(self.get_all_data())

    def __repr__(self):
        return self.__str__()

    def get_exchange_name(self):
        """# """
        return self.exchange_name

    def get_symbol_name(self):
        """# """
        return self.symbol_name

    def get_asset_type(self):
        """# """
        return self.asset_type

    def get_server_time(self):
        """# """
        return self.server_time

    def get_local_update_time(self):
        """# """
        return self.local_update_time

    def get_account_id(self):
        """# id"""
        return

    def get_account_type(self):
        """# """
        return

    def get_fee_tier(self):
        """# """
        return

    def get_max_withdraw_amount(self):
        """# """
        return

    def get_margin(self):
        """# """
        return self.get_used_margin() + self.get_available_margin()

    def get_used_margin(self):
        """# """
        return self.used_margin

    def get_maintain_margin(self):
        """# """
        return

    def get_available_margin(self):
        """# """
        return self.available_margin

    def get_open_order_initial_margin(self):
        """# """
        return

    def get_position_initial_margin(self):
        """# """
        return self.position_initial_margin

    def get_unrealized_profit(self):
        """# """
        return

    def get_interest(self):
        """# """
        return
