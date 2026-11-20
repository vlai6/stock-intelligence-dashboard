"""Patch the installed four-page Stock Intelligence dashboard without replacing its modules.

Run from the project root: python apply_compact_ui_update.py
Backups are created before writes. The patch refuses unknown source layouts.
"""
from __future__ import annotations

import ast
import datetime
from pathlib import Path
import re
import shutil
import sys

ROOT = Path.cwd()
EXPECTED = {
    'regression_scanner/app.py': 'Regression Scanner',
    'pages/0_Stock_Intelligence.py': 'Stock Intelligence',
    'pages/2_News_Sentiment.py': 'News Sentiment',
    'pages/1_News_Screen.py': 'News Screen',
}


def replace_once(s: str, old: str, new: str, context: str) -> str:
    n = s.count(old)
    if n != 1:
        raise ValueError(f'{context}: expected one matching block; found {n}. No files were modified.')
    return s.replace(old, new, 1)


def update_scanner(s: str) -> str:
    if 'Stocks (N)' in s and 'Advanced filters & scan assumptions' not in s:
        return s
    start_marker = '    # One compact settings row instead of a full-height sidebar.\n'
    end_marker = '    length = regression_sessions(years)\n'
    if s.count(start_marker) != 1 or s.count(end_marker) != 1:
        raise ValueError('Scanner control layout has changed; refusing automatic edit.')
    start = s.index(start_marker)
    end = s.index(end_marker, start)
    replacement = '''    # Keep scan inputs in one row; zero maximum means no upper cap.\n    # Custom ticker scans remain supported by the engine but not the page UI.\n    if st.session_state.get("scan_scope") not in (TOP_N_SCOPE, MAX_SCOPE):\n        st.session_state["scan_scope"] = TOP_N_SCOPE\n    scope_col, n_col, min_col, max_col, years_col, action_col = st.columns(\n        [2.3, 1.05, 1.2, 1.2, 0.95, 1.15], vertical_alignment="bottom", gap="small"\n    )\n    with scope_col:\n        scope = st.selectbox(\n            "Universe", (TOP_N_SCOPE, MAX_SCOPE),\n            format_func=lambda option: {\n                TOP_N_SCOPE: "Top N Stocks by Market Cap",\n                MAX_SCOPE: "All available",\n            }[option],\n            key="scan_scope",\n            help="Scan the largest N stocks within the market-cap range, or attempt all available stocks.",\n        )\n    with n_col:\n        top_n = st.number_input(\n            "Stocks (N)", min_value=1, value=100, step=1,\n            disabled=(scope != TOP_N_SCOPE),\n            help="Number of the largest eligible companies to attempt, not a guaranteed result count.",\n        )\n    with min_col:\n        min_cap = st.number_input(\n            "Min cap ($B)", min_value=0.0, value=50.0, step=1.0, format="%.1f",\n            help="Minimum market cap in billions of USD.",\n        )\n    with max_col:\n        max_input = st.number_input(\n            "Max cap ($B)", min_value=0.0, value=0.0, step=1.0, format="%.1f",\n            help="Optional upper limit in billions of USD. Set 0 for no maximum; otherwise it must exceed Min cap.",\n        )\n    with years_col:\n        years = st.number_input(\n            "Years", min_value=0.5, max_value=30.0, value=10.0, step=0.1, format="%.2f",\n            help="Regression lookback in years; approximately 250 trading sessions per year.",\n        )\n    with action_col:\n        launch = st.button(\n            "Run Scan", type="primary", use_container_width=True, key="run_scan_main",\n            help="Scan the selected universe using completed daily closes.",\n        )\n    custom = ""  # The custom symbol control is deliberately removed.\n    max_cap = float(max_input) if max_input > 0 else None\n'''
    s=s[:start]+replacement+s[end:]
    # Preserve original engine and validation: max<=min causes existing ValueError.
    return s


def update_stock(s: str) -> str:
    if 'si_stock_loading_bar' in s:
        return s
    s=replace_once(s,
        '    try:\n        with st.spinner("Loading stock data..."):\n            data, info = get_stock(symbol)\n',
        '    try:\n        # A real progress indicator is visible during potentially slow Yahoo and peer requests.\n        si_stock_loading_bar = st.progress(5, text=f"Loading {symbol} stock prices and company data…")\n        with st.spinner("Loading stock data..."):\n            data, info = get_stock(symbol)\n        si_stock_loading_bar.progress(45, text="Stock data loaded · finding comparable companies…")\n',
        'Stock Intelligence stock load')
    s=replace_once(s,
        '        selected = []\n\n        # SECTION 1 — PRIMARY STOCK (FULL WIDTH)',
        '        si_stock_loading_bar.progress(100, text="Stock and competitor data ready")\n        si_stock_loading_bar.empty()\n        selected = []\n\n        # SECTION 1 — PRIMARY STOCK (FULL WIDTH)',
        'Stock Intelligence peer load')
    return s


