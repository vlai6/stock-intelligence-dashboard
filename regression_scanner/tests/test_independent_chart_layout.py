"""Regression Scanner: free ticker chart must precede full scan settings.

These static tests avoid importing the Streamlit page, which runs immediately
and would otherwise invoke live Yahoo requests during CI.
"""
from __future__ import annotations

import ast
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "app.py"
code = SCRIPT.read_text(encoding="utf-8")
tree = ast.parse(code, filename=str(SCRIPT))


def test_top_level_visual_order():
    header = code.index('st.subheader("REGRESSION ANALYSIS")')
    ticker = code.index('chart_query = st.text_input(')
    chart = code.index('render_selected_channel(chart_ticker, last_completed_session(), float(chart_years))')
    options = code.index('st.subheader("FULL ANALYSIS OPTIONS")')
    controls = code.index('with st.container(border=True):\n    # Make failures visible')
    scan = code.index('for progress in scan_market(settings):')
    table = code.rindex('with results_slot.container(key="regression_results_surface"):')
    assert header < ticker < chart < options < controls < scan < table


def test_any_ticker_not_just_saved_scan_results():
    functions = {
        node.name: node for node in tree.body if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        )
    }
    chart = functions["render_selected_channel"]
    assert [a.arg for a in chart.args.args] == ["ticker", "session", "saved_years"]
    chart_source = ast.get_source_segment(code, chart)
    assert "cached_chart_prices(ticker, session, saved_years)" in chart_source
    assert "make_channel_data(daily, saved_years, DAILY_BASIS)" in chart_source
    assert "selected_chart_ticker(view)" not in chart_source
    assert "view.loc[" not in chart_source
    assert "Saved scan Z-score" not in chart_source


def test_chart_entry_and_table_selection_share_ticker_state():
    assert 'st.session_state.setdefault("regression_chart_input", "SPY")' in code
    assert 'key="regression_chart_input"' in code
    assert "chart_ticker = str(chart_query).strip().upper()" in code
    assert 're.fullmatch(r"[A-Z0-9.^-]{1,18}", chart_ticker)' in code
    callback = ast.get_source_segment(
        code, next(x for x in tree.body
                   if isinstance(x, ast.FunctionDef)
                   and x.name == "graph_checkbox_changed")
    )
    assert 'st.session_state["regression_chart_input"] = checked[-1]' in callback
    assert "on_change=graph_checkbox_changed" in code
    assert 'key="regression_graph_stock_search"' in code


def test_existing_scanner_and_saved_results_remain():
    assert 'scan_market(settings)' in code
    assert 'render_saved_results(scope, top_n, min_cap, max_cap, length)' in code
    assert 'if scope == ETF_SCOPE and current_etf_symbol:' in code
    assert '"Calculate Intrinsic Value"' in code
    assert 'st.download_button("Download filtered CSV"' in code
    assert 'last_scan_error' in code
    assert 'st.session_state["last_run_complete"] = False' in code
    # No second copy of chart inside the saved results routine.
    assert "render_selected_channel(view, summary, report_session)" not in code
