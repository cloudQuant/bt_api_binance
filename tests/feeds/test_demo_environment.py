"""Offline demo endpoint, authentication and contract-order regression tests."""
import asyncio
import hashlib
import hmac
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from bt_api_base.feeds.my_websocket_app import MyWebsocketApp

from bt_api_binance import client as client_module
from bt_api_binance.client import BinanceDirectClient
from bt_api_binance.feeds.coin_m import BinanceRequestDataCoinM
from bt_api_binance.feeds.spot import BinanceMarketWssDataSpot, BinanceRequestDataSpot
from bt_api_binance.feeds.swap import (
    BinanceAccountWssDataSwap,
    BinanceMarketWssDataSwap,
    BinanceRequestDataSwap,
)


class _EventBus:
    def __init__(self):
        self.events = []

    def emit(self, event_type, payload):
        self.events.append((event_type, payload))


@pytest.mark.parametrize("cls,environment,rest,stream,account", [
    (BinanceRequestDataSpot, "testnet", "https://testnet.binance.vision", "wss://stream.testnet.binance.vision/ws", "wss://ws-api.testnet.binance.vision/ws-api/v3"),
    (BinanceRequestDataSpot, "demo", "https://demo-api.binance.com", "wss://demo-stream.binance.com/ws", "wss://demo-ws-api.binance.com/ws-api/v3"),
    (BinanceRequestDataSwap, "demo", "https://demo-fapi.binance.com", "wss://demo-fstream.binance.com/ws", "wss://demo-fstream.binance.com/ws"),
])
def test_rest_and_websockets_share_environment(cls, environment, rest, stream, account):
    feed = cls(None, environment=environment)
    assert (feed._params.rest_url, feed._params.wss_url, feed._params.acct_wss_url) == (rest, stream, account)
    assert "demo" not in cls(None)._params.rest_url


@pytest.mark.parametrize("options", [{"environment": "demmo"}, {"testnet": "false"},
                                    {"environment": "production", "demo": True},
                                    {"environment": "demo", "rest_url": "https://fapi.binance.com"},
                                    {"environment": "demo", "wss_url": "wss://fstream.binance.com/ws"}])
def test_mixed_or_unknown_environment_rejected(options):
    with pytest.raises(ValueError):
        BinanceRequestDataSwap(None, **options)


def test_unsupported_asset_has_no_simulation_fallback():
    with pytest.raises(ValueError, match="unsupported"):
        BinanceRequestDataCoinM(None, environment="demo")


def test_testnet_boolean_alias_for_usdm_uses_demo():
    assert BinanceRequestDataSwap(None, testnet=True)._params.rest_url == "https://demo-fapi.binance.com"


def test_public_funding_mark_metadata_work_without_keys(monkeypatch):
    feed = BinanceRequestDataSwap(None, environment="demo")
    request = Mock(return_value={"symbols": []})
    monkeypatch.setattr(feed, "http_request", request)
    for method in (feed.get_exchange_info, feed.get_funding_rate, feed.get_mark_price):
        method("BTCUSDT")
        assert request.call_args.args[1].startswith("https://demo-fapi.binance.com/")
        assert "signature=" not in request.call_args.args[1]
        assert request.call_args.args[2] == {}


def test_ioc_reduce_only_query_signature_and_single_send():
    feed = BinanceRequestDataSwap(None, environment="demo", api_key="fixture-key", api_secret="fixture-secret")
    captured = []
    def respond(request):
        captured.append(request)
        return httpx.Response(200, json={"orderId": 1, "symbol": "BTCUSDT"})
    feed._http_client._sync_client.close()
    feed._http_client._sync_client = httpx.Client(transport=httpx.MockTransport(respond))
    feed.make_order("BTCUSDT", "0.001", price="60000", time_in_force="IOC", reduce_only=True)
    req = captured[0]
    params = parse_qs(urlsplit(str(req.url)).query)
    assert params["timeInForce"] == ["IOC"] and params["reduceOnly"] == ["true"]
    assert params["quantity"] == ["0.001"]
    query, signature = req.url.query.decode().rsplit("&signature=", 1)
    assert signature == hmac.new(b"fixture-secret", query.encode(), hashlib.sha256).hexdigest()
    assert req.url.host == "demo-fapi.binance.com"
    feed._http_client.close()


def test_order_timeout_is_not_retried():
    feed = BinanceRequestDataSwap(None, environment="demo", api_key="fixture-key", api_secret="fixture-secret")
    captured = []
    def timeout(request):
        captured.append(request)
        raise httpx.ReadTimeout("simulated response loss", request=request)
    feed._http_client._sync_client.close()
    feed._http_client._sync_client = httpx.Client(transport=httpx.MockTransport(timeout))
    with pytest.raises(Exception):
        feed.make_order("BTCUSDT", "0.001", price="60000")
    assert len(captured) == 1
    feed._http_client.close()


