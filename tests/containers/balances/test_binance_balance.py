"""Module-level docstring."""
from __future__ import annotations

from bt_api_binance.containers.balances import (
    BinanceSpotRequestBalanceData,
    BinanceSpotWssBalanceData,
    BinanceSwapRequestBalanceData,
    BinanceSwapWssBalanceData,
)


def test_binance_spot_wss_balance_data():
    """test_binance_spot_wss_balance_data function"""
    data = {"a": "USDT", "f": "29.24200000", "l": "6.75800000"}
    spot_wss_data = BinanceSpotWssBalanceData(data, "USDT", "SPOT", True)
    spot_wss_data.init_data()
    assert spot_wss_data.get_margin() == 29.24200000 + 6.75800000
    assert spot_wss_data.get_used_margin() == 6.75800000
    assert spot_wss_data.get_available_margin() == 29.24200000


def test_binance_spot_request_balance():
    """test_binance_spot_request_balance function"""
    data = {"asset": "BTC", "free": "0.00000000", "locked": "0.00000000"}
    bal = BinanceSpotRequestBalanceData(data, "BTC", "SPOT", True)
    bal.init_data()
    assert bal is not None
    assert isinstance(bal, BinanceSpotRequestBalanceData)
    assert bal.get_symbol_name() == "BTC"


def test_binance_request_account_balance():
    """test_binance_request_account_balance function"""
    data = {
        "asset": "USDT",  # 
        "walletBalance": "23.72469206",  # 
        "unrealizedProfit": "0.00000000",  # 
        "marginBalance": "23.72469206",  # 
        "maintMargin": "0.00000000",  # 
        "initialMargin": "0.00000000",  # 
        "positionInitialMargin": "0.00000000",  # ()
        "openOrderInitialMargin": "0.00000000",  # ()
        "crossWalletBalance": "23.72469206",  # 
        "crossUnPnl": "0.00000000",  # 
        "availableBalance": "126.72469206",  # 
        "maxWithdrawAmount": "23.72469206",  # 
        "marginAvailable": "true",  # 
        "updateTime": 1625474304765,  # 
    }
    symbol = data["asset"]
    asset_type = data["asset"]
    data = BinanceSwapRequestBalanceData(data, symbol, asset_type, True)
    data.init_data()
    assert data.get_position_initial_margin() == 0.0
    assert data.get_unrealized_profit() == 0.0


def test_binance_request_balance():
    """test_binance_request_balance function"""
    data = {
        "accountAlias": "SgsR",  # 
        "asset": "USDT",  # 
        "balance": "122607.35137903",  # 
        "crossWalletBalance": "23.72469206",  # 
        "crossUnPnl": "0.00000000",  # 
        "availableBalance": "23.72469206",  # 
        "maxWithdrawAmount": "23.72469206",  # 
        "marginAvailable": "true",  # 
        "updateTime": 1617939110373,
    }

    bo = BinanceSwapRequestBalanceData(data, "USDT", "SWAP", True)
    bo.init_data()
    assert isinstance(bo, BinanceSwapRequestBalanceData)
    assert bo.get_account_id() == data["accountAlias"]
    assert bo.get_server_time() == float(data["updateTime"])
    assert bo.get_max_withdraw_amount() == float(data["maxWithdrawAmount"])
    assert bo.get_margin() == float(data["balance"])
    assert bo.get_available_margin() == float(data["availableBalance"])
    assert bo.get_unrealized_profit() == float(data["crossUnPnl"])


def test_binance_wss_balance():
    """test_binance_wss_balance function"""
    data = {
        "a": "USDT",  # 
        "wb": "122624.12345678",  # 
        "cw": "100.12345678",  # 
        "bc": "50.12345678",  # 
    }

    bo = BinanceSwapWssBalanceData(data, "USDT", "SWAP", True)
    bo.init_data()
    assert bo.get_margin() == float(data["wb"])
    assert bo.get_account_type() == data["a"]


if __name__ == "__main__":
    test_binance_request_balance()
    test_binance_wss_balance()
