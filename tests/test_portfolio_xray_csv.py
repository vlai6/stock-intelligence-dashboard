"""Offline tests for two-column CSV Portfolio X-Ray imports and asset classification."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from portfolio_xray_csv import parse_portfolio_csv
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

print("PASS: portfolio X-Ray CSV percentage/dollar mode, CUSIP/cash and invalid inputs")
