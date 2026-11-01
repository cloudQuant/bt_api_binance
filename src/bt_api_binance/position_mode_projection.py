"""Binance-specific position-mode request projection."""

from __future__ import annotations

from typing import Any

from bt_api_base.contract_errors import CapabilityNotSupportedError


def write_position_mode(feed: Any, exchange_name: str, position_mode: str, extra_data: Any, kwargs: dict[str, Any]) -> Any:
    method = getattr(feed, "change_position_mode", None)
    native_mode = position_mode == "dual_side"
    if not callable(method):
        raise CapabilityNotSupportedError(
            "set_position_mode",
            detail=f"transport=direct; {exchange_name} does not implement this operation",
            definite_reject=True,
        )
    return method(native_mode, extra_data=extra_data, **kwargs)
