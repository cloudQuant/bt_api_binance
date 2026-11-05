"""Iteration 62: Binance USDⓈ-M bookTicker + aggTrade tick channel (fake frames).

The real route-bound Binance market WSS is built for the demo route; only its
``start``/``stop`` are replaced by a fake lifecycle, and JSON frames enter
through the real ``on_message`` -> ``message_rsp`` -> ``handle_data`` path.
Evidence level: UNIT/FAKE; the owner test is INTEGRATION_SIM against the
in-process SDK ``ProviderMarketStreamOwner``.
"""

from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest
from bt_api_base.market_protocol import MarketInstrumentKey
from bt_api_base.market_stream_protocol import MarketStreamRequest
from bt_api_base.market_stream_provider_protocol import (
    MarketStreamChannelCapability,
    MarketStreamProviderContractError,
    SelectedMarketStreamRoute,
)
from bt_api_base.market_tick_protocol import (
    MarketClockQuality,
    MarketFreshnessStatus,
    MarketTickEvent,
    MarketTickPayload,
)
from bt_api_binance import market_tick_stream
from bt_api_binance.feeds.swap import BinanceRequestDataSwap
from bt_api_binance.market_stream_provider import BinanceMarketStreamAdapter
from bt_api_binance.market_tick_stream import BinanceTickMarketStreamSession

ROUTE = "BINANCE___SWAP"
SYMBOL = "BTCUSDT"
KEY = MarketInstrumentKey("binance", "BINANCE", "demo", "USDM_PERPETUAL", SYMBOL, SYMBOL)
REAL_WSS = market_tick_stream._RouteBoundBinanceTickWss


def _connect(stream):
    stream._connection_generation += 1
    socket = object()
    with stream._connection_lock:
        stream._connection_by_id[id(socket)] = (socket, stream._connection_generation)
    stream.fake_socket = socket


def _fake_lifecycle(stream, streams):
    def start(connect_timeout=30):
        stream._stop_event = threading.Event()
        _connect(stream)
        stream._running_flag = True

    def stop():
        stream._running_flag = False
        stream._stop_event.set()
        stream.ws = None

    stream.start = start
    stream.stop = stop
    streams.append(stream)
    return stream


def _book(stream, bid="60000", ask="60001", event_ms=1794020400123, symbol=SYMBOL):
    frame = {"e": "bookTicker", "u": 1, "E": event_ms, "T": event_ms - 1, "s": symbol,
             "b": bid, "B": "7", "a": ask, "A": "12"}
    stream.on_message(stream.fake_socket, json.dumps(frame))


def _trade(stream, price="60000.5", event_ms=1794020400200, agg_id=9, qty="0.003"):
    frame = {"e": "aggTrade", "E": event_ms, "a": agg_id, "s": SYMBOL, "p": price, "q": qty,
             "f": 1, "l": 1, "T": event_ms - 1, "m": False}
    stream.on_message(stream.fake_socket, json.dumps(frame))


@pytest.fixture
def env():
    feed = BinanceRequestDataSwap(None, environment="demo")
    route = SelectedMarketStreamRoute(ROUTE, feed, KEY, "demo")
    streams: list = []
    session = BinanceTickMarketStreamSession(
        route,
        wake_callback=lambda: None,
        stream_factory=lambda ingress, selected: _fake_lifecycle(REAL_WSS(ingress, selected), streams),
    )
    yield SimpleNamespace(feed=feed, route=route, session=session, streams=streams)
    feed._http_client.close()


def _subscribe(env):
    binding = env.session.subscribe(MarketStreamRequest(ROUTE, KEY, "tick"))
    return binding, env.streams[0]


def test_adapter_advertises_tick_only_and_opens_a_tick_session(env):
    adapter = BinanceMarketStreamAdapter(env.route)
    assert adapter.capabilities() == (MarketStreamChannelCapability(channel="tick"),)
    assert type(adapter.open_session(wake_callback=lambda: None)) is BinanceTickMarketStreamSession
    with pytest.raises(MarketStreamProviderContractError):
        env.session.subscribe(MarketStreamRequest(ROUTE, KEY, "orderbook", depth=5))


def test_subscribe_binds_the_demo_bookticker_and_aggtrade_source(env):
    binding, stream = _subscribe(env)
    assert stream.wss_url == "wss://demo-fstream.binance.com/ws"
    assert stream.topics == [
        {"topic": "book_ticker", "symbol": SYMBOL},
        {"topic": "agg_trade", "symbol": SYMBOL},
    ]
    assert json.loads(stream._params.get_wss_path(topic="book_ticker", symbol=SYMBOL))["params"] == [
        "btcusdt@bookTicker"
    ]
    assert json.loads(stream._params.get_wss_path(topic="agg_trade", symbol=SYMBOL))["params"] == [
        "btcusdt@aggTrade"
    ]
    assert binding.source.provider == "binance" and binding.source.connection_generation == 1
    assert binding.initial_events == () and binding.key.channel == "tick"


