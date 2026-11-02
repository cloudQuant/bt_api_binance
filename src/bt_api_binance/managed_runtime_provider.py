"""Provider-owned read-only direct runtime construction for Binance SWAP.

The configuration handle is consumed from this package's private vault.  The
result keeps the raw BtApi and credentials inside the SDK/provider boundary;
it is a route owner, not a live-session or account-readiness proof.  This
module deliberately has no managed-write path.
"""

from __future__ import annotations

from collections.abc import Mapping
from threading import Lock
from typing import Any, Callable

from bt_api_base.market_protocol import MarketInstrumentKey
from bt_api_base.managed_runtime_protocol import (
    ManagedRuntimeContractError,
    ManagedRuntimeFactoryRegistryPort,
    ManagedRuntimeProviderProduct,
    SelectedManagedRuntimeRoute,
    ReadOnlyRouteOwnerCloseError,
    ReadOnlyRouteOwnerProduct,
    ReadOnlyRouteOwnerRegistryPort,
    SelectedReadOnlyRoute,
)
from bt_api_base.provider_configuration_protocol import (
    ProviderConfiguration,
    ProviderConfigurationHandle,
)

from .feeds.swap import BinanceRequestDataSwap
from .provider_configuration_registration import (
    EXCHANGE_NAME,
    _PrivateConfiguration,
    _VAULT,
    _VAULT_LOCK,
)

_PROVIDER_ENVIRONMENT = {
    "paper": "demo",
    "live": "production",
    "demo": "demo",
    "production": "production",
}
_CREDENTIAL_ROLES = frozenset({"api_key", "api_secret"})


class BinanceManagedRuntimeProviderError(RuntimeError):
    """Finite, value-free failure from the Binance runtime provider."""

    _CODES = frozenset(
        {
            "binance_runtime_configuration_invalid",
            "binance_runtime_configuration_unavailable",
            "binance_runtime_route_invalid",
            "binance_runtime_api_unavailable",
            "binance_runtime_feed_unavailable",
            "binance_runtime_environment_unverified",
            "binance_runtime_close_unconfirmed",
        }
    )

    def __init__(self, code: str) -> None:
        self.code = code if type(code) is str and code in self._CODES else (
            "binance_runtime_api_unavailable"
        )
        super().__init__(self.code)


class BinanceReadOnlyRouteOwnerV1:
    """Private owner for one configured REST route; repr never contains values."""

    __slots__ = (
        "__api",
        "__feed",
        "__configuration",
        "__environment",
        "__lock",
        "__close_attempted",
    )

    def __init__(
        self,
        api: object,
        feed: object,
        configuration: ProviderConfiguration,
    ) -> None:
        self.__api = api
        self.__feed = feed
        self.__configuration = configuration
        self.__environment = _PROVIDER_ENVIRONMENT.get(configuration.environment)
        self.__lock = Lock()
        self.__close_attempted = False

    def __repr__(self) -> str:
        return "<Binance read-only route owner>"

    def _internal_api_for_factory(
        self,
        configuration: ProviderConfiguration,
        *,
        api_type: type,
    ) -> object:
        if not self._verify_exact_route(configuration, api_type=api_type):
            raise BinanceManagedRuntimeProviderError("binance_runtime_route_invalid")
        return self.__api

    def _verify_exact_route(self, configuration: object, *, api_type: type) -> bool:
        if (
            type(configuration) is not ProviderConfiguration
            or configuration is not self.__configuration
            or configuration.exchange_name != EXCHANGE_NAME
            or type(configuration.instrument) is not MarketInstrumentKey
            or configuration.instrument.provider != "binance"
            or configuration.instrument.venue != "BINANCE"
            or configuration.instrument.product_type != "USDM_PERPETUAL"
            or type(self.__api) is not api_type
            or type(self.__feed) is not BinanceRequestDataSwap
            or self.__environment not in {"demo", "production"}
        ):
            return False
        try:
            if self.__api.list_exchanges() != [EXCHANGE_NAME]:
                return False
            if self.__api.exchange_feeds.get(EXCHANGE_NAME) is not self.__feed:
                return False
            proof = self.__api.get_environment_info(EXCHANGE_NAME)
        except Exception:
            return False
        return (
            type(proof) is dict
            and proof.get("verified") is True
            and proof.get("environment") == self.__environment
            and proof.get("simulated") is (self.__environment == "demo")
        )

    def close(self) -> None:
        """Close this internally owned API at most once; never retry uncertainty."""

        with self.__lock:
            if self.__close_attempted:
                return
            self.__close_attempted = True
        try:
            self.__api.close()
        except Exception:
            raise ReadOnlyRouteOwnerCloseError() from None


