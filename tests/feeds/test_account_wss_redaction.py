"""Binance account WebSocket diagnostics must not expose credentials."""

from __future__ import annotations

import json
import logging
import threading
from types import SimpleNamespace

import pytest
import websocket

from bt_api_binance.feeds.account_wss_base import BinanceAccountWssData
from bt_api_binance.feeds.spot import BinanceAccountWssDataSpot

LISTEN_KEY = "listen-key-that-must-not-leak"
SIGNATURE = "signature-that-must-not-leak"
API_KEY = "api-key-that-must-not-leak"
PRIVATE_SECRET = "private-secret-that-must-not-leak"
TIMESTAMP = "1700000000123"
SIGNED_URL = (
    "https://demo-fapi.binance.com/fapi/v1/listenKey"
    f"?timestamp={TIMESTAMP}&signature={SIGNATURE}"
)


def _bare_account_stream(logger_name: str) -> BinanceAccountWssData:
    stream = object.__new__(BinanceAccountWssData)
    stream._params = SimpleNamespace(get_rest_path=lambda _name: "/fapi/v1/listenKey")
    stream.asset_type = "SWAP"
    stream.exchange_name = "BINANCE___SWAP"
    stream.logger_name = "binance_account_wss"
    stream.logger = logging.getLogger(f"{logger_name}.request")
    stream.wss_logger = logging.getLogger(f"{logger_name}.socket")
    stream.listen_key_keepalive_interval = 1.0
    stream._stop_event = SimpleNamespace(wait=lambda _timeout: False)
    stream._listen_key_lock = threading.Lock()
    stream.listen_key = LISTEN_KEY
    stream._listen_key_generation = 0
    stream._needs_listen_key_renewal = False
    stream._running_flag = True
    stream._event_bus = None
    stream.ws = None
    return stream


def _assert_secrets_absent(value) -> None:
    rendered = str(value)
    for secret in (LISTEN_KEY, SIGNATURE, API_KEY, PRIVATE_SECRET, TIMESTAMP):
        assert secret not in rendered


def test_get_listen_key_redacts_unexpected_response_and_final_error(caplog) -> None:
    stream = _bare_account_stream("test.binance.account.response")
    stream.request = lambda *args, **kwargs: SimpleNamespace(
        get_data=lambda: {
            "url": f"wss://demo-fstream.binance.com/ws/{LISTEN_KEY}",
            "signature": SIGNATURE,
            "apiKey": API_KEY,
            "secret": PRIVATE_SECRET,
            "timestamp": TIMESTAMP,
        }
    )

    with caplog.at_level(logging.WARNING), pytest.raises(RuntimeError) as caught:
        stream.get_listen_key(max_retries=1)

    _assert_secrets_absent(caplog.text)
    _assert_secrets_absent(caught.value)
    assert caught.value.__context__ is None


def test_get_listen_key_redacts_signed_request_exception(caplog) -> None:
    stream = _bare_account_stream("test.binance.account.exception")

    def fail(*args, **kwargs):
        raise RuntimeError(
            f"failed {SIGNED_URL}; X-MBX-APIKEY={API_KEY}; secret={PRIVATE_SECRET}"
        )

    stream.request = fail
    with caplog.at_level(logging.WARNING), pytest.raises(RuntimeError) as caught:
        stream.get_listen_key(max_retries=1)

    _assert_secrets_absent(caplog.text)
    _assert_secrets_absent(caught.value)
    assert caught.value.__context__ is None


def test_ping_and_non_event_response_logs_are_redacted(monkeypatch, caplog) -> None:
    stream = _bare_account_stream("test.binance.account.misc")
    calls = 0

    def refresh():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError(f"listenKey={LISTEN_KEY}; {SIGNED_URL}")
        raise KeyboardInterrupt

    stream.refresh_listen_key = refresh
    with caplog.at_level(logging.INFO), pytest.raises(KeyboardInterrupt):
        stream.ping()
    stream.message_rsp(
        json.dumps(
            {
                "listenKey": LISTEN_KEY,
                "signature": SIGNATURE,
                "apiKey": API_KEY,
                "secret": PRIVATE_SECRET,
                "timestamp": TIMESTAMP,
            }
        )
    )

    _assert_secrets_absent(caplog.text)


def test_spot_listen_key_uses_verified_tls_and_redacts_callback_error(
    monkeypatch, caplog
) -> None:
    ssl_options = []

    class FakeWebSocketApp:
        def __init__(self, _url, *, on_open, on_message, on_error):
            self.on_error = on_error

        def run_forever(self, *, sslopt):
            ssl_options.append(sslopt)
            self.on_error(
                self,
                RuntimeError(
                    f"apiKey={API_KEY}; secret={PRIVATE_SECRET}; {SIGNED_URL}"
                ),
            )

        def close(self):
            return None

    monkeypatch.setattr(websocket, "WebSocketApp", FakeWebSocketApp)
    stream = object.__new__(BinanceAccountWssDataSpot)
    stream.public_key = API_KEY
    stream._params = SimpleNamespace(acct_wss_url="wss://ws-api.binance.com/ws-api/v3")
    stream.logger = logging.getLogger("test.binance.spot.listen-key")

    with caplog.at_level(logging.WARNING), pytest.raises(RuntimeError) as caught:
        stream.get_listen_key(max_retries=1)

    assert ssl_options
    assert ssl_options[0]["cert_reqs"] != 0
    assert ssl_options[0]["check_hostname"] is True
    _assert_secrets_absent(caplog.text)
    _assert_secrets_absent(caught.value)
    assert caught.value.__context__ is None
