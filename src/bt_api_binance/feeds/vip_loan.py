"""Binance VIP Loan API - VIP.

 Binance VIP REST API ，：
- VIP
- VIP
- VIP
- VIP
- VIP
"""

from __future__ import annotations

from typing import Any

from bt_api_base.functions.utils import update_extra_data
from bt_api_base.logging_factory import get_logger

from bt_api_binance.exchange_data import BinanceExchangeDataVipLoan

from .request_base import BinanceRequestData


class BinanceRequestDataVipLoan(BinanceRequestData):
    """Binance VIP Loan API .

    VIP。
    """

    def __init__(self, data_queue: Any = None, **kwargs: Any) -> None:
        """__init__ method"""
        kwargs.setdefault("exchange_data", BinanceExchangeDataVipLoan())
        kwargs.setdefault("exchange_name", "binance_vip_loan")
        super().__init__(data_queue, **kwargs)
        self.asset_type = kwargs.get("asset_type", "VIP_LOAN")
        self.logger_name = kwargs.get("logger_name", "binance_vip_loan_feed.log")
        self._params = kwargs["exchange_data"]
        self.request_logger = get_logger("binance_vip_loan_feed")
        self.async_logger = get_logger("binance_vip_loan_feed")

    # ==================== VIP Loan  ====================

    def _get_vip_loan_ongoing_orders(
        self,
        loan_coin=None,
        collateral_coin=None,
        current=None,
        size=None,
        extra_data=None,
        **kwargs,
    ):
        """VIP.

        Args: loan_coin:
            collateral_coin: 
            current: 
            size: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_vip_loan_ongoing_orders"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if loan_coin is not None:
            params["loanCoin"] = loan_coin
        if collateral_coin is not None:
            params["collateralCoin"] = collateral_coin
        if current is not None:
            params["current"] = current
        if size is not None:
            params["size"] = size
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": loan_coin or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_vip_loan_ongoing_orders(
        self,
        loan_coin=None,
        collateral_coin=None,
        current=None,
        size=None,
        extra_data=None,
        **kwargs,
    ):
        """VIP.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_vip_loan_ongoing_orders(
            loan_coin=loan_coin,
            collateral_coin=collateral_coin,
            current=current,
            size=size,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _vip_loan_borrow(
        self, loan_coin, collateral_coin, loan_amount, collateral_amount, extra_data=None, **kwargs
    ):
        """VIP.

        Args: loan_coin:
            collateral_coin: 
            loan_amount: 
            collateral_amount: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "vip_loan_borrow"
        path = self._params.get_rest_path(request_type)
        params = {
            "loanCoin": loan_coin,
            "collateralCoin": collateral_coin,
            "loanAmount": loan_amount,
            "collateralAmount": collateral_amount,
        }
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": loan_coin,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def vip_loan_borrow(
        self, loan_coin, collateral_coin, loan_amount, collateral_amount, extra_data=None, **kwargs
    ):
        """VIP.

        Returns: RequestData:

        """
        path, params, extra_data = self._vip_loan_borrow(
            loan_coin=loan_coin,
            collateral_coin=collateral_coin,
            loan_amount=loan_amount,
            collateral_amount=collateral_amount,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _vip_loan_repay(
        self,
        loan_coin,
        collateral_coin,
        repay_amount=None,
        collateral_amount=None,
        extra_data=None,
        **kwargs,
    ):
        """VIP.

        Args: loan_coin:
            collateral_coin: 
            repay_amount: 
            collateral_amount:  ()
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "vip_loan_repay"
        path = self._params.get_rest_path(request_type)
        params = {
            "loanCoin": loan_coin,
            "collateralCoin": collateral_coin,
        }
        if repay_amount is not None:
            params["repayAmount"] = repay_amount
        if collateral_amount is not None:
            params["collateralAmount"] = collateral_amount
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": loan_coin,
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def vip_loan_repay(
        self,
        loan_coin,
        collateral_coin,
        repay_amount=None,
        collateral_amount=None,
        extra_data=None,
        **kwargs,
    ):
        """VIP.

        Returns: RequestData:

        """
        path, params, extra_data = self._vip_loan_repay(
            loan_coin=loan_coin,
            collateral_coin=collateral_coin,
            repay_amount=repay_amount,
            collateral_amount=collateral_amount,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_vip_loan_history(
        self,
        loan_coin=None,
        collateral_coin=None,
        start_time=None,
        end_time=None,
        current=None,
        size=None,
        extra_data=None,
        **kwargs,
    ):
        """VIP.

        Args: loan_coin:
            collateral_coin: 
            start_time: 
            end_time: 
            current: 
            size: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_vip_loan_history"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if loan_coin is not None:
            params["loanCoin"] = loan_coin
        if collateral_coin is not None:
            params["collateralCoin"] = collateral_coin
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if current is not None:
            params["current"] = current
        if size is not None:
            params["size"] = size
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": loan_coin or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_vip_loan_history(
        self,
        loan_coin=None,
        collateral_coin=None,
        start_time=None,
        end_time=None,
        current=None,
        size=None,
        extra_data=None,
        **kwargs,
    ):
        """VIP.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_vip_loan_history(
            loan_coin=loan_coin,
            collateral_coin=collateral_coin,
            start_time=start_time,
            end_time=end_time,
            current=current,
            size=size,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data

    def _get_vip_repayment_history(
        self,
        loan_coin=None,
        collateral_coin=None,
        start_time=None,
        end_time=None,
        current=None,
        size=None,
        extra_data=None,
        **kwargs,
    ):
        """VIP.

        Args: loan_coin:
            collateral_coin: 
            start_time: 
            end_time: 
            current: 
            size: 
            extra_data: 
            **kwargs: 

        Returns: tuple: (path, params, extra_data)

        """
        request_type = "get_vip_repayment_history"
        path = self._params.get_rest_path(request_type)
        params: dict[str, Any] = {}
        if loan_coin is not None:
            params["loanCoin"] = loan_coin
        if collateral_coin is not None:
            params["collateralCoin"] = collateral_coin
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if current is not None:
            params["current"] = current
        if size is not None:
            params["size"] = size
        extra_data = update_extra_data(
            extra_data,
            **{
                "request_type": request_type,
                "symbol_name": loan_coin or "ALL",
                "asset_type": self.asset_type,
                "exchange_name": self.exchange_name,
                "normalize_function": None,
            },
        )
        return path, params, extra_data

    def get_vip_repayment_history(
        self,
        loan_coin=None,
        collateral_coin=None,
        start_time=None,
        end_time=None,
        current=None,
        size=None,
        extra_data=None,
        **kwargs,
    ):
        """VIP.

        Returns: RequestData:

        """
        path, params, extra_data = self._get_vip_repayment_history(
            loan_coin=loan_coin,
            collateral_coin=collateral_coin,
            start_time=start_time,
            end_time=end_time,
            current=current,
            size=size,
            extra_data=extra_data,
            **kwargs,
        )
        data = self.request(path, params=params, extra_data=extra_data, is_sign=True)
        return data
