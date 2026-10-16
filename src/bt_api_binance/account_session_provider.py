"""Read-only USDⓈ-M Demo provider for the Gateway account-session protocol.

This adapter deliberately supports the Demo host only. It performs signed
``GET`` requests for account facts and has no order, cancellation, transfer,
or other mutating endpoint. Binance's account response does not provide the
provider-authoritative monotonic revision required by DIM03, so this adapter
returns an ordinary ``AccountObservation`` and never mints a full-position
snapshot receipt.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from bt_api_base.account_protocol import (
    MAX_ACCOUNT_OBSERVATION_BYTES,
    MAX_ACCOUNT_ROWS,
    AccountBalance,
    AccountKey,
    AccountObservation,
    AccountOpenOrder,
    AccountPosition,
    AccountResourceKey,
)
from bt_api_base.market_protocol import MarketInstrumentKey

_BASE_URL = "https://demo-fapi.binance.com"
_MAX_TIMEOUT_SECONDS = 30.0
_SERVER_TIME_MAX_AGE_SECONDS = 60.0
_MAX_RECV_WINDOW_MS = 5_000
_MAX_SYMBOL_LENGTH = 32
_SYMBOL = re.compile(r"[A-Z0-9]{1,32}\Z", re.ASCII)
_SESSION_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)
_PRODUCT_TYPE = "usdm_perpetual"
_RESOURCE = AccountResourceKey(product_type=_PRODUCT_TYPE, margin_pool="cross")
_ROUTES = {
    "server_time": "/fapi/v1/time",
    "account_config": "/fapi/v1/accountConfig",
    "account": "/fapi/v2/account",
    "open_orders": "/fapi/v1/openOrders",
    "open_algo_orders": "/fapi/v1/openAlgoOrders",
}


class _NoRedirectHandler(HTTPRedirectHandler):
    """Never forward a signed request beyond its fixed Demo origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BinanceUsdMProviderError(RuntimeError):
    """Finite provider error that never carries HTTP or credential content."""

    _CODES = frozenset(
        {
            "INVALID_CREDENTIALS",
            "INVALID_ACCOUNT_IDENTITY",
            "INVALID_GENERATION",
            "INVALID_TIMEOUT",
            "PROVIDER_SESSION_NOT_ACTIVE",
            "PROVIDER_SESSION_CLOSED",
            "PROVIDER_SESSION_ALREADY_CONNECTED",
            "PROVIDER_THREAD_MISMATCH",
            "PROVIDER_GENERATION_MISMATCH",
            "SERVER_TIME_READ_FAILED",
            "SERVER_TIME_INVALID",
            "SERVER_TIME_PROBE_REQUIRED",
            "SERVER_TIME_PROBE_STALE",
            "ACCOUNT_CONFIGURATION_READ_FAILED",
            "ACCOUNT_CONFIGURATION_INVALID",
            "ACCOUNT_SNAPSHOT_READ_FAILED",
            "ACCOUNT_SNAPSHOT_INVALID",
            "ACCOUNT_COVERAGE_UNSUPPORTED",
            "ACCOUNT_ROWS_EXCEEDED",
            "OPEN_ORDER_SHAPE_UNSUPPORTED",
            "REQUEST_TIMEOUT",
            "RESPONSE_TOO_LARGE",
            "TRANSPORT_FAILED",
            "INVALID_JSON_RESPONSE",
        }
    )

    def __init__(self, code: str) -> None:
        self.code = code if type(code) is str and code in self._CODES else "PROVIDER_FAILED"
        super().__init__(self.code)


@dataclass(frozen=True)
class BinanceUsdMApiCredentials:
    """Opaque trusted-owner credential material; repr never reveals either value."""

    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)

    def __post_init__(self) -> None:
        for name in ("api_key", "api_secret"):
            value = getattr(self, name)
            if (
                type(value) is not str
                or not value
                or value != value.strip()
                or len(value) > 512
                or not value.isascii()
                or not value.isprintable()
            ):
                raise BinanceUsdMProviderError("INVALID_CREDENTIALS")

    def __repr__(self) -> str:
        return "BinanceUsdMApiCredentials(<redacted>)"


