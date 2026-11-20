"""Discover U.S.-region, U.S.-exchange equity candidates by market-cap range.

Yahoo's region/exchange/quoteType data are a practical approximation: they do
not independently certify a U.S. company's primary stock listing.
"""
import math
import re
import time
from dataclasses import dataclass

import yfinance as yf

EXCHANGES = {"NMS", "NYQ", "ASE"}
ADR_NAME = re.compile(r"\b(?:ADR|ADS|AMERICAN DEPOSITARY|DEPOSITARY RECEIPT)\b", re.I)
MAX_SCREENER_PAGES = 20  # 20 * 250 = 5000 candidate records maximum


@dataclass(frozen=True)
class Stock:
    symbol: str
    name: str
    exchange: str
    cap: int | None


def validate_market_caps(min_cap_b: float, max_cap_b: float | None) -> None:
    """Validate dollar values expressed in billions (not raw dollars)."""
    if not math.isfinite(min_cap_b) or min_cap_b < 0:
        raise ValueError("Minimum market cap must be a finite number >= $0B")
    if max_cap_b is not None:
        if not math.isfinite(max_cap_b) or max_cap_b <= min_cap_b:
            raise ValueError("Maximum market cap must be greater than the minimum")


def large_cap_stocks(min_cap_b: float = 50.0, max_cap_b: float | None = None, limit: int | None = None) -> list[Stock]:
    """Find stocks from Yahoo's screener inside [min_cap_b, max_cap_b].

    cap bounds are in US$ billions. The upper bound is optional.
    If limit is set, stop paging as soon as enough market-cap-ranked candidates
    match the requested range, rather than downloading the entire universe.
    Results with missing or invalid market-cap metadata are excluded, because
    we cannot prove they satisfy the user's requested range.
    """
    if limit is not None and (not isinstance(limit, int) or limit < 1):
        raise ValueError("Stock limit must be a positive integer")
    min_cap_b = float(min_cap_b)
    max_cap_b = float(max_cap_b) if max_cap_b is not None else None
    validate_market_caps(min_cap_b, max_cap_b)
    floor = round(min_cap_b * 1_000_000_000)
    ceiling = round(max_cap_b * 1_000_000_000) if max_cap_b is not None else None

    filters = [
        yf.EquityQuery("eq", ["region", "us"]),
        yf.EquityQuery("is-in", ["exchange", *sorted(EXCHANGES)]),
        yf.EquityQuery("gte", ["intradaymarketcap", max(floor, 1)]),
    ]
    if ceiling is not None:
        filters.append(yf.EquityQuery("lte", ["intradaymarketcap", ceiling]))
    query = yf.EquityQuery("and", filters)

    selected: dict[str, Stock] = {}
    for offset in range(0, MAX_SCREENER_PAGES * 250, 250):
        response = None
        for attempt in range(3):
            try:
                response = yf.screen(query, offset=offset, size=250,
                                     sortField="intradaymarketcap", sortAsc=False)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(3 * (attempt + 1))

        quotes = response.get("quotes", []) if isinstance(response, dict) else []
        if not quotes and offset == 0:
            raise RuntimeError("Yahoo returned no screener results; cannot claim a complete scan")
        for quote in quotes:
            symbol = str(quote.get("symbol") or "").strip().upper()
            name = str(quote.get("longName") or quote.get("shortName") or symbol)
            exchange = str(quote.get("exchange") or "").upper()
            quote_type = str(quote.get("quoteType") or "EQUITY").upper()
            cap_raw = quote.get("marketCap") or quote.get("intradaymarketcap")
            try:
                cap = int(cap_raw) if cap_raw is not None else None
            except (TypeError, ValueError, OverflowError):
                cap = None
            if (not symbol or exchange not in EXCHANGES or quote_type != "EQUITY"
                    or ADR_NAME.search(name)):
                continue
            if cap is None or cap < floor or (ceiling is not None and cap > ceiling):
                continue
            selected[symbol] = Stock(symbol, name, exchange, cap)
        # Yahoo returns rows sorted by descending market capitalization.
        # Stop pagination once we have enough eligible stocks for Top N.
        if (limit is not None and len(selected) >= limit) or len(quotes) < 250:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("Screener returned >5,000 records: refusing a truncated universe")

    if not selected:
        raise RuntimeError("No stocks match this market-cap range in Yahoo's screener")
    ranked = sorted(selected.values(), key=lambda s: (-s.cap, s.symbol))
    return ranked[:limit] if limit is not None else ranked
