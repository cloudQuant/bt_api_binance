"""Binance funding symbol selection and exchange-evidenced schedule completion.

SDK-supplied neutral projection callbacks own typed snapshots and errors.
"""

from __future__ import annotations

from copy import deepcopy


def _funding_symbol_key(value):
    """Match Binance native symbols to the SDK's optional dashed spelling."""
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def _matching_funding_rows(source, symbol):
    target = _funding_symbol_key(symbol)
    if not target:
        return []
    matched = []
    for row in source:
        identities = [
            _funding_symbol_key(row.get(field))
            for field in (
                "symbol",
                "symbol_name",
                "funding_rate_symbol_name",
            )
            if row.get(field) not in (None, "")
        ]
        if identities and all(identity == target for identity in identities):
            matched.append(row)
    return matched


def select_funding_payload(native, exchange_name, symbol, *, rows):
    """Select exactly one matching Binance native premium row."""
    native_rows = rows(native, "get_funding_snapshot", exchange_name=exchange_name)
    matches = _matching_funding_rows(native_rows, symbol)
    if len(matches) != 1:
        raise ValueError("funding_payload_invalid")
    return matches[0]


def complete_funding_schedule(
    exchange_name,
    symbol,
    premium_native,
    incomplete,
    extra_data,
    *,
    get_feed,
    rows,
    funding_snapshot,
    seconds,
    unavailable_snapshot,
    capability_error_type,
    normalized_error_type,
):
    """Complete Binance's premium-index row from exchange-evidenced schedule data.

    ``fundingInfo`` contains only symbols whose schedule or caps were
    adjusted. For an unlisted symbol, the most recent public funding
    settlement and ``nextFundingTime`` provide an evidenced interval. No
    default Binance interval is assumed.
    """

    try:
        premium_rows = rows(
            premium_native,
            "get_funding_snapshot",
            exchange_name=exchange_name,
        )
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError):
        return unavailable_snapshot(
            exchange_name,
            symbol,
            "funding_payload_invalid",
        )
    matched_premium = _matching_funding_rows(premium_rows, symbol)
    if len(matched_premium) != 1:
        return unavailable_snapshot(
            exchange_name,
            symbol,
            "funding_payload_invalid",
        )
    premium_row = matched_premium[0]
    incomplete = funding_snapshot(premium_row, exchange_name, symbol)
    if incomplete.available or incomplete.unavailable_reason != "funding_interval_missing":
        return incomplete
    feed = get_feed(exchange_name)
    transport_failed = False
    payload_invalid = False

    funding_info = getattr(feed, "get_funding_info", None)
    if callable(funding_info):
        try:
            info_native = funding_info(extra_data=deepcopy(extra_data))
        except (capability_error_type, NotImplementedError):
            pass
        except Exception:
            transport_failed = True
        else:
            try:
                info_rows = rows(
                    info_native,
                    "get_funding_info",
                    exchange_name=exchange_name,
                )
            except normalized_error_type:
                transport_failed = True
            except (AttributeError, KeyError, OverflowError, TypeError, ValueError):
                payload_invalid = True
            else:
                matched = _matching_funding_rows(info_rows, symbol)
                if len(matched) > 1:
                    return unavailable_snapshot(
                        exchange_name,
                        symbol,
                        "funding_payload_invalid",
                    )
                if matched:
                    merged = {
                        **premium_row,
                        "fundingIntervalHours": matched[0].get("fundingIntervalHours"),
                    }
                    return funding_snapshot(merged, exchange_name, symbol)

    history = getattr(feed, "get_history_funding_rate", None)
    if callable(history):
        try:
            history_native = history(
                symbol,
                count=2,
                extra_data=deepcopy(extra_data),
            )
        except (capability_error_type, NotImplementedError):
            pass
        except Exception:
            transport_failed = True
        else:
            try:
                history_rows = rows(
                    history_native,
                    "get_history_funding_rate",
                    exchange_name=exchange_name,
                )
            except normalized_error_type:
                transport_failed = True
            except (AttributeError, KeyError, OverflowError, TypeError, ValueError):
                payload_invalid = True
            else:
                matched = _matching_funding_rows(history_rows, symbol)
                settlements = []
                next_epoch = incomplete.next_funding_time.timestamp()
                for row in matched:
                    funding_time = row.get("fundingTime", row.get("current_funding_time"))
                    try:
                        funding_epoch = seconds(funding_time)
                    except (OverflowError, TypeError, ValueError):
                        payload_invalid = True
                        continue
                    if funding_epoch is not None and 0 < funding_epoch < next_epoch:
                        settlements.append((funding_epoch, funding_time))
                if settlements:
                    _, latest_funding_time = max(settlements, key=lambda item: item[0])
                    merged = {
                        **premium_row,
                        "fundingTime": latest_funding_time,
                    }
                    return funding_snapshot(merged, exchange_name, symbol)
                if matched:
                    payload_invalid = True

    if payload_invalid:
        return unavailable_snapshot(
            exchange_name,
            symbol,
            "funding_payload_invalid",
        )
    if transport_failed:
        return unavailable_snapshot(
            exchange_name,
            symbol,
            "funding_transport_failed",
        )
    return incomplete


__all__ = ("complete_funding_schedule", "select_funding_payload")
