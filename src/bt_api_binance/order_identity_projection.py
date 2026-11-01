"""Map neutral order identity to this provider's query/cancel fields."""

from __future__ import annotations

from typing import Any


def project_order_identity(operation: str, request: Any, kwargs: dict[str, Any], default_order_id: Any) -> Any:
    """Use the provider's client-order field when no exchange order ID exists."""
    del operation, default_order_id
    order_id = request.order_id
    if order_id is None:
        kwargs["client_order_id"] = request.client_order_id
    return order_id
