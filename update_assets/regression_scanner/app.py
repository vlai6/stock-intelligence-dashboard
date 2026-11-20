"""Streamlit dashboard for interactive, incremental regression scans.

Launch in VS Code (Windows):
  python -m streamlit run app.py
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import datetime
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

# Scanner imports remain local even when the page is launched from the parent app.
_SCANNER_DIR = str(Path(__file__).resolve().parent)
if _SCANNER_DIR not in sys.path:
    sys.path.insert(0, _SCANNER_DIR)

import pandas as pd
import streamlit as st
from dashboard_theme import apply_dashboard_theme, render_page_header, style_blue_figure

from storage import data_root
from channel_chart import (
    DAILY_BASIS, BAND_OPTIONS, DEFAULT_BANDS,
    download_chart_prices, make_channel_data, channel_figure,
)
from lookback import regression_sessions
from intrinsic_value import enrich_table_rows
from regression_scanner.scanner import ScanSettings, scan_market, last_completed_session
from universe import MAX_SCREENER_PAGES
from etf_holdings import normalize_symbol
from etf_full_holdings import get_etf_constituents
from etf_scan_results import etf_report_dir, load_etf_scores

ROOT = data_root()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_FILE = ROOT / "results" / "latest_scan.csv"
SUMMARY_FILE = ROOT / "results" / "summary.json"
SKIP_FILE = ROOT / "results" / "skipped.csv"
TZ = ZoneInfo("America/New_York")

TOP_N_SCOPE = "Top N by market cap"
MAX_SCOPE = "Maximum available (experimental)"
CUSTOM_SCOPE = "Custom tickers (diagnostic)"
ETF_SCOPE = "ETF holdings"
SCREENER_RECORD_SAFETY_CAP = MAX_SCREENER_PAGES * 250

# Per-option explanations appear when hovering directly over the scope buttons.
SCOPE_TOOLTIPS = {
    TOP_N_SCOPE: (
        "Scan the largest N stocks **within your selected market-cap range**. "
        "You choose N below (for example, 500). Stocks still need to pass "
        "the regression and history filters to appear in results."
    ),
    MAX_SCOPE: (
        "Attempt to scan **every eligible stock** in your market-cap range. "
        "Large scans can take a long time, hit Yahoo rate limits, or stop "
        "at the stock-discovery safeguard."
    ),
    CUSTOM_SCOPE: (
        "Scan only ticker symbols you type (for example, AAPL, MSFT, NVDA). "
        "This is for testing; it bypasses the market-cap and listing filters."
    ),
    ETF_SCOPE: (
        "Run the same regression calculation across available ETF equity holdings. "
        "The dashboard first loads published full holdings, falling back to Yahoo top holdings only when unavailable."
    ),
}


def choose_scope(value: str) -> None:
    """Set scan scope before Streamlit reruns the script for the clicked button."""
    st.session_state["scan_scope"] = value


# Page configuration comes from the parent Stock Intelligence router.

if "scan_scope" not in st.session_state:
    st.session_state["scan_scope"] = TOP_N_SCOPE

COLUMN_CONFIG = {
    "ticker": st.column_config.TextColumn("Ticker"),
    "name": st.column_config.TextColumn("Company", width="medium"),
    "market_cap_b": st.column_config.NumberColumn("Market cap ($B)", format="%.1f",
        help="Company market capitalization in billions of USD."),
    "close": st.column_config.NumberColumn("Close", format="$%.2f",
        help="Closing stock price used for the scan. Not a live quote."),
    "z_score": st.column_config.NumberColumn("Z-score (σ)", format="%.2f",
        help="How many residual standard deviations the current closing price is from its fitted regression trend. Negative means below trend."),
    "lower_3": st.column_config.NumberColumn("−3σ price", format="$%.2f",
        help="Lower regression band at minus three residual standard deviations; this is not a fundamental price target."),
    "lower_4": st.column_config.NumberColumn("−4σ price", format="$%.2f",
        help="Lower regression band at minus four residual standard deviations; this is not intrinsic value."),
    # These columns are shown ONLY after the on-demand button is clicked.
    # Text columns display an explicit N/A when company financials are unavailable.
    "intrinsic_value": st.column_config.TextColumn(
        "Intrinsic Value", width="medium",
        help="Estimated fair value per share from a five-year discounted cash-flow (DCF) model. "
             "This is a scenario estimate, not a price target or guaranteed value."
    ),
    "upside_downside_pct": st.column_config.NumberColumn(
        "Upside / Downside %", width="medium", format="%+.1f%%",
        help="(Estimated intrinsic value ÷ current share price − 1) × 100. "
             "Positive means the model estimates potential upside; negative means downside. "
             "It is not a forecast."
    ),
    "margin_of_safety_pct": st.column_config.NumberColumn(
        "Margin of Safety %", width="medium", format="%+.1f%%",
        help="(Estimated intrinsic value − current price) ÷ estimated intrinsic value × 100. "
             "Positive means the share trades below the modeled value. "
             "Negative means it trades above it. This is not protection from losses."
    ),
    "tradingview": st.column_config.LinkColumn("TradingView", display_text="Open chart"),
}
# Default: a clean regression-only table. The second view replaces this one
# after a deliberate click; both versions use the same Streamlit data editor.
VISIBLE_COLUMNS = ["ticker", "name", "market_cap_b", "close", "z_score",
                   "lower_3", "lower_4", "tradingview"]
VALUATION_COLUMNS = ["intrinsic_value", "upside_downside_pct", "margin_of_safety_pct"]
VALUED_COLUMNS = [*VISIBLE_COLUMNS[:-1], *VALUATION_COLUMNS, VISIBLE_COLUMNS[-1]]


def format_intrinsic_cell(value: object, kind: str) -> str:
    """Format an optional DCF metric for the dashboard (including literal N/A)."""
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return "N/A"
    number = float(numeric)
    if kind == "intrinsic_value":
        return f"${number:,.2f}"
    return f"{number:+.1f}%"



def prepare_intrinsic_display(frame: pd.DataFrame) -> pd.DataFrame:
    """Preserve percentage values as numbers for proper column-header sorting."""
    display = frame.copy()
    display["intrinsic_value"] = display["intrinsic_value"].map(
        lambda val: format_intrinsic_cell(val, "intrinsic_value")
    )
    for metric_name in ("upside_downside_pct", "margin_of_safety_pct"):
        display[metric_name] = pd.to_numeric(display[metric_name], errors="coerce")
    return display


def attach_intrinsic_values(frame: pd.DataFrame, values: pd.DataFrame | None) -> pd.DataFrame:
    """Add DCF columns without changing membership or existing scanner data."""
    base = frame.drop(columns=[*VALUATION_COLUMNS, "valuation_confidence"], errors="ignore").copy()
    if values is not None and not values.empty and "ticker" in values.columns:
        extra = values[[c for c in ["ticker", *VALUATION_COLUMNS] if c in values.columns]]
        extra = extra.drop_duplicates(subset=["ticker"], keep="last")
        base = base.merge(extra, on="ticker", how="left", validate="many_to_one", sort=False)
    for col in VALUATION_COLUMNS:
        if col not in base.columns:
            base[col] = float("nan")
    return base


def only_complete_intrinsic_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Hide rows with any unavailable DCF metric; never mutate scan data."""
    if any(column not in frame.columns for column in VALUATION_COLUMNS):
        return frame.iloc[0:0].copy()
    valid = pd.Series(True, index=frame.index)
    for column in VALUATION_COLUMNS:
        valid &= pd.to_numeric(frame[column], errors="coerce").notna()
    return frame.loc[valid].copy()


