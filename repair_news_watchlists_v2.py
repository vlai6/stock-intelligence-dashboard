"""Repair General News Screen list switching, and ensure email-alert list is installed.

Safeguards: operates on existing project; backs up page & helper before changing;
never writes/deletes browser localStorage from Python; preserves all named lists;
never touches scanner math, other pages, GitHub workflow, or secrets.
"""
from __future__ import annotations

import ast
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
SRC_DIR = Path(__file__).resolve().parent
PAGE = ROOT / "pages" / "1_News_Screen.py"
HELPER = ROOT / "scanner_email_watchlist.py"
BACKUPS = ROOT / ".ui_watchlist_repair_backups"


def read(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


# This replaces *only* state restoration/persistence and list switch handling.
# The rest of the Streamlit page (news, charts, sentiment, card styles) remains untouched.
STATE_BLOCK = '''# si_weekday_emailed_alerts_v1
# --- Named watchlists (one authoritative mapping per browser session) ---
# ns_lists maps name -> tickers. ns_watchlist is a view of the active list only.
# List changes are committed through mark_watchlist_dirty(); switching never
# writes a possibly stale ns_watchlist back into the list being left.
import time as _ns_time
SAVED_LISTS_KEY = 'stock_intelligence_named_watchlists_v1'


def valid_saved_watchlist(raw: object) -> list[str] | None:
    if raw is None:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, list):
        return None
    cleaned = []
    for item in parsed:
        if isinstance(item, str):
            symbol = clean_ticker(item)
            if symbol and symbol not in cleaned:
                cleaned.append(symbol)
    return cleaned[:MAX_TICKERS]


def browser_saved_lists_read():
    # Do not overwrite any browser-saved lists until the read actually resolves.
    expression = (
        '(function(){try{return JSON.stringify({ok:true,'
        'modern:window.localStorage.getItem(' + json.dumps(SAVED_LISTS_KEY) + '),'
        'legacy:window.localStorage.getItem(' + json.dumps(BROWSER_WATCHLIST_KEY) + ')' 
        '});}catch(e){return JSON.stringify({ok:false});}})()'
    )
    result = streamlit_js_eval(js_expressions=expression, want_output=True,
                              key='ns_saved_lists_restore_repaired_v1')
    if result is None:
        return None
    try:
        return json.loads(result) if isinstance(result, str) else result
    except (ValueError, TypeError):
        return {'ok': False}


def queue_watchlist_save():
    # Millisecond Unix time remains exactly representable as a JS Number.
    # Monotonic increase prevents older asynchronous writes overwriting newer.
    prior = int(st.session_state.get('ns_save_revision', 0))
    revision = max(prior + 1, int(_ns_time.time() * 1000))
    st.session_state['ns_save_revision'] = revision
    st.session_state['ns_pending_watchlist_save'] = revision


def mark_watchlist_dirty():
    # Called ONLY on explicit list edits/creation/deletion, never on selection.
    active = st.session_state['ns_active_list']
    if active != AUTO_LIST_NAME:
        clean = valid_saved_watchlist(st.session_state.get('ns_watchlist'))
        if clean is not None:
            st.session_state['ns_lists'][active] = clean
    queue_watchlist_save()


def switch_named_watchlist():
    selected = st.session_state.get('ns_named_watchlist_select')
    lists = st.session_state['ns_lists']
    if selected not in lists:
        return
    if selected == st.session_state.get('ns_active_list'):
        return
    # The mapping has already been updated by any prior add/remove operation.
    # Do not copy ns_watchlist back into the previous list on a selection event.
    st.session_state['ns_active_list'] = selected
    st.session_state['ns_watchlist'] = list(lists[selected])
    queue_watchlist_save()  # save selection preference, NOT ticker changes


def save_watchlist_on_next_render():
    pending = st.session_state.get('ns_pending_watchlist_save')
    if not pending:
        return
    lists = {name: symbols for name, symbols in st.session_state['ns_lists'].items()
             if name != AUTO_LIST_NAME}
    payload = json.dumps({'version': int(pending),
                          'active': st.session_state['ns_active_list'],
                          'lists': lists}, separators=(',', ':'))
    # Keep a one-time backup of the old browser record and guard out-of-order
    # asynchronous component writes using the monotonically increasing version.
    script = (
        '(function(){try{'
        'const k=' + json.dumps(SAVED_LISTS_KEY) + ';'
        'const incoming=' + json.dumps(payload) + ';'
        'const n=JSON.parse(incoming);'
        'const old=window.localStorage.getItem(k);'
        'if(old&&!window.localStorage.getItem(k+"_before_repair"))'
        'window.localStorage.setItem(k+"_before_repair",old);'
        'let v=0;try{v=Number(JSON.parse(old).version||0)||0}catch(e){}'
        'if(Number(n.version)>=v)window.localStorage.setItem(k,incoming);'
        'return "saved";'
        '}catch(e){return "error";}})()'
    )
    result = streamlit_js_eval(js_expressions=script, want_output=True,
                              key=f'ns_save_named_lists_repaired_{pending}')
    if result == 'saved' and st.session_state.get('ns_pending_watchlist_save') == pending:
        st.session_state.pop('ns_pending_watchlist_save', None)
    elif result == 'error':
        st.warning('Browser storage is unavailable. Watchlist changes may not persist.')


if 'ns_named_lists_restored' not in st.session_state:
    saved = browser_saved_lists_read()
    if saved is None:
        st.caption('Restoring your saved watchlists…')
        st.stop()
    if not isinstance(saved, dict) or not saved.get('ok'):
        st.error('Browser storage is blocked. Enable site storage to restore your watchlists.')
        st.stop()
    modern = None
    try:
        modern = json.loads(saved.get('modern') or 'null')
    except (TypeError, ValueError):
        pass
    lists = {}
    active = None
    if isinstance(modern, dict):
        candidates = modern.get('lists') or {}
        if isinstance(candidates, dict):
            for name, symbols in candidates.items():
                if not isinstance(name, str) or not name.strip() or len(name) > 32 or name == AUTO_LIST_NAME:
                    continue
                validated = valid_saved_watchlist(symbols)
                if validated is not None and len(lists) < 12:
                    lists[name] = validated
        active = modern.get('active')
    if not lists:
        legacy = valid_saved_watchlist(saved.get('legacy'))
        session = valid_saved_watchlist(st.session_state.get('ns_watchlist'))
        lists = {'Default': legacy if legacy is not None else (
                 session if session is not None else DEFAULT_WATCHLIST.copy())}
    if active not in lists and active != AUTO_LIST_NAME:
        active = 'Default' if 'Default' in lists else next(iter(lists))
    st.session_state['ns_lists'] = lists
    st.session_state['ns_active_list'] = active
    st.session_state['ns_watchlist'] = list(lists.get(active, []))
    st.session_state['ns_named_lists_restored'] = True
    if not isinstance(modern, dict):
        queue_watchlist_save()  # migrate legacy v1 list without destroying it

# Keep existing in-memory lists when the source code is reloaded mid-session.
if not isinstance(st.session_state.get('ns_lists'), dict):
    st.error('Could not recover saved watchlist state. Reload the page.')
    st.stop()

# Always include the read-only emailed-alert list, even when GitHub is
# misconfigured or returns 404. Errors are shown when this list is selected.
email_snapshot = load_email_alerts()
st.session_state['ns_lists'][AUTO_LIST_NAME] = (
    list(email_snapshot.symbols) if not email_snapshot.error else []
)
if st.session_state.get('ns_active_list') not in st.session_state['ns_lists']:
    st.session_state['ns_active_list'] = next(iter(st.session_state['ns_lists']))
active_now = st.session_state['ns_active_list']
st.session_state['ns_watchlist'] = list(st.session_state['ns_lists'][active_now])
if st.session_state.get('ns_named_watchlist_select') != active_now:
    st.session_state['ns_named_watchlist_select'] = active_now
st.session_state.setdefault('ns_scans', {})
save_watchlist_on_next_render()
watchlist = list(st.session_state['ns_lists'][st.session_state['ns_active_list']])


'''



def _add_email_import(code: str) -> str:
    if 'from scanner_email_watchlist import' in code:
        return code
    pattern = re.compile(r'^from dashboard_theme import [^\n]+$', re.M)
    injection = ('from scanner_email_watchlist import ('
                 'AUTO_LIST_NAME, load_email_alerts, '
                 'saved_regression_zscores, sigma_label)')
    code, n = pattern.subn(lambda m: m.group(0) + '\n' + injection, code, count=1)
    if n != 1:
        raise ValueError('Cannot locate dashboard_theme import in News Screen.')
    return code


def _remove_old_switch(code: str) -> str:
    """Remove stale copy-on-switch using AST, regardless of quote/whitespace."""
    tree = ast.parse(code)
    to_remove = []
    for node in tree.body:
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
            continue
        test = node.test
        if (isinstance(test.left, ast.Name) and test.left.id == 'selected_name'
                and len(test.ops) == 1 and isinstance(test.ops[0], ast.NotEq)
                and len(test.comparators) == 1):
            other = ast.unparse(test.comparators[0])
            if other in ("st.session_state['ns_active_list']", 'st.session_state["ns_active_list"]'):
                to_remove.append(node)
    if len(to_remove) > 1:
        raise ValueError('Multiple legacy switch handlers detected. No files changed.')
    if not to_remove:
        # Already using a callback or another workflow. If callback is missing,
        # prefer failing visibly over keeping a potentially conflicting handler.
        if 'on_change=switch_named_watchlist' not in code:
            raise ValueError('Cannot identify the old watchlist switching handler. No files changed.')
        return code
    node = to_remove[0]
    lines = code.splitlines(keepends=True)
    return ''.join(lines[:node.lineno - 1] + lines[node.end_lineno:])


def _attach_switch_callback(code: str) -> str:
    if 'on_change=switch_named_watchlist' in code:
        return code
    pattern = re.compile(r"key=(['\"])ns_named_watchlist_select\1")
    code, count = pattern.subn("key='ns_named_watchlist_select', on_change=switch_named_watchlist", code, count=1)
    if count != 1:
        raise ValueError('Cannot find watchlist selector key; no files changed.')
    return code


def _enable_readonly_controls(code: str) -> str:
    # Disable editing of a system-generated list without changing any manual lists.
    code = re.sub(
        r'(st\.form_submit_button\(\s*[\'"]Add stock[\'"](?:(?!\)\s*).)*?)(\))',
        lambda m: m.group(0) if 'disabled=' in m.group(0) else m.group(1) + ', disabled=(st.session_state["ns_active_list"] == AUTO_LIST_NAME)' + m.group(2),
        code, count=1, flags=re.S,
    )
    code = re.sub(
        r'(st\.button\(\s*[\'"]Delete selected watchlist[\'"](?:(?!\)\s*).)*?)(\))',
        lambda m: m.group(0) if 'disabled=' in m.group(0) else m.group(1) + ', disabled=(st.session_state["ns_active_list"] == AUTO_LIST_NAME)' + m.group(2),
        code, count=1, flags=re.S,
    )
    return code


def _add_auto_chips(code: str) -> str:
    if 'WATCHLIST · AUTOMATIC' in code:
        return code
    start = re.search(r'^chip_sizes\s*=.*$', code, flags=re.M)
    end = re.search(r'^control_left(?:,\s*sigma_control)?,\s*control_right\s*=\s*st\.columns\(', code, flags=re.M)
    if not start or not end or end.start() <= start.start():
        raise ValueError('Cannot locate existing ticker-chip layout; no files changed.')
    current = code[start.start():end.start()].rstrip('\n')
    if 'with st.popover(' not in current and 'chip_cols' not in current:
        raise ValueError('Unexpected ticker-chip layout; no files changed.')
    replacement = (
        "if st.session_state['ns_active_list'] == AUTO_LIST_NAME:\n"
        '    st.markdown("**WATCHLIST · AUTOMATIC**")\n'
        '    st.caption(" · ".join(watchlist) if watchlist else "No emailed tickers in the latest batch.")\n'
        'else:\n' + '\n'.join('    ' + l if l else '' for l in current.split('\n')) + '\n\n'
    )
    return code[:start.start()] + replacement + code[end.start():]


def _add_auto_status(code: str) -> str:
    if 'Automatic scanner watchlist unavailable:' in code:
        return code
    anchor = "st.markdown('<div class=\"ns-toprule\"></div>', unsafe_allow_html=True)"
    if code.count(anchor) != 1:
        raise ValueError('Cannot find watchlist separator; no files changed.')
    status = '''if st.session_state['ns_active_list'] == AUTO_LIST_NAME:
    if email_snapshot.error:
        st.warning('Automatic scanner watchlist unavailable: ' + email_snapshot.error)
    elif email_snapshot.latest_email_date:
        st.caption('Latest emailed crossings: ' + email_snapshot.latest_email_time
                   + f' · {len(email_snapshot.symbols)} stocks. Refreshes from GitHub about every 5 minutes.')
    else:
        st.info('No successfully emailed crossings are recorded yet.')
'''
    return code.replace(anchor, status + anchor, 1)


def _add_sigma(code: str) -> str:
    if 'ns_show_sigma' in code:
        return code
    pat = re.compile(r'^control_left,\s*control_right\s*=\s*st\.columns\((.+)\)$', re.M)
    matches = list(pat.finditer(code))
    if len(matches) != 1:
        raise ValueError('Cannot locate News Screen refresh row for Show σ; no files changed.')
    signature = matches[0].group(0)
    code = code.replace(signature,
        'control_left, sigma_control, control_right = st.columns([3.1, 0.75, 1.15], vertical_alignment="center")\n'
        'with sigma_control:\n'
        '    show_sigma = st.checkbox("Show σ", key="ns_show_sigma", '
        'help="Saved scanner regression Z-score; N/A if unavailable. Not daily volatility.")',1)
    fn = re.compile(r'^def make_card\([^\n]+\) -> str:',re.M)
    matches=list(fn.finditer(code))
    if len(matches) != 1:
        raise ValueError('Cannot locate stock card function; no files changed.')
    signature=matches[0].group(0)
    if 'sigma_text:' not in signature:
        code=code.replace(signature,signature.replace(') -> str:',", sigma_text: str = '') -> str:"),1)
    # The original cards contain this stable HTML title fragment in all known layouts.
    match=re.search(r'f\'<div><div class="ns-symbol">\{safe_symbol\}</div><div class="ns-company">\{name\}</div>(\{event_html\})?</div>\'',code)
    if not match:
        raise ValueError('Cannot locate stock card title to show σ; no files changed.')
    if '{sigma_html}' not in match.group(0):
        code=code.replace(match.group(0),match.group(0).replace('</div>\'', '{sigma_html}</div>\''),1)
    pattern='    articles_html = "".join(article_rows)\n'
    if 'sigma_html = ' not in code:
        if code.count(pattern) != 1:
            raise ValueError('Cannot locate stock card article rows; no files changed.')
        code=code.replace(pattern,pattern+'    sigma_html = (f\'<div class="ns-sigma">{html.escape(sigma_text)}</div>\' if sigma_text else "")\n',1)
    # Standalone style tag avoids depending on any exact end of the existing CSS.
    anchor='apply_dashboard_theme()\n'
    if code.count(anchor) != 1:
        raise ValueError('Cannot locate theme setup for σ style; no files changed.')
    code=code.replace(anchor, anchor+'''st.markdown('<style>.ns-sigma{font-size:10px;color:#81BEDF;margin-top:5px;}</style>', unsafe_allow_html=True)
''',1)
    # Precompute scores only if requested and append to each stock card.
    cards_match=re.search(r'^cards\s*=\s*\[',code,re.M)
    if not cards_match:
        raise ValueError('Cannot locate stock card list; no files changed.')
    code=code[:cards_match.start()]+(
        'sigma_scores = saved_regression_zscores(str(PROJECT_ROOT)) if show_sigma else {}\n'
        +code[cards_match.start():]
    )
    argmatch=re.search(r'(?m)^(\s+)first=\(i == 0\),\s*$',code)
    if not argmatch:
        raise ValueError('Cannot locate stock card arguments; no files changed.')
    insertion=(f'{argmatch.group(1)}sigma_text=(sigma_label(symbol, sigma_scores, email_snapshot, '
               f'st.session_state["ns_active_list"] == AUTO_LIST_NAME) if show_sigma else ""),\n')
    code=code[:argmatch.end()]+'\n'+insertion+code[argmatch.end():]
    return code


def transform(source: str) -> str:
    # Idempotence: don't rewrite or reset previously repaired browser state.
    if '# si_watchlist_repair_v2' in source:
        return source
    if '# --- Browser-local named watchlists' not in source:
        if '# si_watchlist_switch_repaired_v1' in source:
            return source
        raise ValueError('Cannot locate named watchlist state code; no files changed.')
    source = _add_email_import(source)
    begin=source.index('# --- Browser-local named watchlists')
    finish=source.find('render_page_header(',begin)
    if finish<0:
        raise ValueError('Cannot locate General News Screen header; no files changed.')
    source=source[:begin]+'# si_watchlist_repair_v2\n'+STATE_BLOCK+source[finish:]
    source=_remove_old_switch(source)
    source=_attach_switch_callback(source)
    source=_enable_readonly_controls(source)
    source=_add_auto_status(source)
    source=_add_auto_chips(source)
    source=_add_sigma(source)
    ast.parse(source, filename=str(PAGE))
    return source


def run() -> None:
    if not (ROOT / 'app.py').is_file() or not PAGE.is_file():
        raise ValueError('Run inside StockIntelligenceDashboard, beside app.py and pages/1_News_Screen.py.')
    supplied_helper = SRC_DIR / 'scanner_email_watchlist.py'
    if not supplied_helper.is_file():
        raise ValueError('Place scanner_email_watchlist.py next to this installer.')
    current=read(PAGE)
    updated=transform(current)
    if updated==current and HELPER.is_file():
        print('Already repaired; no changes necessary.')
        return
    backup=BACKUPS / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(PAGE, backup/'1_News_Screen.py')
    if HELPER.is_file():
        shutil.copy2(HELPER, backup/'scanner_email_watchlist.py')
    try:
        # Fail before writing if there is an unexpected import conflict.
        ast.parse(updated)
        PAGE.write_text(updated,encoding='utf-8', newline='\n')
        if not HELPER.is_file():
            shutil.copy2(supplied_helper, HELPER)
    except BaseException:
        shutil.copy2(backup/'1_News_Screen.py',PAGE)
        if not (backup/'scanner_email_watchlist.py').exists() and HELPER.exists():
            HELPER.unlink()
        raise
    print('SUCCESS: Fixed named list selection and added read-only Weekday Scanner Alerts and Show σ.')
    print('Backup:',backup)
    print('Your browser-local watchlists are not modified by this installer.')


if __name__=='__main__':
    try:
        run()
    except (OSError,ValueError,SyntaxError,UnicodeError) as error:
        print('UPDATE NOT APPLIED:',error,file=sys.stderr)
        raise SystemExit(1)
