"""News Screen — drop this file into your Streamlit project's pages/ folder.

Reuses the existing project's news_sentiment.fetch_stock_news and
finbert_sentiment.analyze_finbert when available. No new API keys required.
"""

from __future__ import annotations

import html
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf
from streamlit_js_eval import streamlit_js_eval

# Multipage scripts live inside pages/, but project helper modules live next to app.py.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from news_sentiment import fetch_stock_news as existing_fetch_stock_news
except ImportError:
    existing_fetch_stock_news = None

try:
    from finbert_sentiment import analyze_finbert
except ImportError:
    analyze_finbert = None

st.set_page_config(
    page_title="News Screen | Stock Intelligence",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MARKET_TZ = ZoneInfo("America/New_York")
DEFAULT_WATCHLIST = ["NVDA", "AAPL", "GOOG", "MSFT", "AMZN", "TSM", "SPCX", "META"]
COMPANY_NAMES = {
    "NVDA": "NVIDIA Corporation",
    "AAPL": "Apple Inc.",
    "GOOG": "Alphabet Inc.",
    "GOOGL": "Alphabet Inc.",
    "MSFT": "Microsoft Corporation",
    "AMZN": "Amazon.com, Inc.",
    "TSM": "Taiwan Semiconductor Manufacturing",
    "META": "Meta Platforms, Inc.",
    "SPCX": "Space Exploration Technologies Corp.",
}
MAX_TICKERS = 12
BROWSER_WATCHLIST_KEY = "stock_intelligence_news_watchlist_v1"
MAX_HEADLINES = 6
TICKER_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.\-^=]{0,14}$")