def highlight_deviation_row(row: pd.Series) -> list[str]:
    """Tint the entire row by deviation. -4σ takes priority over -3σ."""
    z_score = pd.to_numeric(row.get("z_score"), errors="coerce")
    if pd.isna(z_score):
        return [""] * len(row)
    if z_score <= -4:
        # Subtle green for the deepest deviations.
        shade = "background-color: rgba(30, 175, 85, 0.22)"
    elif z_score <= -3:
        # Subtle yellow-green / lime for -3σ to -4σ.
        shade = "background-color: rgba(183, 220, 48, 0.20)"
    else:
        shade = ""
    return [shade] * len(row)


def styled_stock_table(frame: pd.DataFrame):
    """Keep Streamlit's regular table, formatting, sorting, and chart links."""
    return frame.style.apply(highlight_deviation_row, axis=1)


def render_saved_scan_parameters(
    summary: dict, report_session: str, displayed_count: int,
    total_results: int, display_filter: str, search: str, sorting: str,
) -> None:
    """Screenshot-friendly provenance, based on SAVED scan settings, not sidebar inputs."""
    saved_filters = summary.get("filters", {}) or {}
    if saved_filters:
        if saved_filters.get("custom_symbols"):
            scope_label = "Custom tickers"
            cap_label = "Not applied (custom tickers)"
        else:
            limit = saved_filters.get("top_n_limit")
            scope_label = f"Top {int(limit):,} by market cap" if limit is not None else "Maximum available"
            low = saved_filters.get("min_cap_b")
            high = saved_filters.get("max_cap_b")
            if low is None:
                cap_label = "Not recorded"
            elif high is None:
                cap_label = f"${float(low):g}B+"
            else:
                cap_label = f"${float(low):g}B–${float(high):g}B"
        lookback = saved_filters.get("regression_years")
        sessions = saved_filters.get("regression_sessions")
        if lookback is None:
            lookback_label = "Not recorded"
        else:
            lookback_label = f"{float(lookback):g} years"
            if sessions is not None:
                lookback_label += f" · {int(sessions):,} sessions"
    else:
        scope_label = cap_label = lookback_label = "Not recorded (older scan)"

    complete = summary.get("complete")
    quality_label = ("Complete" if complete is True else
                     "Incomplete / data errors" if complete is False else
                     "Not recorded")
    candidates = summary.get("candidates")
    candidate_label = f"{int(candidates):,}" if candidates is not None else "Unknown"

    with st.expander("Saved scan details & coverage", expanded=False):
        st.markdown("**Scan parameters — saved run**")
        universe_col, market_col, timeframe_col, session_col = st.columns([1.3, 1.1, 1.5, 1.0])
        universe_col.caption("**Scan scope**")
        universe_col.write(scope_label)
        market_col.caption("**Market cap range**")
        market_col.write(cap_label)
        timeframe_col.caption("**Regression lookback**")
        timeframe_col.write(lookback_label)
        session_col.caption("**Market session**")
        session_col.write(report_session)

        st.caption(
            "**Strategy:** Positive regression slope · −3σ/−4σ screening · "
            "Both lower bands above $0 · Daily closing prices"
        )
        st.caption(
            f"**Coverage:** {candidate_label} stock candidates · **Data status:** {quality_label} · "
            f"**Table:** {displayed_count:,} of {total_results:,} qualifying stocks · "
            f"**Display:** {display_filter} · **Order:** {sorting}" +
            (f" · **Search:** {search.strip()}" if search.strip() else "")
        )
        if not saved_filters:
            st.warning("This report predates saved scan settings. Rerun it to make screenshots verifiable.", icon="⚠️")


def read_results() -> tuple[pd.DataFrame | None, dict]:
    if not REPORT_FILE.exists():
        return None, {}
    frame = pd.read_csv(REPORT_FILE, dtype={"ticker": "string"})
    for field in ("market_cap_b", "close", "regression", "sigma", "z_score",
                  "lower_3", "lower_4", "slope_per_session"):
        if field in frame.columns:
            frame[field] = pd.to_numeric(frame[field], errors="coerce")
    if "new_crossings" in frame.columns:
        frame["new_crossings"] = frame["new_crossings"].fillna("")
    summary = {}
    if SUMMARY_FILE.exists():
        try:
            summary = json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return frame, summary


