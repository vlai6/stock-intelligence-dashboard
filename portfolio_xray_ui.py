"""Compact two-column ETF + direct-stock X-ray on Investment Philosophy."""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_theme import style_blue_figure
from portfolio_xray import (
    ticker_of, issuer_holdings, portfolio_rows, pie_data, pie_legend_labels,
    security_type,
)

@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _cached_issuer_holdings(ticker: str):
    return issuer_holdings(ticker)


def _clean_positions(table: pd.DataFrame) -> list[dict]:
    """Only ticker and dollar amount are entered; no user-provided asset type."""
    positions, errors = [], []
    for index, raw in table.iterrows():
        symbol = str(raw.get("Ticker", "") or "").strip()
        amount_raw = raw.get("Amount ($)", 0)
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            amount = 0.0
        if not symbol and not amount:
            continue
        if not symbol or not (amount > 0):
            errors.append(f"Row {index + 1}: provide a ticker and positive amount.")
            continue
        try:
            symbol = ticker_of(symbol)
        except ValueError as exc:
            errors.append(f"Row {index + 1}: {exc}")
            continue
        positions.append({"ticker": symbol, "amount": amount})
    if errors:
        raise ValueError(" ".join(errors))
    if not positions:
        raise ValueError("Add at least one ticker and dollar amount.")
    if len(positions) > 30:
        raise ValueError("This tool supports up to 30 portfolio positions per analysis.")
    return positions


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _security_type(ticker: str) -> str:
    """Use known ETF identities or live quote metadata; never guess an unknown."""
    return security_type(ticker)


def _analyze(positions):
    classified = [
        {**position, "type": _security_type(position["ticker"])}
        for position in positions
    ]
    etfs = {pos["ticker"] for pos in classified if pos["type"] == "ETF"}
    snapshots, errors = {}, {}
    for ticker in sorted(etfs):
        try:
            snapshots[ticker] = _cached_issuer_holdings(ticker)
        except Exception as exc:
            errors[ticker] = str(exc).splitlines()[0][:185]
    return portfolio_rows(classified, snapshots, errors)


def _append_xray_row_when_complete():
    """Append one new blank row only after the final row is fully populated.

    Streamlit form inputs do not rerun on edit; ordinary controls with
    on_change callbacks allow a fresh row to appear immediately instead.
    """
    count = st.session_state.get("portfolio_xray_row_count", 1)
    if count >= 30:
        return
    last = count - 1
    ticker = str(st.session_state.get(f"portfolio_xray_ticker_{last}", "")).strip()
    amount = st.session_state.get(f"portfolio_xray_amount_{last}", 0.0)
    if ticker and amount is not None and float(amount) > 0:
        st.session_state["portfolio_xray_row_count"] = count + 1


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
            # Exactly one initial row. Filling both fields immediately creates
            # the next blank row, without a separate Add Row button.
            count = st.session_state.setdefault("portfolio_xray_row_count", 1)
            header_ticker, header_amount = st.columns([1, 1], gap="small")
            with header_ticker:
                st.caption("Ticker")
            with header_amount:
                st.caption("Amount ($)")
            for index in range(count):
                ticker_col, amount_col = st.columns([1, 1], gap="small")
                with ticker_col:
                    st.text_input(
                        f"Ticker {index + 1}",
                        key=f"portfolio_xray_ticker_{index}",
                        placeholder="e.g. SPY" if index == 0 else "Ticker",
                        label_visibility="collapsed",
                        on_change=_append_xray_row_when_complete,
                    )
                with amount_col:
                    st.number_input(
                        f"Amount ($) {index + 1}",
                        key=f"portfolio_xray_amount_{index}",
                        min_value=0.0, step=100.0, format="%.2f",
                        label_visibility="collapsed",
                        on_change=_append_xray_row_when_complete,
                    )
            submitted = st.button(
                "Analyze portfolio", type="primary", use_container_width=True,
                key="portfolio_xray_analyze",
            )
            st.caption("ETFs and individual stocks are identified automatically.")
            if submitted:
                editor = pd.DataFrame([
                    {
                        "Ticker": st.session_state.get(f"portfolio_xray_ticker_{i}", ""),
                        "Amount ($)": st.session_state.get(f"portfolio_xray_amount_{i}", 0.0),
                    }
                    for i in range(st.session_state["portfolio_xray_row_count"])
                ])
                try:
                    positions = _clean_positions(editor)
                    with st.spinner("Loading ETF holdings…"):
                        st.session_state["portfolio_xray_results"] = _analyze(positions)
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
            else:
                labels, amounts = pie_data(rows)
                legend_labels = pie_legend_labels(labels, amounts)
                fig = go.Figure(go.Pie(
                    labels=legend_labels, values=amounts, hole=.58, sort=False,
                    customdata=labels,
                    textinfo="percent", textposition="inside",
                    textfont=dict(family="Inter, Segoe UI, Arial, sans-serif", size=13),
                    hovertemplate="%{customdata}: $%{value:,.2f} (%{percent})<extra></extra>",
                    marker=dict(line=dict(color="#091624", width=1)),
                ))
                fig.update_layout(
                    height=280, margin=dict(l=4, r=4, t=4, b=4),
                    showlegend=True, legend=dict(
                        orientation="v", x=1.02, y=.5, xanchor="left",
                        font=dict(
                            family="Inter, Segoe UI, Arial, sans-serif",
                            size=13, color="#DEEAF7",
                        ), bgcolor="rgba(0,0,0,0)",
                    ),
                    annotations=[dict(text="Portfolio", x=.5, y=.5,
                                      showarrow=False, font=dict(
                                          family="Inter, Segoe UI, Arial, sans-serif",
                                          size=13, color="#B8D3E7",
                                      ))],
                )
                st.plotly_chart(style_blue_figure(fig), use_container_width=True,
                                config={"displayModeBar": False})
            if info["unresolved"] > 0.01:
                st.warning(
                    f"USD {info['unresolved']:,.2f} in ETF exposure could not be "
                    "resolved to stocks because full issuer holdings were unavailable. "
                    "Amounts are not redistributed."
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
                       "ETF holdings dates may differ. Unavailable funds stay unresolved.")
