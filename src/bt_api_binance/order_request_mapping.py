"""Provider-owned mapping of neutral order requests to venue arguments."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bt_api_base.contract_errors import CapabilityNotSupportedError
from bt_api_base.order_intent import position_intent


def _wire_decimal(value: Decimal | None) -> str | None:
    """Render an exact, non-scientific decimal for signing and wire transport."""
    return None if value is None else format(value, "f")


def map_order_request(request: Any) -> dict[str, Any]:
    """Map a v1 ``OrderRequest`` to Binance ``make_order`` arguments."""
    offset, closing = position_intent(request)
    if offset in {"close_today", "close_yesterday"} or request.position_id is not None:
        raise CapabilityNotSupportedError(
            "make_order",
            detail="Binance does not support dated or ticket-specific closes",
            definite_reject=True,
        )
    result = {
        "symbol": request.symbol,
        "vol": _wire_decimal(request.quantity),
        "price": _wire_decimal(request.price),
        "order_type": f"{request.side.value}-{request.order_type.value}",
        "offset": offset,
        "post_only": False,
        "client_order_id": request.client_order_id,
        "reduce_only": closing,
        "time_in_force": request.time_in_force,
    }
    if request.position_mode == "dual_side":
        result["position_side"] = request.position_side.upper()
        result.pop("reduce_only")
    elif request.position_mode == "net":
        result["position_side"] = "BOTH"
    elif request.position_side is not None:
        result["position_side"] = request.position_side.upper()
    return result