class BinanceUsdMAccountSessionProvider:
    """One-shot, owner-thread USDⓈ-M Demo reader compatible with Gateway.

    ``transport`` exists for deterministic source tests. Production callers
    should use the default HTTPS transport; the endpoint host and route table
    are fixed in this module and cannot be supplied by deployment metadata.
    """

    def __init__(
        self,
        credentials: BinanceUsdMApiCredentials | Mapping[str, Any],
        *,
        environment: str = "demo",
        transport: Callable[[str, str, Mapping[str, str], float, int], bytes] | None = None,
        wall_clock: Callable[[], float] = time.time,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if environment != "demo":
            raise BinanceUsdMProviderError("INVALID_ACCOUNT_IDENTITY")
        self._credentials = _credentials(credentials)
        self._transport = transport or _https_get
        if not callable(self._transport) or not callable(wall_clock) or not callable(
            monotonic_clock
        ):
            self._credentials = None
            raise BinanceUsdMProviderError("INVALID_CREDENTIALS")
        self._wall_clock = wall_clock
        self._monotonic_clock = monotonic_clock
        self._owner_thread: int | None = None
        self._account_key: AccountKey | None = None
        self._generation: str | None = None
        self._closed = False
        self._server_time_offset_ms: int | None = None
        self._server_time_observed_monotonic: float | None = None

    def __repr__(self) -> str:
        state = "closed" if self._closed else "active" if self._generation else "new"
        return f"BinanceUsdMAccountSessionProvider(environment=demo, state={state})"

    def connect(self, *, account_key: AccountKey, generation: str, timeout: float) -> None:
        """Bind this provider instance to one demo account and owner thread."""

        if self._closed:
            raise BinanceUsdMProviderError("PROVIDER_SESSION_CLOSED")
        if self._generation is not None:
            raise BinanceUsdMProviderError("PROVIDER_SESSION_ALREADY_CONNECTED")
        _validate_timeout(timeout)
        if (
            type(account_key) is not AccountKey
            or account_key.provider != "binance"
            or account_key.venue != "binance"
            or account_key.environment != "demo"
            or account_key.subaccount_id is not None
        ):
            raise BinanceUsdMProviderError("INVALID_ACCOUNT_IDENTITY")
        _validate_generation(generation)
        self._owner_thread = threading.get_ident()
        self._account_key = account_key
        self._generation = generation

        # Establish exchange-clock offset before the worker's first signed
        # account snapshot. The formal C01 server-time operation performs its
        # own separate fresh probe through read_exchange_server_time().
        self._fetch_server_time(_deadline(self._monotonic_clock, timeout))

    def read_exchange_server_time(self, *, generation: str, timeout: float) -> Mapping[str, int]:
        """Read a fresh provider server-time fact; no account cache fallback."""

        self._assert_active(generation)
        deadline = _deadline(self._monotonic_clock, timeout)
        try:
            server_time, _, observed = self._fetch_server_time(deadline)
        except BinanceUsdMProviderError:
            raise
        except Exception:
            raise BinanceUsdMProviderError("SERVER_TIME_READ_FAILED") from None
        self._server_time_observed_monotonic = observed
        return {"serverTime": server_time}

    def read_account_configuration(self, *, generation: str, timeout: float) -> Mapping[str, Any]:
        """Read allowlisted account configuration from the signed config route."""

        self._assert_active(generation)
        deadline = _deadline(self._monotonic_clock, timeout)
        self._ensure_server_time(deadline)
        try:
            response = self._request_json("account_config", deadline=deadline, signed=True)
            if type(response) is not dict:
                raise BinanceUsdMProviderError("ACCOUNT_CONFIGURATION_INVALID")
            fields = ("canTrade", "canDeposit", "canWithdraw", "dualSidePosition")
            if any(type(response.get(field_name)) is not bool for field_name in fields):
                raise BinanceUsdMProviderError("ACCOUNT_CONFIGURATION_INVALID")
            return {field_name: response[field_name] for field_name in fields}
        except BinanceUsdMProviderError:
            raise
        except Exception:
            raise BinanceUsdMProviderError("ACCOUNT_CONFIGURATION_READ_FAILED") from None

    def read_account(self, *, generation: str, timeout: float) -> AccountObservation:
        """Read full cross USDⓈ-M balances, positions, and both open-order classes."""

        self._assert_active(generation)
        deadline = _deadline(self._monotonic_clock, timeout)
        self._ensure_server_time(deadline)
        started = _utc_now(self._wall_clock)
        try:
            account = self._request_json("account", deadline=deadline, signed=True)
            if type(account) is not dict or type(account.get("multiAssetsMargin")) is not bool:
                raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")
            if account["multiAssetsMargin"]:
                # In multi-assets mode Binance's asset availableBalance may be
                # an account-wide USD value, not a per-asset amount. Do not
                # publish it as a currency-scoped AccountBalance fact.
                raise BinanceUsdMProviderError("ACCOUNT_COVERAGE_UNSUPPORTED")
            regular_orders = self._request_json("open_orders", deadline=deadline, signed=True)
            algo_orders = self._request_json(
                "open_algo_orders", deadline=deadline, signed=True
            )
            asset_rows = _rows(account.get("assets"), "ACCOUNT_SNAPSHOT_INVALID")
            position_rows = _rows(account.get("positions"), "ACCOUNT_SNAPSHOT_INVALID")
            regular_rows = _rows(regular_orders, "ACCOUNT_SNAPSHOT_INVALID")
            algo_rows = _rows(algo_orders, "ACCOUNT_SNAPSHOT_INVALID")
            if len(asset_rows) > MAX_ACCOUNT_ROWS or len(position_rows) > MAX_ACCOUNT_ROWS:
                raise BinanceUsdMProviderError("ACCOUNT_ROWS_EXCEEDED")
            if len(regular_rows) + len(algo_rows) > MAX_ACCOUNT_ROWS:
                raise BinanceUsdMProviderError("ACCOUNT_ROWS_EXCEEDED")

            completed = _utc_now(self._wall_clock)
            margin_by_symbol: dict[str, bool] = {}
            for row in position_rows:
                symbol = _symbol(row.get("symbol"))
                isolated = row.get("isolated")
                if type(isolated) is not bool:
                    raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")
                prior = margin_by_symbol.setdefault(symbol, isolated)
                if prior is not isolated:
                    raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")

            balances = tuple(_balance(row, observed_at=completed) for row in asset_rows)
            positions = tuple(
                _position(row, account_key=self._account_key, observed_at=completed)
                for row in position_rows
                if row["isolated"] is False
            )
            open_orders = _collect_open_orders(
                regular_rows,
                algo_rows,
                margin_by_symbol=margin_by_symbol,
                account_key=self._account_key,
                observed_at=completed,
            )
            return AccountObservation(
                account_key=self._account_key,
                observation_id="binance-usdm-" + uuid.uuid4().hex,
                coverage=(_RESOURCE,),
                balances=balances,
                positions=positions,
                valuation=None,
                started_at_utc=started,
                completed_at_utc=completed,
                consistency="multi_query",
                balances_complete=True,
                positions_complete=True,
                open_orders=open_orders,
                open_orders_complete=True,
            )
        except BinanceUsdMProviderError:
            raise
        except Exception:
            raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_READ_FAILED") from None

    def close(self) -> bool:
        """Drop local credential references; no remote session exists to mutate."""

        if self._closed:
            return True
        if self._owner_thread is not None and threading.get_ident() != self._owner_thread:
            raise BinanceUsdMProviderError("PROVIDER_THREAD_MISMATCH")
        self._credentials = None
        self._server_time_offset_ms = None
        self._server_time_observed_monotonic = None
        self._closed = True
        return True

    def _fetch_server_time(
        self, deadline: float
    ) -> tuple[int, float, float]:
        mono_before = _clock_value(self._monotonic_clock)
        wall_before = _clock_value(self._wall_clock)
        try:
            response = self._request_json("server_time", deadline=deadline, signed=False)
        except BinanceUsdMProviderError:
            raise
        except Exception:
            raise BinanceUsdMProviderError("SERVER_TIME_READ_FAILED") from None
        wall_after = _clock_value(self._wall_clock)
        mono_after = _clock_value(self._monotonic_clock)
        if (
            type(response) is not dict
            or set(response) != {"serverTime"}
            or type(response["serverTime"]) is not int
            or not 0 < response["serverTime"] <= 253402300799999
            or mono_after < mono_before
            or wall_after < wall_before
        ):
            raise BinanceUsdMProviderError("SERVER_TIME_INVALID")
        rtt = mono_after - mono_before
        if rtt > _MAX_TIMEOUT_SECONDS:
            raise BinanceUsdMProviderError("REQUEST_TIMEOUT")
        midpoint_ms = int(round((wall_before + wall_after) * 500))
        self._server_time_offset_ms = response["serverTime"] - midpoint_ms
        self._server_time_observed_monotonic = mono_after
        return response["serverTime"], rtt, mono_after

    def _request_json(self, route: str, *, deadline: float, signed: bool) -> Any:
        path = _ROUTES.get(route)
        if path is None:
            raise BinanceUsdMProviderError("TRANSPORT_FAILED")
        remaining = deadline - _clock_value(self._monotonic_clock)
        if remaining <= 0:
            raise BinanceUsdMProviderError("REQUEST_TIMEOUT")
        headers = {"Accept": "application/json"}
        params: dict[str, str] = {}
        if signed:
            credentials = self._credentials
            offset = self._server_time_offset_ms
            if credentials is None or offset is None:
                raise BinanceUsdMProviderError("SERVER_TIME_PROBE_REQUIRED")
            timestamp = int(self._wall_clock() * 1000) + offset
            if timestamp < 0:
                raise BinanceUsdMProviderError("SERVER_TIME_INVALID")
            params = {"recvWindow": str(_MAX_RECV_WINDOW_MS), "timestamp": str(timestamp)}
            query = urlencode(sorted(params.items()))
            signature = hmac.new(
                credentials.api_secret.encode("ascii"),
                query.encode("ascii"),
                hashlib.sha256,
            ).hexdigest()
            query += "&signature=" + signature
            headers["X-MBX-APIKEY"] = credentials.api_key
        else:
            query = ""
        url = _BASE_URL + path + ("?" + query if query else "")
        try:
            body = self._transport("GET", url, headers, remaining, MAX_ACCOUNT_OBSERVATION_BYTES)
        except BinanceUsdMProviderError:
            raise
        except Exception:
            raise BinanceUsdMProviderError("TRANSPORT_FAILED") from None
        if _clock_value(self._monotonic_clock) > deadline:
            raise BinanceUsdMProviderError("REQUEST_TIMEOUT")
        if type(body) is not bytes:
            raise BinanceUsdMProviderError("INVALID_JSON_RESPONSE")
        if len(body) > MAX_ACCOUNT_OBSERVATION_BYTES:
            raise BinanceUsdMProviderError("RESPONSE_TOO_LARGE")
        try:
            return json.loads(body.decode("utf-8", errors="strict"))
        except Exception:
            raise BinanceUsdMProviderError("INVALID_JSON_RESPONSE") from None

    def _assert_active(self, generation: str) -> None:
        if self._closed:
            raise BinanceUsdMProviderError("PROVIDER_SESSION_CLOSED")
        if self._generation is None or self._owner_thread is None or self._account_key is None:
            raise BinanceUsdMProviderError("PROVIDER_SESSION_NOT_ACTIVE")
        if threading.get_ident() != self._owner_thread:
            raise BinanceUsdMProviderError("PROVIDER_THREAD_MISMATCH")
        _validate_generation(generation)
        if generation != self._generation:
            raise BinanceUsdMProviderError("PROVIDER_GENERATION_MISMATCH")

    def _ensure_server_time(self, deadline: float) -> None:
        observed = self._server_time_observed_monotonic
        if observed is None or self._server_time_offset_ms is None:
            self._fetch_server_time(deadline)
            return
        now = _clock_value(self._monotonic_clock)
        if now < observed:
            raise BinanceUsdMProviderError("SERVER_TIME_INVALID")
        if now - observed > _SERVER_TIME_MAX_AGE_SECONDS:
            self._fetch_server_time(deadline)


def make_binance_usdm_demo_provider(
    session_ref: str, credential_obj: object
) -> BinanceUsdMAccountSessionProvider:
    """GatewaySessionOwner-compatible factory for trusted Demo credentials."""

    if type(session_ref) is not str or _SESSION_REF.fullmatch(session_ref) is None:
        raise BinanceUsdMProviderError("INVALID_ACCOUNT_IDENTITY")
    return BinanceUsdMAccountSessionProvider(credential_obj)  # type: ignore[arg-type]


def _credentials(value: object) -> BinanceUsdMApiCredentials:
    if type(value) is BinanceUsdMApiCredentials:
        return value
    if isinstance(value, Mapping):
        try:
            if set(value) != {"api_key", "api_secret"}:
                raise BinanceUsdMProviderError("INVALID_CREDENTIALS")
            return BinanceUsdMApiCredentials(
                api_key=value["api_key"], api_secret=value["api_secret"]
            )
        except BinanceUsdMProviderError:
            raise
        except Exception:
            raise BinanceUsdMProviderError("INVALID_CREDENTIALS") from None
    raise BinanceUsdMProviderError("INVALID_CREDENTIALS")


def _https_get(
    method: str,
    url: str,
    headers: Mapping[str, str],
    timeout: float,
    max_bytes: int,
) -> bytes:
    try:
        parsed = urlsplit(url)
    except (TypeError, ValueError):
        raise BinanceUsdMProviderError("TRANSPORT_FAILED") from None
    if (
        method != "GET"
        or parsed.scheme != "https"
        or parsed.netloc != "demo-fapi.binance.com"
        or parsed.path not in _ROUTES.values()
        or parsed.fragment
    ):
        raise BinanceUsdMProviderError("TRANSPORT_FAILED")
    request = Request(  # noqa: S310 - exact HTTPS origin and route; redirects are disabled
        url, headers=dict(headers), method="GET"
    )
    try:
        opener = build_opener(_NoRedirectHandler())
        with opener.open(request, timeout=timeout) as response:
            payload = response.read(max_bytes + 1)
    except Exception:
        raise BinanceUsdMProviderError("TRANSPORT_FAILED") from None
    if len(payload) > max_bytes:
        raise BinanceUsdMProviderError("RESPONSE_TOO_LARGE")
    return payload


def _deadline(clock: Callable[[], float], timeout: float) -> float:
    _validate_timeout(timeout)
    return _clock_value(clock) + timeout


def _validate_timeout(timeout: float) -> None:
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not (
        0 < timeout <= _MAX_TIMEOUT_SECONDS
    ):
        raise BinanceUsdMProviderError("INVALID_TIMEOUT")


def _validate_generation(generation: str) -> None:
    if type(generation) is not str or not generation or generation != generation.strip():
        raise BinanceUsdMProviderError("INVALID_GENERATION")


def _clock_value(clock: Callable[[], float]) -> float:
    try:
        value = clock()
    except Exception:
        raise BinanceUsdMProviderError("REQUEST_TIMEOUT") from None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise BinanceUsdMProviderError("REQUEST_TIMEOUT")
    return float(value)


def _utc_now(clock: Callable[[], float]) -> str:
    try:
        value = datetime.fromtimestamp(_clock_value(clock), tz=timezone.utc)
    except Exception:
        raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID") from None
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _rows(value: Any, error_code: str) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) > MAX_ACCOUNT_ROWS:
        raise BinanceUsdMProviderError(error_code)
    if any(type(row) is not dict or any(type(key) is not str for key in row) for row in value):
        raise BinanceUsdMProviderError(error_code)
    return value


