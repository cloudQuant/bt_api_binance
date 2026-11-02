"""Unified SDK query and session provider for Binance USD-M account facts.

The provider is bound to the exact USD-M feed selected by ``BtApi``. It
publishes authentication only after that feed's signed ``GET /fapi/v2/account``
returns a strict account-shaped response. Its source and generation identify
the local selected-feed binding; they do not identify a physical account or a
remote server revision. Balance and position observations receive a short
local lease, not a claim that remote account state stayed unchanged after the
response. Position projection contains only neutral instrument, side, quantity,
unit, average-price, resource, and local observation-time facts; it does not
project provider margin, liquidation, or PnL fields.

Binance does not supply the neutral valuation facts required for cash/equity
projection here. The ``account_valuation`` family therefore remains explicitly
unavailable. In particular, ``availableBalance`` is kept as an account balance
field and is not relabeled as settled cash or equity.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
import weakref
from collections import OrderedDict
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from weakref import WeakKeyDictionary

from bt_api_base.account_balance_snapshot_protocol import (
    ACCOUNT_BALANCE_LEASE_PURPOSE,
    ACCOUNT_BALANCE_QUERY_FAMILY,
    ACCOUNT_VALUATION_QUERY_FAMILY,
)
from bt_api_base.account_position_snapshot_protocol import ACCOUNT_POSITION_LEASE_PURPOSE
from bt_api_base.account_protocol import (
    AccountPosition,
    AccountResourceKey,
    MAX_ACCOUNT_ROWS,
)
from bt_api_base.account_session_protocol import (
    AccountPreflightRequest,
    AccountPreflightSnapshot,
    AccountSessionPort,
    AccountSessionSnapshot,
    SettlementVerificationReceipt,
)
from bt_api_base.account_session_registry_protocol import (
    AccountSessionProviderRegistry,
    SelectedAccountSessionRoute,
)
from bt_api_base.containers.requestdatas.request_data import RequestData
from bt_api_base.feeds.feed import Feed
from bt_api_base.feeds.http_client import HttpClient
from bt_api_base.market_protocol import MarketInstrumentKey
from bt_api_base.query_protocol import (
    MAX_QUERY_BATCH_REQUESTS,
    QueryBatchReceipt,
    QueryCompleteness,
    QueryRequest,
    QuerySnapshot,
    QuerySnapshotLease,
)
from bt_api_base.query_provider_protocol import (
    QueryProviderRegistryPort,
    QueryProviderRouteError,
    SelectedQueryRoute,
)

from .account_session_provider import (
    BinanceUsdMProviderError,
    _PRODUCT_TYPE,
    _balance,
    _decimal,
    _decimal_text,
    _symbol,
)
from .exchange_data.binance_exchange_data import (
    BinanceExchangeData,
    BinanceExchangeDataSwap,
)
from .feeds.request_base import BinanceRequestData
from .feeds.swap import BinanceRequestDataSwap
from .provider_configuration_registration import EXCHANGE_NAME

_UTC = timezone.utc
_ENVIRONMENTS = frozenset({"demo", "production"})
_ACCOUNT_PATH = "GET /fapi/v2/account"
_POSITIONS_QUERY_FAMILY = "positions"
_SESSION_TTL = timedelta(seconds=2)
_MAX_REQUEST_TIMEOUT_SECONDS = 10.0
_MAX_RETAINED = 64
_OWNER_LOCK = threading.RLock()
_OWNER_BY_FEED: WeakKeyDictionary[object, weakref.ReferenceType[Any]] = WeakKeyDictionary()


class _BinanceUnifiedAccountProvider(AccountSessionPort):
    """Shared query/session owner for one exact selected USD-M feed."""

    def __init__(self, feed: BinanceRequestDataSwap, environment: str) -> None:
        self._feed = feed
        self._environment = environment
        self._params_binding = getattr(feed, "_params", None)
        self._http_client_binding = getattr(feed, "_http_client", None)
        self._sync_client_binding = getattr(self._http_client_binding, "_sync_client", None)
        self._transport_binding = getattr(self._sync_client_binding, "_transport", None)
        self._source_ref = "binance-usdm-account-source-" + uuid.uuid4().hex
        self._generation = "binance-usdm-feed-generation-" + uuid.uuid4().hex
        self._session_ref: str | None = None
        # Keep credentials private only to detect in-place rotation of this
        # selected feed. They are never hashed, formatted, or returned.
        self._public_key = getattr(feed, "public_key", None)
        self._private_key = getattr(feed, "private_key", None)
        self._invalidated = False
        self._last_authenticated_at: datetime | None = None
        self._last_authenticated_monotonic: float | None = None
        self._latest_receipt: QueryBatchReceipt | None = None
        self._receipts: OrderedDict[int, QueryBatchReceipt] = OrderedDict()
        self._leases: OrderedDict[int, tuple[QuerySnapshotLease, QueryBatchReceipt]] = (
            OrderedDict()
        )
        self._lock = threading.RLock()

    def __repr__(self) -> str:
        state = "authenticated" if self._last_authenticated_at is not None else "unobserved"
        return f"_BinanceUnifiedAccountProvider(state={state})"

    def query_batch(
        self,
        requests: Sequence[QueryRequest],
        *,
        deadline: datetime,
    ) -> QueryBatchReceipt:
        """Query one full account response and project requested neutral rows."""

        selected = _validate_requests(requests)
        _require_utc(deadline, "deadline")
        batch_started_at = _utc_now()
        batch_started_monotonic = time.monotonic()
        deadline_monotonic = batch_started_monotonic + max(
            0.0, (deadline - batch_started_at).total_seconds()
        )

        with self._lock:
            self._latest_receipt = None
            family_counts = _family_counts(selected)
            snapshots_by_request_ref: dict[str, QuerySnapshot] = {}
            provider_requests: list[QueryRequest] = []
            for family, duplicate_code, scope_blocker in (
                (
                    ACCOUNT_BALANCE_QUERY_FAMILY,
                    "binance_duplicate_account_family_unsupported",
                    _account_scope_blocker,
                ),
                (
                    _POSITIONS_QUERY_FAMILY,
                    "binance_duplicate_positions_family_unsupported",
                    _positions_scope_blocker,
                ),
            ):
                family_requests = tuple(item for item in selected if item.family == family)
                if not family_requests:
                    continue
                if family_counts[family] != 1:
                    completed_at = _utc_now()
                    for request in family_requests:
                        snapshots_by_request_ref[request.request_ref] = (
                            self._unavailable_snapshot(
                                request,
                                duplicate_code,
                                started_at=batch_started_at,
                                completed_at=completed_at,
                            )
                        )
                    continue
                request = family_requests[0]
                blocker = scope_blocker(request)
                if blocker is not None:
                    snapshots_by_request_ref[request.request_ref] = (
                        self._unavailable_snapshot(
                            request,
                            blocker,
                            started_at=batch_started_at,
                            completed_at=_utc_now(),
                        )
                    )
                    continue
                provider_requests.append(request)

            if provider_requests:
                snapshots_by_request_ref.update(
                    self._query_account_snapshots(
                        tuple(provider_requests),
                        started_at=batch_started_at,
                        deadline=deadline,
                        deadline_monotonic=deadline_monotonic,
                    )
                )

            snapshots: list[QuerySnapshot] = []
            for request in selected:
                snapshot = snapshots_by_request_ref.get(request.request_ref)
                if snapshot is not None:
                    snapshots.append(snapshot)
                elif request.family == ACCOUNT_VALUATION_QUERY_FAMILY:
                    snapshots.append(
                        self._unavailable_snapshot(
                            request,
                            "binance_account_valuation_semantics_unavailable",
                            started_at=batch_started_at,
                            completed_at=_utc_now(),
                        )
                    )
                else:
                    snapshots.append(
                        self._unavailable_snapshot(
                            request,
                            "binance_query_family_unsupported",
                            started_at=batch_started_at,
                            completed_at=_utc_now(),
                        )
                    )

            batch_completed_at = _utc_now()
            if (
                batch_completed_at > deadline
                or time.monotonic() > deadline_monotonic
            ):
                snapshots = [
                    self._unavailable_snapshot(
                        snapshot.request,
                        "binance_query_deadline_exceeded",
                        started_at=(snapshot.started_at or batch_started_at),
                        completed_at=batch_completed_at,
                        completeness=QueryCompleteness.UNKNOWN,
                    )
                    if snapshot.completeness is QueryCompleteness.COMPLETE
                    else snapshot
                    for snapshot in snapshots
                ]

            receipt = QueryBatchReceipt(
                batch_ref="binance-query-batch-" + uuid.uuid4().hex,
                source_ref=self._source_ref,
                generation=self._generation,
                started_at=batch_started_at,
                completed_at=batch_completed_at,
                requests=selected,
                snapshots=tuple(snapshots),
            )
            self._remember_receipt(receipt)
            return receipt

    def acquire_snapshot_lease(
        self,
        receipt: QueryBatchReceipt,
        *,
        purpose: str,
        expires_at: datetime,
    ) -> QuerySnapshotLease:
        """Issue a brief lease over the latest retained local observation."""

        if type(receipt) is not QueryBatchReceipt:
            raise TypeError("receipt must be a QueryBatchReceipt")
        _require_utc(expires_at, "expires_at")
        with self._lock:
            self._require_current_receipt(receipt)
            if not _lease_purpose_matches_receipt(purpose, receipt):
                raise ValueError("unsupported Binance query lease purpose or scope")
            if not receipt.complete or not receipt.complete_snapshot_refs:
                raise ValueError("incomplete Binance receipt cannot be leased")
            if self._binding_blocker() is not None or not self._authentication_fresh():
                raise ValueError("Binance selected feed or authentication is unavailable")

            issued_at = _utc_now()
            max_expiry = issued_at + _SESSION_TTL
            bounded_expiry = min(expires_at, max_expiry)
            if issued_at >= bounded_expiry:
                raise ValueError("lease expiry must be in the future")
            lease = QuerySnapshotLease(
                lease_ref="binance-query-lease-" + uuid.uuid4().hex,
                receipt_digest=receipt.receipt_digest,
                source_ref=self._source_ref,
                generation=self._generation,
                snapshot_refs=receipt.complete_snapshot_refs,
                issued_at=issued_at,
                expires_at=bounded_expiry,
                purpose=purpose,
            )
            self._leases[id(lease)] = (lease, receipt)
            self._leases.move_to_end(id(lease))
            while len(self._leases) > _MAX_RETAINED:
                self._leases.popitem(last=False)
            return lease

    def validate_lease(
        self,
        lease: QuerySnapshotLease,
        receipt: QueryBatchReceipt,
        *,
        now: datetime,
    ) -> bool:
        """Validate exact local receipt identity, feed binding, and TTL.

        The owner clock is authoritative for expiry. ``now`` is checked only
        as an additional bound; callers cannot extend this provider's lease by
        passing an earlier timestamp.
        """

        if (
            type(lease) is not QuerySnapshotLease
            or type(receipt) is not QueryBatchReceipt
            or not _is_utc(now)
        ):
            return False
        with self._lock:
            issued = self._leases.get(id(lease))
            if issued is None or issued[0] is not lease or issued[1] is not receipt:
                return False
            current = _utc_now()
            return bool(
                self._latest_receipt is receipt
                and self._receipts.get(id(receipt)) is receipt
                and receipt.receipt_digest == lease.receipt_digest
                and receipt.source_ref == self._source_ref == lease.source_ref
                and receipt.generation == self._generation == lease.generation
                and receipt.complete
                and receipt.complete_snapshot_refs == lease.snapshot_refs
                and _lease_purpose_matches_receipt(lease.purpose, receipt)
                and lease.issued_at <= current < lease.expires_at
                and lease.issued_at <= now < lease.expires_at
                and self._binding_blocker() is None
                and self._authentication_fresh()
            )

    def session_snapshot(self) -> AccountSessionSnapshot:
        """Return recent signed-query evidence, never inferred from credentials."""

        with self._lock:
            blocker = self._binding_blocker()
            if blocker is None and self._authentication_fresh():
                observed_at = self._last_authenticated_at
                session_ref = self._session_ref
                if observed_at is not None and session_ref is not None:
                    return AccountSessionSnapshot(
                        exchange_name=EXCHANGE_NAME,
                        source_ref=self._source_ref,
                        generation=self._generation,
                        session_ref=session_ref,
                        # Connected means that the selected HTTPS endpoint
                        # answered the signed request; this is not a durable
                        # socket or physical-account identity claim.
                        connected=True,
                        authenticated=True,
                        trading_enabled=None,
                        business_day=None,
                        settlement_status="unavailable",
                        observed_at=observed_at,
                        available=True,
                    )
            if blocker is None:
                blocker = (
                    "binance_authenticated_read_stale"
                    if self._last_authenticated_at is not None
                    else "binance_authenticated_read_not_observed"
                )
            return AccountSessionSnapshot(
                exchange_name=EXCHANGE_NAME,
                source_ref=self._source_ref,
                generation=self._generation,
                session_ref=None,
                connected=None,
                authenticated=None,
                trading_enabled=None,
                business_day=None,
                settlement_status="unavailable",
                observed_at=None,
                available=False,
                blockers=(blocker,),
            )

    def preflight(self, request: AccountPreflightRequest) -> AccountPreflightSnapshot:
        """Fail closed; endpoint reachability alone is not trade readiness."""

        if type(request) is not AccountPreflightRequest:
            raise TypeError("request must be an AccountPreflightRequest")
        return AccountPreflightSnapshot(
            request=request,
            source_ref=self._source_ref,
            generation=self._generation,
            observed_at=None,
            ready=None,
            available=False,
            blockers=("binance_account_preflight_unavailable",),
        )

    def verify_settlement(self, *, deadline: datetime) -> SettlementVerificationReceipt:
        """No settlement endpoint is registered for this account provider."""

        _require_utc(deadline, "deadline")
        return SettlementVerificationReceipt(
            exchange_name=EXCHANGE_NAME,
            source_ref=self._source_ref,
            generation=self._generation,
            business_day=None,
            status="unavailable",
            observed_at=None,
            complete=False,
            read_only_safe=True,
            receipt_ref=None,
            reason_code="binance_settlement_readback_unavailable",
        )

    def validate_preflight(
        self,
        snapshot: AccountPreflightSnapshot,
        *,
        now: datetime,
    ) -> bool:
        """No preflight snapshot from this provider is actionable."""

        return False

    def _query_account_snapshots(
        self,
        requests: tuple[QueryRequest, ...],
        *,
        started_at: datetime,
        deadline: datetime,
        deadline_monotonic: float,
    ) -> dict[str, QuerySnapshot]:
        """Read once and project requested account and position families."""

        if not requests:
            return {}
        blocker = self._binding_blocker()
        if blocker is not None:
            return self._unavailable_snapshots(
                requests,
                blocker,
                started_at=started_at,
                completed_at=_utc_now(),
            )
        remaining = min(
            _MAX_REQUEST_TIMEOUT_SECONDS,
            deadline_monotonic - time.monotonic(),
        )
        if remaining <= 0:
            return self._unavailable_snapshots(
                requests,
                "binance_query_deadline_elapsed",
                started_at=started_at,
                completed_at=_utc_now(),
                completeness=QueryCompleteness.UNKNOWN,
            )

        try:
            data = self._signed_account_response(remaining)
            completed_at = _utc_now()
            completed_monotonic = time.monotonic()
            if (
                completed_at > deadline
                or completed_monotonic > deadline_monotonic
            ):
                return self._unavailable_snapshots(
                    requests,
                    "binance_query_deadline_exceeded",
                    started_at=started_at,
                    completed_at=completed_at,
                    completeness=QueryCompleteness.UNKNOWN,
                )
            if (
                type(data) is not dict
                or "code" in data
                or type(data.get("multiAssetsMargin")) is not bool
                or type(data.get("assets")) is not list
                or type(data.get("positions")) is not list
                or len(data["assets"]) > MAX_ACCOUNT_ROWS
                or len(data["positions"]) > MAX_ACCOUNT_ROWS
            ):
                raise ValueError("signed account response shape invalid")
        except Exception:
            return self._unavailable_snapshots(
                requests,
                "binance_account_query_outcome_unknown",
                started_at=started_at,
                completed_at=_utc_now(),
                completeness=QueryCompleteness.UNKNOWN,
            )

        # A strict successful response from the signed endpoint establishes
        # only authenticated credential acceptance on this selected feed.
        if self._binding_blocker() is not None:
            return self._unavailable_snapshots(
                requests,
                "binance_selected_feed_binding_invalid",
                started_at=started_at,
                completed_at=completed_at,
            )
        self._record_authenticated_response(completed_at, completed_monotonic)

        observed_at = _timestamp(completed_at)
        snapshots: dict[str, QuerySnapshot] = {}
        for request in requests:
            if request.family == ACCOUNT_BALANCE_QUERY_FAMILY:
                if data["multiAssetsMargin"] is not False:
                    snapshots[request.request_ref] = self._unavailable_snapshot(
                        request,
                        "binance_multi_asset_balance_semantics_unavailable",
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                    continue
                try:
                    balances = tuple(
                        _balance(row, observed_at=observed_at).to_dict()
                        for row in data["assets"]
                    )
                    identities = tuple(
                        (
                            row["resource"]["product_type"],
                            row["resource"]["margin_pool"],
                            row["currency"],
                        )
                        for row in balances
                    )
                    if len(set(identities)) != len(identities):
                        raise ValueError("duplicate account balance row")
                    snapshots[request.request_ref] = QuerySnapshot(
                        request=request,
                        source_ref=self._source_ref,
                        generation=self._generation,
                        snapshot_ref="binance-account-snapshot-" + uuid.uuid4().hex,
                        completeness=QueryCompleteness.COMPLETE,
                        started_at=started_at,
                        completed_at=completed_at,
                        observed_at=completed_at,
                        scope_complete=True,
                        records=balances,
                    )
                except (BinanceUsdMProviderError, TypeError, ValueError):
                    snapshots[request.request_ref] = self._unavailable_snapshot(
                        request,
                        "binance_account_projection_unavailable",
                        started_at=started_at,
                        completed_at=completed_at,
                    )
            elif request.family == _POSITIONS_QUERY_FAMILY:
                try:
                    positions = _project_position_records(
                        data["positions"],
                        environment=self._environment,
                        observed_at=observed_at,
                    )
                    snapshots[request.request_ref] = QuerySnapshot(
                        request=request,
                        source_ref=self._source_ref,
                        generation=self._generation,
                        snapshot_ref="binance-account-positions-snapshot-"
                        + uuid.uuid4().hex,
                        completeness=QueryCompleteness.COMPLETE,
                        started_at=started_at,
                        completed_at=completed_at,
                        observed_at=completed_at,
                        scope_complete=True,
                        records=positions,
                    )
                except (BinanceUsdMProviderError, TypeError, ValueError):
                    snapshots[request.request_ref] = self._unavailable_snapshot(
                        request,
                        "binance_positions_projection_unavailable",
                        started_at=started_at,
                        completed_at=completed_at,
                    )
            else:
                raise AssertionError("only supported account families may be projected")
        return snapshots

    def _unavailable_snapshots(
        self,
        requests: tuple[QueryRequest, ...],
        blocker: str,
        *,
        started_at: datetime,
        completed_at: datetime,
        completeness: QueryCompleteness = QueryCompleteness.UNAVAILABLE,
    ) -> dict[str, QuerySnapshot]:
        return {
            request.request_ref: self._unavailable_snapshot(
                request,
                blocker,
                started_at=started_at,
                completed_at=completed_at,
                completeness=completeness,
            )
            for request in requests
        }

    def _signed_account_response(self, timeout: float) -> dict[str, Any]:
        """Read through the selected feed's signer and retain the HTTP status."""

        feed = self._feed
        path, params, extra_data = BinanceRequestData._get_account(feed)
        if (
            path != _ACCOUNT_PATH
            or type(params) is not dict
            or params
            or type(extra_data) is not dict
            or extra_data.get("request_type") != "get_account"
            or extra_data.get("exchange_name") != EXCHANGE_NAME
            or extra_data.get("asset_type") != "SWAP"
            or extra_data.get("normalize_function")
            is not BinanceRequestData._get_account_normalize_function
        ):
            raise ValueError("selected account route changed")
        result = BinanceRequestData.request(
            feed,
            path,
            params=params,
            extra_data=extra_data,
            timeout=timeout,
            is_sign=True,
            _include_http_status=True,
            _max_retries=1,
        )
        if (
            type(result) is not tuple
            or len(result) != 2
            or type(result[0]) is not RequestData
            or type(result[1]) is not int
            or result[1] != 200
        ):
            raise ValueError("signed account request was not an exact HTTP success")
        request_data = result[0]
        body = request_data.get_input_data()
        if (
            request_data.request_type != "get_account"
            or request_data.exchange_name != EXCHANGE_NAME
            or request_data.asset_type != "SWAP"
            or request_data.extra_data is not extra_data
            or type(body) is not bytes
            or len(body) > 4 * 1024 * 1024
        ):
            raise ValueError("signed account response bytes are invalid")
        decoded = body.decode("utf-8", errors="strict")
        data = json.loads(
            decoded,
            object_pairs_hook=_json_object_no_duplicates,
            parse_constant=_reject_json_constant,
        )
        if type(data) is not dict:
            raise ValueError("signed account response is not a JSON object")
        return data

    def _unavailable_snapshot(
        self,
        request: QueryRequest,
        blocker: str,
        *,
        started_at: datetime,
        completed_at: datetime,
        completeness: QueryCompleteness = QueryCompleteness.UNAVAILABLE,
    ) -> QuerySnapshot:
        return QuerySnapshot(
            request=request,
            source_ref=self._source_ref,
            generation=self._generation,
            snapshot_ref=None,
            completeness=completeness,
            started_at=started_at,
            completed_at=completed_at,
            observed_at=completed_at,
            scope_complete=False,
            blockers=(blocker,),
        )

    def _record_authenticated_response(
        self,
        observed_at: datetime,
        observed_monotonic: float,
    ) -> None:
        if self._session_ref is None:
            self._session_ref = "binance-authenticated-read-session-" + uuid.uuid4().hex
        self._last_authenticated_at = observed_at
        self._last_authenticated_monotonic = observed_monotonic

    def _authentication_fresh(self) -> bool:
        observed = self._last_authenticated_monotonic
        if self._last_authenticated_at is None or observed is None or self._session_ref is None:
            return False
        age = time.monotonic() - observed
        return 0.0 <= age < _SESSION_TTL.total_seconds()

    def _binding_blocker(self) -> str | None:
        if self._invalidated:
            return "binance_selected_feed_binding_invalid"
        feed = self._feed
        try:
            if (
                type(feed) is not BinanceRequestDataSwap
                or feed.exchange_name != EXCHANGE_NAME
                or feed.asset_type != "SWAP"
                or type(feed).request is not BinanceRequestData.request
                or type(feed)._get_account is not BinanceRequestData._get_account
                or type(feed).http_request is not Feed.http_request
                or type(feed).sign is not BinanceRequestData.sign
                or type(feed)._require_private_credentials
                is not BinanceRequestData._require_private_credentials
                or type(feed)._raise_if_error is not BinanceRequestData._raise_if_error
                or type(feed).translate_error is not BinanceRequestData.translate_error
                or type(feed).get_environment_info
                is not BinanceRequestDataSwap.get_environment_info
            ):
                raise ValueError("selected feed methods changed")
            overridden = {
                "request",
                "_get_account",
                "http_request",
                "sign",
                "_require_private_credentials",
                "_raise_if_error",
                "translate_error",
                "get_environment_info",
            }
            if overridden.intersection(vars(feed)):
                raise ValueError("selected feed instance changed")
            if (
                feed._params is not self._params_binding
                or type(feed._params) is not BinanceExchangeDataSwap
                or type(feed._params).get_rest_path is not BinanceExchangeData.get_rest_path
                or "get_rest_path" in vars(feed._params)
                or feed._params.exchange_name != EXCHANGE_NAME
                or feed._params.get_rest_path("get_account") != _ACCOUNT_PATH
                or feed._params.rest_paths.get("get_account") != _ACCOUNT_PATH
                or feed._params.environment != self._environment
            ):
                raise ValueError("selected endpoint changed")
            proof = BinanceRequestDataSwap.get_environment_info(feed)
            if (
                type(proof) is not dict
                or proof.get("verified") is not True
                or proof.get("environment") != self._environment
                or proof.get("simulated") is not (self._environment == "demo")
            ):
                raise ValueError("selected environment is not verified")
            if (
                type(self._public_key) is not str
                or not self._public_key
                or self._public_key != self._public_key.strip()
                or type(self._private_key) is not str
                or not self._private_key
                or self._private_key != self._private_key.strip()
                or feed.public_key != self._public_key
                or feed.private_key != self._private_key
            ):
                raise ValueError("selected credentials are unavailable or changed")
            http_client = feed._http_client
            if (
                http_client is not self._http_client_binding
                or type(http_client) is not HttpClient
                or type(http_client).request is not HttpClient.request
                or type(http_client)._process_response is not HttpClient._process_response
                or "request" in vars(http_client)
                or "_process_response" in vars(http_client)
            ):
                raise ValueError("selected HTTP client changed")
            import httpx

            sync_client = http_client._sync_client
            if (
                sync_client is not self._sync_client_binding
                or type(sync_client) is not httpx.Client
                or type(sync_client).request is not httpx.Client.request
                or "request" in vars(sync_client)
                or sync_client._transport is not self._transport_binding
                or type(sync_client._transport) is not httpx.HTTPTransport
                or type(sync_client._transport).handle_request
                is not httpx.HTTPTransport.handle_request
                or "handle_request" in vars(sync_client._transport)
                or sync_client.is_closed
                or sync_client.follow_redirects
            ):
                raise ValueError("selected HTTPS transport changed")
        except Exception:
            self._invalidated = True
            return "binance_selected_feed_binding_invalid"
        return None

    def _remember_receipt(self, receipt: QueryBatchReceipt) -> None:
        self._latest_receipt = receipt
        self._receipts[id(receipt)] = receipt
        self._receipts.move_to_end(id(receipt))
        while len(self._receipts) > _MAX_RETAINED:
            self._receipts.popitem(last=False)

    def _require_current_receipt(self, receipt: QueryBatchReceipt) -> None:
        if (
            self._latest_receipt is not receipt
            or self._receipts.get(id(receipt)) is not receipt
            or receipt.source_ref != self._source_ref
            or receipt.generation != self._generation
        ):
            raise ValueError("receipt is not the latest exact Binance observation")


