"""Offline share/import/save coverage for X-Ray Date,Ticker,Amount rows."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from portfolio_xray_csv import export_portfolio_csv, parse_portfolio_csv
from portfolio_xray_dates import position_signature
from portfolio_xray_saved import (
    _sanitize_positions, _load_selected, _save_current, NS
)
from portfolio_xray_ui import _analyzed_portfolio_share_csv, _import_portfolio_csv


data = (
    b"Date,Ticker,Amount\n"
    b"2025-01-02,VOO,50%\n"
    b"2024-10-01,VGT,25%\n"
    b",NVDA,15%\n"
    b",Cash & Cash Inv,10%\n"
)
expected = [
    {"date": "2025-01-02", "ticker": "VOO", "amount": 50.0},
    {"date": "2024-10-01", "ticker": "VGT", "amount": 25.0},
    {"ticker": "NVDA", "amount": 15.0},
    {"ticker": "Cash & Cash Inv", "amount": 10.0},
]
rows, units, notices = parse_portfolio_csv(data)
assert units == "pct" and not notices
assert rows == expected
exported = export_portfolio_csv(rows, units)
assert exported.decode("utf-8-sig").startswith("Date,Ticker,Amount")
assert parse_portfolio_csv(exported)[0] == expected
assert "2025-01-02,VOO,50.0%" in exported.decode("utf-8-sig")
assert ",NVDA,15.0%" in exported.decode("utf-8-sig")
assert _sanitize_positions(expected) == expected

# Legacy files still work, but every *new* export has the leading Date column.
old, old_units, _ = parse_portfolio_csv(b"Ticker,Amount\nSPY,70%\nNVDA,30%\n")
assert old_units == "pct"
assert old == [
    {"ticker": "SPY", "amount": 70.0},
    {"ticker": "NVDA", "amount": 30.0},
]
assert export_portfolio_csv(old, old_units).decode("utf-8-sig").startswith(
    "Date,Ticker,Amount\r\n,SPY"
)

for invalid in [
    b"Date,Ticker,Amount\n2028-01-01,SPY,100%\n",
    b"Date,Ticker,Amount\n2020/01/01,SPY,100%\n",
    b"Date,Ticker,Amount\n2018-01-01,SPY,100%\n",
    b"Date,Ticker,Amount\n2025-01-01,,100%\n",
]:
    try:
        parse_portfolio_csv(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Invalid date/row accepted: {invalid!r}")

class Uploaded:
    def __init__(self, payload):
        self.payload = payload
    def getvalue(self):
        return self.payload

# CSV upload assigns Python date objects to Streamlit date widgets.
state = {"portfolio_xray_csv_file": Uploaded(data)}
with patch("portfolio_xray_ui.st.session_state", state):
    _import_portfolio_csv()
assert state["portfolio_xray_auto_analyze"] is True
assert state["portfolio_xray_date_0"] == date(2025, 1, 2)
assert state["portfolio_xray_date_1"] == date(2024, 10, 1)
assert state["portfolio_xray_date_2"] is None
assert state["portfolio_xray_ticker_3"] == "Cash & Cash Inv"
assert state["portfolio_xray_row_count"] == 5
assert "portfolio_xray_results_signature" not in state

# Export is only possible when the displayed analysis reflects same dates.
signature = ("pct", position_signature(expected))
state["portfolio_xray_results"] = ([], {"total": 100.0})
state["portfolio_xray_results_signature"] = signature
with patch("portfolio_xray_ui.st.session_state", state), patch(
    "portfolio_xray_saved.st.session_state", state,
):
    exported_data = _analyzed_portfolio_share_csv()
    assert exported_data is not None
    assert parse_portfolio_csv(exported_data[0])[0] == expected
    state["portfolio_xray_date_0"] = date(2024, 1, 2)
    assert _analyzed_portfolio_share_csv() is None
    state["portfolio_xray_date_0"] = date(2025, 1, 2)

# Mixed dated and undated rows must preserve blank dates in the actual
# pandas-backed X-Ray editor (including NaT where pandas infers it).
import pandas as pd
from portfolio_xray_ui import _clean_positions
mixed_editor = pd.DataFrame([
    {"Date": pd.Timestamp("2025-01-02"), "Ticker": "VOO", "Amount ($)": 50},
    {"Date": pd.NaT, "Ticker": "SPY", "Amount ($)": 50},
    {"Date": pd.NaT, "Ticker": "", "Amount ($)": 0},
])
assert _clean_positions(mixed_editor) == [
    {"ticker": "VOO", "amount": 50.0, "date": "2025-01-02"},
    {"ticker": "SPY", "amount": 50.0},
]

# Save and load historical ETF dates with the same session callbacks.
state[NS + "portfolios"] = {}
state[NS + "units"] = {}
state["portfolio_xray_unit_mode"] = "pct"
with patch("portfolio_xray_saved.st.session_state", state):
    _save_current("Dated Allocation")
assert state[NS + "portfolios"]["Dated Allocation"] == expected
assert state[NS + "units"]["Dated Allocation"] == "pct"
assert state[NS + "loaded_name"] == "Dated Allocation"
state[NS + "selected"] = "Dated Allocation"
with patch("portfolio_xray_saved.st.session_state", state):
    _load_selected()
assert state["portfolio_xray_date_0"] == date(2025, 1, 2)
assert state["portfolio_xray_date_1"] == date(2024, 10, 1)
assert state["portfolio_xray_date_2"] is None
assert state["portfolio_xray_auto_analyze"] is True
assert state["portfolio_xray_row_count"] == 5
print("PASS: Date/Ticker/Amount CSV, date-sensitive export, save and reload")