def _build_read_only_route_owner(
    configuration: ProviderConfiguration,
    *,
    api_factory: Callable[..., object],
) -> BinanceReadOnlyRouteOwnerV1:
    """Consume one exact provider handle and construct an SDK-owned BtApi route."""

    if not callable(api_factory):
        raise BinanceManagedRuntimeProviderError("binance_runtime_api_unavailable")
    provider_environment, credentials = _consume_private_configuration(configuration)
    route_options: dict[str, Any] = {
        "api_key": credentials["api_key"],
        "api_secret": credentials["api_secret"],
        "environment": provider_environment,
        "exchange_name": EXCHANGE_NAME,
        "asset_type": "SWAP",
        # Do not open the private account WebSocket as a side effect of a
        # read-only REST route.
        "subscribe_account": False,
    }
    api = None
    owner = None
    try:
        api = api_factory(exchange_kwargs={EXCHANGE_NAME: route_options}, debug=False)
        if not callable(getattr(api, "list_exchanges", None)):
            raise BinanceManagedRuntimeProviderError("binance_runtime_api_unavailable")
        feed = getattr(api, "exchange_feeds", {}).get(EXCHANGE_NAME)
        if type(feed) is not BinanceRequestDataSwap:
            raise BinanceManagedRuntimeProviderError("binance_runtime_feed_unavailable")
        owner = BinanceReadOnlyRouteOwnerV1(api, feed, configuration)
        if not owner._verify_exact_route(configuration, api_type=api_factory):
            raise BinanceManagedRuntimeProviderError(
                "binance_runtime_environment_unverified"
            )
        return owner
    except BinanceManagedRuntimeProviderError:
        if owner is not None:
            owner.close()
        elif api is not None:
            try:
                api.close()
            except Exception:
                raise ReadOnlyRouteOwnerCloseError() from None
        raise
    except Exception:
        if owner is not None:
            owner.close()
        elif api is not None:
            try:
                api.close()
            except Exception:
                raise ReadOnlyRouteOwnerCloseError() from None
        raise BinanceManagedRuntimeProviderError("binance_runtime_api_unavailable") from None
    finally:
        # Strings remain held by BtApi/feed for request signing. This only
        # drops this builder's temporary references; it is not memory erasure.
        credentials.clear()


def _consume_private_configuration(
    configuration: object,
) -> tuple[str, dict[str, str]]:
    if (
        type(configuration) is not ProviderConfiguration
        or configuration.exchange_name != EXCHANGE_NAME
        or type(configuration.instrument) is not MarketInstrumentKey
        or configuration.instrument.provider != "binance"
        or configuration.instrument.venue != "BINANCE"
        or configuration.instrument.environment != configuration.environment
        or configuration.instrument.product_type != "USDM_PERPETUAL"
        or type(configuration.provider_configuration_handle) is not ProviderConfigurationHandle
    ):
        raise BinanceManagedRuntimeProviderError("binance_runtime_configuration_invalid")
    expected_environment = _PROVIDER_ENVIRONMENT.get(configuration.environment)
    if expected_environment not in {"demo", "production"}:
        raise BinanceManagedRuntimeProviderError("binance_runtime_configuration_invalid")
    with _VAULT_LOCK:
        private = _VAULT.get(configuration.provider_configuration_handle)
        if (
            type(private) is not _PrivateConfiguration
            or private.exchange_name != EXCHANGE_NAME
            or private.environment != configuration.environment
            or private.provider_environment != expected_environment
            or private.profile_ref != configuration.profile_ref
            or private.instrument != configuration.instrument
            or not isinstance(private.credential_values, Mapping)
            or set(private.credential_values) != _CREDENTIAL_ROLES
        ):
            raise BinanceManagedRuntimeProviderError(
                "binance_runtime_configuration_unavailable"
            )
        credentials = dict(private.credential_values)
        if any(
            type(value) is not str
            or not value
            or value != value.strip()
            or len(value) > 512
            or not value.isascii()
            or not value.isprintable()
            for value in credentials.values()
        ):
            raise BinanceManagedRuntimeProviderError(
                "binance_runtime_configuration_unavailable"
            )
        _VAULT.pop(configuration.provider_configuration_handle, None)
    return expected_environment, credentials


