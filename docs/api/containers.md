---
title: Containers | bt_api_binance
---

# Containers | 数据容器

All Binance data containers normalize exchange responses into bt_api_base unified types.

---

## AccountBalanceContainer

```python
class AccountBalanceContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `account` | `str` | Asset type (e.g. `"SPOT"`, `"SWAP"`) |
| `timestamp` | `int` | Unix timestamp in milliseconds |
| `balance` | `float` | Total balance |
| `frozen` | `float` | Frozen/locked balance |
| `available` | `float` | Available balance |
| `asset` | `str` | Asset symbol (e.g. `"USDT"`) |

---

## OrderContainer

```python
class OrderContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `symbol` | `str` | Trading symbol (e.g. `"BTCUSDT"`) |
| `order_id` | `str` | Exchange order ID |
| `client_order_id` | `str` | Client-supplied order ID |
| `price` | `float` | Order price |
| `stop_price` | `float` | Stop price (if any) |
| `orig_qty` | `float` | Original quantity |
| `executed_qty` | `float` | Filled quantity |
| `avg_price` | `float` | Average fill price |
| `status` | `str` | `"NEW"`, `"PARTIALLY_FILLED"`, `"FILLED"`, `"CANCELED"`, `"REJECTED"`, `"EXPIRED"` |
| `type` | `str` | `"LIMIT"`, `"MARKET"`, `"STOP"`, `"STOP_MARKET"`, `"TAKE_PROFIT"`, `"TAKE_PROFIT_MARKET"`, `"TRAILING_STOP_MARKET"` |
| `side` | `str` | `"BUY"` or `"SELL"` |
| `position_side` | `str` | `"LONG"`, `"SHORT"`, `"BOTH"` (futures only) |
| `time` | `int` | Order creation time (ms) |
| `update_time` | `int` | Last update time (ms) |
| `is_isolated` | `bool` | Isolated margin (margin only) |
| `is_market` | `bool` | Whether order is market type |

---

## PositionContainer

```python
class PositionContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `symbol` | `str` | Position symbol (e.g. `"BTCUSDT"`) |
| `amount` | `float` | Position size |
| `available` | `float` | Available to close |
| `price` | `float` | Entry price |
| `value` | `float` | Position notional value |
| `leverage` | `float` | Leverage multiplier |
| `isolated` | `bool` | Whether isolated margin |
| `side` | `str` | `"LONG"` or `"SHORT"` |
| `unrealized_pnl` | `float` | Unrealized PnL |
| `realized_pnl` | `float` | Realized PnL today |
| `margin` | `float` | Position margin |
| `maintenance_margin` | `float` | Maintenance margin |
| `r_open_ratio` | `float` | ROI % (unrealized) |
| `r_day_profit` | `float` | Daily realized PnL |

---

## TickContainer

```python
class TickContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `symbol` | `str` | Symbol (e.g. `"BTCUSDT"`) |
| `timestamp` | `int` | Unix timestamp (ms) |
| `price` | `float` | Last trade price |
| `bid_price` | `float` | Best bid price |
| `ask_price` | `float` | Best ask price |
| `bid_qty` | `float` | Best bid quantity |
| `ask_qty` | `float` | Best ask quantity |
| `open` | `float` | 24h open price |
| `high` | `float` | 24h high |
| `low` | `float` | 24h low |
| `volume` | `float` | 24h volume (base asset) |
| `quote_volume` | `float` | 24h volume (quote asset) |
| `direction` | `int` | `1` = up, `-1` = down, `0` = unchanged |

---

## OrderBookContainer

```python
class OrderBookContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `symbol` | `str` | Symbol |
| `timestamp` | `int` | Unix timestamp (ms) |
| `asks` | `List[Tuple[float, float]]` | Ask levels `[[price, qty], ...]` |
| `bids` | `List[Tuple[float, float]]` | Bid levels `[[price, qty], ...]` |
| `seq` | `int` | Sequence number (exchange provided) |

---

## BarContainer

```python
class BarContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `symbol` | `str` | Symbol |
| `timestamp` | `int` | Bar start time (ms) |
| `open` | `float` | Open price |
| `high` | `float` | High price |
| `low` | `float` | Low price |
| `close` | `float` | Close price |
| `volume` | `float` | Volume (base asset) |
| `quote_volume` | `float` | Turnover (quote asset) |
| `close_time` | `int` | Bar close time (ms) |
| `interval` | `str` | Bar interval (e.g. `"1m"`, `"1h"`, `"1d"`) |