def test_ticks_merge_quote_and_trade_honestly(env):
    binding, stream = _subscribe(env)
    _book(stream)
    _trade(stream)
    _book(stream, bid="60000.5", event_ms=1794020400300)
    quote_only, with_trade, merged = env.session.poll(timeout_ms=0, max_events=10)
    assert all(type(event) is MarketTickEvent for event in (quote_only, with_trade, merged))
    assert [e.cursor.sequence for e in (quote_only, with_trade, merged)] == [1, 2, 3]
    first = quote_only.data
    assert first.last_price is None and (first.bid_price, first.ask_price) == (60000.0, 60001.0)
    assert (first.bid_size, first.ask_size) == (7.0, 12.0) and first.quality_flags == ()
    assert first.provider_event_time_utc == "2026-11-07T03:00:00.123000Z"
    assert first.event_time_provenance == "provider_reported"
    assert first.received_at_utc is not None and first.received_monotonic_ns > 0
    assert first.continuity_status == "gap"
    second = with_trade.data
    assert second.last_price == 60000.5 and second.bid_price == 60000.0
    assert second.provider_event_time_utc == "2026-11-07T03:00:00.200000Z"
    assert second.continuity_status == "continuous"
    # The first aggregate trade anchors the volume accounting (baseline).
    assert (second.delta_volume, second.volume_complete, second.volume_quality) == (
        0.0, False, "baseline"
    )
    assert merged.data.bid_price == 60000.5 and merged.data.last_price == 60000.5
    assert (merged.data.delta_volume, merged.data.volume_complete) == (0.0, True)
    assert (first.delta_volume, first.volume_complete, first.volume_quality) == (0.0, False, "baseline")
    for tick in (first, second, merged.data):
        assert tick.source_clock_quality is MarketClockQuality.UNKNOWN
        assert tick.receive_clock_quality is MarketClockQuality.UNKNOWN
        assert tick.freshness_status is MarketFreshnessStatus.UNAVAILABLE
        assert tick.cumulative_volume is None and tick.quality_flags == ()
        assert tick.execution_eligible is False
        assert MarketTickPayload.from_dict(tick.to_dict()) == tick
    assert quote_only.source == binding.source


def test_lost_or_foreign_frames_make_the_next_tick_a_gap(env):
    _binding, stream = _subscribe(env)
    _book(stream)
    _book(stream, bid="nan")
    _book(stream, symbol="ETHUSDT")
    _book(stream)
    events = env.session.poll(timeout_ms=0, max_events=10)
    assert [e.data.continuity_status for e in events] == ["gap", "gap"]
    assert env.session.counters["tick_frame_invalid"] == 2


def test_reconnect_requires_resync_to_a_new_epoch(env):
    binding, stream = _subscribe(env)
    _book(stream)
    assert len(env.session.poll(timeout_ms=0, max_events=10)) == 1
    _connect(stream)  # the WSS reopened: generation 2
    _book(stream)
    with pytest.raises(MarketStreamProviderContractError) as info:
        env.session.poll(timeout_ms=0, max_events=10)
    assert info.value.code == "MARKET_STREAM_PROVIDER_EVENT_INVALID"
    _book(stream)
    assert env.session.poll(timeout_ms=0, max_events=10) == ()
    renewed = env.session.resync(binding, acknowledge_data_loss=True)
    assert renewed.source.epoch != binding.source.epoch
    assert renewed.source.stream_id == binding.source.stream_id
    assert renewed.source.connection_generation == 2
    _trade(stream)
    (event,) = env.session.poll(timeout_ms=0, max_events=10)
    assert event.source == renewed.source and event.cursor.sequence == 1
    assert event.data.continuity_status == "gap"
    assert event.data.bid_price is None  # quote state does not cross epochs


def test_unsubscribe_and_close_stop_the_stream(env):
    binding, stream = _subscribe(env)
    assert env.session.unsubscribe(binding) is True
    assert stream._running_flag is False and stream._stop_event.is_set()
    assert env.session.close() is True


def test_sdk_owner_delivers_ticks_through_the_registered_provider(monkeypatch):
    # Discovers the provider through the installed bt_api.market_stream_providers
    # entry point, as BtApi.market_stream() does.
    owner_module = pytest.importorskip("bt_api_py.service_market_stream_owner")
    feed = BinanceRequestDataSwap(None, environment="demo")
    streams: list = []
    monkeypatch.setattr(
        market_tick_stream,
        "_RouteBoundBinanceTickWss",
        lambda ingress, route: _fake_lifecycle(REAL_WSS(ingress, route), streams),
    )
    api = SimpleNamespace(
        exchange_feeds={ROUTE: feed},
        _selected_route_clients={ROUTE: feed},
        _selected_provider_route=lambda name: (feed, "demo"),
    )
    owner = owner_module.ProviderMarketStreamOwner(api)
    try:
        subscription = owner.subscribe(MarketStreamRequest(ROUTE, KEY, "tick"))
        _book(streams[0])
        _trade(streams[0])
        result = owner.poll(subscription, timeout_ms=0, max_events=10)
        assert [event.data.last_price for event in result.events] == [None, 60000.5]
        assert result.state.value == "active"
    finally:
        owner.close()
        feed._http_client.close()


