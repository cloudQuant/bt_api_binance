"""Binance-specific normalization choices used by the unified SDK."""

from bt_api_base.normalization_policy import LegacyNormalizationPolicy


class BinanceNormalizationPolicy(LegacyNormalizationPolicy):
    default_multiplier = 1.0


class BinanceSwapNormalizationPolicy(BinanceNormalizationPolicy):
    zero_balance_currency = "USDT"


def normalization_policy(exchange_name):
    if exchange_name == "BINANCE___SWAP":
        return BinanceSwapNormalizationPolicy()
    return BinanceNormalizationPolicy()


__all__ = ("normalization_policy",)
