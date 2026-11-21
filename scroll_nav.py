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
  top: 48px;
  left: 0;
  right: 0;
  z-index: 100001;
  box-sizing: border-box;
  height: 48px;
  min-height: 48px;
  padding: 0 max(14px, calc((100vw - 1620px) / 2));
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
  color: #c5d7e8;
  cursor: pointer;
  font-size: var(--si-type-nav, .85rem);
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
  color: #c5eaff;
  border-color: #21466b;
}
@media(max-width:700px) {
  .si-scroll-nav { top: 48px; padding-inline: 8px; }
  .si-scroll-nav button { padding: 8px 9px; font-size:.8rem; }
}
"""

JS = """
export default function({parentElement, data, setTriggerValue}) {
  // Streamlit's component wrapper may clip position:fixed descendants.
  // Mount the one global sticky bar at document.body instead of inside it.
  // Do not touch parentElement.innerHTML: Streamlit owns that markup.
  const navId = "si-global-scroll-nav";
  let nav = document.getElementById(navId);
  if (!nav) {
    nav = document.createElement("nav");
    nav.id = navId;
  }
  nav.className = "si-scroll-nav";
  nav.setAttribute("aria-label", "Dashboard sections");
  const owner = Symbol("si-scroll-nav-owner");
  nav.__siOwner = owner;
  // Re-rendering the component must never append a second copy of the tabs.
  nav.replaceChildren();
  document.body.appendChild(nav);

  const entries = Array.isArray(data.sections) ? data.sections : [];
  const loaded = new Set(Array.isArray(data.loaded) ? data.loaded : []);
  const controls = new Map();
  // Align under Streamlit's actual toolbar height.
  const header = document.querySelector('[data-testid="stHeader"]');
  const headerBottom = header ? header.getBoundingClientRect().bottom : 48;
  nav.style.top = Math.max(38, Math.ceil(headerBottom)) + "px";
  const navOffset = () => nav.getBoundingClientRect().bottom + 22;
  document.documentElement.style.setProperty("--si-section-offset", navOffset() + "px");

  // Unlike scrollIntoView(start), this leaves section headings visible
  // below the pinned navigation and works with Streamlit's scroll container.
  function scrollToSection(id, behavior = "smooth") {
    const target = document.getElementById("si-anchor-" + id);
    if (!target) return false;
    const delta = target.getBoundingClientRect().top - navOffset();
    if (Math.abs(delta) < 3) return true;
    let ancestor = target.parentElement;
    while (ancestor && ancestor !== document.body) {
      const computed = window.getComputedStyle(ancestor);
      if (/(auto|scroll|overlay)/.test(computed.overflowY)
          && ancestor.scrollHeight > ancestor.clientHeight + 2) {
        ancestor.scrollBy({top: delta, behavior});
        return true;
      }
      ancestor = ancestor.parentElement;
    }
    const page = document.scrollingElement;
    if (page && page.scrollHeight > page.clientHeight + 2) {
      page.scrollBy({top: delta, behavior});
    } else {
      window.scrollBy({top: delta, behavior});
    }
    return true;
  }

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
      if (!loaded.has(entry.id)) nav.__siPendingSection = entry.id;
      if (scrollToSection(entry.id)) {
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
    const activeThreshold = navOffset() + 16;
    let current = entries.length ? entries[0].id : null;
    let nextToLoad = null;

    for (const entry of entries) {
      const anchor = document.getElementById("si-anchor-" + entry.id);
      if (!anchor) continue;
      const y = anchor.getBoundingClientRect().top;
      if (y <= activeThreshold) current = entry.id;
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
  if (nav.__siPendingSection && loaded.has(nav.__siPendingSection)) {
    const revealed = nav.__siPendingSection;
    nav.__siPendingSection = null;
    requestAnimationFrame(() => scrollToSection(revealed, "auto"));
  } else if (window.location.hash.startsWith("#si-")) {
    const id = window.location.hash.slice(4);
    if (entries.some(entry => entry.id === id)) {
      requestAnimationFrame(() => scrollToSection(id, "auto"));
    }
  }
  return () => {
    closed = true;
    observer.disconnect();
    document.removeEventListener("scroll", schedule, true);
    window.removeEventListener("resize", schedule);
    // Old component instances can unmount after a new instance has rendered.
    // Only the latest owner may remove the shared navigation element.
    if (nav.__siOwner === owner) nav.remove();
  };
}
"""

_SCROLL_COMPONENT = st.components.v2.component(
    "stock_intelligence_scroll_navigation_v1",
    html='<span aria-hidden="true" class="si-scroll-nav-mount"></span>',
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
