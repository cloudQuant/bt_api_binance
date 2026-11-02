"""Binance containers against Base container contract v1 (iteration 60, 60.04/60.05).

Every standard Base getter answers on a Binance container (unknown facts are
None, not NotImplementedError), readers cannot mutate a published container,
and ticker volume semantics are declared per endpoint.
"""

from __future__ import annotations

import pytest
from bt_api_base.containers.auto_init_mixin import container_fingerprint
from bt_api_base.containers.bars.bar import BarData
from bt_api_base.containers.orders.order import OrderData
from bt_api_base.containers.positions.position import PositionData
from bt_api_base.containers.semantics import (
    VOLUME_LAST_TRADE,
    VOLUME_UNKNOWN,
    normalize_position_side,
)
from bt_api_base.containers.tickers.ticker import TickerData
from bt_api_base.containers.trades.trade import TradeData

from bt_api_binance.containers.bars.binance_bar import BinanceRequestBarData, BinanceWssBarData
from bt_api_binance.containers.orders.binance_order import BinanceRequestOrderData
from bt_api_binance.containers.positions.binance_position import BinanceRequestPositionData
from bt_api_binance.containers.tickers.binance_ticker import (
    BinanceRequestTickerData,
    BinanceWssTickerData,
)
from bt_api_binance.containers.trades.binance_trade import BinanceRequestTradeData

WSS_TICKER = {
    "e": "24hrTicker",
    "E": 1700000000000,
    "s": "BTCUSDT",
    "b": "50000.00",
    "B": "10.0",
    "a": "50001.00",
    "A": "5.0",
    "c": "50000.50",
    "Q": "1.0",
    "o": "49000.00",
    "h": "51000.00",
    "l": "48000.00",
    "x": "49500.00",
    "v": "10000.0",
    "q": "500000000.0",
    "p": "500.50",
    "P": "1.01",
}
BOOK_TICKER = {
    "symbol": "BTCUSDT",
    "bidPrice": "50000.00",
    "bidQty": "10.0",
    "askPrice": "50001.00",
    "askQty": "5.0",
}
WSS_BAR = {
    "e": "kline",
    "E": 1607443058651,
    "s": "BTCUSDT",
    "k": {
        "t": 1607443020000,
        "T": 1607443079999,
        "o": "50000",
        "c": "50500",
        "h": "51000",
        "l": "49000",
        "v": "100",
        "q": "5000000",
        "n": 500,
        "V": "50",
        "Q": "2500000",
        "x": False,
    },
}
REQUEST_BAR = [
    1607444700000,
    "50000",
    "51000",
    "49000",
    "50500",
    "100",
    1607444759999,
    "5000000",
    500,
    "50",
    "2500000",
    "0",
]
ORDER = {
    "symbol": "BTCUSDT",
    "orderId": "123456",
    "clientOrderId": "client_123",
    "price": "50000",
    "origQty": "0.001",
    "executedQty": "0.0005",
    "side": "BUY",
    "type": "LIMIT",
    "status": "NEW",
    "time": 1688671955000,
}
TRADE = {
    "id": 123,
    "symbol": "BTCUSDT",
    "orderId": 456,
    "side": "BUY",
    "price": "50000",
    "qty": "1",
    "time": 1700000000000,
    "maker": True,
    "commission": "0.1",
    "commissionAsset": "USDT",
}
POSITION = {
    "entryPrice": "6563.6",
    "breakEvenPrice": "6563.6",
    "marginType": "isolated",
    "isAutoAddMargin": "false",
    "isolatedMargin": "12.5",
    "leverage": "10",
    "liquidationPrice": "55000",
    "markPrice": "6679.50671178",
    "maxNotionalValue": "20000000",
    "positionAmt": "0.100",
    "notional": "667.950671178",
    "isolatedWallet": "13",
    "symbol": "BTCUSDT",
    "unRealizedProfit": "8.50000000",
    "positionSide": "BOTH",
    "updateTime": 1625474304765,
}

CASES = [
    (TickerData, lambda: BinanceWssTickerData(WSS_TICKER, "BTC-USDT", "SPOT", True)),
    (TickerData, lambda: BinanceRequestTickerData(BOOK_TICKER, "BTC-USDT", "SPOT", True)),
    (BarData, lambda: BinanceWssBarData(WSS_BAR, "BTC-USDT", "SPOT", True)),
    (BarData, lambda: BinanceRequestBarData(REQUEST_BAR, "BTC-USDT", "SPOT", True)),
    (OrderData, lambda: BinanceRequestOrderData(ORDER, "BTC-USDT", "SPOT", True)),
    (TradeData, lambda: BinanceRequestTradeData(TRADE, "BTC-USDT", "SPOT", True)),
    (PositionData, lambda: BinanceRequestPositionData(POSITION, "BTC-USDT", "SWAP", True)),
]
IDS = [
    "WssTicker",
    "BookTicker",
    "WssBar",
    "RequestBar",
    "RequestOrder",
    "RequestTrade",
    "RequestPosition",
]


def _standard_getters(base):
    return sorted(
        name
        for name, value in vars(base).items()
        if name.startswith("get_") and callable(value) and name != "get_all_data"
    )


@pytest.mark.parametrize("base, factory", CASES, ids=IDS)
def test_every_standard_getter_answers(base, factory):
    container = factory()
    for name in _standard_getters(base):
        getattr(container, name)()


@pytest.mark.parametrize("base, factory", CASES, ids=IDS)
def test_reading_a_frozen_container_does_not_mutate_it(base, factory):
    container = factory().freeze()
    container.get_all_data()  # first call may memoize its dict
    before = container_fingerprint(container)
    for name in _standard_getters(base):
        getattr(container, name)()
    container.get_all_data()
    assert container_fingerprint(container) == before


@pytest.mark.parametrize("base, factory", CASES, ids=IDS)
def test_get_all_data_result_cannot_corrupt_shared_state(base, factory):
    container = factory().freeze()
    first = container.get_all_data()
    snapshot = dict(first)
    first["injected_by_consumer"] = True
    for key in list(snapshot):
        first[key] = "corrupted"
    assert container.get_all_data() == snapshot


def test_ticker_volume_semantics_per_endpoint():
    stream = BinanceWssTickerData(WSS_TICKER, "BTC-USDT", "SPOT", True)
    assert stream.get_volume_semantics() == VOLUME_LAST_TRADE
    assert stream.get_last_volume() == 1.0
    book = BinanceRequestTickerData(BOOK_TICKER, "BTC-USDT", "SPOT", True)
    assert book.get_volume_semantics() == VOLUME_UNKNOWN
    assert book.get_last_volume() is None


def test_bar_status():
    assert BinanceWssBarData(WSS_BAR, "BTC-USDT", "SPOT", True).get_bar_status() is False


def test_position_standard_names_and_side():
    position = BinanceRequestPositionData(POSITION, "BTC-USDT", "SWAP", True)
    assert position.get_maintain_margin() == position.get_maintenance_margin()
    assert position.get_position_fee() == position.get_position_commission()
    assert normalize_position_side(position.get_position_side()) == "net"
