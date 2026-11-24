"""CSV-funded historical returns panel, independent of X-Ray holdings dates."""
from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256

import plotly.graph_objects as go
import streamlit as st

from dashboard_theme import style_blue_figure
from portfolio_xray_history import adjusted_history, HistoricalCoverageError
from portfolio_xray_purchase_history import (
    parse_purchase_csv, simulate_purchase_history,
)


RESULT_KEY = "portfolio_xray_purchase_csv_result"
SAMPLE_CSV = (
    "Portfolio,Date,Ticker,Amount\n"
    "Core ETFs,2024-01-16,VOO,100\n"
    "Core ETFs,2024-06-10,AVUV,30\n"
    "Growth,2024-01-16,QQQ,100\n"
    "Growth,2024-06-10,NVDA,30\n"
)


@st.cache_data(ttl=4 * 3600, show_spinner=False)
def _purchases_prices(symbols: tuple[str, ...], start: date, end: date):
    return adjusted_history(symbols, start, end)


def render_purchase_history() -> None:
    """Import scaled dated contributions, compare 1–5 strategies to SPY."""
    st.caption(
        "Privacy-first import: use actual purchase dates, but SCALE the purchase "
        "amounts before uploading. For example, divide EVERY purchase in one "
        "portfolio by the same private number: 50,000 to 100; 15,000 to 30. "
        "These relative units preserve percentage returns, but not actual dollar "
        "profits. Do not upload brokerage statements, account numbers or balances."
    )
    upload_col, example_col = st.columns([3, 1.4], gap="small")
    with upload_col:
        upload = st.file_uploader(
            "Scaled purchase history CSV", type=["csv"],
            key="portfolio_xray_purchase_history_upload",
            help="Date,Ticker,Amount for one portfolio; "
                 "Portfolio,Date,Ticker,Amount for 2–5 portfolios.",
        )
    with example_col:
        st.download_button(
            "CSV template", SAMPLE_CSV, "portfolio_purchases_template.csv",
            mime="text/csv", use_container_width=True,
            key="portfolio_xray_purchase_csv_template",
        )
    if upload is None:
        st.caption(
            "CSV format: Date,Ticker,Amount or Portfolio,Date,Ticker,Amount. "
            "Example: 2024-01-16,VOO,100 (scaled units). Include every "
            "historical buy you wish to model, not current portfolio weights. "
            "One constant scaling factor PER portfolio; never rescale "
            "individual transactions differently."
        )
        return

    raw = upload.getvalue()
    try:
        portfolios = parse_purchase_csv(raw)
    except ValueError as exc:
        st.error(str(exc))
        return

    names = list(portfolios)
    total_rows = sum(len(rows) for rows in portfolios.values())
    st.caption(
        f"Loaded {total_rows} dated purchases across {len(names)} "
        f"portfolio{'s' if len(names) != 1 else ''}: {', '.join(names)}."
    )
    st.warning(
        "Only buy transactions are simulated. Sales, withdrawals, cash, "
        "taxes and fees are NOT reconstructed. Historical adjusted daily "
        "closes approximate purchases and reinvestment. The upload travels "
        "to the Streamlit application server for processing, so remove "
        "personal identifiers and actual dollar amounts FIRST."
    )
    fingerprint = sha256(raw).hexdigest()
    if st.session_state.get("portfolio_xray_purchase_last_csv_hash") != fingerprint:
        st.session_state["portfolio_xray_purchase_last_csv_hash"] = fingerprint
        st.session_state["portfolio_xray_purchase_confirm"] = False
        st.session_state.pop(RESULT_KEY, None)
    confirmed = st.checkbox(
        "I replaced actual amounts with proportional purchase units, removed "
        "identifiers, and used actual purchase dates—not today's holdings weights.",
        key="portfolio_xray_purchase_confirm",
    )
    if st.button(
        "Calculate purchase-date returns", type="primary",
        disabled=not confirmed,
        key="portfolio_xray_purchase_csv_calculate",
    ):
        st.session_state.pop(RESULT_KEY, None)
        start = min(buy["date"] for records in portfolios.values() for buy in records)
        symbols = tuple(sorted(
            {"SPY"} | {
                buy["ticker"] for records in portfolios.values()
                for buy in records
            }
        ))
        try:
            with st.spinner("Calculating dated purchases and matched SPY investments…"):
                prices = _purchases_prices(
                    symbols, start, date.today() + timedelta(days=1)
                )
                result = simulate_purchase_history(
                    portfolios, prices, date.today()
                )
            st.session_state[RESULT_KEY] = (fingerprint, result)
        except (HistoricalCoverageError, ValueError) as exc:
            st.warning(str(exc))
        except Exception:
            st.warning(
                "Historical prices could not be retrieved for all purchases. "
                "No incomplete portfolio result was displayed."
            )

    saved = st.session_state.get(RESULT_KEY)
    if not saved or saved[0] != fingerprint:
        return
    result = saved[1]
    st.caption(
        f"Comparable performance window: {result['start']} to "
        f"{result['end']}. All series are rebased to 100 on the same "
        "first session; there is no artificial performance before purchases."
    )
    st.dataframe(
        result["summary"], hide_index=True, use_container_width=True,
        column_config={
            "Common-period return %": st.column_config.NumberColumn(format="%+.2f%%"),
            "SPY return %": st.column_config.NumberColumn(format="%+.2f%%"),
            "Excess return (pp)": st.column_config.NumberColumn(format="%+.2f"),
            "Invested (units)": st.column_config.NumberColumn(format="%.2f"),
            "Ending value (units)": st.column_config.NumberColumn(format="%.2f"),
            "Profit (units)": st.column_config.NumberColumn(format="%+.2f"),
            "SPY profit (units)": st.column_config.NumberColumn(format="%+.2f"),
        },
    )
    chart = go.Figure()
    colors = ["#50B9F1", "#BA8EFF", "#55D3B2", "#F099A6", "#81B1F4"]
    for idx, series in enumerate(result["series"]):
        chart.add_trace(go.Scatter(
            x=result["chart"]["Date"], y=result["chart"][series["key"]],
            mode="lines", name=series["name"],
            line=dict(color=colors[idx], width=2.6),
        ))
    chart.add_trace(go.Scatter(
        x=result["chart"]["Date"], y=result["chart"]["SPY"],
        mode="lines", name="SPY (same dates, dividends adjusted)",
        line=dict(color="#F3BD57", width=2, dash="dash"),
    ))
    chart.update_layout(
        height=390,
        xaxis_title="Date",
        yaxis_title="Cash-flow-adjusted growth of 100",
        margin=dict(l=12, r=12, t=16, b=14),
        legend=dict(orientation="h", y=1.15, x=0),
        hovermode="x unified",
    )
    st.plotly_chart(style_blue_figure(chart), use_container_width=True)
    st.caption(
        "Common-period return and SPY excess are time-weighted on identical "
        "dates. Invested amount, ending value, and profit use your normalized "
        "input units, NOT real USD. Relative amounts must preserve the "
        "sizes and dates of your original buys for accurate comparisons."
    )
