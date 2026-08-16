"""
Tests for Binance Wallet API
 Binance  API 
"""

from __future__ import annotations

from bt_api_binance.exchange_data import (
    BinanceExchangeDataGrid,
    BinanceExchangeDataMining,
    BinanceExchangeDataPortfolio,
    BinanceExchangeDataStaking,
    BinanceExchangeDataSubAccount,
    BinanceExchangeDataVipLoan,
    BinanceExchangeDataWallet,
)


def test_binance_wallet_api_init():
    """ Binance Wallet API """
    wallet = BinanceExchangeDataWallet()
    assert wallet.exchange_name == "binance_wallet"
    assert wallet.rest_url == "https://api.binance.com"
    assert wallet.wss_url == "wss://stream.binance.com/ws"


def test_binance_wallet_rest_paths():
    """ Binance Wallet REST """
    wallet = BinanceExchangeDataWallet()

    # 
    assert wallet.get_rest_path("get_wallet_balance") == "GET /sapi/v1/asset/wallet/balance"
    assert wallet.get_rest_path("get_asset_detail") == "GET /sapi/v1/asset/assetDetail"
    assert wallet.get_rest_path("get_asset_ledger") == "GET /sapi/v1/asset/ledger"
    assert wallet.get_rest_path("get_asset_dividend") == "GET /sapi/v1/asset/assetDividend"

    # 
    assert wallet.get_rest_path("asset_transfer") == "POST /sapi/v1/asset/transfer"
    assert wallet.get_rest_path("get_asset_transfer") == "GET /sapi/v1/asset/transfer"
    assert (
        wallet.get_rest_path("transfer_to_futures_main")
        == "POST /sapi/v1/asset/transfer-to-future-main-account"
    )
    assert (
        wallet.get_rest_path("transfer_to_futures_sub")
        == "POST /sapi/v1/asset/transfer-to-future-sub-account"
    )
    assert wallet.get_rest_path("transfer_to_um") == "POST /sapi/v1/asset/transfer-to-UM"
    assert (
        wallet.get_rest_path("transfer_to_isolated_margin")
        == "POST /sapi/v1/asset/transfer-to-isolated-margin"
    )

    # 
    assert wallet.get_rest_path("get_deposit_address") == "GET /sapi/v1/capital/deposit/address"
    assert wallet.get_rest_path("get_deposit_history") == "GET /sapi/v1/capital/deposit/hisrec"

    # 
    assert wallet.get_rest_path("withdraw") == "POST /sapi/v1/capital/withdraw/apply"
    assert wallet.get_rest_path("get_withdraw_history") == "GET /sapi/v1/capital/withdraw/history"
    assert wallet.get_rest_path("get_withdraw_address") == "GET /sapi/v1/capital/withdraw/address"

    # 
    assert wallet.get_rest_path("get_dust") == "GET /sapi/v1/asset/dust"
    assert wallet.get_rest_path("dust_transfer") == "POST /sapi/v1/asset/dust/btc"


def test_binance_wallet_symbol_conversion():
    """ Wallet symbol """
    wallet = BinanceExchangeDataWallet()
    # get_symbol  '-'
    assert wallet.get_symbol("BTC-USDT") == "BTCUSDT"
    assert wallet.get_symbol("ETH-USDT") == "ETHUSDT"
    assert wallet.get_symbol("BTC/USDT") == "BTC/USDT"  # / 


def test_binance_sub_account_api_init():
    """ Binance Sub-account API """
    sub_account = BinanceExchangeDataSubAccount()
    assert sub_account.exchange_name == "binance_sub_account"
    assert sub_account.rest_url == "https://api.binance.com"


