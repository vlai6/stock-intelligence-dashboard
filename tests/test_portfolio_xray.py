"""Offline TickerInside Portfolio X-Ray tests; never contact external APIs."""
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from portfolio_xray import (
    Holdings, _tickerinside_json, issuer_holdings, tickerinside_identifiers,
    portfolio_rows, pie_data, pie_legend_labels, display_ticker, ticker_of, security_type,
)

IDENTIFIERS = {
    "fields": ["ticker", "name", "asset_type", "exchange"],
    "securities": [
        ["SPY", "State Street SPDR S&P 500 ETF", "etf", "NYSE Arca"],
        ["SPMO", "Invesco S&P 500 Momentum ETF", "etf", "NYSE Arca"],
        ["AVLV", "Avantis U.S. Large Cap Value ETF", "etf", "NYSE Arca"],
        ["NVDA", "Nvidia", "stock", "Nasdaq"],
        ["AAPL", "Apple", "stock", "Nasdaq"],
        ["MU", "Micron", "stock", "Nasdaq"],
        ["NOTE", "Example Exchange Traded Note", "etn", "NYSE"],
    ],
}
with patch("portfolio_xray._tickerinside_json", return_value=IDENTIFIERS):
    kinds = tickerinside_identifiers()
assert security_type("SPY", kinds) == "ETF"
assert security_type("SPMO", kinds) == "ETF"
assert security_type("AVLV", kinds) == "ETF"
assert security_type("NVDA", kinds) == "STOCK"
assert security_type("AAPL", kinds) == "STOCK"
assert security_type("NOTE", kinds) == "ETF"  # Do not treat notes as direct company shares.
try:
    security_type("UNKNOWN", kinds)
except ValueError:
    pass
else:
    raise AssertionError("Unknown TickerInside tickers must not be guessed")

assert ticker_of("brk.b") == "BRK.B"
try:
    ticker_of("SPY; rm -rf")
except ValueError:
    pass
else:
    raise AssertionError("Unvalidated ticker was accepted")

# A TickerInside fund lists percentage weights, not decimals.
EXAMPLE_FUND = {
    "ticker": "SPMO", "source_layer": "sec_nport",
    "holdings_as_of": "2026-08-31",
    "holdings": {"NVDA": 10.0, "MSFT": 20.0, "AAPL": 65.0},
}
with patch("portfolio_xray._tickerinside_json", return_value=EXAMPLE_FUND) as fetch:
    snap = issuer_holdings("SPMO")
    fetch.assert_called_once_with("fund/spmo.json")
assert snap.as_of == "2026-08-31"
assert "TickerInside" in snap.source
assert abs(snap.coverage - 0.95) < 1e-10
assert abs(snap.weights["NVDA"] - .1) < 1e-10

# Detect malformed source totals, and keep non-stock ETFs unresolved.
with patch("portfolio_xray._tickerinside_json", return_value={
    "holdings": {"NVDA": 80, "AAPL": 50},
}):
    try:
        issuer_holdings("SPY")
    except ValueError:
        pass
    else:
        raise AssertionError("Holdings greater than 102% must be rejected")

with patch("portfolio_xray._tickerinside_json", return_value={
    "holdings_kind": "bond", "holdings": {"US TREASURY": 100},
}):
    try:
        issuer_holdings("TLT")
    except ValueError:
        pass
    else:
        raise AssertionError("Bonds cannot be presented as stock holdings")

# Stock exposure can come through two ETFs plus a direct-stock position.
other = Holdings("SECOND", {"NVDA": .25, "MSFT": .75}, "synthetic")
positions = [
    {"type": "ETF", "ticker": "SPMO", "amount": 6000},
    {"type": "ETF", "ticker": "SECOND", "amount": 4000},
    {"type": "STOCK", "ticker": "NVDA", "amount": 1000},
]
out, info = portfolio_rows(positions, {"SPMO": snap, "SECOND": other})
exposure = {r["Stock"]: r for r in out}
assert info["total"] == 11000
assert abs(exposure["NVDA"]["_value"] - 2600) < 1e-8
assert abs(exposure["MSFT"]["_value"] - 4200) < 1e-8
assert abs(exposure["AAPL"]["_value"] - 3900) < 1e-8
assert abs(exposure["Unreported SPMO"]["_value"] - 300) < 1e-8
assert abs(sum(r["_value"] for r in out) - 11000) < 1e-8
# Direct positions and aggregated ETF exposure must add up to each stock's value.
assert exposure["NVDA"]["Direct Amount"] == 1000
assert exposure["NVDA"]["ETF Amount"] == 1600
assert exposure["MSFT"]["Direct Amount"] == 0
assert exposure["MSFT"]["ETF Amount"] == 4200
assert exposure["Unreported SPMO"]["Direct Amount"] == 0
assert exposure["Unreported SPMO"]["ETF Amount"] == 300
assert all(
    abs(r["Direct Amount"] + r["ETF Amount"] - r["Amount ($)"]) < 0.011
    for r in out
)

