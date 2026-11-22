"""Strict import/export of dated three-column Portfolio X-Ray CSV files.

Accepts Date,Ticker,Amount (or legacy Ticker,Amount) and either all
percentage weights (e.g. 12.29%) or all dollar amounts (e.g. 1250.50).
Does not renormalize percentages or silently drop meaningful non-stock assets.
"""
from __future__ import annotations

import csv
import io
import math
import re

from portfolio_xray import ticker_of
from portfolio_xray_dates import normalized_position_date, position_with_date

MAX_CSV_BYTES = 256_000
MAX_CSV_ROWS = 500
MAX_POSITIONS = 30



def export_portfolio_csv(positions: list[dict], unit: str) -> bytes:
    """Produce an exact round-trippable share file for the X-Ray CSV importer.

    Export the *input* holdings (not ETF-expanded stocks): another user can
    upload the file and run the same look-through on the same instruments.
    Percentage weights retain the '%' suffix; dollar inputs never gain one.
    """
    if unit not in {"pct", "usd"}:
        raise ValueError("Portfolio amount unit must be percentage or USD.")
    if not isinstance(positions, list) or not 1 <= len(positions) <= MAX_POSITIONS:
        raise ValueError(f"Export needs 1–{MAX_POSITIONS} valid portfolio positions.")

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Date", "Ticker", "Amount"])
    for index, item in enumerate(positions, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Position {index}: expected ticker and amount.")
        ticker = ticker_of(item.get("ticker", ""))
        try:
            amount = float(item.get("amount"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Position {index}: amount must be numeric.") from exc
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError(f"Position {index}: amount must be finite and positive.")
        if unit == "pct" and amount > 100:
            raise ValueError(f"Position {index}: weight exceeds 100%.")
        # Python's float string is a shortest round-trippable representation.
        # Do not round small allocations or convert percent points to fractions.
        value = str(amount) + ("%" if unit == "pct" else "")
        writer.writerow([normalized_position_date(item.get("date")), ticker, value])

    data = output.getvalue().encode("utf-8-sig")  # Excel-friendly UTF-8 BOM.
    # The shared CSV must always be re-importable by this very same tool.
    decoded, decoded_unit, _ = parse_portfolio_csv(data)
    if decoded_unit != unit or decoded != [
        position_with_date(
            ticker_of(item["ticker"]), float(item["amount"]), item.get("date")
        )
        for item in positions
    ]:
        raise ValueError("Unable to verify CSV export round-trip.")
    return data


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
        raise ValueError("CSV must start with Date,Ticker,Amount (or Ticker,Amount).") from exc
    headers = [str(cell).strip().lower().replace(" ", "") for cell in header]
    has_date = len(headers) == 3 and headers[0] == "date"
    ticker_col = 1 if has_date else 0
    amount_col = 2 if has_date else 1
    if len(headers) not in (2, 3) or headers[ticker_col] != "ticker" or headers[amount_col] not in {
        "amount", "amount($)", "amount(%)", "weight", "weight(%)",
    } or (len(headers) == 3 and not has_date):
        raise ValueError(
            "CSV needs Date,Ticker,Amount (or the older Ticker,Amount format)."
        )

    positions = []
    warnings = []
    units = None
    ignored_zeros = 0
    for index, record in enumerate(reader, start=2):
        if index > MAX_CSV_ROWS:
            raise ValueError("CSV exceeds the 500-row safety limit.")
        if not record or all(not x.strip() for x in record):
            continue
        if len(record) != (3 if has_date else 2):
            raise ValueError(
                f"CSV row {index}: expected "
                + ("Date, Ticker, Amount." if has_date else "Ticker, Amount.")
            )
        date_raw = record[0].strip() if has_date else ""
        try:
            row_date = normalized_position_date(date_raw)
        except ValueError as exc:
            raise ValueError(f"CSV row {index}: {exc}") from exc
        symbol_raw = record[ticker_col].strip()
        amount_raw = record[amount_col].strip()
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
        positions.append(position_with_date(symbol, amount, row_date))
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
