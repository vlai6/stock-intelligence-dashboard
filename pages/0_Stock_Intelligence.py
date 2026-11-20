import sys as _si_sys
from pathlib import Path as _si_Path
_si_project_root = str(_si_Path(__file__).resolve().parent.parent)
if _si_project_root not in _si_sys.path:
    _si_sys.path.insert(0, _si_project_root)

import html
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import plotly.graph_objects as go
from dashboard_theme import apply_dashboard_theme, style_blue_figure, render_page_header

from ai_peers import recommend_peers
from advanced_metrics import historical_cagr, calculate_roic
from metric_explanations import EXPLANATIONS
from dcf_health_metrics import compute_extra_metrics, EXTRA_EXPLANATIONS, EXTRA_METRIC_NAMES, format_extra_metric
from news_sentiment import fetch_stock_news
from finbert_sentiment import analyze_finbert
from ai_events import group_news_events
from gnews_history import update_gnews, load_gnews, score_unscored

# Load API keys from the existing project .env file.
load_dotenv()





@st.cache_data(show_spinner=False)
def get_stock(ticker):
    stock = yf.Ticker(ticker)
    history = stock.history(period="5y", auto_adjust=True)

    try:
        info = stock.info
    except Exception:
        info = {}

    return history, info


MARKET_NEWS_TZ = ZoneInfo("America/New_York")


def todays_articles(articles):
    """Select articles published today in US Eastern Time (incl. DST)."""
    if articles.empty:
        return articles.copy()
    dates = pd.to_datetime(articles["Date"], errors="coerce", utc=True)
    local_dates = dates.dt.tz_convert(MARKET_NEWS_TZ).dt.date
    today = datetime.now(MARKET_NEWS_TZ).date()
    return articles.loc[local_dates == today].copy()


@st.cache_data(ttl=1800, show_spinner=False)
def get_competitor_sentiment_counts(ticker):
    """Return FinBERT label counts for a competitor's available Yahoo headlines."""
    articles = fetch_stock_news(ticker)
    articles = todays_articles(articles)
    if articles.empty:
        return {label: 0 for label in ("Positive", "Neutral", "Negative")}
    scored = analyze_finbert(tuple(articles["Title"].astype(str).tolist()))
    if len(scored) != len(articles):
        raise ValueError(f"Unexpected FinBERT result count for {ticker}.")
    counts = scored["FinBERT Sentiment"].value_counts()
    return {label: int(counts.get(label, 0)) for label in ("Positive", "Neutral", "Negative")}



def summarize_todays_sentiment(ticker, counts):
    """One-sentence, headline-based snapshot; not a trading signal."""
    total = sum(counts.values())
    if total == 0:
        return f"No headlines dated today were available for {ticker}."
    positive = counts.get("Positive", 0)
    neutral = counts.get("Neutral", 0)
    negative = counts.get("Negative", 0)
    highest = max(positive, neutral, negative)
    leaders = [label.lower() for label, count in
               (("Positive", positive), ("Neutral", neutral), ("Negative", negative))
               if count == highest]
    if len(leaders) == 1:
        trend = f"mostly {leaders[0]} ({highest / total:.0%})"
    else:
        trend = "mixed (no single leading sentiment)"
    if negative > positive:
        balance = "negative coverage exceeds positive"
    elif positive > negative:
        balance = "positive coverage exceeds negative"
    else:
        balance = "positive and negative coverage are balanced"
    return (f"Today's available {ticker} headlines are {trend}; {balance} "
            f"({total} headlines analyzed).")




def one_sentence_summary(value, limit=205):
    """Keep AI-generated relationship descriptions to a concise single sentence."""
    text = " ".join(str(value or "").split())
    if not text:
        return "Description unavailable."
    # Only end a sentence at punctuation followed by the next capitalized sentence.
    first = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text, maxsplit=1)[0]
    if len(first) > limit:
        first = first[:limit].rsplit(" ", 1)[0].rstrip(",;: ") + "…"
    return first if first.endswith((".", "!", "?", "…")) else first + "."


def company_one_sentence(info, name):
    """Use Yahoo's company classification for a short, factual overview."""
    industry = str(info.get("industry") or "").strip()
    if industry:
        return f"{name} operates in the {industry.lower()} industry."
    business_description = str(info.get("longBusinessSummary") or "").strip()
    if business_description:
        return one_sentence_summary(business_description, limit=175)
    return "Company overview is unavailable from Yahoo Finance."


