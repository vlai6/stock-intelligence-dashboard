"""Deterministic offline tests for X-Ray's historical portfolio comparison."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portfolio_xray_history import (
    portfolio_weights, unsupported_assets, simulate_returns,
    HistoricalCoverageError,
)

t0, t1 = date(2025, 1, 2), date(2025, 1, 3)
days = pd.to_datetime(["2025-01-02", "2025-01-03"])
prices = pd.DataFrame(
    {"SPY": [100.0, 110.0], "NVDA": [50.0, 60.0]},
    index=days,
)

positions = [
    {"ticker": "SPY", "amount": 60},
    {"ticker": "NVDA", "amount": 40},
]
r = simulate_returns(positions, t0, t1, prices)
assert abs(r["portfolio_pct"] - 14.0) < 1e-8
assert abs(r["spy_pct"] - 10.0) < 1e-8
assert abs(r["excess_pp"] - 4.0) < 1e-8
assert all(abs(a - b) < 1e-8 for a, b in zip(r["chart"]["Portfolio"], [100.0, 114.0]))
assert round(r["contributions"]["Contribution (pp)"].sum(), 8) == 14.0
assert r["start"] == t0 and r["end"] == t1

with_cash = simulate_returns([
    {"ticker": "SPY", "amount": 80},
    {"ticker": "Cash & Cash Inv", "amount": 20},
], t0, t1, prices)
assert abs(with_cash["portfolio_pct"] - 8) < 1e-8
assert abs(with_cash["excess_pp"] + 2) < 1e-8
cash_only = simulate_returns([
    {"ticker": "Cash & Cash Inv", "amount": 100},
], t0, t1, prices[["SPY"]])
assert cash_only["portfolio_pct"] == 0
assert abs(cash_only["excess_pp"] + 10) < 1e-8

double = portfolio_weights([
    {"ticker": "SPY", "amount": 10},
    {"ticker": "SPY", "amount": 20},
    {"ticker": "NVDA", "amount": 70},
])
assert abs(double["SPY"] - 0.30) < 1e-8
assert abs(sum(double.values()) - 1.0) < 1e-8
assert unsupported_assets({"91282CMB4": 0.4, "TLT": 0.4, "Cash & Cash Inv": 0.2}) == {
    "91282CMB4": 0.4
}

for positions, data, error_phrase in [
    ([{"ticker": "91282CMB4", "amount": 50}, {"ticker": "SPY", "amount": 50}],
     prices, "CUSIP"),
    ([{"ticker": "UNAVAILABLE", "amount": 50}, {"ticker": "SPY", "amount": 50}],
     prices, "Missing adjusted price"),
    ([{"ticker": "SPY", "amount": 50}, {"ticker": "NVDA", "amount": 50}],
     prices.loc[prices.index[:1]], "Not enough common trading dates"),
]:
    try:
        simulate_returns(positions, t0, t1, data)
    except HistoricalCoverageError as e:
        assert error_phrase in str(e), str(e)
    else:
        raise AssertionError(f"Missing coverage must block full return: {positions}")

# A holding that went public much later cannot be back-filled to make
# an artificially complete "since 2020" result.
late = pd.DataFrame(
    {"SPY": [100, 110], "NEW": [100, 120]},
    index=pd.to_datetime(["2025-04-02", "2025-04-03"]),
)
try:
    simulate_returns([{"ticker": "SPY", "amount": 50},
                      {"ticker": "NEW", "amount": 50}],
                     t0, date(2025, 4, 3), late)
except HistoricalCoverageError as exc:
    assert "after the selected" in str(exc)
else:
    raise AssertionError("Must not silently start months later than requested")

print("PASS: normalized buy-and-hold vs SPY, cash, CUSIP and price coverage")
