"""Binance websocket adapters kept inside the bt_api_binance plugin."""

from __future__ import annotations

import json
import time
from typing import Any

from bt_api_base.websocket.exchange_adapters import (
    AuthenticationType,
    ExchangeCredentials,
    ExchangeType,
    ExchangeWebSocketAdapter,
    RateLimitConfig,
)

__all__ = ["BinanceWebSocketAdapter"]


class BinanceWebSocketAdapter(ExchangeWebSocketAdapter):
    """Binance-specific WebSocket adapter."""

    def __init__(
        self,
        exchange_type: ExchangeType = ExchangeType.SPOT,
        credentials: ExchangeCredentials | None = None,
    ):
        super().__init__("BINANCE", credentials)
        self.exchange_type = exchange_type
        self._listen_key: str | None = None

    def get_endpoints(self, primary_url: str) -> list[str]:
        """Get Binance failover endpoints."""
        base_urls = [
            "wss://stream.binance.com:9443",
            "wss://stream.binance.com:443",
            "wss://stream1.binance.com:9443",
            "wss://stream2.binance.com:9443",
        ]

        if self.exchange_type == ExchangeType.FUTURES:
            base_urls = [
                "wss://fstream.binance.com",
                "wss://fstream.binance.com:443",
                "wss://fstream1.binance.com",
                "wss://fstream2.binance.com",
            ]
        elif self.exchange_type == ExchangeType.SWAP:
            base_urls = [
                "wss://dstream.binance.com",
                "wss://dstream.binance.com:443",
                "wss://dstream1.binance.com",
                "wss://dstream2.binance.com",
            ]

        return base_urls

    async def authenticate(self, websocket: Any) -> None:
        """Authenticate for user data streams."""
        if self.credentials and self.credentials.auth_type == AuthenticationType.API_KEY_SECRET:
            await self._get_listen_key()

            message = {
                "method": "SUBSCRIBE",
                "params": [self._listen_key],
                "id": int(time.time() * 1000),
            }

            await websocket.send(json.dumps(message))
            self.logger.info("Binance authentication completed")

    async def _get_listen_key(self) -> None:
        """Get listen key for user data stream."""
        self.logger.info("Getting Binance listen key")

    def format_subscription_message(
        self, subscription_id: str, topic: str, symbol: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Format Binance subscription message."""
        stream_name = self._get_stream_name(topic, symbol, params)

        return {"method": "SUBSCRIBE", "params": [stream_name], "id": subscription_id}

    def format_unsubscription_message(
        self, subscription_id: str, topic: str, symbol: str
    ) -> dict[str, Any]:
        """Format Binance unsubscription message."""
        stream_name = self._get_stream_name(topic, symbol, {})

        return {"method": "UNSUBSCRIBE", "params": [stream_name], "id": subscription_id}

    def _get_stream_name(self, topic: str, symbol: str, params: dict[str, Any]) -> str:
        """Get Binance stream name."""
        symbol_lower = symbol.lower()

        if topic == "ticker":
            return f"{symbol_lower}@ticker"
        if topic == "depth":
            level = params.get("level", "20")
            return f"{symbol_lower}@depth{level}"
        if topic == "trades":
            return f"{symbol_lower}@trade"
        if topic == "kline":
            interval = params.get("interval", "1m")
            return f"{symbol_lower}@kline_{interval}"
        if topic == "aggTrades":
            return f"{symbol_lower}@aggTrade"
        if topic == "markPrice":
            return f"{symbol_lower}@markPrice@1s"
        return f"{symbol_lower}@{topic}"

    def extract_topic_symbol(self, message: dict[str, Any]) -> tuple[str | None, str | None]:
        """Extract topic and symbol from Binance message."""
        stream = message.get("stream")
        if isinstance(stream, str) and "@" in stream:
            symbol, topic = stream.split("@", 1)
            return topic, symbol.upper()
        return None, None

    def normalize_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Normalize Binance message format."""
        if "data" not in message or "stream" not in message:
            return message

        data = message["data"]
        topic, symbol = self.extract_topic_symbol(message)

        normalized = {
            "exchange": "BINANCE",
            "symbol": symbol,
            "topic": topic,
            "data": data,
            "timestamp": data.get("E", time.time() * 1000),
        }

        if topic == "ticker":
            normalized.update(
                {
                    "last_price": float(data.get("c", 0)),
                    "volume": float(data.get("v", 0)),
                    "high_24h": float(data.get("h", 0)),
                    "low_24h": float(data.get("l", 0)),
                    "change_24h": float(data.get("P", 0)),
                }
            )
        elif topic == "depth":
            normalized.update(
                {
                    "bids": [[float(p), float(q)] for p, q in data.get("bids", [])],
                    "asks": [[float(p), float(q)] for p, q in data.get("asks", [])],
                    "last_update_id": data.get("lastUpdateId"),
                }
            )
        elif topic in ("trade", "aggTrade"):
            normalized.update(
                {
                    "price": float(data.get("p", 0)),
                    "quantity": float(data.get("q", 0)),
                    "trade_time": data.get("T"),
                    "is_buyer_maker": data.get("m", False),
                }
            )
        elif topic and topic.startswith("kline"):
            kline_data = data.get("k", {}) if data else {}
            normalized.update(
                {
                    "open_time": kline_data.get("t"),
                    "close_time": kline_data.get("T"),
                    "open": float(kline_data.get("o", 0)),
                    "high": float(kline_data.get("h", 0)),
                    "low": float(kline_data.get("l", 0)),
                    "close": float(kline_data.get("c", 0)),
                    "volume": float(kline_data.get("v", 0)),
                    "is_closed": kline_data.get("x", False),
                }
            )

        return normalized

    def get_rate_limit_config(self) -> RateLimitConfig:
        """Get Binance rate limiting configuration."""
        return RateLimitConfig(
            max_connections_per_ip=5,
            max_subscriptions_per_connection=1024,
            messages_per_second_limit=5,
            requests_per_second=10,
            requests_per_minute=1200,
        )

    def get_subscription_limits(self) -> dict[str, int]:
        """Get Binance subscription limits."""
        return {
            "ticker": 1024,
            "depth": 1024,
            "trades": 1024,
            "kline": 1024,
            "aggTrades": 1024,
            "markPrice": 1024,
        }
