"""Safely integrate the vetted scanner into the EXISTING four-page-capable router.

Unlike the supplied v1 integration, this script does NOT replace app.py or
turn a navigation router into a dashboard page. Run it only from the folder
containing Stock Intelligence's app.py, dashboard_theme.py, and pages/.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

ROOT = Path.cwd()
ASSETS = Path(__file__).resolve().parent / "integration_assets" / "regression_scanner"
DEST = ROOT / "regression_scanner"
SCANNER_ENTRY = DEST / "app.py"
APP = ROOT / "app.py"
THEME = ROOT / "dashboard_theme.py"
WATCHLIST = ROOT / "regression_watchlists.py"
REQS = ROOT / "requirements.txt"
IGNORE = ROOT / ".gitignore"
BACKUPS = ROOT / ".scanner_integration_backups"
MARKER = "# si_four_page_scanner_integration_v1"


def stop(message: str):
    raise SystemExit("STOP: " + message)


def read(path: Path) -> str:
    """Accept UTF-8, UTF-8 BOM, or BOM-marked UTF-16 (common on Windows).

    The modified files are written back as UTF-8 by the installer.
    """
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def checked_python(source: str, where: str) -> str:
    try:
        ast.parse(source, filename=where)
    except SyntaxError as exc:
        stop(f"{where} does not parse as Python: {exc}")
    return source


def patch_router(source: str) -> str:
    if "st.navigation(" not in source or "pages/0_Stock_Intelligence.py" not in source:
        stop("app.py is not the EXISTING three-page navigation router; no changes made")
    if "regression_scanner/app.py" in source:
        stop("Scanner is already registered in app.py; no changes made")
    anchor = re.compile(r'(?m)^(\s*)st\.Page\(\s*([\'\"])pages/2_News_Sentiment\.py\2')
    found = list(anchor.finditer(source))
    if len(found) != 1:
        stop("Could not locate the News Sentiment registration exactly once in app.py")
    match = found[0]
    indent = match.group(1)
    new_page = f"{indent}st.Page('regression_scanner/app.py', title='Regression Scanner', icon='📉'),\n"
    return checked_python(source[:match.start()] + new_page + source[match.start():], "patched app.py")


def patch_theme(source: str) -> str:
    if "def render_page_header(" not in source or "PAGES = (" not in source:
        stop("dashboard_theme.py is not the expected existing shared theme module")
    if "('scanner', 'Regression Scanner'" not in source:
        sentiment_anchor = re.compile(r'(?m)^(\s*)\(\s*([\'\"])sentiment\2\s*,')
        found = list(sentiment_anchor.finditer(source))
        if len(found) != 1:
            stop("Could not find the sentiment page in dashboard_theme.PAGES")
        m = found[0]
        source = source[:m.start()] + m.group(1) + "('scanner', 'Regression Scanner', 'regression_scanner/app.py', '📉'),\n" + source[m.start():]
    old = "buttons = st.columns(2, gap='small', vertical_alignment='center')"
    if old in source:
        source = source.replace(old, "buttons = st.columns(len(targets), gap='small', vertical_alignment='center')", 1)
    elif "buttons = st.columns(len(targets)" not in source:
        stop("Could not update the shared header to display three right-side buttons")
    # Name-specific legacy selectors omit the scanner header; the generic selector works.
    source = source.replace('.st-key-si_header_general {padding:', '.st-key-si_header_general,\n.st-key-si_header_scanner {padding:')
    source = source.replace('"Same background, font family, inputs, and controls for all three pages."', '"Same background, font family, inputs, and controls for all four pages."')
    return checked_python(source, "patched dashboard_theme.py")


def patch_scanner_page(source: str) -> str:
    old = ('# This page deliberately has NO sidebar. The parent app draws one shared top navbar.\n'
           'st.subheader("Regression Scanner")\n'
           'st.caption("US-listed equities · daily-close regression · automatic −3σ/−4σ screen · hover over settings and table headers for details")')
    new = ('# Integrated page: original scanner engine; shared UI only.\n'
           'apply_dashboard_theme()\n'
           'render_page_header("Regression Scanner", "U.S.-listed equities · daily-close regression · −3σ / −4σ screening", current="scanner")\n'
           'st.caption("Daily close data · hover over settings and table headings for definitions")')
    if source.count(old) != 1:
        stop("Scanner top-of-page anchor changed; cannot safely theme it")
    source = source.replace(old, new, 1)
    source = source.replace('import streamlit as st\n',
                            'import streamlit as st\nfrom dashboard_theme import apply_dashboard_theme, render_page_header, style_blue_figure\n', 1)
    old_chart = '            channel_figure(chart, ticker, visible_bands),\n'
    if source.count(old_chart) != 1:
        stop("Scanner chart anchor changed; refusing unsafe theme patch")
    source = source.replace(old_chart, '            style_blue_figure(channel_figure(chart, ticker, visible_bands)),\n', 1)
    source = source.replace('"Sidebar settings differ from this saved scan. Press **Run scan** to apply them."',
                            '"Settings above differ from this saved scan. Press **Run Scan** to apply them."')
    return checked_python(source, "patched regression_scanner/app.py")


def patch_watchlists(source: str) -> str:
    if "PROJECT / 'regression_scanner' / 'results' / 'latest_scan.csv'" in source:
        return source
    needle = "    paths = ([Path(explicit).expanduser()] if explicit else []) + [\n"
    if source.count(needle) != 1:
        # Older current project (before previous UI refinements) has no helper at all.
        # If there is a different helper, leave it intact instead of guessing.
        print("NOTICE: regression_watchlists.py uses a different layout; leaving it unchanged")
        return source
    replacement = (
        "    scanner_root = os.getenv('REGRESSION_SCANNER_DATA_DIR', '').strip()\n"
        "    paths = ([Path(explicit).expanduser()] if explicit else []) + (\n"
        "        [Path(scanner_root).expanduser() / 'results' / 'latest_scan.csv'] if scanner_root else []\n"
        "    ) + [\n"
        "        PROJECT / 'regression_scanner' / 'results' / 'latest_scan.csv',\n"
    )
    return checked_python(source.replace(needle, replacement, 1), "patched regression_watchlists.py")


def append_line(source: str, line: str) -> str:
    if line in [ln.strip() for ln in source.splitlines()]:
        return source
    return source.rstrip() + "\n" + line + "\n"


def build():
    for mandatory in (APP, THEME, ROOT / "pages" / "0_Stock_Intelligence.py", ROOT / "pages" / "2_News_Sentiment.py", ROOT / "pages" / "1_News_Screen.py"):
        if not mandatory.is_file():
            stop(f"Required existing project file missing: {mandatory.relative_to(ROOT)}")
    if not ASSETS.is_dir() or not (ASSETS / "app.py").is_file():
        stop("Missing integration_assets/regression_scanner folder; extract the entire package")
    if DEST.exists():
        stop("regression_scanner/ already exists. Check whether integration was done before; no changes made")
    if MARKER in read(APP):
        stop("This integration marker already exists in app.py; no changes made")

    originals = {p: read(p) for p in (APP, THEME)}
    if WATCHLIST.exists():
        originals[WATCHLIST] = read(WATCHLIST)
    if REQS.exists():
        originals[REQS] = read(REQS)
    else:
        print("NOTICE: requirements.txt not found; installer will create one containing the scanner-only dependency. Review before deployment.")
    if IGNORE.exists():
        originals[IGNORE] = read(IGNORE)

    patched = {
        APP: patch_router(originals[APP]) + "\n" + MARKER + "\n",
        THEME: patch_theme(originals[THEME]),
    }
    if WATCHLIST in originals:
        patched[WATCHLIST] = patch_watchlists(originals[WATCHLIST])
    patched[REQS] = append_line(originals.get(REQS, ""), "pandas_market_calendars>=5.0,<6.0")
    ignore_additions = (
        ".scanner_integration_backups/",
        "regression_scanner/.env",
        "regression_scanner/results/",
        "regression_scanner/state/",
        "regression_scanner/.cache/",
        "regression_scanner/scheduled_scans/",
        "regression_scanner/logs/",
    )
    ign = originals.get(IGNORE, "")
    for entry in ignore_additions:
        ign = append_line(ign, entry)
    patched[IGNORE] = ign
    scanner_page = patch_scanner_page(read(ASSETS / "app.py"))

    # Stage every modification before touching any existing file.
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_dir = BACKUPS / timestamp
    backup_dir.mkdir(parents=True, exist_ok=False)
    for path, value in originals.items():
        backup_file = backup_dir / path.relative_to(ROOT)
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        backup_file.write_text(value, encoding="utf-8")
    (backup_dir / "README.txt").write_text(
        "Backups of files before regression integration.\n"
        "To roll back, restore these files and delete regression_scanner/.\n",
        encoding="utf-8",
    )

    try:
        shutil.copytree(ASSETS, DEST)
        SCANNER_ENTRY.write_text(scanner_page, encoding="utf-8")
        for path, content in patched.items():
            path.write_text(content, encoding="utf-8")
    except Exception:
        for path, content in originals.items():
            path.write_text(content, encoding="utf-8")
        for newly_created in (REQS, IGNORE):
            if newly_created not in originals:
                newly_created.unlink(missing_ok=True)
        if DEST.exists():
            shutil.rmtree(DEST)
        raise

    print("SUCCESS: Integrated Regression Scanner as page #2 without replacing the router.")
    print("Navigation: Stock Intelligence / Regression Scanner / News Sentiment / General News Screen")
    print("Same near-black navy and blue theme applied to scanner cards and Plotly chart.")
    print("Backups:", backup_dir)
    if WATCHLIST not in originals:
        print("NOTE: The previous regression-watchlist refinements are not installed; install adapted preset UI later, not the older v3 CSV paths.")
    print("Next: pip install -r requirements.txt, then python -m streamlit run app.py")


if __name__ == "__main__":
    build()
