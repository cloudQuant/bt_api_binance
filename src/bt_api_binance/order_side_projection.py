"""Binance native order and position-side field selection."""

from __future__ import annotations

from bt_api_base.order_side_projection import legacy_order_side_candidates


def order_side_candidates(row, native, *, position=False):
    """Select S and ps independently before the legacy common aliases."""
    candidates = []
    key = "ps" if position else "S"
    if isinstance(native, dict):
        candidates.append(native.get(key))
    candidates.append(row.get(key))
    candidates.extend(legacy_order_side_candidates(row, native, position=position))
    return candidates


__all__ = ("order_side_candidates",)
