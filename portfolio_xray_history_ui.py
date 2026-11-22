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
    adjusted_history, portfolio_weights, simulate_returns, simulate_multiple_returns,
    unsupported_assets, HistoricalCoverageError,
)


HISTORY_PORTFOLIO_KEY = "portfolio_xray_history_selected_portfolio"
HISTORY_RESULT_KEY = "portfolio_xray_historical_result"
HISTORY_MODE_KEY = "portfolio_xray_history_mode"
HISTORY_MULTI_KEY = "portfolio_xray_history_compare_portfolios"


def _reset_historical_results() -> None:
    """Mode or comparison selection changed; never display the old analysis."""
    st.session_state.pop(HISTORY_RESULT_KEY, None)


def _comparison_snapshot(names: list[str]) -> tuple:
    """Snapshot saved holdings so edits/overwrites invalidate old results."""
    saved = st.session_state.get(SAVED_NS + "portfolios", {})
    units = st.session_state.get(SAVED_NS + "units", {})
    if not isinstance(saved, dict) or len(names) != len(set(names)):
        raise ValueError("Select distinct saved portfolios.")
    if not 2 <= len(names) <= 5:
        raise ValueError("Select 2–5 saved portfolios to compare.")
    return tuple(
        (
            name,
            units.get(name, "usd") if isinstance(units, dict) else "usd",
            tuple((p["ticker"], float(p["amount"])) for p in saved[name]),
        )
        for name in names
    )


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


def _show_simulation_disclaimer() -> None:
    st.caption(
        "Simulated historical performance is not your actual trading return. "
        "No transaction history, cash flows, taxes, fees, or survivorship "
        "adjustment for today's holdings is included. "
        "Excess return = portfolio return minus SPY return, in percentage points."
    )


def _render_single_history(data: dict) -> None:
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
    _show_simulation_disclaimer()


def _render_multiple_history(data: dict) -> None:
    st.caption(
        f"Common observed closing dates: {data['start']} to {data['end']}. "
        "All portfolios are simulated on the same sessions with no rebalancing; "
        "cash assumes 0% yield."
    )
    st.metric("SPY return", f"{data['spy_pct']:+.2f}%")
    st.dataframe(
        data["summary"],
        hide_index=True, use_container_width=True,
        column_config={
            "Portfolio return %": st.column_config.NumberColumn(format="%+.2f%%"),
            "SPY return %": st.column_config.NumberColumn(format="%+.2f%%"),
            "Excess return (pp)": st.column_config.NumberColumn(format="%+.2f"),
        },
    )
    chart = go.Figure()
    colors = ["#50B9F1", "#BA8EFF", "#55D3B2", "#F099A6", "#81B1F4"]
    for idx, series in enumerate(data["series"]):
        chart.add_trace(go.Scatter(
            x=data["chart"]["Date"], y=data["chart"][series["key"]],
            name=series["name"], mode="lines",
            line=dict(width=2.5, color=colors[idx % len(colors)]),
        ))
    chart.add_trace(go.Scatter(
        x=data["chart"]["Date"], y=data["chart"]["SPY"],
        name="SPY (dividends adjusted)", mode="lines",
        line=dict(width=2.1, color="#F3BD57", dash="dash"),
    ))
    chart.update_layout(
        height=390,
        xaxis_title="Date", yaxis_title="Growth of 100 (index, not dollars)",
        margin=dict(l=12, r=12, t=16, b=14),
        legend=dict(orientation="h", y=1.15, x=0),
        hovermode="x unified",
    )
    st.plotly_chart(style_blue_figure(chart), use_container_width=True)
    with st.expander("Returns and contributions by portfolio"):
        detail = st.selectbox(
            "Portfolio details", options=list(data["outcomes"]),
            key="portfolio_xray_history_comparison_details",
        )
        if detail in data["outcomes"]:
            st.dataframe(
                data["outcomes"][detail]["contributions"],
                hide_index=True, use_container_width=True,
            )
    _show_simulation_disclaimer()


