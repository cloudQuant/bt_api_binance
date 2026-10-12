"""Explicit exchange environment selection; never fall back from simulation to live."""
from __future__ import annotations

from copy import copy
from urllib.parse import urlsplit

_ENDPOINTS = {
    ("SPOT", "production"): (
        "api.binance.com",
        "stream.binance.com",
        "ws-api.binance.com",
    ),
    ("SPOT", "testnet"): (
        "testnet.binance.vision",
        "stream.testnet.binance.vision",
        "ws-api.testnet.binance.vision",
    ),
    ("SPOT", "demo"): (
        "demo-api.binance.com",
        "demo-stream.binance.com",
        "demo-ws-api.binance.com",
    ),
    ("SWAP", "production"): (
        "fapi.binance.com",
        "fstream.binance.com",
        "fstream.binance.com",
    ),
    ("SWAP", "demo"): (
        "demo-fapi.binance.com",
        "demo-fstream.binance.com",
        "demo-fstream.binance.com",
    ),
}

_ENDPOINT_PATHS = {
    "SPOT": ("", "/ws", "/ws-api/v3"),
    "SWAP": ("", "/ws", "/ws"),
}


def resolve_environment(options):
    """Resolve explicit environment and legacy boolean aliases, rejecting ambiguity."""
    aliases = []
    for key in ("testnet", "demo", "simulated_trading"):
        if key not in options:
            continue
        value = options[key]
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a boolean; use environment for named environments")
        if value:
            aliases.append("testnet" if key == "testnet" else "demo")
    environment = options.get("environment")
    if environment is not None:
        if not isinstance(environment, str):
            raise ValueError("environment must be production, demo or testnet")
        environment = environment.strip().lower()
    if len(set(aliases)) > 1:
        raise ValueError("Conflicting demo/testnet flags")
    if environment is None:
        environment = aliases[0] if aliases else "production"
    if environment not in {"production", "demo", "testnet"}:
        raise ValueError("environment must be production, demo or testnet")
    if aliases and environment != aliases[0]:
        raise ValueError("environment conflicts with demo/testnet flag")
    return environment


def _same_path(actual, expected):
    if expected == "":
        return actual in {"", "/"}
    return actual == expected


def _override(options, field, default, allowed_hosts=None, expected_path=None):
    url = options.get(field) or default
    parsed = urlsplit(url)
    expected_scheme = "https" if field == "rest_url" else "wss"
    if (
        parsed.scheme != expected_scheme
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.port not in (None, 443)
        or (expected_path is not None and not _same_path(parsed.path, expected_path))
    ):
        raise ValueError(f"Invalid {field}; an authenticated URL is not allowed")
    if allowed_hosts is not None and parsed.hostname not in allowed_hosts:
        raise ValueError(f"{field} conflicts with the selected simulation environment")
    return url.rstrip("/") if expected_path == "" else url


def _matches_endpoint(value, scheme, host, ports, expected_path):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == scheme
            and parsed.hostname == host
            and parsed.port in ports
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and _same_path(parsed.path, expected_path)
        )
    except (TypeError, ValueError):
        return False


def verify_environment(params):
    """Return a safe proof of the currently configured Binance endpoints."""
    result = {"environment": "unknown", "simulated": None, "verified": False}
    try:
        environment = str(params.environment).strip().lower()
        params_name = type(params).__name__
        asset = (
            params_name[len("BinanceExchangeData") :]
            if params_name.startswith("BinanceExchangeData")
            else params_name
        ).upper()
        endpoint_hosts = _ENDPOINTS.get((asset, environment))
        endpoint_paths = _ENDPOINT_PATHS.get(asset)
        if endpoint_hosts is None or endpoint_paths is None:
            return result
        simulated = environment != "production"
        verified = (
            _matches_endpoint(
                params.rest_url, "https", endpoint_hosts[0], {None, 443}, endpoint_paths[0]
            )
            and _matches_endpoint(
                params.wss_url, "wss", endpoint_hosts[1], {None, 443}, endpoint_paths[1]
            )
            and _matches_endpoint(
                params.acct_wss_url,
                "wss",
                endpoint_hosts[2],
                {None, 443},
                endpoint_paths[2],
            )
        )
        return {
            "environment": environment,
            "simulated": simulated,
            "verified": bool(verified),
        }
    except Exception:
        return result


def configure_environment(params, options):
    """Configure Spot Testnet, Spot Demo or USD-M Demo REST and WS together.

    References: https://testnet.binance.vision/ and
    https://github.com/binance/binance-spot-api-docs/blob/master/demo-mode/general-info.md
    https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/general-info
    """
    params = copy(params)
    environment = resolve_environment(options)
    params_name = type(params).__name__
    asset = (
        params_name[len("BinanceExchangeData") :]
        if params_name.startswith("BinanceExchangeData")
        else params_name
    ).upper()
    # SPOT/SWAP 有专门的模拟环境端点；其余资产类型（WALLET/MARGIN/…）只存在于生产环境，
    # 其 rest/ws 端点来自配置，不做模拟改写——但仍要对 URL 做安全校验（见 _override）。
    # 历史实现对任何非 SPOT/SWAP 资产一律抛错，导致生产环境下这些资产的请求无法构造。
    endpoint_paths = _ENDPOINT_PATHS.get(asset)
    if endpoint_paths is None and environment != "production":
        raise ValueError(f"Binance simulation is unsupported for asset type {asset}")
    params.environment = environment
    endpoints = None
    if environment != "production":
        if asset == "SPOT":
            if environment == "testnet":
                endpoints = ("https://testnet.binance.vision",
                             "wss://stream.testnet.binance.vision/ws",
                             "wss://ws-api.testnet.binance.vision/ws-api/v3")
            else:
                endpoints = ("https://demo-api.binance.com",
                             "wss://demo-stream.binance.com/ws",
                             "wss://demo-ws-api.binance.com/ws-api/v3")
        elif asset == "SWAP":
            params.environment = "demo"
            endpoints = ("https://demo-fapi.binance.com",
                         "wss://demo-fstream.binance.com/ws",
                         "wss://demo-fstream.binance.com/ws")
        else:
            raise ValueError(f"Binance simulation is unsupported for asset type {asset}")
    for index, field in enumerate(("rest_url", "wss_url", "acct_wss_url")):
        default = endpoints[index] if endpoints else getattr(params, field)
        if not default:
            # 该资产类型没有配置这个端点（例如钱包没有私有 WS）：无可校验或改写的内容
            continue
        expected_path = endpoint_paths[index] if endpoint_paths else urlsplit(default).path
        allowed = {urlsplit(default).hostname}
        setattr(
            params,
            field,
            _override(options, field, default, allowed, expected_path),
        )
    return params
