"""Position mode is expressed by legal native futures order parameters."""

import pytest

from bt_api_binance.feeds.swap import BinanceRequestDataSwap


@pytest.mark.parametrize("position_side", ["LONG", "SHORT"])
def test_hedge_parameters_omit_reduce_only(position_side):
    feed = BinanceRequestDataSwap(None, environment="demo")
    try:
        _, params, _ = feed._make_order(
            "BTCUSDT",
            0.002,
            price=60000,
            order_type="sell-limit",
            offset="close",
            position_side=position_side,
            reduce_only=True,
            time_in_force="IOC",
        )
        assert params["positionSide"] == position_side
        assert params["timeInForce"] == "IOC"
        assert "reduceOnly" not in params
    finally:
        feed._http_client.close()


def test_explicit_both_preserves_net_reduce_only():
    feed = BinanceRequestDataSwap(None, environment="demo")
    try:
        _, params, _ = feed._make_order(
            "BTCUSDT",
            0.002,
            price=60000,
            order_type="sell-limit",
            offset="close",
            position_side="BOTH",
            reduce_only=True,
        )
        assert params["positionSide"] == "BOTH"
        assert params["reduceOnly"] == "true"
    finally:
        feed._http_client.close()
