"""
Tests for Binance Margin WebSocket API
 Binance  WebSocket API
"""

import queue
from unittest.mock import patch

import pytest

from bt_api_binance.containers.accounts import BinanceSpotWssAccountData
from bt_api_binance.containers.orders.binance_order import BinanceSpotWssOrderData
from bt_api_binance.containers.trades.binance_trade import BinanceSpotWssTradeData
from bt_api_binance.exchange_data import BinanceExchangeDataMargin, BinanceExchangeDataSpot
from bt_api_binance.feeds.margin import BinanceAccountWssDataMargin
from bt_api_binance.feeds.spot import BinanceAccountWssDataSpot


def init_margin_wss():
    """ Margin WSS  (mock wss_author )"""
    data_queue = queue.Queue()
    kwargs = {
        "exchange_data": BinanceExchangeDataMargin(),
    }
    # Mock wss_author to avoid actual network calls
    with patch.object(BinanceAccountWssDataMargin, "wss_author", return_value=None):
        margin_wss = BinanceAccountWssDataMargin(data_queue, **kwargs)
        # Set listen_key manually
        margin_wss.listen_key = "test_listen_key"
    return margin_wss, data_queue


def test_margin_account_wss_has_handle_data():
    """ Margin Account WSS  handle_data """
    margin_wss, _ = init_margin_wss()
    assert hasattr(margin_wss, "handle_data")
    assert callable(margin_wss.handle_data)


def test_margin_account_wss_handle_data_execution_report():
    """ executionReport """
    margin_wss, data_queue = init_margin_wss()

    #  executionReport  ()
    content = {
        "e": "executionReport",
        "E": 123456789,
        "s": "BTCUSDT",
        "c": "CLIENT_ORDER_ID",
        "S": "BUY",
        "o": "LIMIT",
        "f": "GTC",
        "q": "1.00000000",
        "p": "50000.00000000",
        "x": "NEW",  #  TRADE 
        "X": "NEW",
        "r": "NONE",
        "i": 12345678,
        "l": "0.00000000",
        "z": "0.00000000",
        "L": "0.00000000",
        "n": "0",
        "N": None,
        "T": 123456789,
        "t": 0,
        "I": 12345678,
        "w": True,
        "m": False,
        "M": False,
        "O": 123456789,
        "Z": "0.00000000",
        "Y": "0.00000000",
        "Q": "0.00000000",
    }

    margin_wss.handle_data(content)

    # 
    try:
        data = data_queue.get(timeout=1)
        assert isinstance(data, BinanceSpotWssOrderData)
    except queue.Empty:
        pytest.fail("No order data received")


def test_margin_account_wss_handle_data_outbound_account_position():
    """ outboundAccountPosition """
    margin_wss, data_queue = init_margin_wss()

    #  outboundAccountPosition 
    content = {
        "e": "outboundAccountPosition",
        "E": 123456789,
        "u": 123456789,
        "B": [
            {"a": "USDT", "f": "1000.00000000", "l": "0.00000000"},
            {"a": "BTC", "f": "0.50000000", "l": "0.00000000"},
        ],
    }

    margin_wss.handle_data(content)

    # 
    try:
        data = data_queue.get(timeout=1)
        assert isinstance(data, BinanceSpotWssAccountData)
    except queue.Empty:
        pytest.fail("No account data received")


def test_margin_account_wss_handle_data_execution_report_trade():
    """ executionReport """
    margin_wss, data_queue = init_margin_wss()

    #  executionReport 
    content = {
        "e": "executionReport",
        "E": 123456789,
        "s": "BTCUSDT",
        "c": "CLIENT_ORDER_ID",
        "S": "BUY",
        "o": "LIMIT",
        "f": "GTC",
        "q": "1.00000000",
        "p": "50000.00000000",
        "x": "TRADE",  # 
        "X": "FILLED",
        "r": "NONE",
        "i": 12345678,
        "l": "1.00000000",
        "z": "1.00000000",
        "L": "50000.00000000",
        "n": "0",
        "N": None,
        "T": 123456789,
        "t": 12345678,
        "I": 12345678,
        "w": True,
        "m": False,
        "M": False,
        "O": 123456789,
        "Z": "50000.00000000",
        "Y": "0.00000000",
        "Q": "0.00000000",
    }

    margin_wss.handle_data(content)

    # 
    try:
        data = data_queue.get(timeout=1)
        assert isinstance(data, BinanceSpotWssTradeData)
    except queue.Empty:
        pytest.fail("No trade data received")


def test_margin_account_wss_handle_data_balance_update():
    """ balanceUpdate """
    margin_wss, data_queue = init_margin_wss()

    #  balanceUpdate  ()
    content = {
        "e": "balanceUpdate",
        "E": 1573200697114,
        "s": "BTC",
        "u": "15896533547050558808",
        "B": "500.00000000",
    }

    margin_wss.handle_data(content)

    # 
    try:
        data = data_queue.get(timeout=1)
        assert isinstance(data, BinanceSpotWssAccountData)
    except queue.Empty:
        pytest.fail("No balance update data received")


def test_margin_account_wss_has_push_methods():
    """ Margin Account WSS  push """
    margin_wss, _ = init_margin_wss()

    assert hasattr(margin_wss, "push_account")
    assert hasattr(margin_wss, "push_order")
    assert hasattr(margin_wss, "push_trade")
    assert hasattr(margin_wss, "push_balance")
    assert callable(margin_wss.push_account)
    assert callable(margin_wss.push_order)
    assert callable(margin_wss.push_trade)
    assert callable(margin_wss.push_balance)


def test_spot_account_wss_has_push_balance():
    """ Spot Account WSS  push_balance """
    data_queue = queue.Queue()
    kwargs = {"exchange_data": BinanceExchangeDataSpot()}
    # Mock wss_author to avoid actual network calls
    with patch.object(BinanceAccountWssDataSpot, "wss_author", return_value=None):
        spot_wss = BinanceAccountWssDataSpot(data_queue, **kwargs)
        spot_wss.listen_key = "test_listen_key"

    assert hasattr(spot_wss, "push_balance")
    assert callable(spot_wss.push_balance)


def test_spot_account_wss_handle_balance_update():
    """ Spot  balanceUpdate """
    data_queue = queue.Queue()
    kwargs = {"exchange_data": BinanceExchangeDataSpot()}
    # Mock wss_author to avoid actual network calls
    with patch.object(BinanceAccountWssDataSpot, "wss_author", return_value=None):
        spot_wss = BinanceAccountWssDataSpot(data_queue, **kwargs)
        spot_wss.listen_key = "test_listen_key"

    #  balanceUpdate 
    content = {
        "e": "balanceUpdate",
        "E": 1573200697114,
        "s": "BTC",
        "u": "15896533547050558808",
        "B": "500.00000000",
    }

    spot_wss.handle_data(content)

    # 
    try:
        data = data_queue.get(timeout=1)
        assert isinstance(data, BinanceSpotWssAccountData)
    except queue.Empty:
        pytest.fail("No balance update data received")


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