def render_stock_results_heading() -> None:
    """Consistent uppercase heading and faint divider for live/final results."""
    st.subheader("STOCK RESULTS")
    st.markdown(
        '<hr style="border:0;border-top:1px solid rgba(150,150,150,0.23);'
        'margin:0.1rem 0 0.8rem">',
        unsafe_allow_html=True,
    )


def show_live_table(rows: list[dict]) -> None:
    if not rows:
        st.caption("No stocks passing the trend/history filters yet in the processed batches.")
        return
    frame = pd.DataFrame(rows).sort_values("z_score")
    visible = frame[[c for c in VISIBLE_COLUMNS if c in frame.columns]]
    st.dataframe(styled_stock_table(visible),
                 hide_index=True, use_container_width=True, height=850,
                 column_config=COLUMN_CONFIG)


def as_settings(scope: str, top_n: int, custom: str,
                min_cap: float, max_cap: float | None, years: float) -> ScanSettings:
    regression_sessions(years)
    if max_cap is not None and max_cap <= min_cap:
        raise ValueError("Maximum market cap must exceed minimum market cap.")
    if scope == CUSTOM_SCOPE:
        symbols = tuple(dict.fromkeys(t.upper() for t in re.split(r"[\s,]+", custom) if t.strip()))
        if not symbols or len(symbols) > 50:
            raise ValueError("Enter between 1 and 50 custom tickers.")
        if any(not re.fullmatch(r"[A-Z0-9.^-]{1,18}", s) for s in symbols):
            raise ValueError("Invalid ticker: use letters, numbers, periods or hyphens.")
        return ScanSettings(years=years, limit=None, symbols=symbols)
    return ScanSettings(min_cap_b=min_cap, max_cap_b=max_cap, years=years,
                        limit=top_n if scope == TOP_N_SCOPE else None)


# Integrated page: original scanner engine; shared UI only.
apply_dashboard_theme()
render_page_header("Regression Scanner", "U.S.-listed equities · daily-close regression · −3σ / −4σ screening", current="scanner")
st.caption("Daily close data · hover over settings and table headings for definitions")

with st.container(border=True):
    # Make failures visible above the scan controls instead of below a large table.
    scan_error_slot = st.empty()
    if st.session_state.get("last_scan_error"):
        scan_error_slot.error(st.session_state["last_scan_error"], icon="🚨")

    # Keep scan inputs in one row; zero maximum means no upper cap.
    # Custom ticker scans remain supported by the engine but not the page UI.
    if st.session_state.get("scan_scope") not in (TOP_N_SCOPE, MAX_SCOPE, ETF_SCOPE):
        st.session_state["scan_scope"] = TOP_N_SCOPE
    scope_col, n_col, min_col, max_col, years_col, action_col = st.columns(
        [2.3, 1.05, 1.2, 1.2, 0.95, 1.15], vertical_alignment="bottom", gap="small"
    )
    with scope_col:
        scope = st.selectbox(
            "Universe", (TOP_N_SCOPE, MAX_SCOPE, ETF_SCOPE),
            format_func=lambda option: {
                TOP_N_SCOPE: "Top N Stocks by Market Cap",
                MAX_SCOPE: "All available",
                ETF_SCOPE: "ETF holdings",
            }[option],
            key="scan_scope",
            help="Scan the largest N stocks within the market-cap range, or attempt all available stocks.",
        )
    with n_col:
        top_n = st.number_input(
            "Stocks (N)", min_value=1, value=100, step=1,
            disabled=(scope != TOP_N_SCOPE),
            help="Number of the largest eligible companies to attempt, not a guaranteed result count.",
        )
    with min_col:
        min_cap = st.number_input(
            "Min cap ($B)", min_value=0.0, value=50.0, step=1.0, format="%.1f",
            disabled=(scope == ETF_SCOPE),
            help="Minimum market cap in billions of USD; not used in ETF mode.",
        )
    with max_col:
        max_input = st.number_input(
            "Max cap ($B)", min_value=0.0, value=0.0, step=1.0, format="%.1f",
            disabled=(scope == ETF_SCOPE),
            help="Not used in ETF mode. Set 0 for no maximum in normal scans.",
        )
    with years_col:
        years = st.number_input(
            "Years", min_value=0.5, max_value=30.0, value=10.0, step=0.1, format="%.2f",
            help="Regression lookback in years; approximately 250 trading sessions per year.",
        )
    with action_col:
        launch = st.button(
            "Run Scan", type="primary", use_container_width=True, key="run_scan_main",
            help="Scan the selected universe using completed daily closes.",
        )
    custom = ""  # Custom symbols are provided by the ETF holdings source in ETF mode.
    etf_ticker = ""
    if scope == ETF_SCOPE:
        etf_col, caption_col = st.columns([1, 3], vertical_alignment="bottom")
        with etf_col:
            etf_ticker = st.text_input("ETF ticker", value="SPY", max_chars=12,
                                       key="regression_etf_ticker",
                                       help="Enter SPY, SMH, QQQ, VGT, etc.").strip().upper()
        with caption_col:
            st.caption("Automatically retrieve all published stock holdings when available. "
                       "Source data is dated; some ETFs have older SEC filing holdings. "
                       "No CSV upload is necessary.")
        st.caption("ETF mode scans every ticker supplied by the holdings source, with no top-10 cap. "
                   "Large ETFs may take substantial time and some stocks may lack 10 years of valid prices. "
                   "Z-scores are saved separately for News Screen use.")
    max_cap = float(max_input) if max_input > 0 else None
    length = regression_sessions(years)
    if scope == TOP_N_SCOPE and top_n > SCREENER_RECORD_SAFETY_CAP:
        st.warning(
            f"Top N exceeds the {SCREENER_RECORD_SAFETY_CAP:,}-record stock-discovery safeguard.",
            icon="⚠️",
        )
    elif scope == TOP_N_SCOPE and top_n >= 1000:
        st.caption("Large scans may encounter Yahoo throttling or missing histories.")
    elif scope == MAX_SCOPE:
        st.caption("All available: large universes may hit Yahoo's discovery safeguard or download limits.")

    st.caption(f"Daily closes only · {length:,} trading sessions · not a live intraday feed")

