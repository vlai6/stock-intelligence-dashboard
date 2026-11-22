"""Shared date controls for Portfolio X-Ray ETF constituent look-through.

The actual controls live under Historical Portfolio Returns; the X-Ray editor
reads the values before rendering so its analysis still refreshes automatically
when these controls change. Historical ETF composition is separate from price
returns, which continue to use original portfolio allocations.
"""
from __future__ import annotations

from datetime import date, timedelta
import streamlit as st


def _holdings_date_changed() -> None:
    """Refresh the main X-Ray when historical holdings settings change."""
    st.session_state["portfolio_xray_results"] = None
    st.session_state.pop("portfolio_xray_results_signature", None)
    st.session_state.pop("portfolio_xray_historical_result", None)
    st.session_state["portfolio_xray_auto_analyze"] = True


def selected_holdings_dates(etfs: list[str]) -> dict[str, date] | None:
    """Read already-selected dates before the main X-Ray runs its analysis."""
    if st.session_state.get("portfolio_xray_holdings_mode") != "Historical as-of":
        return None
    common = st.session_state.get(
        "portfolio_xray_holdings_date", date.today() - timedelta(days=365),
    )
    individual = st.session_state.get(
        "portfolio_xray_individual_etf_dates", False,
    )
    return {
        ticker: (
            st.session_state.get(f"portfolio_xray_etf_asof_{ticker}", common)
            if individual else common
        )
        for ticker in etfs
    }


def render_holdings_dates(etfs: list[str]) -> None:
    """Render a compact popover beneath HISTORICAL PORTFOLIO RETURNS."""
    with st.popover("Holdings Dates", use_container_width=True):
        choice = st.selectbox(
            "Holdings view", ["Latest available", "Historical as-of"],
            key="portfolio_xray_holdings_mode",
            on_change=_holdings_date_changed,
        )
        if choice != "Historical as-of":
            st.caption("Showing latest TickerInside holdings for each ETF.")
            return
        st.date_input(
            "Default as-of date",
            min_value=date(2019, 9, 30),
            max_value=date.today(),
            value=date.today() - timedelta(days=365),
            key="portfolio_xray_holdings_date",
            on_change=_holdings_date_changed,
        )
        st.caption(
            "Selects the most recent available quarterly SEC holdings "
            "at or before this date. Report dates differ by ETF."
        )
        if etfs:
            with st.expander("Individual ETF dates"):
                st.checkbox(
                    "Use different dates per ETF",
                    key="portfolio_xray_individual_etf_dates",
                    on_change=_holdings_date_changed,
                )
                if st.session_state.get("portfolio_xray_individual_etf_dates"):
                    for ticker in etfs:
                        st.date_input(
                            f"{ticker} as-of date",
                            min_value=date(2019, 9, 30),
                            max_value=date.today(),
                            value=st.session_state.get(
                                "portfolio_xray_holdings_date",
                                date.today() - timedelta(days=365),
                            ),
                            key=f"portfolio_xray_etf_asof_{ticker}",
                            on_change=_holdings_date_changed,
                        )
        st.caption(
            "Changes the ETF holdings shown in the X-Ray pie chart and "
            "Full Table. This does not change Historical Portfolio Returns, "
            "which uses the original allocation and historical market prices."
        )
        st.caption(
            "Historical coverage is not available for every ticker "
            "(for example, SPY). Missing holdings remain unresolved."
        )
