"""Deterministic regression tests for dated-buy portfolio returns."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for file in (
    "portfolio_xray_purchase_history.py",
    "portfolio_xray_purchase_ui.py",
    "portfolio_xray_history_ui.py",
):
    ast.parse((ROOT / file).read_text(encoding="utf-8"), filename=file)

from portfolio_xray_purchase_history import (
    parse_purchase_csv, simulate_purchase_history,
)
from portfolio_xray_history import HistoricalCoverageError


one = parse_purchase_csv(
    b"Date,Ticker,Amount\n2025-01-02,SPY,100\n2025-01-03,NVDA,40\n"
)
assert list(one) == ["Uploaded Portfolio"]
assert one["Uploaded Portfolio"][0] == {
    "date": date(2025, 1, 2), "ticker": "SPY", "amount": 100,
}
assert one["Uploaded Portfolio"][1]["amount"] == 40

two = parse_purchase_csv(
    b"Portfolio,Date,Ticker,Amount\n"
    b"A,2025-01-02,SPY,100\n"
    b"A,2025-01-03,NVDA,40\n"
    b"B,2025-01-03,SPY,140\n"
)
assert len(two) == 2

for malformed in (
    b"Date,Ticker,Amount\n2025-01-02,SPY,25%\n",
    b"Date,Ticker,Amount\n2025-01-02,SPY,-100\n",
    b"Date,Ticker,Amount\n2025-01-02,SPY,0\n",
    b"Date,Ticker,Amount\n,SPY,100\n",
    b"Date,Ticker,Amount\n2025-01-02,91282CMB4,100\n",
    b"Date,Ticker,Amount\n2025-01-02,Cash & Cash Inv,100\n",
    b"Date,Ticker,Amount\n2025-01-02,SPY,100,extra\n",
    b"Ticker,Amount\nSPY,100\n",
):
    try:
        parse_purchase_csv(malformed)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Rejected input accepted: {malformed!r}")

days = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
prices = pd.DataFrame({
    "SPY": [100.0, 110.0, 100.0],
    "NVDA": [50.0, 40.0, 80.0],
}, index=days)
result = simulate_purchase_history(two, prices, date(2025, 1, 6))
assert result["start"] == date(2025, 1, 3)
assert result["end"] == date(2025, 1, 6)
a, b = result["outcomes"]["A"], result["outcomes"]["B"]
assert abs(a["ending_value"] - 180) < 1e-9
assert abs(a["invested"] - 140) < 1e-9
assert abs(a["net_profit"] - 40) < 1e-9
assert abs(a["since_inception_return_pct"] - 32) < 1e-8
assert abs(a["spy_profit"] - (-3.63636363636)) < 1e-6
summary = result["summary"].set_index("Portfolio")
assert abs(summary.loc["A", "Common-period return %"] - 20) < 1e-8
assert abs(summary.loc["B", "Common-period return %"] - (100/110-1)*100) < 1e-8
assert abs(summary.loc["A", "SPY return %"] - (100/110-1)*100) < 1e-8
assert abs(result["chart"]["portfolio_0"].iloc[0] - 100) < 1e-8
assert abs(result["chart"]["portfolio_0"].iloc[-1] - 120) < 1e-8

# Cash added on day two at unchanged prices must not manufacture "returns".
flat = pd.DataFrame({"SPY":[100,100,100]},
    index=days)
flat_buys = parse_purchase_csv(
    b"Date,Ticker,Amount\n2025-01-02,SPY,100\n2025-01-03,SPY,900\n"
)
flat_result = simulate_purchase_history(flat_buys, flat, date(2025,1,6))
assert flat_result["outcomes"]["Uploaded Portfolio"]["net_profit"] == 0
assert flat_result["summary"].iloc[0]["Common-period return %"] == 0

# Missing quotes for an owned position must block the entire return.
missing = prices.copy()
missing.loc[days[-1], "NVDA"] = float("nan")
try:
    simulate_purchase_history(two, missing, date(2025, 1, 6))
except HistoricalCoverageError as exc:
    assert "missing NVDA" in str(exc)
else:
    raise AssertionError("An active holding with missing data was ignored.")

# Missing prices on the actual intended buy session cannot be silently shifted.
missing_at_buy = prices.copy()
missing_at_buy.loc[days[1], "NVDA"] = float("nan")
try:
    simulate_purchase_history(two, missing_at_buy, date(2025, 1, 6))
except HistoricalCoverageError as exc:
    assert "purchase session" in str(exc)
else:
    raise AssertionError("A buy was backfilled past its intended date.")

# A weekend purchase uses the next trading session, never a prior one.
weekend = parse_purchase_csv(
    b"Date,Ticker,Amount\n2025-01-04,SPY,100\n"
)
weekend_result = simulate_purchase_history(weekend, flat, date(2025, 1, 6))
assert weekend_result["outcomes"]["Uploaded Portfolio"]["start"] == date(2025, 1, 6)

print("PASS: purchase CSV validation, cash-flow-adjusted returns, matched SPY, common windows")
