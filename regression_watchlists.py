"""Read *actual* Regression Stock Scanner reports for two News Sentiment presets.

This module intentionally does not claim to scan the full equity universe. It
filters the user's last completed scanner export and reports its provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import os
from pathlib import Path
import re

import pandas as pd


PROJECT = Path(__file__).resolve().parent
MAX_CSV_BYTES = 8_000_000
MAX_ROWS = 100_000
# Values are in billions of USD, matching the Regression Scanner CSV format.
PRESETS = {
    '50B+ market cap · −3σ or lower': (50.0, -3.0),
    '2B+ market cap · −4σ or lower': (2.0, -4.0),
}


@dataclass
class ScanReport:
    rows: pd.DataFrame
    source: str
    modified_utc: datetime | None


def candidates() -> list[Path]:
    explicit = os.getenv('REGRESSION_SCANNER_RESULTS', '').strip()
    parent = PROJECT.parent
    paths = ([Path(explicit).expanduser()] if explicit else []) + [
        PROJECT / 'results' / 'latest_scan.csv',
        parent / 'regression-stock-scanner' / 'results' / 'latest_scan.csv',
        parent / 'RegressionStockScanner' / 'results' / 'latest_scan.csv',
        parent / 'regression_stock_scanner' / 'results' / 'latest_scan.csv',
    ]
    return list(dict.fromkeys(paths))


def parse_scan_csv(content: bytes, source: str, modified: datetime | None = None) -> ScanReport:
    if not content or len(content) > MAX_CSV_BYTES:
        raise ValueError('The scanner CSV is empty or too large (8 MB maximum).')
    frame = pd.read_csv(BytesIO(content), low_memory=False)
    frame.columns = [str(c).strip().casefold() for c in frame.columns]
    required = {'ticker', 'market_cap_b', 'z_score'}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError('Expected regression scanner columns: ticker, market_cap_b, z_score. Missing: ' + ', '.join(sorted(missing)))
    if len(frame) > MAX_ROWS:
        raise ValueError('The scanner report has too many rows.')
    frame = frame.copy()
    frame['ticker'] = frame['ticker'].astype('string').str.strip().str.upper()
    frame = frame[frame['ticker'].str.fullmatch(r'[A-Z0-9.^=\-]{1,18}', na=False)]
    for col in ('market_cap_b', 'z_score'):
        frame[col] = pd.to_numeric(frame[col], errors='coerce')
    frame = frame.dropna(subset=['market_cap_b', 'z_score'])
    frame = frame[(frame['market_cap_b'] >= 0) & (frame['z_score'].between(-25, 25))]
    frame = frame.drop_duplicates(subset=['ticker'], keep='first')
    frame = frame.sort_values(['z_score', 'market_cap_b'], ascending=[True, False]).reset_index(drop=True)
    return ScanReport(frame, source, modified)


def read_local_scan() -> ScanReport | None:
    for path in candidates():
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_CSV_BYTES:
                continue
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            return parse_scan_csv(path.read_bytes(), str(path), modified)
        except (OSError, ValueError, UnicodeError, pd.errors.ParserError):
            continue
    return None


def filtered(report: ScanReport, preset: str) -> pd.DataFrame:
    min_cap, z_limit = PRESETS[preset]
    rows = report.rows
    return rows[(rows['market_cap_b'] >= min_cap) & (rows['z_score'] <= z_limit)].copy()


def display_row(row: pd.Series, show_sigma: bool = False) -> str:
    ticker = str(row['ticker'])
    if show_sigma:
        return f"{ticker}  ·  {row['z_score']:.2f}σ"
    return ticker


def stale_report(report: ScanReport, days: int = 7) -> bool:
    if report.modified_utc is None:
        return False
    return (datetime.now(timezone.utc) - report.modified_utc).total_seconds() > days * 86400