def test_binance_sub_account_rest_paths():
    """ Binance Sub-account REST """
    sub_account = BinanceExchangeDataSubAccount()

    # 
    assert sub_account.get_rest_path("get_sub_account_list") == "GET /sapi/v1/sub-account/list"
    assert sub_account.get_rest_path("get_sub_account_status") == "GET /sapi/v1/sub-account/status"
    assert (
        sub_account.get_rest_path("get_sub_account_spot_summary")
        == "GET /sapi/v1/sub-account/spotSummary"
    )

    # 
    assert (
        sub_account.get_rest_path("sub_transfer_to_main")
        == "POST /sapi/v1/sub-account/transfer/sub-to-main"
    )
    assert (
        sub_account.get_rest_path("main_transfer_to_sub")
        == "POST /sapi/v1/sub-account/transfer/main-to-sub"
    )
    assert (
        sub_account.get_rest_path("sub_transfer_to_sub")
        == "POST /sapi/v1/sub-account/transfer/sub-to-sub"
    )
    assert (
        sub_account.get_rest_path("get_sub_transfer_history")
        == "GET /sapi/v1/sub-account/sub-transfer-history"
    )
    assert (
        sub_account.get_rest_path("get_sub_account_universal_transfer")
        == "GET /sapi/v1/sub-account/universal-transfer"
    )

    # 
    assert sub_account.get_rest_path("get_sub_account_assets") == "GET /sapi/v1/sub-account/assets"
    assert (
        sub_account.get_rest_path("get_sub_account_margin_account")
        == "GET /sapi/v1/sub-account/margin/account"
    )
    assert (
        sub_account.get_rest_path("get_sub_account_margin_summary")
        == "GET /sapi/v1/sub-account/margin/accountSummary"
    )
    assert (
        sub_account.get_rest_path("get_sub_account_futures_account")
        == "GET /sapi/v1/sub-account/futuresAccount"
    )

    #  API Key 
    assert sub_account.get_rest_path("create_sub_api_key") == "POST /sapi/v1/sub-account/apiKey"
    assert sub_account.get_rest_path("get_sub_api_key") == "GET /sapi/v1/sub-account/apiKey"
    assert sub_account.get_rest_path("delete_sub_api_key") == "DELETE /sapi/v1/sub-account/apiKey"
    assert (
        sub_account.get_rest_path("get_sub_api_ip_restriction")
        == "GET /sapi/v1/sub-account/apiIpRestriction"
    )
    assert (
        sub_account.get_rest_path("delete_sub_ip_restriction")
        == "DELETE /sapi/v1/sub-account/apiIpRestriction"
    )


def test_binance_portfolio_api_init():
    """ Binance Portfolio Margin API """
    portfolio = BinanceExchangeDataPortfolio()
    assert portfolio.exchange_name == "binance_portfolio"
    assert portfolio.rest_url == "https://api.binance.com"


def test_binance_portfolio_rest_paths():
    """ Binance Portfolio Margin REST """
    portfolio = BinanceExchangeDataPortfolio()

    # 
    assert portfolio.get_rest_path("get_portfolio_account") == "GET /sapi/v1/portfolio/account"
    assert (
        portfolio.get_rest_path("get_portfolio_collateral_rate")
        == "GET /sapi/v1/portfolio/collateralRate"
    )
    assert portfolio.get_rest_path("portfolio_transfer") == "POST /sapi/v1/portfolio/transfer"


def test_binance_grid_api_init():
    """ Binance Grid Trading API """
    grid = BinanceExchangeDataGrid()
    assert grid.exchange_name == "binance_grid"
    assert grid.rest_url == "https://api.binance.com"


def test_binance_grid_rest_paths():
    """ Binance Grid Trading REST """
    grid = BinanceExchangeDataGrid()

    # 
    assert grid.get_rest_path("futures_grid_new_order") == "POST /sapi/v1/futures/fortune/order"
    assert (
        grid.get_rest_path("futures_grid_cancel_order") == "DELETE /sapi/v1/futures/fortune/order"
    )
    assert grid.get_rest_path("get_futures_grid_orders") == "GET /sapi/v1/futures/fortune/order"
    assert (
        grid.get_rest_path("get_futures_grid_position") == "GET /sapi/v1/futures/fortune/position"
    )
    assert grid.get_rest_path("get_futures_grid_income") == "GET /sapi/v1/futures/fortune/income"


def test_binance_staking_api_init():
    """ Binance Staking API """
    staking = BinanceExchangeDataStaking()
    assert staking.exchange_name == "binance_staking"
    assert staking.rest_url == "https://api.binance.com"


