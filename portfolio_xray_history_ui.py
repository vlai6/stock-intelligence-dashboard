"""Historical Returns panel for the existing Portfolio X-Ray allocation."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_theme import style_blue_figure
from portfolio_xray_saved import (
    NS as SAVED_NS, _load_selected, loaded_portfolio_chart_name,
)
from portfolio_xray_history import (
    adjusted_history, portfolio_weights, simulate_returns,
    unsupported_assets, HistoricalCoverageError,
)


HISTORY_PORTFOLIO_KEY = "portfolio_xray_history_selected_portfolio"
HISTORY_RESULT_KEY = "portfolio_xray_historical_result"


def _change_history_portfolio() -> None:
    """Change the *main* X-Ray portfolio before Streamlit creates its widgets.

    This callback is shared with the main X-Ray session state, not a separate
    historical-only allocation. The existing saved-portfolio loader restores
    the editor, percent/dollar units, active name and auto-analysis request.
    """
    state = st.session_state
    name = state.get(HISTORY_PORTFOLIO_KEY)
    saved = state.get(SAVED_NS + "portfolios", {})
    if not isinstance(name, str) or name not in saved:
        return
    state[SAVED_NS + "selected"] = name
    _load_selected()
    # The previous time series belongs to another portfolio and must not be
    # visible while the newly loaded X-Ray allocation is being analyzed.
    state.pop(HISTORY_RESULT_KEY, None)


def _sync_history_portfolio_selection() -> list[str]:
    """Reflect whichever portfolio is actually loaded in the main X-Ray.

    Called before this selector is instantiated, after the main X-Ray controls
    have loaded/analyzed the current portfolio. Merely highlighting a different
    name in the top dropdown does not count as loading it.
    """
    state = st.session_state
    saved = state.get(SAVED_NS + "portfolios", {})
    names = list(saved) if isinstance(saved, dict) else []
    actual = loaded_portfolio_chart_name()
    selected = actual if actual in names else None
    if state.get(HISTORY_PORTFOLIO_KEY) != selected:
        state[HISTORY_PORTFOLIO_KEY] = selected
    return names


@st.cache_data(ttl=4 * 3600, show_spinner=False)
def _history_prices(
    symbols: tuple[str, ...], start: date, end: date,
) -> pd.DataFrame:
    return adjusted_history(symbols, start, end)


def render_historical_returns(
    analyzed_signature: tuple | None,
    analyzed_inputs_valid: bool,
) -> None:
    """Only use the holdings underlying the currently shown X-Ray analysis."""
    st.divider()
    st.markdown("#### HISTORICAL PORTFOLIO RETURNS")
    st.caption(
        "Hypothetical buy-and-hold of the entered allocation, without rebalancing. "
        "Adjusted ETF/stock prices include dividends and splits; returns are "
        "before taxes and fees."
    )
    # The selector and the main X-Ray share the SAME saved-portfolio loader.
    # Selection changes rerun the editor and its ETF look-through automatically.
    names = _sync_history_portfolio_selection()
    selector_col, date_col, run_col = st.columns(
        [2.1, 1.65, 1.9], gap="small", vertical_alignment="bottom"
    )
    with selector_col:
        st.selectbox(
            "Portfolio",
            options=names,
            index=None,
            placeholder=("Current / unsaved" if names else "No saved portfolios"),
            disabled=not names,
            key=HISTORY_PORTFOLIO_KEY,
            on_change=_change_history_portfolio,
            help="Choosing a saved portfolio also loads it into the main Portfolio X-Ray.",
        )
    if not analyzed_inputs_valid or not analyzed_signature:
        st.info("Analyze your current Portfolio X-Ray holdings to enable historical returns.")
        return
    try:
        unit, holdings = analyzed_signature
        positions = [{"ticker": ticker, "amount": float(amount)} for ticker, amount in holdings]
        weights = portfolio_weights(positions)
    except (TypeError, ValueError):
        st.warning("Re-analyze your portfolio to refresh the historical return inputs.")
        return

    today = date.today()
    latest = today - timedelta(days=1)
    default_start = max(date(2000, 1, 1), today - timedelta(days=365))
    with date_col:
        start = st.date_input(
            "Start date", value=default_start, min_value=date(2000, 1, 1),
            max_value=latest, key="portfolio_xray_history_start",
        )
    with run_col:
        clicked = st.button(
            "Calculate returns", type="primary",
            key="portfolio_xray_calculate_history", use_container_width=True,
        )

    unavailable = unsupported_assets(weights)
    if unavailable:
        amount = 100 * sum(unavailable.values())
        tickers = ", ".join(unavailable)
        st.warning(
            f"Complete portfolio returns cannot be calculated: direct Treasury "
            f"or other CUSIP positions ({tickers}) represent {amount:.2f}% "
            "of this allocation. Historical bond values and coupon cash flows "
            "are not available. No return is assumed for these positions."
        )

    signature = (analyzed_signature, start)
    cache_key = HISTORY_RESULT_KEY
    if clicked:
        st.session_state.pop(cache_key, None)
        if not unavailable:
            symbols = tuple(sorted(set(weights) - {"Cash & Cash Inv"} | {"SPY"}))
            try:
                with st.spinner("Retrieving dividend-adjusted historical prices…"):
                    prices = _history_prices(symbols, start, today + timedelta(days=1))
                    outcome = simulate_returns(positions, start, today, prices)
                st.session_state[cache_key] = (signature, outcome)
            except (HistoricalCoverageError, ValueError) as exc:
                st.warning(str(exc))
            except Exception:
                st.warning(
                    "Historical price data could not be retrieved right now. "
                    "Please retry later. No estimate was substituted."
                )

    saved = st.session_state.get(cache_key)
    if not saved or saved[0] != signature or unavailable:
        return
    data = saved[1]
    st.caption(
        f"Common observed closing dates: {data['start']} to {data['end']}. "
        "Initial allocation held without rebalancing; cash assumed 0% yield."
    )
    a, b, c = st.columns(3)
    a.metric("Portfolio return", f"{data['portfolio_pct']:+.2f}%")
    b.metric("SPY return", f"{data['spy_pct']:+.2f}%")
    c.metric("Excess return", f"{data['excess_pp']:+.2f} pp")
    chart = go.Figure()
    chart.add_trace(go.Scatter(
        x=data["chart"]["Date"], y=data["chart"]["Portfolio"],
        mode="lines", name="Portfolio", line=dict(width=2.7, color="#50B9F1"),
    ))
    chart.add_trace(go.Scatter(
        x=data["chart"]["Date"], y=data["chart"]["SPY"],
        mode="lines", name="SPY (dividends adjusted)",
        line=dict(width=2, color="#F3BD57"),
    ))
    chart.update_layout(
        height=360,
        xaxis_title="Date", yaxis_title="Growth of 100 (index, not dollars)",
        margin=dict(l=12, r=12, t=12, b=14),
        legend=dict(orientation="h", y=1.05, x=0),
        hovermode="x unified",
    )
    st.plotly_chart(style_blue_figure(chart), use_container_width=True)
    with st.expander("Returns and contributions by holding"):
        st.dataframe(
            data["contributions"], hide_index=True, use_container_width=True,
            column_config={
                "Starting weight %": st.column_config.NumberColumn(format="%.2f%%"),
                "Holding return %": st.column_config.NumberColumn(format="%+.2f%%"),
                "Contribution (pp)": st.column_config.NumberColumn(format="%+.2f"),
            },
        )
    st.caption(
        "Simulated historical performance is not your actual trading return. "
        "No transaction history, cash flows, tax impact, investment fees, or "
        "survivorship adjustment for today's holdings is included. "
        "Excess return = portfolio return minus SPY return in percentage points."
    )
