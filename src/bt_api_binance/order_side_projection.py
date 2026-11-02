"""Binance native order and position-side field selection."""
from __future__ import annotations

from bt_api_base.order_side_projection import selected_order_side_candidates


def order_side_candidates(row, *, position=False):
    key = "ps" if position else "S"
    native = row.get("o")
    candidates = [native.get(key)] if isinstance(native, dict) else []
    candidates.append(row.get(key))
    candidates.extend(selected_order_side_candidates(
        row, position=position,
        side_fields=("side", "order_side", "trade_side"),
        position_side_fields=("position_side", "positionSide"),
    ))
    return candidates


__all__ = ("order_side_candidates",)
