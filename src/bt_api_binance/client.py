"""Standalone direct Binance client for REST + websocket flows."""

from __future__ import annotations

import queue
import threading
import time
from collections import defaultdict
from typing import Any

from bt_api_base.logging_factory import get_logger

from bt_api_binance.containers.orders.binance_order import BinanceSwapWssOrderData
from bt_api_binance.containers.tickers.binance_ticker import BinanceWssTickerData
from bt_api_binance.containers.trades.binance_trade import BinanceSwapWssTradeData
from bt_api_binance.exchange_data import (
    BinanceExchangeDataSpot,
    BinanceExchangeDataSwap,
)
from bt_api_binance.feeds.swap import (
    BinanceAccountWssDataSwap,
    BinanceMarketWssDataSwap,
    BinanceRequestDataSwap,
)

CHANNEL_EVENT = "event"
CHANNEL_MARKET = "market"

LegacyBinanceSwapWssOrderData = BinanceSwapWssOrderData
LegacyBinanceSwapWssTradeData = BinanceSwapWssTradeData


def _normalize_asset_type(raw: Any) -> str:
    value = str(raw or "SWAP").strip().upper()
    mapping = {"SWAP": "SWAP", "SPOT": "SPOT", "FUTURE": "SWAP", "FUT": "SWAP"}
    return mapping.get(value, value)


def _create_feed(q: queue.Queue, kwargs: dict[str, Any]):
    asset_type = kwargs.get("asset_type", "SWAP")
    if asset_type == "SPOT":
        from bt_api_binance.feeds.spot import BinanceRequestDataSpot

        return BinanceRequestDataSpot(q, **kwargs)
    return BinanceRequestDataSwap(q, **kwargs)


def _create_exchange_data(asset_type: str):
    if asset_type == "SPOT":
        return BinanceExchangeDataSpot()
    return BinanceExchangeDataSwap()


def _request_data_payload(result: Any) -> Any:
    return result.get_data() if hasattr(result, "get_data") else result


def _container_to_dict(item: Any) -> dict[str, Any]:
    init_data = getattr(item, "init_data", None)
    if callable(init_data):
        item = init_data()
    if hasattr(item, "get_all_data"):
        return dict(item.get_all_data())
    return dict(item) if isinstance(item, dict) else {"raw": str(item)}


def _payload_rows(payload: Any) -> list[Any]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return [payload]
    if isinstance(payload, list):
        return payload
    return []


def _normalise_order_row(item: Any) -> dict[str, Any]:
    row = _container_to_dict(item)
    order_id = (
        row.get("order_id")
        or row.get("orderId")
        or row.get("i")
        or row.get("id")
    )
    client_order_id = (
        row.get("client_order_id")
        or row.get("clientOrderId")
        or row.get("origClientOrderId")
        or row.get("c")
    )
    symbol = row.get("symbol") or row.get("symbol_name") or row.get("s")
    status = row.get("status") or row.get("order_status") or row.get("X")
    remaining = row.get("remaining")
    if remaining in (None, ""):
        try:
            size = float(row.get("origQty") or row.get("size") or row.get("volume") or 0)
            filled = float(row.get("executedQty") or row.get("filled") or 0)
            remaining = max(size - filled, 0.0)
        except (TypeError, ValueError):
            remaining = None
    if order_id not in (None, ""):
        row["order_id"] = order_id
        row.setdefault("external_order_id", order_id)
    if client_order_id not in (None, ""):
        row["client_order_id"] = client_order_id
    if symbol not in (None, ""):
        row["symbol"] = symbol
        row.setdefault("data_name", symbol)
    if status not in (None, ""):
        row["status"] = status
    if remaining not in (None, ""):
        row["remaining"] = remaining
    return row


def _symbol_lookup_candidates(symbol: str, exchange_data: Any) -> set[str]:
    raw = str(symbol or "").strip()
    candidates = {
        raw,
        raw.upper(),
        raw.replace("-", ""),
        raw.replace("/", ""),
        raw.replace("_", ""),
    }
    get_symbol = getattr(exchange_data, "get_symbol", None)
    if callable(get_symbol):
        try:
            converted = str(get_symbol(raw) or "").strip()
        except Exception:
            converted = ""
        if converted:
            candidates.update({converted, converted.upper()})
    return {item for item in candidates if item}


