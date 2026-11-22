"""News Screen — drop this file into your Streamlit project's pages/ folder.

Reuses the existing project's news_sentiment.fetch_stock_news and
finbert_sentiment.analyze_finbert when available. No new API keys required.
"""

from __future__ import annotations

import html
import os
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from dotenv import load_dotenv
import streamlit as st
import yfinance as yf

# Multipage scripts live inside pages/, but project helper modules live next to app.py.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard_theme import apply_dashboard_theme, render_page_header
from etf_holdings import ETFHoldings, fetch_etf_holdings
from etf_scan_results import load_etf_scores, etf_score_map
from custom_watchlists import (
    DRAFT_KEY, render_custom_list, render_working_list,
    named_groups, active_named_group, activate_named_group,
    save_named_group, remove_named_group, removable_stock_list,
)
from scanner_email_watchlist import (
    AlertSnapshot,
    load_email_alerts,
    saved_regression_zscores,
    sigma_label,
)
load_dotenv(PROJECT_ROOT / ".env")

try:
    from news_sentiment import fetch_stock_news as existing_fetch_stock_news
except ImportError:
    existing_fetch_stock_news = None

try:
    from finbert_sentiment import analyze_finbert
except ImportError:
    analyze_finbert = None


MARKET_TZ = ZoneInfo("America/New_York")
COMPANY_NAMES = {
    "NVDA": "NVIDIA Corporation",
    "AAPL": "Apple Inc.",
    "GOOG": "Alphabet Inc.",
    "GOOGL": "Alphabet Inc.",
    "MSFT": "Microsoft Corporation",
    "AMZN": "Amazon.com, Inc.",
    "TSM": "Taiwan Semiconductor Manufacturing",
    "META": "Meta Platforms, Inc.",
    "AVGO": "Broadcom Inc.",
    "TSLA": "Tesla Inc.",
    "BRK-B": "Berkshire Hathaway Inc. (Class B)",
    "TXN": "Texas Instruments Inc.",
    "AMD": "Advanced Micro Devices Inc.",
    "ADI": "Analog Devices Inc.",
    "ASML": "ASML Holding N.V.",
    "QCOM": "QUALCOMM Inc.",
    "KLAC": "KLA Corporation",
    "MU": "Micron Technology Inc.",
    "SPCX": "Space Exploration Technologies Corp.",
}
MAX_HEADLINES = 6
LOOKBACK_DAYS = 7
TICKER_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.\-^=]{0,14}$")
# Only headlines that explicitly mention one of these company names may appear.
# Corporate affiliates/products are intentionally NOT a substitute for the name.
HEADLINE_ALIASES = {
    "NVDA": ("NVIDIA",),
    "AAPL": ("Apple",),
    "GOOG": ("Google", "Alphabet"),
    "GOOGL": ("Google", "Alphabet"),
    "MSFT": ("Microsoft",),
    "AMZN": ("Amazon",),
    "TSM": ("TSMC", "Taiwan Semiconductor"),
    "META": ("Meta", "Facebook"),
    "SPCX": ("SpaceX", "Space Exploration Technologies"),
    "MU": ("Micron", "Micron Technology"),
    "INTC": ("Intel",),
    "AMD": ("AMD", "Advanced Micro Devices"),
    "TSLA": ("Tesla",),
    "PLTR": ("Palantir",),
    "AVGO": ("Broadcom",),
    "ARM": ("Arm Holdings", "Arm"),
    "ASML": ("ASML",),
    "BABA": ("Alibaba",),
    "BRK-B": ("Berkshire Hathaway",),
    "TXN": ("Texas Instruments",),
    "ADI": ("Analog Devices",),
    "QCOM": ("Qualcomm",),
    "KLAC": ("KLA", "KLA Corporation"),
}


