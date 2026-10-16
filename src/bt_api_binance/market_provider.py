"""Read-only Binance USDⓈ-M Demo ticker adapter for the Gateway Market Hub."""

from __future__ import annotations

import math
import re
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from bt_api_base.market_protocol import MarketProviderEvent, MarketSubscriptionKey

from bt_api_binance.containers.tickers.binance_ticker import BinanceWssTickerData
from bt_api_binance.environment import configure_environment
from bt_api_binance.exchange_data import BinanceExchangeData, BinanceExchangeDataSwap
from bt_api_binance.feeds.market_wss_base import BinanceMarketWssData

DEFAULT_BINANCE_TICKER_QUEUE_CAPACITY = 1_024
MAX_BINANCE_TICKER_QUEUE_CAPACITY = 65_536
MAX_BINANCE_PROVIDER_POLL_LIMIT = 256

_SOURCE_REF = "binance-usdm-demo-market-r1"
_ENTITLEMENT_REF = "public-ticker-r1"
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{3,40}$")
_DEMO_WS_HOST = "demo-fstream.binance.com"


class BoundedBinanceTickerQueue:
    """Thread-safe nonblocking sink compatible with Binance feed ``put`` calls."""

    def __init__(self, capacity: int = DEFAULT_BINANCE_TICKER_QUEUE_CAPACITY) -> None:
        if type(capacity) is not int or not 1 <= capacity <= MAX_BINANCE_TICKER_QUEUE_CAPACITY:
            raise ValueError("INVALID_BINANCE_TICKER_QUEUE_CAPACITY")
        self._capacity = capacity
        self._items: deque[object] = deque()
        self._lock = threading.Lock()
        self._dropped_oldest = 0

    @property
    def dropped_oldest(self) -> int:
        with self._lock:
            return self._dropped_oldest

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def put(self, item: object, block: bool = True, timeout: float | None = None) -> None:
        del block, timeout
        with self._lock:
            if len(self._items) == self._capacity:
                self._items.popleft()
                self._dropped_oldest += 1
            self._items.append(item)

    def drain(self, limit: int) -> tuple[object, ...]:
        if type(limit) is not int or not 1 <= limit <= MAX_BINANCE_PROVIDER_POLL_LIMIT:
            raise ValueError("INVALID_BINANCE_PROVIDER_POLL_LIMIT")
        with self._lock:
            count = min(limit, len(self._items))
            return tuple(self._items.popleft() for _ in range(count))

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


@dataclass
class BinanceUsdMDemoTickerHandle:
    """One started existing Binance market feed and its Hub generation."""

    key: MarketSubscriptionKey
    generation: str
    queue: BoundedBinanceTickerQueue
    stream: object
    active: bool = True


def _demo_market_stream_url(wss_url: str) -> str:
    """Use Binance's routed regular-market endpoint on the explicit Demo host."""
    parsed = urlsplit(wss_url)
    if (
        parsed.scheme != "wss"
        or parsed.hostname != _DEMO_WS_HOST
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != "/ws"
    ):
        raise ValueError("UNVERIFIED_BINANCE_USDM_DEMO_ENDPOINT")
    return urlunsplit(("wss", parsed.netloc, "/market/ws", "", ""))


def _build_default_demo_stream(
    key: MarketSubscriptionKey, ticker_queue: BoundedBinanceTickerQueue
) -> object:
    """Construct the existing feed against the current USDⓈ-M Demo market route."""
    _validate_supported_key(key)
    # The normal exchange-data constructor reads the user's exchange YAML.
    # Public market data needs neither that file nor credential material, so
    # initialize only the public ticker subscription template on a blank object.
    params = BinanceExchangeDataSwap.__new__(BinanceExchangeDataSwap)
    BinanceExchangeData.__init__(params)
    params.wss_paths = {
        "ticker": {"params": ["<symbol>@ticker"], "method": "SUBSCRIBE", "id": 1}
    }
    params = configure_environment(params, {"environment": "demo"})
    stream = BinanceMarketWssData(
        ticker_queue,
        exchange_data=params,
        environment="demo",
        wss_url=params.wss_url,
        topics=[{"topic": "ticker", "symbol": key.instrument.native_symbol}],
        asset_type="SWAP",
        wss_name="service_binance_usdm_demo_ticker",
    )
    # The legacy feed constructor still validates /ws. Point only the actual
    # market transport at the routed URL; leave its verified Demo base params
    # intact so no account/private endpoint is rewritten.
    routed_url = _demo_market_stream_url(params.wss_url)
    stream.wss_url = routed_url
    return stream