if launch:
    st.session_state.pop("last_scan_error", None)
    scan_error_slot.empty()

# ETF results live in their own directory; normal market-cap reports are never overwritten.
if scope == ETF_SCOPE:
    current_etf_symbol = normalize_symbol(etf_ticker)
    scan_output_dir = etf_report_dir(current_etf_symbol, PROJECT_ROOT) if current_etf_symbol else ROOT / "results" / "etf_scans" / "invalid"
    REPORT_FILE = scan_output_dir / "latest_scan.csv"
    SUMMARY_FILE = scan_output_dir / "summary.json"
    SKIP_FILE = scan_output_dir / "skipped.csv"
else:
    REPORT_FILE = ROOT / "results" / "latest_scan.csv"
    SUMMARY_FILE = ROOT / "results" / "summary.json"
    SKIP_FILE = ROOT / "results" / "skipped.csv"

# One results container is reused for the live preview and the saved/final table.
# No duplicate chart is rendered underneath the live table after a scan.
progress_slot = st.empty()
results_slot = st.empty()

if launch:
    try:
        if scope == ETF_SCOPE:
            etf_clean = normalize_symbol(etf_ticker)
            if not etf_clean:
                raise ValueError("Enter a valid ETF ticker such as SPY, SMH, QQQ or VGT.")
            holdings = get_etf_constituents(etf_clean)
            if not holdings.symbols:
                raise ValueError(holdings.error or "ETF equity holdings are unavailable.")
            tickers = list(holdings.symbols)
            source_name = holdings.source
            st.session_state['etf_regression_as_of'] = holdings.holdings_as_of
            st.session_state['etf_regression_count'] = len(tickers)
            if not holdings.complete_holdings_source:
                st.warning("The full-holdings provider was unavailable. "
                           "Yahoo supplied top holdings only; this run does NOT cover the entire ETF.")
            elif holdings.holdings_as_of:
                st.info(f"Scanning {len(tickers):,} published holdings from {holdings.holdings_as_of}. "
                        "Full published holdings may omit positions without a usable ticker.")
            if holdings.attribution:
                st.caption(holdings.attribution)
            if len(tickers) > 300:
                st.warning(f"Full ETF scan includes {len(tickers):,} stocks. "
                           "Downloads may take a long time and be incomplete if Yahoo throttles requests.")
            st.session_state['etf_regression_source'] = source_name
            st.session_state['etf_regression_count'] = len(tickers)
            settings = ScanSettings(years=years, limit=None, symbols=tuple(tickers),
                                    output_dir=etf_report_dir(etf_clean, PROJECT_ROOT),
                                    record_all_zscores=True,
                                    universe_source=source_name)
        else:
            settings = as_settings(scope, top_n, custom, min_cap, max_cap, years)
    except ValueError as exc:
        st.session_state["last_scan_error"] = str(exc)
        scan_error_slot.error(st.session_state["last_scan_error"], icon="🚨")
    else:
        with progress_slot.container():
            # Deliberately small section label; the changing status line is prominent.
            st.markdown("**Live scanning progress**")
            status_text = st.empty()
            bar = st.progress(0.0, text="Preparing stock universe…")
            metrics_box = st.empty()
        last_complete = False
        scan_started_at = time.monotonic()
        try:
            for progress in scan_market(settings):
                eta_note = ""
                if progress.completed and progress.total > progress.completed:
                    elapsed = time.monotonic() - scan_started_at
                    estimate_seconds = elapsed * (progress.total - progress.completed) / progress.completed
                    eta_note = f" · roughly {max(1, round(estimate_seconds / 60))} min remaining (estimate)"
                is_finished = progress.phase == "finished"
                live_message = (
                    "SCAN FINISHED" if is_finished and bool(progress.summary and progress.summary.get("complete"))
                    else "SCAN FINISHED — DATA-QUALITY WARNINGS" if is_finished
                    else progress.message + eta_note
                )
                status_text.markdown(
                    '<div style="font-size:1.17rem;font-weight:700;line-height:1.45;'
                    'margin:0.25rem 0 0.45rem;">'
                    + html.escape(live_message) + '</div>',
                    unsafe_allow_html=True,
                )
                portion = progress.completed / progress.total if progress.total else 0.0
                bar.progress(min(1.0, portion), text=(f"{progress.completed:,} / "
                           f"{progress.total:,} stocks scanned ({portion:.0%})" if progress.total else
                           "Looking up market-cap ranked stocks…"))
                # Single compact metrics strip, rather than five tall Streamlit metric cards.
                compact_values = (
                    ("Processed", progress.completed),
                    ("Analyzed", progress.analyzed),
                    ("Passing filters", len(progress.rows)),
                    ("Data errors", progress.data_errors),
                    ("Cache hits", progress.cache_hits),
                )
                compact_items = "".join(
                    '<span style="white-space:nowrap;font-size:0.78rem;">'
                    f'<span style="color:#9da7b2;">{label}</span> '
                    f'<strong style="font-size:0.88rem;">{value:,}</strong></span>'
                    for label, value in compact_values
                )
                metrics_box.markdown(
                    '<div style="border:1px solid rgba(140,150,160,0.25);'
                    'border-radius:0.5rem;padding:0.38rem 0.7rem;display:flex;'
                    'gap:0.65rem 1.5rem;flex-wrap:wrap;align-items:center;">'
                    '<span style="color:#9da7b2;font-size:0.75rem;font-weight:600;">'
                    'LIVE METRICS</span>' + compact_items + '</div>',
                    unsafe_allow_html=True,
                )
                with results_slot.container():
                    render_stock_results_heading()
                    st.caption("Updating after each processed batch — results are partial until the scan finishes.")
                    show_live_table(progress.rows)
                if progress.phase == "finished":
                    last_complete = True
                    st.session_state["last_run_complete"] = bool(progress.summary and progress.summary.get("complete"))
            if last_complete and not st.session_state["last_run_complete"]:
                st.warning("Some downloaded prices failed validation. Check scan diagnostics for missing symbols.")
        except Exception as exc:
            st.session_state["last_run_complete"] = False
            st.session_state["last_scan_error"] = (
                f"SCAN FAILED — {type(exc).__name__}: {exc}. "
                "The previous saved results may still appear below; they are NOT from this failed scan."
            )
            scan_error_slot.error(st.session_state["last_scan_error"], icon="🚨")