def test_async_private_requests_use_same_demo_host(monkeypatch):
    feed = BinanceRequestDataSwap(None, environment="demo", api_key="fixture-key", api_secret="fixture-secret")
    request = AsyncMock(return_value={"orderId": 1})
    monkeypatch.setattr(feed, "async_http_request", request)
    asyncio.run(feed.async_request("POST /fapi/v1/order", params={"symbol": "BTCUSDT"}, is_sign=True))
    url = request.call_args.args[1]
    assert url.startswith("https://demo-fapi.binance.com/fapi/v1/order?")
    assert "signature=" in url


def test_spot_market_constructor_keeps_testnet_after_subclass_reset():
    feed = BinanceMarketWssDataSpot(None, environment="testnet")
    assert feed.wss_url == "wss://stream.testnet.binance.vision/ws"
    assert feed._params.rest_url == "https://testnet.binance.vision"


def test_usdm_account_listen_key_and_stream_both_use_demo(monkeypatch):
    captured = []
    def listen(self, max_retries=3):
        captured.append(self._params.rest_url)
        return {"listenKey": "fixture-listen-key"}
    monkeypatch.setattr(BinanceAccountWssDataSwap, "get_listen_key", listen)
    feed = BinanceAccountWssDataSwap(None, environment="demo", api_key="fixture-key", api_secret="fixture-secret")
    assert captured == ["https://demo-fapi.binance.com"]
    assert feed.wss_url == "wss://demo-fstream.binance.com/ws/fixture-listen-key"
    assert feed.public_key == "fixture-key"


def test_usdm_listen_key_keepalive_uses_api_key_only_request_shape(monkeypatch):
    monkeypatch.setattr(
        BinanceAccountWssDataSwap,
        "get_listen_key",
        lambda self, max_retries=3: {"listenKey": "fixture-listen-key"},
    )
    feed = BinanceAccountWssDataSwap(
        None,
        environment="demo",
        api_key="fixture-key",
        api_secret="fixture-secret",
    )
    response = SimpleNamespace(get_data=lambda: {})
    request = Mock(return_value=response)
    monkeypatch.setattr(feed, "request", request)

    assert feed.refresh_listen_key() == {}

    assert request.call_args.args[0] == "PUT /fapi/v1/listenKey"
    assert request.call_args.kwargs["params"] == {}
    assert request.call_args.kwargs["is_sign"] is False


@pytest.mark.parametrize("value", [True, 0, -1, float("inf"), float("nan")])
def test_usdm_listen_key_keepalive_interval_must_be_finite_and_positive(value):
    with pytest.raises(ValueError, match="listen_key_keepalive_interval"):
        BinanceAccountWssDataSwap(
            None,
            environment="demo",
            api_key="fixture-key",
            api_secret="fixture-secret",
            listen_key_keepalive_interval=value,
        )


def test_usdm_expired_listen_key_is_renewed_on_next_connection(monkeypatch):
    listen_keys = iter(("first-listen-key", "second-listen-key"))
    monkeypatch.setattr(
        BinanceAccountWssDataSwap,
        "get_listen_key",
        lambda self, max_retries=3: {"listenKey": next(listen_keys)},
    )
    event_bus = _EventBus()
    feed = BinanceAccountWssDataSwap(
        None,
        environment="demo",
        api_key="fixture-key",
        api_secret="fixture-secret",
        event_bus=event_bus,
    )
    old_socket = Mock()
    feed.ws = old_socket
    feed._running_flag = True

    feed.message_rsp(json.dumps({"e": "listenKeyExpired", "listenKey": "first-listen-key"}))

    assert feed._needs_listen_key_renewal
    assert not feed._running_flag
    old_socket.close.assert_called_once_with()

    next_socket = feed._create_websocket_app()

    assert feed.listen_key == "second-listen-key"
    assert next_socket.url.endswith("/second-listen-key")
    assert not feed._needs_listen_key_renewal
    assert [event for event, _ in event_bus.events] == [
        "ws.listen_key_expired",
        "ws.listen_key_renewal_required",
    ]