class BinanceUsdMDemoMarketProvider:
    """Adapt the existing Binance USDⓈ-M SWAP ticker feed to the Gateway port.

    This provider is restricted to one explicitly keyed USDⓈ-M Demo product
    family and public ticker events. It does not load credentials, issue REST
    requests, or expose account or order operations. The optional stream
    factory is trusted test/deployment wiring and must not start its stream.
    """

    def __init__(
        self,
        *,
        stream_factory: Callable[[MarketSubscriptionKey, BoundedBinanceTickerQueue], object]
        | None = None,
        queue_capacity: int = DEFAULT_BINANCE_TICKER_QUEUE_CAPACITY,
        connect_timeout: float = 30.0,
    ) -> None:
        if type(queue_capacity) is not int or not 1 <= queue_capacity <= MAX_BINANCE_TICKER_QUEUE_CAPACITY:
            raise ValueError("INVALID_BINANCE_TICKER_QUEUE_CAPACITY")
        if isinstance(connect_timeout, bool) or not isinstance(connect_timeout, (int, float)):
            raise ValueError("INVALID_BINANCE_CONNECT_TIMEOUT")
        normalized_timeout = float(connect_timeout)
        if not math.isfinite(normalized_timeout) or normalized_timeout < 0:
            raise ValueError("INVALID_BINANCE_CONNECT_TIMEOUT")
        if stream_factory is not None and not callable(stream_factory):
            raise ValueError("INVALID_BINANCE_STREAM_FACTORY")
        self._stream_factory = stream_factory or _build_default_demo_stream
        self._queue_capacity = queue_capacity
        self._connect_timeout = normalized_timeout
        self._pending_start_cleanup: list[object] = []
        self._handles: list[BinanceUsdMDemoTickerHandle] = []
        self._invalid_ticker_events = 0

    @property
    def diagnostics(self) -> dict[str, int]:
        return {
            "active_handles": sum(handle.active for handle in self._handles),
            "pending_start_cleanup": len(self._pending_start_cleanup),
            "invalid_ticker_events": self._invalid_ticker_events,
        }

    def subscribe(
        self, key: MarketSubscriptionKey, *, generation: str
    ) -> BinanceUsdMDemoTickerHandle:
        _validate_supported_key(key)
        if type(generation) is not str or not generation.strip():
            raise ValueError("INVALID_SOURCE_GENERATION")
        self._retry_pending_start_cleanup()
        ticker_queue = BoundedBinanceTickerQueue(self._queue_capacity)
        stream = self._stream_factory(key, ticker_queue)
        start = getattr(stream, "start", None)
        stop = getattr(stream, "stop", None)
        if not callable(start) or not callable(stop):
            raise TypeError("Binance stream factory must return a startable and stoppable stream")
        try:
            start(connect_timeout=self._connect_timeout)
        except BaseException:
            try:
                stopped = stop()
            except BaseException:
                stopped = False
            if stopped is False:
                self._pending_start_cleanup.append(stream)
            raise
        handle = BinanceUsdMDemoTickerHandle(key, generation, ticker_queue, stream)
        self._handles.append(handle)
        return handle

    def unsubscribe(self, handle: object) -> bool:
        if type(handle) is not BinanceUsdMDemoTickerHandle:
            return False
        if not handle.active:
            return True
        try:
            stopped = handle.stream.stop()
        except Exception:
            return False
        if stopped is False:
            return False
        handle.active = False
        handle.queue.clear()
        self._handles.remove(handle)
        return True

    def poll(self, handle: object, *, limit: int) -> tuple[MarketProviderEvent, ...]:
        if type(handle) is not BinanceUsdMDemoTickerHandle or not handle.active:
            return ()
        raw_items = handle.queue.drain(limit)
        events = []
        for raw_item in raw_items:
            if type(raw_item) is not BinanceWssTickerData:
                self._invalid_ticker_events += 1
                raise ValueError("INVALID_BINANCE_TICKER_EVENT")
            projection, observed_at_utc = _project_ticker(raw_item, handle.key)
            events.append(
                MarketProviderEvent(
                    generation=handle.generation,
                    observed_at_utc=observed_at_utc,
                    data=projection,
                )
            )
        return tuple(events)

    def close(self) -> bool:
        """Close known streams and retry only their exact retained handles."""
        all_closed = True
        for handle in tuple(self._handles):
            if handle.active and not self.unsubscribe(handle):
                all_closed = False
        self._retry_pending_start_cleanup()
        return all_closed and not any(handle.active for handle in self._handles)

    def _retry_pending_start_cleanup(self) -> None:
        pending: list[object] = []
        for stream in self._pending_start_cleanup:
            try:
                stopped = stream.stop()
            except Exception:
                stopped = False
            if stopped is False:
                pending.append(stream)
        self._pending_start_cleanup = pending
        if pending:
            raise RuntimeError("BINANCE_STARTUP_CLEANUP_PENDING")


