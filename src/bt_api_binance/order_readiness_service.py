"""Binance-owned collection and projection of read-only order readiness."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from bt_api_binance.order_request_mapping import build_order_readiness_normalizer


def collect_order_readiness(backend: Any, exchange_name: str, symbol: str, quantity_native: Any, *,
                            margin_mode: str, position_mode: str | None, account_config: Any,
                            extra_data: Any, normalizers: dict[str, Any]) -> dict[str, Any]:
    normalize = build_order_readiness_normalizer(
        rows=normalizers["rows"], pick=normalizers["pick"],
        _trading_permissions=normalizers["trading_permissions"],
        instrument_spec=normalizers["instrument_spec"],
    )
    def options() -> Any:
        return deepcopy(extra_data)

    exchange_info = backend.get_exchange_info(exchange_name, symbol, extra_data=options())

    def optional_read(name: str, *args: Any, **read_kwargs: Any) -> Any:
        method = getattr(backend, name, None)
        if not callable(method):
            return None
        try:
            return method(*args, **read_kwargs)
        except Exception:
            return None

    position_mode_info = optional_read("get_position_mode", exchange_name, extra_data=options())
    initial = normalize(
        exchange_name, symbol, quantity_native, margin_mode=margin_mode,
        expected_position_mode=position_mode, account_config=account_config,
        exchange_info=exchange_info, position_mode_info=position_mode_info,
    )
    if initial["definite_failure"]:
        return initial
    symbol_config = optional_read("get_symbol_config", exchange_name, symbol, extra_data=options())
    leverage_info = optional_read(
        "get_leverage_info", exchange_name, symbol, margin_mode=margin_mode, extra_data=options()
    )
    max_size = optional_read(
        "get_max_size", exchange_name, symbol, margin_mode=margin_mode, extra_data=options()
    )
    return normalize(
        exchange_name, symbol, quantity_native, margin_mode=margin_mode,
        expected_position_mode=position_mode, account_config=account_config,
        exchange_info=exchange_info, position_mode_info=position_mode_info,
        symbol_config=symbol_config, leverage_info=leverage_info, max_size=max_size,
    )
