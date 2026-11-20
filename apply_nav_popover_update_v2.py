"""Repair navigation order/labels and opaque watchlist popovers safely.

Run in StockIntelligenceDashboard (same folder as app.py):
    .\\.venv\\Scripts\\python.exe apply_nav_popover_update_v2.py

Does not modify regression or stock calculations. Creates backups before edits.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import shutil
import sys

ROOT = Path.cwd()
BACKUP_DIR = '.ui_nav_popover_backups'
TARGET_FILES = ('app.py', 'dashboard_theme.py', 'pages/2_News_Sentiment.py')
STYLE_MARKER = '/* SI opaque watchlist popovers v2 */'
PAGES = (
    ('general', 'General News Screen', 'pages/1_News_Screen.py', '📰'),
    ('scanner', 'Regression Scanner', 'regression_scanner/app.py', '📉'),
    ('stock', 'Stock Intelligence', 'pages/0_Stock_Intelligence.py', '📊'),
    ('sentiment', 'Recent Sentiment', 'pages/2_News_Sentiment.py', '📈'),
)
CSS = r'''
/* SI opaque watchlist popovers v2 */
/* The actual popover is portaled outside the button's parent column. */
div[data-baseweb="popover"] { z-index: 10000 !important; }
div[data-baseweb="popover"] > div,
div[data-baseweb="popover"] [data-testid="stPopoverBody"],
[data-testid="stPopoverBody"] {
  background: #0B1B2E !important;
  background-color: #0B1B2E !important;
  background-image: none !important;
  opacity: 1 !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  border: 1px solid #285075 !important;
  border-radius: 12px !important;
  box-shadow: 0 18px 48px rgba(0, 0, 0, .83) !important;
}
div[data-baseweb="popover"] [data-testid="stPopoverBody"] > div {
  background: #0B1B2E !important;
  background-color: #0B1B2E !important;
  opacity: 1 !important;
}
[data-testid="stPopoverBody"] [data-testid="stForm"] {
  background: #0D2238 !important;
  border-color: #244968 !important;
}
[data-testid="stPopoverBody"] [data-testid="stMarkdownContainer"] p,
[data-testid="stPopoverBody"] label { color: #E5F2FF !important; }
'''


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    if raw.startswith(b'\xef\xbb\xbf'):
        return raw.decode('utf-8-sig')
    return raw.decode('utf-8')


def replace_node(source: str, node: ast.AST, replacement: str) -> str:
    """Replace an AST span, handling CRLF, UTF-8 byte columns and EOF."""
    lines = source.splitlines(keepends=True)

    def index(line_no: int, column: int) -> int:
        prefix = sum(len(s) for s in lines[:line_no-1])
        line = lines[line_no-1]
        chars = line.encode('utf-8')[:column].decode('utf-8')
        return prefix + len(chars)

    first = index(node.lineno, node.col_offset)
    last = index(node.end_lineno, node.end_col_offset)
    return source[:first] + replacement + source[last:]


def is_st_call(node: ast.AST, name: str) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == name and isinstance(node.func.value, ast.Name)
            and node.func.value.id == 'st')


def get_str(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def update_router(src: str) -> str:
    tree = ast.parse(src, filename='app.py')
    candidates = [node for node in ast.walk(tree) if is_st_call(node, 'navigation')
                  and node.args and isinstance(node.args[0], (ast.List, ast.Tuple))]
    if len(candidates) != 1:
        raise ValueError('Expected one st.navigation([...]) router in app.py; found '+str(len(candidates)))
    nav = candidates[0]
    entries = nav.args[0]
    path_icons = {}
    for element in entries.elts:
        if not is_st_call(element, 'Page') or not element.args:
            raise ValueError('Unexpected page entry; not modifying the router')
        path = get_str(element.args[0])
        icon = next((get_str(k.value) for k in element.keywords if k.arg == 'icon'), None)
        if path is None:
            raise ValueError('A page path is not a literal; not modifying the router')
        path_icons[path] = icon
    expected = {p[2] for p in PAGES}
    if len(entries.elts) != 4 or set(path_icons) != expected:
        raise ValueError('Unexpected navigation pages: ' + ', '.join(sorted(path_icons)))
    new_list = '[\n' + '\n'.join(
        '    st.Page(' + repr(path) + ', title=' + repr(title) + ', icon=' + repr(path_icons[path] or icon)
        + (', default=True' if i == 0 else '') + '),'
        for i, (_slug, title, path, icon) in enumerate(PAGES)
    ) + '\n]'
    out = replace_node(src, entries, new_list)
    ast.parse(out, filename='app.py')
    return out


def update_theme(src: str) -> str:
    tree = ast.parse(src, filename='dashboard_theme.py')
    assignments = [n for n in ast.walk(tree)
                   if ((isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PAGES' for t in n.targets))
                       or (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == 'PAGES'))]
    if len(assignments) != 1:
        raise ValueError('Could not identify exactly one shared PAGES assignment in dashboard_theme.py')
    statement = assignments[0]
    value = statement.value
    try:
        items = ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, MemoryError) as exc:
        raise ValueError('PAGES must be a literal tuple/list of page registrations') from exc
    if len(items) != 4 or {row[2] for row in items} != {p[2] for p in PAGES}:
        raise ValueError('Unexpected shared PAGES entries; not overwriting them')
    pages_text = 'PAGES = (\n' + ''.join(
        '    '+repr((slug, title, path, next((old[3] for old in items if old[2] == path), icon)))+',\n'
        for slug, title, path, icon in PAGES
    ) + ')'
    out = replace_node(src, statement, pages_text)
    if STYLE_MARKER not in out:
        left = out.find('<style>')
        right = out.find('</style>', left + 7) if left >= 0 else -1
        if right < 0:
            raise ValueError('Cannot find a shared CSS <style> block in dashboard_theme.py')
        out = out[:right] + CSS + '\n' + out[right:]
    ast.parse(out, filename='dashboard_theme.py')
    return out


def update_sentiment(src: str) -> str:
    tree = ast.parse(src, filename='pages/2_News_Sentiment.py')
    title_candidates = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'render_page_header' and node.args:
            if get_str(node.args[0]) in {'News Sentiment','Recent Sentiment'}:
                title_candidates.append(node.args[0])
    if len(title_candidates) != 1:
        raise ValueError('Could not identify one News/Recent Sentiment page title; not modifying it')
    out = replace_node(src, title_candidates[0], repr('Recent Sentiment'))
    # Optional standalone stock-list label, if present.
    out = out.replace("'News Sentiment stock list'", "'Recent Sentiment stock list'")
    ast.parse(out, filename='pages/2_News_Sentiment.py')
    return out


def main() -> None:
    originals = {}
    for rel in TARGET_FILES:
        path = ROOT / rel
        if not path.is_file():
            raise ValueError(f'Missing {rel}; run in StockIntelligenceDashboard')
        originals[rel] = read_text(path)
    updated = {
        'app.py': update_router(originals['app.py']),
        'dashboard_theme.py': update_theme(originals['dashboard_theme.py']),
        'pages/2_News_Sentiment.py': update_sentiment(originals['pages/2_News_Sentiment.py']),
    }
    gitignore = ROOT / '.gitignore'
    if gitignore.exists():
        originals['.gitignore'] = read_text(gitignore)
        if BACKUP_DIR+'/' not in originals['.gitignore'].splitlines():
            updated['.gitignore'] = originals['.gitignore'].rstrip('\r\n')+'\n\n# Local navigation backups\n'+BACKUP_DIR+'/\n'
    changes = [key for key in updated if updated[key] != originals[key]]
    if not changes:
        print('Already updated; nothing to change.')
        return
    backup = ROOT / BACKUP_DIR / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    for rel in changes:
        path = backup / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, path)
    try:
        for rel in changes:
            (ROOT / rel).write_text(updated[rel], encoding='utf-8', newline='\n')
    except Exception:
        for rel in changes:
            shutil.copy2(backup / rel, ROOT / rel)
        raise
    print('SUCCESS: Navigation reordered; Recent Sentiment renamed; popovers made opaque.')
    print('Changed:', ', '.join(changes))
    print('Backups:', backup)
    print('Restart Streamlit to see changes.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('UPDATE NOT APPLIED:', exc, file=sys.stderr)
        raise SystemExit(1)
