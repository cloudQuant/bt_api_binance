"""Iteration 60: Binance market ingress accepts published (frozen) containers.

``freeze()`` moves a container to a read-only subclass of its class, so
``type(x) is BinanceWssTickerData`` no longer holds for a published ticker.
The ingress checks use Base ``container_class`` instead: still exact (a
hand-made subclass is refused), and the same before and after ``freeze()``.
"""

from __future__ import annotations

import pytest
from bt_api_base.containers.auto_init_mixin import container_class
from test_market_provider import _key, _SyntheticBinanceStream, _ticker

from bt_api_binance.containers.orderbooks.binance_orderbook import BinanceWssOrderBookData
from bt_api_binance.containers.tickers.binance_ticker import BinanceWssTickerData
from bt_api_binance.market_provider import (
    BinanceUsdMDemoMarketProvider,
    BoundedBinanceTickerQueue,
)


def _provider():
    streams = []

    def stream_factory(_key, sink: BoundedBinanceTickerQueue):
        stream = _SyntheticBinanceStream(sink)
        streams.append(stream)
        return stream

    provider = BinanceUsdMDemoMarketProvider(stream_factory=stream_factory, connect_timeout=1.0)
    handle = provider.subscribe(_key(), generation="market-generation-1")
    return provider, handle, streams[0]


def test_frozen_ticker_is_projected_exactly_like_the_unfrozen_one():
    provider, handle, stream = _provider()
    try:
        stream.sink.put(_ticker())
        (live,) = provider.poll(handle, limit=1)
        published = _ticker()
        published.init_data()
        published.freeze()
        assert type(published) is not BinanceWssTickerData
        assert container_class(published) is BinanceWssTickerData
        stream.sink.put(published)
        (frozen,) = provider.poll(handle, limit=1)
        assert dict(frozen.data) == dict(live.data)
        assert frozen.observed_at_utc == live.observed_at_utc
    finally:
        provider.unsubscribe(handle)
        provider.close()


def test_hand_made_ticker_subclass_is_refused():
    class _Forged(BinanceWssTickerData):
        pass

    provider, handle, stream = _provider()
    try:
        forged = _Forged(*_ticker_args())
        stream.sink.put(forged)
        with pytest.raises(ValueError, match="INVALID_BINANCE_TICKER_EVENT"):
            provider.poll(handle, limit=1)
    finally:
        provider.unsubscribe(handle)
        provider.close()


def _ticker_args():
    original = _ticker()
    return (original.ticker_info, original.symbol_name, original.asset_type, True)


def test_frozen_order_book_keeps_its_exact_class_and_reinit_is_a_no_op():
    data = {
        "e": "depthUpdate",
        "E": 1571889248277,
        "s": "BTCUSDT",
        "U": 157,
        "u": 160,
        "pu": 149,
        "b": [["7403.89", "0.002"]],
        "a": [["7405.96", "3.340"]],
    }
    book = BinanceWssOrderBookData(data, "BTCUSDT", "SWAP", True)
    book.init_data()
    book.freeze()
    assert container_class(book) is BinanceWssOrderBookData
    # The stream session calls init_data() after its class check; on a
    # published book that is a guarded no-op, not a write.
    assert book.init_data() is book
    assert book.get_symbol_name() == "BTCUSDT"
