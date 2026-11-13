
import json
import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

# Use the same working model as your ai_peers.py file.
MODEL_NAME = "gemini-3.5-flash-lite"


def group_news_events(news_df, symbol):
    """
    Group articles that describe the same underlying event.
    Gemini identifies relationships; Python calculates dates.
    """
    if news_df.empty:
        return pd.DataFrame(), {}

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY missing from .env")

    articles = []
    for i, (_, row) in enumerate(news_df.iterrows()):
        articles.append({
            "id": i,
            "title": str(row["Title"]),
            "source": str(row["Source"]),
            "published": str(row["Date"])
        })

    prompt = f"""
You are a financial news event-grouping analyst.

Target stock: {symbol}

Group the articles below into distinct underlying news events.

Rules:
1. Group articles ONLY when they describe the same specific
   development, announcement, incident, or disclosure.
2. Similar topics are not necessarily the same event.
3. A broad market roundup is not the same event as a
   company-specific announcement.
4. Never assume an unverified claim is true.
5. A reported or rumored event must remain labeled as such.
6. Do not invent events or article IDs.
7. Every article ID must appear in exactly one group.
8. Give each group a concise, neutral event name.
9. Include a short explanation of why articles belong together.
10. Assign a report_status:
    "Confirmed", "Reported", "Speculative", or "Unclear".
    This is an assessment based on headlines only, not
    independent fact-checking.
11. Do not generate event dates. Python will calculate them.

Return JSON only, with this structure:
{{
  "events": [
    {{
      "name": "Concise event description",
      "article_ids": [0, 2],
      "reason": "Both headlines describe the same announcement.",
      "report_status": "Reported"
    }}
  ]
}}

Articles:
{json.dumps(articles, ensure_ascii=False)}
"""

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0
        )
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    result = json.loads(response.text)
    proposed_events = result.get("events", [])

    if not isinstance(proposed_events, list):
        raise ValueError("Invalid event grouping response.")

    used_ids = set()
    valid_events = []

    for event in proposed_events:
        if not isinstance(event, dict):
            continue

        ids = []
        for article_id in event.get("article_ids", []):
            if (
                type(article_id) is int
                and 0 <= article_id < len(news_df)
                and article_id not in used_ids
                and article_id not in ids
            ):
                ids.append(article_id)

        if not ids:
            continue

        used_ids.update(ids)

        valid_events.append({
            "name": str(event.get("name", "News event")),
            "article_ids": ids,
            "reason": str(event.get("reason", "")),
            "report_status": str(
                event.get("report_status", "Unclear")
            )
        })

    # Preserve any articles Gemini omitted as separate events.
    for i in range(len(news_df)):
        if i not in used_ids:
            valid_events.append({
                "name": articles[i]["title"],
                "article_ids": [i],
                "reason": "Article not assigned to another event.",
                "report_status": "Unclear"
            })

    rows = []
    event_articles = {}
    working = news_df.reset_index(drop=True)

    for event_number, event in enumerate(valid_events, start=1):
        group = working.iloc[event["article_ids"]].copy()
        group = group.sort_values("Date")

        event_id = f"E{event_number:03d}"
        first_seen = group["Date"].min()

        # Use the active FinBERT/VADER classifications.
        sentiment_counts = group["Sentiment"].value_counts()
        sentiment = (
            sentiment_counts.idxmax()
            if not sentiment_counts.empty
            else "Unknown"
        )

        rows.append({
            "Event ID": event_id,
            "Event": event["name"],
            "First Seen": first_seen,
            "Sentiment": sentiment,
            "Articles": len(group),
            "Report Status": event["report_status"],
            "Reason": event["reason"]
        })

        event_articles[event_id] = group

    events_df = pd.DataFrame(rows)
    events_df = events_df.sort_values(
        "First Seen", ascending=False
    ).reset_index(drop=True)

    return events_df, event_articles
