"""Rolling linear-regression channel math for the Regression Stock Scanner.

Daily closes, oldest to newest. Uses OLS and sample residual sigma:
    sqrt(sum((close - fitted)^2) / (length - 1))
The newest close is included in the fit, as in the TradingView channel.
"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Point:
    close: float
    line: float
    sigma: float
    slope: float
    z: float
    lower3: float
    lower4: float


def regression_point(window: np.ndarray) -> Point:
    y = np.asarray(window, dtype=float)
    n = len(y)
    if n < 2 or not np.all(np.isfinite(y)) or np.any(y <= 0):
        raise ValueError("Expected at least two finite, positive closing prices")

    # x=0 is oldest, x=n-1 is newest. Positive slope means uptrend.
    x = np.arange(n, dtype=float)
    xm = (n - 1) / 2.0
    ym = float(y.mean())
    xc = x - xm
    slope = float(np.dot(xc, y - ym) / np.dot(xc, xc))
    fitted = ym + slope * xc
    line = float(fitted[-1])
    sigma = float(np.sqrt(np.sum((y - fitted) ** 2) / (n - 1)))
    z = float((y[-1] - line) / sigma) if sigma > 0 else 0.0
    return Point(
        close=float(y[-1]), line=line, sigma=sigma, slope=slope,
        z=z, lower3=line - 3.0 * sigma, lower4=line - 4.0 * sigma,
    )


def evaluate(closes: np.ndarray, length: int = 2500) -> tuple[Point, Point, list[str]]:
    """Return (current channel, prior channel, newly crossed band labels)."""
    y = np.asarray(closes, dtype=float)
    if len(y) < length + 1:
        raise ValueError(f"Need {length + 1} valid sessions for crossing detection")

    prev = regression_point(y[-length - 1:-1])
    curr = regression_point(y[-length:])
    crosses = []
    if prev.close > prev.lower3 and curr.close <= curr.lower3:
        crosses.append("-3σ")
    if prev.close > prev.lower4 and curr.close <= curr.lower4:
        crosses.append("-4σ")
    return curr, prev, crosses


def passes_filters(point: Point) -> bool:
    """Upward-pointing regression, and both negative-side bands above zero."""
    return point.slope > 0 and point.lower3 > 0 and point.lower4 > 0
