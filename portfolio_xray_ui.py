"""Compact two-column ETF + direct-stock X-ray on Investment Philosophy."""
from __future__ import annotations
from pathlib import Path
import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_theme import style_blue_figure
from portfolio_xray import (
    ticker_of, parse_file, issuer_holdings, portfolio_rows, pie_data,
)

@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _cached_issuer_holdings(ticker: str):
    return issuer_holdings(ticker)


def _clean_positions(table: pd.DataFrame) -> list[dict]:
    positions = []
    errors = []
    for index, raw in table.iterrows():
        kind = str(raw.get("Type", "ETF") or "ETF").strip()
        symbol = str(raw.get("Ticker", "") or "").strip()
        amount_raw = raw.get("Amount ($)", 0)
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            amount = 0.0
        if not symbol and not amount:
            continue
        if not symbol or amount <= 0:
            errors.append(f"Row {index + 1}: provide both ticker and positive amount.")
            continue
        if kind not in ("ETF", "Stock"):
            errors.append(f"Row {index + 1}: choose ETF or Stock.")
            continue
        try:
            symbol = ticker_of(symbol)
        except ValueError as exc:
            errors.append(f"Row {index + 1}: {exc}")
            continue
        positions.append({"type": kind, "ticker": symbol, "amount": amount})
    if errors:
        raise ValueError(" ".join(errors))
    if not positions:
        raise ValueError("Add an ETF or stock and a dollar amount.")
    if len(positions) > 30:
        raise ValueError("This tool supports up to 30 portfolio positions per analysis.")
    return positions


def _uploaded_holdings(files, etf_tickers: set[str]):
    """Associate uploads using TICKER.csv or TICKER-anything.xlsx naming."""
    uploaded, errors = {}, {}
    for item in files:
        prefix = re.split(r"[^A-Za-z0-9]", Path(item.name).stem.upper())[0]
        if prefix not in etf_tickers:
            errors[item.name] = "Name the file after a portfolio ETF, e.g. AVLV.csv"
            continue
        if prefix in uploaded:
            errors[item.name] = f"Two uploads were provided for {prefix}"
            continue
        try:
            uploaded[prefix] = parse_file(item.name, item.getvalue(), prefix)
        except Exception as exc:
            errors[prefix] = str(exc)
    return uploaded, errors


def _analyze(positions, files):
    etfs = {position["ticker"] for position in positions if position["type"] == "ETF"}
    snapshots, errors = _uploaded_holdings(files, etfs)
    for ticker in sorted(etfs):
        if ticker in snapshots:
            continue
        try:
            snapshots[ticker] = _cached_issuer_holdings(ticker)
        except Exception as exc:
            errors[ticker] = str(exc).splitlines()[0][:185]
    return portfolio_rows(positions, snapshots, errors)


