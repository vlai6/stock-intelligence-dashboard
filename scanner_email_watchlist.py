"""Read the scanner's *already emailed* daily crossings from its GitHub history.

No extra scanner run, Gmail access, emails, or scheduled tasks are performed here.
The original regression scanner commits state/alerts.json after successful email.
"""
from __future__ import annotations

import base64
import csv
import io
import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import streamlit as st

ET = ZoneInfo("America/New_York")
AUTO_LIST_NAME = "Weekday Scanner Alerts"
REPO_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
TICKER_PATTERN = re.compile(r"[A-Z0-9^][A-Z0-9.\-^=]{0,14}\Z")
MAX_GITHUB_JSON_BYTES = 2_000_000


@dataclass
class AlertSnapshot:
    symbols: list[str] = field(default_factory=list)
    latest_email_date: str = ""
    latest_email_time: str = ""
    session_by_symbol: dict[str, str] = field(default_factory=dict)
    bands_by_symbol: dict[str, str] = field(default_factory=dict)
    emailed_z_by_symbol: dict[str, float] = field(default_factory=dict)
    source: str = ""
    configured: bool = False
    error: str = ""


def _configuration(key: str) -> str:
    value = os.getenv(key, "").strip()
    if value:
        return value
    try:
        # Access can throw if local secrets.toml does not exist.
        return str(st.secrets.get(key, "") or "").strip()
    except (OSError, KeyError, ValueError, RuntimeError):
        return ""


def configured_repo() -> str:
    return _configuration("SCANNER_GITHUB_REPOSITORY")


@st.cache_data(ttl=300, show_spinner=False)
def _read_github_contents(repo: str, branch: str, _token: str) -> dict:
    """Fetch GitHub repository file contents. Token isn't part of cache key/logs."""
    headers = {"Accept": "application/vnd.github+json"}
    if _token:
        headers["Authorization"] = "Bearer " + _token
    response = requests.get(
        f"https://api.github.com/repos/{repo}/contents/state/alerts.json",
        headers=headers, params={"ref": branch}, timeout=12,
    )
    if response.status_code != 200:
        raise ValueError(
            f"GitHub returned HTTP {response.status_code} reading state/alerts.json. "
            "Check repository name, branch, and read-only token permissions."
        )
    data = response.json()
    if not isinstance(data, dict) or data.get("encoding") != "base64":
        raise ValueError("GitHub did not return a base64-encoded scanner history file.")
    contents = data.get("content", "")
    if not isinstance(contents, str) or len(contents) > (MAX_GITHUB_JSON_BYTES * 2):
        raise ValueError("Scanner alert history is unexpectedly large.")
    raw = base64.b64decode(contents, validate=False)
    if len(raw) > MAX_GITHUB_JSON_BYTES:
        raise ValueError("Scanner alert history exceeds the 2 MB read limit.")
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Scanner alert history is not an object.")
    return payload


def _parse_last_email_snapshot(payload: dict) -> AlertSnapshot | None:
    """Read the ACTUAL emailed stock list; unlike crossing history, it includes
    existing qualifying signals and the large-cap -2.75 sigma band.
    """
    record = payload.get("last_email")
    if not isinstance(record, dict) or not isinstance(record.get("stocks"), list):
        return None  # Legacy alert history uses the older `sent` dictionary.

    raw_time = str(record.get("sent_at") or "")
    try:
        timestamp = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        timestamp = timestamp.replace(tzinfo=ET) if timestamp.tzinfo is None else timestamp.astimezone(ET)
    except (ValueError, OverflowError):
        raise ValueError("Last emailed watchlist has an invalid sent_at timestamp")

    symbols, sessions, bands, scores = [], {}, {}, {}
    for entry in record["stocks"][:500]:
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker") or "").strip().upper()
        if not TICKER_PATTERN.fullmatch(ticker) or ticker in sessions:
            continue
        symbols.append(ticker)
        sessions[ticker] = str(entry.get("session") or "")
        bands[ticker] = str(entry.get("alert_level") or "")
        try:
            score = float(entry.get("z_score"))
            if math.isfinite(score):
                scores[ticker] = score
        except (ValueError, TypeError):
            pass
    return AlertSnapshot(
        symbols=symbols,
        latest_email_date=timestamp.date().isoformat(),
        latest_email_time=timestamp.strftime("%b %d, %Y at %I:%M %p ET"),
        session_by_symbol=sessions,
        bands_by_symbol=bands,
        emailed_z_by_symbol=scores,
        configured=True,
    )


