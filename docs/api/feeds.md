---
title: Feeds | bt_api_binance
---

# Feeds | 数据订阅层

Feeds handle data subscription and retrieval for Binance. Each asset type has three feed layers.

---

## Architecture

```
Request Layer (REST polling)
  └── BinanceRequestData<AssetType>

Market WebSocket Layer (real-time market data)
  └── BinanceMarketWssData<AssetType>

Account WebSocket Layer (real-time account/position/order data)
  └── BinanceAccountWssData<AssetType>
```

---

## BinanceRequestData

Base: `RequestData`

Base class for REST request feeds. Handles synchronous REST API calls.

### Common Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_ticker(symbol)` | `TickContainer` | 24hr ticker statistics |
| `get_orderbook(symbol, depth)` | `OrderBookContainer` | Order book depth |
| `get_bars(symbol, interval, limit)` | `List[BarContainer]` | K-line/candlestick data |
| `get_trades(symbol, limit)` | `List[TradeContainer]` | Recent trades |
| `get_symbol_info(symbol)` | `SymbolContainer` | Symbol trading rules |
| `get_balance()` | `List[AccountBalanceContainer]` | Account balances |
| `get_order(symbol, order_id)` | `OrderContainer` | Query specific order |
| `get_open_orders(symbol)` | `List[OrderContainer]` | All open orders |
| `get_position(symbol)` | `List[PositionContainer]` | Position details |
| `get_account()` | `AccountContainer` | Full account info |
| `make_order(...)` | `OrderContainer` | Place a new order |
| `cancel_order(symbol, order_id)` | `bool` | Cancel an order |
| `cancel_orders(symbol)` | `bool` | Cancel all open orders |
| `set_leverage(symbol, leverage)` | `bool` | Set symbol leverage |

---

## BinanceMarketWssData

Base: `MarketWssData`

Base class for WebSocket market data feeds.

### Subscription Topics

| Topic | Description | Example |
|-------|-------------|---------|
| `"ticker"` | 24hr rolling ticker | `{"symbol": "BTCUSDT"}` |
| `"depth"` | Order book depth | `{"symbol": "BTCUSDT", "depth": 20}` |
| `"kline"` | K-line/candlestick | `{"symbol": "BTCUSDT", "interval": "1m"}` |
| `"trade"` | Individual trades | `{"symbol": "BTCUSDT"}` |
| `"markPrice"` | Mark price (futures) | `{"symbol": "BTCUSDT"}` |
| `"fundingRate"` | Funding rate (futures) | `{"symbol": "BTCUSDT"}` |

### Common Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `subscribe(symbols, topics)` | `bool` | Subscribe to market data |
| `unsubscribe(symbols, topics)` | `bool` | Unsubscribe |
| `is_connected()` | `bool` | WebSocket connection status |

---

## BinanceAccountWssData

Base: `AccountWssData`

Base class for WebSocket account data feeds.

### Subscription Topics

| Topic | Description |
|-------|-------------|
| `"balance"` | Account balance updates |
| `"position"` | Position updates |
| `"order"` | Order updates |
| `"myTrades"` | Executed trades |

### Common Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `subscribe(symbols, topics)` | `bool` | Subscribe to account data |
| `unsubscribe(symbols, topics)` | `bool` | Unsubscribe |
| `is_connected()` | `bool` | WebSocket connection status |

---

## Spot Feeds

### BinanceRequestDataSpot

File: `src/bt_api_binance/feeds/spot.py`

| Method | Description |
|--------|-------------|
| `get_ticker(symbol)` | 24hr ticker for spot symbol |
| `get_orderbook(symbol, depth)` | Spot order book |
| `get_bars(symbol, interval, limit)` | Spot K-lines |
| `get_trades(symbol, limit)` | Spot trade history |
| `get_symbol_info(symbol)` | Spot symbol info |
| `get_balance()` | Spot wallet balances |
| `get_order(symbol, order_id)` | Spot order status |
| `get_open_orders(symbol)` | All open spot orders |
| `make_order(symbol, side, price, qty, order_type)` | Place spot order |
| `cancel_order(symbol, order_id)` | Cancel spot order |
| `cancel_orders(symbol)` | Cancel all spot orders |

### BinanceMarketWssDataSpot

| Topic | Binance WebSocket Stream |
|-------|--------------------------|
| `ticker` | `<symbol>@ticker` |
| `depth` | `<symbol>@depth<level>@100ms` |
| `kline` | `<symbol>@kline_<interval>` |
| `trade` | `<symbol>@trade` |

### BinanceAccountWssDataSpot

