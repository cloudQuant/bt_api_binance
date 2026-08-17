"""Binance WSS 账户数据容器。"""
from __future__ import annotations

import json
import time
from typing import Any

from bt_api_base.containers.accounts.account import AccountData
from bt_api_base.functions.utils import (
    from_dict_get_bool,
    from_dict_get_float,
    from_dict_get_string,
)

from bt_api_binance.containers.balances.binance_balance import (
    BinanceSpotRequestBalanceData,
    BinanceSpotWssBalanceData,
    BinanceSwapRequestBalanceData,
    BinanceSwapWssBalanceData,
)
from bt_api_binance.containers.positions.binance_position import (
    BinanceRequestPositionData,
    BinanceWssPositionData,
)


class BinanceSwapWssAccountData(AccountData):
    """BinanceWebSocket。

    WebSocketBinance。
    """

    def __init__(
        self,
        account_info: dict[str, Any] | str,
        symbol_name: str,
        asset_type: str,
        has_been_json_encoded: bool = False,
    ) -> None:
        """BinanceWebSocket。

        Args: account_info: ，JSON。
            symbol_name: 。
            asset_type: 。
            has_been_json_encoded: JSON。
        """
        super().__init__(account_info, has_been_json_encoded)
        self.exchange_name = "BINANCE"
        self.symbol_name = symbol_name
        self.local_update_time = time.time()
        self.asset_type = asset_type
        self.account_data = self.account_info if has_been_json_encoded else None
        self.positions: list[BinanceWssPositionData] | None = None
        self.balances: list[BinanceSwapWssBalanceData] | None = None
        self.server_time: float | None = None
        self.all_data: dict[str, Any] | None = None
        self.has_been_init_data = False

    def init_data(self) -> BinanceSwapWssAccountData:
        """。

        Returns: 。
        """
        if not self.has_been_json_encoded:
            raw = self.account_info
            self.account_data = json.loads(raw) if isinstance(raw, str) else raw
            self.has_been_json_encoded = True
        if self.has_been_init_data:
            return self
        data = self.account_data or {}
        self.server_time = from_dict_get_float(data, "E")
        acct = data.get("a", {}) if isinstance(data, dict) else {}
        self.balances = [
            BinanceSwapWssBalanceData(i, self.symbol_name, self.asset_type, True)
            for i in acct.get("B", [])
        ]
        self.positions = [
            BinanceWssPositionData(i, self.symbol_name, self.asset_type, True)
            for i in acct.get("P", [])
        ]
        self.has_been_init_data = True
        return self

    def get_all_data(self) -> dict[str, Any]:
        """。

        Returns: 。
        """
        if self.all_data is None:
            self.all_data = {
                "exchange_name": self.exchange_name,
                "symbol_name": self.symbol_name,
                "local_update_time": self.local_update_time,
                "asset_type": self.asset_type,
                "positions": self.positions,
                "balances": self.balances,
                "server_time": self.server_time,
            }
        return self.all_data

    def __str__(self) -> str:
        self.init_data()
        return str(self.get_all_data())

    def __repr__(self) -> str:
        return self.__str__()

    def get_exchange_name(self) -> str:
        """。

        Returns: 。
        """
        return self.exchange_name

    def get_symbol_name(self) -> str:
        """。

        Returns: 。
        """
        return self.symbol_name

    def get_asset_type(self) -> str:
        """。

        Returns: 。
        """
        return self.asset_type

    def get_server_time(self) -> float:
        """。

        Returns: 。
        """
        return self.server_time or 0.0

    def get_local_update_time(self) -> float:
        """。

        Returns: 。
        """
        return self.local_update_time

    def get_account_id(self) -> str:
        """ID。

        Returns: ID。
        """
        return None

    def get_account_type(self) -> str:
        """。

        Returns: 。
        """
        return None

    def get_can_deposit(self) -> bool:
        """。

        Returns: 。
        """
        return None

    def get_can_trade(self) -> bool:
        """。

        Returns: 。
        """
        return None

    def get_can_withdraw(self) -> bool:
        """。

        Returns: 。
        """
        return None

    def get_fee_tier(self) -> int | str:
        """。

        Returns: 。
        """
        return None

    def get_max_withdraw_amount(self) -> float:
        """。

        Returns: 。
        """
        return None

    def get_total_margin(self) -> float:
        """。

        Returns: 。
        """
        return None

    def get_total_used_margin(self) -> float:
        """。

        Returns: 。
        """
        return None

    def get_total_maintain_margin(self) -> float:
        """。

        Returns: 。
        """
        return None

    def get_total_available_margin(self) -> float:
        """。

        Returns: 。
        """
        return None

    def get_total_open_order_initial_margin(self) -> float:
        """。

        Returns: 。
        """
        return None

    def get_total_position_initial_margin(self) -> float:
        """。

        Returns: 。
        """
        return None

    def get_total_unrealized_profit(self) -> float:
        """。

        Returns: 。
        """
        return None

    def get_total_wallet_balance(self) -> float:
        """。

        Returns: 。
        """
        return None

    def get_balances(self) -> list[BinanceSwapWssBalanceData]:
        """。

        Returns: 。
        """
        if self.balances is None:
            return []
        return self.balances

    def get_positions(self) -> list[BinanceWssPositionData]:
        """。

        Returns: 。
        """
        if self.positions is None:
            return []
        return self.positions

    def get_spot_maker_commission_rate(self) -> float:
        """maker。

        Returns: maker。
        """
        return None

    def get_spot_taker_commission_rate(self) -> float:
        """taker。

        Returns: taker。
        """
        return None

    def get_future_maker_commission_rate(self) -> float:
        """maker。

        Returns: maker。
        """
        return None

    def get_future_taker_commission_rate(self) -> float:
        """taker。

        Returns: taker。
        """
        return None

    def get_option_maker_commission_rate(self) -> float:
        """maker。

        Returns: maker。
        """
        return None

    def get_option_taker_commission_rate(self) -> float:
        """taker。

        Returns: taker。
        """
        return None




