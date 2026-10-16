"""Focused fake-transport contract tests for the USDⓈ-M Demo session provider."""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler

import pytest
from bt_api_base.account_protocol import AccountKey

import bt_api_binance.account_session_provider as provider_module
from bt_api_binance.account_session_provider import (
    BinanceUsdMAccountSessionProvider,
    BinanceUsdMApiCredentials,
    BinanceUsdMProviderError,
    make_binance_usdm_demo_provider,
)

_LOCAL_TIME = 1_700_000_000.0
_GENERATION = "generation-01"
_TEST_API_SECRET = "fixture-api-secret"


class _FakeBinanceTransport:
    def __init__(self, *, local_time: float = _LOCAL_TIME) -> None:
        self.local_time = local_time
        self.calls: list[tuple[str, str, dict[str, str], float]] = []

    def __call__(self, method, url, headers, timeout, max_bytes):
        self.calls.append((method, url, dict(headers), timeout))
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "demo-fapi.binance.com":
            raise AssertionError("provider attempted a non-Demo host")
        if method != "GET":
            raise AssertionError("provider attempted a non-read method")
        payloads = {
            "/fapi/v1/time": {"serverTime": int(self.local_time * 1000)},
            "/fapi/v1/accountConfig": {
                "canTrade": True,
                "canDeposit": False,
                "canWithdraw": False,
                "dualSidePosition": True,
                "updateTime": 0,
            },
            "/fapi/v2/account": {
                "updateTime": 0,
                "multiAssetsMargin": False,
                "assets": [
                    {
                        "asset": "USDT",
                        "walletBalance": "12.00",
                        "crossWalletBalance": "10.00",
                        "availableBalance": "7.50",
                    }
                ],
                "positions": [
                    {
                        "symbol": "BTCUSDT",
                        "positionSide": "BOTH",
                        "positionAmt": "0.250",
                        "isolated": False,
                        "entryPrice": "40000.00",
                        "updateTime": 0,
                    },
                    {
                        "symbol": "ETHUSDT",
                        "positionSide": "SHORT",
                        "positionAmt": "-1.50",
                        "isolated": False,
                        "entryPrice": "2000",
                        "updateTime": 0,
                    },
                    {
                        "symbol": "SOLUSDT",
                        "positionSide": "BOTH",
                        "positionAmt": "2",
                        "isolated": True,
                        "entryPrice": "100",
                        "updateTime": 0,
                    },
                ],
            },
            "/fapi/v1/openOrders": [
                {
                    "symbol": "BTCUSDT",
                    "orderId": 11,
                    "clientOrderId": "client-11",
                    "side": "BUY",
                    "positionSide": "BOTH",
                    "origType": "LIMIT",
                    "status": "PARTIALLY_FILLED",
                    "origQty": "1.0",
                    "executedQty": "0.25",
                    "price": "39900.00",
                    "stopPrice": "0",
                    "time": int(self.local_time * 1000) - 1_000,
                    "reduceOnly": True,
                },
                {
                    "symbol": "SOLUSDT",
                    "orderId": 12,
                    "side": "SELL",
                    "positionSide": "BOTH",
                    "type": "LIMIT",
                    "status": "NEW",
                    "origQty": "1",
                    "executedQty": "0",
                    "price": "101",
                    "time": int(self.local_time * 1000) - 1_000,
                    "reduceOnly": False,
                },
            ],
            "/fapi/v1/openAlgoOrders": [
                {
                    "algoId": 21,
                    "clientAlgoId": "algo-21",
                    "algoType": "CONDITIONAL",
                    "orderType": "STOP_MARKET",
                    "symbol": "BTCUSDT",
                    "side": "SELL",
                    "positionSide": "BOTH",
                    "quantity": "0.25",
                    "algoStatus": "NEW",
                    "triggerPrice": "39000",
                    "price": "0",
                    "closePosition": False,
                    "reduceOnly": True,
                    "createTime": int(self.local_time * 1000) - 2_000,
                }
            ],
        }
        if parsed.path not in payloads:
            raise AssertionError(f"unexpected route: {parsed.path}")
        return json.dumps(payloads[parsed.path], separators=(",", ":")).encode()


