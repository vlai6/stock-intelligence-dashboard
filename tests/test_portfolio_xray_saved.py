"""Offline validation of browser-saved Portfolio X-Ray snapshots."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from portfolio_xray_saved import (
    _sanitize_positions, _sanitize_saved, MAX_PORTFOLIOS, MAX_POSITIONS,
)

rows = [
    {"ticker": "nvda", "amount": 500.0},
    {"ticker": "spy", "amount": 1000.25},
]
assert _sanitize_positions(rows) == [
    {"ticker": "NVDA", "amount": 500.0},
    {"ticker": "SPY", "amount": 1000.25},
]
assert _sanitize_positions([{"ticker": "bad;drop", "amount": 100}]) == []
assert _sanitize_positions([{"ticker": "SPY", "amount": float("inf")}]) == []
assert _sanitize_positions([{"ticker": "SPY", "amount": -2}]) == []
assert _sanitize_positions([{"ticker": "SPY", "amount": 0}]) == []
assert _sanitize_positions([{"ticker": "SPY"}]) == []

portfolios = _sanitize_saved({
    "Core ETFs": rows,
    "empty": [],
    "invalid": [{"ticker": "SPY", "amount": 0}],
})
assert list(portfolios) == ["Core ETFs"]
assert len(portfolios["Core ETFs"]) == 2

too_many_positions = [{"ticker": "SPY", "amount": i + 1} for i in range(MAX_POSITIONS + 1)]
assert len(_sanitize_positions(too_many_positions)) == MAX_POSITIONS

many_portfolios = {
    f"Portfolio {i}": [{"ticker": "NVDA", "amount": 1}]
    for i in range(MAX_PORTFOLIOS + 5)
}
assert len(_sanitize_saved(many_portfolios)) == MAX_PORTFOLIOS

print("PASS: browser-saved portfolio input validation and storage limits")
