"""Offline regression checks for compact multi-portfolio Historical Returns."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from unittest.mock import patch
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for path in ("portfolio_xray_history.py", "portfolio_xray_history_ui.py"):
    ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)

from portfolio_xray_history import (
    simulate_multiple_returns, HistoricalCoverageError,
)
from portfolio_xray_history_ui import (
    _comparison_snapshot, _reset_historical_results,
    HISTORY_RESULT_KEY, HISTORY_MULTI_KEY, HISTORY_MODE_KEY,
)
from portfolio_xray_saved import NS

start, end = date(2025, 1, 2), date(2025, 1, 3)
prices = pd.DataFrame({
    "SPY": [100, 110],
    "NVDA": [50, 60],
}, index=pd.to_datetime(["2025-01-02", "2025-01-03"]))
portfolios = {
    "Core": [{"ticker": "SPY", "amount": 100}],
    "Growth": [
        {"ticker": "SPY", "amount": 50}, {"ticker": "NVDA", "amount": 50}
    ],
    "Cash mix": [
        {"ticker": "NVDA", "amount": 20},
        {"ticker": "Cash & Cash Inv", "amount": 80},
    ],
}
result = simulate_multiple_returns(portfolios, start, end, prices)
summary = result["summary"].set_index("Portfolio")
assert list(result["summary"]["Portfolio"]) == list(portfolios)
assert all(abs(x - 10) < 1e-8 for x in summary["SPY return %"])
assert abs(summary.loc["Core", "Portfolio return %"] - 10) < 1e-8
assert abs(summary.loc["Growth", "Portfolio return %"] - 15) < 1e-8
assert abs(summary.loc["Cash mix", "Portfolio return %"] - 4) < 1e-8
assert abs(summary.loc["Growth", "Excess return (pp)"] - 5) < 1e-8
assert abs(summary.loc["Cash mix", "Excess return (pp)"] + 6) < 1e-8
assert result["start"] == start and result["end"] == end
assert list(result["chart"].columns) == [
    "Date", "SPY", "portfolio_0", "portfolio_1", "portfolio_2"
]
assert list(result["series"]) == [
    {"key": "portfolio_0", "name": "Core"},
    {"key": "portfolio_1", "name": "Growth"},
    {"key": "portfolio_2", "name": "Cash mix"},
]
assert result["chart"]["portfolio_2"].iloc[-1] == 104

# A saved portfolio literally named SPY must not overwrite the benchmark.
collision = simulate_multiple_returns({
    "SPY": portfolios["Core"], "Date": portfolios["Growth"]
}, start, end, prices)
assert len(collision["chart"].columns) == 4
assert abs(collision["chart"]["SPY"].iloc[-1] - 110) < 1e-8
assert [x["name"] for x in collision["series"]] == ["SPY", "Date"]

for bad in [
    {"One": portfolios["Core"]},
    {str(n): portfolios["Core"] for n in range(6)},
]:
    try:
        simulate_multiple_returns(bad, start, end, prices)
    except ValueError:
        pass
    else:
        raise AssertionError("Comparison must require 2–5 portfolios.")

# Never silently discard CUSIPs, missing/new stocks, or nonmatching dates.
for comparison, dataset, message in [
    ({
        "Core": portfolios["Core"],
        "Treasury": [{"ticker": "91282CMB4", "amount": 100}],
    }, prices, "CUSIP"),
    ({
        "Core": portfolios["Core"],
        "Unknown": [{"ticker": "FOO", "amount": 100}],
    }, prices, "Missing adjusted price"),
    ({"Core": portfolios["Core"], "Growth": portfolios["Growth"]},
     prices.iloc[:1], "Not enough common trading dates"),
]:
    try:
        simulate_multiple_returns(comparison, start, end, dataset)
    except HistoricalCoverageError as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError(f"Missing historical coverage must block: {comparison}")

# A late IPO can have a nonempty series but still must not shift the period.
late = pd.DataFrame(
    {"SPY": [100, 120], "NEW": [80, 95]},
    index=pd.to_datetime(["2025-05-01", "2025-05-02"]),
)
try:
    simulate_multiple_returns({
        "Core": portfolios["Core"],
        "IPO": [{"ticker": "NEW", "amount": 100}],
    }, start, date(2025, 5, 2), late)
except HistoricalCoverageError as exc:
    assert "after the selected" in str(exc)
else:
    raise AssertionError("Late inception must not produce a fake long-period return.")

# UI reads *saved* holdings; selections do not invoke the main X-Ray loader.
state = {
    NS + "portfolios": portfolios,
    NS + "units": {"Core": "usd", "Growth": "pct", "Cash mix": "usd"},
    NS + "loaded_name": "Core",
    NS + "selected": "Core",
    HISTORY_RESULT_KEY: (("stale",), {}),
    HISTORY_MODE_KEY: "Compare Multiple Portfolios",
    HISTORY_MULTI_KEY: ["Core", "Growth"],
}
with patch("portfolio_xray_history_ui.st.session_state", state):
    snapshot = _comparison_snapshot(["Core", "Growth"])
    assert snapshot == (
        ("Core", "usd", (("SPY", 100.0),)),
        ("Growth", "pct", (("SPY", 50.0), ("NVDA", 50.0))),
    )
    assert state[NS + "selected"] == "Core"
    assert state[NS + "loaded_name"] == "Core"
    _reset_historical_results()
    assert HISTORY_RESULT_KEY not in state
    state[NS + "portfolios"]["Growth"][0]["amount"] = 70
    assert _comparison_snapshot(["Core", "Growth"]) != snapshot
    for invalid in (["Core"], ["Core", "Core"], ["Missing", "Core"]):
        try:
            _comparison_snapshot(invalid)
        except (ValueError, KeyError):
            pass
        else:
            raise AssertionError(f"Invalid multi-selection was accepted: {invalid}")

print("PASS: same-day multiple returns, SPY benchmark, CUSIP/missing-data safeguards and UI snapshot")