| Topic | Binance WebSocket Stream |
|-------|--------------------------|
| `balance` | `<account>@balance` |
| `order` | `<account>@order` |
| `myTrades` | `<account>@trade` |

---

## Swap Feeds (USDT-M Futures)

### BinanceRequestDataSwap

| Method | Description |
|--------|-------------|
| `get_ticker(symbol)` | 24hr ticker |
| `get_orderbook(symbol, depth)` | Order book |
| `get_bars(symbol, interval, limit)` | K-lines |
| `get_trades(symbol, limit)` | Trade history |
| `get_funding_rate(symbol)` | Current funding rate |
| `get_mark_price(symbol)` | Mark price |
| `get_position(symbol)` | Futures position |
| `get_balance()` | USDT-M account balance |
| `get_open_orders(symbol)` | Open orders |
| `get_order(symbol, order_id)` | Order status |
| `make_order(...)` | Place futures order |
| `set_leverage(symbol, leverage)` | Set leverage |
| `set_margin_type(symbol, margin_type)` | Set cross/isolated |
| `add_margin(symbol, qty)` | Add position margin |
| `cancel_order(symbol, order_id)` | Cancel order |
| `get_income(symbol, limit)` | Position income history |

### BinanceMarketWssDataSwap

| Topic | Binance WebSocket Stream |
|-------|--------------------------|
| `ticker` | `<symbol>@ticker` |
| `depth` | `<symbol>@depth<level>@100ms` |
| `kline` | `<symbol>@kline_<interval>` |
| `trade` | `<symbol>@trade` |
| `markPrice` | `<symbol>@markPrice` |
| `fundingRate` | `<symbol>@fundingRate` |

### BinanceAccountWssDataSwap

| Topic | Binance WebSocket Stream |
|-------|--------------------------|
| `balance` | `<account>@balance` |
| `position` | `<account>@position` |
| `order` | `<account>@order` |
| `myTrades` | `<account>@trade` |

---

## Coin-M Feeds (COIN-M Futures)

### BinanceRequestDataCoinM

Same interface as Swap but for coin-margined futures (`dapi`).

### BinanceMarketWssDataCoinM

Same topics as Swap but via `dstream.binance.com`.

### BinanceAccountWssDataCoinM

Same topics as Swap.

---

## Other Asset Type Feeds

| Asset Type | Request Class | Market WSS Class | Account WSS Class |
|---|---|---|---|
| MARGIN | `BinanceRequestDataMargin` | `BinanceMarketWssDataMargin` | `BinanceAccountWssDataMargin` |
| OPTION | `BinanceRequestDataOption` | `BinanceMarketWssDataOption` | `BinanceAccountWssDataOption` |
| ALGO | `BinanceRequestDataAlgo` | — | — |
| GRID | `BinanceRequestDataGrid` | — | — |
| STAKING | `BinanceRequestDataStaking` | — | — |
| MINING | `BinanceRequestDataMining` | — | — |
| VIP_LOAN | `BinanceRequestDataVipLoan` | — | — |
| WALLET | `BinanceRequestDataWallet` | — | — |
| SUB_ACCOUNT | `BinanceRequestDataSubAccount` | — | — |
| PORTFOLIO | `BinanceRequestDataPortfolio` | — | — |

Note: ALGO, GRID, STAKING, MINING, VIP_LOAN, WALLET, SUB_ACCOUNT, PORTFOLIO are **REST-only** (no WebSocket support).

---

## K-Line Intervals

Binance supports these K-line intervals:

| Interval | Description |
|----------|-------------|
| `1m` | 1 minute |
| `3m` | 3 minutes |
| `5m` | 5 minutes |
| `15m` | 15 minutes |
| `30m` | 30 minutes |
| `1h` | 1 hour |
| `2h` | 2 hours |
| `4h` | 4 hours |
| `6h` | 6 hours |
| `8h` | 8 hours |
| `12h` | 12 hours |
| `1d` | 1 day |
| `3d` | 3 days |
| `1w` | 1 week |
| `1M` | 1 month |

---

## Order Types

| Type | Description |
|------|-------------|
| `LIMIT` | Limit order |
| `MARKET` | Market order |
| `STOP` | Stop loss limit |
| `STOP_MARKET` | Stop loss market |
| `TAKE_PROFIT` | Take profit limit |
| `TAKE_PROFIT_MARKET` | Take profit market |
| `TRAILING_STOP_MARKET` | Trailing stop |
| `GTC` | Good-Till-Cancel (default) |
| `IOC` | Immediate-Or-Cancel |
| `FOK` | Fill-Or-Kill |
