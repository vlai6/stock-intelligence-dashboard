"""ETF / individual-stock portfolio X-ray powered solely by TickerInside."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
import math
import re

VALID = re.compile(r"^[A-Z][A-Z0-9.\-]{0,12}$")
TICKERINSIDE_API = "https://tickerinside.com/api/v1"


def _tickerinside_json(path: str) -> dict:
    """Read an allowlisted TickerInside API path; never fetch arbitrary URLs."""
    import requests
    if path != "identifiers.json" and not re.fullmatch(
        r"fund/[a-z0-9.\-]+\.json", path
    ):
        raise ValueError("Unexpected TickerInside API path")
    url = f"{TICKERINSIDE_API}/{path}"
    try:
        response = requests.get(url, timeout=25, headers={
            "User-Agent": "StockIntelligence-XRay/1.0",
            "Accept": "application/json",
        })
        if response.status_code == 404:
            raise ValueError(f"No TickerInside data for {path}")
        response.raise_for_status()
        if len(response.content) > 3_000_000:
            raise ValueError("TickerInside response exceeds the allowed size")
        payload = response.json()
    except requests.RequestException as exc:
        raise ValueError(f"TickerInside request failed: {exc}") from exc
    except ValueError as exc:
        if "TickerInside" in str(exc):
            raise
        raise ValueError("TickerInside returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("TickerInside returned unexpected JSON structure")
    return payload


def tickerinside_identifiers() -> dict[str, str]:
    """One provider for stock, ETF and ETN identities; caller caches the index."""
    payload = _tickerinside_json("identifiers.json")
    fields = payload.get("fields")
    securities = payload.get("securities")
    if not isinstance(fields, list) or not isinstance(securities, list):
        raise ValueError("TickerInside's security identifier index is unavailable")
    try:
        t_idx, type_idx = fields.index("ticker"), fields.index("asset_type")
    except ValueError as exc:
        raise ValueError("TickerInside identifiers lack security type fields") from exc
    kinds = {}
    for item in securities:
        if not isinstance(item, list) or len(item) <= max(t_idx, type_idx):
            continue
        symbol = str(item[t_idx] or "").strip().upper()
        asset_type = str(item[type_idx] or "").strip().lower()
        if VALID.fullmatch(symbol):
            if asset_type in {"etf", "etn"}:
                kinds[symbol] = "ETF"
            elif asset_type == "stock":
                kinds[symbol] = "STOCK"
    if not kinds:
        raise ValueError("TickerInside returned an empty security identifier list")
    return kinds


def security_type(ticker: str, identifiers: dict[str, str] | None = None) -> str:
    """TickerInside classifies stocks/ETFs; explicit cash/Treasury IDs are other."""
    ticker = ticker_of(ticker)
    # Cash and Treasury CUSIPs are already non-equity holdings supplied by
    # the user. Don't attempt to look these up as TickerInside stock tickers.
    if ticker == "Cash & Cash Inv" or re.fullmatch(r"\d[A-Z0-9]{8}", ticker):
        return "OTHER"
    kinds = identifiers if identifiers is not None else tickerinside_identifiers()
    kind = kinds.get(ticker)
    if kind not in {"ETF", "STOCK"}:
        raise ValueError(
            f"{ticker} is not in TickerInside's security directory; "
            "this X-Ray cannot verify it as a stock or ETF."
        )
    return kind

@dataclass(frozen=True)
class Holdings:
    ticker: str
    weights: dict[str, float]  # Each is a fraction of fund NAV
    source: str
    as_of: str = ""
    page_url: str = ""

    @property
    def coverage(self):
        return sum(self.weights.values())


def ticker_of(value):
    ticker = str(value or "").strip().upper().replace("/", ".")
    if ticker in {
        "CASH", "CASH & CASH INV", "CASH & CASH INVESTMENTS",
        "CASH & EQUIVALENTS", "CASH AND CASH INVESTMENTS",
    }:
        return "Cash & Cash Inv"
    # Nine-character CUSIPs such as 912797WG8 and 91282CMB4 represent
    # directly owned securities, not unsupported stock tickers.
    if re.fullmatch(r"\d[A-Z0-9]{8}", ticker):
        return ticker
    if not VALID.fullmatch(ticker):
        raise ValueError("Ticker must be a symbol, Treasury CUSIP, or cash entry")
    return ticker


def issuer_holdings(ticker: str) -> Holdings:
    """TickerInside percentages become NAV fractions, keeping unmapped NAV intact.

    Bonds, derivatives, commodities and mixed funds are not classified as
    individual stock exposure. They remain unresolved in the existing chart.
    """
    ticker = ticker_of(ticker)
    data = _tickerinside_json(f"fund/{ticker.lower()}.json")
    kind = str(data.get("holdings_kind") or "").strip().lower()
    if kind not in {"", "stock"}:
        raise ValueError(
            f"TickerInside classifies {ticker} holdings as {kind}, not stocks; "
            "keeping this position unresolved."
        )
    weights_raw = data.get("holdings")
    if not isinstance(weights_raw, dict) or not weights_raw:
        raise ValueError(
            f"TickerInside has no reported stock holdings for {ticker}; "
            "keeping this position unresolved."
        )
    proportions = {}
    for symbol, pct_raw in weights_raw.items():
        if not isinstance(symbol, str) or not symbol.strip():
            continue
        try:
            pct = float(pct_raw)
        except (ValueError, TypeError):
            continue
        if not math.isfinite(pct) or pct < 0:
            raise ValueError(f"TickerInside reported an invalid weight for {ticker}")
        if pct > 0:
            label = symbol.strip().upper()
            proportions[label] = proportions.get(label, 0.0) + pct / 100.0
    total = sum(proportions.values())
    if not proportions or total <= 0:
        raise ValueError(f"TickerInside reported no usable holdings for {ticker}")
    if total > 1.02:
        raise ValueError(f"TickerInside holdings for {ticker} total {total:.1%}")
    if total > 1.0:
        proportions = {symbol: weight / total for symbol, weight in proportions.items()}
    source_layer = str(data.get("source_layer") or "unspecified").replace("_", " ")
    as_of = str(data.get("holdings_as_of") or data.get("report_date") or "")
    page_url = str(data.get("page_url") or "")
    if not page_url.startswith("https://tickerinside.com/"):
        page_url = ""
    return Holdings(
        ticker=ticker,
        weights=proportions,
        source=f"TickerInside ({source_layer})",
        as_of=as_of,
        page_url=page_url,
    )

def portfolio_rows(positions, etfs, failures=None):
    """Combine weighted holdings and direct positions, preserving missing NAV."""
    failures = failures or {}
    dollars = defaultdict(float)
    contributors = defaultdict(lambda: defaultdict(float))
    total = 0.0
    details = []
    other_total = 0.0
    for position in positions:
        ticker = ticker_of(position["ticker"])
        amount = float(position["amount"])
        kind = str(position["type"]).strip().upper()
        if kind not in {"ETF", "STOCK", "OTHER", "UNKNOWN"} or not math.isfinite(amount) or amount <= 0:
            raise ValueError("Every position needs stock, ETF, other or unknown type, and positive amount")
        total += amount
        if kind == "UNKNOWN":
            # Keep its allocation in the portfolio rather than guessing it
            # is a stock or omitting it (both would distort exposure).
            missing = "Unverified " + ticker
            dollars[missing] += amount
            contributors[missing]["Direct"] += amount
            continue
        if kind in {"STOCK", "OTHER"}:
            dollars[ticker] += amount
            contributors[ticker]["Direct"] += amount
            if kind == "OTHER":
                other_total += amount
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
            "As of": holdings.as_of or "Unknown", "Source": holdings.source,
            "TickerInside page": holdings.page_url,
        })
    if total <= 0:
        raise ValueError("Add at least one position before analyzing")
    results = sorted(({
        "Stock": stock, "Amount ($)": round(value, 2),
        "Portfolio %": round(100 * value / total, 3),
        # Preserve small percentage-point exposures from CSV imports. Dollar
        # portfolios are still displayed to cents by the UI formatter.
        "Direct Amount": round(contributors[stock].get("Direct", 0.0), 6),
        "ETF Amount": round(value - contributors[stock].get("Direct", 0.0), 6),
        "Unresolved": stock.startswith(("Unresolved ", "Unreported ", "Unverified ")),
        "_value": value,
    } for stock, value in dollars.items() if value > 1e-7),
        key=lambda row: row["_value"], reverse=True)
    unresolved = sum(x["_value"] for x in results if x["Unresolved"])
    return results, {"total": total, "mapped": total - unresolved,
                     "unresolved": unresolved, "other_assets": other_total,
                     "sources": details, "failed": failures}


def pie_data(results):
    """Include every resolved stock as its own slice; never aggregate small stocks.

    The legend and on-slice text may hide small percentages, but the pie and
    hover details always retain all individual stock exposure. Only genuinely
    unresolved ETF exposure is combined into a distinct non-stock slice.
    """
    known = [r for r in results if not r["Unresolved"]]
    missing = [r for r in results if r["Unresolved"]]
    names = [r["Stock"] for r in known]
    amounts = [r["_value"] for r in known]
    missing_etfs = [r for r in missing if not r["Stock"].startswith("Unverified ")]
    unverified = [r for r in missing if r["Stock"].startswith("Unverified ")]
    if missing_etfs:
        names.append("Unresolved ETF exposure")
        amounts.append(sum(r["_value"] for r in missing_etfs))
    if unverified:
        names.append("Unclassified positions")
        amounts.append(sum(r["_value"] for r in unverified))
    return names, amounts

def pie_legend_labels(labels, amounts):
    """Show portfolio allocation in every slice's legend label, to 0.1%."""
    if len(labels) != len(amounts):
        raise ValueError("Legend labels and pie amounts must match")
    total = sum(amounts)
    if total <= 0:
        return [str(label) for label in labels]
    return [
        f"{label} {100 * amount / total:.1f}%"
        for label, amount in zip(labels, amounts)
    ]
