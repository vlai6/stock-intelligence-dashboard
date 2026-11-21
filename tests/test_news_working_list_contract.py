"""Lightweight contracts for unsaved on-screen watchlists.

No Streamlit app or live market data is launched during these tests.
"""
from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1]
news = (ROOT / "pages/1_News_Screen.py").read_text(encoding="utf-8-sig")
custom = (ROOT / "custom_watchlists.py").read_text(encoding="utf-8-sig")
theme = (ROOT / "dashboard_theme.py").read_text(encoding="utf-8-sig")

# Confirm the view has a direct blank-list action, an editor and a snapshot
# save without modifying read-only scan/ETF selections.
for snippet in (
    '"Clear & add stocks"', '"Save displayed as list"', '"Edit displayed"',
    'WORKING_STOCK_LABEL = "Working List (Unsaved)"',
    "st.session_state[DRAFT_KEY] = []",
    "st.session_state[DRAFT_KEY] = watchlist.copy()",
    "'stocks': watchlist.copy()",
    "elif mode == WORKING_STOCK_LABEL:",
    "watchlist = render_working_list()",
):
    assert snippet in news, snippet
assert "load_email_alerts()" in news
assert "st.session_state['ns_pending_list_save']" in news

for snippet in (
    "def render_working_list()", "def save_displayed_watchlist(",
    "def parse_working_tickers(", "_queue_write()", "_init()",
    "if name in lists:", "DRAFT_KEY =",
):
    assert snippet in custom, snippet

# Exercise ticker parsing from the real production function without running
# any Streamlit UI or network calls.
module = ast.parse(custom)
parser = next(
    node for node in module.body
    if isinstance(node, ast.FunctionDef) and node.name == "parse_working_tickers"
)
namespace = {"re": re}
pattern = re.compile(r"^[A-Z0-9^][A-Z0-9.\\-^=]{0,14}$")
def validate(raw):
    t = str(raw or "").strip().upper()
    if t in ("BRK.B", "BF.B"):
        t = t.replace(".", "-")
    return t if pattern.fullmatch(t) else ""
namespace["valid_symbol"] = validate
exec(compile(ast.Module(body=[parser], type_ignores=[]), "custom_watchlists.py", "exec"), namespace)
parse = namespace["parse_working_tickers"]
assert parse("mu, nvda; BRK.B NVDA") == (["MU", "NVDA", "BRK-B"], [])
symbols, invalid = parse("AAPL, INVALID@@, MSFT")
assert symbols == ["AAPL", "MSFT"]
assert invalid == ["INVALID@@"]
assert parse("  ") == ([], [])

# Exact user-provided Pexels image identifier, dark fallback still exists.
assert "30596231/pexels-photo-30596231.jpeg" in theme
assert "background-color:var(--si-bg) !important;" in theme
print("PASS: immediate edit, save-current, safe presets, ticker parsing and Earth background")
