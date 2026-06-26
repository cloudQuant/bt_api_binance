from __future__ import annotations

from bt_api_binance.containers.positions.binance_position import (
    BinanceRequestPositionData,
    BinanceWssPositionData,
)


def test_binance_position():
    data = {
        "s": "BTCUSDT",  # 交易对
        "pa": "0",  # 仓位
        "ep": "0.00000",  # 入仓价格
        "bep": "0",  # 盈亏平衡价
        "cr": "200",  # (费前)累计实现损益
        "up": "0",  # 持仓未实现盈亏
        "mt": "isolated",  # 保证金模式
        "iw": "12.5",  # 若为逐仓，仓位保证金
        "ps": "BOTH",  # 持仓方向
        "notional": "250",
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
    assert bo.get_initial_margin() == 12.5
    assert bo.get_maintenance_margin() is None
    assert bo.open_order_initial_margin() is None
    assert bo.get_position_initial_margin() == 12.5
    assert bo.get_position_commission() is None
    assert bo.get_position_realized_pnl() == 200.0
    assert bo.get_position_unrealized_pnl() == 0.0
    assert bo.get_position_funding_value() is None
    assert bo.get_all_data()["notional"] == 250.0
    assert bo.get_all_data()["market_value"] == 250.0


def test_binance_req_position():
    data = {
        "entryPrice": "0.00000",  # 开仓均价
        "breakEvenPrice": "0.0",  # 盈亏平衡价
        "marginType": "isolated",  # 逐仓模式或全仓模式
        "isAutoAddMargin": "false",
        "isolatedMargin": "12.5",  # 逐仓保证金
        "leverage": "10",  # 当前杠杆倍数
        "liquidationPrice": "55000",  # 参考强平价格
        "markPrice": "6679.50671178",  # 当前标记价格
        "maxNotionalValue": "20000000",  # 当前杠杆倍数允许的名义价值上限
        "positionAmt": "0.100",  # 头寸数量，符号代表多空方向, 正数为多，负数为空
        "notional": "667.950671178",
        "isolatedWallet": "13",
        "symbol": "BTCUSDT",  # 交易对
        "unRealizedProfit": "8.50000000",  # 持仓未实现盈亏
        "positionSide": "BOTH",  # 持仓方向
        "updateTime": 1625474304765,  # 更新时间
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
    assert bo.get_position_volume() == 0.1
    assert bo.get_position_side() == "BOTH"
    assert bo.get_trade_num() is None
    assert bo.get_avg_price() == 0.0
    assert bo.get_mark_price() == 6679.50671178
    assert bo.get_liquidation_price() == 55000.0
    assert bo.get_initial_margin() == 12.5
    assert bo.get_maintenance_margin() is None
    assert bo.open_order_initial_margin() is None
    assert bo.get_position_initial_margin() == 12.5
    assert bo.get_position_commission() is None
    assert bo.get_position_realized_pnl() is None
    assert bo.get_position_unrealized_pnl() == 8.5
    assert bo.get_position_funding_value() is None
    all_data = bo.get_all_data()
    assert all_data["break_even_price"] == 0.0
    assert all_data["liquidation_price"] == 55000.0
    assert all_data["isolated_margin"] == 12.5
    assert all_data["isolated_wallet"] == 13.0
    assert all_data["position_notional"] == 667.950671178
    assert all_data["notional"] == 667.950671178
    assert all_data["market_value"] == 667.950671178


def test_binance_req_position_accepts_raw_json_payload():
    payload = (
        '{"data":{"symbol":"ETHUSDT","positionAmt":"-0.2","entryPrice":"3000",'
        '"markPrice":"2990","notional":"-598","unRealizedProfit":"2",'
        '"marginType":"cross","leverage":"5"}}'
    )
    bo = BinanceRequestPositionData(payload, "ETH-USDT", "PERPETUAL", False)

    bo.init_data()

    assert bo.get_position_symbol_name() == "ETHUSDT"
    assert bo.get_position_volume() == -0.2
    assert bo.get_mark_price() == 2990.0
    assert bo.position_notional == -598.0
    assert bo.get_position_unrealized_pnl() == 2.0


if __name__ == "__main__":
    test_binance_position()
    test_binance_req_position()