def render_portfolio_xray():
    st.markdown("#### PORTFOLIO X-RAY")
    st.caption("Look through ETFs and directly held stocks to see combined stock exposure.")
    st.markdown("""
    <style>
    .st-key-portfolio_xray_left, .st-key-portfolio_xray_right {
       background:linear-gradient(150deg,rgba(8,20,34,.70),rgba(7,15,27,.60)) !important;
       border:1px solid rgba(71,120,158,.27);border-radius:12px;
       backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
       padding:10px 12px;
    }
    .st-key-portfolio_xray_left [data-testid="stForm"] {border:0 !important;padding:0 !important;}
    .st-key-portfolio_xray_left [data-testid="stDataFrame"] {max-height:228px;}
    .st-key-portfolio_xray_right [data-testid="stDataFrame"] {font-size:var(--si-type-data);}
    </style>
    """, unsafe_allow_html=True)

    left, right = st.columns([1, 1], gap="medium")
    with left:
        with st.container(key="portfolio_xray_left"):
            with st.form("portfolio_xray_inputs", border=False):
                editor = st.data_editor(
                    pd.DataFrame([
                        {"Type": "ETF", "Ticker": "", "Amount ($)": 0.0},
                        {"Type": "Stock", "Ticker": "", "Amount ($)": 0.0},
                    ]),
                    column_config={
                        "Type": st.column_config.SelectboxColumn(
                            "Type", options=["ETF", "Stock"], required=True, width="small"
                        ),
                        "Ticker": st.column_config.TextColumn(
                            "Ticker", help="An ETF or individual stock symbol", width="small"
                        ),
                        "Amount ($)": st.column_config.NumberColumn(
                            "Amount ($)", min_value=0.0, step=100.0,
                            format="$%.2f", width="medium"
                        ),
                    },
                    num_rows="dynamic", hide_index=True,
                    height=183, use_container_width=True,
                    key="portfolio_xray_editor",
                )
                with st.expander("ETF holdings file (if needed)", expanded=False):
                    uploads = st.file_uploader(
                        "Issuer CSV/XLSX files; name each as TICKER.csv or TICKER.xlsx",
                        type=["csv", "xlsx"], accept_multiple_files=True,
                        key="portfolio_xray_uploads", label_visibility="visible",
                    )
                submitted = st.form_submit_button(
                    "Analyze portfolio", type="primary", use_container_width=True
                )
            st.caption("Direct stocks need no file. ETF data use issuer holdings or an uploaded full-holdings file.")
            if submitted:
                try:
                    positions = _clean_positions(editor)
                    with st.spinner("Loading ETF holdings…"):
                        st.session_state["portfolio_xray_results"] = _analyze(positions, uploads or [])
                except Exception as exc:
                    st.session_state["portfolio_xray_results"] = None
                    st.error(str(exc))
    with right:
        result = st.session_state.get("portfolio_xray_results")
        if not result:
            return  # Deliberately blank until the first Analyze action.
        rows, info = result
        with st.container(key="portfolio_xray_right"):
            mode = st.segmented_control(
                "Display", ["Pie chart", "Table"],
                default="Pie chart", label_visibility="collapsed",
                key="portfolio_xray_display",
            )
            st.caption(
                f"Total: USD {info['total']:,.2f}  ·  "
                f"Mapped: {info['mapped']/info['total']:.1%}  ·  "
                f"Positions: {sum(not row['Unresolved'] for row in rows)}"
            )
            if mode == "Table":
                visible = [{k: r[k] for k in ("Stock", "Amount ($)", "Portfolio %", "From")}
                           for r in rows]
                st.dataframe(
                    pd.DataFrame(visible), hide_index=True,
                    height=250, use_container_width=True,
                    column_config={
                        "Amount ($)": st.column_config.NumberColumn(format="$%.2f"),
                        "Portfolio %": st.column_config.NumberColumn(format="%.2f%%"),
                    },
                )
                st.download_button(
                    "Download exposures CSV", data=pd.DataFrame(visible).to_csv(index=False),
                    file_name="portfolio_xray_exposure.csv", mime="text/csv",
                    use_container_width=True,
                )
            else:
                labels, amounts = pie_data(rows)
                fig = go.Figure(go.Pie(
                    labels=labels, values=amounts, hole=.58, sort=False,
                    textinfo="percent", textposition="inside",
                    hovertemplate="%{label}: $%{value:,.2f} (%{percent})<extra></extra>",
                    marker=dict(line=dict(color="#091624", width=1)),
                ))
                fig.update_layout(
                    height=280, margin=dict(l=4, r=4, t=4, b=4),
                    showlegend=True, legend=dict(
                        orientation="v", x=1.02, y=.5, xanchor="left",
                        font=dict(size=10), bgcolor="rgba(0,0,0,0)",
                    ),
                    annotations=[dict(text="Portfolio", x=.5, y=.5,
                                      showarrow=False, font=dict(size=12, color="#B8D3E7"))],
                )
                st.plotly_chart(style_blue_figure(fig), use_container_width=True,
                                config={"displayModeBar": False})
            if info["unresolved"] > 0.01:
                st.warning(
                    f"USD {info['unresolved']:,.2f} in ETF exposure could not be "
                    "resolved to stocks. Upload the missing fund's full-holdings "
                    "CSV/XLSX; amounts are not redistributed."
                )
            if info["failed"]:
                with st.expander("Unavailable holdings sources", expanded=False):
                    for symbol, problem in info["failed"].items():
                        st.caption(f"{symbol}: {problem}")
            if info["sources"]:
                with st.expander("Holdings sources and coverage", expanded=False):
                    st.dataframe(pd.DataFrame(info["sources"]), hide_index=True,
                                 use_container_width=True)
            st.caption("Ticker-level look-through; share classes remain separate. "
                       "ETF holdings dates may differ.")
