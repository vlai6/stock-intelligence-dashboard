"""Offline checks for date-specific ETF holdings and look-through differences."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch
import ast
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for name in (
    "portfolio_xray.py",
    "portfolio_xray_history_holdings.py",
    "portfolio_xray_ui.py",
):
    ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)

from portfolio_xray import Holdings
from portfolio_xray_history_holdings import (
    HistoricalHoldingsUnavailable, parse_historical_holdings,
    exposure_changes, _historical_holdings_payload,
)
from portfolio_xray_ui import _analyze, _portfolio_input_changed

requested = date(2025, 6, 30)
payload = {
    "holdings": {"NVDA": 60.0, "MSFT": 30.0, "AAPL": 9.0},
    "holdings_as_of": "2025-03-31",
    "source_layer": "sec_nport",
}
obj = parse_historical_holdings("VOO", requested, payload)
assert obj.ticker == "VOO"
assert obj.as_of == "2025-03-31"
assert abs(obj.coverage - 0.99) < 1e-9
assert abs(obj.weights["NVDA"] - 0.6) < 1e-9
assert "history/voo/2025-06-30.json" in obj.page_url

for bad in [
    {**payload, "holdings_as_of": "2025-07-01"},
    {**payload, "holdings_as_of": ""},
    {**payload, "holdings": {}},
    {**payload, "holdings": {"NVDA": -2}},
    {**payload, "holdings": {"NVDA": 112}},
    {**payload, "holdings_kind": "bonds"},
]:
    try:
        parse_historical_holdings("VOO", requested, bad)
    except HistoricalHoldingsUnavailable:
        pass
    else:
        raise AssertionError(f"Failed to reject invalid history: {bad}")

def mkresponse(status, body):
    class Response:
        status_code = status
        content = b"{}"
        def json(self):
            return body
        def raise_for_status(self):
            if self.status_code >= 400:
                raise ValueError("HTTP failure")
    return Response()

with patch("portfolio_xray_history_holdings.requests.get") as get:
    get.return_value = mkresponse(404, {
        "reason": "holdings_at_date_not_enabled",
    })
    try:
        _historical_holdings_payload("SPY", requested)
    except HistoricalHoldingsUnavailable as exc:
        assert "SPY" in str(exc)
        assert "holdings_at_date_not_enabled" in str(exc)
    else:
        raise AssertionError("SPY cannot silently become latest holdings.")
    assert "history/spy/2025-06-30.json" in get.call_args.args[0]

historical = Holdings("VOO", {"NVDA": .6, "AAPL": .4},
                       "TickerInside (historical SEC N-PORT)", "2025-03-31")
latest = Holdings("VOO", {"NVDA": .8, "AAPL": .2},
                  "TickerInside (issuer)", "2026-11-20")
positions = [
    {"ticker": "VOO", "amount": 60.0},
    {"ticker": "NVDA", "amount": 40.0},
]
with patch("portfolio_xray_ui._security_type", side_effect=lambda ticker: (
    "ETF" if ticker == "VOO" else "STOCK"
)), patch("portfolio_xray_ui._cached_historical_issuer_holdings", return_value=historical), patch(
    "portfolio_xray_ui._cached_issuer_holdings", return_value=latest,
):
    historical_rows, info = _analyze(positions, {"VOO": requested})
assert info["historical_dates"] == {"VOO": "2025-06-30"}
assert info["historical_unavailable"] == []
assert info["sources"][0]["As of"] == "2025-03-31"
diff = {r["Ticker / exposure"]: r for r in info["historical_comparison"]}
assert abs(diff["NVDA"]["Historical %"] - 76) < 1e-8
assert abs(diff["NVDA"]["Latest %"] - 88) < 1e-8
assert abs(diff["NVDA"]["Change (pp)"] - 12) < 1e-8
assert abs(diff["AAPL"]["Change (pp)"] + 12) < 1e-8

with patch("portfolio_xray_ui._security_type", side_effect=lambda ticker: (
    "ETF" if ticker == "VOO" else "STOCK"
)), patch("portfolio_xray_ui._cached_historical_issuer_holdings",
          side_effect=HistoricalHoldingsUnavailable("No prior report")):
    rows, info = _analyze(positions, {"VOO": requested})
assert info["historical_unavailable"] == ["VOO"]
assert "historical_comparison" not in info
assert any(r["Stock"] == "Unresolved VOO" for r in rows)

# The new Date value is read directly from each row. Direct stock dates
# remain metadata and do not trigger an ETF historical holdings request.
dated_positions = [
    {"ticker": "VOO", "amount": 60.0, "date": "2025-06-30"},
    {"ticker": "NVDA", "amount": 40.0, "date": "2024-12-31"},
]
with patch("portfolio_xray_ui._security_type", side_effect=lambda ticker: (
    "ETF" if ticker == "VOO" else "STOCK"
)), patch("portfolio_xray_ui._cached_historical_issuer_holdings",
          return_value=historical) as dated_fetch, patch(
    "portfolio_xray_ui._cached_issuer_holdings", return_value=latest,
):
    dated_rows, dated_info = _analyze(dated_positions)
assert dated_info["historical_dates"] == {"VOO": "2025-06-30"}
assert dated_fetch.call_count == 1
assert dated_fetch.call_args.args == ("VOO", requested)
assert abs(sum(r["_value"] for r in dated_rows) - 100.0) < 1e-8

state = {
    "portfolio_xray_saved_loaded_name": "Dated",
    "portfolio_xray_historical_result": "old time series",
    "portfolio_xray_row_count": 2,
    "portfolio_xray_ticker_0": "VOO",
    "portfolio_xray_amount_0": 60.0,
    "portfolio_xray_date_0": requested,
    "portfolio_xray_ticker_1": "",
    "portfolio_xray_amount_1": 0.0,
    "portfolio_xray_date_1": None,
}
with patch("portfolio_xray_ui.st.session_state", state):
    _portfolio_input_changed()
assert state["portfolio_xray_saved_loaded_name"] is None
assert "portfolio_xray_historical_result" not in state

print("PASS: dated ETF reports, missing SPY history, per-row look-through and edits")
