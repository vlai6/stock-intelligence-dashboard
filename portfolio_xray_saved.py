"""Named Portfolio X-Ray snapshots persisted in browser-local storage.

Uses the same streamlit-js-eval localStorage mechanism as custom watchlists.
No GitHub writes, credentials, server-level shared files, or paid database.
"""
from __future__ import annotations

import json
import math
import re
import time
import unicodedata
from datetime import date

import streamlit as st

from portfolio_xray import ticker_of
from portfolio_xray_dates import position_with_date, position_signature

try:
    from streamlit_js_eval import streamlit_js_eval
except ImportError:
    streamlit_js_eval = None

STORAGE_KEY = "stock_intelligence_saved_portfolios_v1"
NS = "portfolio_xray_saved_"
MAX_PORTFOLIOS = 15
MAX_POSITIONS = 30
MAX_NAME_LENGTH = 40


def _sanitize_positions(raw) -> list[dict]:
    """Accept validated positions with positive amounts or percentage weights."""
    if not isinstance(raw, list):
        return []
    clean = []
    for item in raw[:MAX_POSITIONS]:
        if not isinstance(item, dict):
            return []
        try:
            ticker = ticker_of(item.get("ticker", ""))
            amount = float(item.get("amount", 0))
        except (ValueError, TypeError):
            return []
        if not math.isfinite(amount) or amount <= 0 or amount > 1e12:
            return []
        try:
            clean.append(position_with_date(
                ticker, amount, item.get("date"),
            ))
        except ValueError:
            return []
    return clean


def _sanitize_saved(raw) -> dict[str, list[dict]]:
    """Validate untrusted browser data before assigning it to editor widgets."""
    if not isinstance(raw, dict):
        return {}
    clean = {}
    for raw_name, raw_positions in raw.items():
        if not isinstance(raw_name, str):
            continue
        name = raw_name.strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            continue
        positions = _sanitize_positions(raw_positions)
        if positions:
            clean[name] = positions
        if len(clean) >= MAX_PORTFOLIOS:
            break
    return clean


def portfolio_png_filename(name: str | None) -> str:
    """Safe PNG basename; never allow a saved name to become a path."""
    if not name:
        return "portfolio_xray_pie_chart"
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_name).strip("_-")[:48]
    return f"portfolio_xray_{safe or 'saved_portfolio'}"


def loaded_portfolio_chart_name() -> str | None:
    """Name only the saved portfolio that was actually loaded and analyzed.

    Merely selecting a dropdown entry is not loading it. A modified input,
    removed saved entry, change of units, or stale analysis cannot inherit
    the previous saved portfolio title or exported filename.
    """
    state = st.session_state
    name = state.get(NS + "loaded_name")
    saved = state.get(NS + "portfolios", {})
    if not isinstance(name, str) or not isinstance(saved, dict) or name not in saved:
        return None
    if state.get("portfolio_xray_results") is None:
        return None
    units = state.get(NS + "units", {})
    expected_unit = units.get(name, "usd") if isinstance(units, dict) else "usd"
    current_unit = state.get("portfolio_xray_unit_mode", "usd")
    if current_unit != expected_unit:
        return None
    try:
        current = _current_positions()
    except ValueError:
        return None
    if current != saved[name]:
        return None
    signature = (
        current_unit,
        position_signature(current),
    )
    if state.get("portfolio_xray_results_signature") != signature:
        return None
    return name


def _read_from_browser():
    if streamlit_js_eval is None:
        return "unavailable"
    script = (
        "(function(){try{return JSON.stringify({ok:true,data:"
        "window.localStorage.getItem(" + json.dumps(STORAGE_KEY) + ")});}"
        "catch(e){return JSON.stringify({ok:false});}})()"
    )
    value = streamlit_js_eval(
        js_expressions=script, want_output=True, key="px_saved_read_browser_v1"
    )
    if value is None:
        return None
    try:
        record = json.loads(value) if isinstance(value, str) else value
        if isinstance(record, dict) and record.get("ok"):
            return json.loads(record["data"]) if record.get("data") else {}
    except (ValueError, TypeError):
        pass
    return "unavailable"


def _queue_write():
    previous = int(st.session_state.get(NS + "revision", 0))
    version = max(time.time_ns(), previous + 1)
    st.session_state[NS + "revision"] = version
    st.session_state[NS + "pending"] = version