class BinanceSpotWssAccountData(AccountData):
    """BinanceWebSocket。

    WebSocketBinance。
    """

    def __init__(
        self,
        account_info: dict[str, Any] | str,
        symbol_name: str,
        asset_type: str,
        has_been_json_encoded: bool = False,
    ) -> None:
        """BinanceWebSocket。

        Args: account_info: ，JSON。
            symbol_name: 。
            asset_type: 。
            has_been_json_encoded: JSON。
        """
        super().__init__(account_info, has_been_json_encoded)
        self.exchange_name = "BINANCE"
        self.symbol_name = symbol_name
        self.local_update_time = time.time()
        self.asset_type = asset_type
        self.account_data = self.account_info if has_been_json_encoded else None
        self.server_time: float | None = None
        self.balances: list[BinanceSpotWssBalanceData] | None = None
        self.all_data: dict[str, Any] | None = None
        self.has_been_init_data = False

    def init_data(self) -> BinanceSpotWssAccountData:
        """。

        Returns: 。
        """
        if not self.has_been_json_encoded:
            raw = self.account_info
            self.account_data = json.loads(raw) if isinstance(raw, str) else raw
            self.has_been_json_encoded = True
        if self.has_been_init_data:
            return self
        data = self.account_data or {}
        self.server_time = from_dict_get_float(data, "E")
        balances_raw = data.get("B", []) if isinstance(data, dict) else []
        self.balances = [
            BinanceSpotWssBalanceData(i, self.symbol_name, self.asset_type, True)
            for i in balances_raw
        ]
        self.has_been_init_data = True
        return self

    def get_all_data(self) -> dict[str, Any]:
        """。

        Returns: 。
        """
        if self.all_data is None:
            self.all_data = {
                "symbol": self.symbol_name,
                "exchange_name": self.exchange_name,
                "local_update_time": self.local_update_time,
                "server_time": self.server_time,
                "balances": self.balances,
            }
        return self.all_data

    def __str__(self) -> str:
        self.init_data()
        return str(self.get_all_data())

    def __repr__(self) -> str:
        return self.__str__()

    def get_exchange_name(self) -> str:
        """。

        Returns: 。
        """
        return self.exchange_name

    def get_symbol_name(self) -> str:
        """。

        Returns: 。
        """
        return self.symbol_name

    def get_asset_type(self) -> str:
        """。

        Returns: 。
        """
        return self.asset_type

    def get_server_time(self) -> float:
        """。

        Returns: 。
        """
        return self.server_time or 0.0

    def get_local_update_time(self) -> float:
        """。

        Returns: 。
        """
        return self.local_update_time

    def get_account_id(self) -> str:
        """ID。

        Returns: ID。
        """
        return ""

    def get_account_type(self) -> str:
        """。

        Returns: 。
        """
        return ""

    def get_can_deposit(self) -> bool:
        """。

        Returns: 。
        """
        return False

    def get_can_trade(self) -> bool:
        """。

        Returns: 。
        """
        return False

    def get_can_withdraw(self) -> bool:
        """。

        Returns: 。
        """
        return False

    def get_fee_tier(self) -> int | str:
        """。

        Returns: 。
        """
        return 0

    def get_max_withdraw_amount(self) -> float:
        """。

        Returns: 。
        """
        return 0.0

    def get_total_margin(self) -> float:
        """。

        Returns: 。
        """
        return 0.0

    def get_total_used_margin(self) -> float:
        """。

        Returns: 。
        """
        return 0.0

    def get_total_maintain_margin(self) -> float:
        """。

        Returns: 。
        """
        return 0.0

    def get_total_available_margin(self) -> float:
        """。

        Returns: 。
        """
        return 0.0

    def get_total_open_order_initial_margin(self) -> float:
        """。

        Returns: 。
        """
        return 0.0

    def get_total_position_initial_margin(self) -> float:
        """。

        Returns: 。
        """
        return 0.0

    def get_total_unrealized_profit(self) -> float:
        """。

        Returns: 。
        """
        return 0.0

    def get_total_wallet_balance(self) -> float:
        """。

        Returns: 。
        """
        return 0.0

    def get_balances(self) -> list[dict[str, Any]]:
        """。

        Returns: 。
        """
        if self.balances is None:
            return []
        return [b.get_all_data() for b in self.balances]

    def get_positions(self) -> list[dict[str, Any]]:
        """。

        Returns: 。
        """
        return []

    def get_spot_maker_commission_rate(self) -> float:
        """maker。

        Returns: maker。
        """
        return 0.0

    def get_spot_taker_commission_rate(self) -> float:
        """taker。

        Returns: taker。
        """
        return 0.0

    def get_future_maker_commission_rate(self) -> float:
        """maker。

        Returns: maker。
        """
        return 0.0

    def get_future_taker_commission_rate(self) -> float:
        """taker。

        Returns: taker。
        """
        return 0.0

    def get_option_maker_commission_rate(self) -> float:
        """maker。

        Returns: maker。
        """
        return 0.0

    def get_option_taker_commission_rate(self) -> float:
        """taker。

        Returns: taker。
        """
        return 0.0