# --- Shared theme + News Screen-specific responsive five-column cards -----------------
apply_dashboard_theme()
st.markdown(r"""
<style>
[data-testid="stAppViewBlockContainer"] {
  max-width:1840px !important;
  padding:1.25rem 1.3rem 2.8rem !important;
}
.ns-masthead {display:flex;align-items:center;gap:14px;min-height:57px;}
.ns-icon {display:flex;align-items:center;justify-content:center;flex:none;background:#1585C8;
  color:#F4FBFF;width:37px;height:37px;border-radius:9px;font-size:22px;font-weight:900;
  box-shadow:0 0 24px rgba(18,138,224,.15);}
.ns-title {font-size:var(--si-type-section);letter-spacing:.2em;font-weight:900;color:#CCEDFF;line-height:1.12;}
.ns-subtitle {color:#8AA9C2;font-size:var(--si-type-caption);margin-top:6px;}
.ns-toprule {height:1px;background:linear-gradient(90deg,#18324A,#218CCE,#18324A);margin:12px 0 16px;}
.ns-section-label {color:#91A9BF;font-size:var(--si-type-label);letter-spacing:.14em;font-weight:800;padding-top:9px;}
.ns-agent-label {color:#88A5BC;font-size:var(--si-type-caption);padding-top:11px;text-align:right;}
.ns-agent-label b {color:#78CDFF;font-weight:700;}
.ns-grid {display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:13px;margin:16px 0 9px;align-items:stretch;}
.ns-card {
  background:linear-gradient(150deg,rgba(8,20,34,.59) 0%,rgba(7,15,27,.46) 100%);
  backdrop-filter:blur(8px);
  -webkit-backdrop-filter:blur(8px);
  border:1px solid #19344D;border-radius:13px;padding:17px 15px 11px;
  display:flex;flex-direction:column;min-width:0;min-height:420px;
  box-shadow:0 12px 32px rgba(0,0,0,.12);}
.ns-card.ns-featured {border-color:#287FB8;box-shadow:0 0 0 1px rgba(35,154,224,.1) inset,0 12px 32px rgba(0,0,0,.12);}
.ns-cardtop {display:flex;justify-content:space-between;align-items:flex-start;gap:7px;}
.ns-symbol {color:#4DC5FF;font-size:var(--si-type-ticker);font-weight:900;letter-spacing:-.025em;line-height:1.13;}
.ns-sigma {font-size:var(--si-type-caption);color:#95C8EB;margin:3px 0 7px;white-space:nowrap;}
.ns-etf-weight {font-size:var(--si-type-caption);color:#75D3BA;margin:3px 0 5px;white-space:nowrap;}
.ns-auto-pills {display:flex;gap:7px;flex-wrap:wrap;align-items:center;padding:7px 0;}
.ns-auto-pill {border:1px solid #244461;background:rgba(16,31,48,.57);border-radius:7px;padding:7px 10px;color:#9FD3F6;font-size:var(--si-type-caption);}
.st-key-ns_editable_stock_pills [data-testid="stButton"] button {
  background:rgba(16,31,48,.57) !important;
  color:#9FD3F6 !important;
  border:1px solid #244461 !important;
  border-radius:7px !important;
  min-height:34px !important;
  padding:4px 8px !important;
  font-size:var(--si-type-caption) !important;
  white-space:nowrap !important;
}
.st-key-ns_editable_stock_pills [data-testid="stButton"] button:hover {
  background:rgba(29,64,97,.90) !important;
  border-color:#4485B2 !important;
  color:#E5F5FF !important;
}
.st-key-ns_editable_stock_pills [data-testid="stHorizontalBlock"] {gap:6px !important;}
.ns-company {font-size:var(--si-type-data);color:#8FA9BF;margin-top:5px;line-height:1.3;min-height:28px;overflow:hidden;}
.ns-quote {text-align:right;font-variant-numeric:tabular-nums;min-width:92px;}
.ns-price {color:#E1F2FC;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:1.05rem;font-weight:750;}
.ns-change {font-size:var(--si-type-caption);margin-top:3px;font-weight:800;}
.ns-dollar {color:#7593AC;font-size:var(--si-type-caption);margin-top:3px;}
.ns-pos {color:#4AD9AA !important;} .ns-neg {color:#FB798F !important;}
.ns-neutral {color:#8FA9BF !important;}
.ns-status {display:inline-flex;align-items:center;gap:7px;width:fit-content;max-width:100%;
  margin:6px 0 9px;padding:6px 10px;border-radius:30px;background:rgba(20,37,54,.56);
  font-size:var(--si-type-caption);color:#96B0C5;font-weight:650;}
.ns-status.ns-ready {background:rgba(16,46,73,.69);color:#71CEFF;}
.ns-status.ns-positive {background:rgba(18,53,39,.69);color:#67DBB3;}
.ns-status.ns-negative {background:rgba(56,27,42,.69);color:#FF9AB0;}
.ns-status.ns-mixed {background:rgba(26,48,65,.69);color:#B4D4ED;}
.ns-dot {width:7px;height:7px;border-radius:50%;background:currentColor;display:inline-block;flex:none;}
.ns-article {display:grid;grid-template-columns:45px minmax(0,1fr);gap:8px;
  border-top:1px solid #1B3246;padding:10px 0 10px;text-decoration:none !important;
  min-height:53px;color:#D5E6F2 !important;}
.ns-article:hover .ns-headline {color:#64CEFF;}
.ns-date {font-size:var(--si-type-caption);color:#91ADC2;padding-top:2px;font-weight:600;white-space:nowrap;}
.ns-headline {font-size:var(--si-type-data);color:#DEEAF4;line-height:1.37;display:-webkit-box;
  -webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;overflow-wrap:anywhere;}
.ns-source {color:#6E98B6;font-size:var(--si-type-caption);margin-top:4px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;}
.ns-none {color:#95B4CB;font-size:var(--si-type-data);line-height:1.55;padding:16px 0;
  border-top:1px solid #1D3447;}
.ns-footer {color:#8BA8C0;font-size:var(--si-type-caption);line-height:1.65;margin:12px 0 18px;}
@media(max-width:1350px){.ns-grid{grid-template-columns:repeat(3,minmax(0,1fr));}}
@media(max-width:850px){.ns-grid{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media(max-width:650px){
  .ns-grid{grid-template-columns:1fr;}.ns-card{min-height:0;}
  .ns-title{font-size:var(--si-type-subsection);letter-spacing:.06em;}
  [data-testid="stAppViewBlockContainer"]{padding-left:.75rem !important;padding-right:.75rem !important;}
}

.ns-card {min-height:425px;}

</style>
""", unsafe_allow_html=True)


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
    return articles[:200]


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


