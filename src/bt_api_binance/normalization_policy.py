"""Binance-specific normalization choices used by the unified SDK."""

from bt_api_base.normalization_policy import LegacyNormalizationPolicy


class BinanceNormalizationPolicy(LegacyNormalizationPolicy):
    default_multiplier = 1.0
    event_id_fields = ("event_id", "trade_id", "tradeId", "fill_id", "order_id", "orderId")
    event_audit_fields = (
        "sequence", "sequence_id", "previous_sequence", "pu", "U", "u",
        "checksum", "action", "ts", "E", "T",
    )
    orderbook_sequence_fields = ("sequence", "sequence_id", "update_id", "lastUpdateId", "u")
    orderbook_previous_fields = ("previous_sequence", "prev_sequence", "pu")
    orderbook_delta_predecessor_fields = ("pu",)
    tick_bid_fields = ("bid_price", "bid")
    tick_ask_fields = ("ask_price", "ask")
    tick_price_fields = ("price", "last_price", "last")
    tick_volume_fields = ("volume", "last_volume")
    tick_cumulative_fields = ("cum_volume", "cumulative_volume")


class BinanceSwapNormalizationPolicy(BinanceNormalizationPolicy):
    zero_balance_currency = "USDT"


def normalization_policy(exchange_name):
    if exchange_name == "BINANCE___SWAP":
        return BinanceSwapNormalizationPolicy()
    return BinanceNormalizationPolicy()


__all__ = ("normalization_policy",)
