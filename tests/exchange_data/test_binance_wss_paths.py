"""
Tests for Binance WebSocket API - New implementations
 Binance WebSocket API 
"""

from __future__ import annotations

import pytest

from bt_api_binance.exchange_data import (
    BinanceExchangeDataSpot,
    BinanceExchangeDataSwap,
)


@pytest.mark.kline
def test_spot_wss_kline_timezone():
    """ Spot WebSocket kline_timezone """
    spot = BinanceExchangeDataSpot()
    assert "kline_timezone" in spot.wss_paths
    assert spot.wss_paths["kline_timezone"]["params"] == ["<symbol>@kline_<period>@+08:00"]
    assert spot.wss_paths["kline_timezone"]["method"] == "SUBSCRIBE"


def test_spot_wss_liquidation_order():
    """ Spot WebSocket liquidation_order """
    spot = BinanceExchangeDataSpot()
    assert "liquidation_order" in spot.wss_paths
    assert spot.wss_paths["liquidation_order"]["params"] == ["<symbol>@forceOrder"]
    # Also verify it's the same as force_order
    assert spot.wss_paths["liquidation_order"] == spot.wss_paths["force_order"]


def test_swap_wss_liquidation_order():
    """ Swap WebSocket liquidation_order """
    swap = BinanceExchangeDataSwap()
    assert "liquidation_order" in swap.wss_paths
    assert swap.wss_paths["liquidation_order"]["params"] == ["<symbol>@forceOrder"]
    # Also verify existing liquidation alias
    assert "liquidation" in swap.wss_paths
    assert swap.wss_paths["liquidation"] == swap.wss_paths["force_order"]


def test_swap_all_liquidation_order_stream():
    """"""
    swap = BinanceExchangeDataSwap()
    assert "all_force_order" in swap.wss_paths
    assert swap.wss_paths["all_force_order"]["params"] == ["!forceOrder@arr"]


def test_wss_paths_count():
    """ WebSocket """
    spot = BinanceExchangeDataSpot()
    swap = BinanceExchangeDataSwap()

    # Verify kline_timezone was added
    assert "kline_timezone" in spot.wss_paths

    # Verify liquidation_order was added to both
    assert "liquidation_order" in spot.wss_paths
    assert "liquidation_order" in swap.wss_paths


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
