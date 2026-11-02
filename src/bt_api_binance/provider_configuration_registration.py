"""Provider-owned neutral configuration selection for Binance USDⓈ-M SWAP.

This module validates an explicitly supplied route, environment, and
instrument against the provider's installed endpoint contract. It preserves
``profile_ref`` as the caller's exact label; the label is not looked up as an
identity, trusted profile, session readiness proof, or write authorization.
The SDK issues an opaque handle only after the route, instrument, and endpoint
checks pass. The package registers a stateless read-only route owner; a
successful configuration selection does not establish connection, account
readiness, or managed execution capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
import os
from pathlib import Path
import re
import stat
from threading import RLock
from types import MappingProxyType
from typing import Mapping
from weakref import WeakKeyDictionary

from bt_api_base.market_protocol import MarketInstrumentKey
from bt_api_base.provider_configuration_protocol import (
    ProviderConfiguration,
    ProviderConfigurationError,
    ProviderConfigurationHandle,
    ProviderConfigurationRegistryPort,
    ProviderConfigurationRequest,
    ProviderConfigurationSelection,
)


EXCHANGE_NAME = "BINANCE___SWAP"
_SYMBOL = re.compile(r"[A-Z0-9]{3,40}\Z", re.ASCII)
_PROVIDER_ENVIRONMENT = {
    # Backtrader paper/live modes are mapped only to the exact SDK endpoints
    # selected here. This mapping does not grant any execution capability.
    "paper": "demo",
    "live": "production",
    # The provider's own environment values are also accepted verbatim.
    "demo": "demo",
    "production": "production",
}
_CREDENTIAL_ENV_NAMES = {
    "api_key": "BINANCE_API_KEY",
    "api_secret": "BINANCE_PASSWORD",
}


@dataclass(frozen=True)
class _PrivateConfiguration:
    exchange_name: str
    environment: str
    provider_environment: str
    profile_ref: str
    instrument: MarketInstrumentKey
    credential_values: Mapping[str, str] = field(repr=False)


_VAULT: WeakKeyDictionary = WeakKeyDictionary()
_VAULT_LOCK = RLock()


def register_binance_provider_configuration(
    registry: ProviderConfigurationRegistryPort,
) -> None:
    """Register only the exact Binance USDⓈ-M route."""

    try:
        registry.register(EXCHANGE_NAME, _configure_binance)
    except ProviderConfigurationError:
        raise
    except Exception:
        raise ProviderConfigurationError(
            "PROVIDER_CONFIGURATION_REGISTRATION_FAILED"
        ) from None


def _configure_binance(request: ProviderConfigurationRequest) -> ProviderConfiguration:
    if type(request) is not ProviderConfigurationRequest:
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_REQUEST_INVALID")
    if request.exchange_name != EXCHANGE_NAME:
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_ROUTE_INVALID")
    selection = request.selection
    if type(selection) is not ProviderConfigurationSelection:
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")

    provider_environment = _validate_selection(selection)
    _verify_installed_endpoint_contract(provider_environment)
    handle = selection.provider_profile_handle

    if handle is None:
        credential_values = _resolve_credential_inputs(request)
        handle = ProviderConfigurationHandle()
        private = _PrivateConfiguration(
            exchange_name=selection.exchange_name,
            environment=selection.environment,
            provider_environment=provider_environment,
            profile_ref=selection.profile_ref,
            instrument=selection.instrument,
            credential_values=MappingProxyType(credential_values),
        )
        with _VAULT_LOCK:
            _VAULT[handle] = private
    else:
        with _VAULT_LOCK:
            private = _VAULT.get(handle)
        if not _matches_private_selection(private, selection, provider_environment):
            raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
        if (
            request.credential_values
            or request.credential_names
            or request.credential_env_file is not None
        ):
            raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")

    return ProviderConfiguration(
        exchange_name=selection.exchange_name,
        environment=selection.environment,
        profile_ref=selection.profile_ref,
        instrument=selection.instrument,
        selection_receipt={
            "schema": "bt_api.provider_configuration.selection.v1",
            "provider": "binance",
            "provider_environment": provider_environment,
            "endpoint_verified": True,
        },
        provider_configuration_handle=handle,
    )


def _validate_selection(selection: ProviderConfigurationSelection) -> str:
    if selection.exchange_name != EXCHANGE_NAME:
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_ROUTE_INVALID")
    provider_environment = _PROVIDER_ENVIRONMENT.get(selection.environment)
    if provider_environment is None:
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
    instrument = selection.instrument
    if (
        type(instrument) is not MarketInstrumentKey
        or instrument.provider != "binance"
        or instrument.venue != "BINANCE"
        or instrument.environment != selection.environment
        or instrument.product_type != "USDM_PERPETUAL"
        or instrument.instrument_id != instrument.native_symbol
        or _SYMBOL.fullmatch(instrument.native_symbol) is None
    ):
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
    return provider_environment


def _verify_installed_endpoint_contract(provider_environment: str) -> None:
    """Verify the installed Binance package endpoints without opening caller files."""

    try:
        from bt_api_binance.environment import configure_environment, verify_environment
        from bt_api_binance.exchange_data.binance_exchange_data import (
            BinanceExchangeData,
            BinanceExchangeDataSwap,
        )

        # Avoid the subclass constructor's configuration path. The package's
        # own _load_from_config resolves only its installed public YAML catalog.
        params = BinanceExchangeDataSwap.__new__(BinanceExchangeDataSwap)
        BinanceExchangeData.__init__(params)
        if not params._load_from_config("swap"):
            raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
        selected = configure_environment(params, {"environment": provider_environment})
        proof = verify_environment(selected)
    except ProviderConfigurationError:
        raise
    except Exception:
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE") from None
    if (
        type(proof) is not dict
        or proof.get("verified") is not True
        or proof.get("environment") != provider_environment
    ):
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")


def _resolve_credential_inputs(request: ProviderConfigurationRequest) -> dict[str, str]:
    """Resolve only this package's allowlisted secret roles into its private vault."""

    values = dict(request.credential_values)
    names = dict(request.credential_names)
    allowed_roles = frozenset(_CREDENTIAL_ENV_NAMES)
    if any(type(role) is not str or role not in allowed_roles for role in values):
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_REQUEST_INVALID")
    if any(type(role) is not str or role not in allowed_roles for role in names):
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_REQUEST_INVALID")
    if values and names:
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
    if values and set(values) != allowed_roles:
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
    if names and (
        set(names) != allowed_roles
        or any(names[role] != _CREDENTIAL_ENV_NAMES[role] for role in allowed_roles)
    ):
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
    if request.credential_env_file is not None and not names:
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
    if not names:
        resolved = values
    else:
        source = (
            _read_env_file(request.credential_env_file)
            if request.credential_env_file is not None
            else os.environ
        )
        resolved = {
            role: source.get(environment_name)
            for role, environment_name in names.items()
        }
        if any(type(value) is not str for value in resolved.values()):
            raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
    for value in resolved.values():
        if (
            type(value) is not str
            or not value
            or value != value.strip()
            or len(value) > 512
            or not value.isascii()
            or not value.isprintable()
        ):
            raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
    return resolved


