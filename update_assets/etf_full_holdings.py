"""Fetch published ETF equity constituents without a manual holdings CSV.

Priority: TickerInside's dated public issuer/SEC holdings snapshot (full published
positions). Fallback: Yahoo Finance TOP holdings only, explicitly marked partial.

TickerInside current snapshot is CC BY 4.0; show attribution in UI.
This is an independent external data service. Nothing is downloaded at import.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Any

import requests

from etf_holdings import fetch_etf_holdings, normalize_symbol

BASE_URL = "https://tickerinside.com/api/v1/fund/"
USER_AGENT = "StockIntelligenceDashboard/1.0 (interactive ETF holdings research)"


@dataclass(frozen=True)
class Constituents:
    ticker: str
    symbols: tuple[str, ...]
    source: str
    holdings_as_of: str = ""
    complete_holdings_source: bool = False
    listed_pct: float | None = None
    attribution: str = ""
    error: str = ""


def parse_full_holdings(payload: Any, etf: str) -> Constituents:
    """Return every valid distinct ticker in weight order; do not silently cap at 10."""
    if not isinstance(payload, dict):
        raise ValueError("ETF holdings API returned an invalid response")
    holdings = payload.get("holdings")
    if not isinstance(holdings, dict) or not holdings:
        raise ValueError("No listed equity holdings are available for this ETF")
    selected: dict[str, float] = {}
    for raw, weight in holdings.items():
        # Stock-type symbols only; exclude asset names used for bond/cash buckets.
        symbol = normalize_symbol(raw)
        if not symbol:
            continue
        try:
            w = float(weight)
        except (ValueError, TypeError):
            continue
        if not math.isfinite(w) or w <= 0:
            continue
        selected[symbol] = selected.get(symbol, 0) + w
    if not selected:
        raise ValueError("No stock tickers with holdings weights were returned")
    sorted_symbols = tuple(sorted(selected, key=lambda x: (-selected[x], x)))
    date = str(payload.get("holdings_as_of") or payload.get("report_date") or "")[:24]
    layer = str(payload.get("source_layer") or "issuer / SEC filing")[:50]
    listed = payload.get("listed_pct")
    try:
        listed = float(listed) if listed is not None else None
    except (TypeError, ValueError):
        listed = None
    cite = str(payload.get("cite_as") or "")[:700]
    source = "TickerInside public ETF holdings (" + layer + ")"
    return Constituents(etf, sorted_symbols, source, date, True, listed, cite)


def get_etf_constituents(etf: str, *, request_get: Callable | None = None) -> Constituents:
    ticker = normalize_symbol(etf)
    if not ticker:
        return Constituents(str(etf), (), "", error="Invalid ETF ticker")
    getter = request_get or requests.get
    url = BASE_URL + ticker.lower() + ".json"
    error = ""
    try:
        response = getter(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=24)
        response.raise_for_status()
        return parse_full_holdings(response.json(), ticker)
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        error = type(exc).__name__

    # Fallback has intrinsically limited coverage. The UI must disclose it.
    fallback = fetch_etf_holdings(ticker, limit=100)
    if fallback.tickers:
        return Constituents(ticker, tuple(fallback.tickers),
                            "Yahoo Finance top holdings — PARTIAL, not the entire fund",
                            complete_holdings_source=False,
                            attribution="TickerInside unavailable (" + error + "); top-holdings fallback")
    return Constituents(ticker, (), "", error=(
        "Unable to retrieve full holdings from TickerInside or top holdings from Yahoo Finance. "
        + (fallback.error or error)
    ))
