---
title: WebSocket | bt_api_binance
---

# WebSocket | WebSocket 接口

WebSocket adapters bridge Binance WebSocket streams to bt_api_base's unified WebSocket interface.

---

## BinanceWsAdapter

**File**: `src/bt_api_binance/feeds/spot.py` (also in `swap.py`, `coin_m.py`, `margin.py`, `option.py`)

Internal WebSocket adapter class. Wraps `bt_api_base.websocket.ExchangeAdapter` for Binance-specific stream formatting.

### Stream URL Format

```
# Spot / Margin
wss://stream.binance.com:9443/ws/<stream_name>

# USDT-M Futures
wss://fstream.binance.com/ws/<stream_name>

# COIN-M Futures
wss://dstream.binance.com/ws/<stream_name>

# Options
wss://nbstream.binance.com/eoptions/ws/<stream_name>
```

### Combined Stream Names

Multiple streams can be combined using `/` delimiter:

```
btcusdt@ticker/ethusdt@depth20@100ms/btcusdt@trade
```

### Binance Market Stream Names

| Data Type | Stream Format | Example |
|-----------|---------------|---------|
| 24hr Ticker | `<symbol>@ticker` | `btcusdt@ticker` |
| Book Depth | `<symbol>@depth<level>@<speed>` | `btcusdt@depth20@100ms` |
| K-Line | `<symbol>@kline_<interval>` | `btcusdt@kline_1m` |
| Trade | `<symbol>@trade` | `btcusdt@trade` |
| Mark Price | `<symbol>@markPrice` | `btcusdt@markPrice` |
| Funding Rate | `<symbol>@fundingRate` | `btcusdt@fundingRate` |
| All Mini Ticker | `!miniTicker@arr` | |
| All Book Ticker | `!bookTicker` | |

### Binance Account Stream Names

| Data Type | Stream Format |
|-----------|---------------|
| Account Update | `<account>@account` |
| Order Update | `<account>@order` |
| Trade Update | `<account>@trade` |
| Balance Update | `<account>@balance` |
| Position Update | `<account>@position` |

---

## WebSocket Data Flow

```
Binance WebSocket Server
       │
       ▼
BinanceWsAdapter
  ├─ parse_binance_message()      # Parse JSON, route by stream type
  ├─ convert_to_container()        # Convert to TickContainer/OrderBook/etc
  └─ dispatch_to_callback()        # Push to registered callbacks
       │
       ▼
bt_api Base Event Bus / Data Queue
       │
       ▼
User Code (poll_output() / get_data_queue())
```

---

## WssData Classes

Each asset type has market and account `WssData` classes:

### BinanceMarketWssDataSpot

```python
class BinanceMarketWssDataSpot(BinanceMarketWssDataBase):
    # Subscribes to: ticker, depth, kline, trade
    # WSS base: wss://stream.binance.com:9443/ws
```

### BinanceAccountWssDataSpot

```python
class BinanceAccountWssDataSpot(BinanceAccountWssDataBase):
    # Subscribes to: balance, order, myTrades
    # WSS base: wss://stream.binance.com:9443/ws
```

### BinanceMarketWssDataSwap

```python
class BinanceMarketWssDataSwap(BinanceMarketWssDataBase):
    # Subscribes to: ticker, depth, kline, trade, markPrice, fundingRate
    # WSS base: wss://fstream.binance.com/ws
```

### BinanceAccountWssDataSwap

```python
class BinanceAccountWssDataSwap(BinanceAccountWssDataBase):
    # Subscribes to: balance, position, order, trade
    # WSS base: wss://fstream.binance.com/ws
```

### BinanceMarketWssDataCoinM

```python
class BinanceMarketWssDataCoinM(BinanceMarketWssDataBase):
    # WSS base: wss://dstream.binance.com/ws
```

### BinanceMarketWssDataMargin

```python
class BinanceMarketWssDataMargin(BinanceMarketWssDataBase):
    # WSS base: wss://stream.binance.com/ws
```

### BinanceMarketWssDataOption

```python
class BinanceMarketWssDataOption(BinanceMarketWssDataBase):
    # WSS base: wss://nbstream.binance.com/eoptions/ws
```

---

## Direct Client WebSocket Usage

```python
from bt_api_binance import BinanceApi

client = BinanceApi(
    api_key="your_key",
    secret_key="your_secret",
    asset_type="SPOT",
    testnet=True,
)

client.connect()

# Subscribe to market data
client.subscribe_symbols(["BTCUSDT", "ETHUSDT"])

# Poll for data
while True:
    channel, data = client.poll_output()
    if channel == "market":
        print(f"Ticker: {data['symbol']} @ {data['price']}")
    elif channel == "depth":
        print(f"OrderBook: {data['symbol']} bids={len(data['bids'])} asks={len(data['asks'])}")
    elif channel == "kline":
        print(f"Kline: {data['symbol']} {data['interval']} close={data['close']}")
```

---

## bt_api Plugin WebSocket Usage

```python
from bt_api_py import BtApi

api = BtApi(exchange_kwargs={
    "BINANCE___SPOT": {"api_key": "key", "secret": "secret", "testnet": True}
})

# Subscribe via bt_api
api.subscribe(
    "BINANCE___SPOT___BTCUSDT",
    [
        {"topic": "ticker", "symbol": "BTCUSDT"},
        {"topic": "depth", "symbol": "BTCUSDT", "depth": 20},
        {"topic": "kline", "symbol": "BTCUSDT", "interval": "1m"},
    ]
)

# Get data queue
queue = api.get_data_queue("BINANCE___SPOT")
while True:
    msg = queue.get(timeout=10)
    print(type(msg).__name__, msg)
```

---

## Connection Management

| Method | Description |
|--------|-------------|
| `is_connected()` | Check WebSocket connection status |
| `reconnect()` | Manually trigger reconnection |
| `disconnect()` | Gracefully close WebSocket connection |
| `ping()` | Send ping to keep connection alive |

WebSocket connections auto-reconnect on disconnect (handled by `bt_api_base.websocket.ExchangeAdapter`).