def show_peer_sentiment(ticker):
    """Use the same cached, today-only Yahoo/FinBERT analysis as Section 4."""
    try:
        counts = get_competitor_sentiment_counts(ticker)
        st.caption("Today's headline sentiment · Yahoo Finance / FinBERT")
        st.write(summarize_todays_sentiment(ticker, counts))
    except Exception as exc:
        st.caption(f"Today's headline sentiment is unavailable for {ticker}: {exc}")


def switch_stock(symbol):
    st.session_state.primary = symbol
    st.session_state.loaded = True


def add_custom_comparison_ticker(primary_symbol):
    """Form callback runs before widgets render, so multiselect state is safe to update."""
    input_key = f"custom_ticker_input_{primary_symbol}"
    selected_key = f"peers_{primary_symbol}"
    custom_key = f"custom_competitors_{primary_symbol}"
    message_key = f"custom_ticker_message_{primary_symbol}"
    new_ticker = str(st.session_state.get(input_key, "")).strip().upper()

    if not new_ticker:
        st.session_state[message_key] = ("warning", "Enter a ticker symbol first.")
        return
    if not re.fullmatch(r"[A-Z0-9.^=-]{1,20}", new_ticker):
        st.session_state[message_key] = ("warning", "Invalid ticker format.")
        return
    if new_ticker == primary_symbol:
        st.session_state[message_key] = ("info", "The primary stock is already included in every comparison.")
        return

    selected = list(st.session_state.get(selected_key, []))
    custom = list(st.session_state.get(custom_key, []))
    if new_ticker in selected:
        st.session_state[message_key] = ("info", f"{new_ticker} is already selected.")
        return

    try:
        history, _ = get_stock(new_ticker)
        if history.empty or "Close" not in history or history["Close"].dropna().empty:
            st.session_state[message_key] = ("warning", f"No price history found for {new_ticker}. Check its ticker symbol.")
            return
    except Exception as exc:
        st.session_state[message_key] = ("warning", f"Could not validate {new_ticker}: {exc}")
        return

    if new_ticker not in custom:
        custom.append(new_ticker)
    selected.append(new_ticker)
    # Assign fresh lists in the callback BEFORE the multiselect is instantiated.
    st.session_state[custom_key] = custom
    st.session_state[selected_key] = selected
    st.session_state[message_key] = ("success", f"{new_ticker} added to Comparison Stocks.")