def test_a_reconnect_alone_surfaces_recovery_without_waiting_for_data(env):
    _binding, stream = _subscribe(env)
    _book(stream)
    env.session.poll(timeout_ms=0, max_events=10)
    _connect(stream)  # reopened, nothing received yet on the new connection
    with pytest.raises(MarketStreamProviderContractError):
        env.session.poll(timeout_ms=0, max_events=10)
    assert env.session.counters["recovery:connection_changed"] == 1


# ------------------------------------------------------------ traded volume


def _volume(event):
    data = event.data
    return (data.delta_volume, data.volume_complete, data.volume_quality, data.continuity_status)


def test_aggregate_trades_carry_delta_volume_after_a_baseline(env):
    _binding, stream = _subscribe(env)
    _book(stream)
    _trade(stream, agg_id=100, qty="0.005")
    _trade(stream, agg_id=101, qty="0.002", price="60001")
    _book(stream, bid="60000.7")
    quote, baseline, counted, after = env.session.poll(timeout_ms=0, max_events=10)
    assert _volume(quote) == (0.0, False, "baseline", "gap")
    assert _volume(baseline) == (0.0, False, "baseline", "continuous")
    assert _volume(counted) == (0.002, True, "continuous", "continuous")
    assert counted.data.last_price == 60001.0 and counted.data.ask_price == 60001.0
    assert _volume(after) == (0.0, True, "continuous", "continuous")
    assert after.data.last_price == 60001.0


def test_an_aggregate_id_gap_marks_volume_incomplete_without_inventing(env):
    _binding, stream = _subscribe(env)
    _book(stream)
    _trade(stream, agg_id=100)
    _trade(stream, agg_id=103, qty="0.004")
    _trade(stream, agg_id=104, qty="0.001")
    _quote, _baseline, gap, resumed = env.session.poll(timeout_ms=0, max_events=10)
    assert _volume(gap) == (0.004, False, "discontinuous", "gap")
    assert _volume(resumed) == (0.001, True, "continuous", "continuous")
    assert env.session.counters["trade_id_gap"] == 1


def test_repeated_aggregate_ids_are_not_counted_twice(env):
    _binding, stream = _subscribe(env)
    _trade(stream, agg_id=100)
    _trade(stream, agg_id=101)
    _trade(stream, agg_id=101)
    _trade(stream, agg_id=99)
    events = env.session.poll(timeout_ms=0, max_events=10)
    assert len(events) == 2
    assert env.session.counters["trade_repeated_or_out_of_order"] == 2


def test_resync_starts_a_new_volume_baseline(env):
    binding, stream = _subscribe(env)
    _trade(stream, agg_id=100)
    _trade(stream, agg_id=101)
    env.session.poll(timeout_ms=0, max_events=10)
    _connect(stream)
    with pytest.raises(MarketStreamProviderContractError):
        env.session.poll(timeout_ms=0, max_events=10)
    env.session.resync(binding, acknowledge_data_loss=True)
    _trade(stream, agg_id=102)
    (event,) = env.session.poll(timeout_ms=0, max_events=10)
    assert _volume(event) == (0.0, False, "baseline", "gap")


def test_sdk_normalizer_sees_known_delta_volume_semantics(env):
    contracts = pytest.importorskip("bt_api_py.market_tick_contracts")
    _binding, stream = _subscribe(env)
    _book(stream)
    _trade(stream, agg_id=100)
    _trade(stream, agg_id=101)
    for event in env.session.poll(timeout_ms=0, max_events=10)[1:]:
        data = event.data
        # The fields Backtrader's market_tick_adapter hands to the SDK normalizer.
        tick = SimpleNamespace(
            schema_version="sdk.market.tick.v2",
            volume_semantics="delta" if data.delta_volume is not None else "unknown",
            delta_volume=data.delta_volume,
            volume=data.delta_volume,
            price=data.last_price,
            bid_price=data.bid_price,
            ask_price=data.ask_price,
            bid_volume=data.bid_size,
            ask_volume=data.ask_size,
            quality_flags=list(data.quality_flags),
        )
        flags = contracts.prepare_market_tick_fields(
            tick, replay_adapter_available=False, legacy_schema="legacy"
        )[3]
        assert flags == set()
