"""Subtle top-left notice displayed by the Streamlit multipage entrypoint.

Install once in app.py immediately after st.set_page_config, before page.run.
The notice is CSS-driven and appears before slow page API calls.
"""
from __future__ import annotations

import streamlit as st


def show_loading_notice() -> None:
    st.markdown('''
<style>
/* Shared, low-profile reminder inside the main page background. */
[data-testid="stMainBlockContainer"]::before {
    content: "Please allow 2–5 minutes for the page to load.";
    display: block;
    color: #ef7881;
    font: 500 11px/1.45 Inter, "Segoe UI", Arial, sans-serif;
    letter-spacing: .012em;
    padding: 0 0 7px 1px;
    opacity: .85;
    pointer-events: none;
}
</style>
''', unsafe_allow_html=True)
