"""
Tests for Binance Sub-account API Request Implementation
 Binance  API 
"""

import queue

from bt_api_binance.feeds.sub_account import BinanceRequestDataSubAccount


def test_sub_account_request_init():
    """ Sub-account Request """
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(
        data_queue, public_key="test_public_key", private_key="test_private_key"
    )
    assert sub_account.asset_type == "SUB_ACCOUNT"
    assert sub_account.logger_name == "binance_sub_account_feed.log"
    assert sub_account.exchange_name == "binance_sub_account"
    assert sub_account._params.rest_url == "https://api.binance.com"


def test_sub_account_request_has_list_methods():
    """ Sub-account Request """
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(data_queue)
    assert hasattr(sub_account, "get_sub_account_list")
    assert hasattr(sub_account, "_get_sub_account_list")
    assert hasattr(sub_account, "get_sub_account_status")
    assert hasattr(sub_account, "get_sub_account_spot_summary")


def test_sub_account_request_has_transfer_methods():
    """ Sub-account Request """
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(data_queue)
    assert hasattr(sub_account, "sub_transfer_to_main")
    assert hasattr(sub_account, "main_transfer_to_sub")
    assert hasattr(sub_account, "sub_transfer_to_sub")
    assert hasattr(sub_account, "get_sub_transfer_history")


def test_sub_account_request_has_asset_methods():
    """ Sub-account Request """
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(data_queue)
    assert hasattr(sub_account, "get_sub_account_assets")
    assert hasattr(sub_account, "get_sub_account_margin_account")
    assert hasattr(sub_account, "get_sub_account_margin_summary")
    assert hasattr(sub_account, "get_sub_account_futures_account")


def test_sub_account_request_has_api_key_methods():
    """ Sub-account Request  API Key """
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(data_queue)
    assert hasattr(sub_account, "create_sub_api_key")
    assert hasattr(sub_account, "get_sub_api_key")
    assert hasattr(sub_account, "delete_sub_api_key")
    assert hasattr(sub_account, "get_sub_api_ip_restriction")
    assert hasattr(sub_account, "delete_sub_ip_restriction")


def test_sub_account_request_get_sub_account_list_params():
    """ get_sub_account_list """
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(
        data_queue, public_key="test_key", private_key="test_secret"
    )

    path, params, extra_data = sub_account._get_sub_account_list()

    assert path == "GET /sapi/v1/sub-account/list"
    assert params == {}
    assert extra_data["request_type"] == "get_sub_account_list"


def test_sub_account_request_sub_transfer_to_main_params():
    """ sub_transfer_to_main """
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(data_queue)

    path, params, extra_data = sub_account._sub_transfer_to_main(
        email="test@example.com", asset="USDT", amount=100
    )

    assert path == "POST /sapi/v1/sub-account/transfer/sub-to-main"
    assert params["email"] == "test@example.com"
    assert params["asset"] == "USDT"
    assert params["amount"] == 100


def test_sub_account_request_main_transfer_to_sub_params():
    """ main_transfer_to_sub """
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(data_queue)

    path, params, extra_data = sub_account._main_transfer_to_sub(
        email="test@example.com", asset="USDT", amount=100
    )

    assert path == "POST /sapi/v1/sub-account/transfer/main-to-sub"
    assert params["toEmail"] == "test@example.com"
    assert params["asset"] == "USDT"
    assert params["amount"] == 100


def test_sub_account_request_get_sub_account_assets_params():
    """ get_sub_account_assets """
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(data_queue)

    path, params, extra_data = sub_account._get_sub_account_assets(email="test@example.com")

    assert path == "GET /sapi/v1/sub-account/assets"
    assert params["email"] == "test@example.com"


def test_sub_account_request_delete_sub_api_key_params():
    """ delete_sub_api_key """
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(data_queue)

    path, params, extra_data = sub_account._delete_sub_api_key(
        email="test@example.com", api_key="test_api_key"
    )

    assert path == "DELETE /sapi/v1/sub-account/apiKey"
    assert params["email"] == "test@example.com"
    assert params["publicKey"] == "test_api_key"


def test_sub_account_request_all_public_methods():
    """"""
    data_queue = queue.Queue()
    sub_account = BinanceRequestDataSubAccount(data_queue)

    public_methods = [
        # 
        "get_sub_account_list",
        "get_sub_account_status",
        "get_sub_account_spot_summary",
        # 
        "sub_transfer_to_main",
        "main_transfer_to_sub",
        "sub_transfer_to_sub",
        "get_sub_transfer_history",
        "get_sub_account_universal_transfer",
        # 
        "get_sub_account_assets",
        "get_sub_account_margin_account",
        "get_sub_account_margin_summary",
        "get_sub_account_futures_account",
        #  API Key 
        "create_sub_api_key",
        "get_sub_api_key",
        "delete_sub_api_key",
        "get_sub_api_ip_restriction",
        "delete_sub_ip_restriction",
    ]

    for method in public_methods:
        assert hasattr(sub_account, method), f"Missing method: {method}"
        assert callable(getattr(sub_account, method)), f"Method not callable: {method}"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
