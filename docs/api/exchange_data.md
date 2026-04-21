---
title: Exchange Data | bt_api_binance
---

# Exchange Data | 交易所数据

Exchange data classes provide exchange-specific configuration for Binance.

---

## BinanceExchangeData

**File**: `src/bt_api_binance/exchange_data/binance_exchange_data.py`

Base class for all Binance exchange data classes. Provides:
- Exchange name: `BINANCE`
- Asset type identification
- REST and WebSocket base URLs from `binance.yaml` config
- HMAC-SHA256 request signing
- API key / secret key management

```python
class BinanceExchangeData(ExchangeData):
    def __init__(
        self,
        exchange_name: str,
        api_key: str | None = None,
        secret_key: str | None = None,
        passphrase: str | None = None,
        testnet: bool = False,
        asset_type: AssetType | None = None,
    ):
        ...
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_exchange_name()` | `str` | Exchange identifier |
| `get_asset_type()` | `AssetType` | Asset type enum |
| `get_rest_url()` | `str` | REST API base URL |
| `get_wss_url()` | `str` | WebSocket base URL |
| `get_api_key()` | `str \| None` | API key |
| `get_secret_key()` | `str \| None` | Secret key |
| `get_passphrase()` | `str \| None` | Passphrase |
| `is_testnet()` | `bool` | Whether using testnet |
| `is_perpetual()` | `bool` | Whether perpetual futures |
| `sign(params: Dict)` | `Dict` | Sign request params with HMAC-SHA256 |

---

## BinanceExchangeDataSpot

```python
class BinanceExchangeDataSpot(BinanceExchangeData)
```

- Exchange code: `BINANCE___SPOT`
- Asset type: `AssetType.SPOT`
- REST: `https://api.binance.com`
- WSS: `wss://stream.binance.com:9443/ws`
- Perpetual: `False`

---

## BinanceExchangeDataSwap

```python
class BinanceExchangeDataSwap(BinanceExchangeData)
```

- Exchange code: `BINANCE___SWAP`
- Asset type: `AssetType.SWAP`
- REST: `https://fapi.binance.com`
- WSS: `wss://fstream.binance.com/ws`
- Perpetual: `True`

---

## BinanceExchangeDataCoinM

```python
class BinanceExchangeDataCoinM(BinanceExchangeData)
```

- Exchange code: `BINANCE___COIN_M`
- Asset type: `AssetType.SWAP`
- REST: `https://dapi.binance.com`
- WSS: `wss://dstream.binance.com/ws`
- Perpetual: `True`

---

## BinanceExchangeDataMargin

```python
class BinanceExchangeDataMargin(BinanceExchangeData)
```

- Exchange code: `BINANCE___MARGIN`
- Asset type: `AssetType.MARGIN`
- REST: `https://api.binance.com`
- WSS: `wss://stream.binance.com/ws`

---

## BinanceExchangeDataOption

```python
class BinanceExchangeDataOption(BinanceExchangeData)
```

- Exchange code: `BINANCE___OPTION`
- Asset type: `AssetType.OPTION`
- REST: `https://eapi.binance.com`
- WSS: `wss://nbstream.binance.com/eoptions/ws`

---

## BinanceExchangeDataAlgo

```python
class BinanceExchangeDataAlgo(BinanceExchangeData)
```

- Exchange code: `BINANCE___ALGO`
- Asset type: `AssetType.ALGO`
- REST: `https://api.binance.com`
- WSS: N/A (REST-only)

---

## BinanceExchangeDataGrid

```python
class BinanceExchangeDataGrid(BinanceExchangeData)
```

- Exchange code: `BINANCE___GRID`
- Asset type: `AssetType.GRID`
- REST: `https://api.binance.com`

---

## BinanceExchangeDataStaking

```python
class BinanceExchangeDataStaking(BinanceExchangeData)
```

- Exchange code: `BINANCE___STAKING`
- Asset type: `AssetType.STAKING`
- REST: `https://api.binance.com`

---

## BinanceExchangeDataMining

```python
class BinanceExchangeDataMining(BinanceExchangeData)
```

- Exchange code: `BINANCE___MINING`
- Asset type: `AssetType.MINING`
- REST: `https://api.binance.com`

---

## BinanceExchangeDataVipLoan

```python
class BinanceExchangeDataVipLoan(BinanceExchangeData)
```

- Exchange code: `BINANCE___VIP_LOAN`
- Asset type: `AssetType.VIP_LOAN`
- REST: `https://api.binance.com`

---

## BinanceExchangeDataWallet

```python
class BinanceExchangeDataWallet(BinanceExchangeData)
```

- Exchange code: `BINANCE___WALLET`
- Asset type: `AssetType.WALLET`
- REST: `https://api.binance.com`

---

## BinanceExchangeDataSubAccount

```python
class BinanceExchangeDataSubAccount(BinanceExchangeData)
```

- Exchange code: `BINANCE___SUB_ACCOUNT`
- Asset type: `AssetType.SUB_ACCOUNT`
- REST: `https://api.binance.com`

---

## BinanceExchangeDataPortfolio

```python
class BinanceExchangeDataPortfolio(BinanceExchangeData)
```

- Exchange code: `BINANCE___PORTFOLIO`
- Asset type: `AssetType.PORTFOLIO`
- REST: `https://api.binance.com`

---

## Configuration (binance.yaml)

All exchange data classes read configuration from `configs/binance.yaml`:

```yaml
BINANCE:
  SPOT:
    name: "BINANCE"
    asset_type: "SPOT"
    rest:
      base: "https://api.binance.com"
    wss:
      base: "wss://stream.binance.com:9443/ws"
  SWAP:
    name: "BINANCE"
    asset_type: "SWAP"
    rest:
      base: "https://fapi.binance.com"
    wss:
      base: "wss://fstream.binance.com/ws"
  # ... all 13 asset types
```

Rate limits from YAML:

| Asset Type | Requests / Second | Orders / Second |
|---|---|---|
| SPOT | 1200 | 100 |
| SWAP | 2400 | 150 |
| COIN_M | 2400 | 150 |
| MARGIN | 1200 | 100 |
| OPTION | 1200 | 50 |
| ALGO | 1200 | 100 |
| GRID | 200 | 20 |
| STAKING | 200 | 20 |
| MINING | 200 | 20 |
| VIP_LOAN | 200 | 20 |
| WALLET | 200 | 20 |
| SUB_ACCOUNT | 200 | 20 |
| PORTFOLIO | 200 | 20 |
