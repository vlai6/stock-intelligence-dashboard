"""On-demand GNews headline history stored in local SQLite (free-tier friendly)."""
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

DB_PATH = Path(__file__).with_name('gnews_sentiment.db')
API_URL = 'https://gnews.io/api/v4/search'


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute('''CREATE TABLE IF NOT EXISTS articles (
        ticker TEXT NOT NULL, url TEXT NOT NULL, title TEXT NOT NULL,
        published TEXT NOT NULL, source TEXT, sentiment TEXT, score REAL,
        PRIMARY KEY (ticker, url))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS fetches (
        ticker TEXT PRIMARY KEY, fetched_at TEXT NOT NULL)''')
    return conn


def _query_for(ticker, company):
    # Search by company name rather than only ticker; the ticker is often ambiguous.
    clean = company.strip() if company else ticker
    return f'"{clean[:110]}"' if clean.upper() != ticker.upper() else f'"{ticker}" stock'


def update_gnews(ticker, company, api_key, force=False, pages=3):
    """Fetch at most 30 recent articles per stock, once per 24 hours by default.

    Returns (number_of_new_articles, status_message). No API calls when cache fresh.
    """
    if not api_key:
        return 0, 'Add GNEWS_API_KEY to .streamlit/secrets.toml to enable GNews.'
    ticker = ticker.upper()
    with _connect() as conn:
        last = conn.execute('SELECT fetched_at FROM fetches WHERE ticker=?', (ticker,)).fetchone()
        if last and not force:
            elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(last[0])
            if elapsed < timedelta(hours=24):
                return 0, 'Using saved articles; next automatic update after 24 hours.'

    start = (datetime.now(timezone.utc) - timedelta(days=29)).strftime('%Y-%m-%dT%H:%M:%SZ')
    seen = []
    for page in range(1, pages + 1):
        params = {
            'q': _query_for(ticker, company), 'lang': 'en',
            'from': start, 'max': 10, 'page': page, 'sortby': 'publishedAt',
        }
        try:
            response = requests.get(API_URL, params=params,
                                    headers={'X-Api-Key': api_key}, timeout=18)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            return 0, f'GNews request failed: {exc}'
        articles = payload.get('articles', [])
        seen.extend(articles)
        if len(articles) < 10:
            break
        if page < pages:
            time.sleep(1.1)  # GNews free tier: at most one request/second

    inserted = 0
    with _connect() as conn:
        for a in seen:
            url, title, published = a.get('url'), a.get('title'), a.get('publishedAt')
            if not (url and title and published):
                continue
            cur = conn.execute('''INSERT OR IGNORE INTO articles
                (ticker,url,title,published,source) VALUES (?,?,?,?,?)''',
                (ticker, url, title, published, (a.get('source') or {}).get('name', '')))
            inserted += cur.rowcount
        conn.execute('INSERT OR REPLACE INTO fetches (ticker,fetched_at) VALUES (?,?)',
                     (ticker, datetime.now(timezone.utc).isoformat()))
    return inserted, f'Saved {inserted} new articles from GNews ({len(seen)} retrieved).'


def load_gnews(ticker, days=180):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _connect() as conn:
        return pd.read_sql_query('''SELECT title AS Title, url AS URL,
            published AS Date, source AS Source, sentiment AS Sentiment,
            score AS Score FROM articles WHERE ticker=? AND published>=?
            ORDER BY published ASC''', conn, params=(ticker.upper(), since),
            parse_dates=['Date'])


def score_unscored(ticker):
    """Run existing local FinBERT only for articles not yet scored."""
    from finbert_sentiment import analyze_finbert
    with _connect() as conn:
        missing = conn.execute('''SELECT url, title FROM articles
            WHERE ticker=? AND sentiment IS NULL ORDER BY published''',
            (ticker.upper(),)).fetchall()
    if not missing:
        return 0
    # Preserve duplicates safely by scoring distinct titles and mapping results.
    titles = list(dict.fromkeys(title for _, title in missing))
    results = analyze_finbert(tuple(titles))
    scores = {}
    for _, r in results.iterrows():
        scores[str(r['Title'])] = (str(r['FinBERT Sentiment']), float(r['FinBERT Score']))
    with _connect() as conn:
        for url, title in missing:
            if title in scores:
                conn.execute('''UPDATE articles SET sentiment=?,score=?
                    WHERE ticker=? AND url=?''', (*scores[title], ticker.upper(), url))
    return len(missing)