def test_binance_staking_rest_paths():
    """ Binance Staking REST """
    staking = BinanceExchangeDataStaking()

    #  Staking 
    assert staking.get_rest_path("get_staking_products") == "GET /sapi/v1/staking/productList"
    assert staking.get_rest_path("staking_purchase") == "POST /sapi/v1/staking/purchase"
    assert staking.get_rest_path("staking_redeem") == "POST /sapi/v1/staking/redeem"
    assert staking.get_rest_path("get_staking_position") == "GET /sapi/v1/staking/position"
    assert staking.get_rest_path("get_staking_history") == "GET /sapi/v1/staking/stakingRecord"


def test_binance_mining_api_init():
    """ Binance Mining API """
    mining = BinanceExchangeDataMining()
    assert mining.exchange_name == "binance_mining"
    assert mining.rest_url == "https://api.binance.com"


def test_binance_mining_rest_paths():
    """ Binance Mining REST """
    mining = BinanceExchangeDataMining()

    # 
    assert mining.get_rest_path("get_mining_algo_list") == "GET /sapi/v1/mining/pub/algoList"
    assert mining.get_rest_path("get_mining_worker_list") == "GET /sapi/v1/mining/worker/list"
    assert (
        mining.get_rest_path("get_mining_statistics")
        == "GET /sapi/v1/mining/statistics/user/status"
    )


def test_binance_vip_loan_api_init():
    """ Binance VIP Loan API """
    vip_loan = BinanceExchangeDataVipLoan()
    assert vip_loan.exchange_name == "binance_vip_loan"
    assert vip_loan.rest_url == "https://api.binance.com"


def test_binance_vip_loan_rest_paths():
    """ Binance VIP Loan REST """
    vip_loan = BinanceExchangeDataVipLoan()

    #  VIP Loan 
    assert (
        vip_loan.get_rest_path("get_vip_loan_ongoing_orders") == "GET /sapi/v1/loan/ongoing/order"
    )
    assert vip_loan.get_rest_path("vip_loan_borrow") == "POST /sapi/v1/loan/borrow"
    assert vip_loan.get_rest_path("vip_loan_repay") == "POST /sapi/v1/loan/repay"
    assert vip_loan.get_rest_path("get_vip_loan_history") == "GET /sapi/v1/loan/loan/history"
    assert (
        vip_loan.get_rest_path("get_vip_repayment_history") == "GET /sapi/v1/loan/repayment/history"
    )


def test_binance_wallet_api_paths_count():
    """ Wallet API """
    wallet = BinanceExchangeDataWallet()
    # 
    assert len(wallet.rest_paths) > 10  # 10
    # 
    key_paths = ["get_wallet_balance", "asset_transfer", "withdraw", "get_deposit_address"]
    for key in key_paths:
        assert key in wallet.rest_paths


def test_binance_sub_account_api_paths_count():
    """ Sub-account API """
    sub_account = BinanceExchangeDataSubAccount()
    assert len(sub_account.rest_paths) > 10
    key_paths = ["get_sub_account_list", "sub_transfer_to_main", "get_sub_account_assets"]
    for key in key_paths:
        assert key in sub_account.rest_paths


def test_all_new_classes_have_legal_currency():
    """ legal_currency """
    classes = [
        BinanceExchangeDataWallet,
        BinanceExchangeDataSubAccount,
        BinanceExchangeDataPortfolio,
        BinanceExchangeDataGrid,
        BinanceExchangeDataStaking,
        BinanceExchangeDataMining,
        BinanceExchangeDataVipLoan,
    ]

    for cls in classes:
        instance = cls()
        assert hasattr(instance, "legal_currency")
        assert len(instance.legal_currency) > 0
        assert "USDT" in instance.legal_currency or "USD" in instance.legal_currency


def test_all_new_classes_have_wss_paths():
    """ wss_paths （）"""
    classes = [
        BinanceExchangeDataWallet,
        BinanceExchangeDataSubAccount,
        BinanceExchangeDataPortfolio,
        BinanceExchangeDataGrid,
        BinanceExchangeDataStaking,
        BinanceExchangeDataMining,
        BinanceExchangeDataVipLoan,
    ]

    for cls in classes:
        instance = cls()
        assert hasattr(instance, "wss_paths")
        assert isinstance(instance.wss_paths, dict)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
