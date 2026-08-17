"""Binance 请求账户数据容器。"""
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


class BinanceSpotRequestAccountData(AccountData):
    """Binance。

    Binance、。
    """

    def __init__(
        self,
        account_info: dict[str, Any] | str,
        symbol_name: str,
        asset_type: str,
        has_been_json_encoded: bool = False,
    ) -> None:
        """Binance。

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
        self.balances: list[BinanceSpotRequestBalanceData] | None = None
        self.can_withdraw: bool | None = None
        self.can_trade: bool | None = None
        self.can_deposit: bool | None = None
        self.account_type: str | None = None
        self.server_time: float | None = None
        self.is_multi_assets_margin: bool | None = None
        self.all_data: dict[str, Any] | None = None
        self.has_been_init_data = False

    def init_data(self) -> BinanceSpotRequestAccountData:
        """。

        Returns: 。
        """
        if not self.has_been_json_encoded:
            raw = self.account_info
            self.account_data = (
                json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
            )
            self.has_been_json_encoded = True
        if self.has_been_init_data:
            return self
        raw = self.account_data
        data = raw if isinstance(raw, dict) else (json.loads(raw) if isinstance(raw, str) else {})
        self.server_time = from_dict_get_float(data, "updateTime")
        self.account_type = from_dict_get_string(data, "accountType")
        self.can_deposit = from_dict_get_bool(data, "canDeposit")
        self.can_trade = from_dict_get_bool(data, "canTrade")
        self.can_withdraw = from_dict_get_bool(data, "canWithdraw")
        self.balances = [
            BinanceSpotRequestBalanceData(i, i["asset"], self.asset_type, True)
            for i in data.get("balances", [])
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
                "balances": self.balances,
                "can_withdraw": self.can_withdraw,
                "can_trade": self.can_trade,
                "can_deposit": self.can_deposit,
                "account_type": self.account_type,
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

        Returns: ID（）。
        """
        return None

    def get_account_type(self) -> str:
        """。

        Returns: 。
        """
        return self.account_type

    def get_is_multi_assets_margin(self) -> bool | None:
        """。

        Returns: 。
        """
        return self.is_multi_assets_margin

    def get_can_deposit(self) -> bool:
        """。

        Returns: 。
        """
        return self.can_deposit if self.can_deposit is not None else False

    def get_can_trade(self) -> bool:
        """。

        Returns: 。
        """
        return self.can_trade if self.can_trade is not None else False

    def get_can_withdraw(self) -> bool:
        """。

        Returns: 。
        """
        return self.can_withdraw if self.can_withdraw is not None else False

    def get_fee_tier(self) -> int | str:
        """。

        Returns: （）。
        """
        return 0

    def get_max_withdraw_amount(self) -> float:
        """。

        Returns: （）。
        """
        return 0.0

    def get_total_margin(self) -> float:
        """。

        Returns: （）。
        """
        return 0.0

    def get_margin(self) -> int:
        """。

        Returns: （0）。
        """
        return 0

    def get_total_used_margin(self) -> float:
        """。

        Returns: （）。
        """
        return 0.0

    def get_total_maintain_margin(self) -> float:
        """。

        Returns: （）。
        """
        return 0.0

    def get_available_margin(self) -> int:
        """。

        Returns: （0）。
        """
        return 0

    def get_total_available_margin(self) -> float:
        """。

        Returns: （）。
        """
        return 0.0

    def get_total_open_order_initial_margin(self) -> float:
        """。

        Returns: （）。
        """
        return 0.0

    def get_total_position_initial_margin(self) -> float:
        """。

        Returns: （）。
        """
        return 0.0

    def get_total_unrealized_profit(self) -> float:
        """。

        Returns: （）。
        """
        return 0.0

    def get_unrealized_profit(self) -> int:
        """。

        Returns: （0）。
        """
        return 0

    def get_total_wallet_balance(self) -> float:
        """。

        Returns: （）。
        """
        return 0.0

    def get_balances(self) -> list[BinanceSpotRequestBalanceData]:
        """。

        Returns: 。
        """
        if self.balances is None:
            return []
        return self.balances

    def get_positions(self) -> list[dict[str, Any]]:
        """。

        Returns: （）。
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




class BinanceSwapRequestAccountData(AccountData):
    """Binance。

    Binance、、。
    """

    def __init__(
        self,
        account_info: dict[str, Any] | str,
        symbol_name: str,
        asset_type: str,
        has_been_json_encoded: bool = False,
    ) -> None:
        """Binance。

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
        self.balances: list[BinanceSwapRequestBalanceData] | None = None
        self.total_wallet_balance: float | None = None
        self.total_unrealized_profit: float | None = None
        self.total_open_order_initial_margin: float | None = None
        self.total_maintain_margin: float | None = None
        self.total_margin: float | None = None
        self.server_time: float | None = None
        self.positions: list[BinanceRequestPositionData] | None = None
        self.total_position_initial_margin: float | None = None
        self.total_available_margin: float | None = None
        self.max_withdraw_amount: float | None = None
        self.fee_tier: float | None = None
        self.can_withdraw: bool | None = None
        self.can_trade: bool | None = None
        self.can_deposit: bool | None = None
        self.is_multi_assets_margin: bool | None = None
        self.all_data: dict[str, Any] | None = None
        self.has_been_init_data = False

    def init_data(self) -> BinanceSwapRequestAccountData:
        """。

        Returns: 。
        """
        if not self.has_been_json_encoded:
            raw = self.account_info
            self.account_data = (
                json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
            )
            self.has_been_json_encoded = True
        if self.has_been_init_data:
            return self
        raw = self.account_data
        data = raw if isinstance(raw, dict) else (json.loads(raw) if isinstance(raw, str) else {})
        self.server_time = from_dict_get_float(data, "updateTime")
        self.is_multi_assets_margin = from_dict_get_bool(data, "multiAssetsMargin")
        self.can_deposit = from_dict_get_bool(data, "canDeposit")
        self.can_trade = from_dict_get_bool(data, "canTrade")
        self.can_withdraw = from_dict_get_bool(data, "canWithdraw")
        self.fee_tier = from_dict_get_float(data, "feeTier")
        self.max_withdraw_amount = from_dict_get_float(data, "maxWithdrawAmount")
        self.total_margin = from_dict_get_float(data, "totalMarginBalance")
        self.total_maintain_margin = from_dict_get_float(data, "totalMaintMargin")
        self.total_available_margin = from_dict_get_float(data, "availableBalance")
        self.total_open_order_initial_margin = from_dict_get_float(
            data, "totalOpenOrderInitialMargin"
        )
        self.total_position_initial_margin = from_dict_get_float(data, "totalPositionInitialMargin")
        self.total_unrealized_profit = from_dict_get_float(data, "totalCrossUnPnl")
        self.total_wallet_balance = from_dict_get_float(data, "totalWalletBalance")
        self.balances = [
            BinanceSwapRequestBalanceData(i, data, self.asset_type, True)
            for i in data.get("assets", [])
        ]
        self.positions = [
            BinanceRequestPositionData(i, self.symbol_name, self.asset_type, True)
            for i in data.get("positions", [])
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
                "balances": self.balances,
                "total_wallet_balance": self.total_wallet_balance,
                "total_unrealized_profit": self.total_unrealized_profit,
                "total_open_order_initial_margin": self.total_open_order_initial_margin,
                "total_maintain_margin": self.total_maintain_margin,
                "total_margin": self.total_margin,
                "server_time": self.server_time,
                "positions": self.positions,
                "total_position_initial_margin": self.total_position_initial_margin,
                "total_available_margin": self.total_available_margin,
                "max_withdraw_amount": self.max_withdraw_amount,
                "fee_tier": self.fee_tier,
                "can_withdraw": self.can_withdraw,
                "can_trade": self.can_trade,
                "can_deposit": self.can_deposit,
                "is_multi_assets_margin": self.is_multi_assets_margin,
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

    def get_is_multi_assets_margin(self) -> bool:
        """。

        Returns: 。
        """
        return self.is_multi_assets_margin if self.is_multi_assets_margin is not None else False

    def get_can_deposit(self) -> bool:
        """。

        Returns: 。
        """
        return self.can_deposit if self.can_deposit is not None else False

    def get_can_trade(self) -> bool:
        """。

        Returns: 。
        """
        return self.can_trade if self.can_trade is not None else False

    def get_can_withdraw(self) -> bool:
        """。

        Returns: 。
        """
        return self.can_withdraw if self.can_withdraw is not None else False

    def get_fee_tier(self) -> int | str:
        """。

        Returns: 。
        """
        return int(self.fee_tier) if self.fee_tier is not None else 0

    def get_max_withdraw_amount(self) -> float:
        """。

        Returns: 。
        """
        return self.max_withdraw_amount or 0.0

    def get_total_margin(self) -> float:
        """。

        Returns: 。
        """
        return self.total_margin or 0.0

    def get_total_used_margin(self) -> float:
        """。

        Returns: 。
        """
        return (self.get_total_margin() or 0.0) - (self.get_total_available_margin() or 0.0)

    def get_total_maintain_margin(self) -> float:
        """。

        Returns: 。
        """
        return self.total_maintain_margin or 0.0

    def get_total_available_margin(self) -> float:
        """。

        Returns: 。
        """
        return self.total_available_margin or 0.0

    def get_total_open_order_initial_margin(self) -> float:
        """。

        Returns: 。
        """
        return self.total_open_order_initial_margin or 0.0

    def get_total_position_initial_margin(self) -> float:
        """。

        Returns: 。
        """
        return self.total_position_initial_margin or 0.0

    def get_total_unrealized_profit(self) -> float:
        """。

        Returns: 。
        """
        return self.total_unrealized_profit or 0.0

    def get_total_wallet_balance(self) -> float:
        """。

        Returns: 。
        """
        return self.total_wallet_balance or 0.0

    def get_balances(self) -> list[BinanceSwapRequestBalanceData]:
        """。

        Returns: 。
        """
        if self.balances is None:
            return []
        return self.balances

    def get_positions(self) -> list[BinanceRequestPositionData]:
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


