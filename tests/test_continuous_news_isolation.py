"""Static regression checks for Streamlit continuous dashboard section isolation.

The News Screener used to call custom_watchlists._init() from every run.
When browser localStorage had not answered yet, that helper called st.stop(),
which aborted the *whole* dashboard before its lower sections were added.
These checks do not require a browser, Streamlit, or live market data.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
dashboard = (ROOT / "scroll_dashboard.py").read_text(encoding="utf-8")
news = (ROOT / "pages" / "1_News_Screen.py").read_text(encoding="utf-8")
saved_groups = (ROOT / "custom_watchlists.py").read_text(encoding="utf-8")

# Check syntax without importing Streamlit or invoking any API.
for name, source in [
    ("scroll_dashboard.py", dashboard),
    ("1_News_Screen.py", news),
    ("custom_watchlists.py", saved_groups),
]:
    ast.parse(source, filename=name)

assert "class BrowserGroupsPending(Exception):" in saved_groups
init_body = saved_groups.split("def _init():", 1)[1].split("\ndef ", 1)[0]
assert "raise BrowserGroupsPending()" in init_body
assert not re.search(r"(?m)^\s*st\.stop\(\s*\)", init_body)
assert "group_names = named_groups()" in news
assert re.search(
    r"except BrowserGroupsPending:\s*(?:#[^\n]*\n\s*)*st\.stop\(\s*\)",
    news,
)

# Continuous section compilation rewrites the News page's stop to the local
# section sentinel without halting subsequent pages.
assert 'raise _EndSection()' in dashboard
translated_news = re.sub(r"\bst\.stop\(\s*\)", "raise _EndSection()", news)
assert "except BrowserGroupsPending:" in translated_news
assert "raise _EndSection()" in translated_news
ast.parse(translated_news, filename="embedded_News_Screener.py")

# All navigation anchors are allocated before heavy News fetches begin.
assert dashboard.index("section_slots = {}") < dashboard.index(
    "with section_slots[slug].container():"
)
assert "for slug, label in SECTIONS:" in dashboard
assert "for slug, _label in SECTIONS:" in dashboard
assert "Loading section…" in dashboard
assert "@st.fragment" in dashboard
assert '"scanner": "regression_scanner/app.py"' in dashboard
assert '"sentiment": "pages/2_News_Sentiment.py"' in dashboard

print("PASS: News browser storage cannot terminate the continuous dashboard")
