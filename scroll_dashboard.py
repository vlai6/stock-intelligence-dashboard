"""One continuous scroll, with each existing Streamlit page as a lazy fragment.

Keep the original page scripts as the single source of truth: no duplicate
scanner rules, financial calculations or private APIs. The section runner
isolates page-local st.stop() guards so they cannot abort later sections.
"""
from __future__ import annotations

import functools
import re
from pathlib import Path

import streamlit as st

from dashboard_theme import apply_dashboard_theme
from scroll_nav import SECTIONS, render_scroll_navigation

ROOT = Path(__file__).resolve().parent

PAGE_PATHS = {
    "philosophy": "pages/00_Investment_Philosophy.py",
    "news": "pages/1_News_Screen.py",
    "scanner": "regression_scanner/app.py",
    "metrics": "pages/0_Stock_Intelligence.py",
    "sentiment": "pages/2_News_Sentiment.py",
}


class _EndSection(Exception):
    """Only end one embedded page; the next dashboard section must still run."""


@functools.lru_cache(maxsize=5)
def _section_code(relative_path: str):
    """Compile trusted repository code once; never execute untrusted input."""
    if relative_path not in PAGE_PATHS.values():
        raise ValueError("Unknown dashboard section")
    file = ROOT / relative_path
    source = file.read_text(encoding="utf-8-sig")
    # Existing pages use script-wide stop guards. The continuous layout must
    # not allow one page's lack of headlines or ticker to abort all other pages.
    source = re.sub(r"\bst\.stop\(\s*\)", "raise _EndSection()", source)
    return compile(source, str(file), "exec")


def _render_existing_section(section: str) -> None:
    path = PAGE_PATHS[section]
    filename = ROOT / path
    namespace = {
        "__name__": f"_si_continuous_{section}",
        "__file__": str(filename),
        "__package__": None,
        "_EndSection": _EndSection,
    }
    try:
        exec(_section_code(path), namespace)
    except _EndSection:
        pass


def _make_fragment(section: str):
    # Each section has its own fragment identity, so button clicks normally
    # rerun only that section rather than refreshing every news/AI API call.
    @st.fragment(key=f"si_continuous_{section}")
    def display() -> None:
        if section in st.session_state["si_loaded_sections"]:
            _render_existing_section(section)
        else:
            section_title = dict(SECTIONS)[section]
            st.markdown("#### " + section_title)
            st.caption("This section loads automatically when you scroll here.")
            # A visible fallback keeps every section reachable even if the
            # browser's scroll observer fails to fire or another section
            # is spending time fetching news / prices.
            if st.button(
                "Load " + section_title, key=f"si_load_section_{section}",
                help="Open this section now",
            ):
                st.session_state["si_loaded_sections"].add(section)
                st.rerun(scope="fragment")
    return display


st.session_state.setdefault("si_loaded_sections", {"philosophy"})
st.session_state["si_continuous_mode"] = True
apply_dashboard_theme()

st.markdown("""
<style>
/* Reserve room for the always-visible section navigation below Streamlit's toolbar. */
/* More specific than the legacy page themes loaded inside each section. */
html body [data-testid="stMainBlockContainer"],
html body [data-testid="stAppViewBlockContainer"] {
  padding-top: 5.1rem !important;
}
html, body, [data-testid="stMain"], [data-testid="stAppViewContainer"] {
  scroll-padding-top: var(--si-section-offset, 130px) !important;
}
.si-section-marker { height: 1px; scroll-margin-top: var(--si-section-offset, 130px); }
div[class*="st-key-si_section_"] {
  padding: 0.3rem 0 2rem;
  border-bottom: 1px solid rgba(130, 159, 194, .20);
}
@media(max-width:700px) {
  html body [data-testid="stMainBlockContainer"],
  html body [data-testid="stAppViewBlockContainer"] { padding-top:5.5rem !important; }
  .si-section-marker { scroll-margin-top: var(--si-section-offset, 130px); }
}
</style>
""", unsafe_allow_html=True)

render_scroll_navigation()

# Reserve ALL section anchors and placeholders before executing any expensive
# page body. News fetches several tickers sequentially; previously the main
# script could pause on News before it even created the Scanner, Metrics and
# Recent Sentiment sections farther down the page.
section_slots = {}
for slug, label in SECTIONS:
    with st.container(key=f"si_section_{slug}"):
        st.html(f'<div class="si-section-marker" id="si-anchor-{slug}"></div>')
        slot = st.empty()
        with slot:
            st.markdown("#### " + label)
            st.caption("Loading section…")
        section_slots[slug] = slot

# Populate reserved slots in the original visual order. Fragment identities,
# scroll anchors and controls stay unchanged; only the layout skeleton exists
# sooner, so a slow News request never makes later sections disappear.
for slug, _label in SECTIONS:
    with section_slots[slug].container():
        _make_fragment(slug)()