def parse_sent_alert_history(payload: dict) -> AlertSnapshot:
    latest = _parse_last_email_snapshot(payload)
    if latest is not None:
        return latest
    # Fallback for older scanners that stored crossing history only.
    sent = payload.get("sent", {})
    if not isinstance(sent, dict):
        raise ValueError("Scanner alert history has no valid 'sent' dictionary.")
    events = []
    for key, timestamp in sent.items():
        if not isinstance(key, str) or not isinstance(timestamp, str):
            continue
        parts = key.split("|")
        if len(parts) != 3:
            continue
        session, ticker, band = parts
        ticker = ticker.strip().upper()
        if not TICKER_PATTERN.fullmatch(ticker) or band not in ("-3σ", "-4σ"):
            continue
        try:
            at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            at = at.replace(tzinfo=ET) if at.tzinfo is None else at.astimezone(ET)
        except (ValueError, OverflowError):
            continue
        events.append((at, session, ticker, band))
    if not events:
        return AlertSnapshot(configured=True)

    # Email can contain multiple new bands for one stock; dedupe the ticker.
    latest_date = max(row[0].date() for row in events)
    recent = sorted((e for e in events if e[0].date() == latest_date), key=lambda e: (e[0], e[2]))
    symbols, sessions, bands = [], {}, {}
    for _, session, ticker, band in recent:
        if ticker not in sessions:
            symbols.append(ticker)
            sessions[ticker] = session
            bands[ticker] = set()
        bands[ticker].add(band)
    latest_time = max(row[0] for row in recent)
    # Newer standalone scanners also save the exact sent Z scores in this
    # *same* committed alert file. Older histories remain fully supported.
    emailed_z = {}
    last_email = payload.get("last_email")
    if isinstance(last_email, dict):
        try:
            last_sent = datetime.fromisoformat(str(last_email.get("sent_at", "")).replace("Z", "+00:00"))
            last_sent = last_sent.replace(tzinfo=ET) if last_sent.tzinfo is None else last_sent.astimezone(ET)
        except ValueError:
            last_sent = None
        if last_sent is not None and last_sent.date() == latest_date:
            stocks = last_email.get("stocks", [])
            if isinstance(stocks, list):
                for record in stocks[:500]:
                    if not isinstance(record, dict):
                        continue
                    ticker = str(record.get("ticker", "")).upper()
                    if ticker not in sessions:
                        continue
                    try:
                        z = float(record.get("z_score"))
                    except (ValueError, TypeError):
                        continue
                    if math.isfinite(z):
                        emailed_z[ticker] = z
    return AlertSnapshot(
        symbols=symbols,
        latest_email_date=latest_date.isoformat(),
        latest_email_time=latest_time.strftime("%b %d, %Y at %I:%M %p ET"),
        session_by_symbol=sessions,
        bands_by_symbol={t: ", ".join(sorted(bands[t])) for t in symbols},
        emailed_z_by_symbol=emailed_z,
        configured=True,
    )


def load_email_alerts() -> AlertSnapshot:
    repo = configured_repo()
    if not repo:
        return AlertSnapshot(error="Set SCANNER_GITHUB_REPOSITORY in Streamlit secrets to enable automatic email alerts.")
    if not REPO_PATTERN.fullmatch(repo):
        return AlertSnapshot(error="SCANNER_GITHUB_REPOSITORY should look like owner/regression-stock-scanner.")
    branch = _configuration("SCANNER_GITHUB_BRANCH") or "main"
    if (not re.fullmatch(r"[A-Za-z0-9_.\-/]{1,128}", branch)
            or ".." in branch or "//" in branch or branch.startswith("/")):
        return AlertSnapshot(error="SCANNER_GITHUB_BRANCH contains invalid characters.")
    token = _configuration("SCANNER_GITHUB_TOKEN")
    try:
        result = parse_sent_alert_history(_read_github_contents(repo, branch, token))
        result.source = f"{repo}@{branch}"
        return result
    except (requests.RequestException, ValueError, TypeError, json.JSONDecodeError) as exc:
        # The request exception can't print an Authorization header, and it is
        # deliberately never handed the token in a URL.
        return AlertSnapshot(configured=True, error=str(exc), source=repo)


@st.cache_data(ttl=120, show_spinner=False)
def saved_regression_zscores(project_root: str) -> dict[str, tuple[float, str, str]]:
    """Read existing scanner output; never recalculate regression channels."""
    project = Path(project_root)
    paths = [project / "regression_scanner" / "results" / "latest_scan.csv",
             project / "results" / "latest_scan.csv",
             project.parent / "regression-stock-scanner" / "results" / "latest_scan.csv"]
    explicit = _configuration("REGRESSION_SCANNER_RESULTS")
    if explicit:
        paths.insert(0, Path(explicit).expanduser())
    for path in paths:
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 8_000_000:
                continue
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames or not {"ticker", "z_score"}.issubset(set(reader.fieldnames)):
                    continue
                rows = {}
                for i, row in enumerate(reader):
                    if i > 100000:
                        break
                    ticker = str(row.get("ticker", "")).strip().upper()
                    if not TICKER_PATTERN.fullmatch(ticker):
                        continue
                    try:
                        score = float(row["z_score"])
                    except (ValueError, TypeError):
                        continue
                    if math.isfinite(score):
                        rows[ticker] = (score, str(row.get("session") or ""), str(path))
                if rows:
                    return rows
        except (OSError, UnicodeError, csv.Error):
            continue
    return {}


def sigma_label(symbol: str, scores: dict[str, tuple[float, str, str]],
                snapshot: AlertSnapshot, is_email_list: bool) -> str:
    if is_email_list and symbol in snapshot.emailed_z_by_symbol:
        return f"Z-score {snapshot.emailed_z_by_symbol[symbol]:+.2f}σ"
    item = scores.get(symbol)
    if item is not None:
        z, scan_session, _ = item
        # A stock's historical EMAILED Z score must not be replaced with a
        # different scan's Z-score: dates must match if known.
        if not is_email_list or (scan_session and scan_session == snapshot.session_by_symbol.get(symbol)):
            return f"Z-score {z:+.2f}σ"
    if is_email_list:
        band = snapshot.bands_by_symbol.get(symbol, "")
        return f"Crossed {band}" if band else "Z-score N/A"
    return "Z-score N/A"
