"""Sticky, scroll-aware section navigation for the continuous dashboard.

This uses Streamlit's trusted v2 component API (no external JavaScript,
network calls, or secrets). The component sends only approved section IDs.
"""
from __future__ import annotations

import streamlit as st

SECTIONS = (
    ("philosophy", "Investment Philosophy"),
    ("news", "General News Screen"),
    ("scanner", "Regression Scanner"),
    ("metrics", "Metrics & Competition"),
    ("sentiment", "Recent Sentiment"),
)
ALLOWED_SECTION_IDS = frozenset(slug for slug, _ in SECTIONS)

CSS = """
.si-scroll-nav {
  position: fixed;
  top: 38px;
  left: 0;
  right: 0;
  z-index: 998;
  box-sizing: border-box;
  min-height: 44px;
  padding: 5px max(14px, calc((100vw - 1620px) / 2));
  display: flex;
  align-items: center;
  gap: 5px;
  overflow-x: auto;
  background: rgba(3, 7, 17, .98);
  border-bottom: 1px solid #19314c;
  box-shadow: 0 6px 20px rgba(0,0,0,.32);
  scrollbar-width: thin;
}
.si-scroll-nav button {
  flex-shrink: 0;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: #9cb5ca;
  cursor: pointer;
  font-size: .77rem;
  font-weight: 600;
  padding: 7px 12px;
  white-space: nowrap;
}
.si-scroll-nav button:hover, .si-scroll-nav button:focus-visible {
  border-color: #2b5278;
  color: #e6f5ff;
}
.si-scroll-nav button[data-active="true"] {
  background: #10263e;
  color: #73c8ff;
  border-color: #21466b;
}
@media(max-width:700px) {
  .si-scroll-nav { top: 32px; padding-inline: 8px; }
  .si-scroll-nav button { padding: 8px 9px; font-size:.72rem; }
}
"""

JS = """
export default function({parentElement, data, setTriggerValue}) {
  const nav = parentElement.querySelector(".si-scroll-nav");
  if (!nav) return;
  const entries = Array.isArray(data.sections) ? data.sections : [];
  const loaded = new Set(Array.isArray(data.loaded) ? data.loaded : []);
  const controls = new Map();
  let pending = false;
  let waitingFor = null;
  let closed = false;

  for (const entry of entries) {
    // Only fixed, server-authored IDs and labels are provided.
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = entry.label;
    button.dataset.section = entry.id;
    button.addEventListener("click", () => {
      const anchor = document.getElementById("si-anchor-" + entry.id);
      if (anchor) {
        anchor.scrollIntoView({behavior: "smooth", block: "start"});
        const base = window.location.pathname + window.location.search;
        window.history.replaceState(null, "", base + "#si-" + entry.id);
      }
    });
    controls.set(entry.id, button);
    nav.appendChild(button);
  }

  function inspect() {
    if (closed) return;
    // Scroll can occur inside Streamlit's main content element or the page.
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
    let current = entries.length ? entries[0].id : null;
    let nextToLoad = null;

    for (const entry of entries) {
      const anchor = document.getElementById("si-anchor-" + entry.id);
      if (!anchor) continue;
      const y = anchor.getBoundingClientRect().top;
      if (y <= 160) current = entry.id;
      if (!loaded.has(entry.id) && y < viewportHeight + 450 && y > -250
          && nextToLoad === null) {
        nextToLoad = entry.id;
      }
    }
    for (const [id, button] of controls.entries()) {
      const isCurrent = id === current;
      button.dataset.active = String(isCurrent);
      if (isCurrent) button.setAttribute("aria-current", "location");
      else button.removeAttribute("aria-current");
    }
    // Loading a section reruns Python. Never notify for mere active-tab changes.
    if (nextToLoad && !waitingFor) {
      waitingFor = nextToLoad;
      setTriggerValue("reveal", nextToLoad);
    }
  }
  function schedule() {
    if (pending || closed) return;
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      inspect();
    });
  }
  const main = document.querySelector('[data-testid="stMain"]') || document.body;
  const observer = new MutationObserver(schedule);
  observer.observe(main, {childList:true, subtree:true});
  document.addEventListener("scroll", schedule, {passive:true, capture:true});
  window.addEventListener("resize", schedule, {passive:true});
  schedule();
  if (window.location.hash.startsWith("#si-")) {
    const id = window.location.hash.slice(4);
    if (entries.some(entry => entry.id === id)) {
      requestAnimationFrame(() => {
        const target = document.getElementById("si-anchor-" + id);
        if (target) target.scrollIntoView({block:"start"});
      });
    }
  }
  return () => {
    closed = true;
    observer.disconnect();
    document.removeEventListener("scroll", schedule, true);
    window.removeEventListener("resize", schedule);
  };
}
"""

_SCROLL_COMPONENT = st.components.v2.component(
    "stock_intelligence_scroll_navigation_v1",
    html='<nav class="si-scroll-nav" aria-label="Dashboard sections"></nav>',
    css=CSS,
    js=JS,
    isolate_styles=False,
)


def _on_section_reveal() -> None:
    event = (st.session_state.get("si_scroll_navigation_v1") or {}).get("reveal")
    if event in ALLOWED_SECTION_IDS:
        st.session_state.setdefault("si_loaded_sections", {"philosophy"}).add(event)


def render_scroll_navigation() -> None:
    """Highlight the section currently in view and reveal nearby sections."""
    _SCROLL_COMPONENT(
        data={
            "sections": [{"id": key, "label": title} for key, title in SECTIONS],
            "loaded": sorted(st.session_state.get("si_loaded_sections", {"philosophy"})),
        },
        key="si_scroll_navigation_v1",
        on_reveal_change=_on_section_reveal,
    )