# Missing fund data never silently becomes an artificial fully mapped position.
bad, bad_info = portfolio_rows(
    [{"type": "ETF", "ticker": "AVLV", "amount": 2500},
     {"type": "STOCK", "ticker": "AAPL", "amount": 500}],
    {}, {"AVLV": "No available TickerInside holdings"},
)
assert bad_info["unresolved"] == 2500
assert abs(sum(r["_value"] for r in bad) - 3000) < 1e-7
assert {r["Stock"]: r for r in bad}["Unresolved AVLV"]["ETF Amount"] == 2500
assert {r["Stock"]: r for r in bad}["AAPL"]["Direct Amount"] == 500
labels, amounts = pie_data(bad)
assert "AVLV" in labels
assert "Unresolved ETF exposure" not in labels
assert dict(zip(labels, amounts))["AVLV"] == 2500
assert abs(sum(amounts) - 3000) < 1e-7
assert abs(bad_info["mapped"] - 500) < 1e-7

# Keep all 500 distinct underlying stocks as individual pie slices rather than
# collapsing most into an "Other stocks" bucket. Legend filtering is UI-only.
many = [
    {
        "Stock": f"STOCK{i:03d}",
        "_value": 1.0,
        "Unresolved": False,
    }
    for i in range(500)
]
many.append({"Stock": "Unresolved TEST", "_value": 2.5, "Unresolved": True})
full_labels, full_amounts = pie_data(many)
assert len(full_labels) == 501
assert full_labels[0] == "STOCK000"
assert full_labels[499] == "STOCK499"
assert "Other stocks" not in full_labels
assert full_labels[-1] == "TEST"
assert abs(sum(full_amounts) - 502.5) < 1e-8
assert pie_legend_labels(["NVDA", "Other stocks"], [371, 629]) == [
    "NVDA 37.1%", "Other stocks 62.9%",
]
assert pie_legend_labels(["NVDA", "TLT"], [371, 629]) == [
    "NVDA 37.1%", "TLT 62.9%",
]
# Unknown ticker classification should not crash an imported portfolio or
# misrepresent an unverified position as an ETF.
unknown_rows, unknown_info = portfolio_rows([
    {"type": "UNKNOWN", "ticker": "UNKN", "amount": 45},
    {"type": "OTHER", "ticker": "91282CMB4", "amount": 50},
    {"type": "OTHER", "ticker": "Cash & Cash Inv", "amount": 5},
], {})
assert abs(unknown_info["total"] - 100) < 1e-10
assert unknown_info["unresolved"] == 45
assert unknown_info["other_assets"] == 55
unknown = {r["Stock"]: r for r in unknown_rows}
assert unknown["Unverified UNKN"]["Direct Amount"] == 45
assert unknown["Unverified UNKN"]["ETF Amount"] == 0
assert unknown["91282CMB4"]["Unresolved"] is False
assert unknown["Cash & Cash Inv"]["Unresolved"] is False
labels, amounts = pie_data(unknown_rows)
assert "UNKN" in labels
assert "Unclassified positions" not in labels
assert abs(sum(amounts) - 100) < 1e-10

# Each missing ETF's ticker is shown on the donut and in its legend, rather
# than pooling all missing holdings into a misleading generic 31% slice.
breakdown, breakdown_info = portfolio_rows(
    [
        {"type": "ETF", "ticker": "TLT", "amount": 5.0},
        {"type": "ETF", "ticker": "VTEB", "amount": 6.0},
        {"type": "ETF", "ticker": "SPMO", "amount": 10.0},
        {"type": "UNKNOWN", "ticker": "MYSTERY", "amount": 1.0},
    ],
    {"SPMO": Holdings("SPMO", {"NVDA": .8}, "synthetic")},
)
names, values = pie_data(breakdown)
slices = dict(zip(names, values))
assert abs(sum(values) - 22.0) < 1e-8
assert abs(breakdown_info["unresolved"] - 14.0) < 1e-8
assert slices["TLT"] == 5
assert slices["VTEB"] == 6
assert slices["SPMO"] == 2.0
assert slices["MYSTERY"] == 1.0
assert abs(slices["NVDA"] - 8.0) < 1e-8
assert "Unresolved ETF exposure" not in names
assert "Unclassified positions" not in names

# If a ticker is also present among mapped ETF constituents, do not lose a
# slice or silently recategorize the unverified direct position.
collision_rows = [
    {"Stock": "NVDA", "_value": 8.0, "Unresolved": False},
    {"Stock": "Unverified NVDA", "_value": 3.0, "Unresolved": True},
]
collision_names, collision_amounts = pie_data(collision_rows)
assert collision_names == ["NVDA", "NVDA"]
assert collision_amounts == [8.0, 3.0]
assert display_ticker("Unresolved TLT") == "TLT"
assert display_ticker("Unreported SPMO") == "SPMO"
assert display_ticker("Unverified X123") == "X123"
assert display_ticker("NVDA") == "NVDA"

assert pie_legend_labels(["No data"], [0]) == ["No data"]
try:
    pie_legend_labels(["A"], [1, 2])
except ValueError:
    pass
else:
    raise AssertionError("Legend labels must match values")

print("PASS: TickerInside classification, fund weights, non-stock NAV, overlap, missing data")
