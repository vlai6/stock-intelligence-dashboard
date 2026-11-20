"""Safe one-time migration: Stock Intelligence / News Sentiment / General News Screen.

Run from the existing project root: python install_three_pages.py
The installer reads YOUR current app.py and YOUR existing News Screen; it does
not overwrite analysis functions with an old snapshot.
"""
from __future__ import annotations

import ast
import datetime as dt
import re
import shutil
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'ui_assets'
APP = ROOT / 'app.py'
NEWS = ROOT / 'pages' / '1_News_Screen.py'
STOCK = ROOT / 'pages' / '0_Stock_Intelligence.py'
SENTIMENT = ROOT / 'pages' / '2_News_Sentiment.py'
THEME = ROOT / 'dashboard_theme.py'
CONFIG = ROOT / '.streamlit' / 'config.toml'
MAGIC = '# stock_intelligence_ui_router_v1'


class InstallProblem(Exception):
    pass


def load(path):
    return path.read_text(encoding='utf-8-sig')


def is_call(node, method):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'st'
            and node.func.attr == method)


def expr_call(node, method):
    return isinstance(node, ast.Expr) and is_call(node.value, method)


def lines_of(source, node):
    lines = source.splitlines(keepends=True)
    return ''.join(lines[node.lineno - 1: node.end_lineno])


def remove_regions(source, regions):
    """Remove original statement spans bottom-up, avoiding change to other code."""
    lines = source.splitlines(keepends=True)
    occupied = set()
    for start, stop, replacement in sorted(regions, key=lambda r: r[0], reverse=True):
        if any(i in occupied for i in range(start, stop + 1)):
            raise InstallProblem('Overlapping transformations detected; nothing changed.')
        occupied.update(range(start, stop + 1))
        lines[start - 1:stop] = [replacement] if replacement else []
    return ''.join(lines)


def import_root(source):
    """Ensure helper imports work from a script in pages/, not just at root."""
    code = (
        'import sys as _si_sys\n'
        'from pathlib import Path as _si_Path\n'
        '_si_project_root = str(_si_Path(__file__).resolve().parent.parent)\n'
        'if _si_project_root not in _si_sys.path:\n'
        '    _si_sys.path.insert(0, _si_project_root)\n\n'
    )
    if '_si_project_root' in source:
        return source
    # Avoid placing imports before a future import (or an initial docstring).
    tree = ast.parse(source)
    pos = 0
    for stmt in tree.body:
        if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str) and stmt == tree.body[0]):
            pos = stmt.end_lineno
        elif isinstance(stmt, ast.ImportFrom) and stmt.module == '__future__':
            pos = stmt.end_lineno
        else:
            break
    lines = source.splitlines(keepends=True)
    lines.insert(pos, code)
    return ''.join(lines)


def find_news_block(tree):
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for child in node.body[:5]:
            if expr_call(child, 'subheader') and child.value.args:
                arg = child.value.args[0]
                if isinstance(arg, ast.Constant) and arg.value in ('News & Sentiment', 'News and Sentiment'):
                    candidates.append(node)
                    break
    if len(candidates) != 1:
        raise InstallProblem(
            f'Expected exactly one News & Sentiment section; found {len(candidates)}. '
            'Your app.py was left untouched. Contact me with the current app.py.'
        )
    return candidates[0]


def inherited_helpers(source, tree):
    helpers = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
            'get_stock', 'todays_articles', 'get_competitor_sentiment_counts'
        }:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            helpers.append(''.join(source.splitlines(keepends=True)[start - 1:node.end_lineno]))
    return '\n\n'.join(helpers)


