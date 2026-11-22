"""Keep public Stock Intelligence Toolkit branding consistent.

Stable GitHub slug, module paths and localStorage keys intentionally retain
their historical names. Renaming those would break deployment or saved lists.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app = (ROOT / "app.py").read_text(encoding="utf-8")
nav = (ROOT / "scroll_nav.py").read_text(encoding="utf-8")
workflow = (ROOT / ".github/workflows/cloud-email-scanner.yml").read_text(encoding="utf-8")
readme = (ROOT / "README.md").read_text(encoding="utf-8")
saved = (ROOT / "portfolio_xray_saved.py").read_text(encoding="utf-8")
groups = (ROOT / "custom_watchlists.py").read_text(encoding="utf-8")

assert "page_title='Stock Intelligence Toolkit'" in app
assert 'content: "Stock Intelligence Toolkit"' in nav
assert '"Stock Intelligence Toolkit sections"' in nav
assert "name: Stock Intelligence Toolkit - Regression Email Alerts" in workflow
assert readme.startswith("# Stock Intelligence Toolkit\n")
assert "https://stock-intelligence-toolkit.streamlit.app/" in readme
# Keep persisted browser data available across the branding update.
assert 'stock_intelligence_saved_portfolios_v1' in saved
assert 'stock_intelligence_custom_watchlists_v1' in groups
print("PASS: brand and persistent storage compatibility")