def from_yahoo_items(feed: list) -> list[dict]:
    """Both Yahoo Search and ticker news can return old and new response shapes."""
    out = []
    for item in feed or []:
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
            "date": content.get("pubDate") or item.get("providerPublishTime") or item.get("date"),
            "link": url_obj.get("url") or item.get("link") or item.get("url"),
            "source": provider.get("displayName") or item.get("publisher") or item.get("source"),
        })
    return normalize_articles(out)


@st.cache_data(ttl=86400, show_spinner=False)
def company_aliases(symbol: str) -> tuple[str, ...]:
    """Resolve names for newly added tickers; default watchlist uses curated names."""
    if symbol in HEADLINE_ALIASES:
        return HEADLINE_ALIASES[symbol]
    aliases = []
    try:
        info = yf.Ticker(symbol).info or {}
        for field in ("shortName", "longName", "displayName"):
            name = str(info.get(field) or "").strip()
            if not name:
                continue
            name = re.sub(r"(?i)\s+(?:incorporated|inc\.?|corp\.?|corporation|ltd\.?|limited|plc|co\.?|holdings?)$", "", name).strip(" ,.-")
            # A one-word generic value like 'Technology' produces weak matches.
            if len(name) >= 4 and name.lower() not in {"technology", "industries", "holdings", "group"}:
                aliases.append(name)
    except Exception:
        pass
    # A standalone distinctive first brand word (e.g., 'Micron') may appear
    # where the full corporate name does not. Skip generic corporate adjectives.
    generic = {"global", "international", "general", "american", "united",
               "first", "new", "advanced", "applied", "digital", "technology",
               "financial", "capital", "systems", "national", "group", "the"}
    for name in list(aliases):
        first = name.split()[0].strip(".,-'\"")
        if len(first) >= 5 and first.lower() not in generic:
            aliases.append(first)
    return tuple(dict.fromkeys(aliases))


def company_in_headline(title: str, symbol: str, aliases: tuple[str, ...]) -> bool:
    """STRICT: no broad sector headlines merely associated with the ticker feed."""
    for name in aliases:
        if re.search(r"(?<![\w])" + re.escape(name) + r"(?![\w])", title, re.IGNORECASE):
            return True
    # An explicit exchange-style ticker identifier in the actual headline also qualifies.
    escaped = re.escape(symbol)
    if re.search(r"\$" + escaped + r"(?![\w])", title, re.IGNORECASE):
        return True
    if re.search(r"\(" + escaped + r"\)", title):
        return True
    # If Yahoo can't resolve a company's name, accept an all-caps stock ticker
    # only when accompanied by a stock-market context word in the title.
    if not aliases and len(symbol) >= 3 and re.search(r"(?<![A-Za-z0-9])" + escaped + r"(?![A-Za-z0-9])", title):
        return bool(re.search(r"\b(stock|stocks|shares|earnings|investors|IPO)\b", title, re.IGNORECASE))
    return False


