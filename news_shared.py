"""Shared seven-day, named-company headline retrieval for News Sentiment.
Based on the existing General News Screen source. No keys logged or stored.
"""
from __future__ import annotations
import html, json, math, os, re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
import requests
import yfinance as yf
from dotenv import load_dotenv
load_dotenv()
try:
    from news_sentiment import fetch_stock_news as existing_fetch_stock_news
except ImportError:
    existing_fetch_stock_news=None
MARKET_TZ=ZoneInfo("America/New_York")
LOOKBACK_DAYS=7
MAX_HEADLINES=60
HEADLINE_ALIASES={
    "NVDA":("NVIDIA",),"AAPL":("Apple",),"GOOG":("Google","Alphabet"),
    "GOOGL":("Google","Alphabet"),"MSFT":("Microsoft",),"AMZN":("Amazon",),
    "TSM":("TSMC","Taiwan Semiconductor"),"META":("Meta","Facebook"),
    "SPCX":("SpaceX","Space Exploration Technologies"),"MU":("Micron","Micron Technology"),
    "INTC":("Intel",),"AMD":("AMD","Advanced Micro Devices"),
    "TSLA":("Tesla",),"PLTR":("Palantir",),"AVGO":("Broadcom",),
    "ARM":("Arm Holdings","Arm"),"ASML":("ASML",),"BABA":("Alibaba",),
}

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
def fetch_company_news(symbol: str, limit: int = 60) -> list[dict]:
    aliases=company_aliases(symbol)
    records=[]
    if existing_fetch_stock_news is not None:
        try:
            records.extend(from_existing_dataframe(existing_fetch_stock_news(symbol)))
        except Exception:
            pass
    records.extend(yahoo_ticker_feed(symbol))
    query=aliases[0] if aliases else symbol
    records.extend(yahoo_company_search(query))
    filtered=filter_company_week(records,symbol,aliases)
    if len(filtered)<min(limit,8):
        key=gnews_key()
        if key:
            records.extend(gnews_company_search(query,key))
            filtered=filter_company_week(records,symbol,aliases)
    return filtered[:max(1,min(int(limit),100))]