class _BinanceQueryProviderFactory:
    def __call__(self, route: SelectedQueryRoute, /) -> _BinanceUnifiedAccountProvider:
        if type(route) is not SelectedQueryRoute:
            raise QueryProviderRouteError("QUERY_PROVIDER_ROUTE_INVALID")
        try:
            SelectedQueryRoute.__post_init__(route)
        except Exception:
            raise QueryProviderRouteError("QUERY_PROVIDER_ROUTE_INVALID") from None
        owner = _owner_for_route(route.client, route.exchange_name, route.environment)
        if owner is None:
            raise QueryProviderRouteError("QUERY_PROVIDER_ROUTE_CLIENT_UNAVAILABLE")
        return owner


class _BinanceAccountSessionFactory:
    def __call__(
        self,
        route: SelectedAccountSessionRoute,
    ) -> _BinanceUnifiedAccountProvider:
        if type(route) is not SelectedAccountSessionRoute:
            raise ValueError("account_session_route_invalid")
        try:
            route.__post_init__()
        except Exception:
            raise ValueError("account_session_route_invalid") from None
        owner = _owner_for_route(route.client, route.exchange_name, route.environment)
        if owner is None:
            raise ValueError("account_session_route_invalid")
        return owner


def register_binance_query_provider(registry: QueryProviderRegistryPort) -> None:
    """Register the exact selected-feed Binance USD-M query provider."""

    if not isinstance(registry, QueryProviderRegistryPort):
        raise QueryProviderRouteError("QUERY_PROVIDER_ROUTE_INVALID")
    registry.register(EXCHANGE_NAME, _BinanceQueryProviderFactory())


