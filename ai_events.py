"""Gemini event grouping from existing headlines only.

No stock/news fetching here. A single Gemini REST call groups supplied headlines.
The caller (news_ai_shared.py) caches results and allows FinBERT to work if this fails.
Reads GEMINI_API_KEY from .streamlit/secrets.toml or the local .env environment.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def _api_key() -> str:
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY"):
        try:
            import streamlit as st
            secret = st.secrets.get(key, "")
            if secret:
                return str(secret).strip()
        except Exception:
            pass
        if os.getenv(key):
            return os.environ[key].strip()
    return ""


def _unpack_content(data: dict) -> dict:
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Gemini returned no text; check model availability and quota") from exc
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()
    try:
        result = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Gemini did not return valid event JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Gemini returned an unexpected event format")
    return result


def _request_gemini(payload: dict, key: str, model: str) -> dict:
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,64}", model):
        raise RuntimeError("Invalid GEMINI_MODEL configuration")
    response = None
    for attempt in range(2):
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json=payload, timeout=(12, 50),
            )
        except requests.RequestException as exc:
            # One bounded retry for temporary connectivity problems only.
            if attempt == 0:
                time.sleep(1.5)
                continue
            raise RuntimeError(
                f"Gemini connection unavailable ({type(exc).__name__})"
            ) from exc
        if response.status_code in (502, 503, 504) and attempt == 0:
            time.sleep(1.5)
            continue
        break
    if response is None:
        raise RuntimeError("Gemini connection unavailable")
    if not response.ok:
        # Do not log headers, API keys or full request/response bodies.
        diagnostic = {
            400: "invalid request or model configuration",
            401: "API key not accepted",
            403: "API key restricted or not authorized",
            404: "model unavailable for this API key",
            429: "free-tier quota or rate limit reached",
            503: "Gemini temporarily overloaded",
        }.get(response.status_code, "API request rejected")
        raise RuntimeError(f"Gemini HTTP {response.status_code}: {diagnostic}. Model: {model}")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("Gemini returned non-JSON API output") from exc


def make_group_tables(titles: list[str], output: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use only article indexes from our supplied list, never fabricated titles."""
    incoming = output.get("events", [])
    if not isinstance(incoming, list):
        raise RuntimeError("Gemini response has no event list")
    events = []
    assignments = []
    used = set()
    for i, item in enumerate(incoming[:50], 1):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("event") or "").strip()[:100]
        ids = item.get("article_ids") or item.get("article_indices") or []
        if not name or not isinstance(ids, list):
            continue
        matched = []
        for idx in ids:
            if isinstance(idx, bool):
                continue
            try:
                index = int(idx)
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(titles) and index not in used:
                matched.append(index)
                used.add(index)
        if not matched:
            continue
        event_id = str(i)
        events.append({"Event ID": event_id, "Event": name, "Articles": len(matched)})
        assignments.extend({"Event ID": event_id, "Title": titles[idx]} for idx in matched)
    # Preserve EVERY sourced headline. The previous adapter silently dropped
    # articles not assigned to a cluster by Gemini, artificially reducing the
    # number of events shown. A singleton is a real source headline, not a
    # fabricated article; it simply had no matching partner in this response.
    next_id = len(incoming[:50]) + 1
    for idx, title in enumerate(titles):
        if idx in used:
            continue
        event_id = str(next_id)
        next_id += 1
        events.append({"Event ID": event_id, "Event": title[:100], "Articles": 1})
        assignments.append({"Event ID": event_id, "Title": title})
    return (pd.DataFrame(events, columns=["Event ID", "Event", "Articles"]),
            pd.DataFrame(assignments, columns=["Event ID", "Title"]))


def group_news_events(frame: pd.DataFrame, symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cluster the supplied Yahoo headlines into same-event groups."""
    empty_events = pd.DataFrame(columns=["Event ID", "Event", "Articles"])
    empty_articles = pd.DataFrame(columns=["Event ID", "Title"])
    if frame is None or frame.empty:
        return empty_events, empty_articles
    if "Title" not in frame:
        raise RuntimeError("Gemini grouping input is missing Title column")
    titles = [str(t).strip()[:350] for t in frame["Title"].tolist() if str(t).strip()]
    if not titles:
        return empty_events, empty_articles
    key = _api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY not found: add it to .streamlit/secrets.toml or your local .env file")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    prompt = (
        "Cluster these real headlines about the stock " + str(symbol)[:16] + ". "
        "Cluster articles describing the SAME underlying real news event, as in a news digest. "
        "Do not group based solely on sentiment, generic market performance, or the same company. "
        "Assign EVERY input headline to exactly ONE event. "
        "For a headline with no close match, create a SINGLE-ARTICLE event. "
        "Use concise factual event names, avoiding claims not stated in the headlines. "
        "Return exactly JSON: {\"events\":[{\"name\":\"event summary\",\"article_ids\":[0,1]}]}. "
        "Use zero-based indices from the list below. Do not invent indices or headlines.\n\n"
        + "\n".join(f"{i}: {title}" for i, title in enumerate(titles[:90]))
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.15, "responseMimeType": "application/json", "maxOutputTokens": 4500},
    }
    result = _request_gemini(payload, key, model)
    return make_group_tables(titles[:90], _unpack_content(result))
