"""Optional per-position date and identity helpers for Portfolio X-Ray.

A date is a historical ETF *holdings as-of* date. Blank means latest
holdings; dates on direct stocks/cash are kept in shared CSVs and saved
portfolios but do not alter stock look-through or the price-return simulator.
"""
from __future__ import annotations

from datetime import date, datetime

MIN_AS_OF = date(2019, 9, 30)


def normalized_position_date(value) -> str:
    """Return ISO date or blank; reject malformed, future or unsupported dates."""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        day = value
    elif isinstance(value, str):
        try:
            day = date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError("Date must be YYYY-MM-DD.") from exc
    else:
        raise ValueError("Date must be YYYY-MM-DD or blank.")
    if day < MIN_AS_OF or day > date.today():
        raise ValueError(
            f"Date must be between {MIN_AS_OF.isoformat()} and today."
        )
    return day.isoformat()


def position_with_date(ticker: str, amount: float, value=None) -> dict:
    """Canonical position: omit date key entirely when no date was provided."""
    entry = {"ticker": ticker, "amount": float(amount)}
    iso = normalized_position_date(value)
    if iso:
        entry["date"] = iso
    return entry


def position_signature(positions: list[dict]) -> tuple:
    """Keep legacy 2-tuples for undated positions and include dates if present."""
    entries = []
    for position in positions:
        ticker = position["ticker"]
        amount = float(position["amount"])
        iso = normalized_position_date(position.get("date"))
        entries.append((ticker, amount, iso) if iso else (ticker, amount))
    return tuple(entries)


def historical_dates_for_positions(positions: list[dict],
                                   etfs: set[str]) -> dict[str, date]:
    """Dated ETF symbols only; reject contradictory dates for one fund."""
    dates: dict[str, date] = {}
    for p in positions:
        ticker = p["ticker"]
        iso = normalized_position_date(p.get("date"))
        if not iso or ticker not in etfs:
            continue
        day = date.fromisoformat(iso)
        if ticker in dates and dates[ticker] != day:
            raise ValueError(
                f"{ticker} appears with different holdings dates. "
                "Use one as-of date per ETF ticker, or consolidate the rows."
            )
        dates[ticker] = day
    return dates