def filter_company_week(articles: list[dict], symbol: str, aliases: tuple[str, ...]) -> list[dict]:
    now = datetime.now(MARKET_TZ)
    earliest = now - timedelta(days=LOOKBACK_DAYS)
    kept = []
    for item in articles:
        date = item.get("date")
        if date is None or not (earliest <= date <= now + timedelta(minutes=10)):
            continue  # No date = cannot claim it was published in the past 7 days.
        if not company_in_headline(item.get("title", ""), symbol, aliases):
            continue
        kept.append(item)
    # Re-normalize to deduplicate across ticker feed, company Search and GNews.
    return normalize_articles(kept)


@st.cache_data(ttl=1800, show_spinner=False)
def yahoo_ticker_feed(symbol: str) -> list[dict]:
    try:
        ticker = yf.Ticker(symbol)
        # 80 instead of default 10: find named-company titles further back in the feed.
        if hasattr(ticker, "get_news"):
            return from_yahoo_items(ticker.get_news(count=80, tab="news"))
        return from_yahoo_items(ticker.news or [])
    except Exception:
        return []


@st.cache_data(ttl=1800, show_spinner=False)
def yahoo_company_search(query: str) -> list[dict]:
    try:
        # Dedicated company-name search; still independently filter headline + date.
        result = yf.Search(query, news_count=50, max_results=0, raise_errors=False)
        return from_yahoo_items(result.news or [])
    except Exception:
        return []


def gnews_key() -> str:
    # Never hard-code or print keys. Support deployed Streamlit secrets and local .env.
    try:
        secret = st.secrets.get("GNEWS_API_KEY", "")
        if secret:
            return str(secret).strip()
    except Exception:
        pass
    return os.getenv("GNEWS_API_KEY", "").strip()


@st.cache_data(ttl=21600, show_spinner=False)
def gnews_company_search(query: str, api_key: str) -> list[dict]:
    if not api_key:
        return []
    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    try:
        response = requests.get(
            "https://gnews.io/api/v4/search",
            params={
                "q": f'"{query}"',
                "in": "title", "lang": "en", "max": 10,
                "from": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "sortby": "publishedAt", "apikey": api_key,
            },
            timeout=12,
        )
        response.raise_for_status()
        entries = response.json().get("articles", [])
    except (requests.RequestException, ValueError):
        # The free GNews tier has limits and may delay articles; Yahoo still works.
        return []
    out = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        source = item.get("source") or {}
        source_name = source.get("name") if isinstance(source, dict) else source
        out.append({"title": item.get("title"), "date": item.get("publishedAt"),
                    "link": item.get("url"), "source": source_name})
    return normalize_articles(out)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_news(symbol: str) -> list[dict]:
    aliases = company_aliases(symbol)
    # 1. Existing Yahoo feed — avoid changing your main dashboard's news logic.
    records = []
    if existing_fetch_stock_news is not None:
        try:
            records.extend(from_existing_dataframe(existing_fetch_stock_news(symbol)))
        except Exception:
            pass
    records.extend(yahoo_ticker_feed(symbol))
    clean = filter_company_week(records, symbol, aliases)

    # 2. Search by actual company name to fill in the last 7 days.
    if len(clean) < MAX_HEADLINES:
        query = aliases[0] if aliases else symbol
        records.extend(yahoo_company_search(query))
        clean = filter_company_week(records, symbol, aliases)

    # 3. Optional GNews fallback if the user's EXISTING key is set.
    # Search is cached 6h to avoid exhausting free-tier daily requests.
    key = gnews_key()
    if key and len(clean) < MAX_HEADLINES:
        query = aliases[0] if aliases else symbol
        records.extend(gnews_company_search(query, key))
        clean = filter_company_week(records, symbol, aliases)
    return clean[:MAX_HEADLINES]


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



def automatic_stock_scan(symbol, records):
    from news_ai_shared import score_titles
    titles=tuple(str(item['title']) for item in records)
    if not titles:
        return {'status':'empty'}
    try:
        scores=score_titles(titles)
        counts={label:sum(1 for item in scores if item[0].lower()==label)
                for label in ('positive','neutral','negative')}
        status=('positive' if counts['positive']>counts['negative']
                else 'negative' if counts['negative']>counts['positive'] else 'mixed')
        return {'status':status,'counts':counts}
    except Exception:
        return {'status':'unavailable'}


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