def register_binance_account_session_provider(
    registry: AccountSessionProviderRegistry,
) -> None:
    """Register the query-backed Binance session observation provider."""

    if not isinstance(registry, AccountSessionProviderRegistry):
        raise ValueError("account_session_registry_invalid")
    registry.register(EXCHANGE_NAME, _BinanceAccountSessionFactory())


def _owner_for_route(
    client: object,
    exchange_name: str,
    environment: str | None,
) -> _BinanceUnifiedAccountProvider | None:
    if (
        exchange_name != EXCHANGE_NAME
        or environment not in _ENVIRONMENTS
        or type(client) is not BinanceRequestDataSwap
    ):
        return None
    with _OWNER_LOCK:
        try:
            reference = _OWNER_BY_FEED.get(client)
        except TypeError:
            return None
        owner = reference() if reference is not None else None
        if owner is not None and owner._environment == environment:
            return owner
        owner = _BinanceUnifiedAccountProvider(client, environment)
        try:
            _OWNER_BY_FEED[client] = weakref.ref(owner)
        except TypeError:
            return None
        return owner


def _validate_requests(requests: Sequence[QueryRequest]) -> tuple[QueryRequest, ...]:
    if not isinstance(requests, Sequence) or isinstance(requests, (str, bytes, bytearray)):
        raise TypeError("requests must be a sequence of QueryRequest values")
    selected = tuple(requests)
    if not 1 <= len(selected) <= MAX_QUERY_BATCH_REQUESTS:
        raise ValueError("requests must contain between 1 and the batch limit")
    if any(type(request) is not QueryRequest for request in selected):
        raise TypeError("requests must contain QueryRequest values")
    refs = tuple(request.request_ref for request in selected)
    if len(set(refs)) != len(refs):
        raise ValueError("request_ref values must be unique within a batch")
    return selected


