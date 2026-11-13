
import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


analyzer = SentimentIntensityAnalyzer()


def extract_url(value):
    if isinstance(value, dict):
        return value.get("url", "") or ""
    return value if isinstance(value, str) else ""


def classify_sentiment(score):
    if score >= 0.05:
        return "Positive"
    if score <= -0.05:
        return "Negative"
    return "Neutral"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_news(ticker, count=40):
    """Fetch recent Yahoo Finance headlines, cached for one hour."""

    stock = yf.Ticker(ticker)
    raw_news = stock.get_news(count=count) or []

    articles = []
    seen = set()

    for item in raw_news:
        if not isinstance(item, dict):
            continue

        content = item.get("content") or item

        if not isinstance(content, dict):
            continue

        title = str(content.get("title") or "").strip()

        if not title or title.lower() in seen:
            continue

        seen.add(title.lower())

        provider = content.get("provider") or {}
        if not isinstance(provider, dict):
            provider = {}

        source = provider.get("displayName", "Unknown")

        url = (
            extract_url(content.get("canonicalUrl"))
            or extract_url(content.get("clickThroughUrl"))
            or extract_url(content.get("link"))
            or extract_url(item.get("link"))
        )

        raw_date = (
            content.get("pubDate")
            or item.get("providerPublishTime")
        )

        if isinstance(raw_date, (int, float)):
            published = pd.to_datetime(
                raw_date, unit="s", utc=True, errors="coerce"
            )
        else:
            published = pd.to_datetime(
                raw_date, utc=True, errors="coerce"
            )

        if pd.isna(published):
            continue

        # Score headlines only, not article bodies.
        score = analyzer.polarity_scores(title)["compound"]

        articles.append({
            "Title": title,
            "Date": published,
            "Source": source,
            "URL": url,
            "Sentiment": classify_sentiment(score),
            "Score": float(score),
        })

    if not articles:
        return pd.DataFrame(columns=[
            "Title", "Date", "Source",
            "URL", "Sentiment", "Score"
        ])

    return (
        pd.DataFrame(articles)
        .sort_values("Date", ascending=False)
        .reset_index(drop=True)
    )


def calculate_news_returns(news_df, history, horizon=5):
    """
    Calculate stock returns after article publication.

    Baseline: first available trading close strictly after
    the article's UTC publication date.

    Horizon: N trading sessions after that baseline.

    This is an approximation, not an intraday event study.
    """

    if news_df.empty or history.empty:
        return pd.DataFrame()

    prices = history["Close"].dropna().sort_index().copy()

    if prices.empty:
        return pd.DataFrame()

    # Compare by UTC calendar dates.
    price_dates = pd.to_datetime(prices.index, utc=True).normalize()
    price_values = prices.to_numpy(dtype=float)

    results = []

    for _, article in news_df.iterrows():
        publication_date = pd.Timestamp(
            article["Date"]
        ).tz_convert("UTC").normalize()

        # Start from the next trading date.
        positions = np.flatnonzero(
            price_dates > publication_date
        )

        if len(positions) == 0:
            continue

        start_idx = int(positions[0])
        end_idx = start_idx + horizon

        # Do not calculate returns before the horizon exists.
        if end_idx >= len(price_values):
            continue

        start_price = price_values[start_idx]
        end_price = price_values[end_idx]

        if start_price <= 0 or not np.isfinite(end_price):
            continue

        stock_return = end_price / start_price - 1

        results.append({
            "Title": article["Title"],
            "Date": article["Date"],
            "Sentiment": article["Sentiment"],
            "Score": article["Score"],
            "Forward Return": stock_return,
        })

    return pd.DataFrame(results)
