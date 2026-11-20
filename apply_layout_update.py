#!/usr/bin/env python3
"""Targeted layout update for StockIntelligenceDashboard.

Only updates the News Sentiment control widths, the Stock Intelligence trend
line color, and the competitor/metrics column ratio. No source replacement.
"""

from __future__ import annotations

import ast
import argparse
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent
SENTIMENT = ROOT / "pages" / "2_News_Sentiment.py"
STOCK = ROOT / "pages" / "0_Stock_Intelligence.py"
SENT_MARKER = "# si_compact_sentiment_controls_v1"
STOCK_MARKER = "# si_gold_trendline_6040_v1"


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return _call_name(node.value) + "." + node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _call_is(node: ast.AST, dotted: str) -> bool:
    return isinstance(node, ast.Call) and _call_name(node.func) == dotted


def _is_selectbox_call(node: ast.AST, label: str) -> bool:
    return (
        _call_is(node, "st.selectbox")
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == label
    )


def _is_lookup_form(node: ast.AST) -> bool:
    return (
        _call_is(node, "st.form")
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "sentiment_lookup"
    )


def patch_sentiment(src: str) -> tuple[str, list[str]]:
    if SENT_MARKER in src:
        return src, ["News Sentiment controls: already updated"]
    tree = ast.parse(src)
    selector_block = None
    lookup_block = None
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and _is_selectbox_call(child, "News Sentiment stock list"):
                    if node.col_offset == 0 and _call_is(node.items[0].context_expr, "st.container"):
                        selector_block = node
            if node.col_offset == 4 and any(_is_lookup_form(item.context_expr) for item in node.items):
                lookup_block = node
    if selector_block is None:
        raise RuntimeError("Cannot locate the main News Sentiment stock list container; no files changed")
    if lookup_block is None:
        raise RuntimeError("Cannot locate the single-stock search form; no files changed")
    if selector_block.end_lineno >= lookup_block.lineno:
        raise RuntimeError("Sentiment control ranges overlap unexpectedly; no files changed")

    lines = src.splitlines(keepends=True)
    patches = [
        (selector_block.lineno, selector_block.end_lineno,
         SENT_MARKER + "\n"
         "si_stocklist_col, _si_stocklist_blank = st.columns([1, 1], gap='medium')\n"
         "with si_stocklist_col:\n"),
        (lookup_block.lineno, lookup_block.end_lineno,
         "    si_ticker_col, _si_ticker_blank = st.columns([1, 1], gap='medium')\n"
         "    with si_ticker_col:\n"),
    ]
    for start, end, prefix in sorted(patches, key=lambda p: p[0], reverse=True):
        block = lines[start - 1:end]
        # The first wrapper starts at module level, the second inside the if.
        lines[start - 1:end] = [prefix] + ["    " + line if line.strip() else line for line in block]
    updated = "".join(lines)
    ast.parse(updated)
    return updated, ["News Sentiment: stock-list and ticker-search cards limited to ~half the page width"]


def _source_offset(text: str, lineno: int, col: int) -> int:
    return sum(len(line) for line in text.splitlines(keepends=True)[:lineno - 1]) + col


def _replace_node(text: str, node: ast.AST, replacement: str) -> str:
    start = _source_offset(text, node.lineno, node.col_offset)
    end = _source_offset(text, node.end_lineno, node.end_col_offset)
    return text[:start] + replacement + text[end:]