def update_sentiment(s: str) -> str:
    if 'si-compact-headlines' in s:
        return s
    # Keep the same headline filter, article ordering and safe URL check.
    marker='visible=frame if sentiment_filter in (None,\'All\') else frame[frame[\'Sentiment\']==sentiment_filter]\n'
    if s.count(marker)!=1:
        raise ValueError('News Sentiment headline section changed; refusing edit.')
    start=s.index(marker)+len(marker)
    if s.count('if visible.empty:\n',start)!=1:
        raise ValueError('Cannot safely locate the end of Recent Headlines.')
    end=s.index('if visible.empty:\n',start)
    s=s[:start]+'''# One compact rendered block avoids a full Streamlit divider after every headline.\nimport html as _si_html\n_compact_rows = []\nfor _, item in visible.head(max_rows).iterrows():\n    dt = pd.to_datetime(item.get('Date'), utc=True, errors='coerce')\n    date_str = dt.tz_convert(MARKET_TZ).strftime('%d %b %Y') if pd.notna(dt) else 'Date unavailable'\n    url = str(item.get('Link') or '').strip()\n    parts = urlsplit(url)\n    safe_url = parts.scheme in ('http', 'https') and bool(parts.netloc)\n    heading = _si_html.escape(str(item.get('Title', '')))\n    title_html = (f'<a href="{_si_html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{heading}</a>'\n                  if safe_url else f'<span>{heading}</span>')\n    meta = ' · '.join((date_str, str(item.get('Source') or 'Unknown'),\n                       str(item.get('Sentiment') or 'Unavailable')))\n    _compact_rows.append(\n        '<div class="si-compact-row"><div class="si-compact-title">' + title_html + '</div>'\n        '<div class="si-compact-meta">' + _si_html.escape(meta) + '</div></div>'\n    )\nif _compact_rows:\n    st.markdown(\n        '<style>'\n        '.si-compact-headlines{border:1px solid #18314B;border-radius:10px;overflow:hidden}'\n        '.si-compact-row{padding:9px 14px;border-bottom:1px solid #142739;line-height:1.35}'\n        '.si-compact-row:last-child{border-bottom:0}'\n        '.si-compact-title{font-size:.91rem;font-weight:550;margin-bottom:3px}'\n        '.si-compact-title a{color:#8DD3FF;text-decoration:none}'\n        '.si-compact-title a:hover{text-decoration:underline;color:#CBEBFF}'\n        '.si-compact-meta{font-size:.76rem;color:#91A9C0}'\n        '</style><div class="si-compact-headlines">' + ''.join(_compact_rows) + '</div>',\n        unsafe_allow_html=True,\n    )\n''' +s[end:]
    return s