# Slightly larger typography while preserving the original Streamlit theme.
st.markdown(
    """
    <style>
    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stMarkdownContainer"] li { font-size: 1.06rem; }
    div[data-testid="stWidgetLabel"] p,
    label[data-testid="stWidgetLabel"] p { font-size: 1.04rem; }
    div[data-testid="stCaptionContainer"] p { font-size: 0.94rem; }
    div[data-baseweb="select"] { font-size: 1.04rem; }
    div[data-testid="stButton"] button,
    div[data-testid="stFormSubmitButton"] button { font-size: 1.04rem; }
    /* Make the two top-level peer/metrics cards as tall as their taller neighbor.
       No fixed height: the table and expanders can grow without clipping. */
    .st-key-peer_metrics_equal_height div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]) {
        align-items: stretch;
    }
    .st-key-peer_metrics_equal_height div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        align-self: stretch;
    }
    .st-key-peer_metrics_equal_height div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {
        height: 100%;
    }
    .st-key-peer_metrics_equal_height div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        flex: 1 1 auto;
        height: 100%;
    }
    .st-key-peer_metrics_equal_height div[data-testid="stVerticalBlockBorderWrapper"]:has(> div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"]) {
        height: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


apply_dashboard_theme()

render_page_header("Stock Intelligence", "AI-powered stock research and competitor analysis", current="stock")

if "primary" not in st.session_state:
    st.session_state.primary = "NVDA"

if "loaded" not in st.session_state:
    st.session_state.loaded = False

with st.form("stock_search"):
    ticker = st.text_input(
        "Search for a stock ticker",
        value=st.session_state.primary
    )

    submitted = st.form_submit_button(
        "Load Stock",
        type="primary"
    )

if submitted:
    symbol = ticker.strip().upper()

    if symbol:
        switch_stock(symbol)
    else:
        st.warning("Please enter a stock ticker.")

if st.session_state.loaded:
    symbol = st.session_state.primary

    try:
        # A real progress indicator is visible during potentially slow Yahoo and peer requests.
        si_stock_loading_bar = st.progress(5, text=f"Loading {symbol} stock prices and company data…")
        with st.spinner("Loading stock data..."):
            data, info = get_stock(symbol)
        si_stock_loading_bar.progress(45, text="Stock data loaded · finding comparable companies…")

        if data.empty:
            st.error(f"No price data found for {symbol}.")
            st.stop()

        company_name = info.get("longName", symbol)
        description = info.get(
            "longBusinessSummary",
            company_name
        )

        st.subheader(f"{company_name} ({symbol})")

        # Factual industry overview from Yahoo Finance; no extra Gemini call.
        st.markdown(f"**Industry:** {company_one_sentence(info, company_name)}")

        with st.spinner("Finding AI competitors..."):
            try:
                peers = recommend_peers(
                    symbol,
                    company_name,
                    description
                )
                peer_error = None
            except Exception as exc:
                peers = []
                peer_error = str(exc)

        # Keep custom and AI-recommended tickers in the same selection state.
        # Initialize before Section 1 so its optional competitor overlay can
        # immediately read the same selection as the Section 2 multiselect.
        custom_key = f"custom_competitors_{symbol}"
        selection_key = f"peers_{symbol}"
        st.session_state.setdefault(custom_key, [])
        recommended_tickers = list(dict.fromkeys(
            str(p.get("ticker", "")).strip().upper()
            for p in peers
            if str(p.get("ticker", "")).strip().upper() not in ("", symbol)
        ))
        if selection_key not in st.session_state:
            # All AI recommendations selected by default on first load.
            st.session_state[selection_key] = recommended_tickers.copy()

        si_stock_loading_bar.progress(100, text="Stock and competitor data ready")
        si_stock_loading_bar.empty()
        selected = []

        # SECTION 1 — PRIMARY STOCK (FULL WIDTH)
        with st.container(border=True):
            st.subheader("Stock Price History")

            period = st.selectbox(
                "Price history",
                ["1 Month", "3 Months", "6 Months", "1 Year", "5 Years", "Custom Range"],
                index=3,
                key=f"price_history_period_{symbol}",
            )

            price_view = st.radio(
                "Stocks to display",
                ["Primary Stock Only", "Include Competitors"],
                horizontal=True,
                key=f"price_view_{symbol}",
            )

            # Use the available five-year adjusted price history for both
            # the primary chart and the normalized competitor comparison.
            # Compare local calendar dates to include the entire end date.
            available_start = data.index.min().date()
            available_end = data.index.max().date()
            days = {
                "1 Month": 30,
                "3 Months": 90,
                "6 Months": 180,
                "1 Year": 365,
                "5 Years": 1825,
            }

            if period == "Custom Range":
                default_start = max(
                    available_start,
                    available_end - pd.Timedelta(days=365),
                )
                date_start_col, date_end_col = st.columns(2)
                with date_start_col:
                    start_date = st.date_input(
                        "Start date",
                        value=default_start,
                        min_value=available_start,
                        max_value=available_end,
                        key=f"custom_start_date_{symbol}",
                    )
                with date_end_col:
                    end_date = st.date_input(
                        "End date",
                        value=available_end,
                        min_value=available_start,
                        max_value=available_end,
                        key=f"custom_end_date_{symbol}",
                    )
                if start_date > end_date:
                    st.error("Start date must be on or before end date.")
                    st.stop()
            else:
                start_date = max(
                    available_start,
                    available_end - pd.Timedelta(days=days[period]),
                )
                end_date = available_end

            price_data = data.loc[
                (data.index.date >= start_date)
                & (data.index.date <= end_date)
            ].dropna(subset=["Close"])
            if price_data.empty:
                st.warning("No prices are available for the selected period.")
                st.stop()

            # Values use the same adjusted close series as the displayed chart.
            first_date = price_data.index[0]
            first_price = float(price_data["Close"].iloc[0])
            last_date = price_data.index[-1]
            last_price = float(price_data["Close"].iloc[-1])

            # Compact two-line price summary: label and price share the first row.
            start_col, latest_col = st.columns(2)
            with start_col:
                st.markdown(
                    f"""
                    <div style="margin:0 0 6px 0; line-height:1.35;">
                        <div style="display:flex; align-items:baseline; gap:12px; flex-wrap:wrap;">
                            <span style="font-size:1rem;">Starting Price</span>
                            <strong style="font-size:1.15rem;">${first_price:,.2f}</strong>
                        </div>
                        <div style="color:var(--text-color); opacity:.65; font-size:.83rem; margin-top:3px;">
                            Start date: {first_date:%b %d, %Y}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with latest_col:
                st.markdown(
                    f"""
                    <div style="margin:0 0 6px 0; line-height:1.35;">
                        <div style="display:flex; align-items:baseline; gap:12px; flex-wrap:wrap;">
                            <span style="font-size:1rem;">{"Ending Price" if period == "Custom Range" else "Today's Trading Price"}</span>
                            <strong style="font-size:1.15rem;">${last_price:,.2f}</strong>
                        </div>
                        <div style="color:var(--text-color); opacity:.65; font-size:.83rem; margin-top:3px;">
                            {"End date" if period == "Custom Range" else "Latest adjusted close"}: {last_date:%b %d, %Y} (not a live quote)
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            show_trendline = st.checkbox(
                "Show trend line",
                value=False,
                key=f"price_trendline_{symbol}",
                help="Display a straight-line fit of the primary stock's adjusted closing prices over the selected period.",
            )

            # Keep ticker colors stable regardless of optional trend-line traces.
            # A color is assigned from a consistent list of recommended/custom
            # tickers, rather than Plotly's trace insertion order.
            stock_colors = [
                "#63B3ED",  # Primary stock: light blue
                "#1E88E5",  # Blue
                "#F4A6AB",  # Soft pink
                "#FF4040",  # Red
                "#55D88A",  # Green
                "#1AB5A8",  # Teal
                "#A78BFA",  # Violet
                "#F59E0B",  # Amber
                "#E879F9",  # Orchid
                "#94A3B8",  # Slate
            ]
            color_order = list(dict.fromkeys(
                [symbol] + recommended_tickers
                + st.session_state.get(custom_key, [])
                + st.session_state.get(selection_key, [])
            ))
            ticker_colors = {
                ticker_name: stock_colors[i % len(stock_colors)]
                for i, ticker_name in enumerate(color_order)
            }

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=price_data.index,
                y=price_data["Close"],
                name=symbol,
                mode="lines",
                line=dict(color=ticker_colors[symbol]),
                hovertemplate=(
                    "<b>%{fullData.name}</b><br>"
                    "%{x|%B %d, %Y}<br>"
                    "Stock price: <b>$%{y:,.2f}</b><extra></extra>"
                ),
            ))

            if show_trendline and len(price_data) >= 2:
                # Fit by elapsed calendar days (rather than row number) so that
                # the line reflects the chart's date axis accurately.
                elapsed_days = (
                    price_data.index - price_data.index[0]
                ).total_seconds() / 86400.0
                slope, intercept = np.polyfit(elapsed_days, price_data["Close"].to_numpy(), 1)
                fitted_prices = slope * elapsed_days + intercept
                fig.add_trace(go.Scatter(
                    x=price_data.index,
                    y=fitted_prices,
                    name=f"{symbol} Trend Line",
                    mode="lines",
                    line=dict(dash="dash", width=2, color="#71CCFF"),
                    hovertemplate=(
                        "<b>Linear trend</b><br>"
                        "%{x|%B %d, %Y}<br>"
                        "Fitted price: <b>$%{y:,.2f}</b><extra></extra>"
                    ),
                ))
            elif show_trendline:
                st.caption("At least two price observations are needed for a trend line.")

            if price_view == "Include Competitors":
                # Section 2 is rendered below this chart. Read its retained selections
                # from session state so both sections use the same competitors.
                # Includes manually entered tickers as well as AI suggestions.
                selected_peers = [
                    peer for peer in st.session_state.get(selection_key, [])
                    if peer != symbol
                ]
                if selected_peers:
                    for peer_symbol in selected_peers:
                        try:
                            peer_history, _ = get_stock(peer_symbol)
                            peer_history = peer_history.loc[
                                (peer_history.index.date >= start_date)
                                & (peer_history.index.date <= end_date)
                            ]
                            if peer_history.empty:
                                continue
                            fig.add_trace(go.Scatter(
                                x=peer_history.index,
                                y=peer_history["Close"],
                                name=peer_symbol,
                                mode="lines",
                                line=dict(color=ticker_colors[peer_symbol]),
                                hovertemplate=(
                                    "<b>%{fullData.name}</b><br>"
                                    "%{x|%B %d, %Y}<br>"
                                    "Stock price: <b>$%{y:,.2f}</b><extra></extra>"
                                ),
                            ))
                        except Exception:
                            st.warning(f"Could not load {peer_symbol} for the price chart.")
                else:
                    st.caption("Select competitors in AI Competitor Comparison below to add them to this chart.")

            fig.update_layout(
                height=380,
                xaxis_title="Date",
                yaxis_title="Price (USD)",
                hovermode="closest",
                hoverlabel=dict(
                    font=dict(size=17),
                    bordercolor="#888888",
                ),
                font=dict(size=14),
                margin=dict(l=10, r=10, t=30, b=10)
            )

            # si_gold_trendline_6040_v1
            for _gold_trace in fig.data:
                if 'trend line' in str(getattr(_gold_trace, 'name', '')).lower():
                    _gold_trace.line.color = '#FFD21F'
                    _gold_trace.line.width = 4
                    _gold_trace.line.dash = 'dash'
            st.plotly_chart(style_blue_figure(fig), use_container_width=True)
            if price_view == "Include Competitors":
                st.caption(
                    "This chart compares actual share prices (USD), not percentage returns. "
                    "Use the chart below for normalized return comparisons."
                )

        with st.container(key="peer_metrics_equal_height"):
            # SECTIONS 2 & 3 — SHARED PEER SELECTION
            peers_col, metrics_col = st.columns([3, 2])

            # SECTION 2 — AI COMPETITORS
            with peers_col:
                with st.container(border=True):
                    st.subheader("AI Competitor Comparison")

                    if peer_error:
                        st.warning(
                            "AI recommendations unavailable: "
                            + peer_error
                        )

                    st.caption("Select AI-recommended competitors or add your own ticker. Newly added tickers are selected automatically.")

                    # Streamlit form callbacks execute before the entire app reruns,
                    # so adding a ticker immediately checks its chip in the multiselect.
                    with st.form(key=f"add_competitor_form_{symbol}", clear_on_submit=True):
                        st.text_input(
                            "Add a custom ticker",
                            placeholder="e.g., TSM, MU, ASML",
                            key=f"custom_ticker_input_{symbol}",
                        )
                        st.form_submit_button(
                            "Add Ticker",
                            on_click=add_custom_comparison_ticker,
                            args=(symbol,),
                        )

                    message = st.session_state.pop(f"custom_ticker_message_{symbol}", None)
                    if message:
                        level, content = message
                        if level == "success":
                            st.success(content)
                        elif level == "info":
                            st.info(content)
                        else:
                            st.warning(content)

                    # Retain previously selected symbols if Gemini's
                    # recommendation list changes during this session.
                    options = list(dict.fromkeys(
                        recommended_tickers
                        + st.session_state[custom_key]
                        + st.session_state[selection_key]
                    ))
                    selected = st.multiselect(
                        "Comparison Stocks",
                        options=options,
                        key=selection_key,
                    )

                    for peer in peers:
                        with st.expander(f"{peer['ticker']} — {peer['name']}"):
                            st.write(one_sentence_summary(peer.get("reason", "")))
                            st.caption(peer.get("relationship", ""))
                            show_peer_sentiment(peer["ticker"])
                            st.button(
                                f"Switch primary to {peer['ticker']}",
                                key=f"switch_{symbol}_{peer['ticker']}",
                                on_click=switch_stock,
                                args=(peer["ticker"],),
                            )

                    # Manual additions also get a company information expander.
                    # Use Yahoo's business summary: don't invent a Gemini
                    # recommendation or competitor relationship for custom tickers.
                    ai_symbols = set(recommended_tickers)
                    for custom_symbol in st.session_state[custom_key]:
                        if custom_symbol == symbol or custom_symbol in ai_symbols:
                            continue
                        _, custom_info = get_stock(custom_symbol)
                        custom_name = (custom_info.get("longName")
                                       or custom_info.get("shortName")
                                       or custom_symbol)
                        with st.expander(f"{custom_symbol} — {custom_name}"):
                            st.write(company_one_sentence(custom_info, custom_name))
                            st.caption("Manually added comparison stock · Company overview from Yahoo Finance")
                            show_peer_sentiment(custom_symbol)
                            st.button(
                                f"Switch primary to {custom_symbol}",
                                key=f"switch_custom_{symbol}_{custom_symbol}",
                                on_click=switch_stock,
                                args=(custom_symbol,),
                            )

                    comparison = go.Figure()

                    for stock_symbol in [symbol] + selected:
                        try:
                            peer_data, _ = get_stock(stock_symbol)

                            peer_data = peer_data.loc[
                                (peer_data.index.date >= start_date)
                                & (peer_data.index.date <= end_date)
                            ]

                            if peer_data.empty:
                                continue

                            normalized = (
                                peer_data["Close"]
                                / peer_data["Close"].iloc[0]
                                - 1
                            ) * 100

                            comparison.add_trace(go.Scatter(
                                x=normalized.index,
                                y=normalized,
                                name=stock_symbol,
                                mode="lines",
                                line=dict(color=ticker_colors[stock_symbol]),
                                customdata=peer_data["Close"].to_numpy(),
                                hovertemplate=(
                                    "<b>%{fullData.name}</b><br>"
                                    "%{x|%B %d, %Y}<br>"
                                    "Stock price: <b>$%{customdata:,.2f}</b><br>"
                                    "Return: <b>%{y:+.2f}%</b><extra></extra>"
                                ),
                            ))

                        except Exception:
                            st.warning(
                                f"Could not load {stock_symbol}."
                            )

                    comparison.update_layout(
                        height=380,
                        yaxis_title="Return (%)",
                        xaxis_title="Date",
                        hovermode="closest",
                        hoverlabel=dict(
                            font=dict(size=21),
                        ),
                        margin=dict(l=10, r=10, t=30, b=10)
                    )

                    st.plotly_chart(
                        style_blue_figure(comparison),
                        use_container_width=True
                    )
                    st.caption(
                        "Return (%) is the cumulative percentage change from "
                        "each stock's first available closing price in the selected "
                        "period (starting at 0%). It is not a daily return."
                    )
            # SECTION 3 — FINANCIAL METRICS
            with metrics_col:
                with st.container(border=True):
                    st.subheader("Financial Metrics")

                    groups = {'Basic': ['Alpha', 'Beta', 'Sharpe', 'Trailing P/E', 'ROE', 'Total Return'],
                     'Conservative': ['Volatility',
                                      'Max Drawdown',
                                      'Sortino',
                                      'Historical CAGR',
                                      'Revenue Growth',
                                      'Debt/Equity',
                                      'Free Cash Flow'],
                     'High Returns': ['Revenue Growth',
                                      'Earnings Growth',
                                      'ROIC',
                                      'ROE',
                                      'Operating Margin',
                                      'Historical CAGR',
                                      'Total Return',
                                      'PEG Ratio'],
                     'Value': ['Forward P/E',
                               'Price/Book',
                               'EV/EBITDA',
                               'FCF Yield',
                               'Earnings Yield',
                               'EV/Revenue',
                               'ROIC',
                               'DCF Bear / Share',
                               'DCF Base / Share',
                               'DCF Bull / Share',
                               'DCF Base Upside',
                               'Market-Implied FCF Growth',
                               'Normalized FCF',
                               'FCF Stability',
                               'SBC / Revenue',
                               'Share Dilution (YoY)'],
                     'Health': ['Current Ratio',
                                'Quick Ratio',
                                'Net Debt',
                                'Net Debt / EBITDA',
                                'Interest Coverage',
                                'FCF / Total Debt',
                                'Operating Margin',
                                'Revenue Growth',
                                'ROIC',
                                'Share Dilution (YoY)']}

                    # Put All Metrics FIRST in the radio controls, and select it by default.
                    all_metrics = list(dict.fromkeys(
                        metric
                        for strategy_metrics in groups.values()
                        for metric in strategy_metrics
                    ))
                    groups = {"All Metrics": all_metrics, **groups}
                    strategy_order = ['All Metrics', 'Basic', 'Conservative', 'High Returns', 'Value', 'Health']

                    group = st.radio(
                        "Investment strategy",
                        options=strategy_order,
                        index=0,
                        horizontal=True,
                        key=f"investment_strategy_v2_{symbol}",
                    )

                    analysis_period = st.selectbox(
                        "Historical risk period",
                        ["1 Year", "3 Years", "5 Years"],
                        index=0
                    )

                    period_days = {
                        "1 Year": 365,
                        "3 Years": 1095,
                        "5 Years": 1825
                    }

                    cutoff_metrics = (
                        data.index.max()
                        - pd.Timedelta(
                            days=period_days[analysis_period]
                        )
                    )

                    @st.cache_data(show_spinner=False)
                    def get_benchmark():
                        return yf.Ticker("SPY").history(
                            period="5y",
                            auto_adjust=True
                        )

                    benchmark = get_benchmark()

                    def safe_div(a, b):
                        try:
                            if a is None or b is None or b == 0:
                                return np.nan
                            return float(a) / float(b)
                        except (TypeError, ValueError, ZeroDivisionError):
                            return np.nan

                    def calculate_metrics(history, info):
                        result = {}

                        stock_prices = history.loc[
                            history.index >= cutoff_metrics,
                            "Close"
                        ]

                        market_prices = benchmark.loc[
                            benchmark.index >= cutoff_metrics,
                            "Close"
                        ]

                        aligned = pd.concat(
                            [
                                stock_prices.rename("stock"),
                                market_prices.rename("market")
                            ],
                            axis=1,
                            join="inner"
                        ).dropna()

                        result["Historical CAGR"] = historical_cagr(stock_prices)

                        result.update({
                            "Alpha": np.nan,
                            "Beta": np.nan,
                            "Sharpe": np.nan,
                            "Sortino": np.nan,
                            "Volatility": np.nan,
                            "Max Drawdown": np.nan,
                            "Total Return": np.nan
                        })

                        if len(aligned) >= 61:
                            returns = aligned.pct_change().dropna()
                            r = returns["stock"]
                            m = returns["market"]

                            beta = safe_div(
                                r.cov(m),
                                m.var()
                            )

                            volatility = r.std() * np.sqrt(252)

                            result["Beta"] = beta
                            result["Alpha"] = (
                                (r.mean() - beta * m.mean()) * 252
                                if np.isfinite(beta)
                                else np.nan
                            )
                            result["Volatility"] = volatility
                            result["Sharpe"] = safe_div(
                                r.mean() * 252,
                                volatility
                            )

                            downside = np.minimum(r, 0)
                            downside_dev = np.sqrt(
                                np.mean(downside ** 2) * 252
                            )

                            result["Sortino"] = safe_div(
                                r.mean() * 252,
                                downside_dev
                            )

                            cumulative = (
                                aligned["stock"]
                                / aligned["stock"].iloc[0]
                            )

                            result["Max Drawdown"] = (
                                cumulative / cumulative.cummax() - 1
                            ).min()

                            result["Total Return"] = (
                                cumulative.iloc[-1] - 1
                            )

                        market_cap = info.get("marketCap")
                        fcf = info.get("freeCashflow")
                        net_income = info.get("netIncomeToCommon")

                        debt_equity = info.get("debtToEquity")

                        result.update({
                            "Trailing P/E": info.get("trailingPE"),
                            "Forward P/E": info.get("forwardPE"),
                            "Price/Book": info.get("priceToBook"),
                            "EV/EBITDA": info.get("enterpriseToEbitda"),
                            "EV/Revenue": info.get("enterpriseToRevenue"),
                            "PEG Ratio": info.get("trailingPegRatio"),
                            "ROE": info.get("returnOnEquity"),
                            "ROIC": np.nan,
                            "Revenue Growth": info.get("revenueGrowth"),
                            "Earnings Growth": info.get("earningsGrowth"),
                            "Operating Margin": info.get("operatingMargins"),
                            "Free Cash Flow": fcf,
                            "Debt/Equity": (
                                debt_equity / 100
                                if debt_equity is not None
                                else np.nan
                            ),
                            "FCF Yield": safe_div(fcf, market_cap),
                            "Earnings Yield": safe_div(
                                net_income, market_cap
                            )
                        })

                        return result

                    percent_metrics = {
                        "Alpha", "ROE", "Revenue Growth",
                        "Earnings Growth", "Operating Margin",
                        "Volatility", "Max Drawdown",
                        "Total Return", "Historical CAGR",
                        "FCF Yield", "Earnings Yield", "ROIC"
                    }

                    def format_value(name, value):
                        try:
                            if value is None or not np.isfinite(float(value)):
                                return "N/A"

                            value = float(value)

                            if name in EXTRA_METRIC_NAMES:

                                return format_extra_metric(name, value)


                            if name in percent_metrics:
                                return f"{value:.2%}"

                            if name == "Free Cash Flow":
                                return f"${value / 1e9:,.2f}B"

                            return f"{value:,.2f}"
                        except (ValueError, TypeError):
                            return "N/A"

                    selected_metrics = st.multiselect(
                        "Choose metrics to display",
                        options=groups[group],
                        default=groups[group],
                        key=f"metric_group_{group}"
                    )

                    comparison_tickers = list(
                        dict.fromkeys([symbol] + selected)
                    )

                    rows = []

                    with st.spinner("Calculating metrics..."):
                        calculated = {}

                        for stock_symbol in comparison_tickers:
                            try:
                                history, stock_info = get_stock(
                                    stock_symbol
                                )

                                calculated[stock_symbol] = calculate_metrics(
                                    history,
                                    stock_info
                                )
                                # si dcf group metrics — compute only if any extra is selected
                                if any(m in EXTRA_METRIC_NAMES for m in selected_metrics):
                                    latest_for_screen = (history["Close"].iloc[-1]
                                                         if not history.empty and "Close" in history else None)
                                    calculated[stock_symbol].update(
                                        compute_extra_metrics(stock_symbol, stock_info, latest_for_screen)
                                    )

                                if "ROIC" in selected_metrics:
                                    try:
                                        calculated[stock_symbol]["ROIC"] = calculate_roic(
                                            stock_symbol
                                        )
                                    except Exception:
                                        calculated[stock_symbol]["ROIC"] = np.nan
                                                
                            except Exception:
                                calculated[stock_symbol] = {}

                        for metric in selected_metrics:
                            row = {"Metric": metric}

                            for stock_symbol in comparison_tickers:
                                value = calculated[stock_symbol].get(metric)

                                row[stock_symbol] = format_value(
                                    metric, value
                                )

                            rows.append(row)

            
                    if rows:
                        columns = ["Metric"] + comparison_tickers

                        table_html = """
                        <style>
                        /* This table runs inside an isolated Streamlit iframe,
                           so it must declare its own colors in both themes. */
                        :root { color-scheme: dark; }
                        html, body { margin: 0; background: transparent; }
                        .metrics-table {
                            width: 100%;
                            border-collapse: collapse;
                            font-family: Inter, 'Segoe UI', Arial, sans-serif;
                            font-size: 15px;
                            color: #f1f5f9;
                            background: #0E1A29;
                        }
                        .metrics-table th, .metrics-table td {
                            border-bottom: 1px solid #24435D;
                            padding: 9px;
                            text-align: left;
                            vertical-align: middle;
                        }
                        .metrics-table th { font-weight: 700; }
                        .metric-name {
                            font-weight: 700;
                            cursor: help;
                            background: #152D43;
                            transition: background-color 0.12s ease;
                        }
                        .metric-name:hover { background: #244D6E; }
                        </style>
                        <div style="overflow-x:auto;">
                        <table class="metrics-table">
                        <thead><tr>
                        """

                        for col in columns:
                            table_html += (
                                "<th>"
                                + html.escape(col) + "</th>"
                            )

                        table_html += "</tr></thead><tbody>"

                        for row in rows:
                            metric = row["Metric"]
                            explanation = EXPLANATIONS.get(metric, EXTRA_EXPLANATIONS.get(metric, "No explanation available."))

                            table_html += "<tr>"

                            table_html += (
                                "<td class='metric-name' title='"
                                + html.escape(explanation, quote=True)
                                + "'>"
                                + html.escape(metric)
                                + "</td>"
                            )

                            for stock_symbol in comparison_tickers:
                                value = str(row.get(stock_symbol, "N/A"))

                                table_html += (
                                    "<td>"
                                    + html.escape(value)
                                    + "</td>"
                                )

                            table_html += "</tr>"

                        table_html += "</tbody></table></div>"

                        components.html(
                            table_html,
                            height=570,
                            scrolling=True
                        )

                    else:
                        st.info("Select at least one metric.")

                    st.caption(
                        "DCF screens use a simplified normalized free-cash-flow proxy: 5-year growth "
                        "-5% / +5% / +15% (Bear / Base / Bull), 10% equity hurdle and 2% terminal growth. "
                        "Known stock-based compensation is deducted without additionally modeling dilution. "
                        "This is NOT a complete FCFF/WACC valuation or a downside floor; missing inputs show N/A."
                    )
                    st.caption(
                        "Risk metrics use daily adjusted returns against SPY "
                        "with a 0% risk-free rate. Historical CAGR uses adjusted "
                        "closing prices. ROIC uses annual financial statements "
                        "and may be unavailable for some companies."
                    )




        # SECTION 4 — NEWS & SENTIMENT
        # News Sentiment now lives on its dedicated page.




    except Exception as exc:
        st.error(f"Unable to load dashboard: {exc}")

else:
    st.info("Enter a ticker and click Load Stock.")

# si_20261120_repairs_v1
