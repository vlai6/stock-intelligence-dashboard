"""Purchase-dated, cash-flow-adjusted historical portfolio performance.

CSV Amount is USD newly invested at a historical close, NEVER a current weight.
This buy-only approximation assumes fractional shares and dividend reinvestment.
It deliberately rejects unmodelled sales, cash, CUSIPs and absent price history.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
import io
import math
import re

import pandas as pd

from portfolio_xray import ticker_of
from portfolio_xray_history import HistoricalCoverageError


MAX_BYTES = 256_000
MAX_ROWS = 500
MAX_PORTFOLIOS = 5
EARLIEST = date(2000, 1, 1)


def parse_purchase_csv(payload: bytes) -> dict[str, list[dict]]:
    """Parse Date,Ticker,Amount or Portfolio,Date,Ticker,Amount.

    All amounts are positive *USD purchases*, not percentages or valuations.
    """
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("Upload a nonempty purchase-history CSV.")
    if len(payload) > MAX_BYTES:
        raise ValueError("Purchase CSV exceeds the 256 KB limit.")
    try:
        raw = payload.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(raw, newline=""), strict=True)
        if reader.fieldnames is None:
            raise ValueError("CSV must have Date,Ticker,Amount columns.")
        headers = [h.strip() for h in reader.fieldnames]
        keys = [h.lower() for h in headers]
        if len(keys) != len(set(keys)) or set(keys) not in (
            {"date", "ticker", "amount"},
            {"portfolio", "date", "ticker", "amount"},
        ):
            raise ValueError(
                "Use Date,Ticker,Amount (one portfolio), or "
                "Portfolio,Date,Ticker,Amount (up to five portfolios)."
            )
        groups: dict[str, list[dict]] = {}
        for row_number, raw_row in enumerate(reader, 2):
            if row_number > MAX_ROWS + 1:
                raise ValueError("CSV exceeds 500 purchase records.")
            if None in raw_row:
                raise ValueError(f"Row {row_number}: unexpected extra columns.")
            if not raw_row or all(not (v or "").strip() for v in raw_row.values()):
                continue
            row = {key.lower().strip(): (value or "").strip()
                   for key, value in raw_row.items()}
            name = row.get("portfolio", "Uploaded Portfolio").strip()
            if not name or len(name) > 40:
                raise ValueError(f"Row {row_number}: invalid portfolio name.")
            try:
                bought = date.fromisoformat(row["date"])
            except ValueError as exc:
                raise ValueError(
                    f"Row {row_number}: Date must be YYYY-MM-DD."
                ) from exc
            if bought < EARLIEST or bought > date.today():
                raise ValueError(
                    f"Row {row_number}: purchase date must be between "
                    f"{EARLIEST} and today."
                )
            try:
                ticker = ticker_of(row["ticker"])
            except ValueError as exc:
                raise ValueError(f"Row {row_number}: invalid ticker.") from exc
            if ticker == "Cash & Cash Inv" or re.fullmatch(r"[0-9][A-Z0-9]{8}", ticker):
                raise ValueError(
                    f"Row {row_number}: {ticker} is not a supported traded "
                    "stock/ETF. Bond coupons and cash cannot be approximated."
                )
            amt = row["amount"].replace("$", "").replace(",", "")
            if not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", amt):
                raise ValueError(
                    f"Row {row_number}: Amount must be a positive dollar purchase, "
                    "not a percentage, a negative sale or a current holding weight."
                )
            amount = float(amt)
            if not math.isfinite(amount) or amount <= 0 or amount > 1e12:
                raise ValueError(f"Row {row_number}: invalid purchase amount.")
            groups.setdefault(name, []).append({
                "date": bought, "ticker": ticker, "amount": amount,
            })
            if len(groups) > MAX_PORTFOLIOS:
                raise ValueError("Upload up to five portfolios per comparison.")
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("Upload a valid UTF-8 purchase-history CSV.") from exc
    if not groups:
        raise ValueError("The CSV does not contain any valid purchase records.")
    return groups


def _day_prices(prices: pd.DataFrame, through: date) -> pd.DataFrame:
    if prices is None or prices.empty or "SPY" not in prices.columns:
        raise HistoricalCoverageError("SPY adjusted-price history is unavailable.")
    data = prices.copy()
    data.index = pd.DatetimeIndex(data.index).tz_localize(None).normalize()
    data = data.loc[~data.index.duplicated(keep="last")].sort_index()
    data = data.loc[data.index <= pd.Timestamp(through)].apply(
        pd.to_numeric, errors="coerce"
    )
    data = data.loc[data["SPY"].gt(0) & data["SPY"].map(math.isfinite)]
    if len(data) < 2:
        raise HistoricalCoverageError("At least two price sessions are required.")
    if data.index[-1].date() < through - timedelta(days=7):
        raise HistoricalCoverageError(
            "SPY has stale historical prices; no return is reported."
        )
    return data


def _execute_day(bought: date, data: pd.DataFrame, ticker: str) -> pd.Timestamp:
    eligible = data.index[data.index >= pd.Timestamp(bought)]
    if len(eligible) == 0 or eligible[0].date() > bought + timedelta(days=5):
        raise HistoricalCoverageError(
            f"{ticker}: no trading session within five days of {bought}."
        )
    day = eligible[0]
    if ticker not in data.columns:
        raise HistoricalCoverageError(f"No adjusted price history for {ticker}.")
    p = data.at[day, ticker]
    if pd.isna(p) or not math.isfinite(float(p)) or float(p) <= 0:
        raise HistoricalCoverageError(
            f"{ticker}: no valid price on purchase session {day.date()}. "
            "Purchase was not shifted to a later IPO or quote."
        )
    return day


def _one_portfolio(
    name: str, transactions: list[dict], data: pd.DataFrame
) -> dict:
    orders: dict[pd.Timestamp, list[dict]] = {}
    for order in transactions:
        day = _execute_day(order["date"], data, order["ticker"])
        orders.setdefault(day, []).append(order)
    first = min(orders)
    calendar = data.loc[data.index >= first]
    shares = {t["ticker"]: 0.0 for t in transactions}
    spy_shares = 0.0
    prev_value = 0.0
    prev_spy = 0.0
    growth = 100.0
    spy_growth = 100.0
    invested = 0.0
    rows = []
    for day, bar in calendar.iterrows():
        # Never substitute a stale price for an active holding.
        current = 0.0
        for ticker, quantity in shares.items():
            if quantity == 0:
                continue
            p = bar.get(ticker, float("nan"))
            if pd.isna(p) or not math.isfinite(float(p)) or p <= 0:
                raise HistoricalCoverageError(
                    f"{name}: missing {ticker} price on {day.date()} "
                    "while the portfolio holds it."
                )
            current += quantity * float(p)
        spy_before = spy_shares * float(bar["SPY"])
        if prev_value:
            growth *= current / prev_value
            spy_growth *= spy_before / prev_spy
        cash_in = 0.0
        for order in orders.get(day, []):
            p = float(bar[order["ticker"]])
            shares[order["ticker"]] += order["amount"] / p
            cash_in += order["amount"]
        invested += cash_in
        spy_shares += cash_in / float(bar["SPY"])
        prev_value = current + cash_in
        prev_spy = spy_before + cash_in
        rows.append({
            "Date": day, "Portfolio": growth, "SPY": spy_growth,
            "Value": prev_value, "SPY Value": prev_spy,
        })
    series = pd.DataFrame(rows).set_index("Date")
    return {
        "name": name, "series": series, "start": first.date(),
        "end": calendar.index[-1].date(), "invested": invested,
        "ending_value": prev_value, "net_profit": prev_value - invested,
        "spy_ending_value": prev_spy, "spy_profit": prev_spy - invested,
        "since_inception_return_pct": growth - 100.0,
        "spy_since_inception_pct": spy_growth - 100.0,
        "purchase_count": len(transactions),
    }


def simulate_purchase_history(
    portfolios: dict[str, list[dict]], prices: pd.DataFrame, through: date
) -> dict:
    """Time-weight daily returns, excluding same-day external contributions.

    For comparisons, rebase each strategy to 100 on the SAME first shared
    trading session. SPY is funded on each portfolio's identical buy dates.
    USD profit and invested figures describe the entire contribution history.
    """
    if not portfolios or len(portfolios) > MAX_PORTFOLIOS:
        raise ValueError("Provide between one and five purchase portfolios.")
    data = _day_prices(prices, through)
    outcomes = {
        name: _one_portfolio(name, records, data)
        for name, records in portfolios.items()
    }
    common_start = max(v["start"] for v in outcomes.values())
    common = data.loc[data.index >= pd.Timestamp(common_start)]
    if len(common) < 2:
        raise HistoricalCoverageError(
            "Not enough common sessions after the latest portfolio began."
        )
    chart = pd.DataFrame({"Date": common.index})
    spy_base = float(data.at[common.index[0], "SPY"])
    chart["SPY"] = 100 * data.loc[common.index, "SPY"].to_numpy() / spy_base
    summary, series = [], []
    for index, (name, outcome) in enumerate(outcomes.items()):
        history = outcome["series"].loc[common.index]
        base = float(history["Portfolio"].iloc[0])
        if base <= 0:
            raise HistoricalCoverageError(
                f"{name}: invalid portfolio value at comparison start."
            )
        key = f"portfolio_{index}"
        chart[key] = 100 * history["Portfolio"].to_numpy() / base
        pct = float(chart[key].iloc[-1] - 100.0)
        spy_pct = float(chart["SPY"].iloc[-1] - 100.0)
        series.append({"key": key, "name": name})
        summary.append({
            "Portfolio": name,
            "Common-period return %": pct,
            "SPY return %": spy_pct,
            "Excess return (pp)": pct - spy_pct,
            "Total invested ($)": outcome["invested"],
            "Ending value ($)": outcome["ending_value"],
            "Profit ($)": outcome["net_profit"],
            "SPY profit ($)": outcome["spy_profit"],
        })
    return {
        "chart": chart, "summary": pd.DataFrame(summary),
        "series": series, "outcomes": outcomes,
        "start": common.index[0].date(), "end": common.index[-1].date(),
        "spy_pct": float(chart["SPY"].iloc[-1] - 100.0),
    }