def make_card(symbol: str, quote: dict, items: list[dict], scan: dict | None, first: bool = False, sigma_text: str = "", holding_weight: float | None = None) -> str:
    name = html.escape(COMPANY_NAMES.get(symbol, symbol))
    safe_symbol = html.escape("BRK.B" if symbol == "BRK-B" else symbol)
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
        article_rows.append('<div class="ns-none">No headlines naming this company were found in the past 7 days.</div>')
    articles_html = "".join(article_rows)
    sigma_html = f'<div class="ns-sigma">{html.escape(sigma_text)}</div>' if sigma_text else ""
    weight_html = (f'<div class="ns-etf-weight">ETF weight {holding_weight:.2f}%</div>'
                   if holding_weight is not None else "")
    return (
        f'<section class="ns-card{featured}">'
        '<div class="ns-cardtop">'
        f'<div><div class="ns-symbol">{safe_symbol}</div><div class="ns-company">{name}</div>{weight_html}{sigma_html}</div>'
        f'<div class="ns-quote"><div class="ns-price">{value}</div>{delta_html}{dollar_html}{cap_line}</div>'
        '</div>'
        f'<div class="ns-status {status_cls}"><span class="ns-dot"></span>{html.escape(status_label)}</div>'
        f'<div class="ns-articles">{articles_html}</div>'
        '</section>'
    )



# --- Built-in news sources plus persistent named stock groups ------------------
# The existing browser storage key is unchanged. Read-only scan/ETF sources
# remain available and can be saved as editable groups.
TODAYS_SCAN_LABEL = "Today's Regression Scan's Stocks"
SP500_LABEL = "S&P 500 Top 10 Holdings"
CUSTOM_ETF_LABEL = "Other ETF — Top 10 Holdings"
CUSTOM_STOCK_LABEL = "Saved Groups"
WORKING_STOCK_LABEL = "Custom List (Unsaved)"
BUILTIN_GROUP_OPTIONS = [
    TODAYS_SCAN_LABEL, SP500_LABEL, CUSTOM_ETF_LABEL, WORKING_STOCK_LABEL,
]
SAVED_GROUP_PREFIX = "Saved · "

ETF_STARTERS = {
    "SPY": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "AVGO", "GOOG", "META", "TSLA", "BRK-B"],
}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def cached_etf_holdings(ticker: str) -> ETFHoldings:
    """Provider holdings update periodically; avoid refetching on every rerun."""
    return fetch_etf_holdings(ticker, limit=10)


def _group_option(name: str) -> str:
    return SAVED_GROUP_PREFIX + name


def _saved_group_name(option: str) -> str | None:
    if isinstance(option, str) and option.startswith(SAVED_GROUP_PREFIX):
        return option[len(SAVED_GROUP_PREFIX):]
    return None


render_page_header(
    'News Screener',
    'AI news agent · scan signals, ETF holdings, or saved groups',
    current='general',
)

# Read existing saved groups before creating the dropdown. The localStorage
# bridge uses the same mechanism already used by Portfolio X-Ray.
group_names = named_groups()
group_options = BUILTIN_GROUP_OPTIONS + [_group_option(name) for name in group_names]
last_selected = st.session_state.get('ns_group_select')
if last_selected in ('Custom List', CUSTOM_STOCK_LABEL):
    last_selected = _group_option(active_named_group())
elif last_selected == 'Working List (Unsaved)':
    last_selected = WORKING_STOCK_LABEL
if st.session_state.get('ns_group_loaded') == 'Working List (Unsaved)':
    st.session_state['ns_group_loaded'] = WORKING_STOCK_LABEL
if last_selected not in group_options:
    last_selected = TODAYS_SCAN_LABEL
st.session_state['ns_group_select'] = last_selected

if st.session_state.get('ns_group_loaded') not in group_options:
    st.session_state['ns_group_loaded'] = last_selected


def _load_selected_news_group():
    """A pre-render callback loads the chosen source and updates the news."""
    option = st.session_state.get('ns_group_select')
    if option not in group_options:
        return
    name = _saved_group_name(option)
    if name is not None and not activate_named_group(name):
        st.session_state['ns_group_feedback'] = ('error', 'That saved group no longer exists.')
        return
    st.session_state['ns_group_loaded'] = option


