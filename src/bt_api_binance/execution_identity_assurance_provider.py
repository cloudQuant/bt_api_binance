"""Provider-issued execution-credential assurance for Binance USDⓈ-M routes.

The provider binds its proof to the SDK-issued execution route and to one
physical, signed account-configuration REST exchange. Raw response data and
credentials never enter receipt DTOs or public diagnostics. This proves only
that the selected credential was accepted for that request; it does not
identify a physical account or authorize execution.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

from bt_api_base.containers.requestdatas.request_data import RequestData
from bt_api_base.execution_identity_protocol import (
    ExecutionCredentialRequestContextPort,
    ExecutionIdentityAssurance,
    ExecutionIdentityAssurancePort,
    ExecutionIdentityAssuranceProviderRegistryPort,
    ExecutionIdentityAssuranceUnavailable,
    SelectedExecutionIdentityRoute,
)
from bt_api_base.execution_request_receipt_protocol import (
    ExecutionCredentialRequestAttemptContext,
    ExecutionCredentialRequestOpaqueRef,
    ExecutionCredentialRequestReceipt,
    ExecutionCredentialRequestReceiptIssuerPort,
    ExecutionCredentialRequestReceiptUnavailable,
    ExecutionCredentialRequestSuccessCategory,
    ExecutionCredentialRequestTransport,
    ExecutionCredentialRequestTransportObservation,
)
from bt_api_base.feeds.feed import Feed
from bt_api_base.feeds.http_client import HttpClient, httpx

from .exchange_data.binance_exchange_data import BinanceExchangeDataSwap
from .feeds.request_base import BinanceRequestData, _CredentialBinding
from .feeds.swap import BinanceRequestDataSwap
from .provider_configuration_registration import EXCHANGE_NAME

_PROVIDER = "binance"
_ENVIRONMENTS = frozenset({"demo", "production"})
_IDENTITY_TTL = timedelta(seconds=30)
_REQUEST_RECEIPT_TTL = timedelta(seconds=30)
_MAX_RECEIPTS = 128
_MAX_ACCOUNT_CONFIG_RESPONSE_BYTES = 4 * 1024 * 1024
_ACCOUNT_CONFIG_PATH = "GET /fapi/v1/accountConfig"
_ACCOUNT_CONFIG_OPERATION = "get_account_config"
_REQUIRED_CONFIG_FIELDS = ("canTrade", "canDeposit", "canWithdraw", "dualSidePosition")


class _BinanceExecutionIdentityAssurancePort(
    ExecutionIdentityAssurancePort,
    ExecutionCredentialRequestReceiptIssuerPort,
):
    """One selected feed, same-attempt receipt issuer, and owner context."""

    __slots__ = (
        "__route",
        "__context",
        "__credential_binding",
        "__source_ref",
        "__lineage_ref",
        "__issuer_ref",
        "__expiry_policy_ref",
        "__issued",
        "__pending_observations",
        "__receipts",
        "__lock",
    )

    def __init__(self, route: SelectedExecutionIdentityRoute) -> None:
        self.__route = route
        self.__context = route.request_receipt_context
        self.__source_ref = "binance-usdm-account-config"
        try:
            self.__credential_binding = route.client._capture_credential_binding()
            self.__lineage_ref = route.client.execution_credential_lineage_ref()
        except Exception:
            raise _unavailable() from None
        if (
            type(self.__credential_binding) is not _CredentialBinding
            or type(self.__lineage_ref) is not ExecutionCredentialRequestOpaqueRef
            or self.__credential_binding.lineage_ref is not self.__lineage_ref
        ):
            raise _unavailable()
        self.__issuer_ref = ExecutionCredentialRequestOpaqueRef()
        self.__expiry_policy_ref = ExecutionCredentialRequestOpaqueRef()
        self.__issued: OrderedDict[
            int,
            tuple[
                ExecutionIdentityAssurance,
                str,
                ExecutionCredentialRequestReceipt,
                ExecutionCredentialRequestTransportObservation,
            ],
        ] = OrderedDict()
        self.__pending_observations: OrderedDict[
            int,
            tuple[
                ExecutionCredentialRequestTransportObservation,
                RequestData,
                int,
                ExecutionCredentialRequestAttemptContext,
                ExecutionCredentialRequestContextPort,
                tuple[object, ...],
            ],
        ] = OrderedDict()
        self.__receipts: OrderedDict[
            int,
            tuple[
                ExecutionCredentialRequestReceipt,
                ExecutionCredentialRequestTransportObservation,
                ExecutionCredentialRequestAttemptContext,
                ExecutionCredentialRequestContextPort,
                float,
                tuple[object, ...],
                tuple[object, ...],
            ],
        ] = OrderedDict()
        self.__lock = threading.RLock()

    def assure_execution_identity(self) -> ExecutionIdentityAssurance:
        """Return assurance only after one exact signed response and receipt."""

        assurance, _receipt = self.assure_execution_identity_with_receipt()
        return assurance

    def assure_execution_identity_with_receipt(
        self,
    ) -> tuple[ExecutionIdentityAssurance, ExecutionCredentialRequestReceipt]:
        """Synchronously return assurance and receipt for the same REST attempt.

        This extension intentionally has no legacy fallback. Missing selected
        route context, a non-pinned lineage marker, a failed response, or an
        unsupported response shape is unavailable.
        """

        observation, receipt = self.__request_authenticated_account_configuration()
        observed_at = receipt.issued_at_utc
        expires_at = min(receipt.expires_at_utc, observed_at + _IDENTITY_TTL)
        if expires_at <= observed_at:
            raise _unavailable()
        try:
            assurance = ExecutionIdentityAssurance(
                exchange_name=self.__route.exchange_name,
                provider=self.__route.provider,
                environment=self.__route.environment,
                account_ref=self.__route.account_ref,
                identity_binding="authenticated_credential",
                source_ref=self.__source_ref,
                session_generation=self.__route.session_generation,
                observed_at_utc=observed_at,
                expires_at_utc=expires_at,
                receipt_ref="binance-auth-" + uuid.uuid4().hex,
            )
            digest = _assurance_digest(assurance)
        except Exception:
            self.__revoke_receipt(receipt)
            raise _unavailable() from None
        with self.__lock:
            self.__issued[id(assurance)] = (assurance, digest, receipt, observation)
            self.__issued.move_to_end(id(assurance))
            while len(self.__issued) > _MAX_RECEIPTS:
                self.__issued.popitem(last=False)
        return assurance, receipt

    def validate_execution_identity(
        self,
        assurance: ExecutionIdentityAssurance,
        *,
        now_utc: datetime,
    ) -> bool:
        if type(assurance) is not ExecutionIdentityAssurance or not _is_utc(now_utc):
            return False
        with self.__lock:
            issued = self.__issued.get(id(assurance))
        if issued is None or issued[0] is not assurance:
            return False
        try:
            ExecutionIdentityAssurance.__post_init__(assurance)
            provider_now = datetime.now(timezone.utc)
            if (
                _assurance_digest(assurance) != issued[1]
                or not _assurance_matches_route(assurance, self.__route)
                or now_utc < assurance.observed_at_utc
                or now_utc >= assurance.expires_at_utc
                or provider_now < assurance.observed_at_utc
                or provider_now >= assurance.expires_at_utc
            ):
                return False
            self.__require_exact_route()
            receipt, observation = issued[2], issued[3]
            return self.validate_execution_credential_request_receipt(
                receipt,
                expected_observation=observation,
                expected_exchange_name=self.__route.exchange_name,
                expected_provider=self.__route.provider,
                expected_environment=self.__route.environment,
                expected_transport=ExecutionCredentialRequestTransport.REST,
                expected_operation=_ACCOUNT_CONFIG_OPERATION,
                expected_credential_lineage_ref=self.__lineage_ref,
                expected_selected_route_ref=observation.selected_route_ref,
                expected_owner_generation_ref=observation.owner_generation_ref,
                expected_owner_lease_ref=observation.owner_lease_ref,
                expected_session_generation=self.__route.session_generation,
                expected_fencing_epoch=self.__route.fencing_epoch,
            ) is True
        except Exception:
            return False

    def __require_exact_route(self) -> None:
        route = self.__route
        try:
            SelectedExecutionIdentityRoute.__post_init__(route)
        except Exception:
            raise _unavailable() from None
        context = getattr(route, "request_receipt_context", None)
        if (
            type(route) is not SelectedExecutionIdentityRoute
            or route.exchange_name != EXCHANGE_NAME
            or route.provider != _PROVIDER
            or route.environment not in _ENVIRONMENTS
            or route.identity_binding != "authenticated_credential"
            or type(route.client) is not BinanceRequestDataSwap
            or type(route.fencing_epoch) is not int
            or route.fencing_epoch <= 0
            or route.ledger_binding is None
            or not route.account_ref
            or not route.session_generation
            or context is not self.__context
            or not isinstance(context, ExecutionCredentialRequestContextPort)
        ):
            raise _unavailable()
        client = route.client
        if not _exact_feed_transport(client):
            raise _unavailable()
        if client.exchange_name != EXCHANGE_NAME or client.asset_type != "SWAP":
            raise _unavailable()
        try:
            marker = client.execution_credential_lineage_ref()
            binding = client._capture_credential_binding()
            environment = client.get_environment_info()
        except Exception:
            raise _unavailable() from None
        if (
            type(marker) is not ExecutionCredentialRequestOpaqueRef
            or marker is not self.__lineage_ref
            or type(binding) is not _CredentialBinding
            or binding is not self.__credential_binding
            or binding.lineage_ref is not marker
            or type(environment) is not dict
            or environment.get("verified") is not True
            or type(environment.get("environment")) is not str
            or environment.get("environment") != route.environment
            or type(environment.get("simulated")) is not bool
            or environment.get("simulated") is not (route.environment == "demo")
        ):
            raise _unavailable()

    def __request_receipt_context(self) -> ExecutionCredentialRequestContextPort:
        self.__require_exact_route()
        return self.__context

    def __request_authenticated_account_configuration(
        self,
    ) -> tuple[
        ExecutionCredentialRequestTransportObservation,
        ExecutionCredentialRequestReceipt,
    ]:
        try:
            self.__require_exact_route()
            route = self.__route
            client = route.client
            context = self.__request_receipt_context()
            marker = client.execution_credential_lineage_ref()
            binding = client._capture_credential_binding()
            if (
                type(binding) is not _CredentialBinding
                or binding is not self.__credential_binding
                or binding.lineage_ref is not marker
                or marker is not self.__lineage_ref
            ):
                raise ValueError("credential lineage changed")
            attempt = context.begin_request(
                route,
                selected_client=client,
                credential_lineage_ref=marker,
                transport=ExecutionCredentialRequestTransport.REST,
                operation=_ACCOUNT_CONFIG_OPERATION,
            )
            if (
                type(attempt) is not ExecutionCredentialRequestAttemptContext
                or not _attempt_matches_route(attempt, route, marker)
                or context.validate_current(
                    route,
                    selected_client=client,
                    credential_lineage_ref=marker,
                    context=attempt,
                )
                is not True
            ):
                raise ValueError("session request context unavailable")

            request_parts = client._get_account_config()
            if not _exact_account_config_request(request_parts):
                raise ValueError("account configuration request scope unavailable")
            path, params, extra_data = request_parts
            request_ref = "binance-rest-attempt-" + uuid.uuid4().hex
            physical_request_ref = ExecutionCredentialRequestOpaqueRef()
            result = client.request(
                path,
                params=params,
                extra_data=extra_data,
                timeout=10,
                is_sign=True,
                _include_http_status=True,
                _max_retries=1,
                _include_execution_credential_lineage=True,
                _execution_credential_binding=self.__credential_binding,
            )
            if (
                type(result) is not tuple
                or len(result) != 3
                or type(result[0]) is not RequestData
                or type(result[1]) is not int
                or result[1] != 200
                or result[2] is not marker
                or client._capture_credential_binding() is not self.__credential_binding
                or not _is_accepted_config_response(result[0])
                or context.validate_current(
                    route,
                    selected_client=client,
                    credential_lineage_ref=marker,
                    context=attempt,
                )
                is not True
            ):
                raise ValueError("authenticated account configuration unavailable")

            observation = ExecutionCredentialRequestTransportObservation(
                exchange_name=route.exchange_name,
                provider=route.provider,
                environment=route.environment,
                transport=ExecutionCredentialRequestTransport.REST,
                operation=_ACCOUNT_CONFIG_OPERATION,
                request_ref=request_ref,
                physical_request_ref=physical_request_ref,
                physical_response_ref=ExecutionCredentialRequestOpaqueRef(),
                credential_lineage_ref=marker,
                selected_route_ref=attempt.selected_route_ref,
                owner_generation_ref=attempt.owner_generation_ref,
                owner_lease_ref=attempt.owner_lease_ref,
                session_generation=attempt.session_generation,
                fencing_epoch=attempt.fencing_epoch,
                success_category=(
                    ExecutionCredentialRequestSuccessCategory.AUTHENTICATED_RESPONSE_ACCEPTED
                ),
            )
            with self.__lock:
                self.__pending_observations[id(observation)] = (
                    observation,
                    result[0],
                    result[1],
                    attempt,
                    context,
                    _observation_snapshot(observation),
                )
                self.__pending_observations.move_to_end(id(observation))
                while len(self.__pending_observations) > _MAX_RECEIPTS:
                    self.__pending_observations.popitem(last=False)
            receipt = self.issue_execution_credential_request_receipt(observation)
            if (
                context.validate_current(
                    route,
                    selected_client=client,
                    credential_lineage_ref=marker,
                    context=attempt,
                )
                is not True
                or self.validate_execution_credential_request_receipt(
                    receipt,
                    expected_observation=observation,
                    expected_exchange_name=route.exchange_name,
                    expected_provider=route.provider,
                    expected_environment=route.environment,
                    expected_transport=ExecutionCredentialRequestTransport.REST,
                    expected_operation=_ACCOUNT_CONFIG_OPERATION,
                    expected_credential_lineage_ref=marker,
                    expected_selected_route_ref=attempt.selected_route_ref,
                    expected_owner_generation_ref=attempt.owner_generation_ref,
                    expected_owner_lease_ref=attempt.owner_lease_ref,
                    expected_session_generation=attempt.session_generation,
                    expected_fencing_epoch=attempt.fencing_epoch,
                )
                is not True
            ):
                self.__revoke_receipt(receipt)
                raise ValueError("request receipt became unavailable")
            return observation, receipt
        except ExecutionCredentialRequestReceiptUnavailable:
            raise _unavailable() from None
        except Exception:
            raise _unavailable() from None

    def issue_execution_credential_request_receipt(
        self,
        observation: ExecutionCredentialRequestTransportObservation,
        /,
    ) -> ExecutionCredentialRequestReceipt:
        """Issue once for the exact accepted response registered by this feed."""

        if type(observation) is not ExecutionCredentialRequestTransportObservation:
            raise _receipt_unavailable(
                "execution_credential_request_transport_observation_invalid"
            )
        with self.__lock:
            pending = self.__pending_observations.pop(id(observation), None)
        if pending is None or pending[0] is not observation:
            raise _receipt_unavailable(
                "execution_credential_request_transport_observation_invalid"
            )
        _, response, status_code, attempt, context, observation_snapshot = pending
        route = self.__route
        try:
            if (
                _observation_snapshot(observation) != observation_snapshot
                or status_code != 200
                or not _is_accepted_config_response(response)
                or not _observation_matches_attempt(observation, route, attempt)
                or context is not self.__context
                or context.validate_current(
                    route,
                    selected_client=route.client,
                    credential_lineage_ref=self.__lineage_ref,
                    context=attempt,
                )
                is not True
            ):
                raise _receipt_unavailable(
                    "execution_credential_request_transport_observation_invalid"
                )
            issued_at = datetime.now(timezone.utc)
            expires_at = issued_at + _REQUEST_RECEIPT_TTL
            receipt = ExecutionCredentialRequestReceipt(
                observation=observation,
                receipt_ref=ExecutionCredentialRequestOpaqueRef(),
                provider_issuer_ref=self.__issuer_ref,
                expiry_policy_ref=self.__expiry_policy_ref,
                issued_at_utc=issued_at,
                expires_at_utc=expires_at,
            )
            deadline = time.monotonic() + _REQUEST_RECEIPT_TTL.total_seconds()
            with self.__lock:
                self.__receipts[id(receipt)] = (
                    receipt,
                    observation,
                    attempt,
                    context,
                    deadline,
                    _receipt_snapshot(receipt),
                    observation_snapshot,
                )
                self.__receipts.move_to_end(id(receipt))
                while len(self.__receipts) > _MAX_RECEIPTS:
                    self.__receipts.popitem(last=False)
            return receipt
        except ExecutionCredentialRequestReceiptUnavailable:
            raise
        except Exception:
            raise _receipt_unavailable(
                "execution_credential_request_receipt_policy_unavailable"
            ) from None

    def validate_execution_credential_request_receipt(
        self,
        receipt: ExecutionCredentialRequestReceipt,
        *,
        expected_observation: ExecutionCredentialRequestTransportObservation,
        expected_exchange_name: str,
        expected_provider: str,
        expected_environment: str,
        expected_transport: ExecutionCredentialRequestTransport,
        expected_operation: str,
        expected_credential_lineage_ref: ExecutionCredentialRequestOpaqueRef,
        expected_selected_route_ref: ExecutionCredentialRequestOpaqueRef,
        expected_owner_generation_ref: ExecutionCredentialRequestOpaqueRef,
        expected_owner_lease_ref: ExecutionCredentialRequestOpaqueRef,
        expected_session_generation: str,
        expected_fencing_epoch: int,
    ) -> bool:
        if (
            type(receipt) is not ExecutionCredentialRequestReceipt
            or type(expected_observation)
            is not ExecutionCredentialRequestTransportObservation
        ):
            return False
        with self.__lock:
            issued = self.__receipts.get(id(receipt))
        if (
            issued is None
            or issued[0] is not receipt
            or issued[1] is not expected_observation
        ):
            return False
        observation, attempt, context, deadline = issued[1], issued[2], issued[3], issued[4]
        route = self.__route
        try:
            self.__require_exact_route()
            ExecutionCredentialRequestReceipt.__post_init__(receipt)
            if (
                _receipt_snapshot(receipt) != issued[5]
                or _observation_snapshot(observation) != issued[6]
                or receipt.observation is not observation
                or receipt.provider_issuer_ref is not self.__issuer_ref
                or receipt.expiry_policy_ref is not self.__expiry_policy_ref
                or expected_exchange_name != route.exchange_name
                or expected_provider != route.provider
                or expected_environment != route.environment
                or expected_transport is not ExecutionCredentialRequestTransport.REST
                or expected_operation != _ACCOUNT_CONFIG_OPERATION
                or expected_credential_lineage_ref is not self.__lineage_ref
                or expected_selected_route_ref is not observation.selected_route_ref
                or expected_owner_generation_ref is not observation.owner_generation_ref
                or expected_owner_lease_ref is not observation.owner_lease_ref
                or expected_session_generation != route.session_generation
                or type(expected_fencing_epoch) is not int
                or expected_fencing_epoch != route.fencing_epoch
                or time.monotonic() >= deadline
                or datetime.now(timezone.utc) < receipt.issued_at_utc
                or datetime.now(timezone.utc) >= receipt.expires_at_utc
                or not _observation_matches_attempt(observation, route, attempt)
                or not _exact_feed_transport(route.client)
                or route.client.execution_credential_lineage_ref() is not self.__lineage_ref
                or context is not self.__context
                or context.validate_current(
                    route,
                    selected_client=route.client,
                    credential_lineage_ref=self.__lineage_ref,
                    context=attempt,
                )
                is not True
            ):
                return False
            return True
        except Exception:
            return False

    def __revoke_receipt(self, receipt: ExecutionCredentialRequestReceipt) -> None:
        with self.__lock:
            issued = self.__receipts.get(id(receipt))
            if issued is not None and issued[0] is receipt:
                self.__receipts.pop(id(receipt), None)


class _BinanceExecutionIdentityAssuranceFactory:
    def __call__(
        self,
        route: SelectedExecutionIdentityRoute,
        /,
    ) -> ExecutionIdentityAssurancePort | None:
        if type(route) is not SelectedExecutionIdentityRoute:
            return None
        try:
            SelectedExecutionIdentityRoute.__post_init__(route)
        except Exception:
            return None
        if (
            route.exchange_name != EXCHANGE_NAME
            or route.provider != _PROVIDER
            or route.environment not in _ENVIRONMENTS
            or route.identity_binding != "authenticated_credential"
            or type(route.client) is not BinanceRequestDataSwap
            or type(route.fencing_epoch) is not int
            or route.fencing_epoch <= 0
            or route.ledger_binding is None
            or not isinstance(
                route.request_receipt_context, ExecutionCredentialRequestContextPort
            )
            or not _exact_feed_transport(route.client)
        ):
            return None
        try:
            if (
                type(route.client.execution_credential_lineage_ref())
                is not ExecutionCredentialRequestOpaqueRef
            ):
                return None
        except Exception:
            return None
        return _BinanceExecutionIdentityAssurancePort(route)


def register_binance_execution_identity_assurance_provider(
    registry: ExecutionIdentityAssuranceProviderRegistryPort,
) -> None:
    """Register the exact Binance USDⓈ-M execution-identity provider."""

    if not isinstance(registry, ExecutionIdentityAssuranceProviderRegistryPort):
        raise ExecutionIdentityAssuranceUnavailable(
            "execution_identity_assurance_provider_unavailable"
        )
    try:
        registry.register(EXCHANGE_NAME, _BinanceExecutionIdentityAssuranceFactory())
    except ExecutionIdentityAssuranceUnavailable:
        raise
    except Exception:
        raise ExecutionIdentityAssuranceUnavailable(
            "execution_identity_assurance_provider_unavailable"
        ) from None


def _exact_feed_transport(client: object) -> bool:
    if type(client) is not BinanceRequestDataSwap:
        return False
    try:
        instance = vars(client)
        if any(
            name in instance
            for name in (
                "request",
                "http_request",
                "_get_account_config",
                "_capture_credential_binding",
                "get_environment_info",
            )
        ):
            return False
        if (
            type(client).request is not BinanceRequestData.request
            or type(client).http_request is not Feed.http_request
            or type(client)._get_account_config is not BinanceRequestData._get_account_config
            or type(client)._capture_credential_binding
            is not BinanceRequestData._capture_credential_binding
            or type(client).get_environment_info is not BinanceRequestDataSwap.get_environment_info
            or type(client)._raise_if_error is not BinanceRequestData._raise_if_error
        ):
            return False
        http = getattr(client, "_http_client", None)
        sync = getattr(http, "_sync_client", None)
        return (
            type(http) is HttpClient
            and "request" not in vars(http)
            and type(http).request is HttpClient.request
            and httpx is not None
            and type(sync) is httpx.Client
            and "request" not in vars(sync)
            and type(sync).request is httpx.Client.request
            and _exact_httpx_network_transport(sync)
            and type(getattr(client, "_params", None)) is BinanceExchangeDataSwap
            and type(getattr(client, "exchange_name", None)) is str
            and client.exchange_name == EXCHANGE_NAME
            and type(getattr(client, "asset_type", None)) is str
            and client.asset_type == "SWAP"
        )
    except Exception:
        return False


def _exact_httpx_network_transport(client: object) -> bool:
    """Reject mocked/custom transports and event hooks on the selected client."""

    if httpx is None or type(client) is not httpx.Client:
        return False
    try:
        mounts = getattr(client, "_mounts", None)
        if mounts is None:
            mounts = {}
        if type(mounts) is not dict:
            return False
        transports = [getattr(client, "_transport", None)]
        transports.extend(value for value in mounts.values() if value is not None)
        for transport in transports:
            if (
                type(transport) is not httpx.HTTPTransport
                or "handle_request" in vars(transport)
                or type(transport).handle_request is not httpx.HTTPTransport.handle_request
            ):
                return False
        event_hooks = getattr(client, "_event_hooks", None)
        return (
            type(event_hooks) is dict
            and all(type(hooks) is list and not hooks for hooks in event_hooks.values())
        )
    except Exception:
        return False


def _exact_account_config_request(parts: object) -> bool:
    if type(parts) is not tuple or len(parts) != 3:
        return False
    path, params, extra = parts
    return (
        type(path) is str
        and path == _ACCOUNT_CONFIG_PATH
        and type(params) is dict
        and not params
        and type(extra) is dict
        and type(extra.get("request_type")) is str
        and type(extra.get("exchange_name")) is str
        and type(extra.get("asset_type")) is str
        and type(extra.get("symbol_name")) is str
        and extra.get("request_type") == _ACCOUNT_CONFIG_OPERATION
        and extra.get("exchange_name") == EXCHANGE_NAME
        and extra.get("asset_type") == "SWAP"
        and extra.get("symbol_name") == "ALL"
        and extra.get("normalize_function") is None
    )


def _attempt_matches_route(
    attempt: ExecutionCredentialRequestAttemptContext,
    route: SelectedExecutionIdentityRoute,
    lineage_ref: ExecutionCredentialRequestOpaqueRef,
) -> bool:
    try:
        ExecutionCredentialRequestAttemptContext.__post_init__(attempt)
    except Exception:
        return False
    return (
        type(attempt) is ExecutionCredentialRequestAttemptContext
        and attempt.credential_lineage_ref is lineage_ref
        and attempt.session_generation == route.session_generation
        and type(attempt.fencing_epoch) is int
        and attempt.fencing_epoch == route.fencing_epoch
    )


def _observation_matches_attempt(
    observation: ExecutionCredentialRequestTransportObservation,
    route: SelectedExecutionIdentityRoute,
    attempt: ExecutionCredentialRequestAttemptContext,
) -> bool:
    try:
        ExecutionCredentialRequestTransportObservation.__post_init__(observation)
    except Exception:
        return False
    return (
        type(observation) is ExecutionCredentialRequestTransportObservation
        and observation.exchange_name == route.exchange_name
        and observation.provider == route.provider
        and observation.environment == route.environment
        and observation.transport is ExecutionCredentialRequestTransport.REST
        and observation.operation == _ACCOUNT_CONFIG_OPERATION
        and observation.credential_lineage_ref is attempt.credential_lineage_ref
        and observation.selected_route_ref is attempt.selected_route_ref
        and observation.owner_generation_ref is attempt.owner_generation_ref
        and observation.owner_lease_ref is attempt.owner_lease_ref
        and observation.session_generation == attempt.session_generation
        and type(observation.fencing_epoch) is int
        and observation.fencing_epoch == attempt.fencing_epoch
    )


def _is_accepted_config_response(response: object) -> bool:
    if type(response) is not RequestData:
        return False
    try:
        if (
            response.get_request_type() != _ACCOUNT_CONFIG_OPERATION
            or response.get_exchange_name() != EXCHANGE_NAME
        ):
            return False
        data = response.get_input_data()
        return type(data) is dict and all(
            type(data.get(field_name)) is bool for field_name in _REQUIRED_CONFIG_FIELDS
        )
    except Exception:
        return False


def _observation_snapshot(
    observation: ExecutionCredentialRequestTransportObservation,
) -> tuple[object, ...]:
    ExecutionCredentialRequestTransportObservation.__post_init__(observation)
    return (
        observation.exchange_name,
        observation.provider,
        observation.environment,
        observation.transport,
        observation.operation,
        observation.request_ref,
        id(observation.physical_request_ref),
        id(observation.physical_response_ref),
        id(observation.credential_lineage_ref),
        id(observation.selected_route_ref),
        id(observation.owner_generation_ref),
        id(observation.owner_lease_ref),
        observation.session_generation,
        observation.fencing_epoch,
        observation.success_category,
    )


def _receipt_snapshot(receipt: ExecutionCredentialRequestReceipt) -> tuple[object, ...]:
    ExecutionCredentialRequestReceipt.__post_init__(receipt)
    return (
        id(receipt.observation),
        id(receipt.receipt_ref),
        id(receipt.provider_issuer_ref),
        id(receipt.expiry_policy_ref),
        receipt.issued_at_utc,
        receipt.expires_at_utc,
    )


def _assurance_matches_route(
    assurance: ExecutionIdentityAssurance,
    route: SelectedExecutionIdentityRoute,
) -> bool:
    return (
        assurance.exchange_name == route.exchange_name
        and assurance.provider == route.provider
        and assurance.environment == route.environment
        and assurance.account_ref == route.account_ref
        and assurance.identity_binding == "authenticated_credential"
        and assurance.session_generation == route.session_generation
        and assurance.source_ref != ""
        and assurance.receipt_ref != ""
    )


def _assurance_digest(assurance: ExecutionIdentityAssurance) -> str:
    ExecutionIdentityAssurance.__post_init__(assurance)
    payload = {
        "exchange_name": assurance.exchange_name,
        "provider": assurance.provider,
        "environment": assurance.environment,
        "account_ref": assurance.account_ref,
        "identity_binding": assurance.identity_binding,
        "source_ref": assurance.source_ref,
        "session_generation": assurance.session_generation,
        "observed_at_utc": assurance.observed_at_utc.isoformat(),
        "expires_at_utc": assurance.expires_at_utc.isoformat(),
        "receipt_ref": assurance.receipt_ref,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_utc(value: object) -> bool:
    if type(value) is not datetime or value.tzinfo is None:
        return False
    try:
        return value.utcoffset() == timedelta(0)
    except Exception:
        return False


def _unavailable() -> ExecutionIdentityAssuranceUnavailable:
    return ExecutionIdentityAssuranceUnavailable("execution_identity_assurance_unavailable")


def _receipt_unavailable(code: str) -> ExecutionCredentialRequestReceiptUnavailable:
    return ExecutionCredentialRequestReceiptUnavailable(code)


__all__ = ["register_binance_execution_identity_assurance_provider"]
