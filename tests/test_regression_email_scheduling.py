"""Offline test of New York schedule gating and dated email subjects."""
import ast
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from regression_scanner.schedule_guard import (
    EDT_CRON, EST_CRON, EDT_BACKUP_CRON, EST_BACKUP_CRON,
    should_send, scheduled_delivery_exists, is_scheduled_trigger,
)

def at(year, month, day, hour, minute, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)

# UTC conversion, NY daylight saving, weekends, and holiday-adjacent weekdays.
# A UTC schedule starts only Mon-Fri, and the scanner separately checks the
# NYSE calendar before downloading any stocks.
assert should_send("schedule", EST_CRON, at(2026, 11, 23, 13, 35))
assert not should_send("schedule", EDT_CRON, at(2026, 11, 23, 12, 35))
assert should_send("schedule", EDT_CRON, at(2026, 7, 20, 12, 35))
# Backup runs at 8:55 ET, but the opposite season's backup must be ignored.
assert should_send("schedule", EST_BACKUP_CRON, at(2026, 11, 23, 13, 55))
assert should_send("schedule", EDT_BACKUP_CRON, at(2026, 7, 20, 12, 55))
assert not should_send("schedule", EDT_BACKUP_CRON, at(2026, 11, 23, 12, 55))
assert not should_send("schedule", EST_BACKUP_CRON, at(2026, 7, 20, 13, 55))
assert not should_send("schedule", EST_CRON, at(2026, 7, 20, 13, 35))
assert not should_send("schedule", EST_CRON, at(2026, 11, 20, 21, 26))
assert not should_send("schedule", EST_CRON, at(2026, 11, 23, 16, 0))
assert not should_send("schedule", EST_CRON, at(2026, 11, 21, 13, 30))  # Saturday
assert not should_send("schedule", EST_CRON, at(2026, 11, 22, 13, 30))  # Sunday
assert not should_send("schedule", EST_CRON, at(2026, 11, 23, 15, 30))  # after 10:30 AM ET
assert not should_send("schedule", EST_CRON, at(2026, 11, 23, 13, 0))  # before morning window
assert should_send("schedule", EST_CRON, at(2026, 11, 23, 15, 29))  # 10:29 AM ET
# Summer/winter DST switchover is handled by the expected UTC cron.
assert not should_send("push", EST_CRON, at(2026, 11, 23, 13, 35))
assert should_send("workflow_dispatch", "", at(2026, 11, 21, 1, 0))
assert should_send(
    "workflow_dispatch", "", at(2026, 11, 23, 13, 30),
    externally_scheduled=True,
)
assert not should_send(
    "workflow_dispatch", "", at(2026, 11, 23, 16, 30),
    externally_scheduled=True,
)
assert not should_send(
    "workflow_dispatch", "", at(2026, 11, 22, 13, 30),
    externally_scheduled=True,
)
assert is_scheduled_trigger("workflow_dispatch", True)
assert not is_scheduled_trigger("workflow_dispatch")
assert is_scheduled_trigger("schedule")
# Backup dedup recognizes only successfully delivered scheduled emails.
delivery = {"last_delivery": "2026-11-23T04:29:22-05:00",
            "last_scheduled_delivery_date": "2026-11-23"}
assert scheduled_delivery_exists(delivery, at(2026, 11, 23, 13, 55), "schedule")
assert not scheduled_delivery_exists(delivery, at(2026, 11, 24, 13, 55), "schedule")
assert not scheduled_delivery_exists(delivery, at(2026, 11, 23, 13, 55), "workflow_dispatch")
assert scheduled_delivery_exists(
    delivery, at(2026, 11, 23, 13, 55),
    "workflow_dispatch", externally_scheduled=True,
)
assert not scheduled_delivery_exists(
    {"last_delivery": "2026-11-23T04:29:22-05:00"},
    at(2026, 11, 23, 13, 55), "schedule",
)

workflow = (ROOT / ".github/workflows/cloud-email-scanner.yml").read_text()
assert "cron: '30 12 * * 1-5'" in workflow
assert "cron: '30 13 * * 1-5'" in workflow
assert "cron: '55 12 * * 1-5'" in workflow
assert "cron: '55 13 * * 1-5'" in workflow
assert "automated:" in workflow
assert "EXTERNAL_SCHEDULED: ${{ inputs.automated || 'false' }}" in workflow
assert "default: false" in workflow
assert "timezone:" not in workflow
assert "ENABLE_CLOUD_SCHEDULE" not in workflow
assert "SEND_EVERY_SCAN: '1'" in workflow
assert "SMTP_HOST: ${{ secrets.SMTP_HOST }}" in workflow
assert "SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}" in workflow
assert "ALERT_TO: ${{ vars.ALERT_TO || secrets.ALERT_TO }}" in workflow
assert "if: ${{ needs.schedule-gate.outputs.run_scan == 'true' }}" in workflow
# A weekday job must get a live scanner, not the manual test-email default.
assert 'github.event_name == \'schedule\' && \'live\' || inputs.mode' in workflow
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
next_day = subject([], [], run_at=at(2026, 11, 24, 13, 31, 13))
assert one.startswith("Nov 23, 2026 | Potentially Undervalued Stocks:")
assert one == two, "The user requested date-only subjects, not times"
assert next_day.startswith("Nov 24, 2026 | Potentially Undervalued Stocks:")
assert next_day != one, "Different trading days should have different subjects"
assert "new/worsened" in one

scanner_src = (ROOT / "regression_scanner/automated_scan.py").read_text()
assert 'if not force_market_day and not market_open_today()' in scanner_src
assert 'send_every_scan = os.getenv("SEND_EVERY_SCAN", "1")' in scanner_src
assert 'if alerts or send_failures or send_every_scan:' in scanner_src
assert 'send_email(subject, body, html_body=html_body)' in scanner_src
assert "scheduled_delivery_exists(" in scanner_src
assert "externally_scheduled=external_schedule" in scanner_src
assert "is_scheduled_trigger(run_event, external_schedule)" in scanner_src
assert 'previous["last_scheduled_delivery_date"]' in scanner_src
assert '[schedule] Today\'s scheduled scan email already delivered.' in scanner_src
mailer = (ROOT / "regression_scanner/emailer.py").read_text()
assert 'message["Message-ID"] = make_msgid()' in mailer
assert 'message["Date"] = format_datetime' in mailer
html = (ROOT / "regression_scanner/email_report.py").read_text()
assert "<details" not in html and 'style="display:none' not in html
print("PASS: morning scheduling, DST, delayed-run suppression, dated subjects and visible HTML")
