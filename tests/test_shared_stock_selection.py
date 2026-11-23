"""Regression, Metrics and Recent Sentiment must share one active stock.

Offline state tests don't import Streamlit pages or access Yahoo/Gemini.
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
files = {
    name: (ROOT / name).read_text(encoding="utf-8")
    for name in (
        "stock_selection.py", "scroll_dashboard.py",
        "regression_scanner/app.py", "pages/0_Stock_Intelligence.py",
        "pages/2_News_Sentiment.py",
    )
}
for name, code in files.items():
    ast.parse(code, filename=name)


def test_select_stock_only_on_explicit_actions_preserves_all_scan_filters():
    import stock_selection as shared
    state = {
        "primary": "NVDA",
        "loaded": True,
        "regression_chart_active_ticker": "NVDA",
        "regression_chart_active_years": 10.0,
        "regression_chart_lookback": 5,
        "scan_scope": "Top N by market cap",
        "regression_graph_stock_search": "NV",
        "si_continuous_mode": True,
    }
    with patch.object(shared.st, "session_state", state):
        assert shared.set_active_stock(" now ", source="scanner") is True
        assert state["primary"] == "NOW"
        assert state["regression_chart_active_ticker"] == "NOW"
        assert state["loaded"] is True
        assert state["selected_chart_ticker"] == "NOW"
        assert state[shared.CHART_INPUT_PENDING_KEY] == "NOW"
        assert state[shared.RERUN_SOURCE_KEY] == "scanner"
        assert state["regression_chart_active_years"] == 10.0
        assert state["regression_chart_lookback"] == 5
        assert state["scan_scope"] == "Top N by market cap"
        assert state["regression_graph_stock_search"] == "NV"
        assert state[shared.SENTIMENT_MODE_PENDING_KEY] is True

        # Re-selecting the same ticker should not request an expensive rerun.
        state.pop(shared.RERUN_SOURCE_KEY)
        assert shared.set_active_stock("NOW", source="scanner") is False
        assert shared.RERUN_SOURCE_KEY not in state

        # Other sections must update the same state and chart ticker.
        assert shared.set_active_stock("msft", source="metrics") is True
        assert state["primary"] == state["regression_chart_active_ticker"] == "MSFT"
        assert state[shared.RERUN_SOURCE_KEY] == "metrics"
        state.pop(shared.RERUN_SOURCE_KEY)
        assert shared.set_active_stock("aapl", source="sentiment") is True
        assert state["primary"] == state["regression_chart_active_ticker"] == "AAPL"
        assert state[shared.RERUN_SOURCE_KEY] == "sentiment"

        before = dict(state)
        with pytest.raises(ValueError):
            shared.set_active_stock("AAPL;DELETE", source="scanner")
        with pytest.raises(ValueError):
            shared.set_active_stock("AAPL", source="unknown")
        assert state == before


def test_inputs_are_applied_only_before_widget_render():
    import stock_selection as shared
    state = {"primary": "NOW", "si_metrics_ticker_draft": "unsent-value"}
    with patch.object(shared.st, "session_state", state):
        shared.sync_ticker_input("si_metrics_ticker_draft", "followed")
        assert state["si_metrics_ticker_draft"] == "NOW"
        state["si_metrics_ticker_draft"] = "TSLA"  # unsubmitted text
        shared.sync_ticker_input("si_metrics_ticker_draft", "followed")
        assert state["si_metrics_ticker_draft"] == "TSLA"
        state["primary"] = "CRM"
        shared.sync_ticker_input("si_metrics_ticker_draft", "followed")
        assert state["si_metrics_ticker_draft"] == "CRM"

        state[shared.CHART_INPUT_PENDING_KEY] = "CRM"
        state["regression_chart_input"] = "SPY"
        shared.sync_chart_input()
        assert state["regression_chart_input"] == "CRM"
        assert shared.CHART_INPUT_PENDING_KEY not in state


def test_table_and_run_graph_trigger_same_selection():
    scanner = files["regression_scanner/app.py"]
    assert scanner.count('set_active_stock(ticker, source="scanner")') == 2
    assert 'key="regression_chart_run", on_click=run_regression_graph' in scanner
    assert 'on_change=graph_checkbox_changed' in scanner
    assert 'st.session_state["graph_choice_epoch"]' in scanner
    assert 'sync_chart_input()' in scanner
    assert 'setdefault("regression_chart_active_ticker", selected_stock())' in scanner
    assert 'render_selected_channel(chart_ticker, last_completed_session(), active_years)' in scanner
    assert 'for progress in scan_market(settings):' in scanner


def test_metrics_selection_and_comparison_switch_share_stock():
    metrics = files["pages/0_Stock_Intelligence.py"]
    assert 'return set_active_stock(symbol, source="metrics")' in metrics
    assert 'on_click=switch_stock,' in metrics
    assert 'key="si_metrics_ticker_draft"' in metrics
    assert 'sync_ticker_input("si_metrics_ticker_draft",' in metrics
    assert 'if changed_stock and st.session_state.get("si_continuous_mode"):' in metrics
    assert 'st.rerun(scope="app")' in metrics


def test_sentiment_preset_does_not_override_external_ticker():
    sentiment = files["pages/2_News_Sentiment.py"]
    assert 'on_change=_sentiment_preset_ticker_changed' in sentiment
    assert 'on_change=_sentiment_mode_changed' in sentiment
    assert "st.session_state.pop('si_sentiment_preset_just_changed', False)" in sentiment
    assert 'set_active_stock(candidate, source="sentiment")' in sentiment
    assert 'key="si_sentiment_ticker_draft"' in sentiment
    assert "symbol = selected_stock()" in sentiment
    assert "st.session_state.pop(SENTIMENT_MODE_PENDING_KEY, False)" in sentiment
    assert sentiment.index("st.session_state.pop(SENTIMENT_MODE_PENDING_KEY, False)") < (
        sentiment.index("news_list_mode = st.selectbox")
    )
    assert "st.session_state['primary'] = candidate" not in sentiment
    assert "st.session_state['primary']=candidate" not in sentiment


def test_cross_fragment_refresh_only_on_actual_selection():
    dashboard = files["scroll_dashboard.py"]
    assert 'if st.session_state.get(RERUN_SOURCE_KEY) == section:' in dashboard
    assert 'st.session_state.pop(RERUN_SOURCE_KEY, None)' in dashboard
    assert 'st.rerun(scope="app")' in dashboard
    # Only one rerun dispatch in the dashboard, not a background polling loop.
    assert dashboard.count('st.rerun(scope="app")') == 1
    assert 'if section in st.session_state["si_loaded_sections"]:' in dashboard