def build_stock_and_sentiment(original):
    tree = ast.parse(original)
    section = find_news_block(tree)
    entire_section = textwrap.dedent(lines_of(original, section)).rstrip() + '\n'
    # The new page header already has the title. Avoid a second heading.
    entire_section = re.sub(
        r'(?m)^\s{4}st\.subheader\(["\']News & Sentiment["\']\)\s*\n',
        '', entire_section, count=1,
    )

    helpers = inherited_helpers(original, tree)
    news_page = '''"""News Sentiment — extracted from the user's original dashboard on install."""
from __future__ import annotations
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import html
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import plotly.graph_objects as go

from ai_peers import recommend_peers
from advanced_metrics import historical_cagr, calculate_roic
from metric_explanations import EXPLANATIONS
from news_sentiment import fetch_stock_news
from finbert_sentiment import analyze_finbert
from ai_events import group_news_events
from gnews_history import update_gnews, load_gnews, score_unscored
from dashboard_theme import apply_dashboard_theme, style_blue_figure, render_page_header

load_dotenv(PROJECT_ROOT / '.env')
MARKET_NEWS_TZ = ZoneInfo('America/New_York')

'''
    news_page += helpers + '''

apply_dashboard_theme()
render_page_header('News Sentiment',
                   'FinBERT sentiment, competitor comparisons, and AI event grouping',
                   current='sentiment')

# Follow the stock selected on Stock Intelligence, and allow changes here too.
symbol = str(st.session_state.get('primary', 'NVDA')).strip().upper() or 'NVDA'
with st.form('news_sentiment_stock_picker'):
    ticker_col, submit_col = st.columns([4, 1], vertical_alignment='bottom')
    with ticker_col:
        requested_symbol = st.text_input('Stock ticker', value=symbol, max_chars=15)
    with submit_col:
        submitted_symbol = st.form_submit_button('Analyze stock', use_container_width=True)
if submitted_symbol:
    candidate = requested_symbol.strip().upper()
    if not candidate or not all(c.isalnum() or c in '.-^=' for c in candidate):
        st.error('Enter a valid stock ticker.')
        st.stop()
    st.session_state.primary = candidate
    st.session_state.loaded = True
    st.rerun()

@st.cache_data(ttl=3600, show_spinner=False)
def _news_company_info(ticker):
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}

info = _news_company_info(symbol)
# Some existing event-reaction calculations use the selected stock's price data.
# Keep it available after moving the original section to its own page.
try:
    data, _cached_info = get_stock(symbol)
except Exception:
    data = pd.DataFrame()
company_name = info.get('longName') or info.get('shortName') or symbol
description = info.get('longBusinessSummary', company_name)
peer_error = None
peers = []
# Reuse competitor selections from the dashboard when moving between pages.
previous_peers = st.session_state.get(f'peers_{symbol}', [])
if not isinstance(previous_peers, list):
    previous_peers = []
with st.expander('Competitors for sentiment comparison', expanded=False):
    peer_string = st.text_input(
        'Additional competitor tickers (comma-separated)',
        value=', '.join(previous_peers),
        key=f'sentiment_peer_names_{symbol}',
        help='Select Compare Competitors in the chart below to include these tickers.',
    )
selected = list(dict.fromkeys(
    t.strip().upper() for t in peer_string.split(',')
    if t.strip() and all(c.isalnum() or c in '.-^=' for c in t.strip())
    and t.strip().upper() != symbol
))[:10]

'''
    news_page += entire_section
    news_page = news_page.replace('st.plotly_chart(fig_sentiment, use_container_width=True)',
                                  'st.plotly_chart(style_blue_figure(fig_sentiment), use_container_width=True)')
    # Guard high cost if the extracted news section ever used selected on its own.
    compile(news_page, str(SENTIMENT), 'exec')

    changes = [(section.lineno, section.end_lineno,
                ' ' * section.col_offset + '# News Sentiment now lives on its dedicated page.\n')]
    title_found = False
    caption_found = False
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            continue
        call = stmt.value
        if is_call(call, 'set_page_config'):
            changes.append((stmt.lineno, stmt.end_lineno, ''))
        elif is_call(call, 'title') and call.args and isinstance(call.args[0], ast.Constant):
            if 'Stock Intelligence' in str(call.args[0].value):
                changes.append((stmt.lineno, stmt.end_lineno,
                                'render_page_header("Stock Intelligence", '
                                '"AI-powered stock research and competitor analysis", current="stock")\n'))
                title_found = True
        elif is_call(call, 'caption') and call.args and isinstance(call.args[0], ast.Constant):
            if str(call.args[0].value).strip() == 'AI-powered stock research and competitor analysis':
                changes.append((stmt.lineno, stmt.end_lineno, ''))
                caption_found = True
        elif is_call(call, 'page_link') and call.args and isinstance(call.args[0], ast.Constant):
            if str(call.args[0].value).replace('\\', '/') == 'pages/1_News_Screen.py':
                changes.append((stmt.lineno, stmt.end_lineno, ''))
    if not title_found:
        raise InstallProblem('Could not find the existing dashboard title; nothing changed.')

    stock = remove_regions(original, changes)
    stock = import_root(stock)
    if re.search(r'^from dashboard_theme import .*$', stock, re.M):
        def add_header_import(match):
            line = match.group(0)
            return line if 'render_page_header' in line else line.rstrip() + ', render_page_header'
        stock = re.sub(r'^from dashboard_theme import .*$', add_header_import, stock, count=1, flags=re.M)
    else:
        # Insert immediately before old title/header first use; imports need not sit at top.
        stock = 'from dashboard_theme import apply_dashboard_theme, render_page_header\n' + stock
    if 'apply_dashboard_theme()' not in stock:
        stock = stock.replace('render_page_header("Stock Intelligence",',
                              'apply_dashboard_theme()\nrender_page_header("Stock Intelligence",', 1)
    stock = stock.replace('font-family: Arial, sans-serif;',
                          "font-family: Inter, 'Segoe UI', Arial, sans-serif;")
    compile(stock, str(STOCK), 'exec')
    return stock, news_page


