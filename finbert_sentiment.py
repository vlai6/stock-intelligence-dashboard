
import pandas as pd
import streamlit as st
from transformers import pipeline


MODEL_NAME = "ProsusAI/finbert"


@st.cache_resource(show_spinner="Loading FinBERT model...")
def load_finbert():
    """Load the financial sentiment model once."""
    return pipeline(
        task="text-classification",
        model=MODEL_NAME,
        tokenizer=MODEL_NAME,
        device=-1
    )


@st.cache_data(show_spinner=False)
def analyze_finbert(headlines):
    """
    Analyze headlines using FinBERT.

    headlines must be a tuple of strings.
    Results are cached for identical inputs.
    """
    if not headlines:
        return pd.DataFrame(
            columns=[
                "Title", "FinBERT Sentiment",
                "FinBERT Score", "Confidence"
            ]
        )

    classifier = load_finbert()

    predictions = classifier(
        list(headlines),
        truncation=True,
        max_length=512,
        batch_size=8,
        top_k=None
    )

    rows = []

    for title, probabilities in zip(
        headlines, predictions
    ):
        scores = {
            item["label"].lower(): item["score"]
            for item in probabilities
        }

        positive = scores.get("positive", 0.0)
        negative = scores.get("negative", 0.0)
        neutral = scores.get("neutral", 0.0)

        sentiment = max(
            scores,
            key=scores.get
        ).capitalize()

        rows.append({
            "Title": title,
            "FinBERT Sentiment": sentiment,
            "FinBERT Score": positive - negative,
            "Confidence": max(
                positive, neutral, negative
            )
        })

    return pd.DataFrame(rows)
