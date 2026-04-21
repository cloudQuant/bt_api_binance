---
title: Gateway | bt_api_binance
---

# Gateway | 网关适配器

Gateway adapters bridge the bt_api plugin system to Binance exchange APIs.

---

## BinanceGatewayAdapter

**File**: `src/bt_api_binance/gateway/adapter.py`

```python
class BinanceGatewayAdapter(PluginGatewayAdapter):
    def __init__(
        self,
        exchange_config: BinanceExchangeData,
        cache_handler: CacheHandler | None = None,
        rate_limit_handler: RateLimitHandler | None = None,
        http_session_handler: HttpSessionHandler | None = None,
    ):
        ...
```

Inherits from `bt_api_base.gateway.PluginGatewayAdapter`. Provides the bridge between:
- bt_api plugin system (upstream)
- Binance REST / WebSocket APIs (downstream)

### Key Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `connect()` | `None` | Initialize HTTP session, WebSocket connections |
| `disconnect()` | `None` | Close all connections |
| `is_connected()` | `bool` | Connection status |
| `get_exchange_data()` | `BinanceExchangeData` | Exchange configuration |
| `get_request_data()` | `RequestData` | REST request handler |
| `get_market_wss_data()` | `MarketWssData` | Market WebSocket handler |
| `get_account_wss_data()` | `AccountWssData` | Account WebSocket handler |

### Inheritance Chain

```
BinanceGatewayAdapter
  └── PluginGatewayAdapter (bt_api_base.gateway)
        └── GatewayAdapterBase (bt_api_base.gateway)
              ├── connect()
              ├── disconnect()
              ├── is_connected()
              └── get_exchange_data()
```

---

## Plugin Registration

The `register_plugin()` function in `plugin.py` registers `BinanceGatewayAdapter` with the `ExchangeRegistry`:

```python
def register_plugin(registry: ExchangeRegistry) -> None:
    registry.register_adapter(
        exchange_code="BINANCE",
        asset_type=AssetType.SPOT,
        adapter_class=BinanceGatewayAdapter,
        exchange_data_class=BinanceExchangeDataSpot,
        feeds={
            "request": BinanceRequestDataSpot,
            "market_wss": BinanceMarketWssDataSpot,
            "account_wss": BinanceAccountWssDataSpot,
        },
        balance_handler_class=BinanceBalanceHandlerSpot,
    )
    # ... registers SWAP, COIN_M, MARGIN, OPTION, etc.
```

This enables `BtApi("BINANCE___SPOT")` to automatically resolve to `BinanceGatewayAdapter`.

---

## Balance Handler

Each asset type has a `BinanceBalanceHandler<AssetType>` that normalizes balance data from Binance API responses into `AccountBalanceContainer` format.

| Asset Type | Handler Class |
|---|---|
| SPOT | `BinanceBalanceHandlerSpot` |
| SWAP | `BinanceBalanceHandlerSwap` |
| COIN_M | `BinanceBalanceHandlerCoinM` |
| MARGIN | `BinanceBalanceHandlerMargin` |
| OPTION | `BinanceBalanceHandlerOption` |

---

## Error Translation

`BinanceErrorTranslator` (`errors/binance_translator.py`) maps Binance API error codes to bt_api_base `ApiError` exceptions:

| Binance Error Code | bt_api Error | Description |
|---|---|---|
| `-1000` | `API_ERROR` | Unknown error |
| `-1001` | `DISCONNECTED` | Disconnected |
| `-1003` | `RATE_LIMIT` | Too many requests |
| `-1013` | `INVALID_PARAMETER` | Invalid quantity |
| `-1021` | `TIMESTAMP_INVALID` | Invalid timestamp |
| `-1022` | `SIGNATURE_INVALID` | Invalid signature |
| `-1102` | `API_KEY_MISSING` | API key not provided |
| `-1103` | `INVALID_PARAMETER` | Invalid parameter |
| `-1111` | `PRECISION_ERROR` | Price precision error |
| `-2013` | `ORDER_NOT_FOUND` | Order does not exist |
| `-2014` | `API_KEY_INVALID` | Invalid API key |
| `-2015` | `INVALID_PARAMETER` | Invalid nonce |
| `-2019` | `MARGIN_INSUFFICIENT` | Insufficient margin |
| `-2020` | `BALANCE_INSUFFICIENT` | Insufficient balance |
| `-2021` | `ORDER_WOULD_Iceberg` | Order would trigger iceberg |
| `-2022` | `ORDER_WOULD_EXCEED_POSITION` | Position limit exceeded |
| `-2026` | `LEVERAGE_INVALID` | Invalid leverage |
| `-9000` | `RATE_LIMIT` | Rate limit exceeded |
