"""Binance-specific credential field and environment declarations."""

from bt_api_base.execution_configuration_policy import ExecutionConfigurationPolicy


def execution_configuration_policy(exchange_name: str) -> ExecutionConfigurationPolicy:
    return ExecutionConfigurationPolicy(
        credential_aliases=(
            ("public", ("public_key", "api_key")),
            ("secret", ("private_key", "secret_key", "api_secret")),
        ),
        require_environment=True,
    )