def _read_env_file(path: Path) -> dict[str, str]:
    """Read one explicit, bounded, regular UTF-8 env file without following links."""

    try:
        before = path.lstat()
        attributes = getattr(before, "st_file_attributes", 0)
        reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (
            stat.S_ISLNK(before.st_mode)
            or attributes & reparse_point
            or not stat.S_ISREG(before.st_mode)
            or before.st_size > 65_536
        ):
            raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
            payload = stream.read(65_537)
            after = os.fstat(stream.fileno())
        if (
            len(payload) > 65_536
            or (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        ):
            raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE")
        text = payload.decode("utf-8-sig", errors="strict")
        from dotenv import dotenv_values

        parsed = dotenv_values(stream=StringIO(text), interpolate=False)
    except ProviderConfigurationError:
        raise
    except Exception:
        raise ProviderConfigurationError("PROVIDER_CONFIGURATION_INPUT_UNAVAILABLE") from None
    return {
        name: value
        for name, value in parsed.items()
        if type(name) is str and type(value) is str
    }


def _matches_private_selection(
    private: object,
    selection: ProviderConfigurationSelection,
    provider_environment: str,
) -> bool:
    return (
        type(private) is _PrivateConfiguration
        and private.exchange_name == selection.exchange_name
        and private.environment == selection.environment
        and private.provider_environment == provider_environment
        and private.profile_ref == selection.profile_ref
        and private.instrument == selection.instrument
    )


__all__ = ["EXCHANGE_NAME", "register_binance_provider_configuration"]
