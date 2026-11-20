"""Install automatic emailed-crossings watchlist + Show σ into General News Screen.

Run from StockIntelligenceDashboard (beside app.py). Safe for both the older
2-control and newer 4-control named-watchlist versions. Does not touch the
scanner calculation engine, workflow, navigation, other Streamlit pages, or
browser-saved user watchlists.
"""
from __future__ import annotations

import ast
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
TARGET = ROOT / "pages" / "1_News_Screen.py"
HELPER = ROOT / "scanner_email_watchlist.py"
THIS_DIR = Path(__file__).resolve().parent
SOURCE_HELPER = THIS_DIR / "scanner_email_watchlist.py"
MARKER = "# si_weekday_emailed_alerts_v1"
BACKUP_ROOT = ROOT / ".ui_email_alert_backups"


def read_file(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    return raw.decode("utf-8")


def swap_once(src: str, old: str, new: str, label: str) -> str:
    count = src.count(old)
    if count != 1:
        raise ValueError(f"Expected exactly one {label}; found {count}. No files changed.")
    return src.replace(old, new, 1)


def update_page(src: str) -> str:
    if MARKER in src:
        return src
    if "SAVED_LISTS_KEY =" not in src or "mark_watchlist_dirty()" not in src:
        raise ValueError("Cannot identify the named-watchlist version of General News Screen.")
    src = swap_once(
        src,
        "from dashboard_theme import apply_dashboard_theme, render_page_header",
        "from dashboard_theme import apply_dashboard_theme, render_page_header\n"
        "from scanner_email_watchlist import (AUTO_LIST_NAME, load_email_alerts, "
        "saved_regression_zscores, sigma_label)",
        "shared theme import",
    )
    src = swap_once(
        src,
        "</style>\n\"\"\", unsafe_allow_html=True)",
        ".ns-sigma {font-size:10px;color:#81BEDF;margin:5px 0 0;white-space:nowrap;}\n"
        ".ns-auto-pills {display:flex;gap:7px;flex-wrap:wrap;align-items:center;padding:9px 0;}\n"
        ".ns-auto-pill {border:1px solid #244461;background:#101F30;border-radius:7px;"
        "padding:7px 10px;color:#9FD3F6;font-size:11px;}\n"
        "</style>\n\"\"\", unsafe_allow_html=True)",
        "News Screen CSS ending",
    )
    # Append z-score under company name, without changing the source of data.
    src = swap_once(
        src,
        "def make_card(symbol: str, quote: dict, items: list[dict], scan: dict | None, first: bool = False) -> str:",
        "def make_card(symbol: str, quote: dict, items: list[dict], scan: dict | None, first: bool = False, sigma_text: str = '') -> str:",
        "stock card function signature",
    )
    src = swap_once(
        src,
        '    articles_html = "".join(article_rows)\n    return (',
        '    articles_html = "".join(article_rows)\n'
        '    sigma_html = (f\'<div class="ns-sigma">{html.escape(sigma_text)}</div>\' if sigma_text else "")\n'
        '    return (',
        "stock card contents",
    )
    src = swap_once(
        src,
        'f\'<div><div class="ns-symbol">{safe_symbol}</div><div class="ns-company">{name}</div></div>\'',
        'f\'<div><div class="ns-symbol">{safe_symbol}</div><div class="ns-company">{name}</div>{sigma_html}</div>\'',
        "stock card title and company",
    )
    src = swap_once(
        src,
        "                          'lists':st.session_state['ns_lists']}, separators=(',',':'))",
        "                          'lists':{n:v for n,v in st.session_state['ns_lists'].items() "
        "if n != AUTO_LIST_NAME}}, separators=(',',':'))",
        "browser save payload",
    )
    # Setup the virtual, read-only list after the browser's local lists have been restored.
    src = swap_once(
        src,
        "st.session_state.setdefault('ns_scans',{})",
        "# si_weekday_emailed_alerts_v1\n"
        "email_snapshot = load_email_alerts()  # Cached GitHub read, 5-minute TTL\n"
        "if not email_snapshot.error:\n"
        "    st.session_state['ns_lists'][AUTO_LIST_NAME] = list(email_snapshot.symbols)\n"
        "else:\n"
        "    st.session_state['ns_lists'].setdefault(AUTO_LIST_NAME, [])\n"
        "if st.session_state['ns_active_list'] == AUTO_LIST_NAME:\n"
        "    st.session_state['ns_watchlist'] = list(st.session_state['ns_lists'][AUTO_LIST_NAME])\n"
        "st.session_state.setdefault('ns_scans',{})",
        "automatic list initialization",
    )
    # Do not allow automatic list to count against the 12 user-created lists.
    src = src.replace(
        "len(st.session_state['ns_lists']) >= 12",
        "len([n for n in st.session_state['ns_lists'] if n != AUTO_LIST_NAME]) >= 12",
    )
    # Prevent deleting a system-generated list through Manage watchlists.
    src = re.sub(
        r"st\.button\(('Delete selected watchlist'),key='ns_delete_named_list'\)",
        r"st.button(\1,key='ns_delete_named_list', disabled=(st.session_state['ns_active_list'] == AUTO_LIST_NAME))",
        src,
    )
    src = re.sub(
        r'st\.button\(("Delete selected watchlist"), key="ns_delete_named_list", use_container_width=True\)',
        r'st.button(\1, key="ns_delete_named_list", use_container_width=True, disabled=(st.session_state["ns_active_list"] == AUTO_LIST_NAME))',
        src,
    )
    # v3 layout: the Add ticker form lives in the four-controls row.
    src = src.replace(
        'added = st.form_submit_button("Add stock", type="primary", use_container_width=True)',
        'added = st.form_submit_button("Add stock", type="primary", use_container_width=True, '
        'disabled=(st.session_state["ns_active_list"] == AUTO_LIST_NAME))',
    )
    # Do not overwrite manually saved lists when switching out of the auto list.
    old = "st.session_state['ns_lists'][st.session_state['ns_active_list']] = list(st.session_state['ns_watchlist'])"
    src = src.replace(old,
        "if st.session_state['ns_active_list'] != AUTO_LIST_NAME:\n"
        "        " + old,
    )
    # Place alert provenance just below the selector, before the watchlist divider.
    src = swap_once(
        src,
        'st.markdown(\'<div class="ns-toprule"></div>\', unsafe_allow_html=True)',
        'if st.session_state["ns_active_list"] == AUTO_LIST_NAME:\n    if email_snapshot.error:\n        st.warning("Automatic scanner watchlist unavailable: " + email_snapshot.error)\n    elif email_snapshot.latest_email_date:\n        st.caption("From successfully emailed scanner crossings on "\n                   f"{email_snapshot.latest_email_time} · "\n                   f"{len(email_snapshot.symbols)} unique stocks. "\n                   "Auto-sync checks GitHub about every 5 minutes when this page runs.")\n    else:\n        st.info("No sent crossing alerts have been recorded yet. The list will populate after the first successful alert email.")\nst.markdown(\'<div class="ns-toprule"></div>\', unsafe_allow_html=True)',
        "watchlist divider",
    )
    # Render auto ticker chips as a compact wrap (no Remove buttons), and
    # leave the existing regular-watchlist UI alone under else.
    start = re.search(r"^chip_sizes = .*?$", src, flags=re.M)
    end = re.search(r"^control_left, control_right = st\.columns\(\[3\.8, 1\.2\], vertical_alignment=\"center\"\)", src, flags=re.M)
    if start is None or end is None or end.start() <= start.start():
        raise ValueError("Could not locate watchlist chip layout (safe abort).")
    old = src[start.start():end.start()].rstrip("\n")
    auto_markup = (
        "if st.session_state['ns_active_list'] == AUTO_LIST_NAME:\n"
        "    st.markdown('<div class=\"ns-section-label\">WATCHLIST · AUTOMATIC</div>', unsafe_allow_html=True)\n"
        "    pill_html = ''.join('<span class=\"ns-auto-pill\">' + html.escape(s) + '</span>' for s in watchlist)\n"
        "    st.markdown('<div class=\"ns-auto-pills\">' + pill_html + '</div>', unsafe_allow_html=True)\n"
        "else:\n"
        + "\n".join("    " + line if line else "" for line in old.split("\n")) + "\n\n"
    )
    src = src[:start.start()] + auto_markup + src[end.start():]
    # Small checkbox beside refresh; not repeated on each card.
    src = swap_once(
        src,
        'control_left, control_right = st.columns([3.8, 1.2], vertical_alignment="center")',
        'control_left, sigma_control, control_right = st.columns([3.2, 0.65, 1.15], vertical_alignment="center")\n'
        'with sigma_control:\n'
        '    show_sigma = st.checkbox("Show σ", key="ns_show_sigma", '
        'help="Z-score: standard deviations below/above the scanner fitted price trend. '
        'Uses saved scanner results; N/A when unavailable.")',
        "news controls layout",
    )
    src = swap_once(
        src,
        "cards = [\n    make_card(",
        "sigma_scores = saved_regression_zscores(str(PROJECT_ROOT)) if show_sigma else {}\n"
        "cards = [\n    make_card(",
        "news card list",
    )
    src = swap_once(
        src,
        "        first=(i == 0),\n    )",
        "        first=(i == 0),\n"
        "        sigma_text=(sigma_label(symbol, sigma_scores, email_snapshot,\n"
        "                   st.session_state['ns_active_list'] == AUTO_LIST_NAME) if show_sigma else ''),\n"
        "    )",
        "news card rendering arguments",
    )
    # Add one-line data source note for displayed Z-scores.
    src = swap_once(
        src,
        'st.markdown(\'<div class="ns-grid">\' + "".join(cards) + \'</div>\', unsafe_allow_html=True)',
        'st.markdown(\'<div class="ns-grid">\' + "".join(cards) + \'</div>\', unsafe_allow_html=True)\nif show_sigma:\n    st.caption("σ = regression-channel Z-score from the last saved scanner run; "\n               "not daily-return volatility. Email history records only the crossed band. "\n               "An exact emailed-day Z-score is shown only if a matching scan report is available.")',
        "news card grid",
    )
    ast.parse(src, filename=str(TARGET))
    return src


def main() -> None:
    if not TARGET.exists() or not (ROOT / "app.py").is_file():
        raise ValueError("Run this installer from StockIntelligenceDashboard, beside app.py.")
    if not SOURCE_HELPER.is_file():
        raise ValueError("Keep scanner_email_watchlist.py beside the installer while running it.")
    original = read_file(TARGET)
    updated = update_page(original)
    if updated == original and HELPER.exists() and read_file(HELPER) == read_file(SOURCE_HELPER):
        print("Already installed. Nothing changed.")
        return
    if HELPER.exists() and read_file(HELPER) != read_file(SOURCE_HELPER):
        raise ValueError("scanner_email_watchlist.py already exists with different contents; not overwriting.")
    backup_dir = BACKUP_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_file = backup_dir / "pages" / "1_News_Screen.py"
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET, backup_file)
    if HELPER.exists():
        shutil.copy2(HELPER, backup_dir / "scanner_email_watchlist.py")
    try:
        TARGET.write_text(updated, encoding="utf-8", newline="\n")
        shutil.copy2(SOURCE_HELPER, HELPER)
    except Exception:
        shutil.copy2(backup_file, TARGET)
        if not (backup_dir / "scanner_email_watchlist.py").exists() and HELPER.exists():
            HELPER.unlink()
        raise
    print("SUCCESS: Added Show σ and read-only Weekday Scanner Alerts watchlist.")
    print("Original saved at", backup_file)
    print("Configure SCANNER_GITHUB_REPOSITORY in Streamlit secrets to enable sync.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, UnicodeError, SyntaxError) as error:
        print("UPDATE NOT APPLIED:", error, file=sys.stderr)
        raise SystemExit(1)
