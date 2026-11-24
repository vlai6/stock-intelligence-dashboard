"""Five-bucket regression scan with deduplicated email alerts.

Runs under the main dashboard's weekday GitHub Actions schedule or manually.
The optional AI summary uses the separately billed OpenAI API, never the ChatGPT UI.

Usage:
  python automated_scan.py --test-email
  python automated_scan.py --dry-run --limit-per-bucket 10
  python automated_scan.py
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal
from dotenv import load_dotenv

from emailer import send_email
from email_report import formatted_signal, plain_report, html_report, grouped_signals
from scanner import ScanSettings, scan_market
from intrinsic_value import enrich_signals, unavailable, get_assumptions
from storage import data_root
from schedule_guard import daily_delivery_exists, is_scheduled_trigger

ET = ZoneInfo("America/New_York")
ROOT = data_root()
AUTOMATION_ROOT = ROOT / "scheduled_scans"
STATE_PATH = ROOT / "state" / "scheduled_alerts.json"
EMAIL_SNAPSHOT_PATH = ROOT / "state" / "email_watchlist_snapshot.json"
LOCK_PATH = ROOT / "state" / "scheduled_scan.lock"

# No Top N limit on production scans. A market-cap boundary may theoretically
# appear in two adjacent buckets; the aggregate report deduplicates by ticker.
BUCKETS = [
    ("2-5B", 2.0, 5.0),
    ("5-10B", 5.0, 10.0),
    ("10-25B", 10.0, 25.0),
    ("25-50B", 25.0, 50.0),
    ("50B+", 50.0, None),
]


def zone_for(z: float, bucket: str = "") -> str | None:
    """Deeper zone takes priority; large caps qualify from −2.75σ."""
    if z <= -4.0:
        return "-4σ"
    if z <= -3.0:
        return "-3σ"
    if bucket == "50B+" and z <= -2.75:
        return "-2.75σ"
    return None


def _level_rank(level: str | None) -> int:
    return {"-2.75σ": 1, "-3σ": 2, "-4σ": 3}.get(level, 0)


def new_alerts(previous: dict[str, str], current: dict[str, dict]) -> list[dict]:
    """Alert on first qualification or move to a more negative threshold."""
    found: list[dict] = []
    for symbol, row in sorted(current.items(), key=lambda x: x[1]["z_score"]):
        zone = zone_for(float(row["z_score"]), row.get("bucket", ""))
        if zone and _level_rank(zone) > _level_rank(previous.get(symbol)):
            found.append({**row, "alert_level": zone})
    return found


def prime_opportunity(row: dict) -> bool:
    """Priority research heuristic; not a verified buying opportunity."""
    z = float(row["z_score"])
    return z <= -4.0 or (row.get("bucket") == "50B+" and z <= -3.0)


def email_subject(signals: list[dict], alerts: list[dict], *,
                  run_at: datetime | None = None) -> str:
    """Add the Eastern calendar date without a time to the email subject.

    Different trading days have distinct subjects. Gmail may still group
    multiple manually generated reports on the same day.
    """
    from collections import Counter
    cap_order = {name: i for i, (name, _, _) in enumerate(BUCKETS)}
    grouped = Counter((row.get("bucket", ""), zone_for(float(row["z_score"]), row.get("bucket", "")))
                      for row in signals if prime_opportunity(row))
    fragments = []
    for (bucket, level), count in sorted(grouped.items(),
                                         key=lambda item: (cap_order.get(item[0][0], 99), -_level_rank(item[0][1]))):
        fragments.append(f"{count} Opp @ ${bucket} at {level.replace('-', '−')}")
    headline = "Potentially Undervalued Stocks: " + (", ".join(fragments) if fragments else "None today")
    sent_at = (run_at or datetime.now(ET)).astimezone(ET)
    stamp = sent_at.strftime("%b %d, %Y")
    return f"{stamp} | {headline} | {len(alerts)} new/worsened"


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {"active_levels": {}, "last_delivery": None}
    data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("active_levels"), dict):
        raise ValueError("Invalid scheduled alert state — refusing to resend old alerts")
    return data


def write_state(data: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE_PATH)


def build_emailed_watchlist_snapshot(*, started: datetime, sent_at: datetime,
                                    signals: list[dict], alerts: list[dict],
                                    failed: list[str], complete: bool) -> dict:
    """Mirror the stock rows ACTUALLY included in the HTML/plain email (max 100).

    The email groups by bucket and sorts by Z-score; it does NOT only show new
    band-crossings. This public-in-repository snapshot contains NO credentials.
    """
    displayed = [row for _, rows in grouped_signals(signals) for row in rows][:100]
    newly_triggered = {str(row.get("ticker", "")).upper() for row in alerts}
    stocks = []
    for row in displayed:
        ticker = str(row["ticker"]).strip().upper()
        item = {
            "ticker": ticker,
            "session": str(row.get("session") or ""),
            "z_score": float(row["z_score"]),
            "bucket": str(row.get("bucket") or ""),
            "alert_level": str(row.get("alert_level") or ""),
            "new_or_worsened": ticker in newly_triggered,
        }
        stocks.append(item)
    return {
        "schema_version": 2,
        "last_email": {
            "sent_at": sent_at.isoformat(),
            "scan_started_at": started.isoformat(),
            "stocks": stocks,
            "displayed_count": len(stocks),
            "total_active_signals": len(signals),
            "new_or_worsened_count": len(alerts),
            "scan_complete": bool(complete),
            "failed_buckets": list(failed),
        },
    }


def write_email_snapshot(payload: dict) -> None:
    """Write a separate file for publishing; NEVER overwrite deduplication state."""
    EMAIL_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = EMAIL_SNAPSHOT_PATH.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(EMAIL_SNAPSHOT_PATH)


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["session", "bucket", "ticker", "name", "market_cap_b", "close", "regression",
              "z_score", "lower_3", "lower_4", "alert_level", "tradingview",
              "intrinsic_value", "upside_downside_pct", "margin_of_safety_pct",
              "valuation_method", "valuation_note", "valuation_as_of"]
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def optional_ai_summary(signals: list[dict]) -> str:
    """Only runs when explicitly enabled and an API key is configured."""
    if os.getenv("ENABLE_AI_SUMMARY", "0").lower() not in ("1", "true", "yes"):
        return "AI summary disabled. Set ENABLE_AI_SUMMARY=1 and OPENAI_API_KEY to enable paid API analysis."
    if not os.getenv("OPENAI_API_KEY"):
        return "AI summary unavailable: OPENAI_API_KEY is not configured."
    if not signals:
        return "No new signals to analyze."
    try:
        from openai import OpenAI
        client = OpenAI(timeout=35, max_retries=1)
        supplied = [{key: row.get(key) for key in
                     ("ticker", "name", "bucket", "session", "market_cap_b", "close", "regression",
                      "z_score", "lower_3", "lower_4", "slope_per_session",
                      "intrinsic_value", "upside_downside_pct", "margin_of_safety_pct",
                      "valuation_note", "valuation_as_of")}
                    for row in signals[:12]]
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            instructions=(
                "You are a cautious quantitative research assistant. These are numerical scan results only. "
                "For each symbol, provide a short factual assessment of deviation vs regression and a concrete "
                "due-diligence question. Clearly distinguish mathematical signals from investment recommendations. "
                "Intrinsic values, when provided, are rough scenario-based five-year DCF outputs, not verified fair values. "
                "Do not invent earnings, catalysts, news, analyst sentiment, fundamentals or evidence not supplied. "
                "Do not claim that crossing a standard deviation implies a normal-distribution probability. "
                "Limit each company to 2 sentences. No trading instructions."
            ),
            input=json.dumps(supplied),
            max_output_tokens=900,
        )
        note = "" if len(signals) <= 12 else f"\n(Analyzed 12 of {len(signals)} new signals; full list above.)"
        return (response.output_text or "No AI response returned.") + note
    except Exception as exc:
        # Mail the numeric signals even if the paid API is down; never print secrets.
        return f"AI analysis unavailable ({type(exc).__name__}). Numeric signals are listed above."


def market_open_today() -> bool:
    now = datetime.now(ET).date()
    return len(mcal.get_calendar("NYSE").valid_days(start_date=now, end_date=now)) > 0


def _lock():
    """Exclusive process lock; stale locks left by crashes expire after 6 hours."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists() and time.time() - LOCK_PATH.stat().st_mtime > 6 * 3600:
        LOCK_PATH.unlink(missing_ok=True)
    try:
        fd = os.open(LOCK_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(str(os.getpid()))
    except FileExistsError:
        raise RuntimeError("Another scheduled scanner is running (lock exists).")


def execute(*, dry_run: bool = False, limit: int | None = None, force_market_day: bool = False) -> dict:
    load_dotenv(ROOT / ".env")
    if not force_market_day and not market_open_today():
        print("NYSE closed today: skipping scheduled scan.", flush=True)
        return {"skipped": "NYSE closed"}
    if not dry_run:
        needs = [x for x in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "ALERT_TO")
                 if not os.getenv(x)]
        if needs:
            raise RuntimeError(f"Missing SMTP .env values: {', '.join(needs)}. Use --dry-run to test without email.")
    # A limited scan must never affect the real alert state.
    if limit is not None and not dry_run:
        raise ValueError("--limit-per-bucket only allowed with --dry-run")
    _lock()
    try:
        started = datetime.now(ET)
        run_event = os.getenv("GITHUB_EVENT_NAME", "")
        external_schedule = os.getenv("EXTERNAL_SCHEDULED", "").lower() == "true"
        if not dry_run and daily_delivery_exists(read_state(), started):
            print(
                "[mail] Today's regression digest has already been sent. "
                "Skipping duplicate live scan and email.",
                flush=True,
            )
            return {"skipped": "daily regression digest already sent"}
        run_id = started.strftime("%Y%m%d-%H%M%S")
        folder = AUTOMATION_ROOT / run_id
        all_results = []
        reports = []
        for name, lower, upper in BUCKETS:
            print(f"[{name}] Starting market-cap scan...", flush=True)
            dest = folder / name
            settings = ScanSettings(
                min_cap_b=lower, max_cap_b=upper,
                years=float(os.getenv("AUTO_REGRESSION_YEARS", "10.0")),
                limit=limit, output_dir=dest, close_delay_minutes=45,
                # Enforce the requested 20-second maximum even if the user's
                # existing .env still contains the old 90-second value.
                hard_timeout_seconds=min(20, max(5, int(os.getenv("AUTO_BATCH_HARD_TIMEOUT_SECONDS", "20")))),
            )
            try:
                final = None
                started_bucket = time.monotonic()
                last_progress = 0
                for progress in scan_market(settings):
                    if progress.phase == "finished":
                        final = progress
                    elif progress.phase == "scanning" and progress.message.startswith("Download failed for stocks"):
                        print(f"[{name}] WARNING: {progress.message}", flush=True)
                    elif progress.phase == "scanning" and progress.message.startswith("Downloading stocks "):
                        # Print BEFORE starting the batch, so an apparent freeze is traceable.
                        print(f"[{name}] {progress.message}", flush=True)
                    elif progress.phase == "scanning" and progress.completed > last_progress:
                        # At most one line per 25-stock batch. This distinguishes
                        # slow Yahoo requests/cache reads from a stopped process.
                        last_progress = progress.completed
                        duration = time.monotonic() - started_bucket
                        print(
                            f"[{name}] {progress.completed:,}/{progress.total:,} "
                            f"analyzed={progress.analyzed:,} "
                            f"errors={progress.data_errors:,} "
                            f"cache_hits={progress.cache_hits:,} "
                            f"elapsed={duration:.0f}s",
                            flush=True,
                        )
                if final is None or not final.summary:
                    raise RuntimeError("No completed scan summary")
                for row in final.rows:
                    row = dict(row)
                    row["bucket"] = name
                    all_results.append(row)
                reports.append({"bucket": name, "ok": bool(final.summary.get("complete")), **final.summary})
                print(f"[{name}] analyzed={final.analyzed} signals={sum(zone_for(float(r['z_score']), name) is not None for r in final.rows)} "
                      f"data_errors={final.data_errors}", flush=True)
            except Exception as exc:
                print(f"[{name}] ERROR: {type(exc).__name__}: {exc}", flush=True)
                reports.append({"bucket": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
            time.sleep(1)  # modest pause between requests; no guarantee against rate limits

        unique: dict[str, dict] = {}
        for row in all_results:
            unique.setdefault(row["ticker"], row)
        active = {sym: row for sym, row in unique.items() if zone_for(float(row["z_score"]), row.get("bucket", ""))}
        failed = [r["bucket"] for r in reports if not r.get("ok")]
        complete = len(reports) == len(BUCKETS) and not failed
        previous = read_state() if not dry_run else {"active_levels": {}, "last_delivery": None}
        ordered = [{**row, "alert_level": zone_for(float(row["z_score"]), row.get("bucket", ""))}
                   for row in sorted(active.values(), key=lambda r: r["z_score"])]
        # Cap slow Yahoo DCF fetches per workflow configuration. This changes
        # valuation coverage only; it NEVER removes any regression-qualified stock.
        if os.getenv("ENABLE_INTRINSIC_VALUE", "1").lower() in ("1", "true", "yes"):
            try:
                valuation_limit = max(0, int(os.getenv("MAX_INTRINSIC_VALUATIONS_PER_RUN", "30")))
                signal_rows = enrich_signals(ordered, limit=valuation_limit)
            except Exception as exc:
                print(f"[valuation] unavailable: {type(exc).__name__}", flush=True)
                signal_rows = [{**row, **unavailable(f"Valuation unavailable ({type(exc).__name__})")}
                               for row in ordered]
        else:
            signal_rows = [{**row, **unavailable("Intrinsic valuation disabled")}
                           for row in ordered]
        valued_active = {row["ticker"]: row for row in signal_rows}
        alerts = new_alerts(previous["active_levels"], valued_active)
        write_rows(folder / "active_signals.csv", signal_rows)
        (folder / "coverage.json").write_text(json.dumps({"buckets": reports, "complete": complete,
                  "signal_count": len(signal_rows), "new_alert_count": len(alerts),
                  "valuation_count": sum(r.get("intrinsic_value") is not None for r in signal_rows)}, indent=2), encoding="utf-8")
        print(f"Active: {len(signal_rows)}, new/worsened: {len(alerts)}, failed buckets: {failed}", flush=True)
        if dry_run:
            print("DRY RUN: No email was sent and deduplication state was not modified.", flush=True)
            return {"signals": signal_rows, "alerts": alerts, "complete": complete, "folder": str(folder)}

        # Always report failed bucket coverage; send signal alerts only from checked buckets.
        # Do not clear prior alert states if any bucket is missing or incomplete.
        send_failures = bool(failed)
        send_every_scan = os.getenv("SEND_EVERY_SCAN", "1").lower() in ("1", "true", "yes")
        email_sent_at = None
        if alerts or send_failures or send_every_scan:
            try:
                assumptions = (get_assumptions()
                               if os.getenv("ENABLE_INTRINSIC_VALUE", "1").lower() in ("1", "true", "yes")
                               else None)
            except (ValueError, TypeError):
                assumptions = None
            ai_enabled = os.getenv("ENABLE_AI_SUMMARY", "0").lower() in ("1", "true", "yes")
            ai_text = optional_ai_summary(alerts or signal_rows) if ai_enabled and signal_rows else None
            report_args = dict(started=started, signals=signal_rows, alerts=alerts,
                               failed=failed, reports=reports,
                               years=float(os.getenv("AUTO_REGRESSION_YEARS", "10.0")),
                               assumptions=assumptions, ai_summary=ai_text)
            body = plain_report(**report_args)
            html_body = html_report(**report_args)
            subject = email_subject(signal_rows, alerts)
            print(f"[mail] SMTP send initiated at {datetime.now(ET).isoformat()}", flush=True)
            send_email(subject, body, html_body=html_body)
            email_sent_at = datetime.now(ET)
            print(f"[mail] Email sent successfully at {email_sent_at.isoformat()}", flush=True)
            # Tell GitHub the digest was accepted by SMTP immediately, so a
            # later cache/publish failure cannot trigger a SECOND email.
            output_path = os.getenv("GITHUB_OUTPUT")
            if output_path:
                try:
                    with open(output_path, "a", encoding="utf-8") as output:
                        output.write("daily_report_sent=true\\n".replace("\\n", "\n"))
                except OSError:
                    print("[mail] Could not set GitHub delivery output.", flush=True)

        # Mark delivered alerts as active only after email succeeds. An unexpected
        # crash between SMTP delivery and state save could cause a duplicate email.
        if complete:
            previous["active_levels"] = {sym: zone_for(float(row["z_score"]), row.get("bucket", "")) for sym, row in active.items()}
        else:
            previous["active_levels"].update(
                {sym: zone_for(float(row["z_score"]), row.get("bucket", "")) for sym, row in active.items()})
        if email_sent_at is not None:
            previous["last_delivery"] = email_sent_at.isoformat()
            previous["last_daily_delivery_date"] = (
                email_sent_at.astimezone(ET).date().isoformat()
            )
            if is_scheduled_trigger(run_event, external_schedule):
                previous["last_scheduled_delivery_date"] = (
                    email_sent_at.astimezone(ET).date().isoformat()
                )
        write_state(previous)
        if email_sent_at is not None:
            payload = build_emailed_watchlist_snapshot(
                started=started, sent_at=email_sent_at,
                signals=signal_rows, alerts=alerts, failed=failed, complete=complete,
            )
            write_email_snapshot(payload)
            print(f"[watchlist] Snapshot ready: {len(payload['last_email']['stocks'])} "
                  f"emailed tickers, source {EMAIL_SNAPSHOT_PATH.name}", flush=True)
        return {"signals": signal_rows, "alerts": alerts, "complete": complete, "folder": str(folder)}
    finally:
        LOCK_PATH.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scheduled five-bucket regression scanner")
    parser.add_argument("--test-email", action="store_true", help="Send SMTP test without scanning")
    parser.add_argument("--dry-run", action="store_true", help="Scan, save report, but do not email or write alert state")
    parser.add_argument("--limit-per-bucket", type=int, help="Diagnostic Top N for each bucket; requires --dry-run")
    parser.add_argument("--force-market-day", action="store_true", help="Ignore market holiday check for diagnostics")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if args.test_email:
        stamp = datetime.now(ET).strftime("%b %d, %Y")
        send_email(f"[Regression Scanner] SMTP test — {stamp}",
                   "Your regression scanner email settings work.")
        print("Test email sent.")
        return
    execute(dry_run=args.dry_run, limit=args.limit_per_bucket, force_market_day=args.force_market_day)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise
