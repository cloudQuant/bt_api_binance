"""Binance-specific normalization choices used by the unified SDK."""

from types import MappingProxyType

from bt_api_base.normalization_policy import LegacyNormalizationPolicy
from bt_api_base.order_identity_fields import NEUTRAL_ORDER_IDENTITY_FIELDS
from bt_api_base.provider_order_source_aliases import build_provider_order_source_aliases
from bt_api_base.order_provenance_fields import (
    NEUTRAL_ORDER_SOURCE_FIELDS,
    PROVIDER_SCOPED_ORDER_PROVENANCE_SCHEMAS,
)

from .funding_schedule import complete_funding_schedule, select_funding_payload


def _instrument_metadata_defaults(row, *, pick):
    """Translate Binance filter rows into neutral instrument defaults."""
    filters = {item["filterType"]: item for item in row.get("filters", [])}
    lot = filters.get("LOT_SIZE", {})
    floor = filters.get("MIN_NOTIONAL", filters.get("NOTIONAL", {}))
    return {
        "quantity_step": lot.get("stepSize"),
        "min_size": lot.get("minQty"),
        "max_size": lot.get("maxQty"),
        "min_notional": pick(floor, "notional", "minNotional"),
        "tick_size": filters.get("PRICE_FILTER", {}).get("tickSize"),
    }


