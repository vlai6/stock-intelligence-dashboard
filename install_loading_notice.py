"""Add one early shared loading notice to the EXISTING app.py, without replacing it.

Usage from the StockIntelligenceDashboard project root:
  .\\.venv\\Scripts\\python.exe install_loading_notice.py
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parent
app = root / 'app.py'
notice_module = root / 'loading_notice.py'
if not app.exists():
    raise SystemExit('app.py not found in this folder. Copy this script beside app.py first. No changes made.')
if not notice_module.exists():
    raise SystemExit('loading_notice.py not found beside app.py. No changes made.')
source = app.read_text(encoding='utf-8-sig')
if '# si_shared_loading_notice_v1' in source:
    print('The shared loading notice is already installed. No changes needed.')
    raise SystemExit(0)
try:
    tree = ast.parse(source)
except SyntaxError as exc:
    raise SystemExit(f'Cannot safely patch app.py: syntax error on line {exc.lineno}. No changes made.')

# Install immediately before the multipage router invokes page.run(). This is
# early enough to appear before slow page queries, while preserving Streamlit's
# normal st.set_page_config -> st.navigation -> page.run order.
line_end = None
insert_before = False
for statement in tree.body:
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        call = statement.value
        if isinstance(call.func, ast.Attribute) and call.func.attr == 'run':
            line_end = statement.lineno - 1
            insert_before = True
            break
if line_end is None:
    for statement in tree.body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == 'set_page_config':
                if isinstance(call.func.value, ast.Name) and call.func.value.id == 'st':
                    line_end = statement.end_lineno
                    break
if line_end is None:
    raise SystemExit('Could not find a top-level page.run() or st.set_page_config(...) in app.py. '
                     'No changes made. See README for manual installation.')
lines = source.splitlines(keepends=True)
addition = ('\n# si_shared_loading_notice_v1\n'
            'from loading_notice import show_loading_notice\n'
            'show_loading_notice()\n')
updated = ''.join(lines[:line_end]) + addition + ''.join(lines[line_end:])
try:
    ast.parse(updated)
except SyntaxError:
    raise SystemExit('The generated app.py failed syntax validation. No changes made.')
backup = root / f'app.py.before_loading_notice.{datetime.now():%Y%m%d_%H%M%S}.bak'
backup.write_text(source,encoding='utf-8')
app.write_text(updated,encoding='utf-8')
print('Added the page-wide loading notice to app.py.')
print('Original app.py backup:',backup.name)
print('Existing navigation and pages were left unchanged.')