def _json_object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError("non-finite JSON constant is unsupported")


def _family_counts(requests: tuple[QueryRequest, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for request in requests:
        counts[request.family] = counts.get(request.family, 0) + 1
    return counts


def _account_scope_blocker(request: QueryRequest) -> str | None:
    if request.filters or request.require_complete_scope is not True:
        return "binance_full_account_scope_required"
    return None


def _lease_purpose_matches_receipt(purpose: Any, receipt: QueryBatchReceipt) -> bool:
    """Bind each lease purpose to only its supported account query scope."""

    if type(purpose) is not str or type(receipt) is not QueryBatchReceipt:
        return False
    requests = receipt.requests
    if purpose == ACCOUNT_POSITION_LEASE_PURPOSE:
        return bool(
            len(requests) == 1
            and requests[0].family == _POSITIONS_QUERY_FAMILY
            and not requests[0].filters
            and requests[0].required is True
            and requests[0].require_complete_scope is True
        )
    if purpose != ACCOUNT_BALANCE_LEASE_PURPOSE or not 1 <= len(requests) <= 2:
        return False

    account_requests = tuple(
        request for request in requests if request.family == ACCOUNT_BALANCE_QUERY_FAMILY
    )
    valuation_requests = tuple(
        request for request in requests if request.family == ACCOUNT_VALUATION_QUERY_FAMILY
    )
    if (
        len(account_requests) != 1
        or len(valuation_requests) > 1
        or len(account_requests) + len(valuation_requests) != len(requests)
    ):
        return False
    account_request = account_requests[0]
    if (
        account_request.filters
        or account_request.required is not True
        or account_request.require_complete_scope is not True
    ):
        return False
    if not valuation_requests:
        return True
    valuation_request = valuation_requests[0]
    return bool(
        not valuation_request.filters
        and valuation_request.required is False
        and valuation_request.require_complete_scope is True
    )


def _positions_scope_blocker(request: QueryRequest) -> str | None:
    if request.filters or request.require_complete_scope is not True:
        return "binance_full_positions_scope_required"
    return None


def _project_position_records(
    rows: Any,
    *,
    environment: str,
    observed_at: str,
) -> tuple[dict[str, Any], ...]:
    """Project every USD-M position row or reject the family as incomplete."""

    if type(rows) is not list or len(rows) > MAX_ACCOUNT_ROWS:
        raise BinanceUsdMProviderError("POSITIONS_SNAPSHOT_INVALID")

    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    margin_pool_by_symbol: dict[str, str] = {}
    for row in rows:
        if type(row) is not dict or any(type(key) is not str for key in row):
            raise BinanceUsdMProviderError("POSITIONS_SNAPSHOT_INVALID")

        symbol = _symbol(row.get("symbol"))
        native_side = row.get("positionSide")
        amount = _decimal(row.get("positionAmt"))
        entry_price = _decimal(row.get("entryPrice"))
        isolated = row.get("isolated")
        if type(isolated) is not bool or entry_price < 0:
            raise BinanceUsdMProviderError("POSITIONS_SNAPSHOT_INVALID")

        if native_side == "BOTH":
            side = "net"
            quantity = amount
        elif native_side == "LONG":
            side = "long"
            quantity = abs(amount)
        elif native_side == "SHORT":
            side = "short"
            quantity = abs(amount)
        else:
            # A malformed side or contradictory signed amount cannot be
            # normalized into a complete neutral position family.
            raise BinanceUsdMProviderError("POSITIONS_SNAPSHOT_INVALID")

        margin_pool = "isolated" if isolated else "cross"
        prior_margin_pool = margin_pool_by_symbol.setdefault(symbol, margin_pool)
        if prior_margin_pool != margin_pool:
            raise BinanceUsdMProviderError("POSITIONS_SNAPSHOT_INVALID")
        identity = (symbol, side)
        if identity in seen:
            raise BinanceUsdMProviderError("POSITIONS_SNAPSHOT_INVALID")
        seen.add(identity)

        instrument = MarketInstrumentKey(
            provider="binance",
            venue="binance",
            environment=environment,
            product_type=_PRODUCT_TYPE,
            instrument_id=symbol,
            native_symbol=symbol,
        )
        record = AccountPosition(
            resource=AccountResourceKey(
                product_type=_PRODUCT_TYPE,
                margin_pool=margin_pool,
            ),
            instrument=instrument,
            side=side,
            quantity=_decimal_text(quantity),
            qty_unit="base_asset",
            average_price=(
                None if entry_price == 0 else _decimal_text(entry_price)
            ),
            price_currency=None,
            observed_at_utc=observed_at,
        )
        result.append(record.to_dict())
    return tuple(result)


def _require_utc(value: object, field_name: str) -> None:
    if type(value) is not datetime or value.tzinfo is None:
        raise TypeError(f"{field_name} must be an aware UTC datetime")
    try:
        if value.utcoffset() != timedelta(0):
            raise ValueError(f"{field_name} must be an aware UTC datetime")
    except Exception:
        raise ValueError(f"{field_name} must be an aware UTC datetime") from None


def _is_utc(value: object) -> bool:
    if type(value) is not datetime or value.tzinfo is None:
        return False
    try:
        return value.utcoffset() == timedelta(0)
    except Exception:
        return False


def _utc_now() -> datetime:
    return datetime.now(_UTC)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "register_binance_account_session_provider",
    "register_binance_query_provider",
]
