"""Apply ETF full-holdings, compact spacing, metrics and Gemini UI updates.

Run from StockIntelligenceDashboard with the extracted ZIP contents in the
project root: .\\.venv\\Scripts\\python.exe install_update.py

All edits are preflighted and backed up before any file is changed. No secrets,
GitHub scanner files, saved watchlists or scan result directories are touched.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def change_theme(old: str) -> str:
    marker = '# si_compact_top_spacing_20261120'
    if marker in old:
        return old
    tree = ast.parse(old)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'apply_dashboard_theme']
    if len(funcs) != 1:
        raise RuntimeError('dashboard_theme.py: could not find apply_dashboard_theme')
    lines = old.splitlines(keepends=True)
    insertion = '''\n    # si_compact_top_spacing_20261120
    # Reduce unused space beneath Streamlit native top navigation.
    st.markdown("""<style>
    [data-testid="stMainBlockContainer"], .stMainBlockContainer, .block-container {
        padding-top: 1.8rem !important;
    }
    [data-testid="stAppViewBlockContainer"] {
        padding-top: 0.6rem !important;
    }
    </style>""", unsafe_allow_html=True)
'''
    lines.insert(funcs[0].end_lineno, insertion)
    new = ''.join(lines)
    ast.parse(new)
    return new


def change_stock(old: str) -> str:
    new = old
    # Broaden the entire financial-metrics panel and extend the scrollable table.
    pat = r'peers_col\s*,\s*metrics_col\s*=\s*st\.columns\(\s*(?:2|\[[^\]]+\])\s*\)'
    new, count = re.subn(pat, 'peers_col, metrics_col = st.columns([0.80, 1.45])', new, count=1)
    if not count and 'st.columns([0.80, 1.45])' not in new:
        raise RuntimeError('Stock Intelligence: competitor/metrics columns were not found')
    # Alter ONLY embedded metric table iframe, not other charts.
    pat = r'(components\.html\(\s*table_html\s*,\s*height\s*=\s*)\d+'
    new, count = re.subn(pat, r'\g<1>570', new, count=1)
    if not count and not re.search(r'components\.html\(\s*table_html\s*,\s*height\s*=\s*570', new):
        raise RuntimeError('Stock Intelligence: financial metrics table size was not found')
    ast.parse(new)
    return new


def change_sentiment(old: str) -> str:
    marker = 'si_retry_gemini_grouping_20261120'
    if marker in old:
        return old
    # Optional only. Previously cached errors may survive until refreshed.
    target = '                st.code(group_error)'
    if target not in old:
        raise RuntimeError('News Sentiment: cannot locate Gemini Technical detail area')
    addition = '''\n            # si_retry_gemini_grouping_20261120
            if st.button('Retry Gemini event grouping', key=f'si_gemini_retry_{symbol}'):
                from news_ai_shared import _events_cached
                _events_cached.clear()
                st.rerun()'''
    new = old.replace(target, target + addition, 1)
    ast.parse(new)
    return new


def main():
    files = {
        'regression_scanner/app.py': ROOT / 'regression_scanner' / 'app.py',
        'regression_scanner/scanner.py': ROOT / 'regression_scanner' / 'scanner.py',
        'etf_full_holdings.py': ROOT / 'etf_full_holdings.py',
        'ai_events.py': ROOT / 'ai_events.py',
        'dashboard_theme.py': ROOT / 'dashboard_theme.py',
        'pages/0_Stock_Intelligence.py': ROOT / 'pages' / '0_Stock_Intelligence.py',
        'pages/2_News_Sentiment.py': ROOT / 'pages' / '2_News_Sentiment.py',
    }
    # The two source replacements are staged under update_assets, not placed in
    # the project directly; this avoids accidental partial installs.
    source_files = {
        'regression_scanner/app.py': ROOT / 'update_assets' / 'regression_scanner' / 'app.py',
        'regression_scanner/scanner.py': ROOT / 'update_assets' / 'regression_scanner' / 'scanner.py',
        'etf_full_holdings.py': ROOT / 'update_assets' / 'etf_full_holdings.py',
        'ai_events.py': ROOT / 'update_assets' / 'ai_events.py',
    }
    missing = [name for name, path in files.items() if name not in source_files and not path.is_file()]
    missing.extend(name + ' (update package)' for name, path in source_files.items() if not path.is_file())
    if missing:
        raise SystemExit('UPDATE NOT APPLIED; missing files:\n  ' + '\n  '.join(missing))
    try:
        changes = []
        for name, src in source_files.items():
            p = files[name]
            old = p.read_text(encoding='utf-8-sig') if p.exists() else None
            updated = src.read_text(encoding='utf-8-sig')
            ast.parse(updated, filename=name)
            if old != updated:
                changes.append((name, p, old, updated))
        for name, fn in (
            ('dashboard_theme.py', change_theme),
            ('pages/0_Stock_Intelligence.py', change_stock),
            ('pages/2_News_Sentiment.py', change_sentiment),
        ):
            p = files[name]
            old = p.read_text(encoding='utf-8-sig')
            updated = fn(old)
            if old != updated:
                changes.append((name, p, old, updated))
        # Verify new scanner app invokes exactly the correct scanner module.
        scanner_app = next((new for name, _, _, new in changes if name == 'regression_scanner/app.py'),
                           files['regression_scanner/app.py'].read_text(encoding='utf-8-sig'))
        scanner = next((new for name, _, _, new in changes if name == 'regression_scanner/scanner.py'),
                       files['regression_scanner/scanner.py'].read_text(encoding='utf-8-sig'))
        if 'from regression_scanner.scanner import ScanSettings' not in scanner_app:
            raise RuntimeError('ETF regression scanner app did not load the qualified scanner import')
        if 'record_all_zscores: bool = False' not in scanner:
            raise RuntimeError('ETF regression engine does not have all-score recording')
    except (RuntimeError, OSError, SyntaxError, UnicodeError) as exc:
        raise SystemExit(f'UPDATE NOT APPLIED: {exc}')
    if not changes:
        print('Already updated. Nothing changed.')
        return
    backup = ROOT / '.ui_finishing_touch_backups' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup.mkdir(parents=True, exist_ok=False)
    for name, path, old, _new in changes:
        if old is not None:
            dest = backup / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(old, encoding='utf-8')
    for name, path, _old, new in changes:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new, encoding='utf-8')
        print('Updated:', name)
    print('Backups:', backup)
    print('Note: Real Gemini API connectivity and ETF data availability need testing in Streamlit.')
    print('Restart Streamlit: .\\.venv\\Scripts\\python.exe -m streamlit run app.py')


if __name__ == '__main__':
    main()