def _save_displayed_news_group():
    """Save the currently displayed ticker list, including presets, by name."""
    name = str(st.session_state.get('ns_new_group_name', '') or '').strip()
    # The list is updated on every normal News Screener render.
    displayed = list(st.session_state.get('ns_watchlist', []))
    success, message = save_named_group(name, displayed)
    st.session_state['ns_group_feedback'] = ('success' if success else 'error', message)
    if success:
        option = _group_option(name)
        # Callbacks run before these widgets are rendered, avoiding the
        # StreamlitWidgetAlreadyInstantiatedError seen in Portfolio X-Ray.
        st.session_state['ns_group_select'] = option
        st.session_state['ns_group_loaded'] = option


def _delete_selected_news_group():
    """Delete only named saved groups; built-in options are protected."""
    option = st.session_state.get('ns_group_select')
    name = _saved_group_name(option)
    if name is None:
        return
    success, message = remove_named_group(name)
    st.session_state['ns_group_feedback'] = ('success' if success else 'error', message)
    if success:
        if st.session_state.get('ns_group_loaded') == option:
            st.session_state['ns_group_loaded'] = TODAYS_SCAN_LABEL
        st.session_state['ns_group_select'] = st.session_state['ns_group_loaded']


def _remove_displayed_stock(ticker: str):
    """Remove from a copy of the visible list, never the preset/saved source.

    Streamlit button callbacks execute before widget instantiation, so we can
    safely update the top dropdown and loaded source without state errors.
    """
    current = list(st.session_state.get('ns_watchlist', []))
    remaining = removable_stock_list(current, ticker)
    if len(remaining) == len(current):
        return
    st.session_state[DRAFT_KEY] = remaining
    st.session_state['ns_group_select'] = WORKING_STOCK_LABEL
    st.session_state['ns_group_loaded'] = WORKING_STOCK_LABEL


# One compact toolbar like Portfolio X-Ray; a different choice must be loaded.
selector_col, load_col, save_col, delete_col, spacer_col = st.columns(
    [3.6, 0.9, 1.8, 1.0, 2.7], gap='small', vertical_alignment='bottom'
)
with selector_col:
    st.selectbox('Stock group', group_options, key='ns_group_select')
selected_group_option = st.session_state['ns_group_select']
with load_col:
    already_loaded = selected_group_option == st.session_state['ns_group_loaded']
    st.button(
        'Load', key='ns_load_group', type='primary',
        disabled=already_loaded, use_container_width=True,
        on_click=_load_selected_news_group,
        help='Already loaded' if already_loaded else 'Load stocks and show this group’s news',
    )
with save_col:
    with st.popover('Save Group', use_container_width=True):
        st.text_input(
            'Group name', placeholder='e.g. Research stocks',
            key='ns_new_group_name',
        )
        st.caption('Saves displayed tickers. An existing name will be updated.')
        st.button(
            'Save', key='ns_save_group_button',
            use_container_width=True, on_click=_save_displayed_news_group,
        )
with delete_col:
    with st.popover(
        'Delete', disabled=_saved_group_name(selected_group_option) is None,
        use_container_width=True,
    ):
        st.caption(f"Delete '{_saved_group_name(selected_group_option)}' and its saved tickers?")
        st.button(
            'Confirm delete', key='ns_delete_group_button',
            use_container_width=True, on_click=_delete_selected_news_group,
        )

feedback = st.session_state.pop('ns_group_feedback', None)
if feedback:
    getattr(st, feedback[0])(feedback[1])

loaded_news_option = st.session_state['ns_group_loaded']
mode = CUSTOM_STOCK_LABEL if _saved_group_name(loaded_news_option) is not None else loaded_news_option

selected_etf = ''
if mode == CUSTOM_ETF_LABEL:
    if 'ns_selected_etf' not in st.session_state:
        st.session_state['ns_selected_etf'] = 'QQQ'
    with st.form('ns_etf_ticker_form'):
        requested = st.text_input('ETF ticker', value=st.session_state['ns_selected_etf'],
                                  max_chars=15, placeholder='QQQ, VOO, VGT, SOXX, SMH, etc.')
        load_etf = st.form_submit_button('Load ETF top holdings', type='primary')
    if load_etf:
        ticker = clean_ticker(requested)
        if not ticker:
            st.error('Enter a valid ETF ticker, for example QQQ, VOO, or SMH.')
        else:
            st.session_state['ns_selected_etf'] = ticker
            st.rerun()
    selected_etf = st.session_state['ns_selected_etf']
