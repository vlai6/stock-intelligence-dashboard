"""Offline news coverage checks: every feed, strict 7-day names, and refresh.

No API keys, Gemini calls, or network requests needed.
"""
from __future__ import annotations

import ast
from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for name in ("news_shared.py", "news_ai_shared.py", "pages/2_News_Sentiment.py"):
    ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)


def test_motley_fool_article_meets_strict_service_now_filter():
    import news_shared as n
    assert "ServiceNow" in n.company_aliases("NOW")
    now = datetime.now(n.MARKET_TZ)
    title = "ServiceNow vs. UiPath: Which Technology Stock Is a Better Buy for 2027?"
    records = [
        {"title": title, "date": now - timedelta(days=3),
         "source": "The Motley Fool", "link": "https://www.fool.com/test"},
        {"title": "ServiceNow historical coverage", "date": now - timedelta(days=9),
         "source": "Publisher", "link": "https://example.org/old"},
        {"title": "UiPath without ServiceNow in title", "date": now - timedelta(days=2),
         "source": "Publisher", "link": "https://example.org/other"},
    ]
    results = n.filter_company_week(records, "NOW", n.company_aliases("NOW"))
    assert [item["title"] for item in results] == [title]


def test_google_news_rss_parses_actual_dates_and_source_without_network(monkeypatch):
    import news_shared as n
    published = format_datetime(datetime.now(n.MARKET_TZ) - timedelta(days=2))
    source = "The Motley Fool"
    title = "ServiceNow vs. UiPath: Which Technology Stock Is a Better Buy for 2027?"
    xml = (
        '<rss version="2.0"><channel><item><title>'
        + title + ' - ' + source
        + '</title><link>https://news.google.com/rss/articles/ABC</link>'
        + '<pubDate>' + published + '</pubDate>'
        + '<source>The Motley Fool</source></item></channel></rss>'
    ).encode("utf-8")

    class StubResponse:
        content = xml
        def raise_for_status(self):
            return None

    def fake_get(url, *, params, headers, timeout):
        assert url == "https://news.google.com/rss/search"
        assert params["q"] == '"ServiceNow" when:7d'
        assert params["ceid"] == "US:en"
        assert timeout[1] <= 15
        return StubResponse()

    monkeypatch.setattr(n.requests, "get", fake_get)
    n.google_news_rss_search.clear()
    result = n.google_news_rss_search("ServiceNow")
    assert len(result) == 1
    assert result[0]["title"] == title
    assert result[0]["source"] == source
    assert n.filter_company_week(result, "NOW", n.company_aliases("NOW"))


def test_gnews_and_rss_are_checked_even_when_yahoo_has_many_articles(monkeypatch):
    import news_shared as n
    now = datetime.now(n.MARKET_TZ)
    def article(title):
        return {"title": title, "date": now - timedelta(days=1),
                "link": "https://example.com/" + str(len(title)),
                "source": "Test"}
    yahoo = [article(f"ServiceNow Yahoo article {i}") for i in range(15)]
    gnews = [article("ServiceNow GNews unique headline")]
    rss = [article("ServiceNow RSS unique headline")]
    calls = []
    monkeypatch.setattr(n, "existing_fetch_stock_news", None)
    monkeypatch.setattr(n, "yahoo_ticker_feed", lambda sym: yahoo)
    monkeypatch.setattr(n, "yahoo_company_search", lambda name: [])
    monkeypatch.setattr(n, "gnews_key", lambda: "test-key")
    def mock_gnews(query, key):
        calls.append(("gnews", query))
        return gnews
    def mock_rss(query):
        calls.append(("rss", query))
        return rss
    monkeypatch.setattr(n, "gnews_company_search", mock_gnews)
    monkeypatch.setattr(n, "google_news_rss_search", mock_rss)
    n.fetch_company_news.clear()
    result = n.fetch_company_news("NOW", 60)
    titles = {record["title"] for record in result}
    assert "ServiceNow GNews unique headline" in titles
    assert "ServiceNow RSS unique headline" in titles
    assert len(titles) == 17
    assert calls == [("gnews", "ServiceNow"), ("rss", "ServiceNow")]


def test_refresh_clears_every_feed_cache_without_resetting_watchlists(monkeypatch):
    import news_shared as n
    calls = []
    def fake_provider(name):
        def provider(*args):
            return []
        provider.clear = lambda: calls.append(name)
        return provider
    providers = (
        "fetch_company_news", "yahoo_ticker_feed", "yahoo_company_search",
        "gnews_company_search", "google_news_rss_search",
    )
    for name in providers:
        monkeypatch.setattr(n, name, fake_provider(name))
    monkeypatch.setattr(n, "existing_fetch_stock_news",
                        fake_provider("existing_fetch_stock_news"))
    n.clear_company_news_caches()
    assert set(calls) == set(providers) | {"existing_fetch_stock_news"}


def test_gemini_error_summary_is_actionable_and_safe():
    from news_ai_shared import explain_gemini_error
    for raw, expected in (
        ("Gemini HTTP 429: free-tier quota reached", "quota"),
        ("Gemini HTTP 503: overloaded", "temporarily"),
        ("GEMINI_API_KEY not found", "not configured"),
        ("Gemini HTTP 404: model unavailable", "model"),
        ("Gemini HTTP 401: API key not accepted", "API key"),
    ):
        assert expected.lower() in explain_gemini_error(raw).lower()
    assert "FinBERT" in explain_gemini_error("Gemini returned no text")


def test_recent_sentiment_refresh_and_grouping_ui_contract():
    page = (ROOT / "pages/2_News_Sentiment.py").read_text()
    assert "clear_company_news_caches()" in page
    assert "_events_cached.clear()" in page
    assert "explain_gemini_error(group_error)" in page
    assert "Headline sources: Yahoo Finance" in page
    assert "group_company_news(symbol,event_frame)" in page
