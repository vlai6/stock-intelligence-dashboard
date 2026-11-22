"""UI contract tests for dated X-Ray look-through (no live network)."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ui = (ROOT / "portfolio_xray_ui.py").read_text(encoding="utf-8")
history = (ROOT / "portfolio_xray_history_holdings.py").read_text(encoding="utf-8")
for filename, source in [
    ("portfolio_xray_ui.py", ui),
    ("portfolio_xray_history_holdings.py", history),
]:
    ast.parse(source, filename=filename)

# Changing the date actually changes the ETF holdings fetch, not merely the
# pie legend or label. Default UI remains latest available.
assert 'with st.popover("ETF Holdings Date", use_container_width=True)' in ui
assert '["Latest available", "Historical as-of"]' in ui
assert 'st.date_input(\n            "Default as-of date"' in ui
assert 'st.checkbox(\n                    "Use different dates per ETF"' in ui
assert 'key=f"portfolio_xray_etf_asof_{ticker}"' in ui
assert 'historical_dates = _historical_date_settings(etfs_entered)' in ui
assert 'st.session_state["portfolio_xray_results"] = _analyze(positions, historical_dates)' in ui
assert '_cached_historical_issuer_holdings(' in ui

# Coverage and current-versus-historical comparisons must be surfaced,
# and directly held equities never undergo ETF look-through.
assert 'if historical:' in ui
assert 'result_info["historical_unavailable"]' in ui
assert 'result_info["historical_comparison"]' in ui
assert 'with st.expander("Compare Historical vs Latest ETF Exposure")' in ui
assert 'report dates:' in ui
assert '"Historical ETF<br>holdings"' in ui
assert 'latest_snapshots[ticker] = _cached_issuer_holdings(ticker)' in ui

# The server route is a known ticker and a validated date. No fallback to
# current holdings on an unavailable date.
assert 'f"{URL_ROOT}/history/{symbol.lower()}/{as_of.isoformat()}.json"' in history
assert 'if report_date > requested:' in history
assert '"holdings_at_date_not_enabled"' not in history  # generic 404 reason preserved
assert "historical report does not provide a valid holdings date." in history
assert 'def exposure_changes(' in history

# Historical price returns are a separate feature with the original input
# allocation; dated ETF composition does not modify original positions.
assert 'render_historical_returns(' in ui
assert 'st.session_state.get("portfolio_xray_results_signature")' in ui

print("PASS: per-ETF dates actually drive dated look-through and status warnings")
