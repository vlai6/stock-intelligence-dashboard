"""Shared selected-equity state across continuous-dashboard Streamlit fragments.

Only explicit selection actions update other sections. Typing, table sorting,
checkbox deselection, filtering, and changing chart settings alone do not.
Do not force expensive analysis on a keystroke: rerun the full dashboard once
per deliberate ticker change, with existing provider/Gemini/FinBERT caches.
"""
from __future__ import annotations

import re

import streamlit as st

DEFAULT_STOCK = "NVDA"
SELECTED_KEY = "primary"
RERUN_SOURCE_KEY = "si_stock_selection_needs_app_rerun"
CHART_INPUT_PENDING_KEY = "si_chart_input_pending_ticker"
SENTIMENT_MODE_PENDING_KEY = "si_sentiment_single_stock_pending"
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.^=-]{1,18}$")
ALLOWED_SOURCES = frozenset({"scanner", "metrics", "sentiment"})


def normalize_stock_ticker(raw: object) -> str:
    symbol = str(raw or "").strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("Enter a valid stock ticker.")
    return symbol


def selected_stock() -> str:
    return str(st.session_state.get(SELECTED_KEY) or DEFAULT_STOCK).upper()


def set_active_stock(raw: object, *, source: str) -> bool:
    """Commit one active ticker for the regression, metrics and news sections.

    Caller should use this only from an explicit click/submit, not while
    typing. Leave chart lookback and all scan filters unchanged. The chart's
    widget draft is synchronized at the start of its *own* section to avoid
    StreamlitWidgetAlreadyInstantiatedError when a later section changes it.
    """
    if source not in ALLOWED_SOURCES:
        raise ValueError("Unsupported stock-selection source.")
    ticker = normalize_stock_ticker(raw)
    state = st.session_state
    previous = str(state.get(SELECTED_KEY) or DEFAULT_STOCK).upper()
    prior_chart = str(
        state.get("regression_chart_active_ticker") or DEFAULT_STOCK
    ).upper()
    changed = ticker != previous or ticker != prior_chart or not state.get("loaded", False)

    state[SELECTED_KEY] = ticker
    state["loaded"] = True
    state["regression_chart_active_ticker"] = ticker
    # Preserve an unsent graph draft if another section simply reloads the
    # already active ticker. Run Graph still normalizes its own input.
    if changed or source == "scanner":
        state[CHART_INPUT_PENDING_KEY] = ticker
    state["selected_chart_ticker"] = ticker
    # When another section selects a stock, switch Recent Sentiment out of
    # any previously chosen scan preset. Otherwise its old Qualifying ticker
    # selector would misleadingly display a different stock.
    if changed and source != "sentiment":
        state[SENTIMENT_MODE_PENDING_KEY] = True
    if changed and state.get("si_continuous_mode"):
        state[RERUN_SOURCE_KEY] = source
    return changed


def sync_chart_input() -> None:
    """Call before constructing the regression_chart_input widget."""
    state = st.session_state
    pending = state.pop(CHART_INPUT_PENDING_KEY, None)
    if pending:
        state["regression_chart_input"] = pending


def sync_ticker_input(widget_key: str, followed_key: str) -> None:
    """Refresh a form draft only when another section selects a new stock.

    Preserves unsent text during unrelated same-stock reruns.
    Call before rendering the form's text input.
    """
    state = st.session_state
    active = selected_stock()
    if state.get(followed_key) != active:
        state[widget_key] = active
        state[followed_key] = active
