"""Chart layout regression tests for saved Portfolio X-Ray title clipping.

The donut was previously pulled upward by Plotly automargin, causing outside
ticker labels to overlap and visually cut off the portfolio name.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ui_source = (ROOT / "portfolio_xray_ui.py").read_text(encoding="utf-8")
ast.parse(ui_source, filename="portfolio_xray_ui.py")

from portfolio_xray_ui import _pie_domain

for has_title in (False, True):
    for size in range(60, 91, 5):
        for position in ("Higher", "Center", "Lower"):
            domain = _pie_domain(size, position, has_title)
            assert 0 <= domain["x"][0] < domain["x"][1] <= 1
            assert 0 <= domain["y"][0] < domain["y"][1] <= 1
            if has_title:
                # 0.17+ paper units above even the highest default pie position
                # ensures the saved title and outside ticker labels have space.
                assert domain["y"][1] <= 0.82
            assert sum(domain["x"]) == 1.0

for has_title in (False, True):
    d60 = _pie_domain(60, "Center", has_title)
    d90 = _pie_domain(90, "Center", has_title)
    assert d90["y"][1] - d90["y"][0] > d60["y"][1] - d60["y"][0]
    upper = _pie_domain(80, "Higher", has_title)
    lower = _pie_domain(80, "Lower", has_title)
    assert sum(upper["y"]) > sum(lower["y"])

for bad_args in ((35, "Center", True), (75, "Unknown", True)):
    try:
        _pie_domain(*bad_args)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid donut layout must be rejected")

# The rendered title uses a separate top-layer annotation, and the pie
# domain stays fixed rather than being moved by Plotly's outside text.
assert "automargin=False" in ui_source
assert "domain=pie_domain" in ui_source
assert "fig.add_annotation(" in ui_source
assert 'y=1.085' in ui_source
assert 'portfolio_png_filename(chart_portfolio_name)' in ui_source
assert 'with st.popover("Adjust pie chart")' in ui_source

print("PASS: adjustable X-Ray pie domains, isolated saved title and PNG naming")
