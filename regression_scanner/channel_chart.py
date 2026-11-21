"""Selected-stock regression-channel chart for the Streamlit dashboard.

Keep the existing scanner math unchanged. The default view aggregates daily candles to weekly while drawing the SAME
channel calculated from daily closes. Plotly opens in pan mode; the app enables
mouse-wheel zoom. The initial view matches the saved regression lookback, but
users can pan/zoom outside it (no hard axis bounds).
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from lookback import price_history_start, regression_sessions
from regression import Point, regression_point

DAILY_BASIS = "Scanner channel (daily closes)"
WEEKLY_BASIS = "TradingView-style channel (weekly closes)"
# Selection affects the chart only; screening still uses the original −3σ/−4σ rules.
BAND_OPTIONS = ("+1σ", "+2σ", "+3σ", "+4σ", "−1σ", "−2σ", "−3σ", "−4σ")
DEFAULT_BANDS = ("+1σ", "+2σ", "−3σ", "−4σ")
BAND_STYLES = {
    "−4σ": ("Lower4", "#27b36a"),
    "−3σ": ("Lower3", "#c8e95b"),
    "−2σ": ("Lower2", "#efba68"),
    "−1σ": ("Lower1", "#e1d394"),
    "+1σ": ("Upper1", "#5da8fc"),
    "+2σ": ("Upper2", "#45c8be"),
    "+3σ": ("Upper3", "#a4cf66"),
    "+4σ": ("Upper4", "#269668"),
}
_REQUIRED = ("Open", "High", "Low", "Close")


@dataclass
class ChannelChartData:
    bars: pd.DataFrame  # weekly OHLCV, with line and +/-3/4-sigma bands
    point: Point
    lookback_bars: int
    basis: str
    snapshot_years: float = 10.0  # Saved scan lookback; independent of sidebar edits


def normalize_yahoo_ohlcv(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Accept both flat and modern yfinance MultiIndex column layouts."""
    if raw is None or raw.empty:
        raise ValueError(f"No historical prices returned for {ticker}.")
    raw = raw.copy()
    if isinstance(raw.columns, pd.MultiIndex):
        for level in range(raw.columns.nlevels):
            if ticker in raw.columns.get_level_values(level):
                raw = raw.xs(ticker, axis=1, level=level)
                break
    raw.columns = [str(c).strip().title() for c in raw.columns]
    missing = [name for name in _REQUIRED if name not in raw.columns]
    if missing:
        raise ValueError(f"Missing price fields for {ticker}: {', '.join(missing)}")

    names = list(_REQUIRED) + (["Volume"] if "Volume" in raw.columns else [])
    cleaned = raw[names].copy()
    for name in names:
        cleaned[name] = pd.to_numeric(cleaned[name], errors="coerce")
    cleaned = cleaned.dropna(subset=list(_REQUIRED))
    cleaned = cleaned.loc[(cleaned[list(_REQUIRED)] > 0).all(axis=1)]
    if "Volume" not in cleaned:
        cleaned["Volume"] = 0.0
    cleaned["Volume"] = cleaned["Volume"].fillna(0).clip(lower=0)
    cleaned.index = pd.to_datetime(cleaned.index)
    if cleaned.index.tz is not None:
        cleaned.index = cleaned.index.tz_localize(None)
    cleaned.index = cleaned.index.normalize()
    cleaned = cleaned[~cleaned.index.duplicated(keep="last")].sort_index()
    if cleaned.empty:
        raise ValueError(f"No valid OHLC bars returned for {ticker}.")
    return cleaned