elif mode == SP500_LABEL:
    selected_etf = 'SPY'  # Tradable S&P 500 proxy; not the index itself.

email_snapshot = AlertSnapshot()
etf_data = ETFHoldings(etf=selected_etf)
if mode == TODAYS_SCAN_LABEL:
    email_snapshot = load_email_alerts()
    watchlist = list(email_snapshot.symbols)
    if email_snapshot.error:
        st.warning("Today's Regression Scan's Stocks could not load: " + email_snapshot.error)
    elif email_snapshot.latest_email_date:
        st.caption('Last successful scanner email: ' + email_snapshot.latest_email_time
                   + ' · ' + str(len(watchlist)) + ' stock(s). '
                   'This is the last emailed scan; it may be from an earlier trading day.')
    else:
        st.info('No successfully emailed regression scan has been published yet.')
elif mode == CUSTOM_STOCK_LABEL:
    watchlist = render_custom_list()
elif mode == WORKING_STOCK_LABEL:
    watchlist = render_working_list()
else:
    etf_data = cached_etf_holdings(selected_etf)
    if etf_data.tickers:
        watchlist = list(etf_data.tickers)
        st.caption(f'{selected_etf} top holdings · {len(watchlist)} tickers from Yahoo Finance. '
                   'Weights and constituents can change; provider data may be delayed.')
    elif selected_etf in ETF_STARTERS:
        watchlist = ETF_STARTERS[selected_etf].copy()
        st.warning(f'Live {selected_etf} holdings are unavailable. Showing your supplied '
                   'starter ticker list instead (not verified current holdings or weights). '
                   'Use Refresh to retry Yahoo Finance.')
    else:
        watchlist = []
        st.warning(etf_data.error or f'No holdings were found for {selected_etf}. '
                   'The data provider does not cover every ETF.')

# The initial user-provided weights were deliberately not hardcoded: they can
# become stale or differ between the index and ETF tracking it.
st.session_state['ns_watchlist'] = watchlist.copy()
st.session_state.setdefault('ns_scans', {})

st.markdown('<div class="ns-toprule"></div>', unsafe_allow_html=True)
if watchlist:
    st.markdown('<div class="ns-section-label">' +
                ('REGRESSION SCAN STOCKS' if mode == TODAYS_SCAN_LABEL
                 else ('CUSTOM STOCKS · UNSAVED' if mode == WORKING_STOCK_LABEL
                       else ('CUSTOM STOCKS' if mode == CUSTOM_STOCK_LABEL
                             else 'ETF CONSTITUENTS · ' + html.escape(selected_etf)))) +
                '</div>', unsafe_allow_html=True)
    # Every visible ticker is removable, including read-only ETF/scan presets.
    # Click × to create an unsaved Custom List copy without changing its source.
    with st.container(key="ns_editable_stock_pills"):
        for offset in range(0, len(watchlist), 10):
            symbols = watchlist[offset:offset + 10]
            widths = [max(7, len(symbol) + 3) for symbol in symbols]
            filler = max(12, 105 - sum(widths))
            columns = st.columns(widths + [filler], gap="small")
            for index, (column, symbol) in enumerate(zip(columns, symbols)):
                label = symbol.replace("BRK-B", "BRK.B")
                with column:
                    st.button(
                        f"{label} ×",
                        key=f"ns_remove_visible_{offset + index}_{symbol}",
                        help=f"Remove {label} and switch to Custom List (Unsaved)",
                        on_click=_remove_displayed_stock,
                        args=(symbol,),
                        use_container_width=True,
                    )

control_left, sigma_col, control_right = st.columns([3.15, 0.7, 1.15], vertical_alignment="center")
with sigma_col:
    show_sigma = st.checkbox('Show σ', key='ns_show_sigma',
                             help='Regression Z-score from saved scanner results, or emailed crossing band. N/A if unavailable.')
with control_left:
    st.markdown(
        '<div class="ns-agent-label" style="text-align:left">'
        'Company-name headlines only · past 7 days · Yahoo + optional GNews · prices are latest daily closes'
        '</div>', unsafe_allow_html=True,
    )
with control_right:
    if st.button("↻ Refresh news & prices", key="ns_refresh", use_container_width=True):
        cached_etf_holdings.clear()
        fetch_news.clear()
        yahoo_ticker_feed.clear()
        yahoo_company_search.clear()
        gnews_company_search.clear()
        fetch_quotes.clear()
        fetch_market_cap.clear()
        if existing_fetch_stock_news is not None and callable(getattr(existing_fetch_stock_news, "clear", None)):
            existing_fetch_stock_news.clear()
        st.session_state["ns_scans"].clear()
        st.rerun()

