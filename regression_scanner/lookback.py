"""Convert a user-entered regression lookback (years) to trading sessions.

Use 250 sessions per nominal year to preserve the legacy 10-year = 2,500
session setting. This is NOT a date-exact 10-calendar-year window.
"""

from __future__ import annotations

from datetime import date, timedelta
import math

SESSIONS_PER_YEAR = 250
DEFAULT_YEARS = 10.0
MIN_YEARS = 0.5
MAX_YEARS = 30.0


def regression_sessions(years: float) -> int:
    """Return a fixed-size session window; require a supported finite range."""
    try:
        value = float(years)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Regression lookback must be a number of years.") from exc
    if not math.isfinite(value) or not MIN_YEARS <= value <= MAX_YEARS:
        raise ValueError(f"Regression lookback must be between {MIN_YEARS:g} and {MAX_YEARS:g} years.")
    return int(round(value * SESSIONS_PER_YEAR))


def price_history_start(target_session: str, years: float) -> str:
    """Use enough calendar history for N+1 sessions plus an extra ~90-day buffer.

    250 sessions per regression year and about 252 sessions/calendar year.
    The 90-day cushion tolerates holidays and unusual trading suspensions.
    """
    n = regression_sessions(years) + 1
    calendar_days = math.ceil(n * 365.25 / 252 + 90)
    return (date.fromisoformat(target_session) - timedelta(days=calendar_days)).isoformat()
