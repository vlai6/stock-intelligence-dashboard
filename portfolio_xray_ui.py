"""Compact two-column ETF + direct-stock X-ray on Investment Philosophy."""
from __future__ import annotations
from html import escape
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


def _append_xray_row_when_started():
    """Append one blank row when either last-row field has content.

    Ordinary Streamlit controls rerun on edit, so the next row is created
    without an extra Add Row button. Changing earlier rows adds nothing.
    """
    count = st.session_state.get("portfolio_xray_row_count", 1)
    if count >= 30:
        return
    last = count - 1
    ticker = str(st.session_state.get(f"portfolio_xray_ticker_{last}", "")).strip()
    amount = st.session_state.get(f"portfolio_xray_amount_{last}", 0.0)
    if ticker or (amount is not None and float(amount) > 0):
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
    /* Aligned holding and percentage columns, independent of name lengths. */
    .si-xray-legend {
        display:flex;
        flex-direction:column;
        justify-content:center;
        max-height:330px;
        overflow-y:auto;
        padding:6px 4px 6px 0;
        font:13px/1.35 Inter, "Segoe UI", Arial, sans-serif;
        color:#DEEAF7;
    }
    .si-xray-legend-row {
        display:grid;
        grid-template-columns:12px minmax(0, 1fr) 55px;
        gap:8px;
        align-items:center;
        padding:3px 0;
    }
    .si-xray-legend-heading {color:#96B2CA;font-size:12px;font-weight:600;}
    .si-xray-legend-ticker {min-width:0;overflow-wrap:anywhere;}
    .si-xray-legend-percent {text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;}
    .si-xray-legend-swatch {width:11px;height:11px;border-radius:2px;display:block;}
    </style>
    """, unsafe_allow_html=True)

    left, right = st.columns([2, 3], gap="medium")
    with left:
        with st.container(key="portfolio_xray_left"):
            # Exactly one initial row; entering a ticker OR dollar amount
            # adds the next blank row, without an Add Row button.
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
                        on_change=_append_xray_row_when_started,
                    )
                with amount_col:
                    st.number_input(
                        f"Amount ($) {index + 1}",
                        key=f"portfolio_xray_amount_{index}",
                        min_value=0.0, step=100.0, format="%.2f",
                        label_visibility="collapsed",
                        on_change=_append_xray_row_when_started,
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
                # Both the chart and its aligned legend use the same colors.
                pie_colors = [
                    "#286C9F", "#6271B2", "#168CB1", "#3180B4",
                    "#556C99", "#26799A", "#7C98B5", "#4A91A8",
                    "#789CBA", "#416A85", "#8A929C",
                ][:len(labels)]
                legend_labels = pie_legend_labels(labels, amounts)
                chart_col, legend_col = st.columns([7, 3], gap="small")
                with chart_col:
                    fig = go.Figure(go.Pie(
                        labels=labels, values=amounts, hole=.58, sort=False,
                        textinfo="percent", textposition="inside",
                        textfont=dict(family="Inter, Segoe UI, Arial, sans-serif", size=13),
                        hovertemplate="%{label}: $%{value:,.2f} (%{percent})<extra></extra>",
                        marker=dict(colors=pie_colors, line=dict(color="#091624", width=1)),
                    ))
                    fig.update_layout(
                        height=320, margin=dict(l=2, r=2, t=4, b=4),
                        showlegend=False,
                        annotations=[dict(text="Portfolio", x=.5, y=.5,
                                          showarrow=False, font=dict(
                                              family="Inter, Segoe UI, Arial, sans-serif",
                                              size=13, color="#B8D3E7",
                                          ))],
                    )
                    st.plotly_chart(style_blue_figure(fig), use_container_width=True,
                                    config={"displayModeBar": False})
                with legend_col:
                    rows_html = [
                        '<div class="si-xray-legend-row">'
                        f'<span class="si-xray-legend-swatch" style="background:{color}"></span>'
                        f'<span class="si-xray-legend-ticker">{escape(str(label))}</span>'
                        f'<span class="si-xray-legend-percent">{escape(full.rsplit(" ", 1)[-1])}</span>'
                        '</div>'
                        for label, full, color in zip(labels, legend_labels, pie_colors)
                    ]
                    st.markdown(
                        '<div class="si-xray-legend">'
                        '<div class="si-xray-legend-row si-xray-legend-heading">'
                        '<span></span><span>Holding</span>'
                        '<span class="si-xray-legend-percent">Portfolio %</span>'
                        '</div>'
                        + "".join(rows_html) + '</div>',
                        unsafe_allow_html=True,
                    )
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
