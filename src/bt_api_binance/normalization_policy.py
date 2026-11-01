"""Binance-specific normalization choices used by the unified SDK."""

from types import MappingProxyType

from bt_api_base.normalization_policy import LegacyNormalizationPolicy


class BinanceNormalizationPolicy(LegacyNormalizationPolicy):
    default_multiplier = 1.0
    order_fields = MappingProxyType({
        "order_id": ("order_id", "external_order_id", "orderId"),
        "client_id": ("client_order_id", "clientOrderId", "order_ref"),
        "filled": ("filled", "filled_quantity", "executed_qty", "executedQty"),
        "average": ("avg_price", "average_price", "order_avg_price", "avgPrice"),
        "cum_quote": ("cum_quote", "cumQuote", "cummulativeQuoteQty"),
        "size": ("quantity", "size", "order_size", "origQty"),
        "order_ref": ("order_ref",), "exchange_id": ("exchange_id",),
        "front_id": ("front_id",), "session_id": ("session_id",),
        "account_id": ("account_id",), "trading_day": ("trading_day",),
        "fee_currency": ("fee_currency", "commissionAsset"),
        "commission_currency": ("commission_currency", "fee_currency", "commissionAsset"),
    })
    trade_fields = MappingProxyType({
        "trade_id": ("trade_id", "fill_id", "deal_id", "tradeId", "id"),
        "order_id": ("order_id", "external_order_id", "orderId"),
        "client_id": ("client_order_id",),
        "size": ("quantity", "size", "trade_volume", "qty", "volume"),
        "price": ("trade_price", "price"), "exchange_id": ("exchange_id",),
        "account_id": ("account_id",), "trading_day": ("trading_day",),
        "fee_currency": ("fee_currency", "trade_fee_symbol", "commissionAsset"),
    })
    signed_fee_currency_field = None
    position_fields = MappingProxyType({
        "quantity": (
            "quantity", "position_volume", "volume", "size", "positionAmt", "trade_volume",
        ),
        "side": ("position_side", "direction", "position_direction", "positionSide", "side"),
        "position_id": ("position_id",),
        "price": ("average_price", "avg_price", "price", "entryPrice"),
        "today": ("today", "today_position", "today_volume"),
        "yesterday": ("yesterday", "yesterday_position", "yd_position"),
        "multiplier": ("multiplier", "contract_size", "volume_multiple"),
        "exchange_id": ("exchange_id",),
    })
    balance_nested_fields = ("assets", "balances")
    balance_fields = MappingProxyType({
        "currency": ("currency", "asset", "account_type", "symbol_name", "symbol"),
        "cash": (
            "available_cash", "availableBalance", "available", "cash", "available_margin",
            "margin_free", "free_margin", "free",
        ),
        "value": ("equity", "marginBalance", "value"),
        "wallet": ("balance", "walletBalance", "margin", "total_wallet_balance"),
        "unrealized": ("crossUnPnl", "unrealizedProfit", "unrealized_profit"),
        "margin_used": ("margin_used", "used_margin", "initialMargin"),
        "account_id": ("account_id",),
    })
    instrument_fields = MappingProxyType({
        "multiplier": ("multiplier", "contract_size"),
        "step": ("lot_size", "order_size_step", "volume_step", "stepSize"),
        "min_size": ("min_size", "volume_min"),
        "max_size": ("max_size", "volume_max"),
        "tick_size": ("tick_size", "price_tick"),
        "settlement_currency": ("settlement_currency", "marginAsset", "currency"),
        "base_currency": ("base_currency", "baseAsset"),
        "margin_rate": ("margin_rate", "long_margin_rate"),
        "commission_rate": ("commission_rate", "taker_commission_rate"),
        "exchange_id": ("exchange_id",),
    })
    instrument_contract_value_field = None
    instrument_contract_multiplier_field = None
    instrument_linear_type_field = None
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