def _symbol(value: Any) -> str:
    if type(value) is not str or len(value) > _MAX_SYMBOL_LENGTH or _SYMBOL.fullmatch(value) is None:
        raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")
    return value


def _decimal(value: Any) -> Decimal:
    if type(value) is Decimal:
        number = value
    elif type(value) is str and value and len(value) <= 128:
        try:
            number = Decimal(value)
        except (InvalidOperation, ValueError):
            raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID") from None
    else:
        raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")
    if not number.is_finite():
        raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")
    return number


def _decimal_text(value: Any) -> str:
    number = _decimal(value)
    sign, digits, exponent = number.as_tuple()
    if not any(digits):
        return "0"

    # Predict the fixed-point output size before formatting. Decimal accepts
    # short exponent strings with enormous exponents, and format(..., "f")
    # would otherwise allocate the expanded representation before our normal
    # 128-character input/output checks could run.
    digits = list(digits)
    if exponent < 0:
        while exponent < 0 and digits[-1] == 0:
            digits.pop()
            exponent += 1
    digit_count = len(digits)
    sign_width = int(bool(sign))
    if exponent >= 0:
        output_length = sign_width + digit_count + exponent
    elif digit_count + exponent > 0:
        output_length = sign_width + digit_count + 1
    else:
        output_length = sign_width + 2 - exponent
    if output_length > 128:
        raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")

    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    if rendered in {"", "-0", "+0"}:
        return "0"
    if rendered.startswith("+"):
        rendered = rendered[1:]
    if rendered.startswith("."):
        rendered = "0" + rendered
    if rendered.startswith("-."):
        rendered = "-0" + rendered[1:]
    if len(rendered) > 128:
        raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")
    return rendered


