from __future__ import annotations

from dataclasses import replace

import pytest
from bt_api_base.market_protocol import MarketInstrumentKey, MarketSubscriptionKey

from bt_api_binance.containers.tickers.binance_ticker import BinanceWssTickerData
from bt_api_binance.environment import verify_environment
from bt_api_binance.market_provider import (
    BinanceUsdMDemoMarketProvider,
    BoundedBinanceTickerQueue,
    _build_default_demo_stream,
)


def _key(**instrument_changes: str) -> MarketSubscriptionKey:
    instrument = MarketInstrumentKey(
        provider="binance",
        venue="BINANCE",
        environment="demo",
        product_type="USDM_PERPETUAL",
        instrument_id="BTCUSDT",
        native_symbol="BTCUSDT",
    )
    if instrument_changes:
        instrument = replace(instrument, **instrument_changes)
    return MarketSubscriptionKey(
        source_ref="binance-usdm-demo-market-r1",
        entitlement_ref="public-ticker-r1",
        instrument=instrument,
        channel="tickers",
    )


def _ticker(symbol: str = "BTCUSDT", *, event_time: object = 1_770_000_000_123):
    return BinanceWssTickerData(
        {
            "e": "24hrTicker",
            "E": event_time,
            "s": symbol,
            "c": "100.25",
            "b": "100.00",
            "a": "100.50",
            "B": "2.0",
            "A": "3.0",
            "v": "500.0",
            "q": "50000.0",
            "o": "90.0",
            "h": "110.0",
            "l": "80.0",
            "x": "95.0",
            "Q": "1.0",
            "p": "10.25",
            "P": "11.3",
        },
        symbol,
        "SWAP",
        has_been_json_encoded=True,
    )


class _SyntheticBinanceStream:
    def __init__(self, sink: BoundedBinanceTickerQueue) -> None:
        self.sink = sink
        self.start_calls: list[float] = []
        self.stop_calls = 0

    def start(self, *, connect_timeout: float) -> None:
        self.start_calls.append(connect_timeout)

    def stop(self) -> None:
        self.stop_calls += 1


class _UncertainStartStream(_SyntheticBinanceStream):
    def start(self, *, connect_timeout: float) -> None:
        raise RuntimeError("synthetic startup failure")

    def stop(self) -> bool:
        self.stop_calls += 1
        return self.stop_calls > 1


class _InterruptedStartStream(_SyntheticBinanceStream):
    def __init__(self, sink: BoundedBinanceTickerQueue) -> None:
        super().__init__(sink)
        self.worker_active = False

    def start(self, *, connect_timeout: float) -> None:
        self.worker_active = True
        raise KeyboardInterrupt("synthetic startup interrupted")

    def stop(self) -> bool:
        self.stop_calls += 1
        if self.stop_calls == 1:
            raise SystemExit("synthetic cleanup interrupted")
        self.worker_active = False
        return True


def test_demo_ticker_provider_projects_existing_feed_event_and_closes() -> None:
    key = _key()
    streams: list[_SyntheticBinanceStream] = []

    def stream_factory(
        _key: MarketSubscriptionKey, sink: BoundedBinanceTickerQueue
    ) -> _SyntheticBinanceStream:
        stream = _SyntheticBinanceStream(sink)
        streams.append(stream)
        return stream

    provider = BinanceUsdMDemoMarketProvider(stream_factory=stream_factory, connect_timeout=1.5)
    handle = provider.subscribe(key, generation="market-generation-1")
    streams[0].sink.put(_ticker())

    (event,) = provider.poll(handle, limit=1)

    assert streams[0].start_calls == [1.5]
    assert event.generation == "market-generation-1"
    assert event.observed_at_utc == "2026-02-02T02:40:00.123000Z"
    assert dict(event.data) == {
        "exchange_name": "BINANCE",
        "symbol": "BTCUSDT",
        "instrument_id": "BTCUSDT",
        "asset_type": "SWAP",
        "product_type": "USDM_PERPETUAL",
        "environment": "demo",
        "timestamp": 1_770_000_000.123,
        "last_price": 100.25,
        "bid_price": 100.0,
        "ask_price": 100.5,
        "bid_volume": 2.0,
        "ask_volume": 3.0,
        "volume": 500.0,
        "turnover": 50_000.0,
        "open": 90.0,
        "high": 110.0,
        "low": 80.0,
    }
    assert provider.unsubscribe(handle) is True
    assert streams[0].stop_calls == 1
    assert provider.close() is True


