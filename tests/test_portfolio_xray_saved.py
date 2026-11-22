"""Offline validation of browser-saved Portfolio X-Ray snapshots."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from portfolio_xray_saved import (
    _sanitize_positions, _sanitize_saved, MAX_PORTFOLIOS, MAX_POSITIONS,
)

rows = [
    {"ticker": "nvda", "amount": 500.0},
    {"ticker": "spy", "amount": 1000.25},
]
assert _sanitize_positions(rows) == [
    {"ticker": "NVDA", "amount": 500.0},
    {"ticker": "SPY", "amount": 1000.25},
]
assert _sanitize_positions([{"ticker": "bad;drop", "amount": 100}]) == []
assert _sanitize_positions([{"ticker": "SPY", "amount": float("inf")}]) == []
assert _sanitize_positions([{"ticker": "SPY", "amount": -2}]) == []
assert _sanitize_positions([{"ticker": "SPY", "amount": 0}]) == []
assert _sanitize_positions([{"ticker": "SPY"}]) == []

portfolios = _sanitize_saved({
    "Core ETFs": rows,
    "empty": [],
    "invalid": [{"ticker": "SPY", "amount": 0}],
})
assert list(portfolios) == ["Core ETFs"]
assert len(portfolios["Core ETFs"]) == 2

too_many_positions = [{"ticker": "SPY", "amount": i + 1} for i in range(MAX_POSITIONS + 1)]
assert len(_sanitize_positions(too_many_positions)) == MAX_POSITIONS

many_portfolios = {
    f"Portfolio {i}": [{"ticker": "NVDA", "amount": 1}]
    for i in range(MAX_PORTFOLIOS + 5)
}
assert len(_sanitize_saved(many_portfolios)) == MAX_PORTFOLIOS

# Loading sets the input widgets and queues an immediate X-Ray analysis.
from unittest.mock import patch
from portfolio_xray_saved import _load_selected, _save_current, _delete_selected, NS

state = {
    NS + "selected": "Core ETFs",
    NS + "portfolios": {
        "Core ETFs": [
            {"ticker": "SPY", "amount": 100.0},
            {"ticker": "NVDA", "amount": 50.0},
        ],
        "Other": [{"ticker": "AAPL", "amount": 25.0}],
    },
    "portfolio_xray_row_count": 4,
    "portfolio_xray_ticker_2": "STALE",
    "portfolio_xray_amount_2": 300.0,
}
with patch("portfolio_xray_saved.st.session_state", state):
    _load_selected()
assert state["portfolio_xray_ticker_0"] == "SPY"
assert state["portfolio_xray_amount_1"] == 50.0
assert state["portfolio_xray_ticker_2"] == ""
assert state["portfolio_xray_amount_2"] == 0.0
assert state["portfolio_xray_row_count"] == 3
assert state["portfolio_xray_auto_analyze"] is True
assert state[NS + "loaded_name"] == "Core ETFs"

# Saving the currently entered positions marks that portfolio as loaded,
# so the Load button can be disabled until a different name is chosen.
with patch("portfolio_xray_saved.st.session_state", state):
    _save_current("Copy")
assert state[NS + "selected"] == "Copy"
assert state[NS + "loaded_name"] == "Copy"
assert state[NS + "portfolios"]["Copy"] == [
    {"ticker": "SPY", "amount": 100.0}, {"ticker": "NVDA", "amount": 50.0},
]

# Deleting the loaded name clears the flag before the selector is rebuilt.
with patch("portfolio_xray_saved.st.session_state", state):
    _delete_selected()
assert state[NS + "loaded_name"] is None
assert "Copy" not in state[NS + "portfolios"]

# Percentage-based imported portfolios keep their weight units through save/load.
state[NS + "selected"] = "Other"
state[NS + "units"] = {"Other": "pct", "Core ETFs": "usd"}
with patch("portfolio_xray_saved.st.session_state", state):
    _load_selected()
assert state["portfolio_xray_unit_mode"] == "pct"
assert state["portfolio_xray_auto_analyze"] is True
assert state["portfolio_xray_amount_0"] == 25.0
state["portfolio_xray_unit_mode"] = "pct"
with patch("portfolio_xray_saved.st.session_state", state):
    _save_current("Percentage Portfolio")
assert state[NS + "units"]["Percentage Portfolio"] == "pct"

# Legacy saves without a units mapping default to dollars, not percentages.
state[NS + "units"] = {}
state[NS + "selected"] = "Core ETFs"
with patch("portfolio_xray_saved.st.session_state", state):
    _load_selected()
assert state["portfolio_xray_unit_mode"] == "usd"

# The export filename is always a basename, even for punctuation/unicode.
from portfolio_xray_saved import loaded_portfolio_chart_name, portfolio_png_filename
assert portfolio_png_filename(None) == "portfolio_xray_pie_chart"
assert portfolio_png_filename("Core ETFs") == "portfolio_xray_Core_ETFs"
assert portfolio_png_filename("My/Investments: 2026") == "portfolio_xray_My_Investments_2026"
assert "/" not in portfolio_png_filename("../../Portfolio")
assert "\\\\" not in portfolio_png_filename("A\\\\B")

# An existing name in the selector is not enough: it must be explicitly loaded
# and the analyzed inputs must still equal the saved portfolio snapshot.
state = {
    NS + "loaded_name": "Core ETFs",
    NS + "selected": "Other",
    NS + "portfolios": {
        "Core ETFs": [
            {"ticker": "SPY", "amount": 100.0},
            {"ticker": "NVDA", "amount": 50.0},
        ],
        "Other": [{"ticker": "AAPL", "amount": 25.0}],
    },
    NS + "units": {"Core ETFs": "usd", "Other": "pct"},
    "portfolio_xray_row_count": 3,
    "portfolio_xray_ticker_0": "SPY",
    "portfolio_xray_amount_0": 100.0,
    "portfolio_xray_ticker_1": "NVDA",
    "portfolio_xray_amount_1": 50.0,
    "portfolio_xray_ticker_2": "",
    "portfolio_xray_amount_2": 0.0,
    "portfolio_xray_unit_mode": "usd",
    "portfolio_xray_results": ([], {"total": 150.0}),
    "portfolio_xray_results_signature": (
        "usd", (("SPY", 100.0), ("NVDA", 50.0))
    ),
}
with patch("portfolio_xray_saved.st.session_state", state):
    assert loaded_portfolio_chart_name() == "Core ETFs"
    # A different selected name is not a loaded portfolio.
    state[NS + "loaded_name"] = None
    assert loaded_portfolio_chart_name() is None
    state[NS + "loaded_name"] = "Core ETFs"
    # Changing a holding without re-analysis removes the label.
    state["portfolio_xray_amount_1"] = 55.0
    assert loaded_portfolio_chart_name() is None
    state["portfolio_xray_amount_1"] = 50.0
    # A result from before another portfolio was loaded is not valid.
    state["portfolio_xray_results_signature"] = ("usd", (("AAPL", 25.0),))
    assert loaded_portfolio_chart_name() is None
    state["portfolio_xray_results_signature"] = (
        "usd", (("SPY", 100.0), ("NVDA", 50.0))
    )
    # The same weights in different units cannot inherit the saved name.
    state["portfolio_xray_unit_mode"] = "pct"
    assert loaded_portfolio_chart_name() is None
    state["portfolio_xray_unit_mode"] = "usd"
    # Deleted portfolios and charts with no analysis cannot be labeled.
    state["portfolio_xray_results"] = None
    assert loaded_portfolio_chart_name() is None
    state["portfolio_xray_results"] = ([], {"total": 150.0})
    state[NS + "portfolios"].pop("Core ETFs")
    assert loaded_portfolio_chart_name() is None

print("PASS: saved portfolios, chart title identity, PNG filenames, and unit persistence")
