"""Host-provided members that Binance mixins rely on.

The REST mixins are combined into :class:`BinanceRequestData`, which supplies
``asset_type`` / ``exchange_name`` / ``_params`` and the request helpers
(``request`` / ``submit`` / ``async_request`` / ``async_callback``).  On their
own the mixins have no such members, so type checking reported ~380
``attr-defined`` errors.

Declaring them here — inside ``if TYPE_CHECKING`` — gives the type checker the
contract **without defining anything at runtime**, so the host's real
implementations are never shadowed through MRO.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["RestHostMixin"]


class RestHostMixin:
    """Type-only declaration of the host surface used by the REST mixins."""

    if TYPE_CHECKING:  # pragma: no cover - never executed
        asset_type: Any
        exchange_name: Any
        public_key: Any
        private_key: Any
        _params: Any

        def request(
            self,
            path: Any,
            params: Any = None,
            body: Any = None,
            extra_data: Any = None,
        ) -> Any: ...

        def async_request(self, path: Any, **kwargs: Any) -> Any: ...

        def submit(self, awaitable: Any, callback: Any = None) -> None: ...

        def async_callback(self, *args: Any, **kwargs: Any) -> None: ...
