"""Module-level docstring."""
from __future__ import annotations

from bt_api_base.containers.requestdatas.request_data import RequestData
from bt_api_binance.containers.orders.binance_order import BinanceRequestOrderData


def test_request_data() -> None:
    """test_request_data function"""
    datas = {
        "clientOrderId": "testOrder",  # 
        "cumQty": "0",
        "cumQuote": "0",  # 
        "executedQty": "0",  # 
        "orderId": 22542179,  # 
        "avgPrice": "0.00000",  # 
        "origQty": "10",  # 
        "price": "0",  # 
        "reduceOnly": "false",  # 
        "side": "SELL",  # 
        "positionSide": "SHORT",  # 
        "status": "NEW",  # 
        "stopPrice": "0",  # ，`TRAILING_STOP_MARKET`
        "closePosition": "false",  # 
        "symbol": "BTCUSDT",  # 
        "timeInForce": "GTD",  # 
        "type": "TRAILING_STOP_MARKET",  # 
        "origType": "TRAILING_STOP_MARKET",  # 
        "activatePrice": "9020",  # , `TRAILING_STOP_MARKET` 
        "priceRate": "0.3",  # , `TRAILING_STOP_MARKET` 
        "updateTime": 1566818724722,  # 
        "workingType": "CONTRACT_PRICE",  # 
        "priceProtect": "false",  # 
        "priceMatch": "NONE",  # 
        "selfTradePreventionMode": "NONE",  # 
        "goodTillDate": 1693207680000,  # TIFGTD
    }

    def _get_open_orders_normalize_function(
        input_data: dict[str, object] | list[dict[str, object]],
        extra_data_: dict[str, object],
    ) -> tuple[list[BinanceRequestOrderData], bool]:
        status = input_data is not None
        symbol_name = str(extra_data_["symbol_name"])
        asset_type = str(extra_data_["asset_type"])
        if isinstance(input_data, list):
            data = [BinanceRequestOrderData(i, symbol_name, asset_type, True) for i in input_data]
        elif isinstance(input_data, dict):
            data = [BinanceRequestOrderData(input_data, symbol_name, asset_type, True)]
        else:
            data = []
        return data, status

    extra_data = {
        "request_type": "get_open_orders",
        "symbol_name": "BTCUSDT",
        "asset_type": "SWAP",
        "exchange_name": "BINANCE",
        "normalize_function": _get_open_orders_normalize_function,
    }
    request_data = RequestData(datas, extra_data=extra_data, status=False)

    request_data.init_data()
    assert request_data.get_event() == "RequestEvent"
    assert request_data.get_status() is True
    assert request_data.get_symbol_name() == "BTCUSDT"
    assert request_data.get_asset_type() == "SWAP"
    assert request_data.get_exchange_name() == "BINANCE"
    assert len(request_data.get_data()) > 0
    assert isinstance(request_data.get_extra_data(), dict)


def test_request_data_uses_constructor_normalize_func() -> None:
    """test_request_data_uses_constructor_normalize_func function"""
    calls: list[tuple[object, dict[str, object]]] = []

    def normalize_func(
        input_data: object, extra_data: dict[str, object]
    ) -> tuple[list[dict[str, object]], bool]:
        calls.append((input_data, extra_data))
        return [{"normalized": True}], True

    request_data = RequestData(
        {"payload": 1},
        extra_data={"exchange_name": "BINANCE", "request_type": "ping"},
        normalize_func=normalize_func,
    )

    assert request_data.get_status() is True
    assert request_data.get_data() == [{"normalized": True}]
    assert len(calls) == 1


def test_request_data_without_normalizer_returns_raw_input() -> None:
    """test_request_data_without_normalizer_returns_raw_input function"""
    raw_payload = {"pong": True}
    request_data = RequestData(
        raw_payload,
        extra_data={"exchange_name": "BINANCE", "request_type": "ping"},
        status=False,
    )

    assert request_data.get_data() == raw_payload
    assert request_data.get_status() is None