@st.cache_data(ttl=3600, max_entries=32, show_spinner=False)
def cached_chart_prices(ticker: str, session: str, years: float) -> pd.DataFrame:
    """Only download chart OHLC for the selected stock; cache across reruns."""
    return download_chart_prices(ticker, session, years)


def selected_chart_ticker(view: pd.DataFrame) -> str | None:
    """Return a valid selection within the current filtered/sorted results."""
    if view.empty:
        return None
    tickers = view["ticker"].astype(str).tolist()
    active = st.session_state.get("selected_chart_ticker")
    if active not in tickers:
        active = tickers[0]
        st.session_state["selected_chart_ticker"] = active
    return active


def graph_checkbox_changed(editor_key: str, tickers: tuple[str, ...]) -> None:
    """Single-select behavior for the visibly titled Graph checkbox column.

    The data editor only allows edits to the Graph column. On any checkbox
    change, use its edited row indexes to update the selected ticker.
    The next render receives a new editor key, resetting other checkboxes.
    """
    changes = (st.session_state.get(editor_key) or {}).get("edited_rows", {})
    checked = []
    for raw_index, edit in changes.items():
        try:
            index = int(raw_index)
        except (ValueError, TypeError):
            continue
        if 0 <= index < len(tickers) and edit.get("Graph") is True:
            checked.append(tickers[index])
    if checked:
        st.session_state["selected_chart_ticker"] = checked[-1]
    elif tickers:
        st.session_state["selected_chart_ticker"] = tickers[0]
    # Use a fresh editor widget after every click so old checkbox edits cannot
    # override the single active Graph checkbox on a later rerun.
    st.session_state["graph_choice_epoch"] = st.session_state.get("graph_choice_epoch", 0) + 1


def render_selected_channel(view: pd.DataFrame, summary: dict, session: str) -> None:
    """Show a compact daily-regression chart above the Graph-selection table."""
    st.subheader("REGRESSION ANALYSIS")
    ticker = selected_chart_ticker(view)
    if ticker is None:
        st.caption("No qualifying stocks in this selection. Change the table filter below.")
        return

    chosen = view.loc[view["ticker"].astype(str) == ticker].iloc[0]
    name = str(chosen.get("name") or ticker)
    saved_years = float((summary.get("filters") or {}).get("regression_years", 10.0))
    snapshot_title = f"{saved_years:g} Year Snapshot"
    st.markdown(f"**{ticker} — {name}**  ·  **{snapshot_title}**")
    st.caption("**Standard deviation lines**")
    # Compact, left-aligned line controls. The final column is flexible empty space.
    band_columns = st.columns([0.55] * len(BAND_OPTIONS) + [5.6], gap="small")
    visible_bands = []
    for index, band in enumerate(BAND_OPTIONS):
        with band_columns[index]:
            if st.checkbox(
                band, value=(band in DEFAULT_BANDS),
                key=f"chart_sigma_checkbox_{index}",
            ):
                visible_bands.append(band)

    try:
        with st.spinner(f"Loading candlesticks for {ticker}…"):
            daily = cached_chart_prices(ticker, session, saved_years)
            chart = make_channel_data(daily, saved_years, DAILY_BASIS)
        # Compact descriptive statistics avoid adding an entire row of large cards.
        st.caption(
            f"**Latest close:** ${chart.point.close:,.2f}  ·  "
            f"**Regression:** ${chart.point.line:,.2f}  ·  "
            f"**Channel σ:** ${chart.point.sigma:,.2f}  ·  "
            f"**Z-score:** {chart.point.z:+.2f}σ"
        )
        st.markdown(
            '<div style="text-align:right; color:#9aa3ae; font-size:0.78rem; '
            'margin:0 0 0.35rem 0;">'
            'Hover over X or Y Axis and use MWheel to adjust Axis'
            '</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            style_blue_figure(channel_figure(chart, ticker, visible_bands)),
            use_container_width=True,
            key=f"channel_chart_{ticker}",
            config={
                "displaylogo": False,
                # Native Plotly wheel zoom: gradual per-scroll zooming.
                "scrollZoom": True,
                "doubleClick": "reset",
                # Permit independent X/Y scaling from the tick-label/axis areas.
                "showAxisDragHandles": True,
                "showAxisRangeEntryBoxes": False,
                # Pan is the default drag mode; still allow box-zoom via modebar.
                "modeBarButtonsToRemove": ["select2d", "lasso2d"],
            },
        )
        scanner_z = pd.to_numeric(chosen.get("z_score"), errors="coerce")
        st.caption(
            f"**{snapshot_title}:** Daily-close regression ({chart.lookback_bars:,} sessions, "
            f"{saved_years:g}-year lookback); weekly candlesticks for readability. "
            f"Saved scan Z-score: {scanner_z:.2f}σ."
        )
        if pd.notna(scanner_z) and abs(chart.point.z - float(scanner_z)) > 0.05:
            st.warning(
                "This chart's deviation differs from the saved scanner result. "
                "Check the price feed, market session and split adjustments."
            )
    except Exception as exc:
        st.warning(
            f"Could not load chart for {ticker}: {type(exc).__name__}: {exc}. "
            "The saved results table is still available below."
        )


