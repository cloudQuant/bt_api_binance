"""Module documentation"""

from __future__ import annotations

import json
import threading
import time
from decimal import Decimal
from typing import Any

from bt_api_base.feeds.my_websocket_app import MyWebsocketApp, WebSocketSubscriptionError
from bt_api_base.feeds.transport_safety import sanitize_text
from bt_api_base.logging_factory import get_logger

from bt_api_binance.containers.accounts.binance_account import BinanceSwapWssAccountData
from bt_api_binance.containers.bars.binance_bar import BinanceWssBarData
from bt_api_binance.containers.fundingrates.binance_funding_rate import BinanceWssFundingRateData
from bt_api_binance.containers.markprices.binance_mark_price import BinanceWssMarkPriceData
from bt_api_binance.containers.orderbooks.binance_orderbook import BinanceWssOrderBookData
from bt_api_binance.containers.orders.binance_order import (
    BinanceForceOrderData,
    BinanceSwapWssOrderData,
)
from bt_api_binance.containers.positions.binance_position import BinanceWssPositionData
from bt_api_binance.containers.tickers.binance_ticker import BinanceWssTickerData
from bt_api_binance.containers.trades.binance_trade import (
    BinanceAggTradeData,
    BinanceSwapWssTradeData,
)
from bt_api_binance.environment import configure_environment
from bt_api_binance.exchange_data import BinanceExchangeDataSwap

from .request_base import BinanceRequestData