def test_usdm_keepalive_failure_requests_renewal_and_stops_with_event(monkeypatch):
    class StopAfterOne:
        calls = 0

        def wait(self, _timeout):
            self.calls += 1
            return self.calls > 1

    monkeypatch.setattr(
        BinanceAccountWssDataSwap,
        "get_listen_key",
        lambda self, max_retries=3: {"listenKey": "fixture-listen-key"},
    )
    feed = BinanceAccountWssDataSwap(
        None,
        environment="demo",
        api_key="fixture-key",
        api_secret="fixture-secret",
        event_bus=_EventBus(),
    )
    feed._stop_event = StopAfterOne()
    feed.listen_key_keepalive_interval = 1.0
    feed._running_flag = True
    feed.logger = Mock()
    feed.ws = Mock()
    feed.refresh_listen_key = Mock(side_effect=RuntimeError("refresh failed"))

    feed.ping()

    assert feed._needs_listen_key_renewal
    feed.ws.close.assert_called_once_with()
    assert [event for event, _ in feed._event_bus.events] == [
        "ws.listen_key_refresh_error",
        "ws.listen_key_renewal_required",
    ]


def test_stale_keepalive_failure_cannot_close_new_listen_key_generation(monkeypatch):
    listen_keys = iter(("first-listen-key", "second-listen-key"))
    monkeypatch.setattr(
        BinanceAccountWssDataSwap,
        "get_listen_key",
        lambda self, max_retries=3: {"listenKey": next(listen_keys)},
    )
    event_bus = _EventBus()
    feed = BinanceAccountWssDataSwap(
        None,
        environment="demo",
        api_key="fixture-key",
        api_secret="fixture-secret",
        event_bus=event_bus,
        listen_key_keepalive_interval=0.001,
    )
    old_socket = Mock()
    new_socket = Mock()
    feed.ws = old_socket
    feed._running_flag = True
    refresh_started = threading.Event()
    release_refresh = threading.Event()

    def delayed_old_generation_failure():
        refresh_started.set()
        assert release_refresh.wait(1.0)
        raise RuntimeError("old generation refresh failed")

    feed.refresh_listen_key = delayed_old_generation_failure
    feed._stop_event = threading.Event()
    keepalive_worker = threading.Thread(target=feed.ping, daemon=True)
    keepalive_worker.start()
    assert refresh_started.wait(1.0)

    feed.message_rsp(
        json.dumps({"e": "listenKeyExpired", "listenKey": "first-listen-key"})
    )
    monkeypatch.setattr(MyWebsocketApp, "_create_websocket_app", lambda self: new_socket)
    assert feed._create_websocket_app() is new_socket
    assert feed.listen_key == "second-listen-key"

    feed._stop_event.set()
    release_refresh.set()
    keepalive_worker.join(1.0)

    assert not keepalive_worker.is_alive()
    assert not feed._needs_listen_key_renewal
    old_socket.close.assert_called_once_with()
    new_socket.close.assert_not_called()
    assert [event for event, _ in event_bus.events].count(
        "ws.listen_key_renewal_required"
    ) == 1


def test_expired_event_for_old_listen_key_does_not_close_current_generation(monkeypatch):
    monkeypatch.setattr(
        BinanceAccountWssDataSwap,
        "get_listen_key",
        lambda self, max_retries=3: {"listenKey": "current-listen-key"},
    )
    event_bus = _EventBus()
    feed = BinanceAccountWssDataSwap(
        None,
        environment="demo",
        api_key="fixture-key",
        api_secret="fixture-secret",
        event_bus=event_bus,
    )
    current_socket = Mock()
    feed.ws = current_socket
    feed._running_flag = True

    feed.message_rsp(
        json.dumps({"e": "listenKeyExpired", "listenKey": "old-listen-key"})
    )

    assert feed._running_flag
    assert not feed._needs_listen_key_renewal
    current_socket.close.assert_not_called()
    assert [event for event, _ in event_bus.events] == [
        "ws.listen_key_expired_ignored"
    ]


def test_direct_client_usdm_demo_market_stream_uses_resolved_endpoint(monkeypatch):
    monkeypatch.setattr(
        client_module.BinanceMarketWssDataSwap,
        "start",
        lambda self, connect_timeout=None: None,
    )
    client = BinanceDirectClient(environment="demo", asset_type="SWAP")

    client.subscribe_symbols(["BTCUSDT"])

    assert client.market_stream._params.wss_url == "wss://demo-fstream.binance.com/ws"
    assert client.market_stream.wss_url == "wss://demo-fstream.binance.com/ws"


