"""Module-level docstring."""
from __future__ import annotations

from urllib.parse import urlencode

from bt_api_binance.feeds.request_base import BinanceRequestData


def test_binance_sign_golden_vector():
    """签名黄金向量：调用 BinanceRequestData.sign 断言黄金值（不自指重实现）。

    复算命令：
    python3 -c "import hmac; from urllib.parse import urlencode; c=urlencode({'recvWindow':3000,'timestamp':1709265105581,'symbol':'OPUSDT'}); k='s4eqlypRMA6svUEcxOSHTgyMW4W2waxkSZ3zqLUTPICyPjuRY9g3N1M23F8cTeQE'; print(hmac.new(k.encode(),c.encode(),digestmod='sha256').hexdigest())"
    """
    content = urlencode({"recvWindow": 3000, "timestamp": 1709265105581, "symbol": "OPUSDT"})
    win_sig = "0e567ed596f286653cb3e1bd34beaf5730feb4f777d9fe8ec342d1ba0fc1fb60"
    private_key = "s4eqlypRMA6svUEcxOSHTgyMW4W2waxkSZ3zqLUTPICyPjuRY9g3N1M23F8cTeQE"

    request_data = BinanceRequestData(private_key=private_key)
    assert request_data.sign(content) == win_sig


if __name__ == "__main__":
    test_binance_sign_golden_vector()