def _provider(transport, *, local_time=_LOCAL_TIME):
    return BinanceUsdMAccountSessionProvider(
        BinanceUsdMApiCredentials("fixture-api-key", "fixture-api-secret"),
        transport=transport,
        wall_clock=lambda: local_time,
        monotonic_clock=lambda: 10.0,
    )


def _account_key(environment="demo"):
    return AccountKey(
        provider="binance",
        venue="binance",
        environment=environment,
        account_id="configured-account",
    )


def _assert_signed_query(url, secret):
    raw = urlsplit(url).query
    query_without_signature, signature = raw.rsplit("&signature=", 1)
    expected = hmac.new(secret.encode(), query_without_signature.encode(), hashlib.sha256)
    assert hmac.compare_digest(signature, expected.hexdigest())
    params = parse_qs(query_without_signature)
    assert set(params) == {"recvWindow", "timestamp"}
    assert params["recvWindow"] == ["5000"]


def test_normal_demo_snapshot_reads_only_fixed_signed_get_routes_and_preserves_facts():
    transport = _FakeBinanceTransport()
    provider = _provider(transport)
    provider.connect(account_key=_account_key(), generation=_GENERATION, timeout=2.0)

    server_time = provider.read_exchange_server_time(generation=_GENERATION, timeout=2.0)
    config = provider.read_account_configuration(generation=_GENERATION, timeout=2.0)
    observation = provider.read_account(generation=_GENERATION, timeout=2.0)

    assert server_time == {"serverTime": 1_700_000_000_000}
    assert config == {
        "canTrade": True,
        "canDeposit": False,
        "canWithdraw": False,
        "dualSidePosition": True,
    }
    assert observation.account_key == _account_key()
    assert observation.consistency == "multi_query"
    assert observation.balances_complete is True
    assert observation.positions_complete is True
    assert observation.open_orders_complete is True
    assert observation.coverage[0].product_type == "usdm_perpetual"
    assert observation.coverage[0].margin_pool == "cross"
    assert [(row.currency, row.total, row.available, row.locked) for row in observation.balances] == [
        ("USDT", "10", "7.5", None)
    ]
    assert [(row.instrument.native_symbol, row.side, row.quantity) for row in observation.positions] == [
        ("BTCUSDT", "net", "0.25"),
        ("ETHUSDT", "short", "1.5"),
    ]
    assert [row.order_id for row in observation.open_orders] == ["11", "algo:21"]
    assert observation.open_orders[0].status == "partially_filled"
    assert observation.open_orders[0].limit_price == "39900"
    assert observation.open_orders[1].stop_price == "39000"
    assert all(call[0] == "GET" for call in transport.calls)
    assert [urlsplit(call[1]).path for call in transport.calls] == [
        "/fapi/v1/time",
        "/fapi/v1/time",
        "/fapi/v1/accountConfig",
        "/fapi/v2/account",
        "/fapi/v1/openOrders",
        "/fapi/v1/openAlgoOrders",
    ]
    for _method, url, headers, timeout in transport.calls:
        assert timeout > 0
        if urlsplit(url).path == "/fapi/v1/time":
            assert "X-MBX-APIKEY" not in headers
            assert urlsplit(url).query == ""
        else:
            assert headers["X-MBX-APIKEY"] == "fixture-api-key"
            _assert_signed_query(url, _TEST_API_SECRET)


def test_factory_and_repr_keep_secret_material_local_and_redacted():
    credentials = BinanceUsdMApiCredentials("fixture-api-key", "fixture-api-secret")
    assert "fixture" not in repr(credentials)
    assert "fixture" not in repr(_provider(_FakeBinanceTransport()))
    provider = make_binance_usdm_demo_provider(
        "configured-session", {"api_key": "fixture-api-key", "api_secret": "fixture-api-secret"}
    )
    assert isinstance(provider, BinanceUsdMAccountSessionProvider)
    assert "fixture" not in repr(provider)
    with pytest.raises(BinanceUsdMProviderError) as error:
        make_binance_usdm_demo_provider(
            "configured-session", {"api_key": "fixture-api-key", "api_secret": "secret", "extra": "x"}
        )
    assert error.value.code == "INVALID_CREDENTIALS"
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("environment", ["production", "testnet", "unknown"])
def test_provider_refuses_non_demo_account_identity_before_transport(environment):
    transport = _FakeBinanceTransport()
    provider = _provider(transport)
    with pytest.raises(BinanceUsdMProviderError) as error:
        provider.connect(account_key=_account_key(environment), generation=_GENERATION, timeout=2.0)
    assert error.value.code == "INVALID_ACCOUNT_IDENTITY"
    assert transport.calls == []


