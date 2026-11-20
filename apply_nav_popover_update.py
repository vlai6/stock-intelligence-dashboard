"""Safe, idempotent four-page navigation + opaque Streamlit popover update.

Run from StockIntelligenceDashboard (next to app.py):
    .\\.venv\\Scripts\\python.exe apply_nav_popover_update.py

Only changes the router labels/order, shared theme labels and CSS,
and the Recent Sentiment page's visible name. Preserves all stock logic.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

ROOT = Path.cwd()
ROUTER = "app.py"
THEME = "dashboard_theme.py"
SENTIMENT = "pages/2_News_Sentiment.py"
FILES = (ROUTER, THEME, SENTIMENT)
BACKUPS = ".ui_nav_popover_backups/"
STYLE_MARKER = "/* SI opaque watchlist popovers v1 */"

# Match the actual four-page router without changing page filenames or content.
ROUTER_LIST_RE = re.compile(
    r"(?P<before>page\s*=\s*st\.navigation\(\[)"
    r"(?P<items>.*?)"
    r"(?P<after>\],\s*position\s*=\s*['\"]sidebar['\"]\))",
    re.DOTALL,
)
PAGE_RE = re.compile(
    r"st\.Page\(\s*['\"](?P<path>[^'\"]+)['\"]\s*,\s*"
    r"title\s*=\s*['\"](?P<title>[^'\"]+)['\"]\s*,\s*"
    r"icon\s*=\s*['\"](?P<icon>[^'\"]+)['\"]\s*"
    r"(?:,\s*default\s*=\s*(?:True|False))?\s*\)",
)
ORDER = [
    ("general", "General News Screen", "pages/1_News_Screen.py", "📰"),
    ("scanner", "Regression Scanner", "regression_scanner/app.py", "📉"),
    ("stock", "Stock Intelligence", "pages/0_Stock_Intelligence.py", "📊"),
    ("sentiment", "Recent Sentiment", "pages/2_News_Sentiment.py", "📈"),
]

OPAQUE_CSS = r"""
/* SI opaque watchlist popovers v1 */
/* Streamlit places st.popover bodies in a BaseWeb floating layer, outside
   their originating columns. Give both the floating layer and its inner
   panel fully opaque midnight-navy backgrounds so controls behind cannot
   show through the Add ticker / Manage watchlists dialogs. */
