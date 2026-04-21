---
title: Home | bt_api_binance
---

<!-- English -->
# bt_api_binance Documentation

[![PyPI Version](https://img.shields.io/pypi/v/bt_api_binance.svg)](https://pypi.org/project/bt_api_binance/)
[![Python Versions](https://img.shields.io/pypi/pyversions/bt_api_binance.svg)](https://pypi.org/project/bt_api_binance/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/cloudQuant/bt_api_binance/actions/workflows/ci.yml/badge.svg)](https://github.com/cloudQuant/bt_api_binance/actions)
[![Docs](https://readthedocs.org/projects/bt-api-binance/badge/?version=latest)](https://bt-api-binance.readthedocs.io/)

## Overview

`bt_api_binance` is the **Binance exchange plugin** for the [bt_api](https://github.com/cloudQuant/bt_api_py) plugin ecosystem. It provides unified REST and WebSocket interfaces for **Spot**, **Futures** (USDT-M and COIN-M), **Margin**, **Options**, **Algo Orders**, **Grid Trading**, **Staking**, **Mining**, **VIP Loans**, **Wallet**, **Sub-Accounts**, and **Portfolio Margin**.

This package is a **runtime plugin dependency** for `bt_api` applications connecting to Binance. It depends on [bt_api_base](https://github.com/cloudQuant/bt_api_base) for core infrastructure (registry, event bus, WebSocket management, caching, rate limiting).

## Key Benefits

- **12+ Asset Types**: Spot, USDT-M Futures, COIN-M Futures, Margin, Options, Algo, Grid, Staking, Mining, VIP Loans, Wallet, Sub-Accounts, Portfolio Margin
- **Dual API Modes**: Synchronous REST and asynchronous WebSocket streaming
- **Plugin Architecture**: Integrates via `ExchangeRegistry` — auto-registers at import time
- **Direct Client Mode**: `BinanceDirectClient` for standalone use without the full bt_api framework
- **Unified Data Model**: All responses normalized to bt_api_base container types (Ticker, OrderBook, Bar, Order, Position, Balance...)
- **Config-Driven**: YAML-based exchange configuration — no hardcoded endpoints
- **HMAC-SHA256 Auth**: Full request signing for authenticated endpoints

## Architecture Overview

```
bt_api_binance/
├── client.py                  # BinanceDirectClient — standalone REST + WebSocket client
├── plugin.py                 # register_plugin() — bt_api plugin entry point
├── registry_registration.py   # register_binance() — feeds/exchange_data/balance_handler registration
├── exchange_data/
│   └── binance_exchange_data.py  # BinanceExchangeData (base) + 12 asset-type subclasses
├── feeds/
│   ├── spot.py              # BinanceRequestDataSpot, BinanceMarketWssDataSpot, BinanceAccountWssDataSpot
│   ├── swap.py               # BinanceRequestDataSwap, BinanceMarketWssDataSwap, BinanceAccountWssDataSwap
│   ├── coin_m.py             # BinanceRequestDataCoinM, BinanceMarketWssDataCoinM, BinanceAccountWssDataCoinM
│   ├── margin.py             # Margin trading feeds
│   ├── option.py            # Options trading feeds
│   ├── algo.py              # TWAP/VWAP algo order feeds
│   ├── grid.py              # Grid trading feeds
│   ├── staking.py           # Staking/LDEX feeds
│   ├── mining.py            # Mining API feeds
│   ├── vip_loan.py         # VIP loan feeds
│   ├── sub_account.py       # Sub-account management feeds
│   ├── wallet.py            # Wallet/asset management feeds
│   ├── portfolio.py         # Portfolio margin feeds
│   └── (bases: request_base.py, market_wss_base.py, account_wss_base.py)
├── containers/               # 12 data container types (orders, balances, positions, tickers...)
├── gateway/
│   └── adapter.py           # BinanceGatewayAdapter(PluginGatewayAdapter)
├── errors/
│   └── binance_translator.py  # BinanceErrorTranslator
└── configs/
    └── binance.yaml         # Full YAML config (URLs, paths, rate limits for all asset types)
```

## Supported Exchange Codes

| Exchange Code | Asset Type | REST Base | WSS Base |
|---|---|---|---|
| `BINANCE___SPOT` | Spot | `https://api.binance.com` | `wss://stream.binance.com:9443/ws` |
| `BINANCE___SWAP` | USDT-M Futures | `https://fapi.binance.com` | `wss://fstream.binance.com/ws` |
| `BINANCE___COIN_M` | COIN-M Futures | `https://dapi.binance.com` | `wss://dstream.binance.com/ws` |
| `BINANCE___MARGIN` | Cross/Isolated Margin | `https://api.binance.com` | `wss://stream.binance.com/ws` |
| `BINANCE___OPTION` | Options | `https://eapi.binance.com` | `wss://nbstream.binance.com/eoptions/ws` |
| `BINANCE___ALGO` | TWAP/VWAP | `https://api.binance.com` | — |
| `BINANCE___GRID` | Grid Trading | `https://api.binance.com` | — |
| `BINANCE___STAKING` | Staking/LDEX | `https://api.binance.com` | — |
| `BINANCE___MINING` | Mining | `https://api.binance.com` | — |
| `BINANCE___VIP_LOAN` | VIP Loans | `https://api.binance.com` | — |
| `BINANCE___WALLET` | Wallet | `https://api.binance.com` | — |
| `BINANCE___SUB_ACCOUNT` | Sub-Accounts | `https://api.binance.com` | — |
| `BINANCE___PORTFOLIO` | Portfolio Margin | `https://api.binance.com` | — |

## Quick Start

### Installation

```bash
pip install bt_api_binance
```

Or from source:

```bash
git clone https://github.com/cloudQuant/bt_api_binance
cd bt_api_binance
pip install -e .
```

### Standalone Direct Client

```python
from bt_api_binance import BinanceApi

client = BinanceApi(
    api_key="your_api_key",
    secret_key="your_secret",
    asset_type="SPOT",
    testnet=True,
)

client.connect()

client.subscribe_symbols(["BTCUSDT", "ETHUSDT"])

while True:
    channel, data = client.poll_output()
    if channel == "market":
        print(f"{data['symbol']}: price={data['price']}, bid={data['bid_price']}, ask={data['ask_price']}")
```

### bt_api Plugin Integration

```python
from bt_api_py import BtApi

api = BtApi(
    exchange_kwargs={
        "BINANCE___SPOT": {
            "api_key": "your_key",
            "secret": "your_secret",
            "testnet": True,
        }
    }
)

ticker = api.get_tick("BINANCE___SPOT", "BTCUSDT")
balance = api.get_balance("BINANCE___SPOT")
order = api.make_order(
    exchange_name="BINANCE___SPOT",
    symbol="BTCUSDT",
    volume=0.001,
    price=50000,
    order_type="limit",
)
```

### WebSocket Subscription

```python
api.subscribe(
    "BINANCE___SPOT___BTCUSDT",
    [
        {"topic": "ticker", "symbol": "BTCUSDT"},
        {"topic": "depth", "symbol": "BTCUSDT", "depth": 20},
    ],
)

data_queue = api.get_data_queue("BINANCE___SPOT")
while True:
    msg = data_queue.get(timeout=10)
    print(type(msg).__name__, msg)
```

## API Reference

- [Client](api/client.md) — BinanceDirectClient standalone entry point
- [Feeds](api/feeds.md) — REST request feeds and WebSocket market/account feeds
- [Exchange Data](api/exchange_data.md) — Exchange configuration classes
- [Containers](api/containers.md) — Normalized data containers
- [WebSocket](api/websocket.md) — WebSocket adapter
- [Gateway](api/gateway.md) — Gateway adapter

## Online Documentation

| Resource | Link |
|----------|------|
| English Docs | https://bt-api-binance.readthedocs.io/ |
| Chinese Docs | https://bt-api-binance.readthedocs.io/zh/latest/ |
| GitHub Repository | https://github.com/cloudQuant/bt_api_binance |
| Issue Tracker | https://github.com/cloudQuant/bt_api_binance/issues |
| PyPI Package | https://pypi.org/project/bt_api_binance/ |
| bt_api_base Docs | https://bt-api-base.readthedocs.io/ |
| Main Project | https://github.com/cloudQuant/bt_api_py |

---

## 中文

### 概述

`bt_api_binance` 是 [bt_api](https://github.com/cloudQuant/bt_api_py) 插件生态系统的 **Binance 交易所插件**。它为**现货**、**合约**（U本位和币本位）、**杠杆**、**期权**、**算法单**、**网格交易**、**质押**、**矿池**、**VIP借贷**、**钱包**、**子账户**和**组合保证金**提供统一的 REST 和 WebSocket 接口。

本包是 `bt_api` 应用连接 Binance 的**运行时插件依赖**。它依赖 [bt_api_base](https://github.com/cloudQuant/bt_api_base) 提供核心基础设施（注册表、事件总线、WebSocket 管理、缓存、限流）。

### 核心优势

- **12+ 资产类型**: 现货、U本位合约、币本位合约、杠杆、期权、算法单、网格交易、质押、矿池、VIP借贷、钱包、子账户、组合保证金
- **双 API 模式**: 同步 REST 和异步 WebSocket 流
- **插件架构**: 通过 `ExchangeRegistry` 集成 — 导入时自动注册
- **独立客户端模式**: `BinanceDirectClient` 无需完整 bt_api 框架即可独立使用
- **统一数据模型**: 所有响应规范化为 bt_api_base 容器类型（行情、订单簿、K线、订单、持仓、余额...）
- **配置驱动**: YAML 配置文件 — 无硬编码端点
- **HMAC-SHA256 认证**: 完整请求签名支持

### 架构

```
bt_api_binance/
├── client.py                  # BinanceDirectClient — 独立 REST + WebSocket 客户端
├── plugin.py                 # register_plugin() — bt_api 插件入口
├── registry_registration.py   # register_binance() — feeds/exchange_data/balance_handler 注册
├── exchange_data/
│   └── binance_exchange_data.py  # BinanceExchangeData（基类）+ 12 个资产类型子类
├── feeds/
│   ├── spot.py              # 现货请求、WebSocket 市场、WebSocket 账户 feeds
│   ├── swap.py               # USDT-M 合约 feeds
│   ├── coin_m.py            # 币本位合约 feeds
│   ├── margin.py, option.py, algo.py, grid.py, staking.py,
│   │   mining.py, vip_loan.py, sub_account.py, wallet.py, portfolio.py
│   └── (基类: request_base.py, market_wss_base.py, account_wss_base.py)
├── containers/               # 12 种数据容器类型
├── gateway/
│   └── adapter.py           # BinanceGatewayAdapter(PluginGatewayAdapter)
├── errors/
│   └── binance_translator.py  # BinanceErrorTranslator
└── configs/
    └── binance.yaml         # 全部资产类型的完整 YAML 配置
```

### 支持的交易所代码

| 交易所代码 | 资产类型 | REST 基础地址 | WSS 基础地址 |
|---|---|---|---|
| `BINANCE___SPOT` | 现货 | `https://api.binance.com` | `wss://stream.binance.com:9443/ws` |
| `BINANCE___SWAP` | U本位永续 | `https://fapi.binance.com` | `wss://fstream.binance.com/ws` |
| `BINANCE___COIN_M` | 币本位永续 | `https://dapi.binance.com` | `wss://dstream.binance.com/ws` |
| `BINANCE___MARGIN` | 全仓/逐仓杠杆 | `https://api.binance.com` | `wss://stream.binance.com/ws` |
| `BINANCE___OPTION` | 期权 | `https://eapi.binance.com` | `wss://nbstream.binance.com/eoptions/ws` |
| `BINANCE___ALGO` | TWAP/VWAP | `https://api.binance.com` | — |
| `BINANCE___GRID` | 网格交易 | `https://api.binance.com` | — |
| `BINANCE___STAKING` | 质押理财 | `https://api.binance.com` | — |
| `BINANCE___MINING` | 矿池 | `https://api.binance.com` | — |
| `BINANCE___VIP_LOAN` | VIP借贷 | `https://api.binance.com` | — |
| `BINANCE___WALLET` | 钱包 | `https://api.binance.com` | — |
| `BINANCE___SUB_ACCOUNT` | 子账户 | `https://api.binance.com` | — |
| `BINANCE___PORTFOLIO` | 组合保证金 | `https://api.binance.com` | — |

### 快速开始

```bash
pip install bt_api_binance
```

独立客户端使用：

```python
from bt_api_binance import BinanceApi

client = BinanceApi(
    api_key="your_api_key",
    secret_key="your_secret",
    asset_type="SPOT",
    testnet=True,
)

client.connect()
client.subscribe_symbols(["BTCUSDT", "ETHUSDT"])

while True:
    channel, data = client.poll_output()
    if channel == "market":
        print(f"{data['symbol']}: price={data['price']}")
```

bt_api 插件集成：

```python
from bt_api_py import BtApi

api = BtApi(exchange_kwargs={
    "BINANCE___SPOT": {
        "api_key": "your_key",
        "secret": "your_secret",
        "testnet": True,
    }
})

ticker = api.get_tick("BINANCE___SPOT", "BTCUSDT")
```

### API 参考

- [客户端](api/client.md) — BinanceDirectClient 独立入口
- [Feeds](api/feeds.md) — REST 请求 feeds 和 WebSocket 市场/账户 feeds
- [交易所数据](api/exchange_data.md) — 交易所配置类
- [容器](api/containers.md) — 规范化数据容器
- [WebSocket](api/websocket.md) — WebSocket 适配器
- [网关](api/gateway.md) — 网关适配器

### 在线文档

| 资源 | 链接 |
|----------|------|
| 英文文档 | https://bt-api-binance.readthedocs.io/ |
| 中文文档 | https://bt-api-binance.readthedocs.io/zh/latest/ |
| GitHub 仓库 | https://github.com/cloudQuant/bt_api_binance |
| 问题反馈 | https://github.com/cloudQuant/bt_api_binance/issues |
| PyPI 包 | https://pypi.org/project/bt_api_binance/ |
| bt_api_base 文档 | https://bt-api-base.readthedocs.io/ |
| 主项目 | https://github.com/cloudQuant/bt_api_py |