def download_chart_prices(ticker: str, target_session: str, years: float) -> pd.DataFrame:
    """Download OHLC *only for the selected row*, as of the saved scan date."""
    ticker = str(ticker).upper().strip()
    if not re.fullmatch(r"[A-Z0-9.^-]{1,18}", ticker):
        raise ValueError("Unexpected ticker format; chart request was rejected.")
    # Import lazily: pure channel tests do not need a Yahoo connection.
    import yfinance as yf

    # Download only enough history for the saved regression period + buffer.
    start = price_history_start(target_session, years)
    end = (pd.Timestamp(target_session) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    raw = yf.download(
        tickers=ticker, start=start, end=end, interval="1d",
        auto_adjust=False, progress=False, threads=False, timeout=20,
    )
    frame = normalize_yahoo_ohlcv(raw, ticker)
    frame = frame.loc[:pd.Timestamp(target_session)]
    if frame.empty:
        raise ValueError(f"No chart data available before {target_session}.")
    return frame


def weekly_ohlcv(daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate real daily candles; label each week with its final *trading* day."""
    date_index = pd.DatetimeIndex(daily.index)
    working = daily[list(_REQUIRED) + ["Volume"]].copy()
    working["TradingDate"] = date_index
    weekly = working.resample("W-FRI").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last",
        "Volume": "sum", "TradingDate": "last",
    }).dropna(subset=list(_REQUIRED))
    actual_dates = pd.DatetimeIndex(weekly.pop("TradingDate"))
    weekly.index = actual_dates
    return weekly


def _band_columns(fit: np.ndarray, sigma: float, index: pd.Index) -> pd.DataFrame:
    """Build optional ±1/2/3/4σ overlays without changing the regression fit."""
    return pd.DataFrame({
        "Center": fit,
        **{f"Upper{i}": fit + i * sigma for i in range(1, 5)},
        **{f"Lower{i}": fit - i * sigma for i in range(1, 5)},
    }, index=index)


def _snapshot_start(last_day: pd.Timestamp, years: float) -> pd.Timestamp:
    """Calendar-year chart boundary; support fractional years such as 5.5."""
    years_float = float(years)
    whole = int(years_float)
    fractional_days = int(round((years_float - whole) * 365.25))
    return (pd.Timestamp(last_day).normalize()
            - pd.DateOffset(years=whole)
            - pd.Timedelta(days=fractional_days))


def make_channel_data(daily: pd.DataFrame, years: float, basis: str = DAILY_BASIS) -> ChannelChartData:
    """Fit the selected N-bar channel and show the same years on the x-axis.

    Regression remains defined by 250 trading sessions per year; the chart
    visible boundary uses calendar years. Some earliest snapshot candles may
    precede the first fitted regression line by a few trading sessions.
    """
    if daily.empty:
        raise ValueError("No daily prices available for this chart.")
    snapshot_start = _snapshot_start(pd.Timestamp(daily.index[-1]), years)
    if basis == DAILY_BASIS:
        length = regression_sessions(years)
        if len(daily) < length:
            raise ValueError(f"Chart needs {length:,} daily sessions but received {len(daily):,}.")
        sampled = daily.iloc[-length:].copy()
        point = regression_point(sampled["Close"].to_numpy(dtype=float))
        fit = point.line + point.slope * (np.arange(length, dtype=float) - (length - 1))
        daily_bands = _band_columns(fit, point.sigma, sampled.index)
        # Show only the selected chart horizon, with N fitted channel bars.
        snapshot_daily = daily.loc[daily.index >= snapshot_start]
        bars = weekly_ohlcv(snapshot_daily)
        weekly_bands = daily_bands.resample("W-FRI").last().dropna()
        # Normalize the fitted week's timestamp to the last real trade date.
        # This is needed to align with the actual weekly candles.
        fitted_weekly = weekly_ohlcv(sampled)
        weekly_bands.index = fitted_weekly.index
        bars = bars.join(weekly_bands)
    elif basis == WEEKLY_BASIS:
        length = int(round(float(years) * 52))
        weeks = weekly_ohlcv(daily)
        if len(weeks) < length:
            raise ValueError(f"Weekly chart needs {length:,} bars but received {len(weeks):,}.")
        sampled = weeks.iloc[-length:].copy()
        point = regression_point(sampled["Close"].to_numpy(dtype=float))
        fit = point.line + point.slope * (np.arange(length, dtype=float) - (length - 1))
        bands = _band_columns(fit, point.sigma, sampled.index)
        bars = weeks.loc[weeks.index >= snapshot_start].copy().join(bands)
    else:
        raise ValueError("Unsupported channel basis")
    return ChannelChartData(bars=bars, point=point, lookback_bars=length, basis=basis,
                            snapshot_years=float(years))


def channel_figure(
    chart: ChannelChartData,
    ticker: str,
    selected_bands: Sequence[str] = DEFAULT_BANDS,
) -> go.Figure:
    """Weekly candlesticks with mouse-wheel zoom and unrestricted panning."""
    unknown = set(selected_bands) - set(BAND_OPTIONS)
    if unknown:
        raise ValueError(f"Unsupported standard deviation bands: {sorted(unknown)}")
    bands_to_draw = set(selected_bands)
    bars = chart.bars
    if bars.empty:
        raise ValueError("No chart candles available to display.")
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.025,
        row_heights=[0.81, 0.19],
    )
    # A −4σ-to−3σ shaded buy zone is rendered only when both are selected.
    for label in ("−4σ", "−3σ", "−2σ", "−1σ", "+1σ", "+2σ", "+3σ", "+4σ"):
        if label not in bands_to_draw:
            continue
        column, color = BAND_STYLES[label]
        extra = {}
        if label == "−3σ" and "−4σ" in bands_to_draw:
            extra = {"fill": "tonexty", "fillcolor": "rgba(65,180,105,0.10)"}
        fig.add_trace(go.Scatter(
            x=bars.index, y=bars[column], mode="lines", name=label,
            line=dict(color=color, width=1.8, dash="dash"),
            hovertemplate=f"{label}: $%{{y:.2f}}<extra></extra>",
            **extra,
        ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=bars.index, y=bars["Center"], mode="lines", name="Regression",
        line=dict(color="#f5a343", width=2, dash="dash"),
        hovertemplate="Regression: $%{y:.2f}<extra></extra>",
    ), row=1, col=1)
    fig.add_trace(go.Candlestick(
        x=bars.index, open=bars["Open"], high=bars["High"],
        low=bars["Low"], close=bars["Close"], name=ticker.upper(),
        increasing_line_color="#3bd2bf", decreasing_line_color="#ec6871",
        increasing_fillcolor="#28998b", decreasing_fillcolor="#b84b5b",
    ), row=1, col=1)
    up = bars["Close"] >= bars["Open"]
    fig.add_trace(go.Bar(
        x=bars.index, y=bars["Volume"], name="Weekly volume", showlegend=False,
        marker_color=["rgba(45,190,170,0.65)" if u else "rgba(230,90,105,0.60)" for u in up],
        hovertemplate="Volume: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # The data is already clipped to the saved snapshot period in
    # make_channel_data(). Let Plotly autorange the initial visible data.
    # Explicit x-axis range bounds can cause a jump back to that range when
    # Streamlit redraws the figure after a widget interaction.
    fig.update_layout(
        height=500, template="plotly_dark", autosize=True,
        # A touch of extra space to the right of the price axis makes the
        # chart look centered in its wider dashboard container.
        margin=dict(l=10, r=58, t=26, b=20),
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        font=dict(color="#bfc8d4", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.015, x=0, font=dict(size=10)),
        hovermode="x", dragmode="pan",
        # Preserve the selected zoom window when toggling σ bands.
        uirevision=f"{ticker.upper()}:{chart.lookback_bars}:{pd.Timestamp(bars.index.max()).date()}",
        xaxis_rangeslider_visible=False,
        title=None,  # The heading now lives above the Plotly chart in Streamlit.
    )
    # Allow independent price and date axis scaling via Plotly drag handles.
    # No minallowed/maxallowed and no fixed range restrictions.
    fig.update_yaxes(fixedrange=False)
    fig.update_xaxes(fixedrange=False)
    fig.update_yaxes(gridcolor="rgba(115,135,150,0.17)", zeroline=False, row=1, col=1, tickprefix="$", side="right")
    fig.update_yaxes(gridcolor="rgba(115,135,150,0.10)", zeroline=False, row=2, col=1, side="right")
    fig.update_xaxes(showgrid=True, gridcolor="rgba(115,135,150,0.12)", row=2, col=1)
    # Show the loaded snapshot initially without pinning the axis to its edges.
    fig.update_xaxes(autorange=True, rangeslider_visible=False)
    return fig