def test_direct_client_usdm_demo_account_stream_uses_resolved_endpoint(monkeypatch):
    monkeypatch.setattr(
        client_module.BinanceAccountWssDataSwap,
        "get_listen_key",
        lambda self, max_retries=3: {"listenKey": "fixture-listen-key"},
    )
    monkeypatch.setattr(
        client_module.BinanceAccountWssDataSwap,
        "start",
        lambda self, connect_timeout=None: None,
    )
    client = BinanceDirectClient(
        environment="demo",
        asset_type="SWAP",
        api_key="fixture-key",
        api_secret="fixture-secret",
    )

    client._ensure_account_stream()

    assert client.account_stream._params.acct_wss_url == "wss://demo-fstream.binance.com/ws"
    assert client.account_stream.wss_url == (
        "wss://demo-fstream.binance.com/ws/fixture-listen-key"
    )


def test_subscription_does_not_start_private_stream_without_keys(monkeypatch):
    from bt_api_binance import registry_registration as registry
    instances = []
    class Stream:
        def __init__(self, queue, **kwargs):
            self.options = kwargs
            instances.append(self)
        def start(self):
            pass
    monkeypatch.setattr(registry, "BinanceMarketWssDataSwap", Stream)
    account = Mock()
    monkeypatch.setattr(registry, "BinanceAccountWssDataSwap", account)
    event_bus = object()
    api = SimpleNamespace(_subscription_flags={}, event_bus=event_bus)
    registry._binance_swap_subscribe_handler(
        None,
        {"environment": "demo", "message_idle_timeout": 5},
        [],
        api,
    )
    account.assert_not_called()
    assert instances[0].options["wss_url"] == "wss://demo-fstream.binance.com/ws"
    assert instances[0].options["event_bus"] is event_bus
    assert instances[0].options["message_idle_timeout"] == 5
    assert instances[0].options["wss_name"] == "binance_swap_market_data"
    assert instances[0].options["stream_role"] == "market"
    assert api._subscription_streams == instances


def test_authenticated_subscription_names_market_and_account_streams(monkeypatch):
    from bt_api_binance import registry_registration as registry

    instances = []

    class Stream:
        def __init__(self, queue, **kwargs):
            self.options = kwargs
            instances.append(self)

        def start(self):
            pass

    monkeypatch.setattr(registry, "BinanceMarketWssDataSwap", Stream)
    monkeypatch.setattr(registry, "BinanceAccountWssDataSwap", Stream)
    api = SimpleNamespace(_subscription_flags={}, event_bus=object())

    registry._binance_swap_subscribe_handler(
        None,
        {
            "environment": "demo",
            "api_key": "fixture-key",
            "api_secret": "fixture-secret",
        },
        [],
        api,
    )

    assert [stream.options["wss_name"] for stream in instances] == [
        "binance_swap_market_data",
        "binance_swap_account_data",
    ]
    assert [stream.options["stream_role"] for stream in instances] == [
        "market",
        "account",
    ]


def test_subscription_start_failure_stops_all_new_streams_without_retaining(monkeypatch):
    from bt_api_binance import registry_registration as registry

    instances = []

    class Stream:
        def __init__(self, queue, *, fail=False, **kwargs):
            self.fail = fail
            self.stopped = False
            instances.append(self)

        def start(self):
            if self.fail:
                raise RuntimeError("account start failed")

        def stop(self):
            self.stopped = True

    monkeypatch.setattr(
        registry,
        "BinanceMarketWssDataSwap",
        lambda queue, **kwargs: Stream(queue, **kwargs),
    )
    monkeypatch.setattr(
        registry,
        "BinanceAccountWssDataSwap",
        lambda queue, **kwargs: Stream(queue, fail=True, **kwargs),
    )
    api = SimpleNamespace(_subscription_flags={}, _subscription_streams=[], event_bus=object())

    with pytest.raises(RuntimeError, match="account start failed"):
        registry._binance_swap_subscribe_handler(
            None,
            {
                "environment": "demo",
                "api_key": "fixture-key",
                "api_secret": "fixture-secret",
            },
            [],
            api,
        )

    assert len(instances) == 2
    assert all(stream.stopped for stream in instances)
    assert api._subscription_streams == []
    assert "BINANCE___SWAP_account" not in api._subscription_flags