def _time_from_ms(value: Any) -> str:
    if type(value) is not int or not 0 <= value <= 253402300799999:
        raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
    except Exception:
        raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID") from None


def _instrument(account_key: AccountKey, symbol: str) -> MarketInstrumentKey:
    return MarketInstrumentKey(
        provider=account_key.provider,
        venue=account_key.venue,
        environment=account_key.environment,
        product_type=_PRODUCT_TYPE,
        instrument_id=symbol,
        native_symbol=symbol,
    )


def _balance(row: dict[str, Any], *, observed_at: str) -> AccountBalance:
    currency = row.get("asset")
    if type(currency) is not str or not currency or len(currency) > 32:
        raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")
    return AccountBalance(
        resource=_RESOURCE,
        currency=currency,
        total=_decimal_text(row.get("crossWalletBalance")),
        available=_decimal_text(row.get("availableBalance")),
        # Binance exposes no cross-only locked field in this route.
        locked=None,
        observed_at_utc=observed_at,
    )


def _position(
    row: dict[str, Any], *, account_key: AccountKey, observed_at: str
) -> AccountPosition:
    symbol = _symbol(row.get("symbol"))
    position_side = row.get("positionSide")
    amount = _decimal(row.get("positionAmt"))
    if position_side == "BOTH":
        side = "net"
        quantity = _decimal_text(row.get("positionAmt"))
    elif position_side == "LONG":
        side = "long"
        quantity = _decimal_text(abs(amount))
    elif position_side == "SHORT":
        side = "short"
        quantity = _decimal_text(abs(amount))
    else:
        raise BinanceUsdMProviderError("ACCOUNT_SNAPSHOT_INVALID")
    entry_price = _decimal_text(row.get("entryPrice"))
    return AccountPosition(
        resource=_RESOURCE,
        instrument=_instrument(account_key, symbol),
        side=side,
        quantity=quantity,
        qty_unit="base_asset",
        average_price=None if Decimal(entry_price) == 0 else entry_price,
        price_currency=None,
        observed_at_utc=observed_at,
    )