def patch_stock(src: str) -> tuple[str, list[str]]:
    if STOCK_MARKER in src:
        return src, ["Stock Intelligence: already updated"]
    tree = ast.parse(src)
    columns_arg = None
    trend_scatter = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], (ast.Tuple, ast.List)):
            names = [x.id for x in node.targets[0].elts if isinstance(x, ast.Name)]
            if names == ["peers_col", "metrics_col"] and _call_is(node.value, "st.columns"):
                if node.value.args:
                    columns_arg = node.value.args[0]
        if isinstance(node, ast.Call) and _call_name(node.func) in ("go.Scatter", "plotly.graph_objects.Scatter"):
            name = next((kw.value for kw in node.keywords if kw.arg == "name"), None)
            if isinstance(name, ast.JoinedStr):
                strings = " ".join(chunk.value for chunk in name.values if isinstance(chunk, ast.Constant) and isinstance(chunk.value, str))
                if "Trend Line" in strings:
                    trend_scatter = node
            if isinstance(name, ast.Constant) and isinstance(name.value, str) and "Trend Line" in name.value:
                trend_scatter = node
    if columns_arg is None:
        raise RuntimeError("Cannot locate AI Competitor / Financial Metrics columns; no files changed")
    if trend_scatter is None:
        raise RuntimeError("Cannot locate Stock Price History trend line; no files changed")

    # Find the price chart render, not the competitor chart, and enforce gold
    # immediately before plotting, after any earlier styling passes.
    price_render = None
    for node in sorted(ast.walk(tree), key=lambda n: getattr(n, "lineno", 999999)):
        if isinstance(node, ast.Call) and _call_is(node, "st.plotly_chart") and trend_scatter.end_lineno < node.lineno < columns_arg.lineno:
            price_render = node
            break
    if price_render is None:
        raise RuntimeError("Cannot locate price chart render after trend line; no files changed")

    src = _replace_node(src, columns_arg, "[3, 2]")
    # Reparse because replacing the expression might change source offsets.
    tree2 = ast.parse(src)
    price_render2 = None
    trend_scatter2 = None
    for node in ast.walk(tree2):
        if isinstance(node, ast.Call) and _call_name(node.func) in ("go.Scatter", "plotly.graph_objects.Scatter"):
            name = next((kw.value for kw in node.keywords if kw.arg == "name"), None)
            if isinstance(name, ast.JoinedStr):
                strings = " ".join(chunk.value for chunk in name.values if isinstance(chunk, ast.Constant) and isinstance(chunk.value, str))
                if "Trend Line" in strings:
                    trend_scatter2 = node
    if trend_scatter2 is None:
        raise RuntimeError("Trend line lost during patch; no files changed")
    for node in sorted(ast.walk(tree2), key=lambda n: getattr(n, "lineno", 999999)):
        if isinstance(node, ast.Call) and _call_is(node, "st.plotly_chart") and node.lineno > trend_scatter2.end_lineno:
            price_render2 = node
            break
    if price_render2 is None:
        raise RuntimeError("Cannot locate stock-price chart render; no files changed")

    lines = src.splitlines(keepends=True)
    lnum = price_render2.lineno
    indent = re.match(r"^[ \t]*", lines[lnum - 1]).group()
    # Don't rely solely on the original Scatter color: themes or other helpers
    # can restyle a trace after it is created.
    injection = (
        f"{indent}{STOCK_MARKER}\n"
        f"{indent}for _gold_trace in fig.data:\n"
        f"{indent}    if 'trend line' in str(getattr(_gold_trace, 'name', '')).lower():\n"
        f"{indent}        _gold_trace.line.color = '#FFD21F'\n"
        f"{indent}        _gold_trace.line.width = 4\n"
        f"{indent}        _gold_trace.line.dash = 'dash'\n"
    )
    lines.insert(lnum - 1, injection)
    updated = "".join(lines)
    ast.parse(updated)
    return updated, ["Stock Intelligence: 60% AI competitors / 40% Financial Metrics", "Stock Intelligence: high-contrast gold dashed trend line"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="Verify the patch can apply without changing files")
    args = ap.parse_args()
    if not SENTIMENT.is_file() or not STOCK.is_file():
        print("ERROR: Run this from the StockIntelligenceDashboard project root, beside app.py, with both pages present.")
        return 2
    try:
        source_sent = SENTIMENT.read_text(encoding="utf-8")
        source_stock = STOCK.read_text(encoding="utf-8")
        updated_sent, notes_sent = patch_sentiment(source_sent)
        updated_stock, notes_stock = patch_stock(source_stock)
        ast.parse(updated_sent)
        ast.parse(updated_stock)
    except (SyntaxError, ValueError, RuntimeError) as exc:
        print("UPDATE NOT APPLIED:", exc)
        return 1

    for n in notes_sent + notes_stock:
        print(" -", n)
    if args.check:
        print("Validation OK. No files changed (--check).")
        return 0
    changes = [(SENTIMENT, source_sent, updated_sent), (STOCK, source_stock, updated_stock)]
    actual_changes = [(path, before, after) for path, before, after in changes if before != after]
    if not actual_changes:
        print("Already installed. No files changed.")
        return 0
    backup = ROOT / ".layout_update_backups" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup.mkdir(parents=True, exist_ok=True)
    try:
        for path, _before, _after in actual_changes:
            dest = backup / path.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        for path, before, after in actual_changes:
            path.write_text(after, encoding="utf-8", newline="")
        print("Updated", len(actual_changes), "file(s). Backups:", backup)
        return 0
    except Exception as exc:
        print("WRITE FAILED:", type(exc).__name__, str(exc))
        for path, before, _after in actual_changes:
            try:
                path.write_text(before, encoding="utf-8", newline="")
            except OSError:
                pass
        print("Original source restoration attempted. Backup kept at:", backup)
        return 1


if __name__ == "__main__":
    sys.exit(main())
