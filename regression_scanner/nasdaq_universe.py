"""Fallback stock discovery for Yahoo screener authorization/rate-limit failures.

Nasdaq's public stock screener is not an authenticated, guaranteed API. Treat
any incomplete page/exchange as a hard failure, not an authoritative universe.
The fallback only discovers stocks; historical prices remain on Yahoo.
"""
from __future__ import annotations

import math
import re
import time
import logging
from collections import Counter

import requests

API = "https://api.nasdaq.com/api/screener/stocks"
EXCHANGES = {"NASDAQ": "NMS", "NYSE": "NYQ", "AMEX": "ASE"}
PAGE_SIZE = 1000
MAX_PAGES_PER_EXCHANGE = 12
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/market-activity/stocks/screener",
}
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.-]{0,12}$")
ADR = re.compile(
    r"\b(?:ADR|ADS|AMERICAN DEPOSITARY|DEPOSITARY RECEIPT)\b", re.I
)
# Exclude obvious non-common-stock instruments. A REIT named "...Trust"
# is NOT automatically rejected.
NOT_EQUITY = re.compile(
    r"\b(?:ETF|ETN|EXCHANGE.TRADED FUND|WARRANTS?|"
    r"RIGHTS?|PREFERRED STOCK|PREFERENCE SHARES|"
    r"DEPOSITARY SHARES|UNITS?)\b", re.I
)
US_COUNTRIES = {
    "UNITED STATES", "UNITED STATES OF AMERICA", "US", "USA", "U.S.", "U.S.A."
}


def _market_cap(value) -> int | None:
    """Parse Nasdaq's raw-USD and human-formatted market caps.

    The public endpoint can return a numeric string, currency-formatted
    value, or a suffix such as 3.1T; reject unverifiable values.
    """
    if value is None or isinstance(value, bool):
        return None
    s = str(value).strip().upper().replace("$", "").replace(",", "")
    if not s or s in {"N/A", "NA", "--", "NULL"}:
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?|\.\d+)\s*([KMBT]?)", s)
    if not match:
        return None
    cap = float(match.group(1)) * {
        "": 1, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12,
    }[match.group(2)]
    return int(cap) if math.isfinite(cap) and cap > 0 else None


def _count(value) -> int | None:
    try:
        count = int(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None
    return count if count >= 0 else None


def _page(data: dict) -> tuple[list[dict], int | None]:
    if not isinstance(data, dict):
        raise RuntimeError("Nasdaq screener response was not a JSON object.")
    envelope = data.get("data")
    if not isinstance(envelope, dict):
        raise RuntimeError("Nasdaq screener response has no data object.")
    table = envelope.get("table")
    container = table if isinstance(table, dict) else envelope
    rows = container.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("Nasdaq screener returned an unexpected rows structure.")
    total = _count(
        envelope.get("totalrecords", envelope.get("totalRecords",
            container.get("totalrecords", container.get("totalRecords"))))
    )
    return rows, total


def fetch_nasdaq_universe(
    min_cap: int, max_cap: int | None,
    session=None,
) -> list[dict]:
    """Return all eligible Nasdaq/NYSE/AMEX U.S. company shares, sorted by cap.

    Fetch every exchange and every page BEFORE any Top-N cutoff. This prevents
    choosing the top N from a truncated or incomplete fallback universe.
    """
    http = session or requests
    stocks: dict[str, dict] = {}
    rejected = Counter()
    seen = 0
    for exchange, yf_exchange in EXCHANGES.items():
        seen_symbols = set()
        total = None
        offset = 0
        for _ in range(MAX_PAGES_PER_EXCHANGE):
            try:
                response = http.get(
                    API,
                    params={
                        "tableonly": "true",
                        "exchange": exchange,
                        "limit": PAGE_SIZE,
                        "offset": offset,
                        # Nasdaq's download route provides the full screener
                        # fields, including company country and market cap.
                        "download": "true",
                    },
                    headers=HEADERS,
                    timeout=(5, 22),
                )
                response.raise_for_status()
                rows, reported_total = _page(response.json())
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                raise RuntimeError(
                    f"Nasdaq stock discovery failed for {exchange} at offset "
                    f"{offset}: {type(exc).__name__}. No partial universe was used."
                ) from exc
            if reported_total is not None:
                if total is not None and total != reported_total:
                    raise RuntimeError(
                        f"Nasdaq reported inconsistent {exchange} stock counts."
                    )
                total = reported_total
            if not rows and offset == 0:
                raise RuntimeError(
                    f"Nasdaq returned no {exchange} stocks; cannot verify coverage."
                )
            if len(rows) > PAGE_SIZE:
                raise RuntimeError(
                    f"Nasdaq returned more than the requested page size for {exchange}."
                )
            page_symbols = {
                str(r.get("symbol") or "").upper().strip() for r in rows
                if r.get("symbol")
            }
            if offset and page_symbols and page_symbols.issubset(seen_symbols):
                raise RuntimeError(
                    f"Nasdaq repeated a {exchange} screener page; refusing "
                    "an incomplete stock universe."
                )
            seen_symbols.update(page_symbols)
            for row in rows:
                seen += 1
                country = str(row.get("country") or "").strip().upper()
                if country not in US_COUNTRIES:
                    rejected["non_us_or_missing_country"] += 1
                    continue
                symbol = str(row.get("symbol") or "").strip().upper().replace("/", "-")
                name = str(row.get("name") or "").strip()
                # Nasdaq sometimes varies the case of its capitalization key.
                cap = _market_cap(
                    row.get("marketCap", row.get("marketcap", row.get("market_cap")))
                )
                if not SYMBOL.fullmatch(symbol) or not name:
                    rejected["missing_symbol_or_name"] += 1
                    continue
                if ADR.search(name) or NOT_EQUITY.search(name):
                    rejected["non_common_equity"] += 1
                    continue
                if cap is None:
                    rejected["missing_or_invalid_market_cap"] += 1
                    continue
                if cap < min_cap or max_cap is not None and cap > max_cap:
                    rejected["outside_market_cap_range"] += 1
                    continue
                item = {
                    "symbol": symbol, "name": name,
                    "exchange": yf_exchange, "cap": cap,
                }
                existing = stocks.get(symbol)
                if existing is None or existing["cap"] < cap:
                    stocks[symbol] = item
            offset += len(rows)
            if total is not None:
                if offset >= total:
                    break
                if not rows:
                    raise RuntimeError(
                        f"Nasdaq truncated {exchange} pagination "
                        f"({offset} of {total} records)."
                    )
            elif len(rows) < PAGE_SIZE:
                break
            if rows:
                time.sleep(0.25)
        else:
            raise RuntimeError(
                f"Nasdaq {exchange} discovery exceeded page safety limit; "
                "no partial universe was used."
            )
        if total is not None and offset < total:
            raise RuntimeError(
                f"Nasdaq {exchange} provided only {offset}/{total} records; "
                "no partial universe was used."
            )
    logging.getLogger(__name__).info(
        "Nasdaq fallback examined %d rows; retained %d eligible; rejected %s",
        seen, len(stocks), dict(rejected),
    )
    if not stocks:
        logging.getLogger(__name__).error(
            "Nasdaq screener yielded no eligible stocks. Rejection breakdown: %s",
            dict(rejected),
        )
        raise RuntimeError(
            "Nasdaq returned no eligible U.S. stocks in the selected "
            "market-cap range. Check server logs for which metadata field "
            "prevented discovery. No partial scan was published."
        )
    return sorted(stocks.values(), key=lambda item: (-item["cap"], item["symbol"]))