def build_general_news(original):
    tree = ast.parse(original)
    changes = []
    for stmt in tree.body:
        if expr_call(stmt, 'set_page_config'):
            changes.append((stmt.lineno, stmt.end_lineno, ''))
    result = remove_regions(original, changes)
    if 'from dashboard_theme import apply_dashboard_theme' in result:
        result = result.replace('from dashboard_theme import apply_dashboard_theme',
                                'from dashboard_theme import apply_dashboard_theme, render_page_header', 1)
    elif 'render_page_header' not in result:
        raise InstallProblem('Cannot find the shared theme import in pages/1_News_Screen.py.')
    # Replace the old, smaller gold/blue masthead; retain its scan action.
    begin = result.find('head_left, head_right = st.columns(')
    end = result.find("st.markdown('<div class=\"ns-toprule\"></div>', unsafe_allow_html=True)", begin)
    if begin < 0 or end < 0:
        raise InstallProblem('Cannot locate News Screen masthead; nothing changed.')
    header = '''render_page_header(
    'General News Screen',
    f'AI news agent · {len(watchlist)} stocks on your watchlist',
    current='general',
)
scan_left, scan_right = st.columns([4, 1], vertical_alignment='center')
with scan_right:
    scan_clicked = st.button('Scan headlines', type='primary',
                             use_container_width=True, key='ns_scan_button')

'''
    result = result[:begin] + header + result[end:]
    # Darken fixed background colors in standalone News Screen cards.
    for before, after in {
        '#0D1A29':'#081422', '#09131F':'#070F1B', '#0D1D2D':'#0A1726',
        '#1C3950':'#19344D', '#0B1725':'#071321',
    }.items():
        result = result.replace(before, after)
    compile(result, str(NEWS), 'exec')
    return result


def build_config(original, theme):
    theme_blocks = re.compile(r'(?ms)^\[theme(?:\.[^\]]+)?\]\s*\n.*?(?=^\[[^\]]+\]\s*$|\Z)')
    other = theme_blocks.sub('', original).strip()
    return (other + '\n\n' if other else '') + theme.strip() + '\n'