class BinanceMarketWssData(MyWebsocketApp, BinanceRequestData):
    """Binance market WebSocket data handler."""

    count = 0

    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """Initialize Binance market WebSocket data handler.

        Args: data_queue: Queue for storing data.
            **kwargs: Additional keyword arguments including:
                - topics: Topics to subscribe (default: {})
                - public_key: API public key
                - private_key: API private key
                - wss_url: WebSocket URL (must be provided)
                - asset_type: Asset type (default: "SWAP")
                - listen_key: Listen key for WebSocket
                - proxies: Proxy settings
                - async_proxy: Async proxy settings
                - exchange_name: Exchange name (default: "BINANCE")

        """
        params = configure_environment(
            kwargs.get("exchange_data") or BinanceExchangeDataSwap(), kwargs
        )
        kwargs["exchange_data"] = params
        kwargs.setdefault("wss_url", params.wss_url)
        super().__init__(data_queue, **kwargs)
        # Explicitly init BinanceRequestData/Feed chain to create _http_client
        # (MyWebsocketApp.__init__ does not call super().__init__, so MRO chain stops)
        BinanceRequestData.__init__(self, data_queue, **kwargs)
        self.topics = kwargs.get("topics", {})
        self.wss_url = kwargs.get("wss_url")  #
        self.asset_type = kwargs.get("asset_type", "SWAP")
        self.listen_key = kwargs.get("listen_key")
        self.proxies = kwargs.get("proxies")
        self.async_proxy = kwargs.get("async_proxy")
        self.exchange_name = kwargs.get("exchange_name", "BINANCE")
        self.logger = get_logger("binance_market_wss")
        self._next_subscription_id = 0
        self._pending_subscription_ids: set[int] = set()
        self._depth_sequences: dict[str, int] = {}
        self._depth_gaps: set[str] = set()
        self._depth_books: dict[str, dict[str, Any]] = {}
        self._depth_buffers: dict[str, list[dict[str, Any]]] = {}
        self._depth_lock = threading.RLock()
        self._depth_seed_inflight: set[str] = set()
        self._depth_stale_emitted: set[str] = set()
        self._depth_snapshot_fetcher = self._fetch_depth_snapshot
        # ping = threading.Thread(target=self.ping)
        # ping.start()
        # self.logger.info("")

    def subscribe(self, **kwargs):
        """Send one subscription with a unique id used to correlate its ACK."""
        with self._subscription_lock:
            self._next_subscription_id += 1
            request_id = self._next_subscription_id
            self._pending_subscription_ids.add(request_id)
        try:
            return super().subscribe(_request_id=request_id, **kwargs)
        except Exception:
            with self._subscription_lock:
                self._pending_subscription_ids.discard(request_id)
            raise

    def open_rsp(self) -> bool:
        """Handle WebSocket connection open event."""
        if not self.topics:
            raise WebSocketSubscriptionError("Binance market WebSocket requires at least one topic")
        self.wss_logger.info(
            f"===== {time.strftime('%Y-%m-%d %H:%M:%S')} {self._params.exchange_name} "
            f"Websocket Connected ====="
        )
        with self._subscription_lock:
            self._pending_subscription_ids.clear()
        with self._depth_lock:
            self._depth_sequences.clear()
            self._depth_gaps.clear()
            self._depth_books.clear()
            self._depth_buffers.clear()
            self._depth_seed_inflight.clear()
            self._depth_stale_emitted.clear()
        self._begin_subscription_batch()
        self._init()
        return self._end_subscription_batch()

    def _init(self):
        for topics in self.topics:
            sent_before = self._subscription_batch_send_count
            # time.sleep(0.2)
            self.count += 1
            if topics["topic"] == "ticker":
                symbol = topics.get("symbol", "BTC-USDT")
                self.subscribe(topic="ticker", symbol=symbol)
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, {symbol}, ticker"
                )

            if topics["topic"] == "book_ticker":
                symbol = topics.get("symbol", "BTC-USDT")
                self.subscribe(topic="book_ticker", symbol=symbol)
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, {symbol}, book_ticker"
                )

            if topics["topic"] == "depth":
                # self.logger.info(topics)
                if "symbol" in topics:
                    symbol = topics.get("symbol")
                    self.subscribe(topic="depth", symbol=symbol, type="step0")
                    self.logger.info(
                        f"subscribe {self.count} data, BINANCE, {self.asset_type}, {symbol}, depth"
                    )
                elif "symbol_list" in topics:
                    symbol_list = topics.get("symbol_list")
                    self.subscribe(topic="depth", symbol_list=symbol_list, type="step0")
                    self.logger.info(
                        f"subscribe {self.count} data, BINANCE, {self.asset_type}, depth, symbol_list"
                    )
                else:
                    self.logger.info("depth need symbol to subscribe")

            if topics["topic"] == "funding_rate":
                symbol = topics.get("symbol", "BTC—USDT")
                self.subscribe(topic="funding_rate", symbol=symbol)
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, {symbol}, funding_rate"
                )

            if topics["topic"] == "mark_price":
                symbol = topics.get("symbol", "BTC—USDT")
                self.subscribe(topic="mark_price", symbol=symbol)
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, {symbol}, mark_price"
                )

            if topics["topic"] == "kline":
                period = topics.get("period", "1m")
                symbol = topics.get("symbol", "BTC—USDT")
                self.subscribe(topic="kline", symbol=symbol, period=period)
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, {symbol}, kline"
                )

            if topics["topic"] == "all_mark_price":
                self.subscribe(topic="all_mark_price")
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, all_mark_price"
                )

            if topics["topic"] == "all_ticker":
                self.subscribe(topic="all_ticker")
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type},all_ticker"
                )

            if topics["topic"] == "all_force_order":
                self.subscribe(topic="all_force_order")
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, all_force_order"
                )

            if topics["topic"] == "agg_trade":
                if "symbol" in topics:
                    symbol = topics.get("symbol")
                    self.subscribe(topic="agg_trade", symbol=symbol)
                    self.logger.info(
                        f"subscribe {self.count} data, BINANCE, {self.asset_type}, {symbol}, agg_trade"
                    )
                if "symbol_list" in topics:
                    symbol_list = topics.get("symbol_list")
                    self.subscribe(topic="agg_trade", symbol_list=symbol_list)
                    self.logger.info(
                        f"subscribe {self.count} data, BINANCE, {self.asset_type}, agg_trade, symbol_list"
                    )

            if topics["topic"] == "force_order":
                symbol = topics.get("symbol", "BTC—USDT")
                self.subscribe(topic="force_order", symbol=symbol)
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, {symbol}, force_order"
                )

            if topics["topic"] == "liquidation":
                symbol = topics.get("symbol", "BTC—USDT")
                self.subscribe(topic="liquidation", symbol=symbol)
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, {symbol}, liquidation"
                )

            if topics["topic"] == "mini_ticker":
                symbol = topics.get("symbol", "BTC—USDT")
                self.subscribe(topic="mini_ticker", symbol=symbol)
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, {symbol}, mini_ticker"
                )

            if topics["topic"] == "all_mini_ticker":
                self.subscribe(topic="all_mini_ticker")
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, all_mini_ticker"
                )

            if topics["topic"] == "all_book_ticker":
                self.subscribe(topic="all_book_ticker")
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, all_book_ticker"
                )

            if topics["topic"] == "continuous_kline":
                period = topics.get("period", "1m")
                pair = topics.get("pair", topics.get("symbol", "BTC—USDT"))
                self.subscribe(topic="continuous_kline", pair=pair, period=period)
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, {pair}, continuous_kline"
                )

            if topics["topic"] == "contract_info":
                self.subscribe(topic="contract_info")
                self.logger.info(
                    f"subscribe {self.count} data, BINANCE, {self.asset_type}, contract_info"
                )

            if self._subscription_batch_send_count == sent_before:
                raise WebSocketSubscriptionError(
                    "Unsupported or incomplete Binance WebSocket topic"
                )

    # def handle_all_data(self, content):
    #     if isinstance(content, list):
    #         for c in content:
    #             self.handle_all_data(c)
    #     elif isinstance(content, dict):
    #         self.handle_data(content)

    def handle_data(self, content: dict[str, Any]) -> None:
        """Handle incoming WebSocket data.

        Args: content: Dictionary containing WebSocket message data.

        """
        # self.logger.info(content)
        event = content.get("e")
        if event is not None:
            if event == "bookTicker":
                self.push_ticker(content)
            if event == "depthUpdate":
                self.push_order_book(content)
            if event == "kline":
                self.push_bar(content)
                # self.logger.info(content)
            if event == "markPriceUpdate":
                self.push_funding_rate(content)
            if event == "markPriceUpdate":
                self.push_mark_price(content)
            if event == "ACCOUNT_UPDATE":
                self.push_account(content)
            if event == "aggTrade":
                self.push_agg_trade(content)
            if event == "forceOrder":
                self.push_force_order(content)
            if event == "24hrTicker":
                self.push_ticker(content)
            if event == "24hrMiniTicker":
                self.push_ticker(content)
            if event == "continuous_kline":
                self.push_continuous_kline(content)
            # if "bookTicker" == event:
            #     self.push_order(content)
            # if "bookTicker" == event and content['data'][0].get("tradeId") != "":
            #     self.push_trade(content)
            # # if "trade" in arg["channel"]:
            # #     self.push_trade(content)
            # if "bookTicker" == event:
            #     self.push_position(content)

    def push_continuous_kline(self, content: dict[str, Any]) -> None:
        """Push continuous kline data to queue.

        Args: content: Dictionary containing continuous kline data.

        """
        symbol = content.get("ps", content.get("s", "UNKNOWN"))
        # Add 's' key for compatibility with BinanceWssBarData
        if "s" not in content:
            content["s"] = symbol
        bar_data = BinanceWssBarData(content, symbol, self.asset_type, True)
        bar_data.init_data()
        self.data_queue.put(bar_data)

    def push_force_order(self, content: dict[str, Any]) -> None:
        """Push force order data to queue.

        Args: content: Dictionary containing force order data.

        """
        # self.logger.info("force_order: ", content)
        symbol = content["o"]["s"]
        force_order_data = BinanceForceOrderData(content, symbol, self.asset_type, True)
        self.data_queue.put(force_order_data)

    def push_agg_trade(self, content: dict[str, Any]) -> None:
        """Push aggregate trade data to queue.

        Args: content: Dictionary containing aggregate trade data.

        """
        symbol = content["s"]
        agg_trade_data = BinanceAggTradeData(content, symbol, self.asset_type, True)
        self.data_queue.put(agg_trade_data)

    def push_mark_price(self, content: dict[str, Any]) -> None:
        """Push mark price data to queue.

        Args: content: Dictionary containing mark price data.

        """
        symbol = content["s"]
        mark_price_data = BinanceWssMarkPriceData(content, symbol, self.asset_type, True)
        self.data_queue.put(mark_price_data)
        # self.logger.info("mark_price, mark_price is ", mark_price_data.get_mark_price())

    def push_funding_rate(self, content: dict[str, Any]) -> None:
        """Push funding rate data to queue.

        Args: content: Dictionary containing funding rate data.

        """
        #
        symbol = content["s"]
        funding_rate_data = BinanceWssFundingRateData(content, symbol, self.asset_type, True)
        self.data_queue.put(funding_rate_data)
        # self.logger.info("funding_rate，funding_rate = ",
        #                  funding_rate_data.get_current_funding_rate())

    def push_ticker(self, content: dict[str, Any]) -> None:
        """Push ticker data to queue.

        Args: content: Dictionary containing ticker data.

        """
        # ticker
        symbol = content["s"]
        ticker_data = BinanceWssTickerData(content, symbol, self.asset_type, True)
        self.data_queue.put(ticker_data)
        # self.logger.info("ticker，ticker ask_price = ", ticker_data.get_ask_price())

    def push_order_book(self, content: dict[str, Any]) -> None:
        """Buffer/apply a diff and publish only a fully reconstructed book."""
        symbol = content["s"]
        payload = dict(content)
        sequence = payload.get("u")
        first_sequence = payload.get("U")
        native_previous = payload.get("pu")
        schedule_snapshot = False
        lock = self._get_depth_lock()
        with lock:
            buffers = getattr(self, "_depth_buffers", None)
            if buffers is None:
                buffers = self._depth_buffers = {}
            books = getattr(self, "_depth_books", None)
            if books is None:
                books = self._depth_books = {}
            if sequence is None or first_sequence is None:
                schedule_snapshot = self._latch_depth_gap(symbol, payload, "missing_sequence")
            elif symbol in self._depth_gaps or symbol not in books:
                buffered = buffers.setdefault(symbol, [])
                buffered.append(payload)
                if len(buffered) > 1000:
                    del buffered[:-1000]
                    reason = "depth_buffer_overflow"
                else:
                    reason = "snapshot_required"
                schedule_snapshot = self._latch_depth_gap(symbol, payload, reason)
            elif not self._apply_depth_diff(symbol, payload, native_previous=native_previous):
                buffered = buffers.setdefault(symbol, [])
                buffered.append(payload)
                if len(buffered) > 1000:
                    del buffered[:-1000]
                schedule_snapshot = self._latch_depth_gap(symbol, payload, "sequence_gap")
        if schedule_snapshot:
            self._schedule_depth_snapshot(symbol)

    def _get_depth_lock(self):
        lock = getattr(self, "_depth_lock", None)
        if lock is None:
            lock = self._depth_lock = threading.RLock()
        return lock

    def _latch_depth_gap(self, symbol, payload, reason):
        self._depth_gaps.add(symbol)
        self._depth_books.pop(symbol, None)
        emitted = getattr(self, "_depth_stale_emitted", None)
        if emitted is None:
            emitted = self._depth_stale_emitted = set()
        first_notice = symbol not in emitted
        if first_notice:
            emitted.add(symbol)
            self.data_queue.put(
                {
                    "kind": "orderbook",
                    "exchange_name": getattr(self, "exchange_name", "BINANCE"),
                    "asset_type": self.asset_type,
                    "symbol": symbol,
                    "bids": [],
                    "asks": [],
                    "sequence": payload.get("u"),
                    "previous_sequence": payload.get("pu"),
                    "snapshot_or_delta": "delta",
                    "continuity_status": "gap",
                    "stale": True,
                    "stale_reason": reason,
                    "event_id": f"binance-depth-gap:{symbol}:{payload.get('u', '')}",
                }
            )
        return True

    def _fetch_depth_snapshot(self, symbol):
        result = self.get_depth(symbol, count=1000)
        if hasattr(result, "get_input_data"):
            result = result.get_input_data()
        if isinstance(result, str):
            result = json.loads(result)
        if not isinstance(result, dict):
            raise ValueError("Binance depth snapshot must be a mapping")
        return result

    def _schedule_depth_snapshot(self, symbol):
        fetcher = getattr(self, "_depth_snapshot_fetcher", None)
        if not callable(fetcher):
            return
        lock = self._get_depth_lock()
        with lock:
            inflight = getattr(self, "_depth_seed_inflight", None)
            if inflight is None:
                inflight = self._depth_seed_inflight = set()
            if symbol in inflight:
                return
            inflight.add(symbol)
        threading.Thread(
            target=self._run_depth_snapshot_fetch,
            args=(symbol, fetcher),
            daemon=True,
            name=f"binance-depth-seed-{symbol}",
        ).start()

    def _run_depth_snapshot_fetch(self, symbol, fetcher):
        try:
            snapshot = fetcher(symbol)
            self.seed_depth_snapshot(
                symbol,
                int(snapshot["lastUpdateId"]),
                bids=snapshot.get("bids"),
                asks=snapshot.get("asks"),
            )
        except Exception as error:
            self.wss_logger.warning("Binance depth reseed failed: %s", self._safe_failure(error))
        finally:
            with self._get_depth_lock():
                self._depth_seed_inflight.discard(symbol)

    @staticmethod
    def _update_depth_side(side, levels):
        for level in levels or ():
            if len(level) < 2:
                continue
            price, quantity = str(level[0]), str(level[1])
            if Decimal(quantity) == 0:
                side.pop(price, None)
            else:
                side[price] = quantity

    @staticmethod
    def _sorted_depth_side(side, *, reverse):
        return [[price, side[price]] for price in sorted(side, key=Decimal, reverse=reverse)]

    def _publish_depth_book(self, symbol, source, continuity):
        state = self._depth_books[symbol]
        payload = {
            **source,
            "s": symbol,
            "U": source.get("U", state["last_update_id"]),
            "u": state["last_update_id"],
            "pu": source.get("pu"),
            "b": self._sorted_depth_side(state["bids"], reverse=True),
            "a": self._sorted_depth_side(state["asks"], reverse=False),
            "snapshot_or_delta": "snapshot",
            "continuity_status": continuity,
            "stale": False,
            "stale_reason": None,
        }
        self.data_queue.put(BinanceWssOrderBookData(payload, symbol, self.asset_type, True))

    def _apply_depth_diff(self, symbol, payload, *, native_previous=None, bridge=False):
        state = self._depth_books[symbol]
        previous = state["last_update_id"]
        first_sequence = int(payload["U"])
        sequence = int(payload["u"])
        if sequence <= previous:
            return True
        linked = (
            int(native_previous) == previous
            if native_previous is not None
            else first_sequence <= previous + 1 <= sequence
        )
        if bridge and native_previous is not None:
            linked = int(native_previous) == previous or first_sequence <= previous + 1 <= sequence
        if not linked:
            self._depth_gaps.add(symbol)
            self._depth_books.pop(symbol, None)
            return False
        self._update_depth_side(state["bids"], payload.get("b"))
        self._update_depth_side(state["asks"], payload.get("a"))
        state["last_update_id"] = sequence
        self._depth_sequences[symbol] = sequence
        self._publish_depth_book(symbol, payload, "continuous")
        return True

    def seed_depth_snapshot(
        self,
        symbol: str,
        last_update_id: int,
        bids=None,
        asks=None,
        *,
        publish=True,
    ) -> bool:
        """Install a complete REST snapshot and replay buffered Binance diffs."""
        if bids is None or asks is None:
            with self._get_depth_lock():
                self._latch_depth_gap(symbol, {}, "incomplete_snapshot")
            return False
        with self._get_depth_lock():
            buffers = getattr(self, "_depth_buffers", None)
            if buffers is None:
                buffers = self._depth_buffers = {}
            buffered = list(buffers.get(symbol, ()))
            state = {"bids": {}, "asks": {}, "last_update_id": int(last_update_id)}
            self._update_depth_side(state["bids"], bids)
            self._update_depth_side(state["asks"], asks)
            applied = []
            for payload in buffered:
                sequence = int(payload.get("u", -1))
                if sequence <= state["last_update_id"]:
                    continue
                previous = state["last_update_id"]
                first_sequence = int(payload["U"])
                native_previous = payload.get("pu")
                linked = (
                    int(native_previous) == previous
                    if native_previous is not None
                    else first_sequence <= previous + 1 <= sequence
                )
                if not applied and native_previous is not None:
                    linked = linked or first_sequence <= previous + 1 <= sequence
                if not linked:
                    self._latch_depth_gap(symbol, payload, "snapshot_bridge_gap")
                    return False
                self._update_depth_side(state["bids"], payload.get("b"))
                self._update_depth_side(state["asks"], payload.get("a"))
                state["last_update_id"] = sequence
                applied.append(payload)
            books = getattr(self, "_depth_books", None)
            if books is None:
                books = self._depth_books = {}
            books[symbol] = state
            self._depth_sequences[symbol] = state["last_update_id"]
            self._depth_gaps.discard(symbol)
            getattr(self, "_depth_stale_emitted", set()).discard(symbol)
            buffers.pop(symbol, None)
            source = (
                applied[-1]
                if applied
                else {
                    "e": "depthSnapshot",
                    "s": symbol,
                    "U": int(last_update_id),
                    "u": int(last_update_id),
                    "b": bids,
                    "a": asks,
                }
            )
            if publish:
                self._publish_depth_book(symbol, source, "snapshot")
            return True

    def push_bar(self, content: dict[str, Any]) -> None:
        """Push bar/kline data to queue.

        Args: content: Dictionary containing bar/kline data.

        """
        # bar
        symbol = content["s"]
        bar_data = BinanceWssBarData(content, symbol, self.asset_type, True)
        bar_data.init_data()
        bar_data.get_bar_status()
        # if bar_status:
        #     self.data_queue.put(bar_data)
        self.data_queue.put(bar_data)
        # all_data = bar_data.get_all_data()
        # timestamp = all_data["open_time"]
        # # dtime_utc = datetime.fromtimestamp(timestamp // 1000, tz=UTC)
        # #  UTC （ UTC ）
        # dtime_utc = datetime.fromtimestamp(timestamp // 1000, tz=pytz.UTC)
        # if bar_status:
        #     self.logger.info(f"binance {dtime_utc} kline,"
        #           f"close_price = {bar_data.get_close_price()},"
        #           f"bar_status = {bar_status}")

    def push_account(self, content: dict[str, Any]) -> None:
        """Push account data to queue.

        Args: content: Dictionary containing account data.

        """
        # account
        account_info = content["data"][0]
        symbol = "ANY"
        account_data = BinanceSwapWssAccountData(account_info, symbol, self.asset_type, True)
        self.data_queue.put(account_data)
        # self.logger.info("account，：", account_data.get_total_margin())

    def push_order(self, content: dict[str, Any]) -> None:
        """Push order data to queue.

        Args: content: Dictionary containing order data.

        """
        # self.logger.info("order")
        order_info = content["data"][0]
        symbol = content["arg"]["symbol"]
        order_data = BinanceSwapWssOrderData(order_info, symbol, self.asset_type, True)
        self.data_queue.put(order_data)
        # self.logger.info("order，order_status ：", order_data.get_order_status())

    def push_trade(self, content: dict[str, Any]) -> None:
        """Push trade data to queue.

        Args: content: Dictionary containing trade data.

        """
        trade_info = content["data"][0]
        symbol = content["arg"]["symbol"]
        trade_data = BinanceSwapWssTradeData(trade_info, symbol, self.asset_type, True)
        self.data_queue.put(trade_data)
        # self.logger.info("trade，trade_id ：", trade_data.get_trade_id())

    def push_position(self, content: dict[str, Any]) -> None:
        """Push position data to queue.

        Args: content: Dictionary containing position data.

        """
        data = content["data"]
        if len(data) > 0:
            position_info = data[0]
            symbol = content["arg"]["symbol"]
            position_data = BinanceWssPositionData(position_info, symbol, self.asset_type, True)
            self.data_queue.put(position_data)
            # self.logger.info("position，：",
            #                  position_data.get_position_symbol_name(),
            #                  position_data.get_position_qty())

    def message_rsp(self, message: str) -> None:
        """Handle incoming WebSocket message.

        Args: message: Raw WebSocket message string.

        """
        rsp = json.loads(message)
        if isinstance(rsp, dict):
            if "code" in rsp and "msg" in rsp:
                code = sanitize_text(rsp.get("code", "unknown"))
                raise WebSocketSubscriptionError(
                    f"Binance websocket subscription rejected (code={code})",
                    code=code,
                )
            if "result" in rsp:
                request_id = rsp.get("id")
                with self._subscription_lock:
                    expected = request_id in self._pending_subscription_ids
                    if expected and rsp.get("result") is None:
                        self._pending_subscription_ids.remove(request_id)
                if not expected:
                    self._emit_event("ws.subscription_ack_ignored", request_id=request_id)
                    return
                if rsp.get("result") is not None:
                    raise WebSocketSubscriptionError(
                        "Unexpected Binance websocket subscription response"
                    )
                self.wss_logger.info(
                    f"===== {self._params.exchange_name} Data Websocket Connected ====="
                )
                self._subscription_acknowledged()
            elif "e" in rsp:
                self.handle_data(rsp)
                return
        elif isinstance(rsp, list):
            for data in rsp:
                self.handle_data(data)
