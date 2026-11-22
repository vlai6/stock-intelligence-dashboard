"""ETF / individual-stock portfolio X-ray, using full issuer holdings only."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
import csv
import io
import math
import re

VALID = re.compile(r"^[A-Z][A-Z0-9.\-]{0,12}$")
SPDR = {"SPY", "SPYG", "SPYV", "SPYD", "XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLU", "XLC", "XLRE", "SDY"}
INVESCO = {"SPMO", "XMMO", "XSMO", "QQQ", "QQQM", "RSP", "SPLV"}

@dataclass(frozen=True)
class Holdings:
    ticker: str
    weights: dict[str, float]  # Each is a fraction of fund NAV
    source: str
    as_of: str = ""

    @property
    def coverage(self):
        return sum(self.weights.values())


def ticker_of(value):
    ticker = str(value or "").strip().upper().replace("/", ".")
    if not VALID.fullmatch(ticker):
        raise ValueError("Ticker must contain letters, digits, dots or hyphens")
    return ticker


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _number(value):
    raw = str(value or "").strip().replace(",", "").replace("$", "").replace("%", "")
    if raw.lower() in ("", "--", "-", "na", "n/a", "nan", "none"):
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def parse_rows(rows, ticker, source):
    """Parse an issuer CSV/XLSX by matching column meaning, not row position."""
    rows = [list(r) for r in rows]
    symbols = {"ticker", "holdingticker", "symbol", "securityticker", "stockticker"}
    names = {"name", "company", "companyname", "securityname", "holdingname", "description"}
    weights = {"weight", "weightpercent", "weightpercentage", "weighting",
               "weightofnetassets", "percentageofnetassets", "percentofnetassets",
               "percentofassets", "portfolioweight"}
    header_index, key, name_key, weight_key = None, None, None, None
    for i, row in enumerate(rows[:45]):
        h = [_norm(x) for x in row]
        symbol_index = next((j for j, x in enumerate(h) if x in symbols), None)
        name_index = next((j for j, x in enumerate(h) if x in names), None)
        weight_index = next((j for j, x in enumerate(h) if x in weights), None)
        if (symbol_index is not None or name_index is not None) and weight_index is not None:
            header_index, key, name_key, weight_key = i, symbol_index, name_index, weight_index
            break
    if header_index is None:
        raise ValueError("No complete holdings table: expected Ticker/Company and Weight columns")
    found = defaultdict(float)
    raw_total = 0.0
    for row in rows[header_index + 1:]:
        def cell(i):
            return str(row[i]).strip() if i is not None and i < len(row) else ""
        v = _number(cell(weight_key))
        if v is None or v <= 0:
            continue
        label = cell(key)
        if label.upper() in {"", "N/A", "-", "--"}:
            company = cell(name_key)
            if not company:
                continue
            label = "NAME: " + company[:75].upper()
        else:
            label = label.upper().replace("/", ".").replace(" ", "")
        if label.startswith(("TOTAL", "SUBTOTAL")):
            continue
        found[label] += v
        raw_total += v
    if not found or raw_total <= 0:
        raise ValueError("No positive, usable holdings found")
    # Issuers typically use 7.5 for 7.5%; some files use 0.075.
    factor = 1.0 if raw_total <= 1.05 else 0.01
    proportions = {k: v * factor for k, v in found.items()}
    total = sum(proportions.values())
    if total > 1.02:
        raise ValueError(f"Fund weight total {total:.1%} is invalid")
    if 1 < total <= 1.02:  # rounding in published fund weights
        proportions = {k: v / total for k, v in proportions.items()}
    return Holdings(ticker_of(ticker), proportions, source)


def parse_file(filename: str, data: bytes, ticker: str) -> Holdings:
    if len(data) > 12_000_000:
        raise ValueError("Holdings file over 12MB")
    if filename.lower().endswith(".csv"):
        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))
    elif filename.lower().endswith(".xlsx"):
        import pandas as pd
        frame = pd.read_excel(io.BytesIO(data), sheet_name=0, header=None, dtype=str)
        rows = frame.fillna("").values.tolist()
    else:
        raise ValueError("Upload a CSV or XLSX holdings file")
    return parse_rows(rows, ticker, "Uploaded: " + filename)


def _download(url, params=None):
    import requests
    response = requests.get(url, params=params, timeout=20, headers={
        "User-Agent": "Mozilla/5.0 (compatible; StockIntelligence/1.0)",
        "Accept": "text/csv,application/octet-stream,*/*",
    })
    response.raise_for_status()
    data = response.content
    if not data or len(data) > 12_000_000:
        raise ValueError("Empty or oversized holdings response")
    if data.lstrip()[:80].lower().startswith((b"<!doctype", b"<html", b"<head")):
        raise ValueError("Issuer returned an HTML page instead of holdings")
    return data


def issuer_holdings(ticker):
    """Official feeds when available; other ETFs require user-provided files."""
    ticker = ticker_of(ticker)
    if ticker in SPDR:
        url = ("https://www.ssga.com/library-content/products/fund-data/"
               f"etfs/us/holdings-daily-us-en-{ticker.lower()}.xlsx")
        return parse_file(ticker + ".xlsx", _download(url), ticker)
    if ticker in INVESCO:
        url = "https://www.invesco.com/us/financial-products/etfs/holdings/main/holdings/0"
        data = _download(url, {
            "audienceType": "Investor", "action": "download", "ticker": ticker
        })
        return parse_file(ticker + ".csv", data, ticker)
    raise ValueError(f"{ticker} has no automatic full-holdings adapter; upload its issuer holdings CSV/XLSX")


def portfolio_rows(positions, etfs, failures=None):
    """Dollar-weight holdings and directly owned stocks, preserving missing NAV."""
    failures = failures or {}
    dollars = defaultdict(float)
    contributors = defaultdict(lambda: defaultdict(float))
    total = 0.0
    details = []
    for position in positions:
        ticker = ticker_of(position["ticker"])
        amount = float(position["amount"])
        kind = str(position["type"]).strip().upper()
        if kind not in {"ETF", "STOCK"} or not math.isfinite(amount) or amount <= 0:
            raise ValueError("Every position needs ETF/Stock, ticker, and positive amount")
        total += amount
        if kind == "STOCK":
            dollars[ticker] += amount
            contributors[ticker]["Direct"] += amount
            continue
        holdings = etfs.get(ticker)
        if holdings is None:
            missing = "Unresolved " + ticker
            dollars[missing] += amount
            contributors[missing][ticker] += amount
            continue
        for stock, weight in holdings.weights.items():
            value = amount * weight
            dollars[stock] += value
            contributors[stock][ticker] += value
        gap = max(0.0, 1.0 - holdings.coverage) * amount
        if gap > 1e-7:
            missing = "Unreported " + ticker
            dollars[missing] += gap
            contributors[missing][ticker] += gap
        details.append({
            "ETF": ticker, "Coverage": f"{holdings.coverage:.1%}",
            "As of": holdings.as_of or "Check issuer", "Source": holdings.source,
        })
    if total <= 0:
        raise ValueError("Add at least one position before analyzing")
    results = sorted(({
        "Stock": stock, "Amount ($)": round(value, 2),
        "Portfolio %": round(100 * value / total, 3),
        "From": ", ".join(f"{src}: USD {v:,.2f}" for src, v in sorted(contributors[stock].items())),
        "Unresolved": stock.startswith(("Unresolved ", "Unreported ")),
        "_value": value,
    } for stock, value in dollars.items() if value > 1e-7),
        key=lambda row: row["_value"], reverse=True)
    unresolved = sum(x["_value"] for x in results if x["Unresolved"])
    return results, {"total": total, "mapped": total - unresolved,
                     "unresolved": unresolved, "sources": details, "failed": failures}


def pie_data(results, max_stocks=9):
    known = [r for r in results if not r["Unresolved"]]
    missing = [r for r in results if r["Unresolved"]]
    names = [r["Stock"] for r in known[:max_stocks]]
    amounts = [r["_value"] for r in known[:max_stocks]]
    remainder = sum(r["_value"] for r in known[max_stocks:])
    if remainder:
        names.append("Other stocks")
        amounts.append(remainder)
    if missing:
        names.append("Unresolved ETF exposure")
        amounts.append(sum(r["_value"] for r in missing))
    return names, amounts
