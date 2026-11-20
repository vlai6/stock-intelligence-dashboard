"""Indicative 5-year FCFF discounted cash-flow valuations for scanner candidates.

No valuation is an inclusion/exclusion filter. The estimates use explicitly
configurable assumptions; they are NOT independent professional fair values.
Yahoo financial statement data can be incomplete, missing or rate-limited.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd

from storage import data_root

MODEL_VERSION = "fcff-dcf-v1"
CACHE = data_root() / ".cache" / "intrinsic_value"
DEFAULT_WACC = 0.10
DEFAULT_GROWTH = 0.05
DEFAULT_TERMINAL_GROWTH = 0.025
CACHE_MAX_AGE = 7 * 86400


@dataclass(frozen=True)
class Assumptions:
    wacc: float = DEFAULT_WACC
    growth: float = DEFAULT_GROWTH
    terminal_growth: float = DEFAULT_TERMINAL_GROWTH
    forecast_years: int = 5

    def validate(self) -> None:
        if self.forecast_years != 5:
            raise ValueError("The agreed valuation model forecasts exactly five years")
        for val in (self.wacc, self.growth, self.terminal_growth):
            if not math.isfinite(val):
                raise ValueError("Valuation assumptions must be finite")
        if not (0.04 <= self.wacc <= 0.30):
            raise ValueError("WACC must be between 4% and 30%")
        if not (-0.30 <= self.growth <= 0.30):
            raise ValueError("FCFF growth must be between -30% and 30%")
        if not (-0.02 <= self.terminal_growth <= 0.06):
            raise ValueError("Terminal growth must be between -2% and 6%")
        if self.wacc <= self.terminal_growth:
            raise ValueError("WACC must exceed terminal growth")


def get_assumptions() -> Assumptions:
    a = Assumptions(
        wacc=float(os.getenv("DCF_WACC_PCT", "10")) / 100,
        growth=float(os.getenv("DCF_FCFF_GROWTH_PCT", "5")) / 100,
        terminal_growth=float(os.getenv("DCF_TERMINAL_GROWTH_PCT", "2.5")) / 100,
    )
    a.validate()
    return a


def dcf_per_share(base_fcff: float, cash: float, debt: float, shares: float,
                  assumptions: Assumptions | None = None) -> float:
    """EV = discounted FCFF years 1..5 + terminal value; equity = EV + cash - debt."""
    a = assumptions or Assumptions()
    a.validate()
    vals = (base_fcff, cash, debt, shares)
    if not all(math.isfinite(float(x)) for x in vals) or base_fcff <= 0 or shares <= 0 or debt < 0 or cash < 0:
        raise ValueError("FCFF and shares must be positive, cash/debt nonnegative and finite")
    forecasts = [base_fcff * (1 + a.growth) ** year for year in range(1, 6)]
    pv = sum(v / (1 + a.wacc) ** year for year, v in enumerate(forecasts, 1))
    terminal = forecasts[-1] * (1 + a.terminal_growth) / (a.wacc - a.terminal_growth)
    equity = pv + terminal / (1 + a.wacc) ** 5 + cash - debt
    if equity <= 0:
        raise ValueError("DCF implied zero/negative equity value")
    return equity / shares


def _numeric(value: Any) -> float | None:
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _latest_value(frame: pd.DataFrame | None, names: tuple[str, ...]) -> float | None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    # Statements typically expose dates as columns. Use most recent fiscal year.
    dates = sorted(frame.columns, key=lambda c: pd.Timestamp(c), reverse=True)
    for name in names:
        if name in frame.index:
            for col in dates:
                v = _numeric(frame.at[name, col])
                if v is not None:
                    return v
    return None


def _date_of_latest(frame: pd.DataFrame | None) -> str:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return "unknown"
    try:
        return pd.Timestamp(max(frame.columns)).date().isoformat()
    except Exception:
        return "unknown"


def _annual_fcff(cashflow: pd.DataFrame, income: pd.DataFrame) -> tuple[list[float], bool]:
    if not isinstance(cashflow, pd.DataFrame) or cashflow.empty:
        return [], False
    values = []
    interest_count = 0
    for col in sorted(cashflow.columns, key=lambda c: pd.Timestamp(c), reverse=True)[:3]:
        operating = _numeric(cashflow.at["Operating Cash Flow", col]) if "Operating Cash Flow" in cashflow.index else None
        if operating is None and "Total Cash From Operating Activities" in cashflow.index:
            operating = _numeric(cashflow.at["Total Cash From Operating Activities", col])
        capex = _numeric(cashflow.at["Capital Expenditure", col]) if "Capital Expenditure" in cashflow.index else None
        if operating is None or capex is None:
            continue
        # Yahoo reports capital expenditure as a negative cash-flow item; some feeds use positive.
        fcff_proxy = operating - abs(capex)
        interest = None
        if isinstance(income, pd.DataFrame) and not income.empty:
            for field in ("Interest Expense", "Interest Expense Non Operating"):
                if field in income.index and col in income.columns:
                    interest = _numeric(income.at[field, col])
                    if interest is not None:
                        break
        if interest is not None:
            # CFO generally includes interest paid for US GAAP companies. Add it back after tax.
            interest_count += 1
            fcff_proxy += abs(interest) * (1 - 0.21)
        values.append(fcff_proxy)
    return values, bool(values) and interest_count == len(values)


def unavailable(reason: str) -> dict:
    return {
        "intrinsic_value": None, "upside_downside_pct": None,
        "margin_of_safety_pct": None, "valuation_confidence": "N/A",
        "valuation_method": "5-year FCFF DCF", "valuation_note": reason,
        "valuation_as_of": None,
    }


def evaluate_statements(info: dict, cashflow: pd.DataFrame, balance: pd.DataFrame,
                        income: pd.DataFrame, price: float,
                        assumptions: Assumptions | None = None) -> dict:
    """Financial DCF: returns no value if sector/data make a meaningful DCF unsupported."""
    a = assumptions or Assumptions()
    a.validate()
    if not isinstance(info, dict) or not info:
        return unavailable("Missing company fundamentals")
    sector = str(info.get("sector") or "").lower()
    industry = str(info.get("industry") or "").lower()
    if sector == "financial services" or any(p in industry for p in ("reit", "real estate investment trust", "insurance", "bank")):
        return unavailable("Financial/REIT business: specialized valuation required")
    shares = _numeric(info.get("sharesOutstanding"))
    if shares is None:
        shares = _latest_value(income, ("Diluted Average Shares", "Basic Average Shares"))
    if not shares or shares <= 0:
        return unavailable("Missing current/diluted shares outstanding")
    cash = _latest_value(balance, ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash Equivalents"))
    debt = _latest_value(balance, ("Total Debt",))
    if debt is None:
        cur = _latest_value(balance, ("Current Debt And Capital Lease Obligation", "Current Debt"))
        long = _latest_value(balance, ("Long Term Debt And Capital Lease Obligation", "Long Term Debt"))
        if cur is not None and long is not None:
            debt = cur + long
        elif cur is not None and long is None:
            debt = cur
        elif long is not None and cur is None:
            debt = long
    if cash is None or debt is None:
        return unavailable("Cash or total debt unavailable")
    if cash < 0 or debt < 0:
        return unavailable("Cash/debt data invalid")
    fcffs, addback = _annual_fcff(cashflow, income)
    if len(fcffs) < 2:
        return unavailable("Fewer than two annual operating cash-flow / capex observations")
    base = median(fcffs)
    if base <= 0:
        return unavailable("Nonpositive normalized cash flow; DCF not meaningful")
    as_of = _date_of_latest(cashflow)
    if as_of != "unknown":
        try:
            year_diff = (datetime.now(timezone.utc).date() - pd.Timestamp(as_of).date()).days
            if year_diff > 850 or year_diff < -30:
                return unavailable("Financial statement dates are stale or invalid")
        except (ValueError, TypeError):
            return unavailable("Invalid financial statement date")
    price = _numeric(price)
    if not price or price <= 0:
        return unavailable("Missing valid market price")
    try:
        intrinsic = dcf_per_share(base, cash, debt, shares, a)
    except ValueError as exc:
        return unavailable(str(exc))
    # Use displayed two-decimal intrinsic value for displayed comparison percentages.
    intrinsic = round(intrinsic, 2)
    # Upside% relative to today; margin of safety% relative to intrinsic value.
    confidence = "Provisional" if len(fcffs) >= 3 and addback else "Low (proxy)"
    return {
        "intrinsic_value": intrinsic,
        "upside_downside_pct": round((intrinsic / price - 1) * 100, 1),
        "margin_of_safety_pct": round((intrinsic - price) / intrinsic * 100, 1),
        "valuation_confidence": confidence,
        "valuation_method": "5-year FCFF DCF" if addback else "5-year cash-flow proxy DCF",
        "valuation_note": f"Model assumptions: {a.growth:.1%} annual FCFF growth, {a.wacc:.1%} WACC, "
                          f"{a.terminal_growth:.1%} terminal growth; normalized {len(fcffs)}-yr median; "
                          f"21% tax shield if interest add-back is available",
        "valuation_as_of": as_of,
    }


def _safe_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.^-]{1,18}", value):
        raise ValueError("Invalid ticker")
    return value


def _cache_file(symbol: str) -> Path:
    return CACHE / (symbol.replace("/", "_") + ".json")


def _attach_price(v: dict, price: float) -> dict:
    out = dict(v)
    raw = _numeric(out.get("intrinsic_value"))
    if raw and _numeric(price) and price > 0:
        out["upside_downside_pct"] = round((raw / price - 1) * 100, 1)
        out["margin_of_safety_pct"] = round((raw - price) / raw * 100, 1)
    else:
        out["upside_downside_pct"] = None
        out["margin_of_safety_pct"] = None
    return out


def estimate(symbol: str, price: float, *, assumptions: Assumptions | None = None,
             fetcher=None, cache_dir: Path | None = None) -> dict:
    """Retrieve annual fundamentals for one candidate; cache estimates for 7 days."""
    a = assumptions or get_assumptions()
    a.validate()
    symbol = _safe_symbol(symbol)
    cache_path = ((cache_dir or CACHE) / _cache_file(symbol).name)
    signature = [MODEL_VERSION, asdict(a)]
    if cache_path.exists() and time.time() - cache_path.stat().st_mtime < CACHE_MAX_AGE:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("signature") == signature:
                return _attach_price(cached["value"], price)
        except (ValueError, OSError, KeyError, json.JSONDecodeError):
            pass
    try:
        if fetcher is None:
            import yfinance as yf
            fetcher = yf.Ticker
        t = fetcher(symbol)
        info = t.info or {}
        v = evaluate_statements(info, t.cashflow, t.balance_sheet, t.income_stmt, price, a)
    except Exception as exc:
        # Never fail the entire -3σ/-4σ signal report because valuation data is absent.
        v = unavailable(f"Financial data unavailable ({type(exc).__name__})")
    if v["valuation_confidence"] != "N/A":
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"signature": signature, "value": v}), encoding="utf-8")
            tmp.replace(cache_path)
        except OSError:
            pass
    return _attach_price(v, price)


def enrich_signals(rows: list[dict], *, limit: int | None = None, fetcher=None,
                   assumptions: Assumptions | None = None) -> list[dict]:
    """Attempt DCF for every qualifying email signal, regardless of Z-score."""
    a = assumptions or get_assumptions()
    a.validate()
    if limit is not None and limit < 0:
        raise ValueError("DCF limit cannot be negative")
    count = 0
    enriched = []
    # Incoming rows have already passed their market-cap-specific alert threshold.
    # A $50B+ company at -2.75sigma must receive the same valuation attempt
    # as a company at -3sigma or -4sigma.
    for row in sorted(rows, key=lambda x: float(x["z_score"])):
        new = dict(row)
        if limit is not None and count >= limit:
            v = unavailable("Valuation lookup limit reached; still included as regression signal")
        else:
            count += 1
            try:
                v = estimate(str(row["ticker"]), float(row["close"]),
                             assumptions=a, fetcher=fetcher)
            except Exception as exc:
                v = unavailable(f"Financial data unavailable ({type(exc).__name__})")
        enriched.append({**new, **v})
    return enriched



def enrich_table_rows(rows: list[dict], *, fetcher=None,
                      assumptions: Assumptions | None = None,
                      on_progress=None) -> list[dict]:
    """On-demand dashboard DCF for EVERY visible stock, regardless of Z-score.

    The email enrichment pathway also evaluates all incoming qualifying signals.
    Preserve input order and all scanner columns; never discard a stock because
    its financial statements cannot support the illustrative DCF model.
    """
    a = assumptions or get_assumptions()
    a.validate()
    output = []
    total = len(rows)
    for i, row in enumerate(rows, 1):
        candidate = dict(row)
        try:
            v = estimate(str(row["ticker"]), float(row["close"]),
                         assumptions=a, fetcher=fetcher)
        except Exception as exc:
            v = unavailable(f"Financial data unavailable ({type(exc).__name__})")
        output.append({**candidate, **v})
        if on_progress is not None:
            on_progress(i, total)
    return output