class _BinanceReadOnlyRouteOwnerFactory:
    def __call__(self, route: SelectedReadOnlyRoute, /) -> ReadOnlyRouteOwnerProduct:
        if (
            type(route) is not SelectedReadOnlyRoute
            or route.exchange_name != EXCHANGE_NAME
            or route.configuration.exchange_name != EXCHANGE_NAME
        ):
            raise BinanceManagedRuntimeProviderError("binance_runtime_route_invalid")
        try:
            owner = _build_read_only_route_owner(
                route.configuration,
                api_factory=route.api_factory,
            )
        except BinanceManagedRuntimeProviderError:
            raise
        try:
            api = owner._internal_api_for_factory(
                route.configuration,
                api_type=route.api_factory,
            )
            return ReadOnlyRouteOwnerProduct(
                exchange_name=EXCHANGE_NAME,
                api=api,
                close_route=owner.close,
                route_binding_verified=True,
            )
        except Exception:
            owner.close()
            raise BinanceManagedRuntimeProviderError(
                "binance_runtime_environment_unverified"
            ) from None


class _BinanceBoundReadOnlyRuntimeFactory:
    """Validate the exact provider owner for an SDK-supplied read-only route."""

    def __call__(self, route: SelectedManagedRuntimeRoute, /) -> ManagedRuntimeProviderProduct:
        if (
            type(route) is not SelectedManagedRuntimeRoute
            or route.exchange_name != EXCHANGE_NAME
            or route.configuration.exchange_name != EXCHANGE_NAME
        ):
            raise ManagedRuntimeContractError("MANAGED_RUNTIME_ROUTE_INVALID")
        if route.access_mode != "read_only":
            raise ManagedRuntimeContractError("MANAGED_RUNTIME_WRITE_UNAVAILABLE")
        owner = route.runtime_binding.runtime_owner
        if type(owner) is not BinanceReadOnlyRouteOwnerV1 or type(route.api_factory) is not type:
            raise ManagedRuntimeContractError("MANAGED_RUNTIME_BINDING_UNAVAILABLE")
        try:
            api = owner._internal_api_for_factory(route.configuration, api_type=route.api_factory)
        except BinanceManagedRuntimeProviderError as exc:
            mapped = {
                "binance_runtime_configuration_invalid": "MANAGED_RUNTIME_CONFIGURATION_INVALID",
                "binance_runtime_configuration_unavailable": "MANAGED_RUNTIME_BINDING_UNAVAILABLE",
                "binance_runtime_route_invalid": "MANAGED_RUNTIME_BINDING_ROUTE_MISMATCH",
                "binance_runtime_api_unavailable": "MANAGED_RUNTIME_BINDING_UNAVAILABLE",
                "binance_runtime_feed_unavailable": "MANAGED_RUNTIME_BINDING_UNVERIFIED",
                "binance_runtime_environment_unverified": "MANAGED_RUNTIME_BINDING_UNVERIFIED",
                "binance_runtime_close_unconfirmed": "MANAGED_RUNTIME_CLOSE_FAILED",
            }
            raise ManagedRuntimeContractError(
                mapped.get(exc.code, "MANAGED_RUNTIME_COMPOSITION_FAILED")
            ) from None
        except Exception:
            raise ManagedRuntimeContractError("MANAGED_RUNTIME_BINDING_UNVERIFIED") from None
        if type(api) is not route.api_factory:
            raise ManagedRuntimeContractError("MANAGED_RUNTIME_FACADE_INVALID")
        return ManagedRuntimeProviderProduct(
            api=api, close_route=owner.close,
            runtime_binding_verified=False, operator_grant_verified=False,
            route_binding_verified=True,
        )


def register_binance_managed_runtime_provider(registry: ManagedRuntimeFactoryRegistryPort) -> None:
    """Register only this provider's bound read-only route."""
    if not isinstance(registry, ManagedRuntimeFactoryRegistryPort):
        raise ManagedRuntimeContractError("MANAGED_RUNTIME_FACTORY_INVALID")
    try:
        registry.register(EXCHANGE_NAME, _BinanceBoundReadOnlyRuntimeFactory())
    except ManagedRuntimeContractError:
        raise
    except Exception:
        raise ManagedRuntimeContractError("MANAGED_RUNTIME_PROVIDER_REGISTRATION_FAILED") from None


def register_binance_read_only_route_owner(
    registry: ReadOnlyRouteOwnerRegistryPort,
) -> None:
    """Register only the stateless Binance USD-M route owner factory."""

    if not isinstance(registry, ReadOnlyRouteOwnerRegistryPort):
        raise BinanceManagedRuntimeProviderError("binance_runtime_route_invalid")
    try:
        registry.register(EXCHANGE_NAME, _BinanceReadOnlyRouteOwnerFactory())
    except Exception:
        raise BinanceManagedRuntimeProviderError(
            "binance_runtime_route_invalid"
        ) from None


__all__ = [
    "BinanceManagedRuntimeProviderError",
    "BinanceReadOnlyRouteOwnerV1",
    "register_binance_managed_runtime_provider",
    "register_binance_read_only_route_owner",
]
