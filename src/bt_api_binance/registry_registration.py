"""Module-level docstring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bt_api_base.balance_utils import simple_balance_handler as _binance_balance_handler

from bt_api_binance.environment import configure_environment
from bt_api_binance.exchange_data import BinanceExchangeDataSpot, BinanceExchangeDataSwap
from bt_api_binance.feeds.spot import (
    BinanceAccountWssDataSpot,
    BinanceMarketWssDataSpot,
    BinanceRequestDataSpot,
)
from bt_api_binance.feeds.swap import (
    BinanceAccountWssDataSwap,
    BinanceMarketWssDataSwap,
    BinanceRequestDataSwap,
)

if TYPE_CHECKING:
    from bt_api_base.registry import ExchangeRegistry


def _cleanup_started_streams(streams):
    survivors = []
    for stream in reversed(streams):
        stop = getattr(stream, "stop", None)
        if not callable(stop):
            survivors.append(stream)
            continue
        try:
            stop()
        except Exception:
            survivors.append(stream)
    return list(reversed(survivors))


def _commit_started_streams(bt_api, streams):
    retained = getattr(bt_api, "_subscription_streams", None)
    if retained is None:
        retained = bt_api._subscription_streams = []
    retained.extend(streams)


def _credential_alias(exchange_params, names):
    supplied = []
    for name in names:
        if name not in exchange_params or exchange_params[name] is None:
            continue
        value = exchange_params[name]
        if value == "":
            continue
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError("Binance credentials must be non-empty trimmed strings")
        supplied.append(value)
    if len(set(supplied)) > 1:
        raise ValueError("Binance credential aliases conflict")
    return supplied[0] if supplied else None


def _private_credentials(exchange_params):
    key = _credential_alias(exchange_params, ("public_key", "api_key"))
    secret = _credential_alias(exchange_params, ("private_key", "secret_key", "api_secret"))
    if (key is None) != (secret is None):
        raise ValueError("Binance private access requires both API key and secret")
    return key is not None


def _binance_swap_subscribe_handler(data_queue, exchange_params, topics, bt_api):
    cleanup_flag = "BINANCE___SWAP_subscription_cleanup_failed"
    if bt_api._subscription_flags.get(cleanup_flag, False):
        raise RuntimeError("Close BtApi before retrying the failed Binance swap subscription")
    exchange_data = configure_environment(BinanceExchangeDataSwap(), exchange_params)
    kwargs = dict(exchange_params)
    kwargs.update(
        wss_name="binance_swap_market_data",
        stream_role="market",
        wss_url=exchange_data.wss_url,
        exchange_data=exchange_data,
        topics=topics,
    )
    event_bus = getattr(bt_api, "event_bus", None)
    if event_bus is not None:
        kwargs["event_bus"] = event_bus
    has_credentials = _private_credentials(exchange_params)
    start_account = (
        has_credentials
        and kwargs.get("subscribe_account", True)
        and not bt_api._subscription_flags.get("BINANCE___SWAP_account", False)
    )
    started = []
    try:
        market = BinanceMarketWssDataSwap(data_queue, **kwargs)
        started.append(market)
        market.start()
        if start_account:
            account_kwargs = dict(kwargs)
            account_kwargs["wss_name"] = "binance_swap_account_data"
            account_kwargs["stream_role"] = "account"
            account_kwargs["wss_url"] = exchange_data.wss_url
            account_kwargs["topics"] = [{"topic": "account"}, {"topic": "order"}]
            account_kwargs["message_idle_timeout"] = exchange_params.get(
                "account_message_idle_timeout", 0.0
            )
            account = BinanceAccountWssDataSwap(data_queue, **account_kwargs)
            started.append(account)
            account.start()
    except Exception as start_error:
        survivors = _cleanup_started_streams(started)
        if survivors:
            _commit_started_streams(bt_api, survivors)
            bt_api._subscription_flags[cleanup_flag] = True
            raise RuntimeError(
                "Binance swap subscription startup failed and "
                f"{len(survivors)} stream(s) could not be stopped; close BtApi before retrying"
            ) from start_error
        raise
    _commit_started_streams(bt_api, started)
    if start_account:
        bt_api._subscription_flags["BINANCE___SWAP_account"] = True


def _binance_spot_subscribe_handler(data_queue, exchange_params, topics, bt_api):
    cleanup_flag = "BINANCE___SPOT_subscription_cleanup_failed"
    if bt_api._subscription_flags.get(cleanup_flag, False):
        raise RuntimeError("Close BtApi before retrying the failed Binance spot subscription")
    exchange_data = configure_environment(BinanceExchangeDataSpot(), exchange_params)
    kwargs = dict(exchange_params)
    kwargs.update(
        wss_name="binance_spot_market_data",
        stream_role="market",
        wss_url=exchange_data.wss_url,
        exchange_data=exchange_data,
        topics=topics,
    )
    event_bus = getattr(bt_api, "event_bus", None)
    if event_bus is not None:
        kwargs["event_bus"] = event_bus
    has_credentials = _private_credentials(exchange_params)
    start_account = (
        has_credentials
        and kwargs.get("subscribe_account", True)
        and not bt_api._subscription_flags.get("BINANCE___SPOT_account", False)
    )
    started = []
    try:
        market = BinanceMarketWssDataSpot(data_queue, **kwargs)
        started.append(market)
        market.start()
        if start_account:
            account_kwargs = dict(kwargs)
            account_kwargs["wss_name"] = "binance_spot_account_data"
            account_kwargs["stream_role"] = "account"
            account_kwargs["wss_url"] = exchange_data.wss_url
            account_kwargs["topics"] = [{"topic": "account"}, {"topic": "order"}]
            account_kwargs["message_idle_timeout"] = exchange_params.get(
                "account_message_idle_timeout", 0.0
            )
            account = BinanceAccountWssDataSpot(data_queue, **account_kwargs)
            started.append(account)
            account.start()
    except Exception as start_error:
        survivors = _cleanup_started_streams(started)
        if survivors:
            _commit_started_streams(bt_api, survivors)
            bt_api._subscription_flags[cleanup_flag] = True
            raise RuntimeError(
                "Binance spot subscription startup failed and "
                f"{len(survivors)} stream(s) could not be stopped; close BtApi before retrying"
            ) from start_error
        raise
    _commit_started_streams(bt_api, started)
    if start_account:
        bt_api._subscription_flags["BINANCE___SPOT_account"] = True


def register_binance(registry: ExchangeRegistry) -> None:
    """register_binance function"""
    registry.register_feed("BINANCE___SWAP", BinanceRequestDataSwap)
    registry.register_exchange_data("BINANCE___SWAP", BinanceExchangeDataSwap)
    registry.register_balance_handler("BINANCE___SWAP", _binance_balance_handler)
    registry.register_stream("BINANCE___SWAP", "subscribe", _binance_swap_subscribe_handler)

    registry.register_feed("BINANCE___SPOT", BinanceRequestDataSpot)
    registry.register_exchange_data("BINANCE___SPOT", BinanceExchangeDataSpot)
    registry.register_balance_handler("BINANCE___SPOT", _binance_balance_handler)
    registry.register_stream("BINANCE___SPOT", "subscribe", _binance_spot_subscribe_handler)
