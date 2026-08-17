"""Module-level docstring."""
from __future__ import annotations

from urllib.parse import urlencode

from bt_api_binance.feeds.request_base import BinanceRequestData

# 占位密钥（64 位 hex 零串），非真实凭证
TEST_PRIVATE_KEY = "0" * 64


def test_binance_sign_golden_vector():
    """签名黄金向量：调用 BinanceRequestData.sign 断言黄金值（不自指重实现）。

    复算命令：
    python3 -c "import hmac; from urllib.parse import urlencode; c=urlencode({'recvWindow':3000,'timestamp':1709265105581,'symbol':'OPUSDT'}); k='0'*64; print(hmac.new(k.encode(),c.encode(),digestmod='sha256').hexdigest())"
    """
    content = urlencode({"recvWindow": 3000, "timestamp": 1709265105581, "symbol": "OPUSDT"})
    win_sig = "aafc6c7eea21da4aad680c83027560efb234c6919f5dbeec152b2c10ad1fd684"

    request_data = BinanceRequestData(private_key=TEST_PRIVATE_KEY)
    assert request_data.sign(content) == win_sig


if __name__ == "__main__":
    test_binance_sign_golden_vector()