if not watchlist:
    if mode == WORKING_STOCK_LABEL:
        st.info("Add stocks above to begin your custom list.")
    else:
        st.info("No stock tickers to display for this selection. Choose another group or ETF.")
    st.stop()

# Show visible progress while loading each ticker and scoring its headlines.
si_news_loading_bar = st.progress(5, text="Loading watchlist prices…")
quotes = fetch_quotes(tuple(watchlist))
si_news_loading_bar.progress(20, text="Prices loaded · retrieving company headlines…")
news_by_symbol = {}
for _i, _symbol in enumerate(watchlist, 1):
    news_by_symbol[_symbol] = fetch_news(_symbol)
    si_news_loading_bar.progress(20 + int(45 * _i / len(watchlist)),
                                 text=f"Checking headlines: {_symbol} ({_i}/{len(watchlist)})")
# Market capitalization is optional; quote/news failures remain isolated by ticker.
for _symbol in watchlist:
    if quotes.get(_symbol, {}).get("price") is not None:
        quotes[_symbol]["cap"] = fetch_market_cap(_symbol)
si_news_loading_bar.progress(70, text="Analyzing headlines with FinBERT…")
# Automatic FinBERT scan, without a manual scan button or per-stock Gemini calls.
for _i, _symbol in enumerate(watchlist, 1):
    st.session_state['ns_scans'][_symbol] = automatic_stock_scan(_symbol, news_by_symbol.get(_symbol, []))
    si_news_loading_bar.progress(70 + int(30 * _i / len(watchlist)),
                                 text=f"FinBERT: {_symbol} ({_i}/{len(watchlist)})")
si_news_loading_bar.empty()
st.session_state['ns_scanned_at']=datetime.now(MARKET_TZ).strftime('%d %b %Y, %I:%M %p ET')

sigma_scores = saved_regression_zscores(str(PROJECT_ROOT)) if show_sigma else {}
if show_sigma and mode in (SP500_LABEL, CUSTOM_ETF_LABEL) and selected_etf:
    # Prefer regression on THIS ETF's holdings over a separate filtered market scan.
    # The ETF scan saves evaluated constituents even when they fail strategy filters.
    etf_scores_frame, etf_scores_meta = load_etf_scores(selected_etf, PROJECT_ROOT)
    etf_scores = etf_score_map(etf_scores_frame)
    sigma_scores.update(etf_scores)
    if not etf_scores:
        st.caption(f'For ETF Z-scores, run Regression Scanner → Universe: ETF holdings → '
                   f'{selected_etf}. Yahoo holdings and market history must be available.')
    else:
        st.caption(f'{len(etf_scores)} saved {selected_etf} regression scores · '
                   f'market session {etf_scores_meta.get("session", "unknown")}. '
                   'Stocks with insufficient history may still show N/A.')
cards = [
    make_card(
        symbol,
        quotes.get(symbol, {}),
        news_by_symbol.get(symbol, []),
        st.session_state["ns_scans"].get(symbol),
        first=(i == 0),
        sigma_text=(sigma_label(symbol, sigma_scores, email_snapshot,
                               mode == TODAYS_SCAN_LABEL) if show_sigma else ''),
        holding_weight=(etf_data.weights_pct.get(symbol) if mode in (SP500_LABEL, CUSTOM_ETF_LABEL) else None),
    )
    for i, symbol in enumerate(watchlist)
]
st.markdown('<div class="ns-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)
if show_sigma:
    st.caption('σ = regression-channel Z-score versus the fitted trend, not daily-return volatility. '
               'Email alerts show the crossed band if no exact matching Z-score is available.')

last_scan = st.session_state.get("ns_scanned_at")
scan_note = (
    f"Last FinBERT scan: {html.escape(last_scan)}. "
    if last_scan else 'FinBERT scores are calculated automatically. '
)
st.markdown(
    '<div class="ns-footer">'
    f'{scan_note}Headline sentiment is an estimate, not a trading recommendation. '
    'News comes from Yahoo Finance, with GNews fallback when configured; coverage varies. '
    'ETF holdings come from Yahoo Finance where available; regression stocks come from the last successful email. '
    'Working lists are session-only; saved named custom lists are browser-local.'
    '</div>', unsafe_allow_html=True,
)
