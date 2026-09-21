"""Binance depth reconstruction, bridge and gap-latch contracts."""

from queue import Empty, Queue

import pytest

from bt_api_binance.feeds.market_wss_base import BinanceMarketWssData


def _feed():
    feed = object.__new__(BinanceMarketWssData)
    feed.asset_type = "SWAP"
    feed.data_queue = Queue()
    feed._depth_sequences = {}
    feed._depth_gaps = set()
    feed._depth_books = {}
    feed._depth_buffers = {}
    return feed


def _event(first, final, previous, *, bids=None, asks=None):
    return {
        "e": "depthUpdate",
        "E": 1_700_000_000_000,
        "s": "BTCUSDT",
        "U": first,
        "u": final,
        "pu": previous,
        "b": bids if bids is not None else [["60000", "1"]],
        "a": asks if asks is not None else [["60001", "1"]],
    }


def _next(feed):
    return feed.data_queue.get_nowait().init_data().get_all_data()


def test_depth_requires_snapshot_then_replays_bridge_and_zero_deletes():
    feed = _feed()
    feed.push_order_book(_event(10, 12, 9))
    stale = feed.data_queue.get_nowait()
    assert stale["stale"] is True and stale["continuity_status"] == "gap"

    assert feed.seed_depth_snapshot(
        "BTCUSDT",
        9,
        bids=[["59999", "2"]],
        asks=[["60001", "3"], ["60003", "2"]],
    )
    replayed = _next(feed)
    assert replayed["snapshot_or_delta"] == "snapshot"
    assert replayed["continuity_status"] == "snapshot"
    assert replayed["sequence_id"] == 12
    assert replayed["bid_price_list"] == [60000.0, 59999.0]

    # Binance IDs are watermarks. pu links a valid large jump.
    feed.push_order_book(
        _event(
            13,
            10_015,
            12,
            bids=[["60000", "0"], ["60002", "4"]],
            asks=[["60001", "0"]],
        )
    )
    rebuilt = _next(feed)
    assert rebuilt["sequence_id"] == 10_015
    assert rebuilt["bid_price_list"] == [60002.0, 59999.0]
    assert rebuilt["ask_price_list"] == [60003.0]


@pytest.mark.parametrize(
    ("bids", "asks"),
    [
        ([], [["101", "0"]]),  # delete the last ask
        ([["101", "1"]], []),  # lock the top of book
        ([["102", "1"]], []),  # cross the top of book
        ([["99", "-1"]], []),  # reject nonpositive update size
        ([["0", "1"]], []),  # reject nonpositive update price
    ],
)
def test_invalid_depth_transition_latches_gap_without_publishing_book(bids, asks):
    feed = _feed()
    assert feed.seed_depth_snapshot("BTCUSDT", 100, bids=[["99", "1"]], asks=[["101", "1"]])
    _next(feed)

    feed.push_order_book(_event(101, 101, 100, bids=bids, asks=asks))

    stale = feed.data_queue.get_nowait()
    assert stale["stale"] is True
    assert stale["stale_reason"] == "invalid_reconstructed_book"
    assert "BTCUSDT" in feed._depth_gaps
    assert "BTCUSDT" not in feed._depth_books
    with pytest.raises(Empty):
        feed.data_queue.get_nowait()


@pytest.mark.parametrize(
    ("bids", "asks"),
    [
        ([], [["101", "1"]]),
        ([["99", "0"]], [["101", "1"]]),
        ([["0", "1"]], [["101", "1"]]),
        ([["99", "1"], ["98", "0"]], [["101", "1"]]),
        ([["99", "-1"]], [["101", "1"]]),
        ([["102", "1"]], [["101", "1"]]),
    ],
)
def test_invalid_seed_latches_gap_without_publishing_snapshot(bids, asks):
    feed = _feed()

    assert not feed.seed_depth_snapshot("BTCUSDT", 100, bids=bids, asks=asks)

    stale = feed.data_queue.get_nowait()
    assert stale["stale"] is True
    assert stale["stale_reason"] == "invalid_orderbook_snapshot"
    assert "BTCUSDT" in feed._depth_gaps
    assert "BTCUSDT" not in feed._depth_books
    with pytest.raises(Empty):
        feed.data_queue.get_nowait()


def test_gap_latches_without_publishing_until_complete_snapshot_reseed():
    feed = _feed()
    assert feed.seed_depth_snapshot("BTCUSDT", 100, bids=[["99", "1"]], asks=[["101", "1"]])
    _next(feed)

    gap = _event(200, 250, 199)
    feed.push_order_book(gap)
    stale = feed.data_queue.get_nowait()
    assert stale["stale"] is True and stale["stale_reason"] == "sequence_gap"
    assert "BTCUSDT" in feed._depth_gaps
    assert not feed.seed_depth_snapshot("BTCUSDT", 199)
    with pytest.raises(Empty):
        feed.data_queue.get_nowait()

    assert feed.seed_depth_snapshot("BTCUSDT", 199, bids=[["59998", "1"]], asks=[["60002", "1"]])
    recovered = _next(feed)
    assert recovered["continuity_status"] == "snapshot"
    assert recovered["sequence_id"] == 250


def test_initial_diff_schedules_snapshot_and_publishes_only_validated_book():
    feed = _feed()
    calls = []
    feed._depth_snapshot_fetcher = lambda symbol: {
        "lastUpdateId": 9,
        "bids": [["59999", "2"]],
        "asks": [["60001", "3"]],
    }

    def synchronous_seed(symbol):
        calls.append(symbol)
        feed._depth_seed_inflight = {symbol}
        feed._run_depth_snapshot_fetch(symbol, feed._depth_snapshot_fetcher)

    feed._schedule_depth_snapshot = synchronous_seed
    feed.push_order_book(_event(10, 12, 9))

    assert calls == ["BTCUSDT"]
    assert feed.data_queue.get_nowait()["stale"] is True
    recovered = _next(feed)
    assert recovered["sequence_id"] == 12
    assert recovered["stale"] is False


def test_invalid_buffered_diff_during_reseed_is_not_published_or_replayed():
    feed = _feed()
    feed.push_order_book(_event(10, 12, 9, asks=[["60001", "0"]]))
    assert feed.data_queue.get_nowait()["stale"] is True

    assert not feed.seed_depth_snapshot("BTCUSDT", 9, bids=[["59999", "2"]], asks=[["60001", "3"]])

    assert "BTCUSDT" not in feed._depth_buffers
    assert "BTCUSDT" in feed._depth_gaps
    with pytest.raises(Empty):
        feed.data_queue.get_nowait()


def test_snapshot_older_than_buffer_bridge_never_publishes():
    feed = _feed()
    feed.push_order_book(_event(200, 201, 199))
    assert feed.data_queue.get_nowait()["stale"] is True
    assert not feed.seed_depth_snapshot("BTCUSDT", 50, bids=[["49", "1"]], asks=[["51", "1"]])
    with pytest.raises(Empty):
        feed.data_queue.get_nowait()


def test_sequence_above_float_precision_is_preserved_exactly():
    feed = _feed()
    sequence = 2**53 + 101
    assert feed.seed_depth_snapshot("BTCUSDT", sequence, bids=[["99", "1"]], asks=[["101", "1"]])
    assert _next(feed)["sequence_id"] == sequence