def render_historical_returns(
    analyzed_signature: tuple | None,
    analyzed_inputs_valid: bool,
) -> None:
    """Compare a single loaded X-Ray or 2–5 saved portfolios, on demand."""
    st.divider()
    st.markdown("#### HISTORICAL PORTFOLIO RETURNS")
    st.caption(
        "Hypothetical buy-and-hold of the entered allocation, without rebalancing. "
        "Adjusted ETF/stock prices include dividends and splits; returns are "
        "before taxes and fees."
    )
    names = _sync_history_portfolio_selection()

    # Compact option: the extra inputs are not rendered at all in the default
    # single-portfolio view.
    mode_col, _spacer = st.columns([2.3, 4.7], gap="small")
    with mode_col:
        mode = st.selectbox(
            "Analysis mode",
            ["Single Portfolio", "Compare Multiple Portfolios"],
            key=HISTORY_MODE_KEY,
            label_visibility="collapsed",
            on_change=_reset_historical_results,
        )

    is_compare = mode == "Compare Multiple Portfolios"
    today = date.today()
    latest = today - timedelta(days=1)
    default_start = max(date(2000, 1, 1), today - timedelta(days=365))
    selector_col, date_col, run_col = st.columns(
        [2.1, 1.65, 1.9], gap="small", vertical_alignment="bottom"
    )
    selected: list[str] = []
    with selector_col:
        if is_compare:
            # Preserve user choices across reruns, but discard deleted names.
            state = st.session_state
            current = state.get(HISTORY_MULTI_KEY)
            if not isinstance(current, list):
                current = []
                active = loaded_portfolio_chart_name()
                if active in names:
                    current = [active]
            state[HISTORY_MULTI_KEY] = [
                name for name in current if name in names
            ][:5]
            st.multiselect(
                "Portfolios to compare", options=names,
                key=HISTORY_MULTI_KEY, max_selections=5,
                placeholder="Select 2–5 saved portfolios",
                on_change=_reset_historical_results,
            )
            selected = list(st.session_state.get(HISTORY_MULTI_KEY, []))
        else:
            st.selectbox(
                "Portfolio", options=names, index=None,
                placeholder=("Current / unsaved" if names else "No saved portfolios"),
                disabled=not names, key=HISTORY_PORTFOLIO_KEY,
                on_change=_change_history_portfolio,
                help="Choosing a saved portfolio also loads it into the main Portfolio X-Ray.",
            )
    with date_col:
        start = st.date_input(
            "Start date", value=default_start, min_value=date(2000, 1, 1),
            max_value=latest, key="portfolio_xray_history_start",
        )
    with run_col:
        clicked = st.button(
            "Calculate returns", type="primary",
            disabled=is_compare and len(selected) < 2,
            key="portfolio_xray_calculate_history", use_container_width=True,
        )

    if is_compare:
        if len(selected) < 2:
            st.caption("Select at least two saved portfolios to enable comparison.")
            return
        saved = st.session_state.get(SAVED_NS + "portfolios", {})
        try:
            snapshot = _comparison_snapshot(selected)
            portfolios = {
                name: [{"ticker": t, "amount": amount} for t, amount in holdings]
                for name, _unit, holdings in snapshot
            }
            signature = ("compare", snapshot, start)
        except (KeyError, TypeError, ValueError) as exc:
            st.warning(f"Unable to compare selected portfolios: {exc}")
            return
        if clicked:
            st.session_state.pop(HISTORY_RESULT_KEY, None)
            try:
                symbols = {"SPY"}
                for name, positions in portfolios.items():
                    weights = portfolio_weights(positions)
                    unsupported = unsupported_assets(weights)
                    if unsupported:
                        missing_pct = sum(unsupported.values()) * 100
                        raise HistoricalCoverageError(
                            f"{name}: direct Treasury/CUSIP holdings "
                            f"({', '.join(sorted(unsupported))}) represent "
                            f"{missing_pct:.2f}% of this portfolio. Reliable "
                            "historical bond values and coupons are unavailable."
                        )
                    symbols.update(weights.keys())
                symbols.discard("Cash & Cash Inv")
                with st.spinner("Loading historical prices for selected portfolios…"):
                    prices = _history_prices(
                        tuple(sorted(symbols)), start, today + timedelta(days=1)
                    )
                    result = simulate_multiple_returns(
                        portfolios, start, today, prices
                    )
                st.session_state[HISTORY_RESULT_KEY] = (signature, result)
            except (HistoricalCoverageError, ValueError) as exc:
                st.warning(str(exc))
            except Exception:
                st.warning(
                    "Historical prices could not be retrieved for all selected "
                    "portfolios. Please retry; no incomplete comparison is shown."
                )
    else:
        if not analyzed_inputs_valid or not analyzed_signature:
            st.info("Analyze your current Portfolio X-Ray holdings to enable historical returns.")
            return
        try:
            _unit, holdings = analyzed_signature
            positions = [
                {"ticker": ticker, "amount": float(amount)}
                for ticker, amount in holdings
            ]
            weights = portfolio_weights(positions)
        except (TypeError, ValueError):
            st.warning("Re-analyze your portfolio to refresh the historical return inputs.")
            return

        unsupported = unsupported_assets(weights)
        if unsupported:
            amount = sum(unsupported.values()) * 100
            st.warning(
                "Complete portfolio returns cannot be calculated: "
                f"direct Treasury/CUSIP positions ({', '.join(unsupported)}) "
                f"represent {amount:.2f}% of the allocation. Reliable "
                "historical bond prices and cash flows are unavailable."
            )
        signature = ("single", analyzed_signature, start)
        if clicked:
            st.session_state.pop(HISTORY_RESULT_KEY, None)
            if not unsupported:
                symbols = tuple(sorted(
                    (set(weights) - {"Cash & Cash Inv"}) | {"SPY"}
                ))
                try:
                    with st.spinner("Retrieving dividend-adjusted historical prices…"):
                        prices = _history_prices(
                            symbols, start, today + timedelta(days=1)
                        )
                        result = simulate_returns(
                            positions, start, today, prices
                        )
                    st.session_state[HISTORY_RESULT_KEY] = (signature, result)
                except (HistoricalCoverageError, ValueError) as exc:
                    st.warning(str(exc))
                except Exception:
                    st.warning(
                        "Historical price data could not be retrieved right now. "
                        "Please retry; no estimate was substituted."
                    )

    saved_result = st.session_state.get(HISTORY_RESULT_KEY)
    if not saved_result or saved_result[0] != signature:
        return
    if is_compare:
        _render_multiple_history(saved_result[1])
    elif not unsupported:
        _render_single_history(saved_result[1])
