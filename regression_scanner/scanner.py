"""Large-cap regression scanner with batch-by-batch progress and local price cache.

CLI examples:
  python scanner.py --min-cap-b 2 --max-cap-b 50 --limit 500 --years 5.5
  python scanner.py --min-cap-b 50 --years 10
  python scanner.py --symbols AAPL MSFT

The dashboard imports scan_market() directly, allowing live table updates.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf
from dotenv import load_dotenv

from storage import data_root
from emailer import send_email
from lookback import DEFAULT_YEARS, regression_sessions, price_history_start
from regression import evaluate, passes_filters
from universe import Stock, large_cap_stocks, validate_market_caps

ROOT = data_root()
STATE_FILE = ROOT / "state" / "alerts.json"
REPORT_FILE = ROOT / "results" / "latest_scan.csv"
SKIP_FILE = ROOT / "results" / "skipped.csv"
SUMMARY_FILE = ROOT / "results" / "summary.json"
def _select_cache_root() -> Path:
    """Keep large, frequently-read price-cache files off OneDrive on Windows.

    A separate cache directory does not change where saved reports, alert state,
    or .env credentials live. This is deliberately independent of data_root().
    """
    override = os.getenv("REGRESSION_SCANNER_CACHE_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        local_appdata = os.getenv("LOCALAPPDATA", "").strip()
        if local_appdata:
            return Path(local_appdata) / "RegressionStockScanner" / "price_history"
    return ROOT / ".cache" / "price_history"


CACHE_ROOT = _select_cache_root()
BATCH = 25             # One user-visible progress update per batch
DOWNLOAD_THREADS = 4  # Limited concurrency: Yahoo may rate-limit aggressive requests
FIELDS = ["session", "ticker", "name", "exchange", "market_cap_b", "close",
          "regression", "sigma", "z_score", "lower_3", "lower_4",
          "slope_per_session", "zone", "new_crossings", "tradingview"]


@dataclass(frozen=True)
class ScanSettings:
    min_cap_b: float = 50.0
    max_cap_b: float | None = None
    years: float = DEFAULT_YEARS
    limit: int | None = 100
    symbols: tuple[str, ...] = ()
    close_delay_minutes: int = 75  # scheduled 5 PM runs can use 45; UI stays 75
    output_dir: Path | None = None  # automated buckets must not overwrite dashboard reports
    hard_timeout_seconds: int | None = None  # subprocess watchdog for scheduled Yahoo batches


@dataclass(frozen=True)
class ScanProgress:
    phase: str  # discovery | scanning | finished
    message: str
    completed: int
    total: int
    rows: list[dict]
    analyzed: int
    skipped: int
    data_errors: int
    cache_hits: int
    summary: dict | None = None


def last_completed_session(close_delay_minutes: int = 75) -> str:
    """Latest NYSE session whose close has passed the requested data buffer."""
    if not 0 <= close_delay_minutes <= 240:
        raise ValueError("close_delay_minutes must be between 0 and 240")
    now = pd.Timestamp.now(tz="UTC")
    ny_today = now.tz_convert("America/New_York").date()
    calendar = mcal.get_calendar("NYSE")
    schedule = calendar.schedule(start_date=ny_today - timedelta(days=20), end_date=ny_today)
    done = schedule[schedule["market_close"] <= now - pd.Timedelta(minutes=close_delay_minutes)]
    if done.empty:
        raise RuntimeError("No completed market session found")
    return done.index[-1].strftime("%Y-%m-%d")


def _cache_path(symbol: str, session: str) -> Path:
    safe = re.sub(r"[^A-Z0-9.^-]", "_", symbol.upper())
    return CACHE_ROOT / session / f"{safe}.csv.gz"


def _read_cache(symbol: str, session: str, requested_start: str) -> pd.Series | None:
    path = _cache_path(symbol, session)
    meta = path.with_suffix(".json")
    if not path.exists() or not meta.exists():
        return None
    try:
        props = json.loads(meta.read_text(encoding="utf-8"))
        # Only reuse if downloaded through a sufficiently early start date.
        if props.get("session") != session or props.get("requested_start", "9999") > requested_start:
            return None
        frame = pd.read_csv(path, index_col=0, parse_dates=True, compression="gzip")
        series = pd.to_numeric(frame["Close"], errors="coerce").dropna()
        series.index = pd.to_datetime(series.index).normalize()
        if series.empty or series.index[-1].strftime("%Y-%m-%d") != session:
            return None
        return series
    except (OSError, ValueError, KeyError, json.JSONDecodeError, pd.errors.ParserError):
        return None


def _write_cache(symbol: str, session: str, requested_start: str, series: pd.Series) -> None:
    path = _cache_path(symbol, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    meta = path.with_suffix(".json")
    try:
        series.rename("Close").to_csv(tmp, header=True, compression="gzip", date_format="%Y-%m-%d")
        tmp.replace(path)
        meta.write_text(json.dumps({"session": session, "requested_start": requested_start}), encoding="utf-8")
    except OSError:
        # Caching is optional; a read-only filesystem must not block scanning.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _download_yahoo_with_hard_timeout(symbols: list[str], start: str, timeout_seconds: int) -> pd.DataFrame:
    """Isolate Yahoo network I/O in a child process so stalled threads can be killed.

    yfinance's request timeout does not bound yf.download's aggregate wait time.
    subprocess.run(timeout=...) terminates the entire child process on timeout.
    Only the scheduled scanner requests this mode; dashboard retains its usual path.
    """
    if timeout_seconds < 5:
        raise ValueError("Batch hard timeout must be at least 5 seconds")
    worker = Path(__file__).with_name("price_batch_worker.py")
    if not worker.is_file():
        raise FileNotFoundError(f"Missing Yahoo watchdog helper: {worker.name}; copy it beside scanner.py")
    with tempfile.TemporaryDirectory(prefix="regression-batch-") as temp:
        output = Path(temp) / "download.pkl.gz"
        payload = {"symbols": symbols, "start": start, "download_threads": DOWNLOAD_THREADS}
        try:
            completed = subprocess.run(
                [sys.executable, str(worker), str(output)],
                input=json.dumps(payload), text=True, capture_output=True,
                timeout=timeout_seconds, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"Yahoo batch of {len(symbols)} stocks exceeded {timeout_seconds}s; "
                "skipping this batch to keep the scan moving"
            ) from exc
        if completed.returncode != 0 or not output.is_file():
            # Never include user-controlled credentials or arbitrary long error logs.
            reason = (completed.stderr or "No output from Yahoo download worker").strip()[-300:]
            raise RuntimeError(f"Yahoo batch worker failed (exit {completed.returncode}): {reason}")
        return pd.read_pickle(output, compression="gzip")



def _run_entire_batch_with_timeout(
    batch: list[Stock], start: str, target: str, timeout_seconds: int,
    *, bypass_cache: bool = False,
) -> tuple[dict[str, pd.Series], int]:
    """Bound the whole worker (cache reads + Yahoo + writes) to a wall-clock limit.

    Do not pass an open stderr *file* to the child on Windows. When the worker
    times out, a descendant retaining that handle can make TemporaryDirectory
    cleanup raise WinError 32, masking the original timeout.
    """
    if timeout_seconds < 5:
        raise ValueError("Batch hard timeout must be at least 5 seconds")
    worker = Path(__file__).with_name("price_batch_worker.py")
    if not worker.is_file():
        raise FileNotFoundError(f"Missing complete-batch watchdog helper: {worker.name}")

    # Best-effort cleanup matters on Windows: a killed worker can still hold
    # an output file briefly, and cleanup must never hide the actual timeout.
    with tempfile.TemporaryDirectory(
        prefix="regression-fullbatch-", ignore_cleanup_errors=True
    ) as scratch:
        directory = Path(scratch)
        request_file = directory / "request.json"
        output_file = directory / "prices.pkl.gz"
        error_file = directory / "worker-error.txt"
        request = {
            "stocks": [
                {"symbol": st.symbol, "name": st.name, "exchange": st.exchange, "cap": st.cap}
                for st in batch
            ],
            "start": start, "target": target, "bypass_cache": bypass_cache,
        }
        request_file.write_text(json.dumps(request), encoding="utf-8")
        cmd = [sys.executable, str(worker), "--full-batch", str(request_file),
               str(output_file), str(error_file)]
        try:
            # Avoid console inheritance on Windows. A worker must never write
            # compressed price data or diagnostic bytes to the VS Code terminal.
            process_options = {}
            if os.name == "nt":
                process_options["creationflags"] = subprocess.CREATE_NO_WINDOW
            completed = subprocess.run(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=timeout_seconds, check=False,
                **process_options,
            )
        except subprocess.TimeoutExpired as exc:
            tickers = ",".join(st.symbol for st in batch)
            raise TimeoutError(
                f"Full batch [{tickers}] exceeded {timeout_seconds}s "
                "while reading cache or downloading Yahoo prices"
            ) from exc
        if completed.returncode != 0 or not output_file.is_file():
            try:
                reason = error_file.read_text(encoding="utf-8", errors="replace")[-250:]
            except OSError:
                reason = "worker did not return a usable result"
            raise RuntimeError(f"Full batch worker exited {completed.returncode}: {reason.strip()}")
        # Result deserialization is in the parent; the worker output is a local
        # trusted file produced by our own script, not untrusted network pickle.
        values = pd.read_pickle(output_file, compression="gzip")
        if not isinstance(values, tuple) or len(values) != 2 or not isinstance(values[0], dict):
            raise RuntimeError("Full batch worker returned an invalid result")
        return values


def _download_batch(batch: list[Stock], start: str, target: str, hard_timeout_seconds: int | None = None, *, bypass_cache: bool = False) -> tuple[dict[str, pd.Series], int]:
    """Return closes for all tickers, using per-session cache where possible."""
    result: dict[str, pd.Series] = {}
    missing: list[Stock] = []
    for stock in batch:
        cached = None if bypass_cache else _read_cache(stock.symbol, target, start)
        if cached is None:
            missing.append(stock)
        else:
            result[stock.symbol] = cached

    cache_hits = len(result)
    if not missing:
        return result, cache_hits

    symbols = [stock.symbol for stock in missing]
    data = None
    # The hard timeout applies to the whole batch, not individual HTTP requests.
    # For normal interactive scans, keep the original in-process code path.
    for attempt in range(1 if hard_timeout_seconds is not None else 2):
        try:
            if hard_timeout_seconds is not None:
                data = _download_yahoo_with_hard_timeout(symbols, start, hard_timeout_seconds)
            else:
                data = yf.download(
                    tickers=symbols, start=start, interval="1d", auto_adjust=False,
                    group_by="ticker", multi_level_index=True, progress=False,
                    threads=DOWNLOAD_THREADS, timeout=20,
                )
            if data is None or data.empty:
                raise RuntimeError("empty Yahoo historical-price response")
            break
        except Exception:
            if hard_timeout_seconds is not None or attempt == 1:
                raise
            time.sleep(2)

    for stock in missing:
        try:
            sub = data[stock.symbol] if isinstance(data.columns, pd.MultiIndex) else data
            if not isinstance(data.columns, pd.MultiIndex) and len(missing) > 1:
                raise KeyError("Expected ticker columns for multiple downloads")
            raw = pd.to_numeric(sub["Close"], errors="coerce").dropna()
            index = pd.to_datetime(raw.index)
            if index.tz is not None:
                index = index.tz_localize(None)
            raw.index = index.normalize()
            raw = raw.loc[:pd.Timestamp(target)]
            result[stock.symbol] = raw
            if not raw.empty and raw.index[-1].strftime("%Y-%m-%d") == target:
                _write_cache(stock.symbol, target, start, raw)
        except (KeyError, ValueError, TypeError):
            result[stock.symbol] = pd.Series(dtype=float)
    return result, cache_hits


def download_closes(batch: list[Stock], start: str, target: str) -> dict[str, pd.Series]:
    """Compatibility entrypoint for direct historical close downloads."""
    return _download_batch(batch, start, target)[0]


def tradingview_url(stock: Stock) -> str:
    from urllib.parse import quote
    exchange = {"NMS": "NASDAQ", "NYQ": "NYSE", "ASE": "AMEX"}.get(stock.exchange, "NASDAQ")
    return "https://www.tradingview.com/chart/?symbol=" + quote(
        f"{exchange}:{stock.symbol.replace('-', '.')}", safe=""
    )


def skipped_record(stock: Stock, reason: str) -> dict[str, str]:
    """Keep the Yahoo screener company name with every skipped ticker."""
    return {"symbol": stock.symbol, "company_name": stock.name or stock.symbol, "reason": reason}


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def _state_read() -> dict:
    if not STATE_FILE.exists():
        return {"sent": {}}
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or not isinstance(state.get("sent"), dict):
        raise ValueError("Invalid state/alerts.json")
    return state


def _state_write(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def scan_market(settings: ScanSettings) -> Iterator[ScanProgress]:
    """Scan in batches and yield intermediate results for Streamlit.

    Any partial rows are for preview only; latest_scan.csv is replaced only
    after all batches finish. Failed/missing downloads remain flagged in summary.
    """
    validate_market_caps(settings.min_cap_b, settings.max_cap_b)
    length = regression_sessions(settings.years)
    if settings.limit is not None and settings.limit < 1:
        raise ValueError("Stock limit must be a positive integer")
    target = last_completed_session(settings.close_delay_minutes)

    yield ScanProgress("discovery", "Finding stocks that meet your market-cap range…",
                       0, 0, [], 0, 0, 0, 0)
    if settings.symbols:
        stocks = [Stock(s.upper(), s.upper(), "NMS", None) for s in dict.fromkeys(settings.symbols)]
        if settings.limit is not None:
            stocks = stocks[:settings.limit]
    else:
        stocks = large_cap_stocks(settings.min_cap_b, settings.max_cap_b, limit=settings.limit)
    if not stocks:
        raise RuntimeError("No matching stocks to scan")

    start = price_history_start(target, settings.years)
    rows: list[dict] = []
    skipped_rows: list[dict] = []
    analyzed = data_errors = cache_hits = completed = 0
    total = len(stocks)
    yield ScanProgress("scanning", f"Found {total:,} stocks. Starting price downloads…",
                       0, total, [], 0, 0, 0, 0)

    for index in range(0, total, BATCH):
        batch = stocks[index:index + BATCH]
        yield ScanProgress("scanning", f"Downloading stocks {index+1:,}–{index+len(batch):,} of {total:,}…",
                           completed, total, sorted(rows, key=lambda row: row["z_score"]),
                           analyzed, len(skipped_rows), data_errors, cache_hits)
        # Scheduled mode has one strictly bounded attempt per 25-stock batch.
        # If cache IO or Yahoo download cannot finish in time, do not retry:
        # mark every ticker in this batch as unscanned and move forward.
        recovery_failures: dict[str, str] = {}
        try:
            if settings.hard_timeout_seconds is not None:
                prices, found_cache = _run_entire_batch_with_timeout(
                    batch, start, target, settings.hard_timeout_seconds
                )
            else:
                # The interactive dashboard retains its original download path.
                prices, found_cache = _download_batch(batch, start, target)
        except Exception as exc:
            prices, found_cache = {}, 0
            failure_reason = f"batch_skipped_{type(exc).__name__}"
            recovery_failures = {stock.symbol: failure_reason for stock in batch}
            yield ScanProgress(
                "scanning",
                f"Download failed for stocks {index+1:,}–{index+len(batch):,}: "
                f"{type(exc).__name__}: {str(exc)[:180]}. "
                f"Skipping {len(batch)} stocks; no retries; coverage incomplete.",
                completed, total, sorted(rows, key=lambda row: row["z_score"]),
                analyzed, len(skipped_rows), data_errors, cache_hits,
            )
        cache_hits += found_cache

        for stock in batch:
            if stock.symbol in recovery_failures:
                skipped_rows.append(skipped_record(stock, recovery_failures[stock.symbol]))
                data_errors += 1
                continue
            series = prices.get(stock.symbol)
            if series is None or series.empty:
                skipped_rows.append(skipped_record(stock, "missing_prices"))
                data_errors += 1
                continue
            if series.index[-1].strftime("%Y-%m-%d") != target:
                skipped_rows.append(skipped_record(stock, f"stale_latest_{series.index[-1].date()}"))
                data_errors += 1
                continue
            if len(series) < length + 1:
                skipped_rows.append(skipped_record(stock, f"insufficient_history_{len(series)}"))
                continue
            try:
                cur, _prev, crossings = evaluate(series.to_numpy(), length)
            except ValueError:
                skipped_rows.append(skipped_record(stock, "invalid_price_data"))
                data_errors += 1
                continue
            analyzed += 1
            if not passes_filters(cur):
                skipped_rows.append(skipped_record(stock, "trend_or_band_filter"))
                continue
            rows.append({
                "session": target, "ticker": stock.symbol, "name": stock.name,
                "exchange": stock.exchange,
                "market_cap_b": round(stock.cap / 1e9, 2) if stock.cap is not None else None,
                "close": round(cur.close, 4), "regression": round(cur.line, 4),
                "sigma": round(cur.sigma, 4), "z_score": round(cur.z, 4),
                "lower_3": round(cur.lower3, 4), "lower_4": round(cur.lower4, 4),
                "slope_per_session": round(cur.slope, 8),
                "zone": "-4σ or lower" if cur.z <= -4 else ("-3σ to -4σ" if cur.z <= -3 else "above -3σ"),
                "new_crossings": ", ".join(crossings),
                "tradingview": tradingview_url(stock),
            })
        completed += len(batch)
        yield ScanProgress("scanning", f"Processed {completed:,} / {total:,} stocks",
                           completed, total, sorted(rows, key=lambda row: row["z_score"]),
                           analyzed, len(skipped_rows), data_errors, cache_hits)
        if index + BATCH < total:
            time.sleep(0.2)

    rows.sort(key=lambda row: row["z_score"])
    high_error_rate = data_errors > max(3, int(0.20 * total))
    summary = {
        "session": target, "candidates": total, "eligible": len(rows), "analyzed": analyzed,
        "filters": {
            "min_cap_b": settings.min_cap_b, "max_cap_b": settings.max_cap_b,
            "regression_years": settings.years, "regression_sessions": length,
            "custom_symbols": bool(settings.symbols), "top_n_limit": settings.limit,
        },
        "download_or_data_errors": data_errors, "skipped": len(skipped_rows),
        "cache_hits": cache_hits, "new_crossing_rows": sum(bool(row["new_crossings"]) for row in rows),
        "complete": data_errors == 0 and analyzed > 0,
        "serious_data_failures": high_error_rate,
    }
    # Keep the previous successful report if nearly all downloads failed.
    if analyzed == 0:
        raise RuntimeError("No valid price histories found. Latest successful report was not overwritten.")
    report_dir = Path(settings.output_dir) if settings.output_dir is not None else ROOT / "results"
    write_csv(report_dir / "latest_scan.csv", rows, FIELDS)
    write_csv(report_dir / "skipped.csv", skipped_rows, ["symbol", "company_name", "reason"])
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    yield ScanProgress("finished", "Scan finished" if summary["complete"] else "Scan finished with data-quality warnings",
                       completed, total, list(rows), analyzed, len(skipped_rows), data_errors, cache_hits, summary)


def send_alerts(rows: list[dict], target: str) -> None:
    state = _state_read()
    fresh = []
    for row in rows:
        for band in ("-3σ", "-4σ"):
            if band in row["new_crossings"].split(", "):
                key = f"{row['session']}|{row['ticker']}|{band}"
                if key not in state["sent"]:
                    fresh.append((key, row, band))
    if not fresh:
        print("No newly crossed bands to email.")
        return
    lines = [f"New channel crossings for {target}", ""]
    for _, row, band in fresh:
        lines.extend([f"{row['ticker']}: {band}, Z={row['z_score']:.2f}", row["tradingview"], ""])
    send_email(f"[Regression Scanner] {len(fresh)} new crossing(s)", "\n".join(lines))
    for key, _, _ in fresh:
        state["sent"][key] = datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds")
    _state_write(state)


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Scan daily regression channels")
    parser.add_argument("--symbols", nargs="+", help="Diagnostic tickers (bypass cap/listing checks)")
    parser.add_argument("--limit", type=int, help="Top N stocks by market cap within the requested range")
    parser.add_argument("--min-cap-b", type=float, default=50.0)
    parser.add_argument("--max-cap-b", type=float)
    parser.add_argument("--years", type=float, default=DEFAULT_YEARS)
    parser.add_argument("--alert", action="store_true", help="Optional email alerts (not used by dashboard)")
    parser.add_argument("--test-email", action="store_true")
    args = parser.parse_args()
    if args.test_email:
        send_email("[Regression Scanner] Test", "SMTP test")
        print("Test email sent")
        return
    if args.alert and (args.symbols or args.limit):
        parser.error("--alert requires a complete universe scan without --symbols or --limit")
    settings = ScanSettings(args.min_cap_b, args.max_cap_b, args.years, args.limit, tuple(args.symbols or ()))
    last = None
    for event in scan_market(settings):
        if event.phase == "scanning" and event.completed == last:
            continue
        print(f"[{event.phase}] {event.message}", flush=True)
        last = event.completed
    if event.summary:
        print("Summary:", json.dumps(event.summary, indent=2))
        print("Report:", REPORT_FILE)
        if args.alert:
            if not event.summary["complete"]:
                raise RuntimeError("Incomplete scan: notifications disabled to avoid unreliable alerts")
            send_alerts(event.rows, event.summary["session"])
        if event.summary["serious_data_failures"]:
            raise RuntimeError("Significant missing/stale price data: inspect results/skipped.csv")


if __name__ == "__main__":
    main()