# --- Presentation -----------------------------------------------------------
st.markdown(
    """
<style>
:root {
  --ns-bg: #090a08;
  --ns-panel: #11130e;
  --ns-border: #292b20;
  --ns-ink: #e7e6d2;
  --ns-muted: #77796b;
  --ns-gold: #d8b343;
  --ns-green: #51bb86;
  --ns-red: #e56a73;
}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background: var(--ns-bg) !important;
}
[data-testid="stAppViewBlockContainer"] {
  padding-top: 1.4rem !important;
  max-width: 1800px !important;
  padding-left: 1.15rem !important;
  padding-right: 1.15rem !important;
}
[data-testid="stSidebar"] { background: #11130e !important; }
[data-testid="stMarkdownContainer"] p { margin-bottom: 0; }
[data-testid="stButton"] button[kind="secondary"],
[data-testid="stPopover"] button {
  border-radius: 30px;
  background: #14160f;
  border: 1px solid #343426;
  color: #b9a254;
  font-size: .78rem;
  font-weight: 600;
  min-height: 34px;
  padding: .23rem .6rem;
  white-space: nowrap;
}
[data-testid="stButton"] button[kind="secondary"]:hover,
[data-testid="stPopover"] button:hover {
  border-color: var(--ns-gold);
  color: #edce68;
}
[data-testid="stButton"] button[kind="primary"] {
  background: #c9a33b;
  color: #171409;
  border: 1px solid #c9a33b;
  font-weight: 700;
  border-radius: 8px;
  min-height: 40px;
}
[data-testid="stButton"] button[kind="primary"]:hover {
  background: #efc65a;
  border-color: #efc65a;
  color: #0d0c07;
}
.ns-masthead { display:flex; align-items:center; gap:13px; min-height:56px; }
.ns-icon {
  background:#d5af42; color:#181405; width:32px; height:32px;
  border-radius:7px; display:flex; align-items:center; justify-content:center;
  font-size:20px; font-weight:800;
}
.ns-title {
  font-weight:900; color:#e6ca6b; font-size:20px; letter-spacing:.28em;
  line-height:1.15;
}
.ns-subtitle {color:var(--ns-muted); font-size:12px; margin-top:4px;}
.ns-toprule { height:1px; background:linear-gradient(90deg,#292a1c,#7b6426,#292a1c); margin:8px 0 16px; }
.ns-section-label {color:#77796b; font-size:11px; letter-spacing:.15em; font-weight:800; padding-top:10px; }
.ns-agent-label {color:#858475; font-size:11px; padding-top:12px; text-align:right;}
.ns-agent-label b {color:#d7c16a; font-weight:700;}
.ns-grid {
  display:grid; grid-template-columns:repeat(4,minmax(0,1fr));
  align-items:stretch; gap:12px; margin:15px 0 8px;
}
.ns-card {
  min-width:0; min-height:417px; padding:16px 16px 10px;
  background:linear-gradient(135deg,#11130e 0%, #10110c 100%);
  border:1px solid #282b1e; border-radius:13px;
  display:flex; flex-direction:column;
}
.ns-card.ns-featured {border-color:#5d5021; box-shadow:0 0 0 1px rgba(205,174,68,.05) inset;}
.ns-cardtop {display:flex; align-items:flex-start; justify-content:space-between; gap:7px;}
.ns-symbol {font-size:21px; line-height:1.08; color:var(--ns-gold); font-weight:900; letter-spacing:-.035em;}
.ns-company {font-size:11px; color:#818274; margin-top:4px; min-height:26px; line-height:1.3; overflow:hidden;}
.ns-quote {text-align:right; font-variant-numeric:tabular-nums; min-width:86px;}
.ns-price {font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:16px; color:#d8d7bc; font-weight:700;}
.ns-change {font-size:10px; margin-top:3px; font-weight:700;}
.ns-dollar {color:#646657; font-size:10px; margin-top:3px;}
.ns-pos {color:var(--ns-green) !important;}
.ns-neg {color:var(--ns-red) !important;}
.ns-neutral {color:#a9a99b !important;}
.ns-status {
  display:inline-flex; align-items:center; max-width:100%; width:fit-content;
  background:#1b1d15; border-radius:30px; color:#969a88;
  font-size:11px; padding:6px 10px; margin:7px 0 9px;
  font-weight:650; gap:7px;
}
.ns-status.ns-ready {background:#282210;color:#e2bf58;}
.ns-status.ns-positive {background:#10271b;color:#82d0a0;}
.ns-status.ns-negative {background:#311b1b;color:#f09999;}
.ns-status.ns-mixed {background:#22221d;color:#c6c6b0;}
.ns-dot {width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block;flex:none;}
.ns-article {display:grid;grid-template-columns:48px minmax(0,1fr); gap:7px;
  border-top:1px solid #24271d; padding:10px 0 9px; text-decoration:none !important; min-height:53px;
  color:var(--ns-ink) !important;
}
.ns-article:hover .ns-headline {color:#f4d978;}
.ns-date {font-size:10px;color:#838477;padding-top:2px;font-weight:600;white-space:nowrap;}
.ns-headline {font-size:12px;line-height:1.34;display:-webkit-box;-webkit-box-orient:vertical;
  -webkit-line-clamp:2;overflow:hidden;color:#d6d5be;transition:color .12s;overflow-wrap:anywhere;}
.ns-source {font-size:10px;color:#74766a;margin-top:4px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;}
.ns-none {color:#858678;font-size:12px; border-top:1px solid #28291e; padding:16px 0; line-height:1.55;}
.ns-footer {font-size:11px;color:#757769;margin:12px 0 20px;line-height:1.6;}
@media (max-width:1200px) {.ns-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media (max-width:640px) {
  .ns-grid{grid-template-columns:1fr;}
  .ns-title{font-size:17px;letter-spacing:.19em;}
  .ns-card{min-height:0;}
  [data-testid="stAppViewBlockContainer"]{padding-left:.75rem !important;padding-right:.75rem !important;}
}
</style>
""",
    unsafe_allow_html=True,
)


# --- Data helpers -----------------------------------------------------------
def clean_ticker(raw: str) -> str:
    symbol = (raw or "").strip().upper()
    return symbol if TICKER_PATTERN.fullmatch(symbol) else ""


def safe_link(raw: object) -> str:
    """Accept article URLs only; never interpolate untrusted schemes into HTML."""
    if not isinstance(raw, str):
        return ""
    value = raw.strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
            return value
    except ValueError:
        pass
    return ""


