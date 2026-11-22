"""Historical ETF constituent look-through from TickerInside's dated SEC filings.

These are fund holdings, NOT price history, and NOT the historical prices of
the user's portfolio. Quarterly fund N-PORT reports are selected as-of each
requested date; some ETFs/trusts have no history and are left unresolved.
"""
from __future__ import annotations

from datetime import date
import math

import requests

from portfolio_xray import Holdings, ticker_of

URL_ROOT = "https://tickerinside.com/api/v1"


class HistoricalHoldingsUnavailable(ValueError):
    """No dated SEC holdings exist for the given ETF and date."""


def _historical_holdings_payload(ticker: str, as_of: date) -> dict:
    """Fetch exactly one allowlisted ticker/date; no arbitrary URL input."""
    symbol = ticker_of(ticker)
    if symbol == "Cash & Cash Inv" or symbol[0].isdigit():
        raise HistoricalHoldingsUnavailable("Cash/CUSIPs have no ETF constituents.")
    if not isinstance(as_of, date) or as_of > date.today():
        raise ValueError("Requested holdings date must not be in the future.")
    url = f"{URL_ROOT}/history/{symbol.lower()}/{as_of.isoformat()}.json"
    try:
        response = requests.get(
            url, timeout=24, headers={
                "User-Agent": "StockIntelligenceToolkit-XRay/1.0",
                "Accept": "application/json",
            },
        )
        if response.status_code in (400, 404):
            try:
                body = response.json()
            except ValueError:
                body = {}
            if not isinstance(body, dict):
                body = {}
            reason = str(body.get("reason") or "not_available")[:70]
            if reason == "before_first_report":
                first = str(body.get("first_report") or "unknown date")
                raise HistoricalHoldingsUnavailable(
                    f"{symbol}: first historical SEC report is {first}."
                )
            raise HistoricalHoldingsUnavailable(
                f"{symbol}: historical holdings unavailable for "
                f"{as_of.isoformat()} ({reason})."
            )
        response.raise_for_status()
        if len(response.content) > 3_000_000:
            raise ValueError("Historical holdings response exceeded 3 MB.")
        payload = response.json()
    except requests.RequestException as exc:
        raise HistoricalHoldingsUnavailable(
            f"{symbol}: TickerInside history request failed "
            f"({type(exc).__name__})."
        ) from exc
    if not isinstance(payload, dict):
        raise HistoricalHoldingsUnavailable(
            f"{symbol}: no usable historical holdings response."
        )
    return payload


def parse_historical_holdings(
    ticker: str, requested: date, payload: dict,
) -> Holdings:
    """Return only verified stock weights with a report date <= requested."""
    symbol = ticker_of(ticker)
    raw = payload.get("holdings")
    kind = str(payload.get("holdings_kind") or "stock").lower()
    if kind not in ("stock", ""):
        raise HistoricalHoldingsUnavailable(
            f"{symbol}: historical report contains {kind}, not stock shares."
        )
    if not isinstance(raw, dict) or not raw:
        raise HistoricalHoldingsUnavailable(
            f"{symbol}: historical report has no mapped stock holdings."
        )
    reported = str(payload.get("holdings_as_of") or payload.get("report_date") or "")
    try:
        report_date = date.fromisoformat(reported)
    except ValueError as exc:
        raise HistoricalHoldingsUnavailable(
            f"{symbol}: historical report does not provide a valid holdings date."
        ) from exc
    if report_date > requested:
        raise HistoricalHoldingsUnavailable(
            f"{symbol}: report date is later than the requested as-of date."
        )
    weights: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            continue
        try:
            pct = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(pct) or pct < 0:
            raise HistoricalHoldingsUnavailable(
                f"{symbol}: historical file contains an invalid stock weight."
            )
        if pct:
            stock = key.upper().strip()
            weights[stock] = weights.get(stock, 0.0) + pct / 100.0
    total = sum(weights.values())
    if total <= 0 or total > 1.02:
        raise HistoricalHoldingsUnavailable(
            f"{symbol}: historical stock weights cannot be verified."
        )
    if total > 1:
        weights = {k: v / total for k, v in weights.items()}
    return Holdings(
        ticker=symbol, weights=weights,
        source="TickerInside (historical SEC N-PORT)",
        as_of=reported,
        page_url=f"{URL_ROOT}/history/{symbol.lower()}/{requested.isoformat()}.json",
    )


def historical_issuer_holdings(ticker: str, requested: date) -> Holdings:
    return parse_historical_holdings(
        ticker, requested, _historical_holdings_payload(ticker, requested)
    )


def exposure_changes(older: list[dict], latest: list[dict]) -> list[dict]:
    """Full look-through portfolio % by row including missing exposures."""
    before = {r["Stock"]: float(r["Portfolio %"]) for r in older}
    after = {r["Stock"]: float(r["Portfolio %"]) for r in latest}
    output = [
        {
            "Ticker / exposure": symbol,
            "Historical %": round(before.get(symbol, 0.0), 3),
            "Latest %": round(after.get(symbol, 0.0), 3),
            "Change (pp)": round(after.get(symbol, 0.0) - before.get(symbol, 0.0), 3),
        }
        for symbol in set(before) | set(after)
    ]
    return sorted(output, key=lambda r: abs(r["Change (pp)"]), reverse=True)