def render_saved_results(scope: str, top_n: int, min_cap: float,
                         max_cap: float | None, length: int) -> None:
    try:
        df, summary = read_results()
    except (OSError, pd.errors.ParserError, ValueError) as exc:
        df, summary = None, {}
        st.error(f"Unable to read saved scan: {exc}")

    if df is None:
        st.subheader("No completed scan yet")
        st.write("Start with **Top N by market cap → 25**, then type any number of stocks to scan.")
        st.caption("The Calculate Intrinsic Value button and Filter N/A checkbox appear above the results table after a scan completes.")
        st.stop()
    if "z_score" not in df.columns:
        st.error("Saved report has no Z-scores. Run a new scan.")
        st.stop()

    render_stock_results_heading()
    file_time = datetime.fromtimestamp(REPORT_FILE.stat().st_mtime, TZ).strftime("%b %d, %Y %I:%M %p ET")
    report_session = str(summary.get("session") or (df["session"].iloc[0] if len(df) and "session" in df else "unknown"))
    saved = summary.get("filters", {})
    if saved:
        if saved.get("custom_symbols"):
            changed = scope not in (CUSTOM_SCOPE, ETF_SCOPE)
        else:
            lo = saved.get("min_cap_b", 50.0)
            hi = saved.get("max_cap_b")
            cap_range = f"${lo:g}B–${hi:g}B" if hi is not None else f"${lo:g}B+"
            n = saved.get("top_n_limit")
            changed = (scope == CUSTOM_SCOPE or float(lo) != float(min_cap) or
                       hi != max_cap or n != (top_n if scope == TOP_N_SCOPE else None))
        if saved.get("regression_sessions") != length:
            changed = True
        if changed:
            st.info("Settings above differ from this saved scan. Press **Run Scan** to apply them.")
    else:
        st.caption("This report predates recorded filters. Run a fresh scan for provenance.")

    try:
        if report_session != last_completed_session():
            st.warning("Saved results are from an older market session. Run a new scan.")
    except RuntimeError:
        pass
    if summary.get("complete") is False:
        st.warning("This saved scan was flagged incomplete because of missing or failed data downloads.")
    if summary.get("download_or_data_errors", 0):
        st.caption(f"Data-quality errors: {summary['download_or_data_errors']}. See skipped-stocks table below.")

    # Each newly saved scan starts in the regression-only view, even when a
    # valuation CSV from a previous visit/session exists on disk.
    valuation_file = ROOT / "results" / "intrinsic_values.csv"
    scan_identity = f"{report_session}|{REPORT_FILE.stat().st_mtime_ns}"
    show_intrinsic = st.session_state.get("intrinsic_table_scan_id") == scan_identity
    if st.session_state.get("intrinsic_na_filter_scan_id") != scan_identity:
        # A fresh scan should never inherit N/A filtering from an older scan.
        st.session_state["intrinsic_na_filter_scan_id"] = scan_identity
        st.session_state["intrinsic_na_filter_enabled"] = False

    z = df["z_score"]
    new_crossings_count = int(
        df.get("new_crossings", pd.Series(dtype=str))
        .fillna("").astype(str).str.strip().ne("").sum()
    )
    # All saved-scan metadata and metrics in one scrollable line (no stacked captions).
    saved_scope = (
        "Custom tickers" if saved.get("custom_symbols")
        else (f"Top {int(saved['top_n_limit']):,}" if saved.get("top_n_limit") is not None else "MAX")
        if saved else "Unknown"
    )
    saved_cap = (
        "N/A" if saved.get("custom_symbols")
        else (f"${float(saved['min_cap_b']):g}B–${float(saved['max_cap_b']):g}B" if saved.get("max_cap_b") is not None
              else f"${float(saved['min_cap_b']):g}B+")
        if saved and saved.get("min_cap_b") is not None else "Not recorded"
    )
    summary_parts = [
        f"Session: {report_session}",
        f"Saved: {file_time}",
        f"Scanned: {summary.get('candidates', 'unknown')}",
        f"Scope: {saved_scope}",
        f"Cap: {saved_cap}",
        f"Lookback: {saved.get('regression_years', 'unknown')} yr",
        f"Passing: {len(df):,}",
        f"≤−3σ: {int((z <= -3).sum()):,}",
        f"≤−4σ: {int((z <= -4).sum()):,}",
        f"Crossings: {new_crossings_count:,}",
    ]
    st.markdown(
        '<div style="white-space:nowrap;overflow-x:auto;padding:0.14rem 0;'
        'font-size:0.76rem;color:#9da7b2;">'
        + ' <span style="opacity:0.6;">|</span> '.join(html.escape(item) for item in summary_parts)
        + '</div>',
        unsafe_allow_html=True,
    )

    # Keep the stock filter controls above the chart. The ticker search input
    # itself is displayed directly above the stock table, below the chart.
    # Read its widget state here so it can filter the data and selected chart
    # before the input is rendered later in this same Streamlit rerun.
    c_filter, c_sort = st.columns([2, 1.5])
    with c_filter:
        selected = st.selectbox(
            "Show stocks", ["All qualifying", "At or below −3σ", "At or below −4σ"]
        )
    with c_sort:
        sorting = st.selectbox("Sort", ["Most negative Z-score", "Largest market cap", "Ticker A–Z"])

    search = st.session_state.get("regression_graph_stock_search", "")
    saved_parameters_slot = st.empty()

    view = df.copy()
    if selected == "At or below −3σ":
        view = view.loc[view["z_score"] <= -3]
    elif selected == "At or below −4σ":
        view = view.loc[view["z_score"] <= -4]
    if search.strip():
        term = search.strip()
        view = view.loc[view["ticker"].astype(str).str.contains(term, case=False, regex=False) |
                        view["name"].astype(str).str.contains(term, case=False, regex=False)]
    if sorting == "Largest market cap":
        view = view.sort_values("market_cap_b", ascending=False, na_position="last")
    elif sorting == "Ticker A–Z":
        view = view.sort_values("ticker")
    else:
        view = view.sort_values("z_score")

    with saved_parameters_slot.container():
        render_saved_scan_parameters(summary, report_session, len(view), len(df), selected, search, sorting)
    render_selected_channel(view, summary, report_session)

    # Place BOTH the Graph instruction and ticker/company search directly
    # ABOVE the stock results table, not above the regression chart.
    graph_instructions_col, graph_search_col = st.columns([3, 1.6], vertical_alignment="center")
    with graph_instructions_col:
        st.markdown("**Graph:** Check one stock to display its regression analysis above.")
    with graph_search_col:
        st.text_input(
            "Search ticker or company",
            placeholder="Search ticker or company",
            label_visibility="collapsed",
            key="regression_graph_stock_search",
            help="Filter saved scan results by ticker or company; the chart follows the selected matching stock.",
        )

    # Small secondary action aligned to the UPPER-RIGHT corner of the table,
    # below the chart and search controls. Do not trigger valuation on scan load.
    # Group both controls at the far right rather than spreading them
    # across three full-page columns; keep the filter immediately beside
    # its related action.
    table_mode_col, table_controls_col = st.columns(
        [6.6, 3.4], vertical_alignment="center", gap="small"
    )
    with table_mode_col:
        table_mode_label = st.empty()
    with table_controls_col:
        na_filter_checkbox_col, intrinsic_button_col = st.columns(
            [1.0, 2.45], vertical_alignment="center", gap="small"
        )
        with na_filter_checkbox_col:
            st.checkbox(
                "Filter N/A",
                key="intrinsic_na_filter_enabled",
                disabled=not show_intrinsic,
                help="Only show stocks with all three intrinsic metrics available. Uncheck to show all stocks.",
            )
        with intrinsic_button_col:
            calculate_clicked = st.button(
                "Calculate Intrinsic Value",
                key="calculate_intrinsic_value_table",
                type="secondary",
                use_container_width=True,
                help="Calculate five-year DCF estimates for all stocks currently displayed, "
                     "regardless of Z-score.",
            )

    if calculate_clicked:
        # The DCF button values the CURRENTLY DISPLAYED stock table, not just
        # the <=−3σ subset. This is deliberately independent of trade signals.
        targets = view.to_dict("records")
        if not targets:
            st.info("No stocks in the current table to value. Adjust the display filter or search.")
        else:
            progress = st.progress(0, text=f"Calculating intrinsic value: 0/{len(targets):,} stocks")
            try:
                def report_valuation_progress(completed: int, total: int) -> None:
                    progress.progress(
                        completed / total,
                        text=f"Calculating intrinsic value: {completed:,}/{total:,} stocks",
                    )

                # No 30-stock cap on the interactive button. The scheduled
                # emailer retains its separate valuation limit in automated_scan.py.
                valuations = enrich_table_rows(targets, on_progress=report_valuation_progress)
                if valuations:
                    columns = ["ticker", *VALUATION_COLUMNS,
                               "valuation_method", "valuation_note", "valuation_as_of"]
                    valuation_file.parent.mkdir(parents=True, exist_ok=True)
                    current = pd.DataFrame(valuations).reindex(columns=columns)
                    # Preserve previous valuations for other search/filter views
                    # of this SAME scan, without reusing values from older scans.
                    if valuation_file.exists():
                        try:
                            prior = pd.read_csv(valuation_file, dtype={"ticker": "string"})
                            if (not prior.empty and "scan_identity" in prior.columns
                                and prior["scan_identity"].astype(str).eq(scan_identity).all()):
                                current = pd.concat([prior.reindex(columns=columns), current], ignore_index=True)
                                current = current.drop_duplicates(subset="ticker", keep="last")
                        except (OSError, ValueError, pd.errors.ParserError):
                            pass
                    current.assign(scan_session=report_session, scan_identity=scan_identity).to_csv(
                        valuation_file, index=False
                    )
                    st.session_state["intrinsic_table_scan_id"] = scan_identity
                    show_intrinsic = True
                    # Redraw the checkbox enabled immediately after DCF completes.
                    st.rerun()
                else:
                    st.info("No valuation data returned. The regression table remains available.")
            except Exception as exc:
                st.warning(
                    f"Valuation unavailable: {type(exc).__name__}: {exc}. "
                    "The regression table remains unchanged."
                )
            finally:
                progress.empty()

    if show_intrinsic:
        valuations_df = None
        if valuation_file.exists():
            try:
                saved_valuations = pd.read_csv(valuation_file, dtype={"ticker": "string"})
                # Identity prevents stale values from an earlier scan on the same day.
                if (not saved_valuations.empty and "scan_identity" in saved_valuations.columns
                    and saved_valuations["scan_identity"].astype(str).eq(scan_identity).all()):
                    valuations_df = saved_valuations.drop(
                        columns=["scan_session", "scan_identity"], errors="ignore"
                    )
            except (OSError, ValueError, pd.errors.ParserError):
                pass
        view = attach_intrinsic_values(view, valuations_df)
        if st.session_state["intrinsic_na_filter_enabled"]:
            view = only_complete_intrinsic_rows(view)
            if view.empty:
                st.info("No stocks have all three intrinsic metrics available. Uncheck **Filter N/A** to restore all stocks.")
        st.caption("Indicative five-year DCF, not a buy filter. Default assumptions: "
                   "5% FCFF growth, 10% WACC, 2.5% terminal growth. "
                   "N/A = insufficient/unsuitable financial data or not yet calculated for this view.")

    table_mode_label.caption("Regression + intrinsic valuation" if show_intrinsic else "Regression results")
    table_columns = VALUED_COLUMNS if show_intrinsic else VISIBLE_COLUMNS
    visible_view = view[[c for c in table_columns if c in view.columns]].copy()
    if show_intrinsic:
        # Numeric percentage columns sort correctly and display without commas;
        # the intrinsic-value text column keeps literal N/A for missing DCFs.
        visible_view = prepare_intrinsic_display(visible_view)
    active_ticker = selected_chart_ticker(view)
    # Unlike Streamlit's unlabeled row-selection control, this has a real
    # Graph column header. Only that checkbox is editable; financial data
    # and TradingView links remain read-only and preserve Styler highlights.
    visible_view.insert(0, "Graph", visible_view["ticker"].astype(str).eq(active_ticker))
    identity = (
        f"{report_session}|{REPORT_FILE.stat().st_mtime_ns}|{selected}|{search}|{sorting}|"
        + "|".join(view["ticker"].astype(str))
        + f"|{active_ticker}|{st.session_state.get('graph_choice_epoch', 0)}|dcf={show_intrinsic}"
    )
    editor_key = "graph_editor_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    st.data_editor(
        styled_stock_table(visible_view),
        hide_index=True,
        use_container_width=True,
        height=900,
        column_order=(["Graph", *VISIBLE_COLUMNS] if not show_intrinsic
                      else ["Graph", *VALUED_COLUMNS]),
        column_config={
            "Graph": st.column_config.CheckboxColumn(
                "Graph", width=70, pinned=True,
                help="Check to show this stock above. Only one is selected at a time."
            ),
            **COLUMN_CONFIG,
        },
        disabled=[col for col in visible_view.columns if col != "Graph"],
        key=editor_key,
        on_change=graph_checkbox_changed,
        args=(editor_key, tuple(view["ticker"].astype(str))),
    )
    if view.empty:
        st.info("No stocks match that display filter. Try All qualifying.")
    st.download_button("Download filtered CSV", view.to_csv(index=False).encode("utf-8"),
                       file_name=f"regression_scan_{report_session}.csv", mime="text/csv")
    with st.expander("Scan diagnostics (optional) — coverage, errors and skipped stocks"):
        st.caption("This section shows scan completeness and data-quality details. "
                   "Skipped stocks can include symbols with insufficient history or failed downloads. "
                   "It does not represent buy or sell signals.")
        st.json(summary)
        if SKIP_FILE.exists():
            skipped = pd.read_csv(SKIP_FILE, dtype={"symbol": "string"})
            if "company_name" not in skipped.columns:
                skipped["company_name"] = ""
                st.info("This saved scan predates company-name tracking. Run a new scan to fill company names.")
            st.dataframe(
                skipped[["symbol", "company_name", "reason"]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "symbol": st.column_config.TextColumn("Ticker"),
                    "company_name": st.column_config.TextColumn("Company name", width="large"),
                    "reason": st.column_config.TextColumn("Reason", width="medium"),
                },
            )
            st.download_button(
                "Download skipped CSV",
                skipped[["symbol", "company_name", "reason"]].to_csv(index=False).encode("utf-8"),
                file_name="regression_skipped.csv", mime="text/csv",
            )
    st.caption("A Z-score below −3 or −4 is a screening signal, not an automatic buy recommendation. "
               "Compare price feeds and channel math with your original TradingView indicator. "
               "No email alerts or trading are executed by this dashboard.")


