"""Module documentation"""

from __future__ import annotations

import json
import math
import threading
import time
from typing import Any

from bt_api_base.feeds.my_websocket_app import MyWebsocketApp
from bt_api_base.feeds.transport_safety import sanitize_text, sanitize_value
from bt_api_base.logging_factory import get_logger

from bt_api_binance.containers.accounts.binance_account import BinanceSwapWssAccountData
from bt_api_binance.containers.orders.binance_order import BinanceSwapWssOrderData
from bt_api_binance.containers.trades.binance_trade import BinanceSwapWssTradeData
from bt_api_binance.environment import configure_environment
from bt_api_binance.exchange_data import BinanceExchangeDataSwap

from .request_base import BinanceRequestData, strict_credential_alias


class BinanceAccountWssData(MyWebsocketApp, BinanceRequestData):
    """Class BinanceAccountWssData"""

    def __init__(self, data_queue: Any, **kwargs: Any) -> None:
        """Initialize Binance account WebSocket data handler.

        Args: data_queue: Queue for storing data.
            **kwargs: Additional keyword arguments including:
                - topics: Topics to subscribe (default: {})
                - public_key: API public key
                - private_key: API private key
                - wss_url: WebSocket URL (must be provided)
                - asset_type: Asset type (default: "SWAP")
                - exchange_name: Exchange name (default: "BINANCE")
                - symbol_name: Symbol name
                - listen_key: Listen key for WebSocket
                - proxies: Proxy settings
                - async_proxy: Async proxy settings

        """
        key = strict_credential_alias(kwargs, ("public_key", "api_key"))
        secret = strict_credential_alias(kwargs, ("private_key", "secret_key", "api_secret"))
        if not key or not secret:
            raise ValueError("Binance private access requires both API key and secret")
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
        self._stream_role = "account"
        self.exchange_name = kwargs.get("exchange_name", "BINANCE")
        self.symbol_name = kwargs.get("symbol_name")
        self.listen_key = kwargs.get("listen_key")
        self.proxies = kwargs.get("proxies")
        self.async_proxy = kwargs.get("async_proxy")
        self.logger = get_logger("binance_account_wss")
        raw_keepalive_interval = kwargs.get("listen_key_keepalive_interval", 1800.0)
        if isinstance(raw_keepalive_interval, bool):
            raise ValueError("listen_key_keepalive_interval must be a finite positive number")
        self.listen_key_keepalive_interval = float(raw_keepalive_interval)
        if (
            not math.isfinite(self.listen_key_keepalive_interval)
            or self.listen_key_keepalive_interval <= 0
        ):
            raise ValueError("listen_key_keepalive_interval must be a finite positive number")
        self._listen_key_lock = threading.Lock()
        self._listen_key_generation = 0
        self._needs_listen_key_renewal = False
        self._listen_key_keepalive_process: threading.Thread | None = None
        self.wss_author()

    def get_listen_key(self, max_retries: int = 3) -> dict[str, Any]:
        """Get listen key for WebSocket connection.

        Args: max_retries: Maximum number of retry attempts (default: 3).

        Returns: Dictionary containing listen key data.

        Raises: RuntimeError: If failed to get listen key after max retries.

        """
        path = self._params.get_rest_path("get_listen_key")
        extra_data = {
            "asset_type": self.asset_type,
            "symbol_name": None,
            "request_type": "get_listen_key",
            "exchange_name": self.exchange_name,
            "normalize_function": None,
        }
        last_err: str | None = None
        for attempt in range(max_retries):
            try:
                data = self.request(path, extra_data=extra_data, is_sign=False)
                result = data.get_data()
                if isinstance(result, dict) and "listenKey" in result:
                    return result
                self.logger.warning(
                    f"get_listen_key attempt {attempt + 1}/{max_retries} "
                    f"unexpected response: {sanitize_value(result)}"
                )
            except Exception as e:
                last_err = sanitize_text(e)
                self.logger.warning(
                    f"get_listen_key attempt {attempt + 1}/{max_retries} error: {last_err}"
                )
            if attempt < max_retries - 1:
                time.sleep(2)
        raise RuntimeError(f"Failed to get listen key after {max_retries} attempts: {last_err}")

    def refresh_listen_key(self) -> dict[str, Any]:
        """Refresh the listen key to keep WebSocket connection alive.

        Returns: Dictionary containing refresh result data.

        """
        extra_data = {
            "asset_type": "get_listen_key",
            "symbol_name": None,
            "request_type": "get_listen_key",
        }
        path = self._params.get_rest_path("refresh_listen_key")
        # USD-M user-stream keepalive is authenticated only by X-MBX-APIKEY.
        # It must not carry a listenKey, timestamp, recvWindow, or signature.
        data = self.request(path, params={}, extra_data=extra_data, is_sign=False)
        return data.get_data()

    def ping(self) -> None:
        """Refresh the listen key until this stream is stopped."""
        stop_event = self._stop_event
        while not stop_event.wait(self.listen_key_keepalive_interval):
            with self._listen_key_lock:
                expected_key = self.listen_key
                expected_generation = self._listen_key_generation
                expected_ws = self.ws
            try:
                self.refresh_listen_key()
            except Exception as e:
                self.logger.warning(f"Binance listen key keepalive failed: {sanitize_text(e)}")
                self._emit_event(
                    "ws.listen_key_refresh_error",
                    error=sanitize_text(e),
                )
                self._request_listen_key_renewal(
                    "keepalive_failed",
                    expected_key=expected_key,
                    expected_generation=expected_generation,
                    expected_ws=expected_ws,
                )

    def wss_author(self) -> None:
        """Authorize WebSocket connection using listen key."""
        listen_key = self.get_listen_key()["listenKey"]
        with self._listen_key_lock:
            self.listen_key = listen_key
            self.wss_url = f"{self._params.wss_url}/{listen_key}"
            self._listen_key_generation += 1
            self._needs_listen_key_renewal = False
        # self.logger.info("wss_author", self.wss_url)

    def _request_listen_key_renewal(
        self,
        reason: str,
        *,
        expected_key: str | None,
        expected_generation: int,
        expected_ws: Any,
    ) -> bool:
        """Request renewal only if the failing operation still owns the active generation."""
        with self._listen_key_lock:
            if (
                self.listen_key != expected_key
                or self._listen_key_generation != expected_generation
                or self.ws is not expected_ws
                or self._needs_listen_key_renewal
            ):
                return False
            self._needs_listen_key_renewal = True
            ws_to_close = self.ws
        self._running_flag = False
        self._emit_event("ws.listen_key_renewal_required", reason=reason)
        if ws_to_close is not None:
            ws_to_close.close()
        return True

    def _create_websocket_app(self):
        while True:
            with self._listen_key_lock:
                if not self._needs_listen_key_renewal:
                    ws = super()._create_websocket_app()
                    # Publish the new socket under the same lock as the listen-key
                    # generation so stale keepalive failures cannot close it.
                    self.ws = ws
                    return ws
            self.wss_author()

    def start(self, connect_timeout=30):
        super().start(connect_timeout=connect_timeout)
        worker = self._listen_key_keepalive_process
        if worker is None or not worker.is_alive():
            self._listen_key_keepalive_process = threading.Thread(
                target=self.ping,
                daemon=True,
            )
            self._listen_key_keepalive_process.start()

    def stop(self):
        failure = None
        try:
            super().stop()
        except Exception as error:
            failure = error
        worker = self._listen_key_keepalive_process
        current = threading.current_thread()
        if worker is not None and worker is not current and worker.is_alive():
            worker.join(timeout=self._shutdown_timeout)
            if worker.is_alive():
                cleanup_error = RuntimeError(
                    "Binance listen key keepalive worker did not stop within shutdown_timeout"
                )
                if failure is not None:
                    raise cleanup_error from failure
                raise cleanup_error
        if failure is not None:
            raise failure

    def open_rsp(self) -> None:
        """Handle WebSocket connection open event."""
        self.wss_logger.info(
            f"===== {time.strftime('%Y-%m-%d %H:%M:%S')} {self._params.exchange_name} "
            f"Websocket Connected ====="
        )

    def _init(self) -> None:
        """Initialize WebSocket subscriptions based on topics."""
        for topics in self.topics:
            if "orders" in topics["topic"]:
                symbol = topics.get("symbol", "BTC—USDT")
                self.subscribe(topic="orders", symbol=symbol)
            if "account" in topics["topic"]:
                symbol = topics.get("symbol", "BTC—USDT")
                currency = topics.get("currency", "USDT")
                self.subscribe(topic="account", symbol=symbol, currency=currency)
            if "positions" in topics["topic"]:
                symbol = topics.get("symbol", "BTC—USDT")
                self.subscribe(topic="positions", symbol=symbol)
            if "balance_position" in self.topics:
                self.subscribe(topic="balance_position")

    def handle_data(self, content: dict[str, Any]) -> None:
        """Handle incoming WebSocket data.

        Args: content: Dictionary containing WebSocket message data.

        """
        event = content.get("e")
        if event is not None:
            if event == "ACCOUNT_UPDATE":
                self.push_account(content)
            if event == "ORDER_TRADE_UPDATE":
                self.push_order(content)
            if event == "ORDER_TRADE_UPDATE" and content["o"].get("t") != 0:
                self.push_trade(content)
            # #
            # if "executionReport" == event:
            #     self.push_order(content)
            # if "outboundAccountPosition" == event:
            #     self.push_account(content)
            # if "balanceUpdate" == event:
            #     self.push_balance(content)

    def push_account(self, content: dict[str, Any]) -> None:
        """Push account data to queue.

        Args: content: Dictionary containing account update data.

        """
        # account
        # self.logger.info("")
        symbol = "ALL"
        account_data = BinanceSwapWssAccountData(content, symbol, self.asset_type, True)
        self.data_queue.put(account_data)
        # self.logger.info("account，：", account_data.get_balances()[0].get_margin())

    def push_order(self, content: dict[str, Any]) -> None:
        """Push order data to queue.

        Args: content: Dictionary containing order update data.

        """
        # self.logger.info("order")
        symbol = content["o"]["s"]
        order_data = BinanceSwapWssOrderData(content, symbol, self.asset_type, True)
        self.data_queue.put(order_data)
        # self.logger.info("order，order_status ：", order_data.get_order_status())

    def push_trade(self, content: dict[str, Any]) -> None:
        """Push trade data to queue.

        Args: content: Dictionary containing trade update data.

        """
        symbol = content["o"]["s"]
        trade_data = BinanceSwapWssTradeData(content, symbol, self.asset_type, True)
        self.data_queue.put(trade_data)
        # self.logger.info("trade，trade_id ：", trade_data.get_trade_id())

    def message_rsp(self, message: str) -> None:
        """Handle incoming WebSocket message.

        Args: message: Raw WebSocket message string.

        """
        rsp = json.loads(message)
        # self.logger.info("message received:", rsp)
        if rsp.get("e") == "listenKeyExpired":
            with self._listen_key_lock:
                expected_key = self.listen_key
                expected_generation = self._listen_key_generation
                expected_ws = self.ws
            expired_key = rsp.get("listenKey")
            if expired_key is not None and expired_key != expected_key:
                self._emit_event("ws.listen_key_expired_ignored", reason="stale_key")
                return
            self._emit_event("ws.listen_key_expired")
            self._request_listen_key_renewal(
                "expired",
                expected_key=expected_key,
                expected_generation=expected_generation,
                expected_ws=expected_ws,
            )
            return
        if "e" in rsp:
            self.handle_data(rsp)
        else:
            self.wss_logger.info(f"{self.logger_name}, error, {sanitize_value(rsp)}")
