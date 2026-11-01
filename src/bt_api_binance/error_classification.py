"""BINANCE native error-code classifications."""

_DEFINITE_REJECT_CODES = frozenset(
    {
        "-1002",  # unauthorized request
        "-1013",  # invalid request message
        "-1014",  # unsupported order composition
        "-1015",  # too many new orders
        "-1021",  # timestamp outside recvWindow
        "-1022",  # invalid signature
        "-1099",  # unauthenticated or unauthorized
        "-1100",  # illegal parameter characters
        "-1101",  # too many parameters
        "-1102",  # mandatory parameter missing or malformed
        "-1103",  # unknown parameter
        "-1104",  # unread parameters
        "-1105",  # empty parameter
        "-1106",  # parameter not required
        "-1108",  # invalid asset
        "-1109",  # invalid account
        "-1110",  # invalid instrument type
        "-1111",  # invalid precision
        "-1114",  # time-in-force not required
        "-1115",  # invalid time-in-force
        "-1116",  # invalid order type
        "-1117",  # invalid side
        "-1118",  # empty new client order id
        "-1119",  # empty original client order id
        "-1121",  # invalid symbol
        "-1122",  # invalid symbol status
        "-1128",  # invalid optional parameter combination
        "-1130",  # invalid parameter
        "-1136",  # invalid new-order response type
        "-2010",  # new order rejected
        "-2011",  # cancellation rejected
        "-2013",  # order does not exist
        "-2014",  # invalid API-key format
        "-2015",  # invalid API key, IP, or permission
        "-2018",  # insufficient balance
        "-2019",  # insufficient margin
        "-2021",  # order would immediately trigger
        "-2022",  # reduce-only order rejected
        "-2024",  # insufficient position
        "-2025",  # maximum open orders exceeded
        "-2026",  # unsupported reduce-only order type
        "-2027",  # maximum leverage exceeded
        "-4001",  # price below zero
        "-4002",  # price above maximum
        "-4003",  # quantity below zero
        "-4004",  # quantity below minimum
        "-4005",  # quantity above maximum
        "-4013",  # price below minimum
        "-4014",  # invalid tick-size increment
        "-4015",  # invalid client order id
        "-4016",  # price above multiplier cap
        "-4023",  # invalid step-size increment
        "-4024",  # price below multiplier floor
        "-4060",  # invalid position side
        "-4061",  # position side does not match account mode
        "-4062",  # reduce-only conflict
        "-4118",  # reduce-only margin check failed
        "-4131",  # market order rejected by price filter
        "-4135",  # invalid activation price
        "-4137",  # quantity invalid with closePosition
        "-4138",  # reduceOnly required with closePosition
        "-4139",  # unsupported market order
        "-4140",  # invalid opening-position status
        "-4141",  # symbol closed
        "-4142",  # strategy trigger price rejected
        "-4164",  # minimum notional not met
        "-4189",  # account restricted to reduce-only orders
        "-4192",  # trading forbidden during cooling-off period
    }
)
_AUTH_ENVIRONMENT_MISMATCH_CODES = frozenset(["-2015"])
_PARAMETER_ERROR_CODES = frozenset([])


def classify_error(code):
    """Return category, environment mismatch, and definite-reject facts."""
    rejected = code in _DEFINITE_REJECT_CODES
    if code in _AUTH_ENVIRONMENT_MISMATCH_CODES:
        return "auth", True, rejected
    if code in _PARAMETER_ERROR_CODES:
        return "parameter", False, rejected
    return None, False, rejected
