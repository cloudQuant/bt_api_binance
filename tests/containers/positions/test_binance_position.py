"""Module-level docstring."""
from __future__ import annotations

from bt_api_binance.containers.positions.binance_position import (
    BinanceRequestPositionData,
    BinanceWssPositionData,
)


def test_binance_position():
    """test_binance_position function"""
    data = {
        "s": "BTCUSDT",  # 
        "pa": "0",  # 
        "ep": "0.00000",  # 
        "bep": "0",  # 
        "cr": "200",  # ()
        "up": "0",  # 
        "mt": "isolated",  # 
        "iw": "0.00000000",  # ，
        "ps": "BOTH",  # 
    }
    bo = BinanceWssPositionData(data, "BTC-USDT", "PERPETUAL", True)
    bo.init_data()
    assert bo.get_server_time() is None
    assert bo.get_exchange_name() == "BINANCE"
    assert bo.get_asset_type() == "PERPETUAL"
    assert bo.get_server_time() is None
    assert bo.get_position_id() is None
    assert bo.get_account_id() is None
    assert bo.get_is_isolated() is True
    assert bo.get_margin_type() == "isolated"
    assert bo.get_is_auto_add_margin() is None
    assert bo.get_leverage() is None
    assert bo.get_max_notional_value() is None
    assert bo.get_position_symbol_name() == "BTCUSDT"
    assert bo.get_position_volume() == 0.0
    assert bo.get_position_side() == "BOTH"
    assert bo.get_trade_num() is None
    assert bo.get_avg_price() == 0.0
    assert bo.get_mark_price() is None
    assert bo.get_liquidation_price() is None
    assert bo.get_initial_margin() is None
    assert bo.get_maintenance_margin() is None
    assert bo.open_order_initial_margin() is None
    assert bo.get_position_initial_margin() is None
    assert bo.get_position_commission() is None
    assert bo.get_position_realized_pnl() == 200.0
    assert bo.get_position_unrealized_pnl() == 0.0
    assert bo.get_position_funding_value() is None


def test_binance_req_position():
    """test_binance_req_position function"""
    data = {
        "entryPrice": "0.00000",  # 
        "breakEvenPrice": "0.0",  # 
        "marginType": "isolated",  # 
        "isAutoAddMargin": "false",
        "isolatedMargin": "0.00000000",  # 
        "leverage": "10",  # 
        "liquidationPrice": "0",  # 
        "markPrice": "6679.50671178",  # 
        "maxNotionalValue": "20000000",  # 
        "positionAmt": "0.000",  # ，, ，
        "notional": "0",
        "isolatedWallet": "0",
        "symbol": "BTCUSDT",  # 
        "unRealizedProfit": "0.00000000",  # 
        "positionSide": "BOTH",  # 
        "updateTime": 1625474304765,  # 
    }
    bo = BinanceRequestPositionData(data, "BTC-USDT", "PERPETUAL", True)
    bo.init_data()
    assert bo.get_server_time() == 1625474304765.0
    assert bo.get_exchange_name() == "BINANCE"
    assert bo.get_asset_type() == "PERPETUAL"
    assert bo.get_position_id() is None
    assert bo.get_account_id() is None
    assert bo.get_is_isolated() is True
    assert bo.get_margin_type() == "isolated"
    assert bo.get_is_auto_add_margin() is False
    assert bo.get_leverage() == 10.0
    assert bo.get_max_notional_value() == 20000000.0
    assert bo.get_position_symbol_name() == "BTCUSDT"
    assert bo.get_symbol_name() == "BTC-USDT"
    assert bo.get_position_volume() == 0.0
    assert bo.get_position_side() == "BOTH"
    assert bo.get_trade_num() is None
    assert bo.get_avg_price() == 0.0
    assert bo.get_mark_price() == 6679.50671178
    assert bo.get_liquidation_price() is None
    assert bo.get_initial_margin() is None
    assert bo.get_maintenance_margin() is None
    assert bo.open_order_initial_margin() is None
    assert bo.get_position_initial_margin() is None
    assert bo.get_position_commission() is None
    assert bo.get_position_realized_pnl() is None
    assert bo.get_position_unrealized_pnl() == 0.0
    assert bo.get_position_funding_value() is None


if __name__ == "__main__":
    test_binance_position()
    test_binance_req_position()
