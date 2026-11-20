"""Readable scanner skip explanations while retaining stable diagnostic reason codes.

Pure Python (no Streamlit); can also be imported by the command-line scanner.
"""
from __future__ import annotations

from datetime import date
import re


def _format_date(value: str) -> str:
    try:
        dt = date.fromisoformat(value)
        return dt.strftime("%b %d, %Y")
    except (TypeError, ValueError):
        return str(value)


def describe_skipped_reason(code: object, expected_session: object = None) -> str:
    """Explain why a stock was omitted without changing the underlying rule.

    The original machine-readable `reason` is deliberately preserved for audit,
    scheduled workflows, and any existing consumers of skipped.csv.
    """
    reason = str(code or "").strip()
    expected = str(expected_session or "").strip()
    expected_note = (f" The scan expected a closing price for {_format_date(expected)}."
                     if re.fullmatch(r"\d{4}-\d{2}-\d{2}", expected) else "")

    if reason.startswith("stale_latest_"):
        actual = reason.removeprefix("stale_latest_")
        return (f"Latest available daily close was {_format_date(actual)}."
                + expected_note
                + " The price feed has not supplied the expected session; retry after the data updates."
                + " This stock was excluded, not assigned an estimated price.")
    if reason == "missing_prices":
        return ("No usable historical closing prices were returned for this ticker. "
                "The data feed may be temporarily unavailable, rate-limited, or missing this listing. "
                "Retry later and verify the ticker's exchange.")
    if reason == "invalid_price_data":
        return ("The downloaded closing-price series failed the regression's numeric validation. "
                "The stock was excluded rather than calculating an unreliable Z-score.")
    if reason.startswith("insufficient_history_"):
        available = reason.removeprefix("insufficient_history_")
        count = f"Only {available} daily closing observations were available" if available.isdigit() else "Not enough daily closing observations were available"
        return count + "; fewer than the selected regression lookback requires. This is an eligibility exclusion, not a failed download."
    if reason == "trend_or_band_filter":
        return ("Price data was analyzed successfully, but the stock did not meet the strategy's "
                "positive-trend and lower-band eligibility rules. This is not a data error.")
    if reason.startswith("batch_skipped_"):
        kind = reason.removeprefix("batch_skipped_").replace("_", " ")
        kind_note = f" ({kind})" if kind else ""
        return ("The stock's price-download batch failed" + kind_note +
                ". The scan skipped the batch instead of using incomplete data; rerun when the data service recovers.")
    if reason:
        return f"Stock was skipped; the scanner reported: {reason.replace('_', ' ')}. Review downloaded prices and retry if needed."
    return "No diagnostic reason was recorded for this stock."


def skip_reason_status(code: object) -> str:
    reason = str(code or "")
    if reason == 'trend_or_band_filter':
        return 'Does not meet strategy'
    if reason.startswith('insufficient_history_'):
        return 'Insufficient history'
    if reason.startswith(('stale_latest_', 'batch_skipped_')) or reason in ('missing_prices', 'invalid_price_data'):
        return 'Data unavailable'
    return 'Other'