def test_subscription_cleanup_failure_retains_survivor_and_blocks_retry(monkeypatch):
    from bt_api_binance import registry_registration as registry

    instances = []

    class Stream:
        def __init__(self, queue, *, fail_start=False, fail_stop=False, **kwargs):
            self.fail_start = fail_start
            self.fail_stop = fail_stop
            instances.append(self)

        def start(self):
            if self.fail_start:
                raise RuntimeError("account start failed")

        def stop(self):
            if self.fail_stop:
                raise RuntimeError("market stop failed")

    monkeypatch.setattr(
        registry,
        "BinanceMarketWssDataSwap",
        lambda queue, **kwargs: Stream(queue, fail_stop=True, **kwargs),
    )
    monkeypatch.setattr(
        registry,
        "BinanceAccountWssDataSwap",
        lambda queue, **kwargs: Stream(queue, fail_start=True, **kwargs),
    )
    api = SimpleNamespace(_subscription_flags={}, _subscription_streams=[], event_bus=object())
    options = {
        "environment": "demo",
        "api_key": "fixture-key",
        "api_secret": "fixture-secret",
    }

    with pytest.raises(RuntimeError, match="could not be stopped"):
        registry._binance_swap_subscribe_handler(None, options, [], api)

    assert api._subscription_streams == [instances[0]]
    assert api._subscription_flags["BINANCE___SWAP_subscription_cleanup_failed"] is True
    with pytest.raises(RuntimeError, match="Close BtApi"):
        registry._binance_swap_subscribe_handler(None, options, [], api)
    assert len(instances) == 2


def test_market_stream_becomes_ready_only_after_binance_subscription_ack():
    event_bus = _EventBus()
    feed = BinanceMarketWssDataSwap(
        None,
        environment="demo",
        topics=[{"topic": "book_ticker", "symbol": "BTCUSDT"}],
        event_bus=event_bus,
    )
    feed.ws = Mock()

    assert feed.open_rsp() is False
    assert feed._pending_subscription_acks == 1
    assert not feed._running_flag

    feed.message_rsp(json.dumps({"result": None, "id": 1}))

    assert feed._running_flag
    assert feed._pending_subscription_acks == 0
    assert [event for event, _ in event_bus.events] == ["ws.connected"]


def test_duplicate_binance_ack_does_not_make_multi_topic_stream_ready():
    feed = BinanceMarketWssDataSwap(
        None,
        environment="demo",
        topics=[
            {"topic": "book_ticker", "symbol": "BTCUSDT"},
            {"topic": "mark_price", "symbol": "BTCUSDT"},
        ],
    )
    feed.ws = Mock()

    assert feed.open_rsp() is False
    request_ids = [json.loads(call.args[0])["id"] for call in feed.ws.send.call_args_list]
    assert len(request_ids) == len(set(request_ids)) == 2

    first_ack = json.dumps({"result": None, "id": request_ids[0]})
    feed.message_rsp(first_ack)
    feed.message_rsp(first_ack)

    assert feed._pending_subscription_acks == 1
    assert not feed._running_flag

    feed.message_rsp(json.dumps({"result": None, "id": request_ids[1]}))
    assert feed._running_flag


def test_unsupported_binance_topic_never_becomes_ready():
    feed = BinanceMarketWssDataSwap(
        None,
        environment="demo",
        topics=[{"topic": "unsupported_fixture"}],
    )
    feed.ws = Mock()

    with pytest.raises(RuntimeError, match="Unsupported or incomplete"):
        feed.open_rsp()

    feed.ws.send.assert_not_called()
    assert not feed._running_flag


def test_empty_binance_market_subscription_never_becomes_ready():
    feed = BinanceMarketWssDataSwap(None, environment="demo", topics=[])
    feed.ws = Mock()

    with pytest.raises(RuntimeError, match="at least one topic"):
        feed.open_rsp()

    feed.ws.send.assert_not_called()
    assert not feed._running_flag


def test_binance_subscription_error_closes_stream_and_emits_failure():
    event_bus = _EventBus()
    feed = BinanceMarketWssDataSwap(
        None,
        environment="demo",
        topics=[{"topic": "book_ticker", "symbol": "BTCUSDT"}],
        event_bus=event_bus,
    )
    feed.ws = Mock()
    feed.open_rsp()

    feed.on_message(feed.ws, json.dumps({"code": 2, "msg": "invalid request"}))

    assert not feed._running_flag
    feed.ws.close.assert_called_once_with()
    assert feed._stop_event.is_set()
    assert [event for event, _ in event_bus.events] == ["ws.subscription_error"]


def test_all_account_positions_and_orders_omit_symbol_filter(monkeypatch):
    feed = BinanceRequestDataSwap(None, environment="demo", api_key="fixture-key", api_secret="fixture-secret")
    request = Mock(return_value=[])
    monkeypatch.setattr(feed, "http_request", request)
    feed.get_position(None)
    assert "symbol=" not in request.call_args.args[1]
    feed.get_open_orders(None)
    assert "symbol=" not in request.call_args.args[1]
    extra = {"symbol_name": None, "asset_type": "SWAP"}
    assert feed._get_position_normalize_function([], extra) == ([], True)
    positions, ok = feed._get_position_normalize_function([{"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}], extra)
    assert ok and [position.symbol_name for position in positions] == ["BTCUSDT", "ETHUSDT"]
