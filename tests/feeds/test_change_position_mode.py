"""Offline USD-M position-mode mutation request tests."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from bt_api_binance.feeds.swap import BinanceRequestDataSwap


@pytest.mark.parametrize("dual_side,wire_value", [(True, "true"), (False, "false")])
def test_change_position_mode_uses_signed_account_wide_endpoint(
    monkeypatch, dual_side, wire_value
):
    feed = BinanceRequestDataSwap(None, environment="demo")
    request = Mock(return_value={"code": 200, "msg": "success"})
    monkeypatch.setattr(feed, "request", request)
    try:
        result = feed.change_position_mode(
            dual_side,
            extra_data={"trace": "offline"},
            recvWindow=5000,
        )
        assert result == {"code": 200, "msg": "success"}
        assert request.call_args.args == ("POST /fapi/v1/positionSide/dual",)
        assert request.call_args.kwargs["params"] == {"dualSidePosition": wire_value}
        assert request.call_args.kwargs["is_sign"] is True
        extra_data = request.call_args.kwargs["extra_data"]
        assert extra_data["request_type"] == "change_position_mode"
        assert extra_data["trace"] == "offline"
        assert extra_data["recvWindow"] == 5000
    finally:
        feed._http_client.close()


@pytest.mark.parametrize("value", [None, 0, 1, "true", "false"])
def test_change_position_mode_rejects_non_boolean_before_request(monkeypatch, value):
    feed = BinanceRequestDataSwap(None, environment="demo")
    request = Mock()
    monkeypatch.setattr(feed, "request", request)
    try:
        with pytest.raises(TypeError, match="must be a bool"):
            feed.change_position_mode(value)
        request.assert_not_called()
    finally:
        feed._http_client.close()


def test_async_change_position_mode_schedules_the_same_signed_request(monkeypatch):
    feed = BinanceRequestDataSwap(None, environment="demo")
    pending = object()
    async_request = Mock(return_value=pending)
    submit = Mock()
    monkeypatch.setattr(feed, "async_request", async_request)
    monkeypatch.setattr(feed, "submit", submit)
    try:
        feed.async_change_position_mode(True, extra_data={"trace": "offline"})
        async_request.assert_called_once()
        assert async_request.call_args.args == ("POST /fapi/v1/positionSide/dual",)
        assert async_request.call_args.kwargs["params"] == {"dualSidePosition": "true"}
        assert async_request.call_args.kwargs["is_sign"] is True
        submit.assert_called_once_with(pending, callback=feed.async_callback)
    finally:
        feed._http_client.close()
