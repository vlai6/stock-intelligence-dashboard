"""Offline tests for two-column CSV Portfolio X-Ray imports and asset classification."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from portfolio_xray_csv import parse_portfolio_csv, export_portfolio_csv
from portfolio_xray import portfolio_rows, security_type, ticker_of

# Representative Excel-export content from the requested format; values are
# percentage points, not dollars. Zero-value MCBS is skipped, not rejected.
sample = """Ticker,Amount
AVGO,0.68%
BABA,0.39%
GOOG,1.68%
MBLY,0.22%
MCBS,0.00%
MSFT,0.77%
MU,0.30%
NVDA,2.36%
SNDK,0.81%
AIQ,0.81%
GLD,0.10%
QTUM,2.38%
SPY,12.29%
TLT,5.24%
VGT,1.49%
VOO,1.62%
VTEB,6.19%
912797WG8,6.34%
91282CMB4,50.63%
Cash & Cash Inv,5.71%
"""
positions, unit, warnings = parse_portfolio_csv(sample.encode("utf-8-sig"))
assert unit == "pct"
assert len(positions) == 19
assert len(warnings) == 1 and "0.00" in warnings[0]
assert abs(sum(p["amount"] for p in positions) - 100.01) < 0.000001
by_ticker = {p["ticker"]: p["amount"] for p in positions}
assert by_ticker["SPY"] == 12.29
assert by_ticker["912797WG8"] == 6.34
assert by_ticker["91282CMB4"] == 50.63
assert by_ticker["Cash & Cash Inv"] == 5.71
assert "MCBS" not in by_ticker

# Cash and Treasury CUSIPs must remain non-stock assets, not misclassified.
assert ticker_of("Cash & Cash Inv") == "Cash & Cash Inv"
assert ticker_of("912797WG8") == "912797WG8"
assert security_type("91282CMB4", {}) == "OTHER"
assert security_type("Cash & Cash Inv", {}) == "OTHER"
assert security_type("NVDA", {"NVDA": "STOCK"}) == "STOCK"
other = [dict(pos, type="OTHER") for pos in positions
         if pos["ticker"] in {"912797WG8", "91282CMB4", "Cash & Cash Inv"}]
other_rows, info = portfolio_rows(other, {})
assert abs(info["total"] - 62.68) < 1e-6
assert abs(info["other_assets"] - 62.68) < 1e-6
assert info["unresolved"] == 0
assert {r["Stock"] for r in other_rows} == {
    "Cash & Cash Inv", "912797WG8", "91282CMB4"
}

# Also accept normal dollar allocations without changing old X-Ray semantics.
dollar, unit, notes = parse_portfolio_csv(b"Ticker,Amount\nSPY,1200.50\nNVDA,$350\n")
assert unit == "usd" and not notes
assert dollar == [
    {"ticker": "SPY", "amount": 1200.5},
    {"ticker": "NVDA", "amount": 350.0},
]

# Reject mixed units, malformed percentages, negative weights and oversized CSV.
invalid = [
    b"Ticker,Amount\nSPY,12%\nNVDA,20\n",
    b"Ticker,Amount\nNVDA,-1%\n",
    b"Ticker,Amount\nNVDA,1%%\n",
    b"Ticker,Amount\nNVDA,101%\n",
    b"Wrong,Header\nSPY,10%\n",
    b"Ticker,Amount\nSPY,90%\nNVDA,20%\n",
    b"Ticker,Amount\nCash & Cash Inv,not-a-number\n",
]
for payload in invalid:
    try:
        parse_portfolio_csv(payload)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Invalid CSV was accepted: {payload[:75]!r}")

incomplete, unit, warning = parse_portfolio_csv(
    b"Ticker,Amount\nSPY,20%\nNVDA,25%\n"
)
assert unit == "pct" and warning and "45.00%" in warning[0]

# The file-upload callback populates the existing input rows and requests
# the same automatic look-through analysis as a loaded saved portfolio.
from portfolio_xray_ui import _import_portfolio_csv
class _Uploaded:
    def __init__(self, data):
        self.data = data
    def getvalue(self):
        return self.data

state = {"portfolio_xray_csv_file": _Uploaded(sample.encode("utf-8"))}
with patch("portfolio_xray_ui.st.session_state", state):
    _import_portfolio_csv()
assert state["portfolio_xray_unit_mode"] == "pct"
assert state["portfolio_xray_row_count"] == 20  # 19 positions + 1 empty row
assert state["portfolio_xray_ticker_0"] == "AVGO"
assert state["portfolio_xray_ticker_18"] == "Cash & Cash Inv"
assert state["portfolio_xray_amount_18"] == 5.71
assert state["portfolio_xray_auto_analyze"] is True
assert state["portfolio_xray_saved_loaded_name"] is None
state["portfolio_xray_csv_file"] = _Uploaded(b"Ticker,Amount\\nNVDA,INVALID\\n")
with patch("portfolio_xray_ui.st.session_state", state):
    _import_portfolio_csv()
assert state["portfolio_xray_csv_feedback"][0] == "error"
assert state["portfolio_xray_ticker_0"] == "AVGO"  # Bad import never wipes editor.

# A downloaded CSV must round-trip unchanged through the public importer.
# This is the actual user's two-column percentage format, including cash
# and directly owned Treasury CUSIPs.
exported_pct = export_portfolio_csv(positions, "pct")
imported_pct, imported_unit, _ = parse_portfolio_csv(exported_pct)
assert imported_unit == "pct"
assert imported_pct == positions
assert "91282CMB4,50.63%" in exported_pct.decode("utf-8-sig")
assert "Cash & Cash Inv,5.71%" in exported_pct.decode("utf-8-sig")

exported_usd = export_portfolio_csv(dollar, "usd")
imported_usd, imported_unit, notes = parse_portfolio_csv(exported_usd)
assert imported_unit == "usd" and not notes
assert imported_usd == dollar
assert b"SPY,1200.5" in exported_usd

# Export refuses units and allocations the importer would not accept.
for sample_positions, units in [
    (positions, "unknown"),
    ([{"ticker": "SPY", "amount": -5.0}], "usd"),
    ([{"ticker": "NVDA", "amount": 55.0},
      {"ticker": "SPY", "amount": 55.0}], "pct"),
]:
    try:
        export_portfolio_csv(sample_positions, units)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid export must be refused")

# The UI shares only analyzed inputs that still match the editor's inputs.
from portfolio_xray_ui import _analyzed_portfolio_share_csv

share_state = {
    "portfolio_xray_results": ([], {"total": 100.01}),
    "portfolio_xray_unit_mode": "pct",
    "portfolio_xray_row_count": len(positions) + 1,
    "portfolio_xray_results_signature": (
        "pct", tuple((p["ticker"], float(p["amount"])) for p in positions)
    ),
    "portfolio_xray_saved_loaded_name": None,
}
for index, position in enumerate(positions):
    share_state[f"portfolio_xray_ticker_{index}"] = position["ticker"]
    share_state[f"portfolio_xray_amount_{index}"] = position["amount"]
share_state[f"portfolio_xray_ticker_{len(positions)}"] = ""
share_state[f"portfolio_xray_amount_{len(positions)}"] = 0.0

with patch("portfolio_xray_ui.st.session_state", share_state):
    shared = _analyzed_portfolio_share_csv()
assert shared is not None
assert shared[1] == "portfolio_xray_portfolio.csv"
assert parse_portfolio_csv(shared[0])[0] == positions

with patch("portfolio_xray_ui.st.session_state", share_state):
    share_state["portfolio_xray_amount_0"] = 15.0  # Edited but not analyzed
    assert _analyzed_portfolio_share_csv() is None
    share_state["portfolio_xray_amount_0"] = positions[0]["amount"]
    share_state["portfolio_xray_results_signature"] = ("usd", ())
    assert _analyzed_portfolio_share_csv() is None
    share_state["portfolio_xray_results_signature"] = (
        "pct", tuple((p["ticker"], float(p["amount"])) for p in positions)
    )
    share_state["portfolio_xray_results"] = None
    assert _analyzed_portfolio_share_csv() is None

print("PASS: Portfolio X-Ray share CSV percent/dollar round trip and analyzed-only export")