def _write_to_browser():
    version = st.session_state.get(NS + "pending")
    if version is None:
        return
    if streamlit_js_eval is None or st.session_state.get(NS + "storage_unavailable"):
        st.session_state.pop(NS + "pending", None)
        return
    data = json.dumps({
        "version": version,
        "selected": st.session_state.get(NS + "selected"),
        "portfolios": st.session_state[NS + "portfolios"],
        "units": st.session_state.get(NS + "units", {}),
    }, separators=(",", ":"))
    script = (
        "(function(){try{const k=" + json.dumps(STORAGE_KEY) + ";"
        "const v=" + json.dumps(data) + ";"
        "const incoming=JSON.parse(v);"
        "const original=window.localStorage.getItem(k);"
        "let old=0;try{old=Number(JSON.parse(original).version||0)||0}catch(e){}"
        "if(Number(incoming.version)>=old)window.localStorage.setItem(k,v);"
        "return 'saved';}catch(e){return 'error';}})()"
    )
    result = streamlit_js_eval(
        js_expressions=script, want_output=True, key=f"px_saved_write_{version}"
    )
    if result == "saved" and st.session_state.get(NS + "pending") == version:
        st.session_state.pop(NS + "pending", None)
    elif result == "error":
        st.session_state[NS + "storage_unavailable"] = True
        st.session_state.pop(NS + "pending", None)
        st.session_state[NS + "feedback"] = (
            "warning", "Browser storage is blocked. Portfolios will only last for this session."
        )


def _initialize() -> bool:
    if not st.session_state.get(NS + "loaded"):
        record = _read_from_browser()
        if record is None:
            return False
        unavailable = record == "unavailable"
        if unavailable:
            record = {}
        saved = _sanitize_saved(record.get("portfolios", {})) if isinstance(record, dict) else {}
        selected = record.get("selected") if isinstance(record, dict) else None
        if selected not in saved:
            selected = next(iter(saved), None)
        st.session_state[NS + "portfolios"] = saved
        existing_units = record.get("units", {}) if isinstance(record, dict) else {}
        if not isinstance(existing_units, dict):
            existing_units = {}
        # Old saved portfolios have dollar amounts and no units mapping.
        st.session_state[NS + "units"] = {
            name: "pct" if existing_units.get(name) == "pct" else "usd"
            for name in saved
        }
        st.session_state[NS + "selected"] = selected
        try:
            revision = int(record.get("version", 0) or 0) if isinstance(record, dict) else 0
        except (ValueError, TypeError, OverflowError):
            revision = 0
        st.session_state[NS + "revision"] = max(0, revision)
        st.session_state[NS + "storage_unavailable"] = unavailable
        st.session_state[NS + "loaded"] = True
    saved = st.session_state[NS + "portfolios"]
    if st.session_state.get(NS + "selected") not in saved:
        st.session_state[NS + "selected"] = next(iter(saved), None)
    _write_to_browser()
    return True


