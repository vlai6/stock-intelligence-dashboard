"""Historical Returns selects the same saved portfolio as main X-Ray.

Use Streamlit callbacks before widget construction, so switching in the
historical section cannot raise WidgetAlreadyInstantiatedError or leave
the main X-Ray showing another portfolio.
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in ("portfolio_xray_ui.py", "portfolio_xray_history_ui.py"):
    ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)

from portfolio_xray_history_ui import (
    HISTORY_PORTFOLIO_KEY, HISTORY_RESULT_KEY,
    _change_history_portfolio, _sync_history_portfolio_selection,
)
from portfolio_xray_saved import NS

state = {
    NS + "portfolios": {
        "Core ETFs": [{"ticker": "SPY", "amount": 100.0}],
        "Target Allocation": [
            {"ticker": "AAPL", "amount": 20.0},
            {"ticker": "NVDA", "amount": 80.0},
        ],
    },
    NS + "units": {"Core ETFs": "usd", "Target Allocation": "pct"},
    NS + "selected": "Core ETFs",
    NS + "loaded_name": "Core ETFs",
    "portfolio_xray_row_count": 2,
    "portfolio_xray_ticker_0": "SPY",
    "portfolio_xray_amount_0": 100.0,
    "portfolio_xray_ticker_1": "",
    "portfolio_xray_amount_1": 0.0,
    "portfolio_xray_unit_mode": "usd",
    "portfolio_xray_results": ([], {"total": 100.0}),
    "portfolio_xray_results_signature": ("usd", (("SPY", 100.0),)),
    HISTORY_RESULT_KEY: (("old",), {"portfolio_pct": 10.0}),
}

with patch("portfolio_xray_history_ui.st.session_state", state), patch(
    "portfolio_xray_saved.st.session_state", state
):
    # Changing the TOP selector without loading must NOT change what the
    # historical selector shows. It follows the actively analyzed portfolio.
    state[NS + "selected"] = "Target Allocation"
    names = _sync_history_portfolio_selection()
    assert names == ["Core ETFs", "Target Allocation"]
    assert state[HISTORY_PORTFOLIO_KEY] == "Core ETFs"

    # Selecting in the historical section immediately updates the MAIN
    # selector, inputs, units and automatic look-through request.
    state[HISTORY_PORTFOLIO_KEY] = "Target Allocation"
    _change_history_portfolio()
    assert state[NS + "selected"] == "Target Allocation"
    assert state[NS + "loaded_name"] == "Target Allocation"
    assert state["portfolio_xray_row_count"] == 3
    assert state["portfolio_xray_ticker_0"] == "AAPL"
    assert state["portfolio_xray_amount_1"] == 80.0
    assert state["portfolio_xray_ticker_2"] == ""
    assert state["portfolio_xray_amount_2"] == 0.0
    assert state["portfolio_xray_unit_mode"] == "pct"
    assert state["portfolio_xray_auto_analyze"] is True
    assert state["portfolio_xray_results"] is None
    assert "portfolio_xray_results_signature" not in state
    assert HISTORY_RESULT_KEY not in state

    # Once the main X-Ray has automatically analyzed its new holdings,
    # the historical selector reflects the newly loaded portfolio.
    state["portfolio_xray_results"] = ([], {"total": 100})
    state["portfolio_xray_results_signature"] = (
        "pct", (("AAPL", 20.0), ("NVDA", 80.0))
    )
    assert _sync_history_portfolio_selection() == names
    assert state[HISTORY_PORTFOLIO_KEY] == "Target Allocation"

    # Main selector/load controls can switch back; history follows them.
    state[NS + "selected"] = "Core ETFs"
    from portfolio_xray_saved import _load_selected
    _load_selected()
    state["portfolio_xray_results"] = ([], {"total": 100})
    state["portfolio_xray_results_signature"] = ("usd", (("SPY", 100.0),))
    _sync_history_portfolio_selection()
    assert state[HISTORY_PORTFOLIO_KEY] == "Core ETFs"

    # Unsaved edits must remove the historical selector's saved label.
    state[NS + "loaded_name"] = None
    _sync_history_portfolio_selection()
    assert state[HISTORY_PORTFOLIO_KEY] is None

    # A removed or invalid selected name must never load another portfolio.
    state[HISTORY_PORTFOLIO_KEY] = "Does not exist"
    before = state[NS + "selected"]
    _change_history_portfolio()
    assert state[NS + "selected"] == before

print("PASS: historical portfolio selector syncs and loads the main X-Ray")
