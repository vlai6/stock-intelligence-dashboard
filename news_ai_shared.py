"""FinBERT and Gemini helpers that consume ONLY screened seven-day headlines."""
from __future__ import annotations
from datetime import datetime
from typing import Any
import pandas as pd
import streamlit as st

try:
    from finbert_sentiment import analyze_finbert
except ImportError:
    analyze_finbert = None
try:
    from ai_events import group_news_events
except ImportError:
    group_news_events = None


@st.cache_data(ttl=3600, show_spinner=False)
def score_titles(titles: tuple[str, ...]) -> tuple[tuple[str, float | None], ...]:
    if not titles or analyze_finbert is None:
        return tuple(("Unavailable", None) for _ in titles)
    result = analyze_finbert(titles)
    if len(result) != len(titles):
        raise ValueError('FinBERT output length mismatch')
    labels = result['FinBERT Sentiment'].tolist()
    scores = result['FinBERT Score'].tolist() if 'FinBERT Score' in result.columns else [None] * len(labels)
    return tuple((str(a).strip().title(), float(b) if pd.notna(b) else None) for a, b in zip(labels, scores))


def scored_frame(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=['Title','Date','Source','Link','Sentiment','Score'])
    titles=tuple(str(r['title']) for r in records)
    predictions=score_titles(titles)
    out=[]
    for record, (label, score) in zip(records, predictions):
        out.append({'Title':record['title'], 'Date':record.get('date'), 'Source':record.get('source',''),
                    'Link':record.get('link',''), 'Sentiment':label, 'Score':score})
    return pd.DataFrame(out)


@st.cache_data(ttl=21600, show_spinner=False)
def _events_cached(symbol: str, frozen: tuple[tuple[str, str, str, str, str], ...]):
    if group_news_events is None:
        raise RuntimeError('AI event grouping module is not installed')
    frame=pd.DataFrame([{'Title':title, 'Date':pd.to_datetime(date,utc=True,errors='coerce'),
                         'Sentiment':label, 'Source':source, 'Link':link}
                        for title, date, label, source, link in frozen])
    try:
        events, articles=group_news_events(frame, symbol)
        return events, articles, None
    except Exception as exc:
        # Cache a temporary failure too, instead of exhausting free Gemini quotas
        # on every ordinary Streamlit widget rerun.
        return pd.DataFrame(), pd.DataFrame(), str(exc)[:240]


def group_company_news(symbol: str, scored: pd.DataFrame):
    """Return events + grouped articles; error string when Gemini cannot run.
    Never classify unrelated articles because caller already filtered by name/date.
    """
    if scored is None or scored.empty:
        return pd.DataFrame(), pd.DataFrame(), None
    frozen=tuple(zip(scored['Title'].astype(str), scored['Date'].astype(str),
                     scored['Sentiment'].astype(str), scored['Source'].astype(str),
                     scored['Link'].astype(str)))
    try:
        events, articles, error=_events_cached(symbol, frozen)
        if error:
            return pd.DataFrame(), pd.DataFrame(), error
        if not isinstance(events, pd.DataFrame) or not isinstance(articles, pd.DataFrame):
            raise ValueError('Gemini grouping returned an unexpected result')
        return events, articles, None
    except Exception as exc:
        return pd.DataFrame(), pd.DataFrame(), str(exc)[:240]


def explain_gemini_error(reason: str) -> str:
    """Give a safe and actionable reason while leaving FinBERT intact."""
    detail = str(reason or "").lower()
    if "api_key not found" in detail or "key is missing" in detail:
        return (
            "Gemini grouping is unavailable: GEMINI_API_KEY is not configured "
            "in the deployed app. Headlines and FinBERT still work."
        )
    if "http 429" in detail or "quota" in detail or "rate limit" in detail:
        return (
            "Gemini grouping has reached an API quota or rate limit. "
            "Retry later or check the project's Google AI Studio quota. "
            "Headlines and FinBERT still work."
        )
    if "http 401" in detail or "http 403" in detail:
        return (
            "Gemini grouping cannot authenticate with its API key. "
            "Check the key and its restrictions in Streamlit secrets. "
            "Headlines and FinBERT still work."
        )
    if "http 404" in detail or "model unavailable" in detail:
        return (
            "Gemini grouping cannot access the configured model. "
            "Check GEMINI_MODEL and whether the API key can use it. "
            "Headlines and FinBERT still work."
        )
    if "http 503" in detail or "overloaded" in detail or "connection unavailable" in detail:
        return (
            "Gemini grouping is temporarily unavailable or overloaded. "
            "Try Retry Gemini event grouping shortly. "
            "Headlines and FinBERT still work."
        )
    if "event json" in detail or "no text" in detail or "unexpected" in detail:
        return (
            "Gemini returned an incomplete grouping response. "
            "Retry Gemini event grouping. Headlines and FinBERT still work."
        )
    return (
        "Gemini event grouping is unavailable. Expand Technical detail for "
        "the cause, then retry. Headlines and FinBERT still work."
    )


def article_event_assignments(events: pd.DataFrame, grouped: pd.DataFrame):
    """Map model-assigned article titles to event IDs; never invent missing mappings."""
    labels={}
    ids={}
    if not isinstance(events,pd.DataFrame) or events.empty:
        return labels,ids
    if 'Event ID' not in events.columns or 'Event' not in events.columns:
        return labels, ids
    for idx, row in events.iterrows():
        key=str(row['Event ID'])
        name=str(row['Event']).strip()[:90]
        if name:
            labels[key]=name
    if isinstance(grouped,pd.DataFrame) and not grouped.empty:
        title_col=next((c for c in ('Title','Headline','Article') if c in grouped.columns),None)
        key_col=next((c for c in ('Event ID','EventID','event_id') if c in grouped.columns),None)
        if title_col and key_col:
            for _,row in grouped.iterrows():
                key=str(row[key_col])
                if key in labels:
                    ids[str(row[title_col]).strip().casefold()] = key
    return labels, ids