if scope == ETF_SCOPE and current_etf_symbol:
    score_table, score_meta = load_etf_scores(current_etf_symbol, PROJECT_ROOT)
    st.subheader(f"{current_etf_symbol} — ALL CALCULATED REGRESSION SCORES")
    if score_table.empty:
        st.caption("No ETF regression data saved yet. Choose ETF Holdings above and click Run Scan.")
    else:
        st.caption(f"Daily-close regression session: {score_meta.get('session') or 'unknown'} · "
                   f"{len(score_table)} tickers evaluated · "
                   f"source: {(score_meta.get('filters') or {}).get('etf_source') or 'unrecorded'} · "
                   "includes stocks that do not pass the scanner's strategy filters. "
                   "Missing history/download errors still produce unavailable scores.")
        st.dataframe(score_table[[c for c in (
            'ticker', 'session', 'close', 'regression', 'z_score', 'lower_3', 'lower_4', 'strategy_eligible'
        ) if c in score_table.columns]], hide_index=True, use_container_width=True, height=420)
    if score_meta.get('skipped'):
        with st.expander(f"ETF holdings without calculated Z-scores ({len(score_meta['skipped'])})"):
            st.dataframe(pd.DataFrame(score_meta['skipped']), hide_index=True, use_container_width=True)

# Reuse the exact same results container once the scan finishes (or on reload).
# The live preview is replaced, not followed by another results table.
with results_slot.container():
    if scope == ETF_SCOPE and REPORT_FILE.exists():
        existing, _summary = read_results()
        if existing is not None and existing.empty:
            st.info("No ETF constituent passed the scanner's strategy filters. "
                    "See the all-constituent Z-score table above; these scores were calculated independently of eligibility.")
        else:
            render_saved_results(scope, top_n, min_cap, max_cap, length)
    else:
        render_saved_results(scope, top_n, min_cap, max_cap, length)
