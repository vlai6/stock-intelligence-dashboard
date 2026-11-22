"""UI contract for the relocated Holdings Dates control (offline)."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

sources = {
    filename: (ROOT / filename).read_text(encoding="utf-8")
    for filename in (
        "portfolio_xray_ui.py",
        "portfolio_xray_history_ui.py",
        "portfolio_xray_holdings_dates_ui.py",
        "portfolio_xray_history_holdings.py",
    )
}
for filename, source in sources.items():
    ast.parse(source, filename=filename)

xray = sources["portfolio_xray_ui.py"]
history_ui = sources["portfolio_xray_history_ui.py"]
control = sources["portfolio_xray_holdings_dates_ui.py"]
history_source = sources["portfolio_xray_history_holdings.py"]

# Control is now under Historical Portfolio Returns, not the main editor.
assert 'with st.popover("Holdings Dates", use_container_width=True)' in control
assert '"ETF Holdings Date"' not in xray
assert '"ETF Holdings Date"' not in history_ui
assert "render_holdings_dates(etfs or [])" in history_ui
assert history_ui.index('st.markdown("#### HISTORICAL PORTFOLIO RETURNS")') < (
    history_ui.index("render_holdings_dates(etfs or [])")
)
assert "historical_dates = selected_holdings_dates(etfs_entered)" in xray
assert 'st.session_state["portfolio_xray_results"] = _analyze(positions, historical_dates)' in xray
assert "render_historical_returns(None, False, etfs_entered)" in xray
assert "render_historical_returns(" in xray and "etfs_entered," in xray

# Keep all the same date options and preserve on-change reanalysis.
for label in (
    "Latest available", "Historical as-of", "Default as-of date",
    "Individual ETF dates", "Use different dates per ETF",
):
    assert label in control
assert 'key=f"portfolio_xray_etf_asof_{ticker}"' in control
assert 'on_change=_holdings_date_changed' in control
assert 'st.session_state["portfolio_xray_auto_analyze"] = True' in control
assert 'st.session_state["portfolio_xray_results"] = None' in control

from portfolio_xray_holdings_dates_ui import (
    selected_holdings_dates, _holdings_date_changed,
)
test_date = date(2025, 11, 22)
state = {
    "portfolio_xray_holdings_mode": "Latest available",
    "portfolio_xray_holdings_date": test_date,
    "portfolio_xray_individual_etf_dates": True,
    "portfolio_xray_etf_asof_VGT": date(2022, 12, 31),
}
with patch("portfolio_xray_holdings_dates_ui.st.session_state", state):
    assert selected_holdings_dates(["SPY", "VGT"]) is None
    state["portfolio_xray_holdings_mode"] = "Historical as-of"
    assert selected_holdings_dates(["SPY", "VGT"]) == {
        "SPY": test_date,
        "VGT": date(2022, 12, 31),
    }
    state["portfolio_xray_individual_etf_dates"] = False
    assert selected_holdings_dates(["SPY", "VGT"]) == {
        "SPY": test_date, "VGT": test_date,
    }
    state["portfolio_xray_results"] = ([], {})
    state["portfolio_xray_results_signature"] = ("pct", (("VGT", 20.0),))
    state["portfolio_xray_historical_result"] = "stale"
    _holdings_date_changed()
    assert state["portfolio_xray_results"] is None
    assert "portfolio_xray_results_signature" not in state
    assert "portfolio_xray_historical_result" not in state
    assert state["portfolio_xray_auto_analyze"] is True

# Historical holdings still use the requested date, never latest as a fallback.
assert 'f"{URL_ROOT}/history/{symbol.lower()}/{as_of.isoformat()}.json"' in history_source
assert "if report_date > requested:" in history_source
assert 'result_info["historical_unavailable"]' in xray
assert 'result_info["historical_comparison"]' in xray
assert 'with st.expander("Compare Historical vs Latest ETF Exposure")' in xray

# Pricing/return-date calculations stay separate from historical ETF composition.
assert 'key="portfolio_xray_history_start"' in history_ui
assert '["Single Portfolio", "Compare Multiple Portfolios"]' in history_ui
print("PASS: relocated Holdings Dates UI and per-ETF date state drive main X-Ray")
