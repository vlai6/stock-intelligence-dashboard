"""Offline portfolio X-ray coverage and arithmetic tests (no API requests)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from portfolio_xray import Holdings, parse_rows, portfolio_rows, pie_data, pie_legend_labels, ticker_of, security_type

rows = [
    ["Fund holdings data", "", ""],
    ["Ticker", "Company", "Weight (%)"],
    ["NVDA", "NVIDIA", "10.00%"],
    ["MSFT", "Microsoft", "20.00%"],
    ["AAPL", "Apple", "65.00%"],
]
snap = parse_rows(rows, "TEST", "synthetic fixture")
assert abs(snap.coverage - 0.95) < 1e-10
assert abs(snap.weights["NVDA"] - 0.1) < 1e-10
assert ticker_of("brk.b") == "BRK.B"
assert security_type("SPY") == "ETF"
assert security_type("SPMO") == "ETF"
assert security_type("AVLV") == "ETF"
assert security_type("NVDA") == "STOCK"
assert security_type("AAPL") == "STOCK"
assert security_type("CUSTOMEQUITY", quote_lookup=lambda _: {"quoteType": "EQUITY"}) == "STOCK"
assert security_type("CUSTOMFUND", quote_lookup=lambda _: {"quoteType": "ETF"}) == "ETF"
try:
    security_type("AMBIGUOUS", quote_lookup=lambda _: {})
except ValueError:
    pass
else:
    raise AssertionError("Unknown symbols must not be silently categorized")


# Fractional weights should work and must not be automatically magnified.
fraction = parse_rows([
    ["Holding Ticker", "Weight"], ["NVDA", "0.4"], ["MSFT", "0.6"]
], "FUND", "synthetic fixture")
assert abs(fraction.coverage - 1) < 1e-8
assert abs(fraction.weights["MSFT"] - .6) < 1e-8

# Stock exposure can come from two ETFs plus one direct-stock holding.
other = Holdings("SECOND", {"NVDA": .25, "MSFT": .75}, "synthetic")
positions = [
    {"type": "ETF", "ticker": "TEST", "amount": 6000},
    {"type": "ETF", "ticker": "SECOND", "amount": 4000},
    {"type": "STOCK", "ticker": "NVDA", "amount": 1000},
]
out, info = portfolio_rows(positions, {"TEST": snap, "SECOND": other})
exposure = {r["Stock"]: r for r in out}
assert info["total"] == 11000
assert abs(exposure["NVDA"]["_value"] - 2600) < 1e-8
assert abs(exposure["MSFT"]["_value"] - 4200) < 1e-8
assert abs(exposure["AAPL"]["_value"] - 3900) < 1e-8
assert abs(exposure["Unreported TEST"]["_value"] - 300) < 1e-8
assert abs(sum(r["_value"] for r in out) - 11000) < 1e-8
assert "Direct" in exposure["NVDA"]["From"]
assert "TEST" in exposure["NVDA"]["From"]

# Unknown ETF feed must not become a fake 100%-equity look-through.
bad, bad_info = portfolio_rows(
    [{"type": "ETF", "ticker": "AVLV", "amount": 2500},
     {"type": "STOCK", "ticker": "AAPL", "amount": 500}],
    {}, {"AVLV": "No available holdings"}
)
assert bad_info["unresolved"] == 2500
assert abs(sum(r["_value"] for r in bad) - 3000) < 1e-7
labels, amounts = pie_data(bad)
assert "Unresolved ETF exposure" in labels
assert abs(sum(amounts) - 3000) < 1e-7
assert abs(bad_info["mapped"] - 500) < 1e-7
# Legend percentages are based on total portfolio exposure, including unknown
# holdings, not the total of the mapped subset alone.
assert pie_legend_labels(["NVDA", "Other stocks"], [371, 629]) == [
    "NVDA 37.1%", "Other stocks 62.9%",
]
assert pie_legend_labels(["NVDA", "Unresolved ETF exposure"], [371, 629]) == [
    "NVDA 37.1%", "Unresolved ETF exposure 62.9%",
]
assert pie_legend_labels(["No data"], [0]) == ["No data"]
assert pie_legend_labels(["NVDA", "SPY", "Unresolved ETF exposure"], [37.1, 59.7, 3.2]) == [
    "NVDA 37.1%", "SPY 59.7%", "Unresolved ETF exposure 3.2%",
]
try:
    pie_legend_labels(["A"], [1, 2])
except ValueError:
    pass
else:
    raise AssertionError("Legend labels must match their amounts")

try:
    parse_rows([["Ticker", "Weight"], ["AAPL", "111"]], "BAD", "synthetic")
except ValueError:
    pass
else:
    raise AssertionError("Invalid >100% weight must be rejected")

try:
    ticker_of("SPY; rm -rf")
except ValueError:
    pass
else:
    raise AssertionError("Unvalidated ticker was accepted")
print("PASS: portfolio ETF look-through, partial coverage, stock overlap and validation")
