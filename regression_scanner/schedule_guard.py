"""Prefer 8:30 a.m. Eastern email scans while recovering delayed crons.

GitHub Actions has repeatedly delivered morning UTC cron expressions in
the evening (including 7:12/8:07 p.m. Eastern on Nov 23, 2026). Native
scheduled runs therefore remain eligible later on the same Eastern weekday,
but not before the morning window or on weekends. Only the DST-appropriate
cron is accepted. Externally scheduled workflow dispatches remain restricted
to the morning. Manual runs are still permitted any time; live-report
deduplication is enforced in automated_scan.py.
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
# Native timezone-aware schedules (GitHub Actions, March 2026 onward).
LOCAL_CRONS = ("30 8 * * 1-5",)


def is_scheduled_trigger(event: str, externally_scheduled: bool = False) -> bool:
    """Identify native schedule and authenticated external recurring dispatch."""
    return event == "schedule" or (event == "workflow_dispatch" and externally_scheduled)


def should_send(
    event: str, cron: str, now_utc: datetime | None = None,
    externally_scheduled: bool = False,
) -> bool:
    """Prefer weekday 8:30 ET; accept GitHub's severely delayed native cron.

    Manual dispatch is always allowed. External scheduler requests must be in
    the intended morning window. Native GitHub cron is checked for correct
    DST and weekday but may arrive in the evening. A late same-day report is
    preferable to never sending one; daily dedup remains in automated_scan.
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
    if event == "workflow_dispatch":
        # The external scheduler is expected to dispatch around 8:30 a.m.
        # Do not accept stray external requests in the evening.
        return (8 * 60 + 20) <= minutes < (10 * 60 + 30)
    expected = (
        (EDT_CRON, EDT_BACKUP_CRON)
        if eastern.dst() != timedelta(0)
        else (EST_CRON, EST_BACKUP_CRON)
    )
    # GitHub has repeatedly executed 08:30 ET cron expressions 10+ HOURS
    # late, at 7:12/8:07 PM ET on Nov 23, 2026. Discarding them meant no
    # email all day. Allow matching native cron events later on the same ET
    # weekday; the daily delivery marker prevents duplicate digests.
    return cron in (*expected, *LOCAL_CRONS) and minutes >= (8 * 60 + 20)


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


def daily_delivery_exists(state: dict, local_time: datetime) -> bool:
    """One successful live regression digest per America/New_York date.

    Unlike scheduled_delivery_exists, this also includes manually triggered
    LIVE reports. SMTP test emails and dry runs never set delivery markers.
    Older state files are compatible via the existing last_delivery timestamp.
    """
    day = local_time.astimezone(ET).date().isoformat()
    if state.get("last_daily_delivery_date") == day:
        return True
    if state.get("last_scheduled_delivery_date") == day:
        return True
    prior = state.get("last_delivery")
    if isinstance(prior, str) and prior:
        try:
            sent = datetime.fromisoformat(prior.replace("Z", "+00:00"))
            if sent.tzinfo is not None:
                return sent.astimezone(ET).date().isoformat() == day
        except ValueError:
            pass
    return False


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
    if allowed and event == "schedule" and local.hour >= 10:
        print(
            "[schedule] GitHub delivered the morning cron late. "
            "Proceeding with one best-effort trading-day digest.",
            flush=True,
        )
    if not allowed and is_scheduled_trigger(event, external):
        print(
            "[schedule] Skip: incorrect weekday/DST cron or "
            "outside the permitted dispatch window.",
            flush=True,
        )
    destination = os.environ["GITHUB_OUTPUT"]
    with Path(destination).open("a", encoding="utf-8") as out:
        out.write(f"run_scan={'true' if allowed else 'false'}\n")


if __name__ == "__main__":
    main()
