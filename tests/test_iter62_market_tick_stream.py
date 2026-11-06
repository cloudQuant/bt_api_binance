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
import time
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
from bt_api_binance.market_tick_stream import (
    BinanceTickMarketStreamSession,
    _TickChannel,
    trade_volume,
)

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


class _Log:
    """Captures the session's warnings (the ``bt_api_base`` logger proxy API)."""

    def __init__(self):
        self.warnings: list = []

    def warning(self, *args, **_kwargs):
        self.warnings.append(args[0] % args[1:] if len(args) > 1 else args[0])


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
    log = _Log()
    clock = SimpleNamespace(now=1000.0)
    session._logger = log  # no file logger in tests
    session._log_clock = lambda: clock.now
    yield SimpleNamespace(
        feed=feed, route=route, session=session, streams=streams, log=log, clock=clock
    )
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
    # D62-38: the binding's first tick is continuous; only its volume is a baseline.
    assert first.continuity_status == "continuous"
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
    assert [e.data.continuity_status for e in events] == ["continuous", "gap"]
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
    # The loss was acknowledged by the resync; the new epoch starts continuous.
    assert event.data.continuity_status == "continuous"
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
    assert _volume(quote) == (0.0, False, "baseline", "continuous")
    assert _volume(baseline) == (0.0, False, "baseline", "continuous")
    assert _volume(counted) == (0.002, True, "continuous", "continuous")
    assert counted.data.last_price == 60001.0 and counted.data.ask_price == 60001.0
    assert _volume(after) == (0.0, True, "continuous", "continuous")
    assert after.data.last_price == 60001.0


def test_a_trade_id_jump_keeps_continuity_and_marks_only_its_row_volume_incomplete(env):
    # User decision 3 (iteration 62), following OKX: an uninterrupted
    # connection is continuous; a jump only makes that push's volume incomplete.
    binding, stream = _subscribe(env)
    _book(stream)
    _trade(stream, agg_id=100)
    _trade(stream, agg_id=103, qty="0.004")  # ids 101 and 102 never arrived
    _trade(stream, agg_id=104, qty="0.001")
    _book(stream, bid="60000.2")
    _quote, _baseline, jump, resumed, quote = env.session.poll(timeout_ms=0, max_events=10)
    assert _volume(jump) == (0.004, False, "discontinuous", "continuous")
    assert _volume(resumed) == (0.001, True, "continuous", "continuous")
    assert _volume(quote) == (0.0, True, "continuous", "continuous")
    assert all(event.data.quality_flags == () for event in (jump, resumed, quote))
    assert env.session.counters["trade_id_jump"] == 1
    assert "trade_id_gap" not in env.session.counters
    assert env.session.trade_id_jumps(binding) == 1
    (warning,) = env.log.warnings
    assert f"instrument={SYMBOL}" in warning and "jump=2 " in warning
    assert "binding_jumps=1 " in warning and "suppressed=0" in warning


def test_trade_volume_reports_the_jump_size():
    channel = _TickChannel(SimpleNamespace(), 1)
    assert trade_volume(channel, 100, 5.0) == (0.0, False, "baseline", 0)
    assert trade_volume(channel, 101, 3.0) == (3.0, True, "continuous", 0)
    assert trade_volume(channel, 110, 4.0) == (4.0, False, "discontinuous", 8)
    assert trade_volume(channel, 110, 4.0) is None  # repeated id
    assert channel.trade_anchor == 110 and channel.last_trade_id_jump == 8


def test_trade_id_jump_warnings_are_throttled_per_instrument_but_every_jump_counts(env):
    binding, stream = _subscribe(env)
    _trade(stream, agg_id=100)
    _trade(stream, agg_id=105)
    events = list(env.session.poll(timeout_ms=0, max_events=10))  # first jump: logged
    env.clock.now += 59.0
    _trade(stream, agg_id=110)
    events += env.session.poll(timeout_ms=0, max_events=10)
    assert [event.data.continuity_status for event in events] == ["continuous"] * 3
    assert len(env.log.warnings) == 1  # the second jump is inside the minute
    env.clock.now += 1.0
    _trade(stream, agg_id=120, qty="0.001")
    (event,) = env.session.poll(timeout_ms=0, max_events=10)
    assert _volume(event) == (0.001, False, "discontinuous", "continuous")
    assert len(env.log.warnings) == 2
    assert "jump=9 " in env.log.warnings[1] and "binding_jumps=3 " in env.log.warnings[1]
    assert "suppressed=1" in env.log.warnings[1]
    assert env.session.counters["trade_id_jump"] == 3
    assert env.session.trade_id_jumps(binding) == 3


def test_a_failing_jump_logger_never_stops_the_stream(env):
    binding, stream = _subscribe(env)

    class _Broken:
        def warning(self, *_args, **_kwargs):
            raise RuntimeError("sink down")

    env.session._logger = _Broken()
    _trade(stream, agg_id=100)
    _trade(stream, agg_id=105, qty="0.002")
    _baseline, jump = env.session.poll(timeout_ms=0, max_events=10)
    assert _volume(jump) == (0.002, False, "discontinuous", "continuous")
    assert env.session.trade_id_jumps(binding) == 1
    assert env.session.counters["trade_id_jump_log_failed"] == 1