def test_read_facts_bind_exact_active_generation_and_close_is_idempotent():
    transport = _FakeBinanceTransport()
    provider = _provider(transport)
    provider.connect(account_key=_account_key(), generation=_GENERATION, timeout=2.0)
    with pytest.raises(BinanceUsdMProviderError) as error:
        provider.read_account(generation="another-generation", timeout=2.0)
    assert error.value.code == "PROVIDER_GENERATION_MISMATCH"
    assert provider.close() is True
    assert provider.close() is True
    with pytest.raises(BinanceUsdMProviderError) as error:
        provider.read_exchange_server_time(generation=_GENERATION, timeout=2.0)
    assert error.value.code == "PROVIDER_SESSION_CLOSED"


def test_signed_read_refreshes_stale_exchange_clock_before_request():
    transport = _FakeBinanceTransport()
    monotonic_now = [10.0]
    provider = BinanceUsdMAccountSessionProvider(
        BinanceUsdMApiCredentials("fixture-api-key", _TEST_API_SECRET),
        transport=transport,
        wall_clock=lambda: _LOCAL_TIME,
        monotonic_clock=lambda: monotonic_now[0],
    )
    provider.connect(account_key=_account_key(), generation=_GENERATION, timeout=2.0)
    assert [urlsplit(call[1]).path for call in transport.calls] == ["/fapi/v1/time"]

    monotonic_now[0] += 61.0
    result = provider.read_account_configuration(generation=_GENERATION, timeout=2.0)

    assert result["canTrade"] is True
    assert [urlsplit(call[1]).path for call in transport.calls] == [
        "/fapi/v1/time",
        "/fapi/v1/time",
        "/fapi/v1/accountConfig",
    ]
    refresh_headers = transport.calls[-1][2]
    assert refresh_headers["X-MBX-APIKEY"] == "fixture-api-key"
    _assert_signed_query(transport.calls[-1][1], _TEST_API_SECRET)


def test_unsupported_algo_close_all_shape_fails_closed_after_read_only_gets():
    transport = _FakeBinanceTransport()
    original = transport.__call__

    def with_close_all(method, url, headers, timeout, max_bytes):
        body = original(method, url, headers, timeout, max_bytes)
        if urlsplit(url).path == "/fapi/v1/openAlgoOrders":
            rows = json.loads(body)
            rows[0]["closePosition"] = True
            return json.dumps(rows).encode()
        return body

    provider = BinanceUsdMAccountSessionProvider(
        BinanceUsdMApiCredentials("fixture-api-key", "fixture-api-secret"),
        transport=with_close_all,
        wall_clock=lambda: _LOCAL_TIME,
        monotonic_clock=lambda: 10.0,
    )
    provider.connect(account_key=_account_key(), generation=_GENERATION, timeout=2.0)
    with pytest.raises(BinanceUsdMProviderError) as error:
        provider.read_account(generation=_GENERATION, timeout=2.0)
    assert error.value.code == "OPEN_ORDER_SHAPE_UNSUPPORTED"
    assert all(call[0] == "GET" for call in transport.calls)


def test_multi_assets_account_mode_is_rejected_before_order_reads():
    transport = _FakeBinanceTransport()
    original = transport.__call__

    def multi_assets_response(method, url, headers, timeout, max_bytes):
        body = original(method, url, headers, timeout, max_bytes)
        if urlsplit(url).path == "/fapi/v2/account":
            account = json.loads(body)
            account["multiAssetsMargin"] = True
            return json.dumps(account).encode()
        return body

    provider = BinanceUsdMAccountSessionProvider(
        BinanceUsdMApiCredentials("fixture-api-key", _TEST_API_SECRET),
        transport=multi_assets_response,
        wall_clock=lambda: _LOCAL_TIME,
        monotonic_clock=lambda: 10.0,
    )
    provider.connect(account_key=_account_key(), generation=_GENERATION, timeout=2.0)

    with pytest.raises(BinanceUsdMProviderError) as error:
        provider.read_account(generation=_GENERATION, timeout=2.0)

    assert error.value.code == "ACCOUNT_COVERAGE_UNSUPPORTED"
    assert [urlsplit(call[1]).path for call in transport.calls] == [
        "/fapi/v1/time",
        "/fapi/v2/account",
    ]


