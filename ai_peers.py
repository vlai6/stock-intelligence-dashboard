
import json
import os
import re

import streamlit as st
import yfinance as yf
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = "gemini-3.5-flash-lite"


@st.cache_data(ttl=86400, show_spinner=False)
def recommend_peers(ticker, company_name, description):
    """Ask Gemini for peers and cache results for 24 hours."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from .env")

    client = genai.Client(api_key=api_key)

    prompt = f"""
    Recommend 5 publicly traded competitors or industry peers.

    Primary ticker: {ticker}
    Company: {company_name}
    Business description: {description[:1500]}

    Prioritize direct product competition, overlapping customers,
    and similar business models.

    Return a JSON object containing a "competitors" array.
    Each competitor must have:
    - ticker: exchange ticker symbol
    - name: company name
    - reason: brief explanation
    - relationship: "Direct" or "Industry"

    Exclude the primary company, private companies, and
    known delisted companies. Do not invent tickers.
    """

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    result = json.loads(response.text)
    candidates = result.get("competitors", [])

    if not isinstance(candidates, list):
        raise ValueError("Invalid competitor response.")

    validated = []
    seen = {ticker.upper()}

    for item in candidates:
        if not isinstance(item, dict):
            continue

        symbol = str(item.get("ticker", "")).strip().upper()

        if not re.fullmatch(r"[A-Z0-9.^-]{1,15}", symbol):
            continue

        if symbol in seen:
            continue

        seen.add(symbol)

        try:
            history = yf.Ticker(symbol).history(period="1mo")

            if history.empty:
                continue

            validated.append({
                "ticker": symbol,
                "name": str(item.get("name", symbol)),
                "reason": str(item.get("reason", "")),
                "relationship": str(
                    item.get("relationship", "Industry")
                ),
            })
        except Exception:
            continue

        if len(validated) >= 5:
            break

    return validated
