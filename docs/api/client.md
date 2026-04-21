---
title: Client | bt_api_binance
---

# Client | 客户端接口

`BinanceDirectClient` provides a standalone REST + WebSocket client for Binance, independent of the full bt_api plugin framework.

---

## BinanceApi (Alias)

```python
from bt_api_binance import BinanceApi
```

`BinanceApi` is an alias for `BinanceDirectClient` (exported in `__init__.py` for convenience).

---

## BinanceDirectClient

**File**: `src/bt_api_binance/client.py`

```python
class BinanceDirectClient:
    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        asset_type: str = "SPOT",
        testnet: bool = False,
        auto_connect: bool = True,
    ):
        """
        Initialize Binance direct client.

        Args:
            api_key: Binance API key. If None, only public endpoints work.
            secret_key: Binance API secret. If None, only public endpoints work.
            asset_type: Asset type string. One of:
                "SPOT", "SWAP", "COIN_M", "MARGIN", "OPTION",
                "ALGO", "GRID", "STAKING", "MINING", "VIP_LOAN",
                "WALLET", "SUB_ACCOUNT", "PORTFOLIO"
            testnet: Use Binance testnet endpoints.
            auto_connect: Automatically connect on init.
        """
```

---

## Connection Management

### connect()

```python
def connect(self) -> bool
```

Establish HTTP session and WebSocket connections.

**Returns**: `True` if successful.

---

### disconnect()

```python
def disconnect(self) -> None
```

Close all connections gracefully.

---

### is_connected()

```python
def is_connected(self) -> bool
```

Check if client is connected.

---

## Market Data (Public — No Auth Required)

### get_ticker()

```python
def get_ticker(self, symbol: str) -> dict | None
```

Get 24-hour ticker for a symbol.

```python
result = client.get_ticker("BTCUSDT")
# {'symbol': 'BTCUSDT', 'price': 67432.50, 'bid_price': 67432.49,
#  'ask_price': 67432.51, 'high': 68000.00, 'low': 66000.00,
#  'volume': 12345.67, ...}
```

---

### get_orderbook()

```python
def get_orderbook(self, symbol: str, depth: int = 20) -> dict | None
```

Get order book depth.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `symbol` | `str` | Required | Trading symbol |
| `depth` | `int` | `20` | Depth levels: `5`, `10`, `20`, `50`, `100`, `500`, `1000`, `5000` |

---

### get_bars()

```python
def get_bars(self, symbol: str, interval: str = "1m", limit: int = 100) -> list | None
```

