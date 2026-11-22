"""Compact two-column ETF + direct-stock X-ray on Investment Philosophy."""
from __future__ import annotations
from html import escape
import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_theme import style_blue_figure
from portfolio_xray_saved import (
    render_saved_portfolio_controls, loaded_portfolio_chart_name,
    portfolio_png_filename, NS as SAVED_NS,
)
from portfolio_xray_csv import parse_portfolio_csv
from portfolio_xray import (
    ticker_of, issuer_holdings, portfolio_rows, pie_data, pie_legend_labels,
    security_type, tickerinside_identifiers,
)

@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _cached_issuer_holdings(ticker: str):
    return issuer_holdings(ticker)


def _clean_positions(table: pd.DataFrame) -> list[dict]:
    """Validate ticker and positive amount; units are selected by CSV/editor mode."""
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
def _cached_tickerinside_identifiers() -> dict[str, str]:
    """Download the single-provider stock/ETF identifier catalogue once daily."""
    return tickerinside_identifiers()


def _security_type(ticker: str) -> str:
    """Identify stocks/ETFs via TickerInside; recognize known cash/CUSIPs locally."""
    symbol = ticker_of(ticker)
    if symbol == "Cash & Cash Inv" or re.fullmatch(r"\d[A-Z0-9]{8}", symbol):
        return "OTHER"
    return security_type(symbol, _cached_tickerinside_identifiers())


def _analyze(positions):
    classified, errors = [], {}
    for position in positions:
        try:
            kind = _security_type(position["ticker"])
        except Exception as exc:
            kind = "UNKNOWN"
            errors[position["ticker"]] = (
                "Unable to classify position using TickerInside: "
                + str(exc).splitlines()[0][:170]
            )
        classified.append({**position, "type": kind})
    etfs = {pos["ticker"] for pos in classified if pos["type"] == "ETF"}
    snapshots = {}
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


def _portfolio_input_changed():
    """Mark edited inputs as unsaved, retaining existing auto-row behavior."""
    st.session_state[SAVED_NS + "loaded_name"] = None
    _append_xray_row_when_started()


