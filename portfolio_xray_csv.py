"""Strict, dependency-free import of two-column Portfolio X-Ray CSV files.

Accepts a standard Excel export with headers Ticker,Amount and either all
percentage weights (e.g. 12.29%) or all dollar amounts (e.g. 1250.50).
Does not renormalize percentages or silently drop meaningful non-stock assets.
"""
from __future__ import annotations

import csv
import io
import math
import re

from portfolio_xray import ticker_of

MAX_CSV_BYTES = 256_000
MAX_CSV_ROWS = 500
MAX_POSITIONS = 30


def parse_portfolio_csv(payload: bytes) -> tuple[list[dict], str, list[str]]:
    """Return (positions, unit 'pct'|'usd', visible import warnings)."""
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("Choose a non-empty CSV file.")
    if len(payload) > MAX_CSV_BYTES:
        raise ValueError("CSV is too large (maximum 256 KB).")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Export your spreadsheet as UTF-8 CSV.") from exc

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error) as exc:
        raise ValueError("CSV must start with Ticker,Amount.") from exc
    headers = [str(cell).strip().lower().replace(" ", "") for cell in header]
    if len(headers) != 2 or headers[0] != "ticker" or headers[1] not in {
        "amount", "amount($)", "amount(%)", "weight", "weight(%)",
    }:
        raise ValueError("CSV needs exactly two columns: Ticker, Amount.")

    positions = []
    warnings = []
    units = None
    ignored_zeros = 0
    for index, record in enumerate(reader, start=2):
        if index > MAX_CSV_ROWS:
            raise ValueError("CSV exceeds the 500-row safety limit.")
        if not record or all(not x.strip() for x in record):
            continue
        if len(record) != 2:
            raise ValueError(f"CSV row {index}: expected exactly Ticker and Amount.")
        symbol_raw, amount_raw = (value.strip() for value in record)
        if not symbol_raw:
            raise ValueError(f"CSV row {index}: ticker is blank.")
        try:
            symbol = ticker_of(symbol_raw)
        except ValueError as exc:
            raise ValueError(f"CSV row {index}: unrecognized ticker or asset name: {symbol_raw}") from exc
        is_pct = amount_raw.endswith("%")
        if amount_raw.count("%") > 1 or ("%" in amount_raw and not is_pct):
            raise ValueError(f"CSV row {index}: invalid percentage format.")
        if units is None:
            units = "pct" if is_pct else "usd"
        if (units == "pct") != is_pct:
            raise ValueError("CSV mixes percentages with dollar amounts; use one format.")
        numeric = amount_raw[:-1].strip() if is_pct else amount_raw
        numeric = numeric.replace(",", "").replace("$", "").strip()
        if not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", numeric):
            raise ValueError(f"CSV row {index}: invalid amount '{amount_raw}'.")
        amount = float(numeric)
        if not math.isfinite(amount):
            raise ValueError(f"CSV row {index}: invalid finite amount.")
        if amount == 0:
            ignored_zeros += 1
            continue
        if units == "pct" and amount > 100:
            raise ValueError(f"CSV row {index}: percentage exceeds 100%.")
        positions.append({"ticker": symbol, "amount": amount})
        if len(positions) > MAX_POSITIONS:
            raise ValueError(f"CSV supports up to {MAX_POSITIONS} nonzero positions.")

    if not positions:
        raise ValueError("CSV contains no positive positions.")
    total = sum(pos["amount"] for pos in positions)
    if units == "pct" and total > 100.5:
        raise ValueError(
            f"CSV weights total {total:.2f}%, exceeding 100% by more than rounding."
        )
    if units == "pct" and abs(total - 100.0) > 0.2:
        warnings.append(
            f"CSV allocation totals {total:.2f}%, not 100%. "
            "The X-Ray percentages reflect the supplied positions, without silently filling missing allocations."
        )
    if ignored_zeros:
        warnings.append(
            f"Skipped {ignored_zeros} position(s) with 0.00 amount or weight."
        )
    return positions, units or "usd", warnings
