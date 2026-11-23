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
# A second chance if GitHub drops/delays the normal 8:30 cron.
EDT_BACKUP_CRON = "55 12 * * 1-5"
EST_BACKUP_CRON = "55 13 * * 1-5"


def is_scheduled_trigger(event: str, externally_scheduled: bool = False) -> bool:
    """Identify native schedule and authenticated external recurring dispatch."""
    return event == "schedule" or (event == "workflow_dispatch" and externally_scheduled)


def should_send(
    event: str, cron: str, now_utc: datetime | None = None,
    externally_scheduled: bool = False,
) -> bool:
    """Gate scheduled notifications to weekday mornings in New York.

    Manual dispatch is always allowed. External scheduler requests are checked
    against the same ET morning window as native cron, but are independent of
    which UTC cron expression GitHub emitted.
    """
    if event == "workflow_dispatch" and not externally_scheduled:
        return True
    if not is_scheduled_trigger(event, externally_scheduled):
        return False
    utc_now = now_utc or datetime.now(timezone.utc)
    if utc_now.tzinfo is None:
        raise ValueError("An aware UTC timestamp is required")
    eastern = utc_now.astimezone(ET)
    if eastern.weekday() >= 5:
        return False
    minutes = eastern.hour * 60 + eastern.minute
    if not (8 * 60 + 20) <= minutes < (10 * 60 + 30):
        return False
    if event == "workflow_dispatch":
        return True
    expected = (
        (EDT_CRON, EDT_BACKUP_CRON)
        if eastern.dst() != timedelta(0)
        else (EST_CRON, EST_BACKUP_CRON)
    )
    return cron in expected


def scheduled_delivery_exists(
    state: dict, local_time: datetime, event: str,
    externally_scheduled: bool = False,
) -> bool:
    """Prevent native and external daily triggers from emailing twice.

    Manual dispatch still works independently and does not set a scheduled
    delivery marker. The marker is set only after successful SMTP delivery.
    """
    if not is_scheduled_trigger(event, externally_scheduled):
        return False
    return state.get("last_scheduled_delivery_date") == (
        local_time.astimezone(ET).date().isoformat()
    )


def main() -> None:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    cron = os.environ.get("GITHUB_EVENT_SCHEDULE", "")
    utc_now = datetime.now(timezone.utc)
    local = utc_now.astimezone(ET)
    external = os.environ.get("EXTERNAL_SCHEDULED", "").lower() == "true"
    allowed = should_send(event, cron, utc_now, externally_scheduled=external)
    print(f"[schedule] event={event} cron={cron!r} external={external}", flush=True)
    print(f"[schedule] actual Eastern={local.isoformat(timespec='seconds')}", flush=True)
    print(f"[schedule] allowed={'yes' if allowed else 'no'}", flush=True)
    if not allowed and is_scheduled_trigger(event, external):
        print("[schedule] Skip: outside weekday 08:20–10:30 AM ET window or wrong DST cron.", flush=True)
    destination = os.environ["GITHUB_OUTPUT"]
    with Path(destination).open("a", encoding="utf-8") as out:
        out.write(f"run_scan={'true' if allowed else 'false'}\n")


if __name__ == "__main__":
    main()
