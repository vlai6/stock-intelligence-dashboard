"""Date | Ticker | Amount UI contract and dated ETF look-through checks."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sources = {
    path: (ROOT / path).read_text(encoding="utf-8")
    for path in (
        "portfolio_xray_ui.py", "portfolio_xray_history_ui.py",
        "portfolio_xray_dates.py", "portfolio_xray_csv.py",
        "portfolio_xray_history_holdings.py",
    )
}
for path, source in sources.items():
    ast.parse(source, filename=path)

xray = sources["portfolio_xray_ui.py"]
history_ui = sources["portfolio_xray_history_ui.py"]
csv = sources["portfolio_xray_csv.py"]
holder = sources["portfolio_xray_history_holdings.py"]

# The new first column is Date and the old popover is gone.
assert "header_date, header_ticker, header_amount = st.columns(" in xray
assert "date_col, ticker_col, amount_col = st.columns(" in xray
assert 'key=f"portfolio_xray_date_{index}"' in xray
assert xray.index('st.caption("Date")') < xray.index('st.caption("Ticker")')
assert '"Holdings Dates"' not in history_ui
assert '"ETF Holdings Date"' not in xray
assert 'render_holdings_dates' not in history_ui
assert "selected_holdings_dates" not in xray
assert "st.session_state[\"portfolio_xray_results\"] = _analyze(positions)" in xray
assert "position_signature(positions)" in xray

# The full date travels with input rows and CSV uploads/exports.
assert 'st.session_state[f"portfolio_xray_date_{index}"]' in xray
assert '"Date": st.session_state.get(f"portfolio_xray_date_{i}")' in xray
assert 'writer.writerow(["Date", "Ticker", "Amount"])' in csv
assert "has_date = len(headers) == 3" in csv
assert "historical_dates_for_positions(positions, etfs)" in xray
assert "if ticker in asof_dates:" in xray
assert '"historical_unavailable"' in xray
assert 'with st.expander("Compare Historical vs Latest ETF Exposure")' in xray

from portfolio_xray_dates import (
    normalized_position_date, position_signature,
    position_with_date, historical_dates_for_positions,
)
assert normalized_position_date(None) == ""
assert normalized_position_date(date(2025, 11, 22)) == "2025-11-22"
assert position_with_date("SPY", 10, None) == {"ticker": "SPY", "amount": 10.0}
assert position_with_date("VGT", 20, "2025-11-22") == {
    "ticker": "VGT", "amount": 20.0, "date": "2025-11-22",
}
assert position_signature([
    {"ticker": "SPY", "amount": 10},
    {"ticker": "VGT", "amount": 20, "date": "2025-11-22"},
]) == (("SPY", 10.0), ("VGT", 20.0, "2025-11-22"))

for invalid in ["2025/11/22", "2026-11-23", "2018-01-01", "not-a-date"]:
    try:
        normalized_position_date(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Invalid date accepted: {invalid}")

mixed = [
    {"ticker": "VGT", "amount": 10, "date": "2025-11-22"},
    {"ticker": "VGT", "amount": 20},
]
try:
    historical_dates_for_positions(mixed, {"VGT"})
except ValueError as exc:
    assert "different holdings dates" in str(exc)
else:
    raise AssertionError("Conflicting ETF dates must never be silently merged")

# Price-return dates are an independent calculation.
assert 'key="portfolio_xray_history_start"' in history_ui
assert '["Single Portfolio", "Compare Multiple Portfolios"]' in history_ui
assert 'f"{URL_ROOT}/history/{symbol.lower()}/{as_of.isoformat()}.json"' in holder
print("PASS: Date/Ticker/Amount editor, CSV and historical ETF date rules")
