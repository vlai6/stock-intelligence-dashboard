"""Retrieve top equity ETF holdings using the existing yfinance dependency.

No paid API, secrets, account information, or network calls on module import.
The caller adds Streamlit caching. A failed lookup is not represented as fresh data.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import pandas as pd

# Only securities with recognizable stock tickers should be sent to the news UI.
# Yahoo uses BRK-B / BF-B rather than the common BRK.B / BF.B spelling.
STOCK_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,12}$")
EXCLUDED_TICKERS = {"CASH", "USD", "N/A", "NAN", "NONE", "OTHER", "TOTAL", "ETF"}


@dataclass
class ETFHoldings:
    etf: str
    tickers: list[str] = field(default_factory=list)
    weights_pct: dict[str, float] = field(default_factory=dict)
    source: str = ""
    error: str = ""


def normalize_symbol(raw: object) -> str:
    """Clean Yahoo ETF stock symbols, including Berkshire B formatting."""
    value = str(raw or "").strip().upper().replace("/", "-")
    if value in {"BRK.B", "BRK-B"}:
        return "BRK-B"
    if value in {"BF.B", "BF-B"}:
        return "BF-B"
    if not STOCK_TICKER.fullmatch(value) or value in EXCLUDED_TICKERS:
        return ""
    # Holdings sometimes expose 9-character CUSIP identifiers rather than tickers;
    # do not treat these as price-feed symbols.
    if len(value) == 9 and any(ch.isdigit() for ch in value):
        return ""
    return value


def _parse_percent(raw: object) -> float | None:
    """Yahoo 'Holding Percent' is usually a fraction, e.g. 0.077 = 7.7%."""
    if raw is None:
        return None
    try:
        if pd.isna(raw):
            return None
    except (TypeError, ValueError):
        pass
    percentage_text = isinstance(raw, str) and raw.strip().endswith("%")
    try:
        value = float(str(raw).strip().rstrip("%").replace(",", ""))
    except (ValueError, TypeError):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    percentage = value if percentage_text or value > 1 else value * 100
    return percentage if percentage <= 100 else None


def parse_top_holdings(raw: object, etf: str, limit: int = 10) -> ETFHoldings:
    """Normalize fund_data.top_holdings across common yfinance column shapes."""
    result = ETFHoldings(etf=etf.strip().upper(), source="Yahoo Finance (via yfinance)")
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        result.error = "Yahoo Finance did not return a holdings table for this ETF."
        return result
    df = raw.copy()
    column_map = {str(c).strip().casefold(): c for c in df.columns}
    ticker_col = next((column_map[k] for k in (
        "symbol", "ticker", "holding symbol", "holdings symbol") if k in column_map), None)
    weight_col = next((column_map[k] for k in (
        "holding percent", "holding percentage", "% assets", "percent assets", "weight", "weight (%)")
        if k in column_map), None)
    rows: list[tuple[int, str, float | None]] = []
    seen = set()
    for position, (index, record) in enumerate(df.iterrows()):
        symbol = normalize_symbol(record[ticker_col] if ticker_col is not None else index)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        weight = _parse_percent(record[weight_col]) if weight_col is not None else None
        rows.append((position, symbol, weight))
    if weight_col is not None and any(weight is not None for _, _, weight in rows):
        # The provider is expected to rank by holding weight; sort defensively.
        rows.sort(key=lambda record: (record[2] is None, -(record[2] or 0), record[0]))
    for _, symbol, weight in rows[:max(1, min(100, int(limit)))]:
        result.tickers.append(symbol)
        if weight is not None:
            result.weights_pct[symbol] = weight
    if not result.tickers:
        result.error = "No supported stock tickers were found in this ETF's holdings."
    return result


def fetch_etf_holdings(etf: str, limit: int = 10) -> ETFHoldings:
    """Read the provider's top holdings; it does not guarantee ETF-wide coverage."""
    symbol = normalize_symbol(etf)
    if not symbol:
        return ETFHoldings(etf=str(etf), error="Enter a valid ETF ticker, such as SPY, SMH or QQQ.")
    try:
        import yfinance as yf
        table = yf.Ticker(symbol).funds_data.top_holdings
        return parse_top_holdings(table, symbol, limit)
    except Exception as exc:
        # Avoid exposing provider response bodies, user tokens or raw URLs.
        return ETFHoldings(etf=symbol, error=f"ETF holdings unavailable from Yahoo Finance ({type(exc).__name__}).")