def _first_filter_value(filters: Any, filter_type: str, *keys: str) -> Any:
    if not isinstance(filters, list):
        return None
    for item in filters:
        if not isinstance(item, dict) or item.get("filterType") != filter_type:
            continue
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return value
    return None


def _first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_commission_rate(value: Any) -> float | None:
    rate = _safe_float(value)
    if rate is None:
        return None
    if rate > 1:
        return rate / 10000.0
    return max(rate, 0.0)


def _normalise_percent_rate(value: Any) -> float | None:
    rate = _safe_float(value)
    if rate is None:
        return None
    if rate > 1:
        return rate / 100.0
    return max(rate, 0.0)


def _normalise_binance_fee_info(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        rows = data.get("data")
    elif isinstance(data, dict):
        rows = [data]
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    row = next((item for item in rows if isinstance(item, dict)), None)
    if row is None:
        return {}

    maker_rate = _normalise_commission_rate(
        _first_value(row, "makerCommissionRate", "makerCommission")
    )
    taker_rate = _normalise_commission_rate(
        _first_value(row, "takerCommissionRate", "takerCommission")
    )
    spec: dict[str, Any] = {"fee_source": "binance_get_fee"}
    if maker_rate is not None:
        spec["maker_commission_rate"] = maker_rate
    if taker_rate is not None:
        spec["taker_commission_rate"] = taker_rate
        spec["commission_rate"] = taker_rate
        spec["open_commission_rate"] = taker_rate
    elif maker_rate is not None:
        spec["commission_rate"] = maker_rate
        spec["open_commission_rate"] = maker_rate
    return spec


def _normalise_binance_symbol_info(row: dict[str, Any], *, asset_type: str) -> dict[str, Any]:
    filters = row.get("filters")
    symbol = str(_first_value(row, "symbol", "symbol_name") or "").strip()
    price_tick = _first_filter_value(filters, "PRICE_FILTER", "tickSize")
    lot_filter = "LOT_SIZE"
    min_qty = _first_filter_value(filters, lot_filter, "minQty")
    max_qty = _first_filter_value(filters, lot_filter, "maxQty")
    step_size = _first_filter_value(filters, lot_filter, "stepSize")
    market_min_qty = _first_filter_value(filters, "MARKET_LOT_SIZE", "minQty")
    market_max_qty = _first_filter_value(filters, "MARKET_LOT_SIZE", "maxQty")
    market_step_size = _first_filter_value(filters, "MARKET_LOT_SIZE", "stepSize")
    min_notional = (
        _first_filter_value(filters, "MIN_NOTIONAL", "notional", "minNotional")
        or _first_filter_value(filters, "NOTIONAL", "notional", "minNotional")
    )
    margin_rate = _normalise_percent_rate(
        _first_value(row, "requiredMarginPercent", "maintMarginPercent")
    )

    spec = {
        "source": "binance_exchange_info",
        "exchange": "BINANCE",
        "exchange_id": "BINANCE",
        "symbol": symbol,
        "asset_type": asset_type,
        "base_asset": _first_value(row, "baseAsset", "base_asset"),
        "quote_asset": _first_value(row, "quoteAsset", "quote_asset"),
        "contract_type": _first_value(row, "contractType", "contract_type"),
    }
    contract_size = _first_value(row, "contractSize", "contract_multiplier")
    if contract_size in (None, ""):
        contract_size = 1
    spec.update(
        {
            "contract_multiplier": contract_size,
            "contract_size": contract_size,
            "multiplier": contract_size,
            "price_tick": price_tick or _first_value(row, "price_unit", "tick_size"),
            "tick_size": price_tick or _first_value(row, "price_unit", "tick_size"),
            "min_order_size": min_qty or _first_value(row, "min_qty", "minQty"),
            "max_order_size": max_qty or _first_value(row, "max_qty", "maxQty"),
            "order_size_step": step_size or _first_value(row, "qty_unit", "stepSize"),
            "market_min_order_size": market_min_qty,
            "market_max_order_size": market_max_qty,
            "market_order_size_step": market_step_size,
            "min_notional": min_notional or _first_value(row, "min_amount", "minNotional"),
            "required_margin_percent": margin_rate,
            "margin_rate": margin_rate,
        }
    )
    return {key: value for key, value in spec.items() if value not in (None, "")}


class BinanceDirectClient:
    """Direct Binance client without any gateway dependency."""

    def __init__(self, **kwargs: Any) -> None:
        """__init__ method"""
        normalized = dict(kwargs)
        self.asset_type = _normalize_asset_type(normalized.get("asset_type"))
        normalized["asset_type"] = self.asset_type
        normalized.setdefault("public_key", normalized.get("api_key", ""))
        normalized.setdefault("private_key", normalized.get("secret_key", ""))
        normalized.setdefault("exchange_name", "BINANCE")
        exchange_data = _create_exchange_data(self.asset_type)
        normalized["exchange_data"] = exchange_data
        self.kwargs = normalized
        self.logger = get_logger("gateway")
        self.q: queue.Queue[Any] = queue.Queue()
        self.output_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.feed = _create_feed(self.q, normalized)
        self.market_stream = None
        self.account_stream = None
        self.aliases: dict[str, set[str]] = defaultdict(set)
        self.last_price: dict[str, float] = {}
        self._latest_ticks: dict[str, dict[str, Any]] = {}
        self.running = False
        self.thread: threading.Thread | None = None
        self.timeout = float(normalized.get("gateway_startup_timeout_sec", 10.0) or 10.0)
        self._market_connect_timeout = float(
            normalized.get("market_stream_connect_timeout_sec", 1.0) or 1.0
        )
        self._account_connect_timeout = float(
            normalized.get("account_stream_connect_timeout_sec", 1.0) or 1.0
        )

    def connect(self) -> None:
        """connect method"""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.logger.info("BinanceDirectClient connected")

    def disconnect(self) -> None:
        """disconnect method"""
        self.running = False
        thread = self.thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self.thread = None
        self.market_stream = None
        self.account_stream = None
        self.aliases = defaultdict(set)
        self.last_price.clear()
        self._latest_ticks.clear()
        self.logger.info("BinanceDirectClient disconnected")

    def subscribe_symbols(self, symbols: list[str]) -> dict[str, Any]:
        """subscribe_symbols method"""
        topics: list[dict[str, Any]] = []
        for symbol in symbols:
            topics.append({"topic": "ticker", "symbol": symbol})
            topics.append({"topic": "book_ticker", "symbol": symbol})
        wss_kwargs = dict(self.kwargs)
        if self.asset_type == "SPOT":
            wss_url = "wss://stream.binance.com:9443/ws"
        else:
            wss_url = "wss://fstream.binance.com/ws"
        wss_kwargs["wss_url"] = wss_url
        wss_kwargs["wss_name"] = "binance_market_data"
        wss_kwargs["topics"] = topics

        if self.market_stream is None:
            if self.asset_type == "SPOT":
                from bt_api_binance.feeds.spot import BinanceMarketWssDataSpot

                self.market_stream = BinanceMarketWssDataSpot(self.q, **wss_kwargs)
            else:
                self.market_stream = BinanceMarketWssDataSwap(self.q, **wss_kwargs)
            self.market_stream.start(connect_timeout=self._market_connect_timeout)
            self.logger.info(f"Binance market stream started for {symbols}")

        for symbol in symbols:
            self.aliases[symbol].add(symbol)
        return {"symbols": symbols}

    def _ensure_account_stream(self) -> None:
        if self.account_stream is not None:
            return
        wss_kwargs = dict(self.kwargs)
        if self.asset_type == "SPOT":
            wss_url = "wss://stream.binance.com:9443/ws"
        else:
            wss_url = "wss://fstream.binance.com/ws"
        wss_kwargs["wss_url"] = wss_url
        wss_kwargs["wss_name"] = "binance_account_data"
        wss_kwargs["topics"] = [
            {"topic": "account"},
            {"topic": "order"},
            {"topic": "trade"},
        ]
        try:
            if self.asset_type == "SPOT":
                from bt_api_binance.feeds.spot import BinanceAccountWssDataSpot

                self.account_stream = BinanceAccountWssDataSpot(self.q, **wss_kwargs)
            else:
                self.account_stream = BinanceAccountWssDataSwap(self.q, **wss_kwargs)
            self.account_stream.start(connect_timeout=self._account_connect_timeout)
            self.logger.info("Binance account stream started")
        except Exception as exc:
            self.account_stream = None
            self.logger.warning(
                "Binance account stream unavailable; continuing with market data only: %s",
                exc,
            )

    def get_balance(self) -> dict[str, Any]:
        """get_balance method"""
        self._ensure_account_stream()
        try:
            result = self.feed.get_balance()
            data = result.get_data() if hasattr(result, "get_data") else result
            if isinstance(data, list) and len(data) > 0:
                return _container_to_dict(data[0])
            if isinstance(data, dict):
                return data
            return {"raw": str(data)}
        except Exception as exc:
            self.logger.warning(f"get_balance error: {exc}")
            return {"error": str(exc)}

    def get_positions(self) -> list[dict[str, Any]]:
        """get_positions method"""
        self._ensure_account_stream()
        try:
            result = self.feed.get_position()
            data = result.get_data() if hasattr(result, "get_data") else result
            if isinstance(data, list):
                return [_container_to_dict(item) for item in data]
            return []
        except Exception as exc:
            self.logger.warning(f"get_positions error: {exc}")
            return []

    def get_trades(self, symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        get_deals = getattr(self.feed, "get_deals", None)
        if not callable(get_deals) or not symbol:
            return []
        try:
            result = get_deals(symbol=symbol, count=limit)
            payload = _request_data_payload(result)
            return [_container_to_dict(item) for item in _payload_rows(payload)]
        except Exception as exc:
            self.logger.debug(f"get_trades error: {exc}")
            return []

    def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        get_config = getattr(self.feed, "get_config", None)
        if not callable(get_config):
            return {}
        try:
            data = _request_data_payload(get_config())
        except Exception as exc:
            self.logger.warning(f"get_symbol_info error: {exc}")
            return {}

        candidates = _symbol_lookup_candidates(symbol, getattr(self.feed, "_params", None))
        rows = data.get("symbols") if isinstance(data, dict) else data
        if isinstance(data, dict) and isinstance(data.get("symbol"), str):
            rows = [data]
        if not isinstance(rows, list):
            return {}
        for item in rows:
            if not isinstance(item, dict):
                continue
            item_symbol = str(
                item.get("symbol") or item.get("symbol_name") or item.get("pair") or ""
            ).strip()
            if item_symbol and item_symbol.upper() in {candidate.upper() for candidate in candidates}:
                spec = _normalise_binance_symbol_info(item, asset_type=self.asset_type)
                spec.update(self._query_symbol_fee(symbol))
                return spec
        return {}

    def _query_symbol_fee(self, symbol: str) -> dict[str, Any]:
        get_fee = getattr(self.feed, "get_fee", None)
        if not callable(get_fee):
            return {}
        try:
            return _normalise_binance_fee_info(_request_data_payload(get_fee(symbol)))
        except Exception as exc:
            self.logger.debug(f"get_symbol_info fee lookup failed: {exc}")
            return {}

    def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """place_order method"""
        self._ensure_account_stream()
        symbol = payload.get("data_name") or payload.get("symbol") or ""
        volume = float(payload.get("volume") or payload.get("size") or 0)
        price = payload.get("price")
        if price is not None:
            price = float(price)
        side = str(payload.get("side") or "buy").lower()
        order_type = str(payload.get("order_type") or "limit").lower()
        offset = str(payload.get("offset") or "open").lower()
        order_type_str = f"{side}-{order_type}"
        client_order_id = payload.get("client_order_id")
        position_side = _first_value(payload, "position_side", "positionSide", "posSide")
        reduce_only = _first_value(payload, "reduceOnly", "reduce_only")
        time_in_force = _first_value(payload, "time_in_force", "timeInForce")

        result = self.feed.make_order(
            symbol=symbol,
            vol=volume,
            price=price,
            order_type=order_type_str,
            offset=offset,
            client_order_id=client_order_id,
            position_side=position_side,
            reduceOnly=reduce_only,
            time_in_force=time_in_force or "GTC",
        )
        data = result.get_data() if hasattr(result, "get_data") else result
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            if hasattr(item, "get_all_data"):
                return item.get_all_data()
            return dict(item) if isinstance(item, dict) else {"raw": str(item)}
        if isinstance(data, dict):
            return data
        return {"raw": str(data)}

    def cancel_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """cancel_order method"""
        self._ensure_account_stream()
        symbol = payload.get("data_name") or payload.get("symbol") or payload.get("instrument") or ""
        order_id = (
            payload.get("order_id")
            or payload.get("external_order_id")
            or payload.get("venue_order_id")
            or payload.get("id")
            or payload.get("order_ref")
        )
        client_order_id = payload.get("client_order_id")

        cancel_kwargs: dict[str, Any] = {}
        if client_order_id:
            cancel_kwargs["client_order_id"] = client_order_id

        result = self.feed.cancel_order(
            symbol=symbol,
            order_id=order_id,
            **cancel_kwargs,
        )
        data = result.get_data() if hasattr(result, "get_data") else result
        if isinstance(data, dict):
            return data
        return {"raw": str(data)}

    def get_open_orders(self) -> list[dict[str, Any]]:
        get_open_orders = getattr(self.feed, "get_open_orders", None)
        if not callable(get_open_orders):
            return []
        result = get_open_orders()
        payload = _request_data_payload(result)
        return [_normalise_order_row(item) for item in _payload_rows(payload)]

    def poll_output(self) -> tuple[str, Any] | None:
        """poll_output method"""
        try: return self.output_queue.get_nowait()
        except queue.Empty:
            return None

    def emit(self, channel: str, payload: Any) -> None:
        """emit method"""
        self.output_queue.put((channel, payload))

    def _run(self) -> None:
        while self.running:
            try:
                item = self.q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._dispatch_item(item)
            except Exception as exc:
                self.logger.warning(f"Binance direct client dispatch error: {exc}")

    def _dispatch_item(self, item: Any) -> None:
        if isinstance(item, BinanceWssTickerData):
            self._emit_ticker(item)
        elif isinstance(item, (BinanceSwapWssOrderData, LegacyBinanceSwapWssOrderData)):
            self._emit_order(item)
        elif isinstance(item, (BinanceSwapWssTradeData, LegacyBinanceSwapWssTradeData)):
            self._emit_trade(item)
        else:
            event_name = getattr(item, "event", None) or type(item).__name__
            self.emit(CHANNEL_EVENT, {"kind": "raw", "type": event_name})

    def _emit_ticker(self, ticker: BinanceWssTickerData) -> None:
        ticker.init_data()
        symbol = ticker.get_symbol_name() or ""
        if not symbol:
            return
        server_time = ticker.get_server_time() or 0.0
        ts = server_time / 1000.0 if server_time > 1e12 else server_time
        previous = dict(self._latest_ticks.get(symbol, {}))

        def _coalesce(current: Any, cached: Any) -> Any:
            if current in (None, "", 0, 0.0):
                return cached
            return current

        bid = _coalesce(ticker.get_bid_price(), previous.get("bid_price"))
        ask = _coalesce(ticker.get_ask_price(), previous.get("ask_price"))
        last = _coalesce(ticker.get_last_price(), previous.get("last_price"))
        bid_volume = _coalesce(ticker.get_bid_volume(), previous.get("bid_volume"))
        ask_volume = _coalesce(ticker.get_ask_volume(), previous.get("ask_volume"))
        volume = _coalesce(ticker.get_volume_24h(), previous.get("volume"))
        turnover = _coalesce(ticker.get_turnover_24h(), previous.get("turnover"))
        high_price = _coalesce(ticker.get_high_price(), previous.get("high_price"))
        low_price = _coalesce(ticker.get_low_price(), previous.get("low_price"))
        open_price = _coalesce(ticker.get_open_price(), previous.get("open_price"))
        prev_close = _coalesce(ticker.get_prev_close(), previous.get("prev_close"))
        merged_ts = ts or previous.get("timestamp") or 0.0
        merged_price = (
            float(last)
            if last not in (None, "", 0, 0.0)
            else (float(bid) + float(ask)) / 2.0
            if bid not in (None, "", 0, 0.0) and ask not in (None, "", 0, 0.0)
            else float(previous.get("price") or 0.0)
        )
        self._latest_ticks[symbol] = {
            "timestamp": merged_ts,
            "price": merged_price,
            "last_price": last,
            "bid_price": bid,
            "ask_price": ask,
            "bid_volume": bid_volume,
            "ask_volume": ask_volume,
            "volume": volume,
            "turnover": turnover,
            "high_price": high_price,
            "low_price": low_price,
            "open_price": open_price,
            "prev_close": prev_close,
        }
        if merged_price > 0:
            self.last_price[symbol] = merged_price
        tick = {
            "timestamp": float(merged_ts or 0.0),
            "symbol": symbol,
            "exchange": "BINANCE",
            "asset_type": self.asset_type,
            "local_time": time.time(),
            "price": float(merged_price),
            "bid_price": float(bid) if bid not in (None, "") else None,
            "ask_price": float(ask) if ask not in (None, "") else None,
            "bid_volume": float(bid_volume) if bid_volume not in (None, "") else None,
            "ask_volume": float(ask_volume) if ask_volume not in (None, "") else None,
            "volume": float(volume or 0.0),
            "turnover": float(turnover or 0.0),
            "high_price": float(high_price) if high_price not in (None, "") else None,
            "low_price": float(low_price) if low_price not in (None, "") else None,
            "open_price": float(open_price) if open_price not in (None, "") else None,
            "prev_close": float(prev_close) if prev_close not in (None, "") else None,
        }
        self.emit(CHANNEL_MARKET, tick)

    def _emit_order(self, order: BinanceSwapWssOrderData) -> None:
        try:
            order.init_data()
            self.emit(
                CHANNEL_EVENT,
                {
                    "kind": "order",
                    "exchange": "BINANCE",
                    "symbol": order.get_symbol_name(),
                    "order_id": order.get_order_id(),
                    "client_order_id": order.get_client_order_id(),
                    "status": order.get_order_status(),
                    "side": order.get_order_side(),
                    "price": order.get_order_price(),
                    "volume": order.get_order_size(),
                    "filled": order.get_executed_qty(),
                },
            )
        except Exception as exc:
            self.logger.warning(f"_emit_order error: {exc}")

    def _emit_trade(self, trade: BinanceSwapWssTradeData) -> None:
        try:
            trade.init_data()
            self.emit(
                CHANNEL_EVENT,
                {
                    "kind": "trade",
                    "exchange": "BINANCE",
                    "symbol": trade.get_symbol_name(),
                    "trade_id": trade.get_trade_id(),
                    "order_id": trade.get_order_id(),
                    "price": trade.get_trade_price(),
                    "volume": trade.get_trade_volume(),
                    "side": trade.get_trade_side(),
                    "trade_type": trade.get_trade_type(),
                    "liquidity": trade.get_trade_type(),
                    "trade_fee": trade.get_trade_fee(),
                    "trade_commission": trade.get_trade_fee(),
                    "fee": trade.get_trade_fee(),
                    "fee_currency": trade.get_trade_fee_symbol(),
                },
            )
        except Exception as exc:
            self.logger.warning(f"_emit_trade error: {exc}")