Get K-line/candlestick data.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `symbol` | `str` | Required | Trading symbol |
| `interval` | `str` | `"1m"` | K-line interval: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w` |
| `limit` | `int` | `100` | Max `1000` |

---

### get_trades()

```python
def get_trades(self, symbol: str, limit: int = 100) -> list | None
```

Get recent trades.

---

### get_funding_rate()

```python
def get_funding_rate(self, symbol: str) -> dict | None
```

Get current funding rate (futures only). Returns `None` for spot.

---

## Authenticated Endpoints (Auth Required)

### get_balance()

```python
def get_balance(self) -> list[dict] | None
```

Get account balances. Requires `api_key` and `secret_key`.

---

### get_order()

```python
def get_order(self, symbol: str, order_id: str | int) -> dict | None
```

Query a specific order.

---

### get_open_orders()

```python
def get_open_orders(self, symbol: str | None = None) -> list | None
```

Get all open orders. If `symbol` is `None`, returns all open orders.

---

### make_order()

```python
def make_order(
    self,
    symbol: str,
    side: str,
    order_type: str,
    price: float | None = None,
    qty: float | None = None,
    **kwargs
) -> dict | None
```

Place a new order.

| Param | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Trading symbol (e.g. `"BTCUSDT"`) |
| `side` | `str` | `"BUY"` or `"SELL"` |
| `order_type` | `str` | `"LIMIT"`, `"MARKET"`, `"STOP"`, `"STOP_MARKET"`, `"TAKE_PROFIT"`, `"TAKE_PROFIT_MARKET"` |
| `price` | `float` | Order price (required for LIMIT and conditional orders) |
| `qty` | `float` | Order quantity |
| `stop_price` | `float` | Stop price (for STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET) |
| `position_side` | `str` | `"LONG"`, `"SHORT"`, `"BOTH"` (futures only) |
| `leverage` | `int` | Leverage (futures only) |
| `margin_type` | `str` | `"ISOLATED"` or `"CROSSED"` (futures only) |
| `time_in_force` | `str` | `"GTC"`, `"IOC"`, `"FOK"` |

---

### cancel_order()

```python
def cancel_order(self, symbol: str, order_id: str | int, client_order_id: str | None = None) -> dict | None
```

Cancel a specific order.

---

### cancel_orders()

```python
def cancel_orders(self, symbol: str | None = None) -> bool
```

Cancel all open orders for a symbol (or all symbols if `symbol` is `None`).

---

### get_position()

```python
def get_position(self, symbol: str | None = None) -> list[dict] | None
```

Get position details (futures only). Returns `None` for spot.

---

### set_leverage()

```python
def set_leverage(self, symbol: str, leverage: int) -> dict | None
```

Set leverage for a futures symbol.

---

### get_account()

```python
def get_account(self) -> dict | None
```

Get full account information (spot and margin).

---

## WebSocket Subscriptions

### subscribe_symbols()

```python
def subscribe_symbols(
    self,
    symbols: list[str],
    topics: list[str] | None = None
) -> bool
```

Subscribe to market data WebSocket streams.

| Param | Type | Description |
|-------|------|-------------|
| `symbols` | `list[str]` | List of symbols (e.g. `["BTCUSDT", "ETHUSDT"]`) |
| `topics` | `list[str]` | Topics to subscribe. Default: `["ticker"]` |

Available topics: `"ticker"`, `"depth"`, `"kline"`, `"trade"`, `"markPrice"`, `"fundingRate"`

---

### unsubscribe_symbols()

```python
def unsubscribe_symbols(
    self,
    symbols: list[str],
    topics: list[str] | None = None
) -> bool
```

Unsubscribe from WebSocket streams.

---

### poll_output()

```python
def poll_output(self, timeout: float = 0.1) -> Tuple[str, dict] | Tuple[None, None]
```

Poll WebSocket output queue. **Blocking if timeout > 0.**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `timeout` | `float` | `0.1` | Timeout in seconds. `0` = non-blocking |

**Returns**: `(channel, data)` tuple. `channel` values:
- `"market"` — Market data (ticker, orderbook, kline, trade)
- `"account"` — Account data (balance, order update, position update)

```python
while True:
    channel, data = client.poll_output(timeout=1.0)
    if channel == "market":
        print(f"[{data['symbol']}] {data.get('price', data.get('close'))}")
    elif channel == "account":
        print(f"[ACCOUNT] {data}")
```

---

### get_data_queue()

```python
def get_data_queue(self) -> Queue
```

Get the raw `Queue` object for WebSocket output (alternative to `poll_output()`).

---

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `asset_type` | `str` | Current asset type (`"SPOT"`, `"SWOT"`, etc.) |
| `exchange_data` | `BinanceExchangeData` | Exchange data instance |
| `is_testnet` | `bool` | Whether testnet mode is active |

---

## Usage Examples

### Public Market Data Only

```python
from bt_api_binance import BinanceApi

client = BinanceApi(asset_type="SPOT")
client.connect()

# Get ticker
btc = client.get_ticker("BTCUSDT")
print(f"BTC price: {btc['price']}")

# Subscribe and poll
client.subscribe_symbols(["BTCUSDT", "ETHUSDT"])
while True:
    channel, data = client.poll_output(timeout=1.0)
    if channel:
        print(f"{data['symbol']}: {data['price']}")
```

### Authenticated Trading

```python
from bt_api_binance import BinanceApi

client = BinanceApi(
    api_key="your_api_key",
    secret_key="your_secret",
    asset_type="SWAP",  # USDT-M futures
    testnet=True,
)
client.connect()

# Set leverage
client.set_leverage("BTCUSDT", leverage=10)

# Place order
order = client.make_order(
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    price=67000,
    qty=0.001,
)
print(f"Order placed: {order['order_id']}")

# Monitor
while True:
    channel, data = client.poll_output(timeout=1.0)
    if channel == "account" and data.get("order_id") == order["order_id"]:
        print(f"Order update: {data['status']}")
```

### Real-time Kline Streaming

```python
client = BinanceApi(asset_type="SPOT", testnet=True)
client.connect()

client.subscribe_symbols(
    symbols=["BTCUSDT"],
    topics=["kline_1m", "ticker"]
)

while True:
    channel, data = client.poll_output(timeout=1.0)
    if channel == "market":
        if "interval" in data:
            print(f"Kline {data['interval']}: O={data['open']} H={data['high']} L={data['low']} C={data['close']}")
        else:
            print(f"Ticker: {data['price']}")
```