def _current_positions() -> list[dict]:
    positions = []
    count = int(st.session_state.get("portfolio_xray_row_count", 1))
    for index in range(min(count, MAX_POSITIONS)):
        symbol = str(st.session_state.get(f"portfolio_xray_ticker_{index}", "") or "").strip()
        value = st.session_state.get(f"portfolio_xray_amount_{index}", 0.0)
        try:
            amount = float(value or 0.0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Row {index + 1}: enter a valid amount.") from exc
        row_date = st.session_state.get(f"portfolio_xray_date_{index}")
        if not symbol and amount == 0 and not row_date:
            continue
        if not symbol or not math.isfinite(amount) or amount <= 0:
            raise ValueError(f"Row {index + 1}: enter a ticker and positive amount.")
        try:
            positions.append(position_with_date(ticker_of(symbol), amount, row_date))
        except ValueError as exc:
            raise ValueError(f"Row {index + 1}: {exc}") from exc
    if not positions:
        raise ValueError("Enter at least one ticker and amount before saving.")
    if len(positions) > MAX_POSITIONS:
        raise ValueError(f"Each portfolio supports up to {MAX_POSITIONS} positions.")
    return positions


def _save_current(raw_name: str):
    name = str(raw_name or "").strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        st.session_state[NS + "feedback"] = (
            "error", f"Enter a portfolio name (1–{MAX_NAME_LENGTH} characters)."
        )
        return
    try:
        positions = _current_positions()
    except ValueError as exc:
        st.session_state[NS + "feedback"] = ("error", str(exc))
        return
    saved = st.session_state[NS + "portfolios"]
    if name not in saved and len(saved) >= MAX_PORTFOLIOS:
        st.session_state[NS + "feedback"] = (
            "error", f"Maximum of {MAX_PORTFOLIOS} saved portfolios reached."
        )
        return
    replaced = name in saved
    saved[name] = positions
    st.session_state.setdefault(NS + "units", {})[name] = (
        "pct" if st.session_state.get("portfolio_xray_unit_mode") == "pct" else "usd"
    )
    st.session_state[NS + "selected"] = name
    # These inputs are now exactly the selected saved portfolio.
    st.session_state[NS + "loaded_name"] = name
    # A Save As action creates a named current portfolio. Analyze that exact
    # saved snapshot so an older chart is never exported under the new name.
    st.session_state["portfolio_xray_results"] = None
    st.session_state.pop("portfolio_xray_results_signature", None)
    st.session_state.pop("portfolio_xray_historical_result", None)
    st.session_state["portfolio_xray_auto_analyze"] = True
    _queue_write()
    st.session_state[NS + "feedback"] = (
        "success", f"{'Updated' if replaced else 'Saved'} portfolio '{name}' "
                   f"({len(positions)} positions)."
    )


def _save_current_from_widget():
    """Run before the dropdown is instantiated, in Streamlit's button callback."""
    _save_current(st.session_state.get(NS + "name_input", ""))


def _load_selected():
    name = st.session_state.get(NS + "selected")
    positions = st.session_state[NS + "portfolios"].get(name)
    if not positions:
        return
    # Button callbacks run before widgets are instantiated in the new rerun.
    # Clear old rows so loading a shorter portfolio cannot preserve stale inputs.
    for index in range(MAX_POSITIONS):
        row = positions[index] if index < len(positions) else None
        st.session_state[f"portfolio_xray_ticker_{index}"] = row["ticker"] if row else ""
        st.session_state[f"portfolio_xray_amount_{index}"] = float(row["amount"]) if row else 0.0
        st.session_state[f"portfolio_xray_date_{index}"] = (
            date.fromisoformat(row["date"]) if row and row.get("date") else None
        )
    st.session_state["portfolio_xray_row_count"] = min(MAX_POSITIONS, len(positions) + 1)
    st.session_state["portfolio_xray_unit_mode"] = (
        "pct" if st.session_state.get(NS + "units", {}).get(name) == "pct" else "usd"
    )
    # The X-Ray renderer consumes this one-shot request after recreating its
    # inputs, then runs the exact same analysis used by Analyze portfolio.
    st.session_state["portfolio_xray_results"] = None
    st.session_state.pop("portfolio_xray_results_signature", None)
    st.session_state.pop("portfolio_xray_historical_result", None)
    st.session_state["portfolio_xray_auto_analyze"] = True
    st.session_state[NS + "loaded_name"] = name
    _queue_write()  # Remember which portfolio was last loaded in this browser.
    st.session_state[NS + "feedback"] = ("success", f"Loaded '{name}'.")


def _delete_selected():
    name = st.session_state.get(NS + "selected")
    portfolios = st.session_state[NS + "portfolios"]
    if name not in portfolios:
        return
    portfolios.pop(name)
    st.session_state.setdefault(NS + "units", {}).pop(name, None)
    if st.session_state.get(NS + "loaded_name") == name:
        st.session_state[NS + "loaded_name"] = None
    st.session_state[NS + "selected"] = next(iter(portfolios), None)
    _queue_write()
    st.session_state[NS + "feedback"] = ("success", f"Deleted saved portfolio '{name}'.")


def render_saved_portfolio_controls():
    """Compact controls placed directly above the Portfolio X-Ray input box."""
    st.caption("SAVED PORTFOLIOS")
    if not _initialize():
        st.caption("Restoring portfolios saved in this browser…")
        return

    names = list(st.session_state[NS + "portfolios"])
    select_col, load_col, save_col, delete_col = st.columns(
        [3.9, 1.1, 2.2, 1.2], gap="small", vertical_alignment="bottom"
    )
    with select_col:
        st.selectbox(
            "Saved portfolios", options=names, index=0 if names else None,
            placeholder="No saved portfolios",
            label_visibility="collapsed", key=NS + "selected",
        )
    with load_col:
        # Dim the button until another saved portfolio is selected.
        selected = st.session_state.get(NS + "selected")
        already_loaded = bool(selected) and selected == st.session_state.get(NS + "loaded_name")
        st.button(
            "Load", on_click=_load_selected,
            disabled=not names or already_loaded,
            type="primary", use_container_width=True, key=NS + "load",
            help="Already loaded" if already_loaded else "Load and analyze selected portfolio",
        )
    with save_col:
        with st.popover("Save Portfolio As", use_container_width=True):
            # Use a standard input rather than a form: Streamlit's form-only
            # "Press Enter to submit" overlay collides with the character
            # counter and typed portfolio name in this narrow popover.
            st.text_input(
                "Portfolio name",
                placeholder="e.g. Core ETFs",
                key=NS + "name_input",
            )
            st.caption("Saving an existing name replaces its saved positions.")
            st.button(
                "Save", key=NS + "save_button", use_container_width=True,
                on_click=_save_current_from_widget,
            )
    with delete_col:
        with st.popover("Delete", use_container_width=True, disabled=not names):
            st.caption(f"Delete '{st.session_state.get(NS + 'selected')}'?")
            st.button(
                "Confirm delete", key=NS + "confirm_delete",
                on_click=_delete_selected, use_container_width=True,
            )

    feedback = st.session_state.pop(NS + "feedback", None)
    if feedback:
        status, message = feedback
        if status == "error":
            st.error(message)
        elif status == "warning":
            st.warning(message)
        else:
            st.success(message)
    if st.session_state.get(NS + "storage_unavailable"):
        st.caption("Browser storage unavailable: saved portfolios only last for this session.")
    else:
        st.caption("Saved on this browser and device.")
