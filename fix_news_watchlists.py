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


def _remove_legacy_switch(code: str) -> str:
    tree = ast.parse(code)
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.If):
            statement = ast.get_source_segment(code, node.test) or ''
            if "selected_name != st.session_state['ns_active_list']" in statement:
                nodes.append(node)
    if len(nodes) != 1:
        raise ValueError(f"Expected exactly one old list-switch block, found {len(nodes)}; no changes applied.")
    lines = code.splitlines(keepends=True)
    node = nodes[0]
    return ''.join(lines[:node.lineno-1] + lines[node.end_lineno:])


def _use_callback(code: str) -> str:
    # Both two-control and four-control versions use the same selectbox key.
    if 'on_change=switch_named_watchlist' in code:
        return code
    pat = re.compile(r"key=('|\")ns_named_watchlist_select\1\)")
    code, count = pat.subn("key='ns_named_watchlist_select', on_change=switch_named_watchlist)", code, count=1)
    if count != 1:
        raise ValueError("Could not identify the named watchlist selectbox; no changes applied.")
    return code


def transform(source: str) -> str:
    if '# si_watchlist_switch_repaired_v1' in source:
        return source
    # Integrate the automatic email list and σ toggle if they have not yet
    # actually been installed. Setting secrets.toml alone does not install it.
    if '# si_weekday_emailed_alerts_v1' not in source:
        from install_email_alert_watchlist import update_page
        source = update_page(source)
    start_marker = '# --- Browser-local named watchlists'
    start = source.find(start_marker)
    if start < 0:
        raise ValueError("Cannot locate the existing named-watchlist state block; no changes applied.")
    end = source.find('render_page_header(', start)
    if end < 0:
        raise ValueError("Cannot locate the News Screen header; no changes applied.")
    source = source[:start] + '# si_watchlist_switch_repaired_v1\n' + STATE_BLOCK + source[end:]
    source = _remove_legacy_switch(source)
    source = _use_callback(source)
    ast.parse(source, filename=str(PAGE))
    return source


def run() -> None:
    if not (ROOT / 'app.py').is_file() or not PAGE.is_file():
        raise ValueError('Run this from StockIntelligenceDashboard, beside app.py, with pages/1_News_Screen.py available.')
    helper_template = SRC_DIR / 'scanner_email_watchlist.py'
    if not helper_template.is_file():
        raise ValueError('Copy the entire ZIP, including scanner_email_watchlist.py, to the project root.')
    original = read(PAGE)
    updated = transform(original)
    # Keep the existing helper if installed. Do not silently replace custom code.
    helper_missing = not HELPER.is_file()
    if original == updated and not helper_missing:
        print('Already installed; no changes necessary.')
        return
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = BACKUPS / stamp
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(PAGE, backup / '1_News_Screen.py')
    if HELPER.is_file():
        shutil.copy2(HELPER, backup / 'scanner_email_watchlist.py')
    try:
        PAGE.write_text(updated, encoding='utf-8', newline='\n')
        if helper_missing:
            shutil.copy2(helper_template, HELPER)
    except BaseException:
        shutil.copy2(backup / '1_News_Screen.py', PAGE)
        if helper_missing and HELPER.exists():
            HELPER.unlink()
        raise
    print('SUCCESS: Watchlist selection repaired; Weekday Scanner Alerts option installed.')
    print('Saved page backup at', backup)
    print('Run Streamlit and switch between at least two saved lists to verify.')


if __name__ == '__main__':
    try:
        run()
    except (OSError, ValueError, UnicodeError, SyntaxError) as exc:
        print('UPDATE NOT APPLIED:', exc, file=sys.stderr)
        raise SystemExit(1)
