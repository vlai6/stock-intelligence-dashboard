"""Switch an EXISTING Streamlit app to native top navigation.

Safe, narrow edits only:
- app.py: set st.navigation(..., position='top'), collapse unused sidebar,
          and remove the earlier red loading_notice call.
- dashboard_theme.py: retain normal titles/subtitles, remove duplicate page links.

The script checks syntax and saves both originals outside pages/ before changes.
Run from StockIntelligenceDashboard root:
    .\\.venv\\Scripts\\python.exe apply_top_navigation.py
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app.py'
THEME = ROOT / 'dashboard_theme.py'


def _absolute_index(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    # AST offsets are UTF-8 byte offsets, not character offsets. Decode prefix
    # before counting Unicode characters so non-ASCII comments stay harmless.
    return sum(len(s) for s in lines[:line - 1]) + len(lines[line - 1].encode('utf-8')[:column].decode('utf-8'))


def _replace_spans(source: str, changes: list[tuple[int, int, str]]) -> str:
    for left, right, text in sorted(changes, key=lambda c: c[0], reverse=True):
        if not (0 <= left <= right <= len(source)):
            raise RuntimeError('Invalid source replacement range; no changes applied.')
        source = source[:left] + text + source[right:]
    return source


def _node_span(source: str, node: ast.AST) -> tuple[int, int]:
    return (_absolute_index(source, node.lineno, node.col_offset),
            _absolute_index(source, node.end_lineno, node.end_col_offset))


def _is_st_method(call: ast.Call, name: str) -> bool:
    return (isinstance(call.func, ast.Attribute) and call.func.attr == name
            and isinstance(call.func.value, ast.Name) and call.func.value.id == 'st')


def update_app(source: str) -> str:
    tree = ast.parse(source)
    nav_calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and _is_st_method(node, 'navigation')]
    if len(nav_calls) != 1:
        raise RuntimeError(f'Expected one st.navigation(...) call, found {len(nav_calls)}. '
                           'No files changed. Please provide app.py for an exact edit.')
    nav = nav_calls[0]
    changes: list[tuple[int, int, str]] = []
    position = next((item for item in nav.keywords if item.arg == 'position'), None)
    if position:
        a, b = _node_span(source, position.value)
        changes.append((a, b, "'top'"))
    else:
        # Insert before closing parenthesis; standard multiline navigation calls
        # work without modifying any page objects or their ordering.
        _a, b = _node_span(source, nav)
        changes.append((b - 1, b - 1, ", position='top'"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_st_method(node, 'set_page_config'):
            sidebar = next((item for item in node.keywords if item.arg == 'initial_sidebar_state'), None)
            if sidebar:
                a, b = _node_span(source, sidebar.value)
                changes.append((a, b, "'collapsed'"))

    # Remove the prior red loading CSS injection. Keep the unreferenced
    # loading_notice.py file intact rather than risk altering unrelated code.
    for statement in tree.body:
        is_notice_import = (isinstance(statement, ast.ImportFrom)
                            and statement.module == 'loading_notice'
                            and any(alias.name == 'show_loading_notice' for alias in statement.names))
        is_notice_call = (isinstance(statement, ast.Expr)
                          and isinstance(statement.value, ast.Call)
                          and isinstance(statement.value.func, ast.Name)
                          and statement.value.func.id == 'show_loading_notice')
        if is_notice_import or is_notice_call:
            lines = source.splitlines(keepends=True)
            a = sum(len(line) for line in lines[:statement.lineno - 1])
            b = sum(len(line) for line in lines[:statement.end_lineno])
            changes.append((a, b, ''))
    updated = _replace_spans(source, changes)
    # Remove just our old standalone marker, preserving user comments nearby.
    updated = updated.replace('# si_shared_loading_notice_v1\n', '')
    ast.parse(updated)
    if 'show_loading_notice()' in updated:
        raise RuntimeError('A loading notice call remains; no changes applied. Please share app.py.')
    return updated


HEADER = '''def render_page_header(title: str, subtitle: str = '', current: str = 'stock'):
    """Render each page title; native top navigation is owned by app.py."""
    with st.container(key=f'si_header_{current}'):
        st.markdown(f'<h1 class="si-page-title">{escape(title)}</h1>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<div class="si-page-subtitle">{escape(subtitle)}</div>',
                        unsafe_allow_html=True)
'''


def update_theme(source: str) -> str:
    tree = ast.parse(source)
    functions = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == 'render_page_header']
    if len(functions) != 1:
        raise RuntimeError('Could not locate the page header in dashboard_theme.py. '
                           'No files changed. Please share dashboard_theme.py.')
    if not ('apply_dashboard_theme' in source and 'import streamlit as st' in source):
        raise RuntimeError('Theme does not match the expected dashboard module. No files changed.')
    a, b = _node_span(source, functions[0])
    updated = source[:a] + HEADER.rstrip("\n") + source[b:]
    ast.parse(updated)
    return updated


def main() -> None:
    if not APP.is_file() or not THEME.is_file():
        raise SystemExit('Missing app.py or dashboard_theme.py beside this script. No files changed.')
    app_before = APP.read_text(encoding='utf-8-sig')
    theme_before = THEME.read_text(encoding='utf-8-sig')
    try:
        app_after = update_app(app_before)
        theme_after = update_theme(theme_before)
    except (SyntaxError, RuntimeError) as exc:
        raise SystemExit(f'UPDATE NOT APPLIED: {exc}')

    changed = [(APP, app_before, app_after), (THEME, theme_before, theme_after)]
    changed = [t for t in changed if t[1] != t[2]]
    if not changed:
        print('Top navigation and minimal page headers are already installed. No changes made.')
        return

    backup = ROOT / '.ui_top_navigation_backup' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup.mkdir(parents=True, exist_ok=False)
    for path, before, _ in changed:
        (backup / path.name).write_text(before, encoding='utf-8')
    for path, _, after in changed:
        path.write_text(after, encoding='utf-8')
    print('Updated native horizontal navigation successfully.')
    print('  Streamlit navigation: top of the page')
    print('  Duplicated page-header navigation buttons: removed')
    print('  Red 2–5-minute loading notice: removed')
    print('Backups:', backup)


if __name__ == '__main__':
    main()
