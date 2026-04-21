# bt_api_binance

[![PyPI Version](https://img.shields.io/pypi/v/bt_api_binance.svg)](https://pypi.org/project/bt_api_binance/)
[![Python Versions](https://img.shields.io/pypi/pyversions/bt_api_binance.svg)](https://pypi.org/project/bt_api_binance/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/cloudQuant/bt_api_binance/actions/workflows/ci.yml/badge.svg)](https://github.com/cloudQuant/bt_api_binance/actions)
[![Docs](https://readthedocs.org/projects/bt-api-binance/badge/?version=latest)](https://bt-api-binance.readthedocs.io/)

---

<!-- English -->
# bt_api_binance

> **Binance exchange plugin for bt_api** — Unified REST and WebSocket API for **Spot**, **Futures**, **Margin**, **Options**, and more.

`bt_api_binance` is a runtime plugin for [bt_api](https://github.com/cloudQuant/bt_api_py) that connects to **Binance** exchange. It depends on [bt_api_base](https://github.com/cloudQuant/bt_api_base) for core infrastructure. It also ships `BinanceDirectClient` for **standalone use** without the full bt_api framework.

| Resource | Link |
|----------|------|
| English Docs | https://bt-api-binance.readthedocs.io/ |
| Chinese Docs | https://bt-api-binance.readthedocs.io/zh/latest/ |
| GitHub | https://github.com/cloudQuant/bt_api_binance |
| PyPI | https://pypi.org/project/bt_api_binance/ |
| Issues | https://github.com/cloudQuant/bt_api_binance/issues |
| bt_api_base | https://bt-api-base.readthedocs.io/ |
| Main Project | https://github.com/cloudQuant/bt_api_py |

---

## Features

### 13 Asset Types

| Asset Type | Code | REST | WebSocket | Description |
|---|---|---|---|---|
| Spot | `BINANCE___SPOT` | ✅ | ✅ | Spot trading |
| USDT-M Futures | `BINANCE___SWAP` | ✅ | ✅ | USDT-margined perpetual futures |
| COIN-M Futures | `BINANCE___COIN_M` | ✅ | ✅ | Coin-margined perpetual futures |
| Cross/Isolated Margin | `BINANCE___MARGIN` | ✅ | ✅ | Margin trading |
| Options | `BINANCE___OPTION` | ✅ | ✅ | Vanilla options |
| TWAP / VWAP | `BINANCE___ALGO` | ✅ | — | Algo orders |
| Grid Trading | `BINANCE___GRID` | ✅ | — | Grid trading strategies |
| Staking / LDEX | `BINANCE___STAKING` | ✅ | — | Staking and leveraged staking |
| Mining | `BINANCE___MINING` | ✅ | — | Mining pool API |
| VIP Loans | `BINANCE___VIP_LOAN` | ✅ | — | VIP lending |
| Wallet | `BINANCE___WALLET` | ✅ | — | Asset management |
| Sub-Accounts | `BINANCE___SUB_ACCOUNT` | ✅ | — | Sub-account management |
| Portfolio Margin | `BINANCE___PORTFOLIO` | ✅ | — | Portfolio margin |

### Dual API Modes

- **REST API** — Synchronous polling for order management, balance queries, historical data
- **WebSocket API** — Real-time streaming for ticker, order book, k-lines, trades, account updates

### Plugin Architecture

Auto-registers at import time via `ExchangeRegistry`. Works seamlessly with `BtApi`:

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
balance = api.get_balance("BINANCE___SPOT")
order = api.make_order(exchange_name="BINANCE___SPOT", symbol="BTCUSDT", volume=0.001, price=50000, order_type="limit")
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
    channel, data = client.poll_output(timeout=1.0)
    if channel == "market":
        print(f"{data['symbol']}: {data['price']}")
```

### Unified Data Containers

All exchange responses normalized to bt_api_base container types:

- `TickContainer` — 24hr rolling ticker
- `OrderBookContainer` — Order book depth
- `BarContainer` — K-line/candlestick
- `TradeContainer` — Individual trades
- `OrderContainer` — Order status and fills
- `PositionContainer` — Futures/margin positions
- `AccountBalanceContainer` — Asset balances
- `FundingRateContainer` / `MarkPriceContainer` — Perpetual futures
- `IncomeContainer` — PnL, funding fees, commissions

---

## Installation

### From PyPI (Recommended)

```bash
pip install bt_api_binance
```

### From Source

```bash
git clone https://github.com/cloudQuant/bt_api_binance
cd bt_api_binance
pip install -e .
```

### Requirements

- Python `3.9` – `3.14`
- `bt_api_base >= 0.15`
- `httpx` for HTTP client
- `websockets` for WebSocket client

---

## Quick Start

### 1. Install

```bash
pip install bt_api_binance
```

### 2. Get ticker (public — no API key needed)

```python
from bt_api_binance import BinanceApi

client = BinanceApi(asset_type="SPOT")
client.connect()
btc = client.get_ticker("BTCUSDT")
print(f"BTCUSDT price: {btc['price']}")
```

### 3. Place an order (requires API key)

```python
from bt_api_binance import BinanceApi

client = BinanceApi(
    api_key="your_api_key",
    secret_key="your_secret",
    asset_type="SWAP",  # USDT-M futures
    testnet=True,
)
client.connect()
client.set_leverage("BTCUSDT", leverage=10)

order = client.make_order(
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    price=67000,
    qty=0.001,
)
print(f"Order placed: {order['order_id']}")
```

### 4. Real-time WebSocket

```python
from bt_api_binance import BinanceApi

client = BinanceApi(asset_type="SPOT", testnet=True)
client.connect()
client.subscribe_symbols(["BTCUSDT", "ETHUSDT"], topics=["ticker", "kline_1m"])

while True:
    channel, data = client.poll_output(timeout=1.0)
    if channel == "market":
        if "interval" in data:
            print(f"Kline {data['interval']}: close={data['close']}")
        else:
            print(f"Ticker: {data['price']}")
```

### 5. bt_api Plugin Integration

```python
from bt_api_py import BtApi

api = BtApi(exchange_kwargs={
    "BINANCE___SPOT": {"api_key": "key", "secret": "secret", "testnet": True}
})

# REST calls
ticker = api.get_tick("BINANCE___SPOT", "BTCUSDT")
balance = api.get_balance("BINANCE___SPOT")

# WebSocket subscription
api.subscribe("BINANCE___SPOT___BTCUSDT", [
    {"topic": "ticker", "symbol": "BTCUSDT"},
    {"topic": "depth", "symbol": "BTCUSDT", "depth": 20},
])
queue = api.get_data_queue("BINANCE___SPOT")
msg = queue.get(timeout=10)
```

---

## Architecture

```
bt_api_binance/
├── client.py                      # BinanceDirectClient — standalone REST + WebSocket client
├── plugin.py                     # register_plugin() — bt_api plugin entry point
├── registry_registration.py        # register_binance() — feeds / exchange_data / balance_handler registration
├── exchange_data/
│   └── binance_exchange_data.py   # BinanceExchangeData (base) + 13 asset-type subclasses
├── feeds/
│   ├── spot.py                   # BinanceRequestDataSpot, BinanceMarketWssDataSpot, BinanceAccountWssDataSpot
│   ├── swap.py                   # USDT-M futures feeds
│   ├── coin_m.py                 # COIN-M futures feeds
│   ├── margin.py                 # Margin feeds
│   ├── option.py                 # Options feeds
│   ├── algo.py                  # Algo order feeds (REST-only)
│   ├── grid.py                  # Grid trading feeds (REST-only)
│   ├── staking.py              # Staking feeds (REST-only)
│   ├── mining.py               # Mining feeds (REST-only)
│   ├── vip_loan.py            # VIP loan feeds (REST-only)
│   ├── wallet.py               # Wallet feeds (REST-only)
│   ├── sub_account.py         # Sub-account feeds (REST-only)
│   ├── portfolio.py            # Portfolio margin feeds (REST-only)
│   ├── request_base.py         # RequestData base class
│   ├── market_wss_base.py     # MarketWssData base class
│   └── account_wss_base.py    # AccountWssData base class
├── containers/                   # 12 normalized data container types
├── gateway/
│   └── adapter.py              # BinanceGatewayAdapter(PluginGatewayAdapter)
├── errors/
│   └── binance_translator.py  # BinanceErrorTranslator → bt_api_base.ApiError
└── configs/
    └── binance.yaml           # Full YAML config (REST/WSS paths, rate limits, for all 13 asset types)
```

---

## Supported Operations

| Category | Operation | Notes |
|---|---|---|
| **Market Data** | `get_ticker` | 24hr rolling ticker |
| | `get_orderbook` | Depth: 5/10/20/50/100/500/1000/5000 |
| | `get_bars` | Intervals: 1m–1M |
| | `get_trades` | Recent trade history |
| | `get_funding_rate` | Futures only |
| | `get_mark_price` | Futures only |
| **Account** | `get_balance` | All asset balances |
| | `get_account` | Full account info |
| | `get_position` | Futures/margin positions |
| | `get_open_orders` | All open orders |
| | `get_order` | Single order by ID |
| **Trading** | `make_order` | LIMIT/MARKET/STOP/TAKE_PROFIT and variants |
| | `cancel_order` | Cancel single order |
| | `cancel_orders` | Cancel all open orders |
| | `set_leverage` | Futures only |
| | `set_margin_type` | Cross/isolated |
| | `add_margin` | Add position margin |
| **WebSocket** | `subscribe_symbols` | Market data streams |
| | `poll_output` | Blocking/non-blocking output poll |
| | `get_data_queue` | Raw `Queue` access |

---

## Supported Binance Symbols

All Binance trading pairs are supported, including:

- **Spot**: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `XRPUSDT` ...
- **USDT-M Futures**: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT` ... (200+ pairs)
- **COIN-M Futures**: `BTCUSD`, `ETHUSD`, `SOLUSD` ... (100+ pairs)
- **Options**: All listed option contracts
- **Margin**: All cross and isolated margin pairs

---

## Error Handling

All Binance API errors are translated to bt_api_base `ApiError` subclasses:

| Binance Code | Error | Description |
|---|---|---|
| `-1000` | `API_ERROR` | Unknown error |
| `-1003` | `RATE_LIMIT` | Rate limit exceeded |
| `-1013` | `INVALID_PARAMETER` | Invalid quantity |
| `-1021` | `TIMESTAMP_INVALID` | Invalid timestamp |
| `-1022` | `SIGNATURE_INVALID` | Invalid signature |
| `-1102` | `API_KEY_MISSING` | API key not provided |
| `-2013` | `ORDER_NOT_FOUND` | Order does not exist |
| `-2014` | `API_KEY_INVALID` | Invalid API key |
| `-2019` | `MARGIN_INSUFFICIENT` | Insufficient margin |
| `-2020` | `BALANCE_INSUFFICIENT` | Insufficient balance |
| `-2026` | `LEVERAGE_INVALID` | Invalid leverage |
| `-9000` | `RATE_LIMIT` | Exchange rate limit |

---

## Rate Limits

| Asset Type | Requests/sec | Orders/sec |
|---|---|---|
| SPOT | 1200 | 100 |
| SWAP | 2400 | 150 |
| COIN_M | 2400 | 150 |
| MARGIN | 1200 | 100 |
| OPTION | 1200 | 50 |
| ALGO | 1200 | 100 |
| GRID | 200 | 20 |
| Others | 200 | 20 |

---

## Documentation

| Doc | Link |
|-----|------|
| **English** | https://bt-api-binance.readthedocs.io/ |
| **中文** | https://bt-api-binance.readthedocs.io/zh/latest/ |
| API Reference | https://bt-api-binance.readthedocs.io/api/client/ |
| bt_api_base | https://bt-api-base.readthedocs.io/ |
| Main Project | https://cloudquant.github.io/bt_api_py/ |

---

## License

MIT — see [LICENSE](LICENSE).

---

## Support

- [GitHub Issues](https://github.com/cloudQuant/bt_api_binance/issues) — bug reports, feature requests
- Email: yunjinqi@gmail.com

---

---

## 中文

> **bt_api 的 Binance 交易所插件** — 为**现货**、**合约**、**杠杆**、**期权**等提供统一的 REST 和 WebSocket API。

`bt_api_binance` 是 [bt_api](https://github.com/cloudQuant/bt_api_py) 的运行时插件，连接 **Binance** 交易所。依赖 [bt_api_base](https://github.com/cloudQuant/bt_api_base) 提供核心基础设施。同时提供 `BinanceDirectClient`，可**独立使用**无需完整 bt_api 框架。

| 资源 | 链接 |
|------|------|
| 英文文档 | https://bt-api-binance.readthedocs.io/ |
| 中文文档 | https://bt-api-binance.readthedocs.io/zh/latest/ |
| GitHub | https://github.com/cloudQuant/bt_api_binance |
| PyPI | https://pypi.org/project/bt_api_binance/ |
| 问题反馈 | https://github.com/cloudQuant/bt_api_binance/issues |
| bt_api_base | https://bt-api-base.readthedocs.io/ |
| 主项目 | https://github.com/cloudQuant/bt_api_py |

---

## 功能特点

### 13 种资产类型

| 资产类型 | 代码 | REST | WebSocket | 说明 |
|---|---|---|---|---|
| 现货 | `BINANCE___SPOT` | ✅ | ✅ | 现货交易 |
| U本位永续 | `BINANCE___SWAP` | ✅ | ✅ | USDT 保证金永续合约 |
| 币本位永续 | `BINANCE___COIN_M` | ✅ | ✅ | 币种保证金永续合约 |
| 全仓/逐仓杠杆 | `BINANCE___MARGIN` | ✅ | ✅ | 杠杆交易 |
| 期权 | `BINANCE___OPTION` | ✅ | ✅ | 欧式期权 |
| TWAP / VWAP | `BINANCE___ALGO` | ✅ | — | 算法单 |
| 网格交易 | `BINANCE___GRID` | ✅ | — | 网格策略 |
| 质押理财 | `BINANCE___STAKING` | ✅ | — | 活期/定期质押 |
| 矿池 | `BINANCE___MINING` | ✅ | — | 挖矿API |
| VIP借贷 | `BINANCE___VIP_LOAN` | ✅ | — | VIP借币 |
| 钱包 | `BINANCE___WALLET` | ✅ | — | 资产管理 |
| 子账户 | `BINANCE___SUB_ACCOUNT` | ✅ | — | 子账户管理 |
| 组合保证金 | `BINANCE___PORTFOLIO` | ✅ | — | 组合保证金账户 |

### 双 API 模式

- **REST API** — 同步轮询：订单管理、余额查询、历史数据
- **WebSocket API** — 实时流：行情、订单簿、K线、交易、账户更新

### 插件架构

通过 `ExchangeRegistry` 在导入时自动注册，与 `BtApi` 无缝协作：

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
balance = api.get_balance("BINANCE___SPOT")
order = api.make_order(exchange_name="BINANCE___SPOT", symbol="BTCUSDT", volume=0.001, price=50000, order_type="limit")
```

### 独立直接客户端

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
    channel, data = client.poll_output(timeout=1.0)
    if channel == "market":
        print(f"{data['symbol']}: {data['price']}")
```

### 统一数据容器

所有交易所响应规范化为 bt_api_base 容器类型：

- `TickContainer` — 24小时滚动行情
- `OrderBookContainer` — 订单簿深度
- `BarContainer` — K线/蜡烛图
- `TradeContainer` — 逐笔成交
- `OrderContainer` — 订单状态和成交
- `PositionContainer` — 合约/杠杆持仓
- `AccountBalanceContainer` — 资产余额
- `FundingRateContainer` / `MarkPriceContainer` — 永续合约
- `IncomeContainer` — 收益、资金费、佣金

---

## 安装

### 从 PyPI 安装（推荐）

```bash
pip install bt_api_binance
```

### 从源码安装

```bash
git clone https://github.com/cloudQuant/bt_api_binance
cd bt_api_binance
pip install -e .
```

### 系统要求

- Python `3.9` – `3.14`
- `bt_api_base >= 0.15`
- `httpx` HTTP 客户端
- `websockets` WebSocket 客户端

---

## 快速开始

### 1. 安装

```bash
pip install bt_api_binance
```

### 2. 获取行情（公开接口，无需 API key）

```python
from bt_api_binance import BinanceApi

client = BinanceApi(asset_type="SPOT")
client.connect()
btc = client.get_ticker("BTCUSDT")
print(f"BTCUSDT 价格: {btc['price']}")
```

### 3. 下单交易（需要 API key）

```python
from bt_api_binance import BinanceApi

client = BinanceApi(
    api_key="your_api_key",
    secret_key="your_secret",
    asset_type="SWAP",  # U本位永续
    testnet=True,
)
client.connect()
client.set_leverage("BTCUSDT", leverage=10)

order = client.make_order(
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    price=67000,
    qty=0.001,
)
print(f"订单已下单: {order['order_id']}")
```

### 4. 实时 WebSocket

```python
from bt_api_binance import BinanceApi

client = BinanceApi(asset_type="SPOT", testnet=True)
client.connect()
client.subscribe_symbols(["BTCUSDT", "ETHUSDT"], topics=["ticker", "kline_1m"])

while True:
    channel, data = client.poll_output(timeout=1.0)
    if channel == "market":
        if "interval" in data:
            print(f"K线 {data['interval']}: close={data['close']}")
        else:
            print(f"行情: {data['price']}")
```

### 5. bt_api 插件集成

```python
from bt_api_py import BtApi

api = BtApi(exchange_kwargs={
    "BINANCE___SPOT": {"api_key": "key", "secret": "secret", "testnet": True}
})

# REST 调用
ticker = api.get_tick("BINANCE___SPOT", "BTCUSDT")
balance = api.get_balance("BINANCE___SPOT")

# WebSocket 订阅
api.subscribe("BINANCE___SPOT___BTCUSDT", [
    {"topic": "ticker", "symbol": "BTCUSDT"},
    {"topic": "depth", "symbol": "BTCUSDT", "depth": 20},
])
queue = api.get_data_queue("BINANCE___SPOT")
msg = queue.get(timeout=10)
```

---

## 架构

```
bt_api_binance/
├── client.py                      # BinanceDirectClient — 独立 REST + WebSocket 客户端
├── plugin.py                     # register_plugin() — bt_api 插件入口
├── registry_registration.py      # register_binance() — feeds / exchange_data / balance_handler 注册
├── exchange_data/
│   └── binance_exchange_data.py  # BinanceExchangeData（基类）+ 13 个资产类型子类
├── feeds/
│   ├── spot.py                   # BinanceRequestDataSpot, BinanceMarketWssDataSpot, BinanceAccountWssDataSpot
│   ├── swap.py                   # U本位合约 feeds
│   ├── coin_m.py                 # 币本位合约 feeds
│   ├── margin.py                 # 杠杆 feeds
│   ├── option.py                 # 期权 feeds
│   ├── algo.py                  # 算法单 feeds（仅REST）
│   ├── grid.py                  # 网格交易 feeds（仅REST）
│   ├── staking.py               # 质押 feeds（仅REST）
│   ├── mining.py               # 矿池 feeds（仅REST）
│   ├── vip_loan.py            # VIP借贷 feeds（仅REST）
│   ├── wallet.py               # 钱包 feeds（仅REST）
│   ├── sub_account.py         # 子账户 feeds（仅REST）
│   ├── portfolio.py           # 组合保证金 feeds（仅REST）
│   ├── request_base.py        # RequestData 基类
│   ├── market_wss_base.py    # MarketWssData 基类
│   └── account_wss_base.py   # AccountWssData 基类
├── containers/                   # 12 种规范化数据容器类型
├── gateway/
│   └── adapter.py             # BinanceGatewayAdapter(PluginGatewayAdapter)
├── errors/
│   └── binance_translator.py # BinanceErrorTranslator → bt_api_base.ApiError
└── configs/
    └── binance.yaml          # 完整 YAML 配置（13 种资产类型的 REST/WSS 路径、限流）
```

---

## 支持的操作

| 类别 | 操作 | 说明 |
|---|---|---|
| **行情数据** | `get_ticker` | 24小时滚动行情 |
| | `get_orderbook` | 深度: 5/10/20/50/100/500/1000/5000 |
| | `get_bars` | 周期: 1m–1M |
| | `get_trades` | 近期成交历史 |
| | `get_funding_rate` | 仅合约 |
| | `get_mark_price` | 仅合约 |
| **账户** | `get_balance` | 所有资产余额 |
| | `get_account` | 完整账户信息 |
| | `get_position` | 合约/杠杆持仓 |
| | `get_open_orders` | 所有挂单 |
| | `get_order` | 按ID查询单笔订单 |
| **交易** | `make_order` | 限价/市价/止损/止盈及其市价变体 |
| | `cancel_order` | 撤销单笔订单 |
| | `cancel_orders` | 撤销所有挂单 |
| | `set_leverage` | 仅合约 |
| | `set_margin_type` | 全仓/逐仓 |
| | `add_margin` | 增加持仓保证金 |
| **WebSocket** | `subscribe_symbols` | 行情数据流订阅 |
| | `poll_output` | 阻塞/非阻塞输出轮询 |
| | `get_data_queue` | 原始 `Queue` 访问 |

---

## 支持的 Binance 交易对

全部 Binance 交易对均支持，包括：

- **现货**: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `XRPUSDT` ...
- **U本位合约**: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT` ... (200+ 对)
- **币本位合约**: `BTCUSD`, `ETHUSD`, `SOLUSD` ... (100+ 对)
- **期权**: 所有上市期权合约
- **杠杆**: 所有全仓和逐仓交易对

---

## 错误处理

所有 Binance API 错误均翻译为 bt_api_base `ApiError` 子类：

| Binance 错误码 | 错误类型 | 说明 |
|---|---|---|
| `-1000` | `API_ERROR` | 未知错误 |
| `-1003` | `RATE_LIMIT` | 请求过于频繁 |
| `-1013` | `INVALID_PARAMETER` | 无效数量 |
| `-1021` | `TIMESTAMP_INVALID` | 无效时间戳 |
| `-1022` | `SIGNATURE_INVALID` | 无效签名 |
| `-1102` | `API_KEY_MISSING` | 未提供 API key |
| `-2013` | `ORDER_NOT_FOUND` | 订单不存在 |
| `-2014` | `API_KEY_INVALID` | API key 无效 |
| `-2019` | `MARGIN_INSUFFICIENT` | 保证金不足 |
| `-2020` | `BALANCE_INSUFFICIENT` | 余额不足 |
| `-2026` | `LEVERAGE_INVALID` | 无效杠杆 |
| `-9000` | `RATE_LIMIT` | 交易所限流 |

---

## 限流配置

| 资产类型 | 请求/秒 | 订单/秒 |
|---|---|---|
| 现货 | 1200 | 100 |
| U本位永续 | 2400 | 150 |
| 币本位永续 | 2400 | 150 |
| 杠杆 | 1200 | 100 |
| 期权 | 1200 | 50 |
| 算法单 | 1200 | 100 |
| 网格交易 | 200 | 20 |
| 其他 | 200 | 20 |

---

## 文档

| 文档 | 链接 |
|-----|------|
| **英文文档** | https://bt-api-binance.readthedocs.io/ |
| **中文文档** | https://bt-api-binance.readthedocs.io/zh/latest/ |
| API 参考 | https://bt-api-binance.readthedocs.io/api/client/ |
| bt_api_base | https://bt-api-base.readthedocs.io/ |
| 主项目 | https://cloudquant.github.io/bt_api_py/ |

---

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

---

## 技术支持

- [GitHub Issues](https://github.com/cloudQuant/bt_api_binance/issues) — bug 报告、功能请求
- 邮箱: yunjinqi@gmail.com