def update_news(s: str) -> str:
    if 'si_news_loading_bar' in s and 'automatic_stock_groups(' not in s:
        return s
    # Remove per-stock grouping CSS and filter widgets, retaining card-height rules.
    start_marker='/* Small, inline AI group filters directly below the company name */'
    if start_marker in s:
        start=s.index(start_marker)
        end=s.index('</style>',start)
        s=s[:start]+'.ns-card {min-height:425px;}\n\n'+s[end:]
    # Remove unused grouping code; keep automatic sentiment through FinBERT.
    start_marker='# --- Compact Gemini event filters for each stock\'s 7-day, name-matched headlines ---\n'
    if start_marker in s:
        a=s.index(start_marker)
        b=s.index('def automatic_stock_scan(',a)
        s=s[:a]+s[b:]
    a=s.find('def automatic_stock_groups(symbol, records):\n')
    if a>=0:
        b=s.index('def make_status(',a)
        s=s[:a]+s[b:]
    s=replace_once(s,
        'def make_card(symbol: str, quote: dict, items: list[dict], scan: dict | None, first: bool = False, grouping=None) -> str:',
        'def make_card(symbol: str, quote: dict, items: list[dict], scan: dict | None, first: bool = False) -> str:',
        'News Screen card signature')
    s=replace_once(s,'    event_html, article_groups=compact_event_ui(symbol, *(grouping or (None,None)))\n','',
                   'News Screen event HTML')
    s=replace_once(s,'''        event_group=article_groups.get(str(item.get('title','')).strip().casefold())\n        event_class=f' ns-event-{event_group}' if event_group is not None else ''\n''','', 'News Screen event classes')
    s=s.replace('f\'<a class="ns-article{event_class}" href=', 'f\'<a class="ns-article" href=')
    s=s.replace('f\'<div class="ns-article{event_class}">{inside}</div>\'','f\'<div class="ns-article">{inside}</div>\'')
    s=replace_once(s,
        'f\'<div><div class="ns-symbol">{safe_symbol}</div><div class="ns-company">{name}</div>{event_html}</div>\'',
        'f\'<div><div class="ns-symbol">{safe_symbol}</div><div class="ns-company">{name}</div></div>\'',
        'News Screen card title')
    s=replace_once(s,
        '''with st.spinner("Loading prices and latest headlines..."):\n    quotes = fetch_quotes(tuple(watchlist))\n    news_by_symbol = {symbol: fetch_news(symbol) for symbol in watchlist}\n    # Cap is optional, so Yahoo's throttling doesn't hide prices or news.\n    for symbol in watchlist:\n        if quotes.get(symbol, {}).get("price") is not None:\n            quotes[symbol]["cap"] = fetch_market_cap(symbol)\n\n# Automatic FinBERT labels on each loaded headline snapshot (cached; no scan button).\nfor _symbol in watchlist:\n    st.session_state['ns_scans'][_symbol] = automatic_stock_scan(_symbol, news_by_symbol.get(_symbol,[]))\n\n# Only grouped, already-filtered company headlines are sent to Gemini.\n# The AI helper has a 6-hour cache to avoid repeating API requests on reruns.\nstock_groups={_symbol:automatic_stock_groups(_symbol,news_by_symbol.get(_symbol,[]))\n              for _symbol in watchlist}\n''',
        '''# Show visible progress while loading each ticker and scoring its headlines.\nsi_news_loading_bar = st.progress(5, text="Loading watchlist prices…")\nquotes = fetch_quotes(tuple(watchlist))\nsi_news_loading_bar.progress(20, text="Prices loaded · retrieving company headlines…")\nnews_by_symbol = {}\nfor _i, _symbol in enumerate(watchlist, 1):\n    news_by_symbol[_symbol] = fetch_news(_symbol)\n    si_news_loading_bar.progress(20 + int(45 * _i / len(watchlist)),\n                                 text=f"Checking headlines: {_symbol} ({_i}/{len(watchlist)})")\n# Market capitalization is optional; quote/news failures remain isolated by ticker.\nfor _symbol in watchlist:\n    if quotes.get(_symbol, {}).get("price") is not None:\n        quotes[_symbol]["cap"] = fetch_market_cap(_symbol)\nsi_news_loading_bar.progress(70, text="Analyzing headlines with FinBERT…")\n# Automatic FinBERT scan, without a manual scan button or per-stock Gemini calls.\nfor _i, _symbol in enumerate(watchlist, 1):\n    st.session_state['ns_scans'][_symbol] = automatic_stock_scan(_symbol, news_by_symbol.get(_symbol, []))\n    si_news_loading_bar.progress(70 + int(30 * _i / len(watchlist)),\n                                 text=f"FinBERT: {_symbol} ({_i}/{len(watchlist)})")\nsi_news_loading_bar.empty()\n''',
        'News Screen load and scan')
    s=replace_once(s,'''        first=(i == 0),\n        grouping=stock_groups.get(symbol),\n''','''        first=(i == 0),\n''', 'News Screen make_card call')
    return s


def main() -> None:
    if not (ROOT / 'app.py').is_file():
        raise RuntimeError('Run this script in StockIntelligenceDashboard beside app.py.')
    missing=[name for name in EXPECTED if not (ROOT / name).is_file()]
    if missing:
        raise RuntimeError('Missing expected four-page project files: '+', '.join(missing))
    originals={name:(ROOT/name).read_text(encoding='utf-8-sig') for name in EXPECTED}
    transformers={
        'regression_scanner/app.py': update_scanner,
        'pages/0_Stock_Intelligence.py':update_stock,
        'pages/2_News_Sentiment.py':update_sentiment,
        'pages/1_News_Screen.py':update_news,
    }
    updated={}
    for name, body in originals.items():
        new=transformers[name](body)
        ast.parse(new, filename=name)
        updated[name]=new
    changes=[name for name in EXPECTED if originals[name]!=updated[name]]
    if not changes:
        print('Already updated; no changes necessary.')
        return
    now=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir=ROOT/'.ui_compact_backups'/now
    for name in changes:
        dest=backup_dir/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,dest)
    try:
        for name in changes:
            (ROOT/name).write_text(updated[name],encoding='utf-8')
    except Exception:
        for name in changes:
            shutil.copy2(backup_dir/name,ROOT/name)
        raise
    print('Updated '+', '.join(changes))
    print('Backups: '+str(backup_dir))
    print('Restart Streamlit, inspect all four pages, then commit the changed files.')

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('UPDATE NOT APPLIED: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