class BinanceNormalizationPolicy(LegacyNormalizationPolicy):
    trade_id_fields = ("trade_id", "fill_id", "deal_id", "id")
    tick_trading_day_fields = ("trading_day",)
    tick_action_day_fields = ("action_day",)
    risk_position_dimensions_require_projection = False
    # Preserve the prior acknowledgement contract pending venue review.
    position_mode_ack_code = "200"
    position_mode_placement_guard_required = True
    # Preserve the previous common aliases until venue-specific coverage is reviewed.
    order_status_fields = ("status", "order_status", "state")
    trade_fee_fields = ("fee_amount", "fee", "trade_fee", "commission")
    identity_fields = MappingProxyType({
        **NEUTRAL_ORDER_IDENTITY_FIELDS,
        'side': ('side', 'order_side', 'trade_side', 'S'),
        'position_side': ('position_side', 'positionSide', 'ps'),
        'position_mode': ('position_mode', 'positionMode', 'dualSidePosition'),
    })
    order_provenance_schemas = PROVIDER_SCOPED_ORDER_PROVENANCE_SCHEMAS
    order_provenance_source_fields = NEUTRAL_ORDER_SOURCE_FIELDS | frozenset({
        'S',
        'clientOrderId',
        'executedQty',
        'orderId',
        'origQty',
        'positionSide',
        'ps',
        'tradeId',
    })
    (
        risk_order_source_aliases,
        group_order_source_aliases,
        group_fill_source_aliases,
    ) = build_provider_order_source_aliases(
        order_provenance_source_fields,
        risk_order_native_aliases={
            "provider_order_id": ("orderId",),
            "client_order_id": ("clientOrderId",),
            "status": ("status",),
            "filled_quantity": ("executedQty",),
            "quantity": ("origQty",),
            "instrument": ("symbol",),
            "side": ("side", "S"),
            "price": ("price",),
            "position_side": ("positionSide", "ps"),
        },
        group_order_native_aliases={
            "order_id": ("orderId",),
            "client_order_id": ("clientOrderId",),
            "status": ("status",),
            "filled": ("executedQty",),
            "quantity": ("origQty",),
            "instrument": ("symbol",),
            "side": ("side", "S"),
            "price": ("price",),
        },
        group_fill_native_aliases={
            "trade_id": ("tradeId", "id"),
            "order_id": ("orderId",),
            "instrument": ("symbol",),
            "side": ("side",),
            "quantity": ("qty",),
            "price": ("price",),
        },
    )
    # Binance user-stream order updates carry identity inside "o".
    identity_nested_field = "o"
    nested_identity_fields = MappingProxyType({"side": ("S",), "position_side": ("ps",)})
    instrument_metadata_defaults = staticmethod(_instrument_metadata_defaults)
    # Preserve the former shared response alias pending venue-specific review.
    response_error_item_fields = ("sCode",)
    # This provider uses the native symbols collection.
    result_collection_fields = ("data", "symbols")
    complete_funding_schedule = staticmethod(complete_funding_schedule)
    select_funding_payload = staticmethod(select_funding_payload)

    exchange_time_fields = (
        "exchange_time", "timestamp", "server_time", "E", "T", "event_time",
        "event_time_utc", "timestamp_ms",
    )
    funding_rate_fields = ("funding_rate", "fundingRate", "lastFundingRate", "rate")
    funding_time_fields = ("nextFundingTime", "fundingTime")
    funding_interval_hours_fields = ("fundingIntervalHours",)
    funding_interval_start_fields = ("fundingTime",)
    funding_interval_end_fields = ("nextFundingTime",)
    funding_raw_fields = (
        "funding_rate", "fundingRate", "lastFundingRate", "rate", "next_funding_time",
        "fundingTime", "nextFundingTime", "settlement_interval_seconds",
        "funding_interval_seconds", "fundingIntervalHours",
    )
    fee_maker_fields = ("maker_rate", "makerCommissionRate", "makerCommission", "maker")
    fee_taker_fields = ("taker_rate", "takerCommissionRate", "takerCommission", "taker")
    fee_currency_fields = ("currency", "commissionAsset")
    reconcile_terminal_order_commission = True
    base_symbol_fields = (
        "symbol", "symbol_name", "instrument", "instrument_id", "data_name", "trade_symbol",
    )
    default_multiplier = 1.0
    permission_fields = ("trading_permissions",)
    can_trade_fields = ("can_trade", "canTrade")
    order_statuses = MappingProxyType({
        "new": "accepted", "open": "accepted", "working": "accepted",
        "submitted": "submitted", "accepted": "accepted", "pending": "submitted",
        "partial": "partial", "partially_filled": "partial", "partial_filled": "partial",
        "filled": "completed", "completed": "completed", "cancelled": "canceled",
        "canceled": "canceled", "expired": "expired", "expired_in_match": "expired",
        "rejected": "rejected", "unknown": "unknown", "local_pending": "submitted",
    })
    position_mode_boolean_field = "dualSidePosition"
    position_mode_fields = ("position_mode", "positionMode")
    position_mode_aliases = MappingProxyType({
        "oneway": "net", "one_way": "net", "hedge": "dual_side", "hedge_mode": "dual_side",
    })
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
    instrument_spec_fields = MappingProxyType({
        "symbol": ("symbol", "symbol_name"),
        "base_currency": ("base_currency", "baseAsset"),
        "quote_currency": ("quote_currency", "quoteAsset", "marginAsset"),
        "asset_type": ("asset_type",),
        "contract_type": ("contract_type", "contractType"),
    })
    instrument_spec_linear_type_field = None
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
    instrument_perpetual_type_field = "contractType"
    event_id_fields = ("event_id", "trade_id", "tradeId", "fill_id", "order_id", "orderId")
    event_audit_fields = (
        "sequence", "sequence_id", "previous_sequence", "pu", "U", "u",
        "checksum", "action", "ts", "E", "T",
    )
    orderbook_sequence_fields = ("sequence", "sequence_id", "update_id", "lastUpdateId", "u")
    orderbook_previous_fields = ("previous_sequence", "prev_sequence", "pu")
    orderbook_delta_predecessor_fields = ("pu",)


class BinanceSwapNormalizationPolicy(BinanceNormalizationPolicy):
    zero_balance_currency = "USDT"


def normalization_policy(exchange_name):
    if exchange_name == "BINANCE___SWAP":
        return BinanceSwapNormalizationPolicy()
    return BinanceNormalizationPolicy()


__all__ = ("normalization_policy",)
