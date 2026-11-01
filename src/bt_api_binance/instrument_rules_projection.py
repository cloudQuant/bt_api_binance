"""BINANCE native instrument-rule projection."""


def project_instrument_rules(row, *, pick, normalized_error):
    NormalizedApiError = normalized_error
    filters = {
        item.get("filterType"): item for item in row.get("filters", []) if isinstance(item, dict)
    }
    lot = filters.get("LOT_SIZE") or filters.get("MARKET_LOT_SIZE") or {}
    price_filter = filters.get("PRICE_FILTER") or {}
    notional_filter = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL") or {}
    required = {
        "contract_value": pick(row, "contract_value", default="1"),
        "contract_multiplier": pick(row, "contract_multiplier", default="1"),
        "price_tick": pick(row, "tick_size", default=price_filter.get("tickSize")),
        "quantity_step": pick(row, "quantity_step", default=lot.get("stepSize")),
        "min_quantity": pick(row, "min_quantity", default=lot.get("minQty")),
    }
    max_quantity_raw = pick(row, "max_quantity", default=lot.get("maxQty"))
    quantity_unit = "base"
    return (required, max_quantity_raw, quantity_unit, notional_filter, False)