def test_failed_start_retains_exact_stream_until_provider_close_confirms_stop() -> None:
    streams: list[_UncertainStartStream] = []

    def stream_factory(_key, sink):
        stream = _UncertainStartStream(sink)
        streams.append(stream)
        return stream

    provider = BinanceUsdMDemoMarketProvider(stream_factory=stream_factory)
    with pytest.raises(RuntimeError, match="synthetic startup failure"):
        provider.subscribe(_key(), generation="market-generation-1")

    assert provider.diagnostics == {
        "active_handles": 0,
        "pending_start_cleanup": 1,
        "invalid_ticker_events": 0,
    }
    assert streams[0].stop_calls == 1
    assert provider.close() is True
    assert streams[0].stop_calls == 2
    assert provider.diagnostics["pending_start_cleanup"] == 0


def test_baseexception_start_retains_stream_when_cleanup_is_uncertain() -> None:
    streams: list[_InterruptedStartStream] = []

    def stream_factory(_key, sink):
        stream = _InterruptedStartStream(sink)
        streams.append(stream)
        return stream

    provider = BinanceUsdMDemoMarketProvider(stream_factory=stream_factory)
    with pytest.raises(KeyboardInterrupt, match="synthetic startup interrupted"):
        provider.subscribe(_key(), generation="market-generation-1")

    assert streams[0].worker_active is True
    assert provider._pending_start_cleanup == [streams[0]]
    assert streams[0].stop_calls == 1
    assert provider.close() is True
    assert streams[0].worker_active is False
    assert streams[0].stop_calls == 2
    assert provider._pending_start_cleanup == []


def test_successfully_unsubscribed_handle_is_removed_and_remains_idempotent() -> None:
    streams: list[_SyntheticBinanceStream] = []

    def stream_factory(_key, sink):
        stream = _SyntheticBinanceStream(sink)
        streams.append(stream)
        return stream

    provider = BinanceUsdMDemoMarketProvider(stream_factory=stream_factory)
    handle = provider.subscribe(_key(), generation="market-generation-1")
    assert len(provider._handles) == 1

    assert provider.unsubscribe(handle) is True
    assert handle.active is False
    assert provider._handles == []
    assert streams[0].stop_calls == 1
    assert provider.unsubscribe(handle) is True
    assert streams[0].stop_calls == 1
    assert provider.close() is True


def test_provider_rejects_non_demo_key_before_stream_factory() -> None:
    calls = 0

    def stream_factory(_key, _sink):
        nonlocal calls
        calls += 1
        raise AssertionError("invalid key must be rejected before stream construction")

    provider = BinanceUsdMDemoMarketProvider(stream_factory=stream_factory)
    invalid_key = replace(_key(), instrument=replace(_key().instrument, environment="live"))

    with pytest.raises(ValueError, match="UNSUPPORTED_BINANCE_USDM_DEMO_MARKET_KEY"):
        provider.subscribe(invalid_key, generation="generation-1")
    assert calls == 0


def test_default_feed_uses_demo_market_route_without_loading_config_or_starting(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "bt_api_binance.exchange_data.binance_exchange_data._get_binance_config",
        lambda: pytest.fail("public market adapter must not load user exchange config"),
    )
    stream = _build_default_demo_stream(_key(), BoundedBinanceTickerQueue())

    assert stream.wss_url == "wss://demo-fstream.binance.com/market/ws"
    assert stream._params.wss_url == "wss://demo-fstream.binance.com/ws"
    assert verify_environment(stream._params) == {
        "environment": "demo",
        "simulated": True,
        "verified": True,
    }
    assert stream.topics == [{"topic": "ticker", "symbol": "BTCUSDT"}]
    assert stream._running_flag is False
