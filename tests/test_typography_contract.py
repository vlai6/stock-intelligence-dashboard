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
# Hide only Streamlit chrome, not the header anchor used by scroll navigation.
assert '[data-testid="stToolbar"]' in theme
assert '[data-testid="stAppToolbar"]' in theme
assert '[data-testid="stMainMenu"]' in theme
assert 'toolbarMode = "minimal"' in source(".streamlit/config.toml")
assert '[data-testid="stHeader"]' in theme
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
assert philosophy.count('with st.expander("Momentum factor — research, evidence and risks"') == 1
assert philosophy.count('with st.expander("Value factor — research, evidence and risks"') == 1
assert philosophy.index("What the historical data show") < philosophy.index("ETF examples")
assert "primary candidate for a" not in philosophy
assert "preferred research candidate" not in philosophy
assert "optional **mid-cap momentum**" not in philosophy
assert "optional **small-cap value/profitability**" not in philosophy
assert "1965–1989" in philosophy
assert "March–May 2009" in philosophy
assert "163%" in philosophy and "8%" in philosophy
assert "profitability" in philosophy.lower()
assert "Fama & French (1993)" in philosophy
assert "winner-minus-loser portfolios" in philosophy
assert "AVUV" in philosophy
assert "Value ≠ buying every stock" in philosophy
assert philosophy.index("Why ETFs, momentum, value and quality?") < philosophy.index("FEATURED ETF FACTORS") < philosophy.index("INDIVIDUAL-STOCK STRATEGIES")
for ticker in ("SPMO", "XMMO", "AVLV", "VTV"):
    assert ticker in philosophy
assert "not a prediction of which fund will outperform" in philosophy
assert "not guaranteed to move in opposite directions" in philosophy
assert 'expanded=False' in philosophy

# Background is shared rather than implemented separately in each page.
# Keep the fallback and overlay to preserve legibility on every page.
assert 'earth-enhanced-1920.webp' in theme
assert '_earth_image_data_url()' in theme
assert 'data:image/webp;base64,' in theme
asset = ROOT / "assets" / "earth-enhanced-1920.webp"
assert asset.is_file()
image = asset.read_bytes()
assert image.startswith(b"RIFF") and image[8:12] == b"WEBP"
assert len(image) > 8000
assert 'background-color:var(--si-bg) !important;' in theme
assert 'background-image:' in theme
assert 'linear-gradient(180deg, rgba(3,7,17,.12)' in theme
# Semitransparent glass panels preserve Earth visibility and text opacity.
assert '--si-panel-glass:rgba(5,17,32,.65)' in theme
assert '--si-input-glass:rgba(7,22,39,.66)' in theme
assert '--si-popover-glass:rgba(7,21,39,.87)' in theme
assert '--si-action-bg:rgba(27,96,149,.92)' in theme
assert '--si-selection-bg:rgba(13,38,57,.94)' in theme
assert '[data-testid="stExpander"] summary' in theme
assert 'background:var(--si-panel-glass) !important;' in theme
assert 'backdrop-filter:var(--si-glass-blur);' in theme
assert 'background:var(--si-input-glass) !important;' in theme
assert 'background:var(--si-popover-glass) !important;' in theme
assert 'background:#0C1B2A !important;' not in theme
assert '.ns-card {' in news
assert 'background:linear-gradient(150deg,rgba(8,20,34,.59)' in news
assert 'background:rgba(9,23,38,.54);' in philosophy
assert 'background: rgba(14,26,41,.57);' in stock
assert 'background: rgba(3, 7, 17, .64);' in nav
assert 'background: rgba(4, 14, 28, 0.65);' in scanner

assert 'background-attachment:fixed !important;' in theme
assert '[data-testid="stMain"]' in theme
assert 'background:transparent !important;' in theme

print("PASS: one shared typography hierarchy, without changing scanner or UI logic")