def _import_portfolio_csv():
    """Upload callback: assign input widget state before the editor renders."""
    upload = st.session_state.get("portfolio_xray_csv_file")
    if upload is None:
        return
    try:
        positions, unit, notices = parse_portfolio_csv(upload.getvalue())
    except ValueError as exc:
        st.session_state["portfolio_xray_csv_feedback"] = ("error", str(exc))
        return
    for index in range(30):
        row = positions[index] if index < len(positions) else None
        st.session_state[f"portfolio_xray_ticker_{index}"] = row["ticker"] if row else ""
        st.session_state[f"portfolio_xray_amount_{index}"] = (
            float(row["amount"]) if row else 0.0
        )
    st.session_state["portfolio_xray_row_count"] = min(30, len(positions) + 1)
    st.session_state["portfolio_xray_unit_mode"] = unit
    st.session_state["portfolio_xray_results"] = None
    st.session_state["portfolio_xray_auto_analyze"] = True
    st.session_state[SAVED_NS + "loaded_name"] = None
    st.session_state["portfolio_xray_csv_feedback"] = (
        "warning" if notices else "success",
        (f"Imported {len(positions)} positions in "
         + ("percentage" if unit == "pct" else "dollar")
         + " mode. " + " ".join(notices)),
    )


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
    /* Tighten portfolio inputs only: slightly shorter fields and row spacing. */
    .st-key-portfolio_xray_left [data-testid="stVerticalBlock"] {gap:0.55rem;}
    .st-key-portfolio_xray_left [data-testid="stTextInput"] [data-baseweb="input"],
    .st-key-portfolio_xray_left [data-testid="stNumberInput"] [data-baseweb="input"] {
        min-height:34px !important;
        height:34px !important;
    }
    .st-key-portfolio_xray_left [data-testid="stTextInput"] input,
    .st-key-portfolio_xray_left [data-testid="stNumberInput"] input {
        min-height:34px !important;
        height:34px !important;
        padding-top:0 !important;
        padding-bottom:0 !important;
    }
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
        render_saved_portfolio_controls()
        with st.popover("Import CSV", use_container_width=False):
            st.file_uploader(
                "Ticker, Amount CSV", type=["csv"],
                key="portfolio_xray_csv_file",
                on_change=_import_portfolio_csv,
                help="Exactly two columns: Ticker, Amount. All values must be "
                     "percentages (such as 12.29%) or all dollar amounts.",
            )
            st.caption(
                "Percentages are weights, not USD. Cash and Treasury CUSIPs "
                "stay as directly owned non-stock positions."
            )
        csv_feedback = st.session_state.pop("portfolio_xray_csv_feedback", None)
        if csv_feedback:
            status, message = csv_feedback
            getattr(st, status)(message)
        with st.container(key="portfolio_xray_left"):
            # Fresh portfolios start with SPY filled in and a blank second row.
            # Never overwrite previously entered values or a loaded saved portfolio.
            if "portfolio_xray_row_count" not in st.session_state:
                st.session_state.setdefault("portfolio_xray_ticker_0", "SPY")
                st.session_state["portfolio_xray_row_count"] = 2
            count = st.session_state["portfolio_xray_row_count"]
            input_unit = st.session_state.get("portfolio_xray_unit_mode", "usd")
            is_pct = input_unit == "pct"
            header_ticker, header_amount = st.columns([1, 1], gap="small")
            with header_ticker:
                st.caption("Ticker")
            with header_amount:
                st.caption("Weight (%)" if is_pct else "Amount ($)")
            for index in range(count):
                ticker_col, amount_col = st.columns([1, 1], gap="small")
                with ticker_col:
                    st.text_input(
                        f"Ticker {index + 1}",
                        key=f"portfolio_xray_ticker_{index}",
                        placeholder="e.g. SPY" if index == 0 else "Ticker",
                        label_visibility="collapsed",
                        on_change=_portfolio_input_changed,
                    )
                with amount_col:
                    st.number_input(
                        f"{'Weight (%)' if is_pct else 'Amount ($)'} {index + 1}",
                        key=f"portfolio_xray_amount_{index}",
                        min_value=0.0, step=0.1 if is_pct else 100.0, format="%.2f",
                        label_visibility="collapsed",
                        on_change=_portfolio_input_changed,
                    )
            submitted = st.button(
                "Analyze portfolio", type="primary", use_container_width=True,
                key="portfolio_xray_analyze",
            )
            st.caption(
                "Amounts are allocation percentages, not dollar values."
                if is_pct else "ETFs and individual stocks are identified automatically."
            )
            # Loading a saved portfolio queues this after widget state is restored.
            # Both Load and Analyze use the same validation and X-Ray pipeline.
            auto_analyze = bool(st.session_state.pop("portfolio_xray_auto_analyze", False))
            if submitted or auto_analyze:
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
                        st.session_state["portfolio_xray_results_unit"] = input_unit
                        st.session_state["portfolio_xray_results_signature"] = (
                            input_unit,
                            tuple((p["ticker"], float(p["amount"])) for p in positions),
                        )
                except Exception as exc:
                    st.session_state["portfolio_xray_results"] = None
                    st.session_state.pop("portfolio_xray_results_signature", None)
                    st.error(str(exc))
    with right:
        result = st.session_state.get("portfolio_xray_results")
        if not result:
            return  # Deliberately blank until the first Analyze action.
        rows, info = result
        result_is_pct = st.session_state.get("portfolio_xray_results_unit", "usd") == "pct"
        chart_portfolio_name = loaded_portfolio_chart_name()
        with st.container(key="portfolio_xray_right"):
            # Preserve a user's existing Table selection after the label rename.
            if st.session_state.get("portfolio_xray_display") == "Table":
                st.session_state["portfolio_xray_display"] = "Full Table"
            mode = st.segmented_control(
                "Display", ["Pie chart", "Full Table"],
                default="Pie chart", label_visibility="collapsed",
                key="portfolio_xray_display",
            )
            st.caption(
                (f"Imported allocation: {info['total']:.2f}%  ·  "
                 if result_is_pct else f"Total: USD {info['total']:,.2f}  ·  ")
                + f"Identified: {info['mapped']/info['total']:.1%}  ·  "
                + f"Positions: {sum(not row['Unresolved'] for row in rows)}"
            )
            if mode == "Full Table":
                if result_is_pct:
                    visible = [
                        {
                            "Ticker": r["Stock"],
                            "Portfolio %": r["Portfolio %"],
                            "ETF Allocation (%)": round(r["ETF Amount"], 3),
                            "Individual Allocation (%)": round(r["Direct Amount"], 3),
                        }
                        for r in rows
                    ]
                    column_config = {
                        "Portfolio %": st.column_config.NumberColumn(format="%.2f%%"),
                        "ETF Allocation (%)": st.column_config.NumberColumn(format="%.3f%%"),
                        "Individual Allocation (%)": st.column_config.NumberColumn(format="%.3f%%"),
                    }
                else:
                    visible = [
                        {
                            "Ticker": r["Stock"],
                            "Amount ($)": r["Amount ($)"],
                            "Portfolio %": r["Portfolio %"],
                            "ETF Amount ($)": r["ETF Amount"],
                            "Individual Amount ($)": r["Direct Amount"],
                        }
                        for r in rows
                    ]
                    column_config = {
                        "Amount ($)": st.column_config.NumberColumn(format="$%.2f"),
                        "Portfolio %": st.column_config.NumberColumn(format="%.2f%%"),
                        "ETF Amount ($)": st.column_config.NumberColumn(format="$%.2f"),
                        "Individual Amount ($)": st.column_config.NumberColumn(format="$%.2f"),
                    }
                st.dataframe(
                    pd.DataFrame(visible), hide_index=True,
                    height=250, use_container_width=True,
                    column_config=column_config,
                )
            else:
                labels, amounts = pie_data(rows)
                # Every holding remains in the pie, even below 1%. Emphasize
                # larger holdings with distinct colors; mute the tiny slices.
                total_pie = sum(amounts)
                percentages = [
                    100 * amount / total_pie if total_pie else 0.0
                    for amount in amounts
                ]
                major_palette = [
                    "#286C9F", "#6271B2", "#168CB1", "#3180B4",
                    "#556C99", "#26799A", "#7C98B5", "#4A91A8",
                    "#789CBA", "#416A85",
                ]
                pie_colors = []
                major_index = 0
                for index, (label, pct) in enumerate(zip(labels, percentages)):
                    if label in {"Unresolved ETF exposure", "Unclassified positions"}:
                        pie_colors.append("#8A929C")
                    elif pct >= 1.0:
                        pie_colors.append(major_palette[major_index % len(major_palette)])
                        major_index += 1
                    else:
                        pie_colors.append("#284558" if index % 2 == 0 else "#315469")
                legend_labels = pie_legend_labels(labels, amounts)
                # Plotly's outside text positions draw connector/leader lines
                # from every labeled slice. Keep the 1% threshold so the ETF
                # long tail is still present without hundreds of labels.
                slice_text = [
                    f"{label}  {pct:.1f}%" if pct >= 1.0 else ""
                    for label, pct in zip(labels, percentages)
                ]
                slice_text_positions = [
                    "outside" if pct >= 1.0 else "none"
                    for pct in percentages
                ]
                hover_description = (
                    "%{label}: %{value:.3f} percentage points "
                    "(%{percent} of imported positions)<extra></extra>"
                    if result_is_pct else
                    "%{label}: $%{value:,.2f} (%{percent})<extra></extra>"
                )
                chart_col, legend_col = st.columns([7, 3], gap="small")
                with chart_col:
                    fig = go.Figure(go.Pie(
                        labels=labels, values=amounts, hole=.58, sort=False,
                        # Outside labels have automatic leader lines. No label
                        # for holdings under 1%, but every slice remains.
                        text=slice_text, textinfo="text",
                        textposition=slice_text_positions,
                        outsidetextfont=dict(
                            family="Inter, Segoe UI, Arial, sans-serif",
                            size=12, color="#DDEAF7",
                        ),
                        automargin=True,
                        hovertemplate=hover_description,
                        marker=dict(colors=pie_colors, line=dict(color="#091624", width=0.4)),
                    ))
                    fig.update_layout(
                        # Extra vertical room lets Plotly place outside tickers
                        # without squeezing the donut or clipping connectors.
                        height=440, margin=dict(l=18, r=18, t=16, b=16),
                        showlegend=False,
                        annotations=[dict(text="Portfolio", x=.5, y=.5,
                                          showarrow=False, font=dict(
                                              family="Inter, Segoe UI, Arial, sans-serif",
                                              size=13, color="#B8D3E7",
                                          ))],
                    )
                    # The saved name becomes part of the exported image only
                    # when the currently analyzed positions match that portfolio.
                    # Unloaded or edited portfolios have no chart title.
                    if chart_portfolio_name:
                        fig.update_layout(
                            title=dict(
                                text=escape(chart_portfolio_name),
                                x=0.5, xanchor="center",
                                font=dict(
                                    family="Inter, Segoe UI, Arial, sans-serif",
                                    size=18, color="#DEEAF7",
                                ),
                            )
                        )
                    # Plotly exports the chart client-side, including outside
                    # ticker labels. No additional Python image dependency needed.
                    st.plotly_chart(
                        style_blue_figure(fig),
                        use_container_width=True,
                        config={
                            "displayModeBar": True,
                            "displaylogo": False,
                            # Keep one compact camera/export icon instead of
                            # Plotly's unrelated zoom/pan controls.
                            "modeBarButtons": [["toImage"]],
                            "toImageButtonOptions": {
                                "format": "png",
                                "filename": portfolio_png_filename(chart_portfolio_name),
                                "width": 1200,
                                "height": 650,
                                "scale": 2,
                            },
                        },
                    )
                with legend_col:
                    rows_html = [
                        '<div class="si-xray-legend-row">'
                        f'<span class="si-xray-legend-swatch" style="background:{color}"></span>'
                        f'<span class="si-xray-legend-ticker">{escape(str(label))}</span>'
                        f'<span class="si-xray-legend-percent">{escape(full.rsplit(" ", 1)[-1])}</span>'
                        '</div>'
                        for label, full, color, pct in zip(
                            labels, legend_labels, pie_colors, percentages
                        )
                        if pct >= 1.0
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
            if info["unresolved"] > (0.001 if result_is_pct else 0.01):
                unresolved_amount = (
                    f"{info['unresolved']:.3f} percentage points"
                    if result_is_pct else f"USD {info['unresolved']:,.2f}"
                )
                st.warning(
                    f"{unresolved_amount} of positions or ETF exposure could not "
                    "be verified against TickerInside holdings. Unverified "
                    "positions and missing ETF weights are not redistributed."
                )
            if info.get("other_assets", 0) > 0:
                known_nonstock = (
                    f"{info['other_assets']:.2f} percentage points"
                    if result_is_pct else f"USD {info['other_assets']:,.2f}"
                )
                st.caption(
                    f"Cash and Treasury CUSIPs: {known_nonstock} are retained as "
                    "separate non-stock positions, not converted into equities."
                )
            if info["failed"]:
                with st.expander("Unresolved holdings details", expanded=False):
                    for symbol, problem in info["failed"].items():
                        st.caption(f"{symbol}: {problem}")
            if info["sources"]:
                with st.expander("Source: TickerInside", expanded=False):
                    visible_sources = [
                        {name: entry.get(name, "") for name in ("ETF", "Coverage", "As of")}
                        for entry in info["sources"]
                    ]
                    st.dataframe(
                        pd.DataFrame(visible_sources), hide_index=True,
                        use_container_width=True,
                    )
                    st.markdown(
                        '<span style="font-size:0.78rem;color:#8FA7BC">'
                        'Stock/ETF identities and ETF holdings: '
                        '<a href="https://tickerinside.com" target="_blank" '
                        'rel="noopener noreferrer">TickerInside</a> (CC BY 4.0). '
                        'Holdings may come from dated SEC filings rather than live fund disclosures.'
                        '</span>',
                        unsafe_allow_html=True,
                    )
            st.caption("Ticker-level look-through; share classes remain separate. "
                       "ETF holdings dates may differ. Direct cash and Treasury holdings "
                       "remain separate; missing ETF exposure stays unresolved.")
