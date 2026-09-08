"""Binance async callback diagnostics must not expose signing material."""

from __future__ import annotations

import logging
from concurrent.futures import Future

from bt_api_binance.feeds.request_base import BinanceRequestData

SIGNATURE = "signed-value-that-must-not-leak"
API_KEY = "api-key-that-must-not-leak"
PRIVATE_SECRET = "private-secret-that-must-not-leak"
TIMESTAMP = "1700000000123"
SIGNED_URL = (
    "https://demo-fapi.binance.com/fapi/v1/order?symbol=BTCUSDT"
    f"&timestamp={TIMESTAMP}&signature={SIGNATURE}"
)


def test_async_callback_log_redacts_exception_and_traceback(caplog) -> None:
    feed = object.__new__(BinanceRequestData)
    feed.public_key = API_KEY
    feed.private_key = PRIVATE_SECRET
    test_logger = logging.getLogger("test.binance.async.callback.redaction")
    feed.async_logger = test_logger
    future = Future()
    future.set_exception(
        RuntimeError(f"failed {SIGNED_URL}; X-MBX-APIKEY={API_KEY}; secret={PRIVATE_SECRET}")
    )

    with caplog.at_level(logging.WARNING, logger=test_logger.name):
        feed.async_callback(future)

    for secret in (SIGNATURE, API_KEY, PRIVATE_SECRET, TIMESTAMP):
        assert secret not in caplog.text
