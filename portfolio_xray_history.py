"""Buy-and-hold historical simulation for Portfolio X-Ray input holdings.

Weights are the user's original ETF/stock allocations, not the X-Ray's
constituent look-through. Adjusted prices include distributions and splits.
No silent redistribution of securities with missing history or bond CUSIPs.
"""
from __future__ import annotations

from datetime import date, timedelta
import math
import re

import pandas as pd
import yfinance as yf


class HistoricalCoverageError(ValueError):
    """A full-portfolio comparison would misrepresent unsupported holdings."""


def portfolio_weights(positions: list[dict]) -> dict[str, float]:
    """Combine duplicate input symbols and normalize their original amounts."""
    weights: dict[str, float] = {}
    for position in positions:
        ticker = str(position["ticker"]).strip()
        amount = float(position["amount"])
        if not ticker or not math.isfinite(amount) or amount <= 0:
            raise ValueError("Portfolio contains an invalid holding or amount.")
        weights[ticker] = weights.get(ticker, 0.0) + amount
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Portfolio has no positive allocation.")
    return {ticker: amount / total for ticker, amount in weights.items()}


def unsupported_assets(weights: dict[str, float]) -> dict[str, float]:
    """Direct fixed-income CUSIPs lack reliable adjusted Yahoo series."""
    return {
        ticker: weight
        for ticker, weight in weights.items()
        if re.fullmatch(r"[0-9][A-Z0-9]{8}", ticker)
    }


def adjusted_history(tickers: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    """Fetch dividend/split-adjusted daily closes; no intraday trade prices."""
    symbols = list(dict.fromkeys(tickers))
    if not symbols:
        return pd.DataFrame()
    # end is exclusive in yfinance; return an ordinary data-date-index matrix.
    frame = yf.download(
        tickers=symbols,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=False,
    )
    if frame is None or frame.empty:
        return pd.DataFrame()
    cols = {}
    for ticker in symbols:
        try:
            if isinstance(frame.columns, pd.MultiIndex):
                if ticker in frame.columns.get_level_values(0):
                    col = frame[ticker]["Close"]
                elif ticker in frame.columns.get_level_values(1):
                    col = frame["Close"][ticker]
                else:
                    continue
            else:
                if len(symbols) != 1:
                    continue
                col = frame["Close"]
            series = pd.to_numeric(col, errors="coerce")
            series = series[series.gt(0) & series.map(math.isfinite)]
            if not series.empty:
                cols[ticker] = series
        except (KeyError, TypeError, ValueError):
            continue
    if not cols:
        return pd.DataFrame()
    result = pd.DataFrame(cols)
    idx = pd.DatetimeIndex(result.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    result.index = idx.normalize()
    return result.loc[~result.index.duplicated(keep="last")].sort_index()


def simulate_returns(
    positions: list[dict],
    start: date,
    through: date,
    prices: pd.DataFrame,
) -> dict:
    """Historical *hypothetical* buy-and-hold against dividend-adjusted SPY.

    Require valid data for ALL non-cash holdings before reporting portfolio
    return. No excluding, backfilling, or renormalizing missing holdings.
    """
    if start >= through:
        raise ValueError("Start date must be before the latest market date.")
    weights = portfolio_weights(positions)
    unsupported = unsupported_assets(weights)
    if unsupported:
        names = ", ".join(sorted(unsupported))
        exposure = sum(unsupported.values()) * 100
        raise HistoricalCoverageError(
            f"Cannot calculate a full-portfolio return: direct bond/CUSIP "
            f"positions ({names}) represent {exposure:.2f}% of your allocation. "
            "Historical prices and coupon cash flows are unavailable; "
            "the tool will not silently exclude or assume a return for them."
        )
    symbols = [t for t in weights if t != "Cash & Cash Inv"]
    required = sorted(set(symbols) | {"SPY"})
    if prices is None or prices.empty:
        raise HistoricalCoverageError("No historical price data was returned.")
    missing = [t for t in required if t not in prices.columns or prices[t].dropna().empty]
    if missing:
        raise HistoricalCoverageError(
            "Missing adjusted price history for: " + ", ".join(missing)
            + ". No full-portfolio return was calculated."
        )
    actual = prices.loc[
        (prices.index >= pd.Timestamp(start)) &
        (prices.index <= pd.Timestamp(through)),
        required,
    ].copy()
    # Intersect actual recorded dates, not earlier IPO prices or forward-filled
    # blank values. Individual tickers can be missing on isolated sessions.
    actual = actual.dropna(how="any")
    if len(actual) < 2:
        raise HistoricalCoverageError("Not enough common trading dates for every position and SPY.")
    first, last = actual.index[0], actual.index[-1]
    if first.date() > start + timedelta(days=7):
        raise HistoricalCoverageError(
            f"Complete price history only begins {first.date().isoformat()}, "
            f"after the selected {start.isoformat()} date. Choose a later date."
        )
    if last.date() < through - timedelta(days=7):
        raise HistoricalCoverageError(
            "Some holdings are missing recent prices. No potentially stale "
            "portfolio return will be shown."
        )
    base = actual.iloc[0]
    normalized = actual.div(base)
    # Values represent holding initial shares constant and reinvesting
    # distributions (through auto_adjust). No periodic rebalancing.
    cash_weight = weights.get("Cash & Cash Inv", 0.0)
    portfolio_growth = pd.Series(cash_weight, index=actual.index, dtype=float)
    for ticker, weight in weights.items():
        if ticker != "Cash & Cash Inv":
            portfolio_growth = portfolio_growth + normalized[ticker] * weight
    spy_growth = normalized["SPY"]
    out = pd.DataFrame({
        "Date": actual.index,
        "Portfolio": (portfolio_growth * 100).to_numpy(),
        "SPY": (spy_growth * 100).to_numpy(),
    })
    port_return = float(portfolio_growth.iloc[-1] - 1) * 100
    spy_return = float(spy_growth.iloc[-1] - 1) * 100
    breakdown = [
        {
            "Ticker": t,
            "Starting weight %": round(w * 100, 3),
            "Holding return %": (
                0.0 if t == "Cash & Cash Inv"
                else round(float(normalized[t].iloc[-1] - 1) * 100, 3)
            ),
            "Contribution (pp)": round(
                w * (0 if t == "Cash & Cash Inv" else float(normalized[t].iloc[-1] - 1))
                * 100, 3
            ),
        }
        for t, w in weights.items()
    ]
    return {
        "portfolio_pct": port_return,
        "spy_pct": spy_return,
        "excess_pp": port_return - spy_return,
        "start": first.date(),
        "end": last.date(),
        "chart": out,
        "contributions": pd.DataFrame(breakdown).sort_values(
            "Contribution (pp)", ascending=False
        ),
        "cash_pct": cash_weight * 100,
    }