def test_the_first_tick_of_a_binding_is_continuous_with_a_baseline_even_as_a_trade(env):
    _binding, stream = _subscribe(env)
    _trade(stream, agg_id=100, qty="0.005")
    _trade(stream, agg_id=101, qty="0.002")
    first, second = env.session.poll(timeout_ms=0, max_events=10)
    assert _volume(first) == (0.0, False, "baseline", "continuous")
    assert _volume(second) == (0.002, True, "continuous", "continuous")
    assert "trade_id_jump" not in env.session.counters


def test_a_malformed_trade_still_makes_the_next_tick_a_gap(env):
    _binding, stream = _subscribe(env)
    _book(stream)
    _trade(stream, agg_id=100)
    _trade(stream, agg_id=101, qty="not-a-number")  # a lost push
    _trade(stream, agg_id=102, qty="0.002")
    _trade(stream, agg_id=103, qty="0.001")
    _quote, _baseline, after_loss, resumed = env.session.poll(timeout_ms=0, max_events=10)
    # 101 never entered the accounting, so 102 is also a jump: both facts show.
    assert _volume(after_loss) == (0.002, False, "discontinuous", "gap")
    assert _volume(resumed) == (0.001, True, "continuous", "continuous")
    assert env.session.counters["tick_frame_invalid"] == 1


def test_an_ingress_overflow_still_requires_recovery_then_starts_a_continuous_baseline(env):
    binding = env.session.subscribe(MarketStreamRequest(ROUTE, KEY, "tick", queue_capacity=1))
    stream = env.streams[0]
    _trade(stream, agg_id=100)
    _trade(stream, agg_id=101)  # does not fit: overflow
    with pytest.raises(MarketStreamProviderContractError):
        env.session.poll(timeout_ms=0, max_events=10)
    assert env.session.counters["recovery:queue_overflow"] == 1
    renewed = env.session.resync(binding, acknowledge_data_loss=True)
    _trade(stream, agg_id=150, qty="0.002")
    (event,) = env.session.poll(timeout_ms=0, max_events=10)
    assert event.source == renewed.source
    assert _volume(event) == (0.0, False, "baseline", "continuous")
    assert "trade_id_jump" not in env.session.counters  # a new epoch re-anchors: not a jump


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
    assert _volume(event) == (0.0, False, "baseline", "continuous")


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


def test_the_jump_count_is_per_binding_and_a_resync_binding_starts_at_zero(env):
    binding, stream = _subscribe(env)
    _trade(stream, agg_id=100)
    _trade(stream, agg_id=105)
    env.session.poll(timeout_ms=0, max_events=10)
    assert env.session.trade_id_jumps(binding) == 1
    _connect(stream)  # the WSS reopened: generation 2
    with pytest.raises(MarketStreamProviderContractError):
        env.session.poll(timeout_ms=0, max_events=10)
    renewed = env.session.resync(binding, acknowledge_data_loss=True)
    assert env.session.trade_id_jumps(renewed) == 0
    with pytest.raises(MarketStreamProviderContractError):
        env.session.trade_id_jumps(binding)  # the lost epoch's binding is gone
    assert env.session.counters["trade_id_jump"] == 1  # the session total is kept


def test_sdk_clock_qualification_trades_fresh_first_and_jump_ticks_but_not_after_a_loss(env):
    """The unchanged SDK rule (FRESH and continuous) now implements D62-38."""

    clock = pytest.importorskip("bt_api_py.clock_verification")
    _binding, stream = _subscribe(env)
    now_ms = time.time_ns() // 1_000_000
    _trade(stream, agg_id=100, event_ms=now_ms)
    _trade(stream, agg_id=105, event_ms=now_ms)
    _book(stream, bid="nan", event_ms=now_ms)  # a lost push
    _book(stream, event_ms=now_ms)
    first, jump, after_loss = env.session.poll(timeout_ms=0, max_events=10)
    evidence = clock.ClockEvidence(
        offset_ns=0, error_bound_ns=1_000_000, server="fake-sntp", method="fake",
        measured_monotonic_ns=0, valid_until_monotonic_ns=2**62,
    )
    check = clock.VenueClockCheck(
        consistent=True, difference_ms=0.0, tolerance_ms=50.0, source="fake"
    )
    qualified = [
        clock.qualify_market_tick_event(event, evidence, check, max_latency_seconds=60.0)
        for event in (first, jump, after_loss)
    ]
    assert all(t.data.freshness_status is MarketFreshnessStatus.FRESH for t in qualified)
    assert qualified[0].data.volume_quality == "baseline"
    assert qualified[0].data.execution_eligible is True  # the first tick trades on its price
    assert qualified[1].data.volume_complete is False
    assert qualified[1].data.execution_eligible is True  # incomplete volume is no veto
    assert qualified[2].data.continuity_status == "gap"
    assert qualified[2].data.execution_eligible is False
