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


# Full export sizes are substantially larger than ordinary page sizes.
# Conservative floors catch a partial/changed provider response rather than
# claiming an incomplete result is the globally ranked Top N.
MIN_FULL_EXPORT_RECORDS = {"NASDAQ": 900, "NYSE": 900, "AMEX": 100}


def fetch_nasdaq_universe(
    min_cap: int, max_cap: int | None,
    session=None,
) -> list[dict]:
    """Fetch the full public Nasdaq export for each US exchange.

    Nasdaq's download=true response is a complete export: it may ignore
    limit/offset and return thousands of rows without a total-records field.
    Thus it must NOT be treated as a 1,000-row paginated response.
    """
    http = session or requests
    stocks: dict[str, dict] = {}
    rejected = Counter()
    seen = 0
    for exchange, yf_exchange in EXCHANGES.items():
        try:
            response = http.get(
                API,
                params={
                    "tableonly": "true",
                    "exchange": exchange,
                    "download": "true",
                    "limit": 5000,
                    "offset": 0,
                },
                headers=HEADERS,
                timeout=(6, 45),
            )
            response.raise_for_status()
            payload = response.json()
            status = payload.get("status") if isinstance(payload, dict) else None
            if isinstance(status, dict) and status.get("rCode") not in (None, 200):
                raise RuntimeError(
                    f"Nasdaq reported status {status.get('rCode')}."
                )
            rows, reported_total = _page(payload)
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            raise RuntimeError(
                f"Nasdaq full stock export failed for {exchange}: "
                f"{type(exc).__name__}. No partial universe was used."
            ) from exc

        min_rows = MIN_FULL_EXPORT_RECORDS[exchange]
        if len(rows) < min_rows:
            raise RuntimeError(
                f"Nasdaq {exchange} export returned only {len(rows)} rows "
                f"(expected at least {min_rows}); refusing a potentially "
                "truncated market universe."
            )
        if reported_total is not None and len(rows) != reported_total:
            raise RuntimeError(
                f"Nasdaq {exchange} export returned {len(rows)} of "
                f"{reported_total} reported rows. No partial universe was used."
            )
        symbols = [
            str(row.get("symbol") or "").strip().upper()
            for row in rows
        ]
        if len(set(symbols)) != len(symbols):
            raise RuntimeError(
                f"Nasdaq {exchange} full export contained duplicate symbols; "
                "refusing an uncertain universe."
            )
        # The full export is alphabetically sorted. This inexpensive check
        # detects a first- or last-page-only response even with no row total.
        if not symbols[0].startswith("A") or not symbols[-1].startswith("Z"):
            raise RuntimeError(
                f"Nasdaq {exchange} export did not span A-Z; "
                "refusing a potentially incomplete universe."
            )

        for row in rows:
            seen += 1
            country = str(row.get("country") or "").strip().upper()
            if country not in US_COUNTRIES:
                rejected["non_us_or_missing_country"] += 1
                continue
            symbol = str(row.get("symbol") or "").strip().upper().replace("/", "-")
            name = str(row.get("name") or "").strip()
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

    logging.getLogger(__name__).info(
        "Nasdaq full exports: %d rows, %d eligible, rejected: %s",
        seen, len(stocks), dict(rejected),
    )
    if not stocks:
        logging.getLogger(__name__).error(
            "Nasdaq full export returned no eligible stocks: %s",
            dict(rejected),
        )
        raise RuntimeError(
            "Nasdaq returned no eligible U.S. stocks in the market-cap range. "
            "No empty scan was published."
        )
    return sorted(stocks.values(), key=lambda item: (-item["cap"], item["symbol"]))
