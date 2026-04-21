from __future__ import annotations

from bt_api_base.balance_utils import simple_balance_handler as _binance_balance_handler
from bt_api_base.registry import ExchangeRegistry
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


def _binance_swap_subscribe_handler(data_queue, exchange_params, topics, bt_api):
    exchange_data = BinanceExchangeDataSwap()
    kwargs = dict(exchange_params.items())
    kwargs["wss_name"] = "binance_market_data"
    kwargs["wss_url"] = "wss://fstream.binance.com/ws"
    kwargs["exchange_data"] = exchange_data
    kwargs["topics"] = topics
    BinanceMarketWssDataSwap(data_queue, **kwargs).start()
    if not bt_api._subscription_flags.get("BINANCE___SWAP_account", False):
        account_kwargs = dict(kwargs.items())
        account_kwargs["topics"] = [
            {"topic": "account"},
            {"topic": "order"},
            {"topic": "trade"},
        ]
        BinanceAccountWssDataSwap(data_queue, **account_kwargs).start()
        bt_api._subscription_flags["BINANCE___SWAP_account"] = True


def _binance_spot_subscribe_handler(data_queue, exchange_params, topics, bt_api):
    exchange_data = BinanceExchangeDataSpot()
    kwargs = dict(exchange_params.items())
    kwargs["wss_name"] = "binance_market_data"
    kwargs["wss_url"] = "wss://stream.binance.com:9443/ws"
    kwargs["exchange_data"] = exchange_data
    kwargs["topics"] = topics
    BinanceMarketWssDataSpot(data_queue, **kwargs).start()
    if not bt_api._subscription_flags.get("BINANCE___SPOT_account", False):
        account_kwargs = dict(kwargs.items())
        account_kwargs["topics"] = [
            {"topic": "account"},
            {"topic": "order"},
            {"topic": "trade"},
        ]
        BinanceAccountWssDataSpot(data_queue, **account_kwargs).start()
        bt_api._subscription_flags["BINANCE___SPOT_account"] = True


def register_binance(registry: ExchangeRegistry) -> None:
    registry.register_feed("BINANCE___SWAP", BinanceRequestDataSwap)
    registry.register_exchange_data("BINANCE___SWAP", BinanceExchangeDataSwap)
    registry.register_balance_handler("BINANCE___SWAP", _binance_balance_handler)
    registry.register_stream("BINANCE___SWAP", "subscribe", _binance_swap_subscribe_handler)

    registry.register_feed("BINANCE___SPOT", BinanceRequestDataSpot)
    registry.register_exchange_data("BINANCE___SPOT", BinanceExchangeDataSpot)
    registry.register_balance_handler("BINANCE___SPOT", _binance_balance_handler)
    registry.register_stream("BINANCE___SPOT", "subscribe", _binance_spot_subscribe_handler)
