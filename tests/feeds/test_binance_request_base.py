"""Module-level docstring."""
from bt_api_base.containers.requestdatas.request_data import RequestData

from bt_api_binance.feeds.request_base import BinanceRequestData


def test_binance_defaults_exchange_name() -> None:
    """test_binance_defaults_exchange_name function"""
    request_data = BinanceRequestData(public_key="public-key", private_key="secret-key")

    assert request_data.exchange_name == "BINANCE___SWAP"


def test_binance_request_allows_missing_extra_data(monkeypatch) -> None:
    """test_binance_request_allows_missing_extra_data function"""
    request_data = BinanceRequestData(
        public_key="public-key",
        private_key="secret-key",
        exchange_name="BINANCE___SPOT",
    )

    monkeypatch.setattr(
        request_data,
        "http_request",
        lambda method, url, headers, body, timeout: {"symbol": "BTCUSDT"},
    )

    result = request_data.request("GET /api/v3/ticker/price", is_sign=False)

    assert isinstance(result, RequestData)
    assert result.get_data() == {"symbol": "BTCUSDT"}
    assert result.get_extra_data() == {}


def test_binance_accepts_api_key_and_api_secret_aliases() -> None:
    """test_binance_accepts_api_key_and_api_secret_aliases function"""
    request_data = BinanceRequestData(api_key="public-key", api_secret="secret-key")

    assert request_data.public_key == "public-key"
    assert request_data.private_key == "secret-key"


def test_binance_error_response_raises_invalid_api_key() -> None:
    """API 错误(code<0)必须翻译为 UnifiedError 并抛出，而非当作正常数据返回。"""
    import pytest

    from bt_api_base.error import UnifiedError

    request_data = BinanceRequestData(public_key="pk", private_key="sk")
    with pytest.raises(UnifiedError):
        request_data._raise_if_error({"code": -2014, "msg": "API-key format invalid."})


def test_binance_error_response_raises_rate_limit() -> None:
    import pytest

    from bt_api_base.error import UnifiedError

    request_data = BinanceRequestData(public_key="pk", private_key="sk")
    with pytest.raises(UnifiedError):
        request_data._raise_if_error({"code": -1003, "msg": "Too many requests."})


def test_binance_error_response_raises_invalid_signature() -> None:
    import pytest

    from bt_api_base.error import UnifiedError

    request_data = BinanceRequestData(public_key="pk", private_key="sk")
    with pytest.raises(UnifiedError):
        request_data._raise_if_error({"code": -1022, "msg": "Signature not valid."})


def test_binance_success_response_does_not_raise() -> None:
    """成功响应(无 code 或 code>=0)不抛异常。"""
    request_data = BinanceRequestData(public_key="pk", private_key="sk")
    request_data._raise_if_error({"symbol": "BTCUSDT", "price": "67000"})


def test_binance_sign_requires_private_key() -> None:
    """私钥缺失时签名必须抛 ConfigurationError，不得用空串静默签名。"""
    import pytest

    from bt_api_base.exceptions import ConfigurationError

    request_data = BinanceRequestData(public_key="pk")  # private_key=None
    with pytest.raises(ConfigurationError):
        request_data.sign("some-content")
