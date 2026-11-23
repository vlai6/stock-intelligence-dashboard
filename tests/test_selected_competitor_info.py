"""Keep competitor information boxes synchronized with Comparison Stocks chips.

Static UI contract tests intentionally avoid importing the Streamlit page,
which loads market data on import. No network access is required.
"""
from __future__ import annotations

import ast
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "pages" / "0_Stock_Intelligence.py"
code = PAGE.read_text(encoding="utf-8")
ast.parse(code, filename=str(PAGE))


def test_chips_are_source_of_truth_for_recommended_info_boxes():
    assert 'selected = st.multiselect(\n                        "Comparison Stocks"' in code
    assert "selected_symbols = set(selected)" in code
    assert 'for peer in peers:\n                        if str(peer.get("ticker", "")).strip().upper() not in selected_symbols:\n                            continue' in code
    assert 'with st.expander(f"{peer[\'ticker\']} — {peer[\'name\']}"):' in code


def test_custom_info_boxes_require_active_selection():
    assert "for custom_symbol in st.session_state[custom_key]:" in code
    assert "or custom_symbol not in selected_symbols" in code
    # Unselected custom competitors must not trigger costly get_stock calls.
    assert code.index("or custom_symbol not in selected_symbols") < code.index(
        '_, custom_info = get_stock(custom_symbol)'
    )


def test_charts_and_metrics_still_use_selected_chips():
    assert "for stock_symbol in [symbol] + selected:" in code
    assert "dict.fromkeys([symbol] + selected)" in code
    assert "options=options," in code  # deselected tickers can be reselected
    assert 'st.caption("Select a comparison stock to display its details.")' in code
