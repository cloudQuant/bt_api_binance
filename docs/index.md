# Binance Plugin for bt_api

## English

Welcome to the **Binance** plugin documentation for [bt_api](https://github.com/cloudQuant/bt_api_py).

This plugin provides a unified interface for interacting with **Binance** exchange, supporting Spot, Futures, Margin, and other trading functionalities.

### Features

- **Spot Trading**: Buy and sell cryptocurrencies with order book depth
- **Futures Trading**: USDT-M and COIN-M futures contracts
- **Margin Trading**: Cross-margin and isolated-margin support
- **WebSocket Feeds**: Real-time ticker, orderbook, and trade data
- **REST API**: Full trading functionality including order management
- **Account Management**: Balance, position, and order tracking

### Installation

```bash
pip install bt_api_binance
```

### Quick Start

```python
from bt_api_binance import BinanceApi

# Initialize with API credentials
feed = BinanceApi(
    api_key="your_api_key",
    secret="your_secret",
    testnet=True  # Use testnet for testing
)

# Get ticker data
ticker = feed.get_ticker("BTCUSDT")
print(f"BTC/USDT: {ticker.last_price}")

# Get order book
orderbook = feed.get_orderbook("BTCUSDT", depth=20)
print(f"Bids: {orderbook.bids[:5]}")

# Place an order
order = feed.make_order(
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    price=50000.0,
    quantity=0.001
)
print(f"Order ID: {order.order_id}")
```

### Architecture

```
bt_api_binance/
├── src/bt_api_binance/
│   ├── containers/      # Data models (Ticker, OrderBook, Order, etc.)
│   ├── feeds/          # REST and WebSocket API implementations
│   ├── gateway/        # Gateway adapter for bt_api integration
│   ├── configs/        # Exchange-specific configurations
│   ├── errors/         # Error code translations
│   └── plugin.py       # Plugin registration entry point
├── tests/              # Comprehensive test suite
└── docs/              # Documentation
```

### Configuration

```python
exchange_kwargs = {
    "BINANCE___SPOT": {
        "api_key": "your_api_key",
        "secret": "your_secret",
        "testnet": True,  # or False for production
        "recv_window": 5000,  # Request window in milliseconds
    }
}
```

### Supported Operations

| Operation | Endpoint | Status |
|-----------|----------|--------|
| Get Ticker | `/api/v3/ticker/24hr` | ✅ |
| Get OrderBook | `/api/v3/depth` | ✅ |
| Get Klines | `/api/v3/klines` | ✅ |
| Get Balance | `/api/v3/account` | ✅ |
| Place Order | `/api/v3/order` | ✅ |
| Cancel Order | `/api/v3/order` | ✅ |
| Get Open Orders | `/api/v3/openOrders` | ✅ |
| WebSocket Ticker | `!ticker@arr` | ✅ |
| WebSocket Depth | `<symbol>@depth` | ✅ |

### Online Resources

| Resource | Link |
|----------|------|
| English Docs | https://bt-api-binance.readthedocs.io/ |
| Chinese Docs | https://bt-api-binance.readthedocs.io/zh/latest/ |
| GitHub Repository | https://github.com/cloudQuant/bt_api_binance |
| Issue Tracker | https://github.com/cloudQuant/bt_api_binance/issues |
| PyPI Package | https://pypi.org/project/bt_api_binance/ |

---

## 中文

欢迎使用 **bt_api** 的 **Binance（币安）** 插件文档。

本插件提供与 **币安** 交易所交互的统一接口，支持现货、合约、杠杆等多种交易功能。

### 功能特点

- **现货交易**：买卖加密货币，查看订单簿深度
- **合约交易**：U本位和币本位永续合约
- **杠杆交易**：全仓和逐仓杠杆支持
- **WebSocket 行情**：实时行情、订单簿和成交数据推送
- **REST API**：完整的交易功能，包括订单管理
- **账户管理**：余额、持仓和订单跟踪

### 安装

```bash
pip install bt_api_binance
```

### 快速开始

```python
from bt_api_binance import BinanceApi

# 使用 API 凭证初始化
feed = BinanceApi(
    api_key="your_api_key",
    secret="your_secret",
    testnet=True  # 测试时使用测试网
)

# 获取行情数据
ticker = feed.get_ticker("BTCUSDT")
print(f"BTC/USDT: {ticker.last_price}")

# 获取订单簿
orderbook = feed.get_orderbook("BTCUSDT", depth=20)
print(f"买单: {orderbook.bids[:5]}")

# 下单
order = feed.make_order(
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    price=50000.0,
    quantity=0.001
)
print(f"订单ID: {order.order_id}")
```

### 架构

```
bt_api_binance/
├── src/bt_api_binance/
│   ├── containers/      # 数据模型（行情、订单簿、订单等）
│   ├── feeds/          # REST 和 WebSocket API 实现
│   ├── gateway/        # bt_api 集成的网关适配器
│   ├── configs/        # 交易所特定配置
│   ├── errors/         # 错误码翻译
│   └── plugin.py       # 插件注册入口
├── tests/              # 综合测试套件
└── docs/               # 文档
```

### 配置

```python
exchange_kwargs = {
    "BINANCE___SPOT": {
        "api_key": "your_api_key",
        "secret": "your_secret",
        "testnet": True,  # 或 False 用于生产
        "recv_window": 5000,  # 请求窗口时间（毫秒）
    }
}
```

### 支持的操作

| 操作 | 端点 | 状态 |
|------|------|------|
| 获取行情 | `/api/v3/ticker/24hr` | ✅ |
| 获取订单簿 | `/api/v3/depth` | ✅ |
| 获取K线 | `/api/v3/klines` | ✅ |
| 获取余额 | `/api/v3/account` | ✅ |
| 下单 | `/api/v3/order` | ✅ |
| 撤单 | `/api/v3/order` | ✅ |
| 获取未完成订单 | `/api/v3/openOrders` | ✅ |
| WebSocket 行情 | `!ticker@arr` | ✅ |
| WebSocket 订单簿 | `<symbol>@depth` | ✅ |

### 在线资源

| 资源 | 链接 |
|------|------|
| 英文文档 | https://bt-api-binance.readthedocs.io/ |
| 中文文档 | https://bt-api-binance.readthedocs.io/zh/latest/ |
| GitHub 仓库 | https://github.com/cloudQuant/bt_api_binance |
| 问题反馈 | https://github.com/cloudQuant/bt_api_binance/issues |
| PyPI 包 | https://pypi.org/project/bt_api_binance/ |

---

## API Reference

For detailed API documentation, please refer to the source code in `src/bt_api_binance/` or visit the online documentation.

## License

MIT License - see [LICENSE](LICENSE) for details.
