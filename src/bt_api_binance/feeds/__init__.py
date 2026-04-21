# Base classes
from __future__ import annotations

from .account_wss_base import BinanceAccountWssData

# Algo Trading
from .algo import BinanceRequestDataAlgo

# COIN-M Futures
from .coin_m import (
    BinanceAccountWssDataCoinM,
    BinanceMarketWssDataCoinM,
    BinanceRequestDataCoinM,
)

# Grid Trading API
from .grid import BinanceRequestDataGrid

# Margin Trading
from .margin import (
    BinanceAccountWssDataMargin,
    BinanceMarketWssDataMargin,
    BinanceRequestDataMargin,
)
from .market_wss_base import BinanceMarketWssData

# Mining API
from .mining import BinanceRequestDataMining

# European Options
from .option import (
    BinanceAccountWssDataOption,
    BinanceMarketWssDataOption,
    BinanceRequestDataOption,
)

# Portfolio Margin API
from .portfolio import BinanceRequestDataPortfolio
from .request_base import BinanceRequestData

# Spot
from .spot import (
    BinanceAccountWssDataSpot,
    BinanceMarketWssDataSpot,
    BinanceRequestDataSpot,
)

# Staking API
from .staking import BinanceRequestDataStaking

# Sub-account API
from .sub_account import BinanceRequestDataSubAccount

# Swap (USDT-M Futures)
from .swap import (
    BinanceAccountWssDataSwap,
    BinanceMarketWssDataSwap,
    BinanceRequestDataSwap,
)

# VIP Loan API
from .vip_loan import BinanceRequestDataVipLoan

# Wallet API
from .wallet import BinanceRequestDataWallet

__all__ = [
    # Base
    "BinanceRequestData",
    "BinanceMarketWssData",
    "BinanceAccountWssData",
    # Swap
    "BinanceRequestDataSwap",
    "BinanceMarketWssDataSwap",
    "BinanceAccountWssDataSwap",
    # Spot
    "BinanceRequestDataSpot",
    "BinanceMarketWssDataSpot",
    "BinanceAccountWssDataSpot",
    # COIN-M
    "BinanceRequestDataCoinM",
    "BinanceMarketWssDataCoinM",
    "BinanceAccountWssDataCoinM",
    # Option
    "BinanceRequestDataOption",
    "BinanceMarketWssDataOption",
    "BinanceAccountWssDataOption",
    # Margin
    "BinanceRequestDataMargin",
    "BinanceMarketWssDataMargin",
    "BinanceAccountWssDataMargin",
    # Algo
    "BinanceRequestDataAlgo",
    # Wallet
    "BinanceRequestDataWallet",
    # Sub-account
    "BinanceRequestDataSubAccount",
    # Portfolio
    "BinanceRequestDataPortfolio",
    # Grid
    "BinanceRequestDataGrid",
    # Staking
    "BinanceRequestDataStaking",
    # Mining
    "BinanceRequestDataMining",
    # VIP Loan
    "BinanceRequestDataVipLoan",
]