def router_source():
    return '''"""Stock Intelligence: navigation-only entrypoint for Streamlit Cloud."""
import streamlit as st

''' + MAGIC + '''
st.set_page_config(page_title='Stock Intelligence', page_icon='📊',
                   layout='wide', initial_sidebar_state='expanded')

page = st.navigation([
    st.Page('pages/0_Stock_Intelligence.py', title='Stock Intelligence', icon='📊', default=True),
    st.Page('pages/2_News_Sentiment.py', title='News Sentiment', icon='📈'),
    st.Page('pages/1_News_Screen.py', title='General News Screen', icon='📰'),
], position='sidebar')
page.run()
'''


def run():
    if not APP.is_file() or not NEWS.is_file():
        raise InstallProblem('Expected app.py and pages/1_News_Screen.py in the project. '
                             'Copy this installer to your project root and check the pages folder.')
    if not (ASSETS / 'dashboard_theme.py').is_file():
        raise InstallProblem('Missing ui_assets/dashboard_theme.py from the update ZIP.')
    if not (ASSETS / 'dark_navy_theme.toml').is_file():
        raise InstallProblem('Missing ui_assets/dark_navy_theme.toml from the update ZIP.')
    original_app = load(APP)
    if MAGIC in original_app:
        print('Already migrated. No files changed. To restore original files, use .ui_backups/.')
        return
    original_news = load(NEWS)
    if 'ns_watchlist' not in original_news or 'BROWSER_WATCHLIST_KEY' not in original_news:
        raise InstallProblem('Existing News Screen does not match the persistent-watchlist '
                             'version. Nothing changed. Please supply your current page file.')
    stock, sentiment = build_stock_and_sentiment(original_app)
    general = build_general_news(original_news)
    config_old = load(CONFIG) if CONFIG.exists() else ''
    config_new = build_config(config_old, load(ASSETS / 'dark_navy_theme.toml'))
    theme_new = load(ASSETS / 'dashboard_theme.py')
    # Validate all output files BEFORE touching the real project.
    for path, value in ((STOCK, stock), (SENTIMENT, sentiment), (NEWS, general),
                        (APP, router_source()), (THEME, theme_new)):
        compile(value, str(path), 'exec')
    if STOCK.exists() or SENTIMENT.exists():
        raise InstallProblem('One of the target page files already exists. No changes made: '
                             f'{STOCK.name} / {SENTIMENT.name}.')

    stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = ROOT / '.ui_backups' / stamp
    backup.mkdir(parents=True, exist_ok=False)
    for path in (APP, NEWS, THEME, CONFIG):
        if path.exists():
            relative = path.relative_to(ROOT)
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
    print(f'Backed up original files in: {backup}')

    gitignore = ROOT / '.gitignore'
    if gitignore.exists():
        value = load(gitignore)
        if '/.ui_backups/' not in value:
            gitignore.write_text(value.rstrip() + '\n\n# Local backups from Streamlit page migration\n/.ui_backups/\n', encoding='utf-8')
    else:
        gitignore.write_text('/.ui_backups/\n', encoding='utf-8')

    output = ((STOCK, stock), (SENTIMENT, sentiment), (NEWS, general),
              (APP, router_source()), (THEME, theme_new), (CONFIG, config_new))
    for path, value in output:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')
        print(f'Updated: {path.relative_to(ROOT)}')
    print('\nSUCCESS: Stock Intelligence / News Sentiment / General News Screen.')
    print('Restart with: python -m streamlit run app.py')
    print('Only after local verification, commit the new/modified files to GitHub.')


if __name__ == '__main__':
    try:
        run()
    except (InstallProblem, SyntaxError) as exc:
        print(f'NOT INSTALLED: {exc}', file=sys.stderr)
        sys.exit(1)
