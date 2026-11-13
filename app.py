import html
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import plotly.graph_objects as go

from ai_peers import recommend_peers
from advanced_metrics import historical_cagr, calculate_roic
from metric_explanations import EXPLANATIONS
from news_sentiment import fetch_stock_news
from finbert_sentiment import analyze_finbert
from ai_events import group_news_events
from gnews_history import update_gnews, load_gnews, score_unscored

# Load API keys from the existing project .env file.
load_dotenv()


st.set_page_config(
    page_title="Stock Intelligence Dashboard",
    layout="wide"
)



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


def switch_stock(symbol):
    st.session_state.primary = symbol
    st.session_state.loaded = True


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


st.title("Stock Intelligence Dashboard")
st.caption("AI-powered stock research and competitor analysis")

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
        with st.spinner("Loading stock data..."):
            data, info = get_stock(symbol)

        if data.empty:
            st.error(f"No price data found for {symbol}.")
            st.stop()

        company_name = info.get("longName", symbol)
        description = info.get(
            "longBusinessSummary",
            company_name
        )

        st.subheader(f"{company_name} ({symbol})")

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

        selected = []

        # SECTION 1 — PRIMARY STOCK (FULL WIDTH)
        with st.container(border=True):
            st.subheader("Stock Price History")

            period = st.selectbox(
                "Price history",
                ["1 Month", "3 Months", "6 Months", "1 Year", "5 Years"],
                index=3
            )

            price_view = st.radio(
                "Stocks to display",
                ["Primary Stock Only", "Include Competitors"],
                horizontal=True,
                key=f"price_view_{symbol}",
            )

            price_data = data

            days = {
                "1 Month": 30,
                "3 Months": 90,
                "6 Months": 180,
                "1 Year": 365,
                "5 Years": 1825
            }

            cutoff = (
                price_data.index.max()
                - pd.Timedelta(
                    days=days[period]
                )
            )

            price_data = data[data.index >= cutoff].dropna(subset=["Close"])
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
                            <span style="font-size:1rem;">Today's Trading Price</span>
                            <strong style="font-size:1.15rem;">${last_price:,.2f}</strong>
                        </div>
                        <div style="color:var(--text-color); opacity:.65; font-size:.83rem; margin-top:3px;">
                            Latest adjusted close: {last_date:%b %d, %Y} (not a live quote)
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

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=price_data.index,
                y=price_data["Close"],
                name=symbol,
                mode="lines",
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
                    line=dict(dash="dash", width=2, color="#F1B755"),
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
                available_peers = [
                    p.get("ticker", "").upper()
                    for p in peers
                    if p.get("ticker", "").upper() not in ("", symbol)
                ]
                available_peers = list(dict.fromkeys(available_peers))
                selected_peers = st.session_state.get(
                    f"peers_{symbol}", available_peers[:3]
                )
                selected_peers = [
                    ticker for ticker in selected_peers
                    if ticker in available_peers
                ]
                if selected_peers:
                    for peer_symbol in selected_peers:
                        try:
                            peer_history, _ = get_stock(peer_symbol)
                            peer_history = peer_history.loc[
                                peer_history.index >= cutoff
                            ]
                            if peer_history.empty:
                                continue
                            fig.add_trace(go.Scatter(
                                x=peer_history.index,
                                y=peer_history["Close"],
                                name=peer_symbol,
                                mode="lines",
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

            st.plotly_chart(fig, use_container_width=True)
            if price_view == "Include Competitors":
                st.caption(
                    "This chart compares actual share prices (USD), not percentage returns. "
                    "Use the chart below for normalized return comparisons."
                )

        with st.container(key="peer_metrics_equal_height"):
            # SECTIONS 2 & 3 — SHARED PEER SELECTION
            peers_col, metrics_col = st.columns(2)

            # SECTION 2 — AI COMPETITORS
            with peers_col:
                with st.container(border=True):
                    st.subheader("AI Competitor Comparison")

                    if peer_error:
                        st.warning(
                            "AI recommendations unavailable: "
                            + peer_error
                        )

                    peers = [p for p in peers if p.get("ticker", "").upper() != symbol]

                    if peers:
                        st.caption("Select competitors to compare.")

                        options = [p["ticker"] for p in peers]

                        selected = st.multiselect(
                            "Competitors",
                            options=options,
                            default=options,
                            key=f"peers_{symbol}"
                        )

                        for peer in peers:
                            with st.expander(
                                f"{peer['ticker']} — {peer['name']}"
                            ):
                                st.write(peer["reason"])
                                st.caption(peer["relationship"])

                                st.button(
                                    f"Switch primary to {peer['ticker']}",
                                    key=f"switch_{symbol}_{peer['ticker']}",
                                    on_click=switch_stock,
                                    args=(peer["ticker"],)
                                )

                        comparison = go.Figure()

                        for stock_symbol in [symbol] + selected:
                            try:
                                peer_data, _ = get_stock(stock_symbol)

                                peer_data = peer_data[
                                    peer_data.index >= cutoff
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
                            comparison,
                            use_container_width=True
                        )
                        st.caption(
                            "Return (%) is the cumulative percentage change from "
                            "each stock's first available closing price in the selected "
                            "period (starting at 0%). It is not a daily return."
                        )
                    elif not peer_error:
                        st.info("No validated competitors found.")

            # SECTION 3 — FINANCIAL METRICS
            with metrics_col:
                with st.container(border=True):
                    st.subheader("Financial Metrics")

                    groups = {
                        "Basic": [
                            "Alpha", "Beta", "Sharpe",
                            "Trailing P/E", "ROE", "Total Return"
                        ],
                        "Conservative": [
                            "Volatility", "Max Drawdown",
                            "Sortino", "Historical CAGR", "Revenue Growth",
                            "Debt/Equity", "Free Cash Flow"
                        ],
                        "High Returns": [
                            "Revenue Growth", "Earnings Growth",
                            "ROIC", "ROE", "Operating Margin",
                            "Historical CAGR", "Total Return",
                            "PEG Ratio"
                        ],
                        "Value": [
                            "Forward P/E", "Price/Book",
                            "EV/EBITDA", "FCF Yield",
                            "Earnings Yield", "EV/Revenue",
                            "ROIC"
                        ]
                    }

                    # Put All Metrics FIRST in the radio controls, and select it by default.
                    all_metrics = list(dict.fromkeys(
                        metric
                        for strategy_metrics in groups.values()
                        for metric in strategy_metrics
                    ))
                    groups = {"All Metrics": all_metrics, **groups}
                    strategy_order = ["All Metrics", "Basic", "Conservative", "High Returns", "Value"]

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
                            font-family: Arial, sans-serif;
                            font-size: 15px;
                            color: #f1f5f9;
                            background: #17191f;
                        }
                        .metrics-table th, .metrics-table td {
                            border-bottom: 1px solid #3b414c;
                            padding: 9px;
                            text-align: left;
                            vertical-align: middle;
                        }
                        .metrics-table th { font-weight: 700; }
                        .metric-name {
                            font-weight: 700;
                            cursor: help;
                            background: #30343d;
                            transition: background-color 0.12s ease;
                        }
                        .metric-name:hover { background: #48505d; }
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
                            explanation = EXPLANATIONS.get(
                                metric, "No explanation available."
                            )

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
                            height=350,
                            scrolling=True
                        )

                    else:
                        st.info("Select at least one metric.")

                    st.caption(
                        "Risk metrics use daily adjusted returns against SPY "
                        "with a 0% risk-free rate. Historical CAGR uses adjusted "
                        "closing prices. ROIC uses annual financial statements "
                        "and may be unavailable for some companies."
                    )




        # SECTION 4 — NEWS & SENTIMENT
        with st.container(border=True):
            st.subheader("News & Sentiment")

            st.caption(
                f"Recent news coverage for {company_name} ({symbol})"
            )

            refresh_news = st.button(
                "Refresh News",
                key=f"refresh_news_{symbol}"
            )
            refresh_timestamp_key = f"last_news_refresh_{symbol}"
            refresh_label = st.empty()
            if refresh_news:
                # Force Yahoo to fetch again (not just reuse Streamlit's cache).
                fetch_stock_news.clear()

                # Force Gemini grouping even if the headline snapshot is unchanged.
                for suffix in (
                    "grouped_events", "grouped_articles", "grouped_snapshot",
                    "grouped_attempted_snapshot", "grouped_error"
                ):
                    st.session_state.pop(f"{suffix}_{symbol}", None)
                # Clear the event function's own Streamlit cache, if present.
                clear_events = getattr(group_news_events, "clear", None)
                if callable(clear_events):
                    clear_events()

                # Refresh GNews even when the Yahoo sentiment tab is selected.
                gnews_refresh_key = os.getenv("GNEWS_API_KEY", "").strip()
                if gnews_refresh_key:
                    try:
                        with st.spinner("Refreshing GNews headlines..."):
                            _, gnews_refresh_status = update_gnews(
                                symbol, company_name, gnews_refresh_key, force=True
                            )
                            score_unscored(symbol)
                        # An API error can be returned as a status, rather than thrown.
                        if "failed" in gnews_refresh_status.lower():
                            st.warning(gnews_refresh_status)
                    except Exception as exc:
                        st.warning(f"GNews refresh failed: {exc}")
                else:
                    st.info("GNews was skipped: GNEWS_API_KEY is not set in .env.")

                # Local date/time at which the user requested the full refresh.
                st.session_state[refresh_timestamp_key] = (
                    datetime.now().astimezone().strftime("%b %d, %Y at %I:%M:%S %p %Z")
                )

            if refresh_timestamp_key in st.session_state:
                refresh_label.caption(
                    f"Last refreshed on: {st.session_state[refresh_timestamp_key]}"
                )
            else:
                refresh_label.caption("Last refreshed on: Not manually refreshed yet")

            try:
                with st.spinner("Analyzing recent headlines..."):
                    news_df = fetch_stock_news(symbol)

                if news_df.empty:
                    st.info(
                        "No recent news articles were returned "
                        "for this stock."
                    )

                else:
                    
                    # FinBERT is the sole sentiment model used by the dashboard.
                    # Yahoo's original VADER scores are replaced before any analysis.
                    try:
                        with st.spinner("Analyzing headlines with FinBERT..."):
                            finbert_results = analyze_finbert(
                                tuple(news_df["Title"].tolist())
                            )

                        # Preserve one row per original article, even if titles repeat.
                        if len(finbert_results) != len(news_df):
                            raise ValueError("FinBERT returned an unexpected number of results.")
                        news_df = news_df.reset_index(drop=True).copy()
                        finbert_results = finbert_results.reset_index(drop=True)
                        news_df["Sentiment"] = finbert_results["FinBERT Sentiment"]
                        news_df["Score"] = finbert_results["FinBERT Score"]
                    except Exception as exc:
                        st.error(
                            f"FinBERT sentiment analysis failed: {exc}. "
                            "News sentiment and event analysis cannot run until FinBERT works."
                        )
                        st.stop()


                    sentiment_col, events_col = st.columns(2)

                    with sentiment_col:
                        st.markdown("#### Recent Sentiment Analysis")
                        sentiment_source = st.radio(
                            "News source",
                            ["Recent — Yahoo Finance", "Last 30 Days — GNews"],
                            horizontal=True,
                            key=f"sentiment_source_{symbol}",
                        )

                        if sentiment_source == "Recent — Yahoo Finance":
                            # Today's Yahoo headlines only. Other sections continue
                            # using the full available Yahoo feed.
                            today_news = todays_articles(news_df)
                            today_label = datetime.now(MARKET_NEWS_TZ).strftime("%B %d, %Y")
                            st.caption(f"Yahoo Finance headlines published today ({today_label}, Eastern Time).")

                            labels = ["Positive", "Neutral", "Negative"]
                            sentiment_scope = st.radio(
                                "Sentiment distribution",
                                ["Primary Stock Only", "Compare Competitors"],
                                horizontal=True,
                                key=f"sentiment_scope_{symbol}",
                            )

                            sentiment_counts = {
                                symbol: {label: int((today_news["Sentiment"] == label).sum())
                                         for label in labels}
                            }
                            if sentiment_scope == "Compare Competitors":
                                for peer_symbol in selected:
                                    try:
                                        with st.spinner(f"Analyzing today's {peer_symbol} headlines..."):
                                            sentiment_counts[peer_symbol] = get_competitor_sentiment_counts(peer_symbol)
                                    except Exception as exc:
                                        st.warning(f"Could not analyze {peer_symbol}: {exc}")

                            total = len(today_news)
                            # The detailed bar chart below already shows this distribution.
                            # Avoid displaying a redundant percentage chart above it.
                            if sentiment_scope == "Primary Stock Only":
                                if total == 0:
                                    st.info("Yahoo Finance has not returned any headlines dated today for this stock. Try Refresh News later.")
                                else:
                                    fig_sentiment = go.Figure()
                                    fig_sentiment.add_trace(go.Bar(
                                        x=labels,
                                        y=[sentiment_counts[symbol][label] for label in labels],
                                        text=[sentiment_counts[symbol][label] for label in labels],
                                        textposition="outside",
                                        marker_color=["#33A786", "#8793A3", "#D26A75"],
                                        hovertemplate="%{x}: %{y} headlines<extra></extra>",
                                    ))
                                    fig_sentiment.update_layout(
                                        height=310,
                                        xaxis_title="Sentiment category",
                                        yaxis_title="Today's headlines",
                                        margin=dict(l=10, r=10, t=25, b=10),
                                        font=dict(size=15),
                                    )
                                    st.plotly_chart(fig_sentiment, use_container_width=True)
                            else:
                                available = {ticker: counts for ticker, counts in sentiment_counts.items()
                                             if sum(counts.values()) > 0}
                                if not available:
                                    st.info("No headlines dated today were found for the selected stocks.")
                                else:
                                    fig_sentiment = go.Figure()
                                    for label in labels:
                                        tickers = list(available)
                                        totals = [sum(available[t].values()) for t in tickers]
                                        counts = [available[t][label] for t in tickers]
                                        percentages = [100 * count / n for count, n in zip(counts, totals)]
                                        fig_sentiment.add_trace(go.Bar(
                                            name=label,
                                            x=tickers,
                                            y=percentages,
                                            marker_color={"Positive": "#33A786", "Neutral": "#8793A3", "Negative": "#D26A75"}[label],
                                            customdata=list(zip(counts, totals)),
                                            hovertemplate=(
                                                "%{x}<br>" + label + ": %{y:.1f}%"
                                                "<br>Articles: %{customdata[0]} of %{customdata[1]}"
                                                "<extra></extra>"
                                            ),
                                        ))
                                    fig_sentiment.update_layout(
                                        barmode="group",
                                        height=340,
                                        xaxis_title="Stock ticker",
                                        yaxis_title="Share of today's headlines (%)",
                                        yaxis_range=[0, 110],
                                        legend_title="FinBERT sentiment",
                                        margin=dict(l=10, r=10, t=30, b=10),
                                        font=dict(size=14),
                                    )
                                    st.plotly_chart(fig_sentiment, use_container_width=True)
                                    missing = [t for t, counts in sentiment_counts.items() if sum(counts.values()) == 0]
                                    if missing:
                                        st.caption("No headlines dated today: " + ", ".join(missing) + ".")
                                st.caption(
                                    "Percentages use only today's available Yahoo Finance headlines for each stock. "
                                    "Coverage and headline counts may vary between stocks."
                                )


                        else:
                            st.markdown("##### Last 30 Days — GNews")
                            st.caption(
                                "GNews articles analyzed with FinBERT. "
                                "Days without articles remain missing; available "
                                "coverage may be incomplete."
                            )
                            days_back = 30
                            gnews_key = os.getenv("GNEWS_API_KEY", "").strip()
                            if not gnews_key:
                                st.info("To activate GNews, add GNEWS_API_KEY to your .env file and restart Streamlit.")
                            else:
                                try:
                                    with st.spinner("Updating historical news (cached for 24 hours)..."):
                                        new_count, fetch_status = update_gnews(
                                            symbol, company_name, gnews_key, force=False
                                        )
                                    st.caption(fetch_status)
                                    with st.spinner("Scoring new GNews headlines with FinBERT..."):
                                        score_unscored(symbol)
                                except Exception as exc:
                                    st.warning(f"Historical news update unavailable: {exc}")
                
                                historical = load_gnews(symbol, days_back)
                                historical = historical.dropna(subset=["Date", "Score"])
                                if historical.empty:
                                    st.info("No saved, scored GNews articles in this period yet.")
                                else:
                                    historical["Day"] = historical["Date"].dt.date
                                    daily = (historical.groupby("Day", as_index=False)
                                             .agg(Average_Sentiment=("Score", "mean"),
                                                  Articles=("Score", "size")))
                                    daily["Day"] = pd.to_datetime(daily["Day"])
                                    chart = go.Figure()
                                    chart.add_trace(go.Scatter(
                                        x=daily["Day"], y=daily["Average_Sentiment"],
                                        mode="lines+markers", name="Daily FinBERT sentiment",
                                        customdata=daily[["Articles"]],
                                        hovertemplate="%{x|%b %d, %Y}<br>Score: %{y:+.2f}"
                                                      "<br>Articles: %{customdata[0]}<extra></extra>"
                                    ))
                                    chart.add_hline(y=0, line_dash="dash", line_color="gray")
                                    chart.update_layout(
                                        height=350, yaxis_title="Average sentiment (-1 to +1)",
                                        yaxis_range=[-1, 1], xaxis_title="Publication date",
                                        xaxis_range=[pd.Timestamp.now(tz="UTC").tz_localize(None)
                                                     - pd.Timedelta(days=days_back),
                                                     pd.Timestamp.now(tz="UTC").tz_localize(None)],
                                        margin=dict(l=10, r=10, t=20, b=10)
                                    )
                                    st.plotly_chart(chart, use_container_width=True)
                                    first_day = daily["Day"].min().date()
                                    last_day = daily["Day"].max().date()
                                    st.caption(
                                        f"{len(historical)} saved headlines across {len(daily)} days "
                                        f"with coverage ({first_day} to {last_day}). "
                                        "Unobserved days are gaps; the graph does not prove "
                                        "continuous or comprehensive coverage."
                                    )


                    with events_col:
                        # GEMINI EVENT GROUPING
                        st.markdown("#### AI News Event Grouping")

                        st.caption(
                            "Combine headlines about the same underlying "
                            "event from the available Yahoo Finance headlines "
                            "(not just today). Gemini runs automatically when "
                            "headlines change or you refresh the news."
                        )

                        event_key = f"grouped_events_{symbol}"
                        articles_key = f"grouped_articles_{symbol}"
                        snapshot_key = f"grouped_snapshot_{symbol}"

                        # Detect changes in headlines or classifications.
                        current_snapshot = tuple(
                            zip(
                                news_df["Title"].astype(str),
                                news_df["Date"].astype(str),
                                news_df["Sentiment"].astype(str)
                            )
                        )

                        # Group automatically once per unique headline/sentiment snapshot.
                        # Do not call Gemini on ordinary Streamlit reruns (e.g., sliders).
                        attempted_key = f"grouped_attempted_snapshot_{symbol}"
                        error_key = f"grouped_error_{symbol}"

                        # Always display a dedicated retry, including when Gemini
                        # is overloaded or returned zero events. This retries only
                        # grouping; it does not refetch Yahoo or GNews.
                        retry_grouping = st.button(
                            "Retry AI Event Grouping",
                            key=f"retry_events_{symbol}",
                            help="Try Gemini again using the already loaded Yahoo headlines.",
                        )
                        if retry_grouping:
                            st.session_state.pop(attempted_key, None)
                            st.session_state.pop(error_key, None)
                            clear_events = getattr(group_news_events, "clear", None)
                            if callable(clear_events):
                                clear_events()

                        if st.session_state.get(attempted_key) != current_snapshot:
                            st.session_state[attempted_key] = current_snapshot
                            st.session_state.pop(error_key, None)
                            try:
                                with st.spinner("Automatically grouping news events with Gemini..."):
                                    events_df, event_articles = group_news_events(
                                        news_df, symbol
                                    )
                                st.session_state[event_key] = events_df
                                st.session_state[articles_key] = event_articles
                                st.session_state[snapshot_key] = current_snapshot
                            except Exception as exc:
                                st.session_state[error_key] = str(exc)

                        if st.session_state.get(error_key):
                            st.warning(
                                f"Automatic event grouping failed: {st.session_state[error_key]}. "
                                "Use Retry AI Event Grouping above to try again."
                            )

                        if (
                            event_key in st.session_state
                            and st.session_state.get(snapshot_key)
                            == current_snapshot
                        ):
                            events_df = st.session_state[event_key]
                            event_articles = st.session_state[articles_key]

                            if events_df is None or events_df.empty:
                                st.info(
                                    "Gemini returned no grouped events. "
                                    "Use Retry AI Event Grouping above to try again."
                                )
                                events_df = pd.DataFrame(columns=["Articles"])

                            st.markdown("#### Media Coverage Threshold")

                            min_articles = st.slider(
                                "Minimum articles per event",
                                min_value=1,
                                max_value=10,
                                value=5,
                                step=1,
                                key=f"min_event_articles_{symbol}"
                            )

                            filtered_events = events_df[
                                events_df["Articles"] >= min_articles
                            ].copy()

                            st.caption(
                                f"{len(filtered_events)} of "
                                f"{len(events_df)} events meet the "
                                f"{min_articles}+ article threshold."
                            )


                            c1, c2 = st.columns(2)

                            c1.metric(
                                "Total Events",
                                len(events_df)
                            )

                            c2.metric(
                                "Qualifying Events",
                                len(filtered_events)
                            )

                            st.caption(
                                f"{len(news_df)} headlines grouped into "
                                f"{len(events_df)} distinct events."
                            )

                            for _, event in filtered_events.iterrows():
                                event_id = event["Event ID"]

                                with st.expander(
                                    f"{event['Event']} "
                                    f"({event['Articles']} articles)"
                                ):
                                    st.write(
                                        f"**First observed:** "
                                        f"{event['First Seen']:%b %d, %Y %I:%M %p %Z}"
                                    )
                                    st.write(
                                        f"**Headline sentiment:** "
                                        f"{event['Sentiment']}"
                                    )
                                    st.write(
                                        f"**Report status:** "
                                        f"{event['Report Status']}"
                                    )
                                    st.write(
                                        f"**Grouping rationale:** "
                                        f"{event['Reason']}"
                                    )

                                    group = event_articles[event_id]

                                    for _, article in group.iterrows():
                                        title = article["Title"]
                                        url = str(article["URL"])

                                        if url.startswith(
                                            ("https://", "http://")
                                        ):
                                            st.markdown(
                                                f"- [{title}]({url})"
                                            )
                                        else:
                                            st.write(f"- {title}")

                        elif event_key in st.session_state:
                            st.info(
                                "Headlines or sentiment classifications "
                                "have changed. Group events again to "
                                "refresh the analysis."
                            )



                    # Visually separate full-width headlines from the two sentiment panels.
                    st.divider()
                    # NEWS FILTER
                    st.markdown("#### Recent Headlines")

                    sentiment_filter = st.radio(
                        "Filter by sentiment",
                        ["All", "Positive", "Neutral", "Negative"],
                        horizontal=True,
                        key=f"news_filter_{symbol}"
                    )

                    headline_sort = st.radio(
                        "Sort headlines by",
                        ["Newest First", "Oldest First", "Most Extreme Sentiment"],
                        horizontal=True,
                        key=f"headline_sort_{symbol}",
                        help=("Most Extreme Sentiment ranks headlines by absolute FinBERT "
                              "score (closest to -1 or +1 first). The sentiment filter "
                              "is applied before sorting."),
                    )

                    filtered_news = news_df.copy()

                    if sentiment_filter != "All":
                        filtered_news = filtered_news[
                            filtered_news["Sentiment"]
                            == sentiment_filter
                        ]

                    if headline_sort == "Most Extreme Sentiment":
                        filtered_news = (
                            filtered_news.assign(
                                _strength=pd.to_numeric(filtered_news["Score"], errors="coerce").abs()
                            )
                            .sort_values(["_strength", "Date"], ascending=[False, False], kind="stable")
                            .drop(columns="_strength")
                        )
                    else:
                        filtered_news = filtered_news.sort_values(
                            "Date", ascending=(headline_sort == "Oldest First"), kind="stable"
                        )

                    for _, article in filtered_news.head(15).iterrows():
                        headline = article["Title"]
                        url = article["URL"]
                        score = article["Score"]
                        label = article["Sentiment"]

                        if url.startswith(("https://", "http://")):
                            st.markdown(
                                f"**[{headline}]({url})**"
                            )
                        else:
                            st.markdown(f"**{headline}**")

                        st.caption(
                            f"{article['Source']} | "
                            f"{article['Date']:%b %d, %Y} | "
                            f"{label} ({score:+.2f})"
                        )


            except Exception as exc:
                st.warning(
                    f"News analysis unavailable: {exc}"
                )




    except Exception as exc:
        st.error(f"Unable to load dashboard: {exc}")

else:
    st.info("Enter a ticker and click Load Stock.")