---

## TradeContainer

```python
class TradeContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `symbol` | `str` | Symbol |
| `timestamp` | `int` | Trade time (ms) |
| `price` | `float` | Trade price |
| `qty` | `float` | Trade quantity |
| `is_buyer_maker` | `bool` | `True` = maker sell, `False` = maker buy |
| `trade_id` | `str` | Trade ID |
| `is_auto_atomic` | `bool` | Whether PTBN (auto settle) |

---

## FundingRateContainer

```python
class FundingRateContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `symbol` | `str` | Symbol |
| `funding_rate` | `float` | Current funding rate |
| `funding_time` | `int` | Next funding time (ms) |
| `mark_price` | `float` | Mark price |
| `index_price` | `float` | Index price |

---

## MarkPriceContainer

```python
class MarkPriceContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `symbol` | `str` | Symbol |
| `timestamp` | `int` | Unix timestamp (ms) |
| `mark_price` | `float` | Mark price |
| `index_price` | `float` | Index price |
| `est_settlement_price` | `float` | Estimated settlement price |
| `next_funding_time` | `int` | Next funding time (ms) |

---

## IncomeContainer

```python
class IncomeContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `symbol` | `str` | Symbol |
| `income_type` | `str` | `"TRANSFER"`, `"WELCOME_BONUS"`, `"REALIZED_PNL"`, `"FUNDING_FEE"`, `"COMMISSION"`, `"INSURANCE_CLEAR"`, `"TS_COMMISSION"`, `"liquidation_fee"`, `"BORROW_INTEREST"`, `"LP_FEE"`, `"CUTOFF_PRINCIPAL"`, `"CUTOFF_REMU"`, `"MCUTOFF_REMU"`, `"CLQ魂斗罗"`, `"INSURE_CLEAR"` |
| `amount` | `float` | Income amount |
| `asset` | `str` | Asset symbol |
| `timestamp` | `int` | Trade time (ms) |
| `trade_id` | `str` | Related trade ID |

---

## AccountContainer

```python
class AccountContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `account` | `str` | Asset type |
| `can_trade` | `bool` | Whether trading enabled |
| `can_deposit` | `bool` | Whether deposit enabled |
| `can_withdraw` | `bool` | Whether withdraw enabled |
| `update_time` | `int` | Last update time (ms) |
| `balances` | `List[AccountBalanceContainer]` | All asset balances |

---

## SymbolContainer

```python
class SymbolContainer
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `str` | Always `"BINANCE"` |
| `symbol` | `str` | Symbol |
| `base_asset` | `str` | Base asset (e.g. `"BTC"`) |
| `quote_asset` | `str` | Quote asset (e.g. `"USDT"`) |
| `price_precision` | `int` | Price decimal places |
| `qty_precision` | `int` | Quantity decimal places |
| `min_qty` | `float` | Minimum order quantity |
| `min_notional` | `float` | Minimum order notional value |
| `max_qty` | `float` | Maximum order quantity |
| `max_qty_precision` | `float` | Quantity precision |
| `tick_size` | `float` | Price tick size |
| `status` | `str` | `"TRADING"`, `"BREAK"`, etc. |

---

## All Containers

| Class | File |
|-------|------|
| `AccountBalanceContainer` | `containers/account_balance.py` |
| `OrderContainer` | `containers/order.py` |
| `PositionContainer` | `containers/position.py` |
| `TickContainer` | `containers/tick.py` |
| `OrderBookContainer` | `containers/orderbook.py` |
| `BarContainer` | `containers/bar.py` |
| `TradeContainer` | `containers/trade.py` |
| `FundingRateContainer` | `containers/funding_rate.py` |
| `MarkPriceContainer` | `containers/mark_price.py` |
| `IncomeContainer` | `containers/income.py` |
| `AccountContainer` | `containers/account.py` |
| `SymbolContainer` | `containers/symbol.py` |
