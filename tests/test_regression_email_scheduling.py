"""Offline test of New York schedule gating and unique Gmail report subjects."""
import ast
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from regression_scanner.schedule_guard import (
    EDT_CRON, EST_CRON, should_send,
)

def at(year, month, day, hour, minute, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)

# UTC conversion and NY daylight saving changes (Monday dates).
assert should_send("schedule", EST_CRON, at(2026, 11, 23, 13, 35))
assert not should_send("schedule", EDT_CRON, at(2026, 11, 23, 12, 35))
assert should_send("schedule", EDT_CRON, at(2026, 7, 20, 12, 35))
assert not should_send("schedule", EST_CRON, at(2026, 7, 20, 13, 35))
assert not should_send("schedule", EST_CRON, at(2026, 11, 20, 21, 26))
assert not should_send("schedule", EST_CRON, at(2026, 11, 23, 16, 0))
assert not should_send("push", EST_CRON, at(2026, 11, 23, 13, 35))
assert should_send("workflow_dispatch", "", at(2026, 11, 21, 1, 0))

workflow = (ROOT / ".github/workflows/cloud-email-scanner.yml").read_text()
assert "cron: '30 12 * * 1-5'" in workflow
assert "cron: '30 13 * * 1-5'" in workflow
assert "timezone:" not in workflow
assert "ENABLE_CLOUD_SCHEDULE" not in workflow
assert "needs.schedule-gate.outputs.run_scan == 'true'" in workflow
assert "python regression_scanner/schedule_guard.py" in workflow

# Extract the production subject builder to execute with stubbed helpers:
# automated_scan.py imports pandas and market APIs, unavailable to fast CI.
source = (ROOT / "regression_scanner/automated_scan.py").read_text()
parsed = ast.parse(source)
target = next(n for n in parsed.body
              if isinstance(n, ast.FunctionDef) and n.name == "email_subject")
namespace = {
    "datetime": datetime,
    "ET": ZoneInfo("America/New_York"),
    "BUCKETS": [("2-5B", 2, 5), ("50B+", 50, None)],
    "zone_for": lambda z, bucket="": "-4σ" if z <= -4 else "-3σ",
    "prime_opportunity": lambda row: True,
    "_level_rank": lambda level: 1,
    "Counter": Counter,
}
# The current function imports collections.Counter itself.
exec(compile(ast.Module(body=[target], type_ignores=[]),
             "regression_scanner/automated_scan.py", "exec"), namespace)
subject = namespace["email_subject"]
one = subject([], [], run_at=at(2026, 11, 23, 13, 31, 12))
two = subject([], [], run_at=at(2026, 11, 23, 13, 31, 13))
assert one.startswith("Nov 23, 2026 08:31:12 AM ET | Potentially Undervalued Stocks:")
assert one != two, "Same-day runs must have unique subjects to avoid Gmail threading"
assert "new/worsened" in one

mailer = (ROOT / "regression_scanner/emailer.py").read_text()
assert 'message["Message-ID"] = make_msgid()' in mailer
assert 'message["Date"] = format_datetime' in mailer
html = (ROOT / "regression_scanner/email_report.py").read_text()
assert "<details" not in html and 'style="display:none' not in html
print("PASS: morning scheduling, DST, delayed-run suppression, unique subjects and visible HTML")
