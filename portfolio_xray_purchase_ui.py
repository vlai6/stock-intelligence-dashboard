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
    "Core ETFs,2024-01-16,VOO,10000\n"
    "Core ETFs,2024-06-10,AVUV,3000\n"
    "Growth,2024-01-16,QQQ,10000\n"
    "Growth,2024-06-10,NVDA,3000\n"
)


@st.cache_data(ttl=4 * 3600, show_spinner=False)
def _purchases_prices(symbols: tuple[str, ...], start: date, end: date):
    return adjusted_history(symbols, start, end)


def render_purchase_history() -> None:
    """Import buys as dated dollar cash flows, compare 1–5 strategies to SPY."""
    st.caption(
        "Upload your actual purchase dates and dollar amounts (USD). "
        "Each CSV row is a BUY on that date, not an account weight or today's "
        "market value. Portfolio and SPY use the same contribution dates and "
        "amounts. The chart measures cash-flow-adjusted time-weighted returns."
    )
    upload_col, example_col = st.columns([3, 1.4], gap="small")
    with upload_col:
        upload = st.file_uploader(
            "Purchase history CSV", type=["csv"],
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
            "Example: 2024-01-16,VOO,10000. Include every historical buy "
            "you wish to model, not just currently held tickers."
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
        "Buy-only estimate: actual sells, transfers, trading prices, cash, "
        "taxes and fees are not reconstructed. This is NOT an actual "
        "brokerage-account performance statement. Dividend-adjusted daily "
        "closes approximate purchases and reinvestment."
    )
    fingerprint = sha256(raw).hexdigest()
    if st.button(
        "Calculate purchase-date returns", type="primary",
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
            "Total invested ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Ending value ($)": st.column_config.NumberColumn(format="$%.2f"),
            "Profit ($)": st.column_config.NumberColumn(format="$%+.2f"),
            "SPY profit ($)": st.column_config.NumberColumn(format="$%+.2f"),
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
        "Common-period return and SPY excess are time-weighted and use the "
        "same start/end dates. Invested dollars, ending value and dollar "
        "profit cover each portfolio's complete purchase history; because "
        "contribution timing differs, dollar profit is not a percentage return."
    )