def _collect_open_orders(
    regular_rows: list[dict[str, Any]],
    algo_rows: list[dict[str, Any]],
    *,
    margin_by_symbol: Mapping[str, bool],
    account_key: AccountKey,
    observed_at: str,
) -> tuple[AccountOpenOrder, ...]:
    result: list[AccountOpenOrder] = []
    for row in regular_rows:
        symbol = _symbol(row.get("symbol"))
        isolated = margin_by_symbol.get(symbol)
        if type(isolated) is not bool:
            raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")
        if isolated:
            continue
        result.append(_regular_order(row, symbol=symbol, account_key=account_key, observed_at=observed_at))
    for row in algo_rows:
        symbol = _symbol(row.get("symbol"))
        isolated = margin_by_symbol.get(symbol)
        if type(isolated) is not bool:
            raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")
        if isolated:
            continue
        result.append(_algo_order(row, symbol=symbol, account_key=account_key, observed_at=observed_at))
    if len(result) > MAX_ACCOUNT_ROWS:
        raise BinanceUsdMProviderError("ACCOUNT_ROWS_EXCEEDED")
    return tuple(result)


def _regular_order(
    row: dict[str, Any], *, symbol: str, account_key: AccountKey, observed_at: str
) -> AccountOpenOrder:
    side = _order_side(row.get("side"))
    position_side = _position_side(row.get("positionSide"))
    order_type = row.get("origType", row.get("type"))
    status_raw = row.get("status")
    if type(order_type) is not str or not order_type or status_raw not in {
        "NEW",
        "PARTIALLY_FILLED",
    }:
        raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")
    quantity = _decimal_text(row.get("origQty"))
    filled = _decimal_text(row.get("executedQty"))
    limit_price = _optional_nonzero_decimal(row.get("price"))
    stop_price = _optional_nonzero_decimal(row.get("stopPrice"))
    return AccountOpenOrder(
        resource=_RESOURCE,
        instrument=_instrument(account_key, symbol),
        order_id=_provider_id(row.get("orderId")),
        side=side,
        position_side=position_side,
        order_type=order_type,
        status="open" if status_raw == "NEW" else "partially_filled",
        quantity=quantity,
        filled_quantity=filled,
        qty_unit="base_asset",
        created_at_utc=_time_from_ms(row.get("time")),
        observed_at_utc=observed_at,
        client_order_id=_optional_text(row.get("clientOrderId")),
        limit_price=limit_price,
        stop_price=stop_price,
        price_currency=None,
        reduce_only=_optional_bool(row.get("reduceOnly")),
    )