def test_https_transport_never_follows_cross_origin_redirects(monkeypatch):
    target = "http://attacker.invalid/collect"
    forwarded = []
    open_calls = []

    # Pin the concrete stdlib behavior that made the default opener unsafe for
    # signed requests: a GET redirect to another origin carries the API key.
    original_request = provider_module.Request(
        "https://demo-fapi.binance.com/fapi/v2/account",
        headers={"X-MBX-APIKEY": "fixture-api-key"},
        method="GET",
    )
    default_redirect = HTTPRedirectHandler().redirect_request(
        original_request, None, 302, "Found", {"Location": target}, target
    )
    assert default_redirect is not None
    redirected_headers = {
        key.lower(): value for key, value in default_redirect.header_items()
    }
    assert redirected_headers["x-mbx-apikey"] == "fixture-api-key"

    def fake_build_opener(*handlers):
        redirect_handler = next(
            (handler for handler in handlers if isinstance(handler, HTTPRedirectHandler)),
            HTTPRedirectHandler(),
        )

        class FakeOpener:
            def open(self, request, timeout):
                open_calls.append((request, timeout))
                redirected = redirect_handler.redirect_request(
                    request, None, 302, "Found", {"Location": target}, target
                )
                if redirected is not None:
                    forwarded.append(redirected)
                raise HTTPError(request.full_url, 302, "redirect blocked", {}, None)

        return FakeOpener()

    def unsafe_urlopen(request, timeout):
        # A regression to urlopen would silently restore its default redirect
        # handler; model that path too without opening a socket.
        redirected = HTTPRedirectHandler().redirect_request(
            request, None, 302, "Found", {"Location": target}, target
        )
        if redirected is not None:
            forwarded.append(redirected)
        raise HTTPError(request.full_url, 302, "redirect blocked", {}, None)

    monkeypatch.setattr(provider_module, "build_opener", fake_build_opener)
    monkeypatch.setattr(provider_module, "urlopen", unsafe_urlopen, raising=False)

    with pytest.raises(BinanceUsdMProviderError) as error:
        provider_module._https_get(
            "GET",
            "https://demo-fapi.binance.com/fapi/v2/account?timestamp=1&signature=x",
            {"X-MBX-APIKEY": "fixture-api-key"},
            1.0,
            1024,
        )

    assert error.value.code == "TRANSPORT_FAILED"
    assert len(open_calls) == 1
    assert open_calls[0][1] == 1.0
    assert forwarded == []


@pytest.mark.parametrize("value", ["1e999999999999", "-1e-999999999999"])
def test_decimal_text_rejects_extreme_exponents_before_expansion(value):
    with pytest.raises(BinanceUsdMProviderError) as error:
        provider_module._decimal_text(value)
    assert error.value.code == "ACCOUNT_SNAPSHOT_INVALID"


def test_decimal_text_keeps_bounded_fixed_point_normalization():
    assert provider_module._decimal_text("1.2300") == "1.23"
    assert provider_module._decimal_text("1e126") == "1" + ("0" * 126)


def test_factory_starts_only_after_valid_session_and_timeout_is_bounded():
    transport = _FakeBinanceTransport()
    provider = _provider(transport)
    with pytest.raises(BinanceUsdMProviderError) as error:
        provider.read_account(generation=_GENERATION, timeout=2.0)
    assert error.value.code == "PROVIDER_SESSION_NOT_ACTIVE"
    with pytest.raises(BinanceUsdMProviderError) as error:
        provider.connect(account_key=_account_key(), generation=_GENERATION, timeout=0)
    assert error.value.code == "INVALID_TIMEOUT"
    assert transport.calls == []
