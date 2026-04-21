# bt_api_binance test layout

This directory contains all Binance-specific tests, consolidated from the root `tests/` tree and `examples/`.

## Plugin implementation tests

- `test_plugin_registration.py` — plugin entry point and registry registration
- `test_binance_sign.py` — Binance HMAC signing
- `feeds/test_binance_request_base.py` — request feed base class
- `exchange_data/test_binance_exchange_data.py` — exchange data classes
- `exchange_data/test_binance_exchange_data_smoke.py` — smoke tests
- `exchange_data/test_binance_wallet_api.py` — wallet API paths
- `exchange_data/test_binance_wss_paths.py` — websocket paths
- `exchange_registers/test_register_binance.py` — registry shim compatibility

## Container and data model tests

Migrated from `tests/containers/` and `tests/test_binance_*.py`:

- `containers/accounts/test_binance_account.py`
- `containers/balances/test_binance_balance.py`
- `containers/bars/test_binance_request_bar.py`
- `containers/fundingrates/test_binance_funding_rate.py`
- `containers/incomes/test_binance_income.py`
- `containers/markprices/test_binance_mark_price.py`
- `containers/orderbooks/test_binance_orderbook.py`
- `containers/orders/test_binance_order.py`
- `containers/orders/test_receive_binance_order.py`
- `containers/positions/test_binance_position.py`
- `containers/symbols/test_binance_symbol.py`
- `containers/tickers/test_binance_ticker.py`
- `containers/trades/test_binance_trade.py`
- `test_binance_balance.py`
- `test_binance_funding_rate.py`
- `test_binance_income.py`
- `test_binance_mark_price.py`
- `test_binance_order.py`
- `test_binance_position.py`
- `test_binance_symbol.py`
- `errors/test_binance_translator.py`

Note: these tests still import from `bt_api_py.containers.*` and `bt_api_py.errors.*` because the source code for those container classes has not yet been moved into the plugin package.

## Network-oriented Binance tests

Migrated from `examples/network_tests/feeds/`:

- `network/test_binance.py`
- `network/test_live_binance_margin_wss_data.py`
- `network/test_live_binance_spot_request_data.py`
- `network/test_live_binance_spot_wss_data.py`
- `network/test_live_binance_swap_request_data.py`
- `network/test_live_binance_swap_wss_data.py`
- `network/live_binance/*.py`

## Remaining Binance references in root `tests/`

The following files in the root `tests/` tree still contain Binance references but are **cross-exchange or core integration tests** and should stay there:

- `tests/test_registry_and_balance.py` — multi-exchange registry smoke test
- `tests/plugins/test_bt_api_startup.py` — plugin loader startup behavior
- `tests/test_gateway_runtime.py` — gateway adapter wiring (multi-exchange)
- `tests/test_stage1_exchange_integration.py` — cross-exchange feed/error/rate-limiter integration