def _algo_order(
    row: dict[str, Any], *, symbol: str, account_key: AccountKey, observed_at: str
) -> AccountOpenOrder:
    if row.get("algoType") != "CONDITIONAL":
        raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")
    status_raw = row.get("algoStatus")
    order_type = row.get("orderType")
    if type(order_type) is not str or not order_type or status_raw not in {"NEW", "WORKING"}:
        raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")
    if row.get("closePosition") is True:
        # The shared AccountOpenOrder contract has no close-all flag/quantity.
        raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")
    quantity = _decimal_text(row.get("quantity"))
    if Decimal(quantity) <= 0:
        raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")
    return AccountOpenOrder(
        resource=_RESOURCE,
        instrument=_instrument(account_key, symbol),
        order_id="algo:" + _provider_id(row.get("algoId")),
        side=_order_side(row.get("side")),
        position_side=_position_side(row.get("positionSide")),
        order_type=order_type,
        status="open",
        quantity=quantity,
        filled_quantity="0",
        qty_unit="base_asset",
        created_at_utc=_time_from_ms(row.get("createTime")),
        observed_at_utc=observed_at,
        client_order_id=_optional_text(row.get("clientAlgoId")),
        limit_price=_optional_nonzero_decimal(row.get("price")),
        stop_price=_optional_nonzero_decimal(row.get("triggerPrice")),
        price_currency=None,
        reduce_only=_optional_bool(row.get("reduceOnly")),
    )


def _provider_id(value: Any) -> str:
    if type(value) is int and value >= 0:
        return str(value)
    if type(value) is str and value and len(value) <= 128 and value.isprintable():
        return value
    raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")


def _order_side(value: Any) -> str:
    if value == "BUY":
        return "buy"
    if value == "SELL":
        return "sell"
    raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")


def _position_side(value: Any) -> str:
    if value == "BOTH":
        return "net"
    if value == "LONG":
        return "long"
    if value == "SHORT":
        return "short"
    raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")


def _optional_nonzero_decimal(value: Any) -> str | None:
    if value is None:
        return None
    normalized = _decimal_text(value)
    return None if Decimal(normalized) == 0 else normalized


def _optional_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if type(value) is not str or len(value) > 256 or not value.isprintable():
        raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")
    return value


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if type(value) is not bool:
        raise BinanceUsdMProviderError("OPEN_ORDER_SHAPE_UNSUPPORTED")
    return value


__all__ = [
    "BinanceUsdMAccountSessionProvider",
    "BinanceUsdMApiCredentials",
    "BinanceUsdMProviderError",
    "make_binance_usdm_demo_provider",
]
