"""Optional conservative valuation/financial-health screeners for Stock Intelligence Toolkit.

IMPORTANT: rough five-year, equity-cash-flow proxy; NOT a full FCFF/WACC enterprise DCF.
No data -> N/A. No fabricated balances or downside floors.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

VALUE_EXTRA = [
    "DCF Bear / Share", "DCF Base / Share", "DCF Bull / Share",
    "DCF Base Upside", "Market-Implied FCF Growth",
    "Normalized FCF", "FCF Stability", "SBC / Revenue", "Share Dilution (YoY)",
]
HEALTH_METRICS = [
    "Current Ratio", "Quick Ratio", "Net Debt", "Net Debt / EBITDA",
    "Interest Coverage", "FCF / Total Debt", "Operating Margin",
    "Revenue Growth", "ROIC", "Share Dilution (YoY)",
]
EXTRA_METRIC_NAMES = set(VALUE_EXTRA + HEALTH_METRICS)
EXTRA_EXPLANATIONS = {
    "DCF Bear / Share": "Indicative 5-year discounted FCF/share at -5% annual FCF growth, 10% equity hurdle and 2% terminal growth. NOT a rigorous FCFF/WACC valuation; N/A if inputs are insufficient.",
    "DCF Base / Share": "Indicative 5-year discounted FCF/share at +5% annual FCF growth, 10% equity hurdle and 2% terminal growth. Starting FCF is normalized; SBC is deducted when historical SBC is available.",
    "DCF Bull / Share": "Indicative 5-year discounted FCF/share at +15% annual FCF growth, 10% equity hurdle and 2% terminal growth. A scenario, not a prediction.",
    "DCF Base Upside": "Estimated DCF base value/share divided by latest adjusted close, minus one. Highly sensitive to growth, discount and terminal assumptions.",
    "Market-Implied FCF Growth": "Flat five-year annual FCF growth rate that would approximately justify the observed share price under the same cash-flow proxy, 10% hurdle and 2% terminal growth. N/A if no solution in -50% to +60%.",
    "Normalized FCF": "Median of up to 4 yearly free-cash-flow observations where available; latest FCF as fallback. Negative readings are not excluded.",
    "FCF Stability": "1 / (1 + coefficient of variation) for up to 4 historical FCF observations, if median is positive and >=3 years exist. Higher means more stable. Simplified diagnostic.",
    "SBC / Revenue": "Latest stock-based compensation / revenue when both are available. High SBC can reduce economic owner earnings.",
    "Share Dilution (YoY)": "Change in annual diluted weighted-average share count from the latest available two fiscal years. Negative means buybacks outweighed issuance.",
    "Current Ratio": "Current assets / current liabilities, from the company summary.",
    "Quick Ratio": "Liquid current assets / current liabilities, from the company summary.",
    "Net Debt": "Total debt minus cash and cash equivalents; negative indicates net cash.",
    "Net Debt / EBITDA": "Net debt divided by EBITDA. Cross-industry comparisons require caution.",
    "Interest Coverage": "Operating earnings / interest expense (company summary). N/A if not reported.",
    "FCF / Total Debt": "Annual free cash flow divided by total debt; not a debt maturity schedule.",
    "Operating Margin": "Operating income divided by revenue.",
    "Revenue Growth": "Reported year-over-year revenue growth, when available.",
    "ROIC": "Return on invested capital; calculated by your existing ROIC module when selected.",
}
PERCENT_EXTRA = {"DCF Base Upside", "Market-Implied FCF Growth", "FCF Stability", "SBC / Revenue", "Share Dilution (YoY)", "FCF / Total Debt", "Operating Margin", "Revenue Growth", "ROIC"}
DOLLAR_EXTRA = {"DCF Bear / Share", "DCF Base / Share", "DCF Bull / Share"}
BILLIONS_EXTRA = {"Normalized FCF", "Net Debt"}


def _number(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (ValueError, TypeError):
        return None


def _row(df, candidates):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    matches = {str(x).strip().lower(): x for x in df.index}
    for label in candidates:
        if label.lower() in matches:
            return [x for x in (_number(y) for y in df.loc[matches[label.lower()]].tolist()) if x is not None]
    return []


def _series(df, candidates):
    vals = _row(df, candidates)
    return vals[:4]


def _dcf(starting_fcf, shares, growth, discount=0.10, terminal_growth=0.02):
    if starting_fcf is None or shares is None or starting_fcf <= 0 or shares <= 0 or growth <= -1 or discount <= terminal_growth:
        return None
    pv = sum(starting_fcf * (1+growth)**t / (1+discount)**t for t in range(1, 6))
    final = starting_fcf * (1+growth)**5
    pv_terminal = final * (1+terminal_growth) / (discount-terminal_growth) / (1+discount)**5
    return (pv + pv_terminal) / shares


@st.cache_data(ttl=3600, show_spinner=False)
def compute_extra_metrics(ticker, stock_info, last_close):
    """All assumptions are explicit. None means insufficient evidence, never zero."""
    info = stock_info if isinstance(stock_info, dict) else {}
    out = {key: None for key in EXTRA_METRIC_NAMES}
    annual_cf = pd.DataFrame()
    annual_financials = pd.DataFrame()
    try:
        yf_obj = yf.Ticker(str(ticker))
        annual_cf = yf_obj.cashflow
        annual_financials = yf_obj.financials
    except Exception:
        pass
    fcf_history = _series(annual_cf, ["Free Cash Flow"])
    if not fcf_history:
        op_cash = _series(annual_cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"])
        capex = _series(annual_cf, ["Capital Expenditure", "Capital Expenditures"])
        if op_cash and capex:
            fcf_history = [a - abs(b) for a, b in zip(op_cash, capex)]
    reported_fcf = _number(info.get("freeCashflow"))
    normalized = float(np.median(fcf_history)) if fcf_history else reported_fcf
    out["Normalized FCF"] = normalized
    if len(fcf_history) >= 3 and normalized and normalized > 0:
        out["FCF Stability"] = 1 / (1 + float(np.std(fcf_history) / abs(np.mean(fcf_history)))) if abs(np.mean(fcf_history)) > 0 else None

    revenue = _number(info.get("totalRevenue"))
    sbc_history = _series(annual_cf, ["Stock Based Compensation", "Stock-based Compensation"])
    sbc = sbc_history[0] if sbc_history else _number(info.get("stockBasedCompensation"))
    if revenue and revenue > 0 and sbc is not None:
        out["SBC / Revenue"] = sbc / revenue

    diluted_shares = _series(annual_financials, ["Diluted Average Shares", "Diluted Weighted Average Shares", "Diluted Average Shares Outstanding"])
    if len(diluted_shares) >= 2 and diluted_shares[1] > 0:
        out["Share Dilution (YoY)"] = diluted_shares[0] / diluted_shares[1] - 1

    shares = _number(info.get("sharesOutstanding")) or _number(info.get("impliedSharesOutstanding"))
    price = _number(last_close) or _number(info.get("currentPrice")) or _number(info.get("regularMarketPrice"))
    # SBC cost is reflected in the cash-flow proxy when available. Do NOT additionally
    # apply projected dilution to this same scenario (would double-count compensation).
    owner_cash_proxy = normalized - max(0, sbc) if normalized is not None and sbc is not None else normalized
    if owner_cash_proxy and owner_cash_proxy > 0 and shares and shares > 0:
        for key, growth in (("DCF Bear / Share", -.05), ("DCF Base / Share", .05), ("DCF Bull / Share", .15)):
            out[key] = _dcf(owner_cash_proxy, shares, growth)
        if price and price > 0 and out["DCF Base / Share"] is not None:
            out["DCF Base Upside"] = out["DCF Base / Share"] / price - 1
            low, high = -0.5, 0.6
            low_price = _dcf(owner_cash_proxy, shares, low)
            high_price = _dcf(owner_cash_proxy, shares, high)
            if low_price is not None and high_price is not None and low_price <= price <= high_price:
                for _ in range(45):
                    middle = (low + high) / 2
                    mid_price = _dcf(owner_cash_proxy, shares, middle)
                    if mid_price < price:
                        low = middle
                    else:
                        high = middle
                out["Market-Implied FCF Growth"] = (low + high) / 2

    debt = _number(info.get("totalDebt"))
    cash = _number(info.get("totalCash"))
    ebitda = _number(info.get("ebitda"))
    net_debt = debt - cash if debt is not None and cash is not None else None
    out.update({
        "Current Ratio": _number(info.get("currentRatio")),
        "Quick Ratio": _number(info.get("quickRatio")),
        "Net Debt": net_debt,
        "Net Debt / EBITDA": net_debt / ebitda if net_debt is not None and ebitda and ebitda > 0 else None,
        "Interest Coverage": _number(info.get("interestCoverage")),
        "FCF / Total Debt": reported_fcf / debt if reported_fcf is not None and debt and debt > 0 else None,
        "Operating Margin": _number(info.get("operatingMargins")),
        "Revenue Growth": _number(info.get("revenueGrowth")),
    })
    return out


def format_extra_metric(key, value):
    value = _number(value)
    if value is None:
        return "N/A"
    if key in DOLLAR_EXTRA:
        return f"${value:,.2f}"
    if key in BILLIONS_EXTRA:
        return f"${value / 1e9:,.2f}B"
    if key in PERCENT_EXTRA:
        return f"{value:.2%}"
    return f"{value:,.2f}"