def news_datetime(raw: object) -> datetime | None:
    if raw is None:
        return None
    try:
        if isinstance(raw, (int, float)) and math.isfinite(float(raw)):
            timestamp = float(raw)
            if timestamp > 1e12:  # Unix milliseconds
                timestamp /= 1000.0
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(MARKET_TZ)
        dt = pd.to_datetime(raw, utc=True, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.to_pydatetime().astimezone(MARKET_TZ)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def format_source(raw: object, link: str) -> str:
    source = str(raw).strip() if raw is not None and not pd.isna(raw) else ""
    if source.lower() in {"none", "nan", "null"}:
        source = ""
    if not source and link:
        source = urlsplit(link).hostname or ""
    return source.removeprefix("www.") or "Unknown source"


def normalize_articles(records: list[dict]) -> list[dict]:
    articles = []
    seen = set()
    for record in records:
        title = str(record.get("title") or "").strip()
        if not title or title.lower() == "nan":
            continue
        dedup_key = title.casefold()
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        link = safe_link(record.get("link"))
        articles.append({
            "title": title,
            "date": news_datetime(record.get("date")),
            "link": link,
            "source": format_source(record.get("source"), link),
        })
    articles.sort(key=lambda x: x["date"] or datetime.min.replace(tzinfo=MARKET_TZ), reverse=True)
    return articles[:MAX_HEADLINES]


def from_existing_dataframe(df: pd.DataFrame) -> list[dict]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    lookup = {str(col).strip().lower(): col for col in df.columns}

    def column(row: pd.Series, *aliases: str):
        for alias in aliases:
            if alias in lookup:
                return row.get(lookup[alias])
        return None

    out = []
    for _, row in df.iterrows():
        out.append({
            "title": column(row, "title", "headline", "name"),
            "date": column(row, "date", "published", "publisheddate", "providerpublishtime"),
            "link": column(row, "link", "url", "article_url"),
            "source": column(row, "source", "publisher", "provider"),
        })
    return normalize_articles(out)


def from_yfinance_feed(symbol: str) -> list[dict]:
    """Fallback for projects without news_sentiment.py (handles both API shapes)."""
    stock = yf.Ticker(symbol)
    feed = stock.news or []
    out = []
    for item in feed:
        if not isinstance(item, dict):
            continue
        content = item.get("content") or {}
        if not isinstance(content, dict):
            content = {}
        provider = content.get("provider") or {}
        if not isinstance(provider, dict):
            provider = {}
        url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        if not isinstance(url_obj, dict):
            url_obj = {}
        out.append({
            "title": content.get("title") or item.get("title"),
            "date": content.get("pubDate") or item.get("providerPublishTime"),
            "link": url_obj.get("url") or item.get("link"),
            "source": provider.get("displayName") or item.get("publisher"),
        })
    return normalize_articles(out)


@st.cache_data(ttl=1200, show_spinner=False)
def fetch_news(symbol: str) -> list[dict]:
    if existing_fetch_stock_news is not None:
        try:
            records = from_existing_dataframe(existing_fetch_stock_news(symbol))
            if records:
                return records
        except Exception:
            pass  # Fall back to Yahoo's direct feed.
    try:
        return from_yfinance_feed(symbol)
    except Exception:
        return []  # Show an explicit no-data message instead of invented headlines.


@st.cache_data(ttl=420, show_spinner=False)
def fetch_quotes(symbols: tuple[str, ...]) -> dict[str, dict]:
    """Batch daily-close request. Prices are NOT represented as real-time quotes."""
    if not symbols:
        return {}
    quotes: dict[str, dict] = {s: {"price": None, "change_pct": None, "change_abs": None, "cap": None} for s in symbols}
    try:
        frame = yf.download(
            tickers=" ".join(symbols),
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False,
        )
        for symbol in symbols:
            if frame.empty:
                continue
            if isinstance(frame.columns, pd.MultiIndex):
                # group_by='ticker' => first level is symbol in supported yfinance versions.
                if symbol in frame.columns.get_level_values(0):
                    series = frame[symbol]["Close"]
                elif symbol in frame.columns.get_level_values(1):
                    series = frame.xs(symbol, level=1, axis=1)["Close"]
                else:
                    continue
            else:
                series = frame["Close"] if len(symbols) == 1 else pd.Series(dtype=float)
            closes = pd.to_numeric(series, errors="coerce").dropna()
            closes = closes[closes > 0]
            if closes.empty:
                continue
            latest = float(closes.iloc[-1])
            prior = float(closes.iloc[-2]) if len(closes) >= 2 else None
            quotes[symbol]["price"] = latest
            if prior is not None and prior > 0:
                quotes[symbol]["change_abs"] = latest - prior
                quotes[symbol]["change_pct"] = 100 * (latest / prior - 1)
    except Exception:
        pass
    return quotes


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_market_cap(symbol: str) -> float | None:
    try:
        cap = yf.Ticker(symbol).fast_info.get("market_cap")
        if cap is not None and math.isfinite(float(cap)) and float(cap) > 0:
            return float(cap)
    except Exception:
        pass
    return None


def compact_cap(value: float | None) -> str:
    if value is None:
        return ""
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if value >= 1e6:
        return f"${value / 1e6:.1f}M"
    return f"${value:,.0f}"


def scan_sentiment(watchlist: list[str], news_by_symbol: dict[str, list[dict]]) -> dict[str, dict]:
    """Use *existing* FinBERT: no made-up sentiment and no new AI vendor."""
    outcome: dict[str, dict] = {}
    if analyze_finbert is None:
        return {symbol: {"status": "unavailable", "reason": "FinBERT module not found"} for symbol in watchlist}

    progress = st.progress(0, text="Preparing headline scan...")
    for index, symbol in enumerate(watchlist, start=1):
        progress.progress((index - 1) / len(watchlist), text=f"Agent reading the news · {symbol} ({index}/{len(watchlist)})")
        titles = [item["title"] for item in news_by_symbol.get(symbol, [])]
        if not titles:
            outcome[symbol] = {"status": "empty"}
        else:
            try:
                scores = analyze_finbert(tuple(titles))
                if len(scores) != len(titles):
                    raise ValueError("Unexpected number of FinBERT predictions")
                labels = scores["FinBERT Sentiment"].astype(str).str.strip().str.lower()
                counts = {label: int((labels == label).sum()) for label in ("positive", "neutral", "negative")}
                if counts["positive"] > counts["negative"]:
                    status = "positive"
                elif counts["negative"] > counts["positive"]:
                    status = "negative"
                else:
                    status = "mixed"
                outcome[symbol] = {"status": status, "counts": counts}
            except Exception:
                outcome[symbol] = {"status": "unavailable", "reason": "FinBERT failed for this ticker"}
    progress.progress(1.0, text=f"Completed sentiment scan for {len(watchlist)} ticker(s)")
    progress.empty()
    return outcome


def make_status(scan: dict | None) -> tuple[str, str]:
    if scan is None:
        return "", "waiting for the agent"
    status = scan.get("status", "unavailable")
    counts = scan.get("counts", {})
    if status == "positive":
        return "ns-positive", f"positive · {counts.get('positive', 0)} positive / {counts.get('negative', 0)} negative"
    if status == "negative":
        return "ns-negative", f"negative · {counts.get('negative', 0)} negative / {counts.get('positive', 0)} positive"
    if status == "mixed":
        return "ns-mixed", f"mixed · {counts.get('positive', 0)} positive / {counts.get('negative', 0)} negative"
    if status == "empty":
        return "", "no headlines to scan"
    return "", "sentiment unavailable"


def make_card(symbol: str, quote: dict, items: list[dict], scan: dict | None, first: bool = False) -> str:
    name = html.escape(COMPANY_NAMES.get(symbol, symbol))
    safe_symbol = html.escape(symbol)
    featured = " ns-featured" if first else ""
    price = quote.get("price")
    value = f"${price:,.2f}" if price is not None else "—"
    change = quote.get("change_pct")
    change_abs = quote.get("change_abs")
    if change is None:
        delta_html = '<div class="ns-change ns-neutral">price unavailable</div>'
        dollar_html = ""
    else:
        color = "ns-pos" if change >= 0 else "ns-neg"
        delta_html = f'<div class="ns-change {color}">{change:+.2f}%</div>'
        dollar_html = f'<div class="ns-dollar">{change_abs:+.2f} USD</div>'
    cap = compact_cap(quote.get("cap"))
    cap_line = f'<div class="ns-dollar">Market cap {cap}</div>' if cap else ""
    status_cls, status_label = make_status(scan)
    article_rows: list[str] = []
    for item in items:
        published = item["date"].strftime("%d %b") if item.get("date") else "—"
        headline = html.escape(item["title"])
        source = html.escape(item["source"])
        link = safe_link(item.get("link"))
        inside = (
            f'<span class="ns-date">{html.escape(published)}</span>'
            f'<span><span class="ns-headline">{headline}</span>'
            f'<div class="ns-source">{source}</div></span>'
        )
        if link:
            article_rows.append(
                f'<a class="ns-article" href="{html.escape(link, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">{inside}</a>'
            )
        else:
            article_rows.append(f'<div class="ns-article">{inside}</div>')
    if not article_rows:
        article_rows.append('<div class="ns-none">No recent headlines returned by the news source for this ticker.</div>')
    articles_html = "".join(article_rows)
    return (
        f'<section class="ns-card{featured}">'
        '<div class="ns-cardtop">'
        f'<div><div class="ns-symbol">{safe_symbol}</div><div class="ns-company">{name}</div></div>'
        f'<div class="ns-quote"><div class="ns-price">{value}</div>{delta_html}{dollar_html}{cap_line}</div>'
        '</div>'
        f'<div class="ns-status {status_cls}"><span class="ns-dot"></span>{html.escape(status_label)}</div>'
        f'<div class="ns-articles">{articles_html}</div>'
        '</section>'
    )


# --- Persistent watchlist (browser-local; per user and per website) ---------
def valid_saved_watchlist(raw: object) -> list[str] | None:
    """A missing value means defaults; an empty saved list is a valid choice."""
    if raw is None:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(parsed, list):
        return None
    cleaned = []
    for value in parsed:
        if isinstance(value, str):
            ticker = clean_ticker(value)
            if ticker and ticker not in cleaned:
                cleaned.append(ticker)
        if len(cleaned) >= MAX_TICKERS:
            break
    return cleaned


def browser_watchlist_read() -> dict | None:
    """Returns None only while the JS component is awaiting its first result."""
    # Wrap absent values in a JSON envelope, so missing storage is distinct
    # from the component's initial (not-ready) Python None result.
    key_js = json.dumps(BROWSER_WATCHLIST_KEY)
    expression = (
        "(function(){try{return JSON.stringify({ok:true,stored:"
        f"window.localStorage.getItem({key_js})"
        "});}catch(e){return JSON.stringify({ok:false});}})()"
    )
    result = streamlit_js_eval(
        js_expressions=expression,
        want_output=True,
        key="ns_restore_saved_watchlist",
    )
    if result is None:
        return None
    try:
        value = json.loads(result) if isinstance(result, str) else result
    except (json.JSONDecodeError, TypeError, ValueError):
        value = {"ok": False}
    return value if isinstance(value, dict) else {"ok": False}


def save_watchlist_on_next_render() -> None:
    """Mount a JS write component after a ticker edit and acknowledge success."""
    pending = st.session_state.get("ns_pending_watchlist_save")
    if not pending:
        return
    serialized = json.dumps(st.session_state["ns_watchlist"], separators=(",", ":"))
    key_js = json.dumps(BROWSER_WATCHLIST_KEY)
    value_js = json.dumps(serialized)
    expression = (
        f"(function(){{try{{window.localStorage.setItem({key_js},"
        f"{value_js});return 'saved';}}catch(e){{return 'error';}}}})()"
    )
    result = streamlit_js_eval(
        js_expressions=expression,
        want_output=True,
        key=f"ns_write_watchlist_{pending}",
    )
    if result == "saved":
        st.session_state.pop("ns_pending_watchlist_save", None)
    elif result == "error":
        st.session_state.pop("ns_pending_watchlist_save", None)
        st.warning("Browser storage is blocked, so this watchlist may not survive closing your tab.")


def mark_watchlist_dirty() -> None:
    st.session_state["ns_save_revision"] = st.session_state.get("ns_save_revision", 0) + 1
    st.session_state["ns_pending_watchlist_save"] = st.session_state["ns_save_revision"]


# --- Page -------------------------------------------------------------------
# Initialize from localStorage *before* creating buttons or loading news.
# Do not overwrite a saved watchlist with defaults while JS is still loading.
if "ns_watchlist_loaded_from_browser" not in st.session_state:
    restored = browser_watchlist_read()
    if restored is None:
        st.caption("Restoring your saved News Screen watchlist…")
        st.stop()
    if not restored.get("ok"):
        st.error("This browser is blocking local storage. Enable site storage to save your watchlist.")
        st.stop()
    existing = valid_saved_watchlist(restored.get("stored"))
    # One-time migration of a watchlist from the previous session-only page.
    # If a browser-saved list exists, it always takes precedence.
    prior_session_list = st.session_state.get("ns_watchlist")
    if existing is not None:
        st.session_state["ns_watchlist"] = existing
    elif isinstance(prior_session_list, list):
        st.session_state["ns_watchlist"] = (
            valid_saved_watchlist(prior_session_list) or []
        )
        mark_watchlist_dirty()
    else:
        st.session_state["ns_watchlist"] = DEFAULT_WATCHLIST.copy()
    st.session_state["ns_watchlist_loaded_from_browser"] = True

st.session_state.setdefault("ns_scans", {})
save_watchlist_on_next_render()
watchlist = st.session_state["ns_watchlist"]

head_left, head_right = st.columns([4, 1.1], vertical_alignment="center")
with head_left:
    st.markdown(
        f'<div class="ns-masthead"><div class="ns-icon">≡</div>'
        '<div><div class="ns-title">NEWS SCREEN</div>'
        f'<div class="ns-subtitle">AI news agent · {len(watchlist)} stocks on the watchlist</div>'
        '</div></div>', unsafe_allow_html=True,
    )
with head_right:
    scan_clicked = st.button("Scan headlines", type="primary", use_container_width=True, key="ns_scan_button")

st.markdown('<div class="ns-toprule"></div>', unsafe_allow_html=True)

# Ticker chips are Streamlit buttons rather than custom JS: safe and interactive.
chip_sizes = [1.1] + [0.91] * len(watchlist) + [1.65]
chip_cols = st.columns(chip_sizes, gap="small", vertical_alignment="center")
with chip_cols[0]:
    st.markdown('<div class="ns-section-label">WATCHLIST</div>', unsafe_allow_html=True)
for i, symbol in enumerate(watchlist):
    with chip_cols[i + 1]:
        if st.button(f"{symbol} ×", key=f"ns_remove_{symbol}", use_container_width=True, help=f"Remove {symbol} from watchlist"):
            st.session_state["ns_watchlist"] = [s for s in watchlist if s != symbol]
            st.session_state["ns_scans"].pop(symbol, None)
            mark_watchlist_dirty()
            st.rerun()
with chip_cols[-1]:
    with st.popover("+ add ticker", use_container_width=True):
        with st.form("ns_add_form", clear_on_submit=True):
            raw_symbol = st.text_input("Ticker symbol", max_chars=15, placeholder="e.g. MU", label_visibility="visible")
            added = st.form_submit_button("Add stock", type="primary", use_container_width=True)
        if added:
            new_symbol = clean_ticker(raw_symbol)
            if not new_symbol:
                st.error("Enter a valid ticker symbol (letters, digits, '.', '-', '^', '=').")
            elif new_symbol in watchlist:
                st.info(f"{new_symbol} is already on your watchlist.")
            elif len(watchlist) >= MAX_TICKERS:
                st.warning(f"The watchlist supports up to {MAX_TICKERS} tickers.")
            else:
                st.session_state["ns_watchlist"].append(new_symbol)
                mark_watchlist_dirty()
                st.rerun()

control_left, control_right = st.columns([3.8, 1.2], vertical_alignment="center")
with control_left:
    st.markdown(
        '<div class="ns-agent-label" style="text-align:left">'
        'Yahoo Finance news · prices are latest available daily closes · click a headline to read'
        '</div>', unsafe_allow_html=True,
    )
with control_right:
    if st.button("↻ Refresh news & prices", key="ns_refresh", use_container_width=True):
        fetch_news.clear()
        fetch_quotes.clear()
        fetch_market_cap.clear()
        if existing_fetch_stock_news is not None and callable(getattr(existing_fetch_stock_news, "clear", None)):
            existing_fetch_stock_news.clear()
        st.session_state["ns_scans"].clear()
        st.rerun()

if not watchlist:
    st.info("Your watchlist is empty. Use '+ add ticker' to get started.")
    st.stop()

with st.spinner("Loading prices and latest headlines..."):
    quotes = fetch_quotes(tuple(watchlist))
    news_by_symbol = {symbol: fetch_news(symbol) for symbol in watchlist}
    # Cap is optional, so Yahoo's throttling doesn't hide prices or news.
    for symbol in watchlist:
        if quotes.get(symbol, {}).get("price") is not None:
            quotes[symbol]["cap"] = fetch_market_cap(symbol)

if scan_clicked:
    st.session_state["ns_scans"].update(scan_sentiment(watchlist, news_by_symbol))
    st.session_state["ns_scanned_at"] = datetime.now(MARKET_TZ).strftime("%d %b %Y, %I:%M %p ET")

cards = [
    make_card(
        symbol,
        quotes.get(symbol, {}),
        news_by_symbol.get(symbol, []),
        st.session_state["ns_scans"].get(symbol),
        first=(i == 0),
    )
    for i, symbol in enumerate(watchlist)
]
st.markdown('<div class="ns-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)

last_scan = st.session_state.get("ns_scanned_at")
scan_note = (
    f"Last FinBERT scan: {html.escape(last_scan)}. "
    if last_scan else "Select 'Scan headlines' for FinBERT sentiment per ticker. "
)
st.markdown(
    '<div class="ns-footer">'
    f'{scan_note}Headline sentiment is an estimate, not a trading recommendation. '
    'News and price availability depend on Yahoo Finance. '
    'Your watchlist is saved in this browser and restored when you reopen the page.'
    '</div>', unsafe_allow_html=True,
)