def _validate_supported_key(key: MarketSubscriptionKey) -> None:
    if type(key) is not MarketSubscriptionKey:
        raise TypeError("INVALID_BINANCE_MARKET_KEY")
    instrument = key.instrument
    if (
        key.source_ref != _SOURCE_REF
        or key.entitlement_ref != _ENTITLEMENT_REF
        or instrument.provider != "binance"
        or instrument.venue != "BINANCE"
        or instrument.environment != "demo"
        or instrument.product_type != "USDM_PERPETUAL"
        or instrument.instrument_id != instrument.native_symbol
        or _SYMBOL_PATTERN.fullmatch(instrument.native_symbol) is None
        or key.channel != "tickers"
        or key.depth is not None
        or key.timeframe is not None
    ):
        raise ValueError("UNSUPPORTED_BINANCE_USDM_DEMO_MARKET_KEY")


def _project_ticker(
    ticker: BinanceWssTickerData, key: MarketSubscriptionKey
) -> tuple[dict[str, object], str]:
    ticker.init_data()
    raw = ticker.get_all_data()
    if (
        raw.get("exchange_name") != "BINANCE"
        or raw.get("asset_type") != "SWAP"
        or raw.get("symbol_name") != key.instrument.native_symbol
        or raw.get("ticker_symbol_name") != key.instrument.native_symbol
    ):
        raise ValueError("BINANCE_TICKER_KEY_MISMATCH")
    timestamp = raw.get("server_time")
    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, (int, float))
        or not math.isfinite(float(timestamp))
    ):
        raise ValueError("INVALID_BINANCE_TICKER_TIMESTAMP")
    timestamp_seconds = float(timestamp) / 1_000.0
    try:
        observed_at_utc = (
            datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    except (OverflowError, OSError, ValueError):
        raise ValueError("INVALID_BINANCE_TICKER_TIMESTAMP") from None

    field_names = {
        "last_price": "last_price",
        "bid_price": "bid_price",
        "ask_price": "ask_price",
        "bid_volume": "bid_volume",
        "ask_volume": "ask_volume",
        "volume": "volume_24h",
        "turnover": "turnover_24h",
        "open": "open_price",
        "high": "high_price",
        "low": "low_price",
    }
    values: dict[str, float] = {}
    for output_name, source_name in field_names.items():
        value = raw.get(source_name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0
        ):
            raise ValueError("INVALID_BINANCE_TICKER_VALUE")
        values[output_name] = float(value)
    projection: dict[str, object] = {
        "exchange_name": "BINANCE",
        "symbol": key.instrument.native_symbol,
        "instrument_id": key.instrument.instrument_id,
        "asset_type": "SWAP",
        "product_type": "USDM_PERPETUAL",
        "environment": "demo",
        "timestamp": timestamp_seconds,
        **values,
    }
    return projection, observed_at_utc


__all__ = [
    "BinanceUsdMDemoMarketProvider",
    "BinanceUsdMDemoTickerHandle",
    "BoundedBinanceTickerQueue",
]