div[data-baseweb="popover"] {
  z-index: 10000 !important;
}
div[data-baseweb="popover"] > div,
div[data-baseweb="popover"] [data-testid="stPopoverBody"],
[data-testid="stPopoverBody"] {
  background: #0B1B2E !important;
  background-image: none !important;
  opacity: 1 !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  border: 1px solid #285075 !important;
  border-radius: 12px !important;
  box-shadow: 0 18px 48px rgba(0, 0, 0, .80) !important;
}
div[data-baseweb="popover"] [data-testid="stPopoverBody"] > div {
  background: #0B1B2E !important;
  opacity: 1 !important;
}
/* Inputs within popovers retain their own contrasting control surfaces. */
[data-testid="stPopoverBody"] [data-testid="stForm"] {
  background: #0D2238 !important;
  border-color: #244968 !important;
}
[data-testid="stPopoverBody"] [data-testid="stMarkdownContainer"] p,
[data-testid="stPopoverBody"] label {
  color: #E5F2FF !important;
}
"""


def decode_source(file: Path) -> str:
    content = file.read_bytes()
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16")
    if content.startswith(b"\xef\xbb\xbf"):
        return content.decode("utf-8-sig")
    return content.decode("utf-8")


def set_router(source: str) -> str:
    matches = list(ROUTER_LIST_RE.finditer(source))
    if len(matches) != 1:
        raise ValueError("Cannot uniquely locate Streamlit four-page navigation in app.py")
    match = matches[0]
    current = PAGE_RE.findall(match.group("items"))
    by_path = {path: (title, icon) for path, title, icon in current}
    expected = {row[2] for row in ORDER}
    if len(current) != 4 or set(by_path) != expected:
        raise ValueError(f"Unexpected router pages: {sorted(by_path)}. Refusing to change them.")
    # Preserve existing icons, but standardize labels and page order.
    rows = []
    for i, (_, title, path, _icon) in enumerate(ORDER):
        icon = by_path[path][1]
        rows.append(f"    st.Page({path!r}, title={title!r}, icon={icon!r}"
                    + (", default=True" if i == 0 else "") + "),")
    rewritten = "\n" + "\n".join(rows) + "\n"
    return (source[:match.start("items")] + rewritten + source[match.end("items"):])


def set_theme(source: str) -> str:
    marker = "PAGES = ("
    if source.count(marker) != 1:
        raise ValueError("Cannot locate the shared dashboard_theme.PAGES block")
    start = source.index(marker)
    end = source.find("\n)\n", start)
    if end == -1:
        raise ValueError("Cannot locate the end of the shared PAGES block")
    current = source[start:end + 2]
    if not all(row[2] in current for row in ORDER):
        raise ValueError("Theme page registry does not contain the four expected pages")
    pages = "PAGES = (\n" + "".join(
        f"    ({slug!r}, {title!r}, {path!r}, {icon!r}),\n"
        for slug, title, path, icon in ORDER
    ) + ")"
    source = source[:start] + pages + source[end + 2:]
    if STYLE_MARKER not in source:
        if source.count("</style>") != 1:
            raise ValueError("Cannot uniquely locate shared theme style block")
        source = source.replace("</style>", OPAQUE_CSS + "\n</style>", 1)
    return source


def set_sentiment(source: str) -> str:
    old = "render_page_header('News Sentiment',"
    new = "render_page_header('Recent Sentiment',"
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise ValueError("Could not find the Recent Sentiment page title")
    # Keep the visible stock selector consistent. Other message copy may remain.
    source = source.replace("'News Sentiment stock list'", "'Recent Sentiment stock list'")
    return source


def add_gitignore_ignore(source: str) -> str:
    if BACKUPS in source.splitlines():
        return source
    return source.rstrip("\r\n") + "\n\n# Backups from navigation and popover styling update\n" + BACKUPS + "\n"


def main() -> None:
    required = [ROOT / f for f in FILES]
    missing = [str(file) for file in required if not file.is_file()]
    if missing:
        raise ValueError("Run from the existing four-page StockIntelligenceDashboard folder. Missing: " + ", ".join(missing))

    original = {f: decode_source(ROOT / f) for f in FILES}
    modified = {
        ROUTER: set_router(original[ROUTER]),
        THEME: set_theme(original[THEME]),
        SENTIMENT: set_sentiment(original[SENTIMENT]),
    }
    # Work out all changes and check syntax before writing any file.
    gitignore = ROOT / ".gitignore"
    if gitignore.exists():
        original[".gitignore"] = decode_source(gitignore)
        modified[".gitignore"] = add_gitignore_ignore(original[".gitignore"])
    for name in FILES:
        ast.parse(modified[name], filename=name)

    changes = [name for name, text in modified.items() if text != original[name]]
    if not changes:
        print("Already updated. No files changed.")
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder = ROOT / BACKUPS / stamp
    for name in changes:
        backup = backup_folder / name
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, backup)
    try:
        for name in changes:
            (ROOT / name).write_text(modified[name], encoding="utf-8", newline="\n")
    except Exception:
        for name in changes:
            shutil.copy2(backup_folder / name, ROOT / name)
        raise
    print("SUCCESS: Updated sidebar navigation order, page labels and opaque popovers.")
    print("Modified:", ", ".join(changes))
    print("Backups:", backup_folder)
    print("Restart Streamlit to apply the new navigation and popover styling.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("UPDATE NOT APPLIED:", error, file=sys.stderr)
        raise SystemExit(1)
