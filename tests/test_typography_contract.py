"""Source-level typography regression checks; no external APIs or secrets."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def source(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")

theme = source("dashboard_theme.py")
for name in (
    "--si-type-page:", "--si-type-section:", "--si-type-subsection:",
    "--si-type-body:", "--si-type-data:", "--si-type-label:",
    "--si-type-caption:", "--si-type-nav:", "--si-type-metric:",
):
    assert name in theme, f"Missing shared type token: {name}"
for element in ("h1", "h2", "h3", "h4"):
    assert f'[data-testid="stMarkdownContainer"] {element}' in theme
assert "font-size:var(--si-type-page)" in theme
# The auto-generated anchor shortcut beside a heading must be hidden;
# other hyperlinks and real navigation are not targeted by this selector.
assert '[data-testid="stHeaderActionElements"]' in theme
assert 'display: none !important;' in theme.split('[data-testid="stHeaderActionElements"]', 1)[1].split('}', 1)[0]
assert '[data-testid="stPageLink"] a' in theme
assert "font-size:var(--si-type-caption) !important" in theme
assert "font=dict(family='Inter, Segoe UI, Arial, sans-serif', color='#DEEAF7', size=13)" in theme

stock = source("pages/0_Stock_Intelligence.py")
assert "div[data-testid=\"stMarkdownContainer\"] p,\n    div" not in stock
assert "font-size: 1.06rem;" not in stock
assert "font-size: 0.94rem;" not in stock
assert "font-size: 0.9rem;" in stock, "Metrics iframe must match the table data role"
assert "hoverlabel=dict(" in stock
assert "font=dict(size=21)" not in stock

news = source("pages/1_News_Screen.py")
for field in (".ns-headline", ".ns-company", ".ns-source", ".ns-date", ".ns-price"):
    assert field in news
assert ".ns-headline {font-size:var(--si-type-data);" in news
assert ".ns-company {font-size:var(--si-type-data);" in news
assert ".ns-source {color:#6E98B6;font-size:var(--si-type-caption);" in news

sentiment = source("pages/2_News_Sentiment.py")
assert ".si-event-meta {font-size:var(--si-type-data);" in sentiment
assert ".si-compact-title{font-size:var(--si-type-data);" in sentiment
assert ".si-compact-meta{font-size:var(--si-type-caption);" in sentiment
assert "font-size: var(--si-type-metric) !important;" in sentiment

philosophy = source("pages/00_Investment_Philosophy.py")
assert ".si-simple-chip .label {font-size:var(--si-type-caption);" in philosophy
assert ".si-simple-chip .value {font-size:var(--si-type-metric);" in philosophy

scanner = source("regression_scanner/app.py")
assert "font-size:var(--si-type-data)" in scanner
assert "font-size:var(--si-type-caption)" in scanner

nav = source("scroll_nav.py")
assert "font-size: var(--si-type-nav, .85rem);" in nav
assert "nav.replaceChildren();" in nav
# Two new educational ETF sections should sit beside the existing factor explainer.
philosophy = source("pages/00_Investment_Philosophy.py")
assert philosophy.count('with st.expander("Momentum ETFs — SPMO and XMMO"') == 1
assert philosophy.count('with st.expander("Value ETFs — AVLV and VTV"') == 1
assert philosophy.index("Why ETFs, momentum, value and quality?") < philosophy.index("FEATURED ETF FACTORS") < philosophy.index("INDIVIDUAL-STOCK STRATEGIES")
for ticker in ("SPMO", "XMMO", "AVLV", "VTV"):
    assert ticker in philosophy
assert "High momentum is not the same as undervaluation" in philosophy
assert "not guaranteed to move in opposite directions" in philosophy
assert 'expanded=False' in philosophy

# Background is shared rather than implemented separately in each page.
# Keep the fallback and overlay to preserve legibility on every page.
assert '30596248/pexels-photo-30596248.jpeg' in theme
assert 'background-color:var(--si-bg) !important;' in theme
assert 'background-image:' in theme
assert 'linear-gradient(180deg, rgba(3,7,17,.25)' in theme
assert 'background-attachment:fixed !important;' in theme
assert '[data-testid="stMain"]' in theme
assert 'background:transparent !important;' in theme

print("PASS: one shared typography hierarchy, without changing scanner or UI logic")
