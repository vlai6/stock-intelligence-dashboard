"""Shared ETF regression outputs across Scanner and News Screen (local files only)."""
from __future__ import annotations
import csv
import io
import json
import os
from pathlib import Path
import re
import math
import pandas as pd
from etf_holdings import normalize_symbol


def etf_report_dir(symbol: str, project_root: str | Path) -> Path:
    etf = normalize_symbol(symbol)
    if not etf:
        raise ValueError("Invalid ETF ticker")
    configured = os.getenv("REGRESSION_SCANNER_DATA_DIR", "").strip()
    root = Path(configured).expanduser().resolve() if configured else Path(project_root).resolve() / "regression_scanner"
    return root / "results" / "etf_scans" / etf


def parse_holdings_csv(data: bytes) -> list[str]:
    if len(data) > 3_000_000:
        raise ValueError("Holdings CSV is too large (maximum 3 MB).")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Holdings CSV must use UTF-8 encoding.") from exc
    rows = csv.DictReader(io.StringIO(text))
    if not rows.fieldnames:
        raise ValueError("Holdings CSV has no header row.")
    names = {str(n).strip().lower().replace("_", " "): n for n in rows.fieldnames if n}
    column = next((names.get(n) for n in (
        "ticker", "symbol", "holding ticker", "holding symbol", "stock ticker", "security ticker"
    ) if n in names), None)
    if not column:
        raise ValueError("Holdings CSV must have a Ticker or Symbol column.")
    seen: set[str] = set()
    for row in rows:
        ticker = normalize_symbol(row.get(column))
        if ticker:
            seen.add(ticker)
    return list(sorted(seen))


def load_etf_scores(symbol: str, project_root: str | Path) -> tuple[pd.DataFrame, dict]:
    path = etf_report_dir(symbol, project_root)
    scores = path / "all_regression_scores.csv"
    summary = path / "summary.json"
    skipped = path / "skipped.csv"
    meta: dict = {}
    if summary.is_file():
        try:
            meta = json.loads(summary.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    if skipped.is_file():
        try:
            skip_frame = pd.read_csv(skipped)
            meta["skipped"] = skip_frame.loc[skip_frame["reason"] != "trend_or_band_filter"].to_dict("records")
        except (OSError, ValueError, KeyError, pd.errors.ParserError):
            pass
    if not scores.is_file():
        return pd.DataFrame(), meta
    try:
        frame = pd.read_csv(scores, dtype={"ticker":"string"})
        if not {"ticker", "z_score"}.issubset(frame.columns):
            return pd.DataFrame(), meta
        for col in ["z_score", "close", "regression", "lower_3", "lower_4"]:
            if col in frame:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame = frame.dropna(subset=["z_score"])
        frame = frame.loc[frame["z_score"].map(math.isfinite)].sort_values("z_score")
        return frame, meta
    except (OSError, UnicodeError, ValueError, pd.errors.ParserError):
        return pd.DataFrame(), meta


def etf_score_map(frame: pd.DataFrame) -> dict[str, tuple[float, str, str]]:
    if frame.empty:
        return {}
    return {str(row.ticker).strip().upper(): (float(row.z_score), str(getattr(row, "session", "")), "ETF regression scan")
            for row in frame.itertuples(index=False)}
