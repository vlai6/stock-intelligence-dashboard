"""Optional: save exact emailed Z-scores to scanner's existing alerts.json.

Run this from the separate regression-stock-scanner repository, NOT the
StockIntelligenceDashboard repository. It changes only scanner.py's existing
send_alerts function; existing GitHub Actions already commits alerts.json.
"""
from __future__ import annotations

import ast
import shutil
import sys
from datetime import datetime
from pathlib import Path

MARKER = "# si_email_zscores_v1"
TARGET = Path.cwd() / "scanner.py"


def read(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    return raw.decode('utf-8-sig')


def update(content: str) -> str:
    if MARKER in content:
        return content
    tree = ast.parse(content, filename="scanner.py")
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'send_alerts']
    if len(functions) != 1:
        raise ValueError('Scanner does not contain exactly one send_alerts function.')
    fn = functions[0]
    body = content.splitlines(keepends=True)
    sub = ''.join(body[fn.lineno-1:fn.end_lineno])
    old = '    for key, _, _ in fresh:\n        state["sent"][key] = '
    if sub.count(old) != 1:
        raise ValueError('Expected original sent-alert state update is missing or differs; not modifying scanner.')
    # Captures values from the same fresh rows already included in the email.
    addition = '''    # si_email_zscores_v1: remember exactly which alerts were emailed.
    latest_email_stocks = {}
    for _, row, band in fresh:
        symbol = str(row["ticker"]).strip().upper()
        if symbol not in latest_email_stocks:
            latest_email_stocks[symbol] = {
                "ticker": symbol,
                "z_score": float(row["z_score"]),
                "bands": [],
            }
        if band not in latest_email_stocks[symbol]["bands"]:
            latest_email_stocks[symbol]["bands"].append(band)
    state["last_email"] = {
        "session": target,
        "sent_at": datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds"),
        "stocks": list(latest_email_stocks.values()),
    }
'''
    sub_new = sub.replace(old, addition + old, 1)
    updated = ''.join(body[:fn.lineno-1]) + sub_new + ''.join(body[fn.end_lineno:])
    ast.parse(updated, filename='scanner.py')
    return updated


def main() -> None:
    if not TARGET.is_file():
        raise ValueError('Run this in the original scanner repository, where scanner.py is located.')
    original = read(TARGET)
    updated = update(original)
    if original == updated:
        print('Scanner is already updated.')
        return
    backup = TARGET.with_name('scanner.py.before_email_zscores_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.bak')
    shutil.copy2(TARGET, backup)
    TARGET.write_text(updated, encoding='utf-8', newline='\n')
    print('SUCCESS: scanner.py now saves emailed Z-scores inside state/alerts.json after SMTP succeeds.')
    print('Backup:', backup)
    print('Commit scanner.py to the standalone scanner repository so GitHub Actions runs this change.')
    print('Do not commit the .bak backup file.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, SyntaxError) as exc:
        print('NOT UPDATED:', exc, file=sys.stderr)
        raise SystemExit(1)
