"""Keep scheduled email scans in the Eastern morning, with correct DST.

GitHub's timezone-aware cron unexpectedly fired the legacy scanner at
4:26 PM EST on Nov 20, 2026. The migrated dashboard instead uses UTC
expressions at 12:30/13:30 UTC and runs only the expression corresponding
to 8:30 AM in New York. Late afternoon schedule deliveries are skipped.
Manual workflow_dispatch runs are always permitted.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
EDT_CRON = "30 12 * * 1-5"
EST_CRON = "30 13 * * 1-5"


def should_send(event: str, cron: str, now_utc: datetime | None = None) -> bool:
    """Return True only for the intended weekday ET morning scan.

    A 2-hour grace window permits ordinary runner queueing and scan setup.
    It deliberately does NOT turn a wildly delayed 4 PM schedule into an
    afternoon email. A missed run is visible in Actions as a gate skip.
    """
    if event == "workflow_dispatch":
        return True
    if event != "schedule":
        return False
    utc_now = now_utc or datetime.now(timezone.utc)
    if utc_now.tzinfo is None:
        raise ValueError("An aware UTC timestamp is required")
    eastern = utc_now.astimezone(ET)
    if eastern.weekday() >= 5:
        return False
    expected = EDT_CRON if eastern.dst() != timedelta(0) else EST_CRON
    minutes = eastern.hour * 60 + eastern.minute
    return cron == expected and (8 * 60 + 20) <= minutes < (10 * 60 + 30)


def main() -> None:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    cron = os.environ.get("GITHUB_EVENT_SCHEDULE", "")
    utc_now = datetime.now(timezone.utc)
    local = utc_now.astimezone(ET)
    allowed = should_send(event, cron, utc_now)
    print(f"[schedule] event={event} cron={cron!r}", flush=True)
    print(f"[schedule] actual Eastern={local.isoformat(timespec='seconds')}", flush=True)
    print(f"[schedule] allowed={'yes' if allowed else 'no'}", flush=True)
    if not allowed and event == "schedule":
        print("[schedule] Skip: wrong DST cron or outside 08:20–10:30 AM ET window.", flush=True)
    destination = os.environ["GITHUB_OUTPUT"]
    with Path(destination).open("a", encoding="utf-8") as out:
        out.write(f"run_scan={'true' if allowed else 'false'}\n")


if __name__ == "__main__":
    main()
