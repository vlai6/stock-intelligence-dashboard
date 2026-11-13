
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st


def historical_cagr(prices):
    """Annualized adjusted-price growth using actual dates."""
    if prices is None or len(prices) < 2:
        return np.nan

    prices = prices.dropna().sort_index()

    if len(prices) < 2:
        return np.nan

    start = float(prices.iloc[0])
    end = float(prices.iloc[-1])

    years = (
        prices.index[-1] - prices.index[0]
    ).total_seconds() / (365.2425 * 86400)

    if start <= 0 or end <= 0 or years <= 0:
        return np.nan

    return (end / start) ** (1 / years) - 1


def statement_value(statement, names, column):
    """Read a financial statement row using alternative labels."""
    for name in names:
        if name in statement.index:
            value = statement.loc[name, column]

            if isinstance(value, pd.Series):
                value = value.iloc[0]

            if pd.notna(value):
                return float(value)

    return np.nan


@st.cache_data(show_spinner=False)
def calculate_roic(ticker):
    """
    ROIC = NOPAT / average invested capital

    NOPAT = EBIT * (1 - effective tax rate)
    Invested capital = debt + equity - cash
    """
    try:
        stock = yf.Ticker(ticker)

        income = stock.income_stmt
        balance = stock.balance_sheet

        if income.empty or balance.empty:
            return np.nan

        dates = sorted(
            set(income.columns).intersection(balance.columns),
            reverse=True
        )

        if len(dates) < 2:
            return np.nan

        current, previous = dates[:2]

        ebit = statement_value(
            income,
            ["EBIT", "Operating Income"],
            current
        )

        tax = statement_value(
            income,
            ["Tax Provision"],
            current
        )

        pretax = statement_value(
            income,
            ["Pretax Income"],
            current
        )

        if not np.isfinite(ebit):
            return np.nan

        if not np.isfinite(tax) or not np.isfinite(pretax):
            return np.nan

        if pretax <= 0:
            return np.nan

        tax_rate = np.clip(tax / pretax, 0, 1)
        nopat = ebit * (1 - tax_rate)

        capital_values = []

        for date in [current, previous]:
            debt = statement_value(
                balance,
                ["Total Debt"],
                date
            )

            equity = statement_value(
                balance,
                [
                    "Stockholders Equity",
                    "Total Equity Gross Minority Interest"
                ],
                date
            )

            cash = statement_value(
                balance,
                [
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash And Cash Equivalents"
                ],
                date
            )

            if not all(np.isfinite(x) for x in [debt, equity, cash]):
                return np.nan

            capital_values.append(debt + equity - cash)

        average_capital = np.mean(capital_values)

        if average_capital <= 0:
            return np.nan

        return nopat / average_capital

    except (KeyError, TypeError, ValueError, IndexError):
        return np.nan

