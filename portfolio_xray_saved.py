"""Named Portfolio X-Ray snapshots persisted in browser-local storage.

Uses the same streamlit-js-eval localStorage mechanism as custom watchlists.
No GitHub writes, credentials, server-level shared files, or paid database.
"""
from __future__ import annotations

import json
import math
import time

import streamlit as st

from portfolio_xray import ticker_of

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
    """Accept only validated tickers and positive finite dollar amounts."""
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
        clean.append({"ticker": ticker, "amount": amount})
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
        if not symbol and amount == 0:
            continue
        if not symbol or not math.isfinite(amount) or amount <= 0:
            raise ValueError(f"Row {index + 1}: enter a ticker and positive dollar amount.")
        positions.append({"ticker": ticker_of(symbol), "amount": amount})
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
    st.session_state[NS + "selected"] = name
    _queue_write()
    st.session_state[NS + "feedback"] = (
        "success", f"{'Updated' if replaced else 'Saved'} portfolio '{name}' "
                   f"({len(positions)} positions)."
    )
    st.rerun()


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
    st.session_state["portfolio_xray_row_count"] = min(MAX_POSITIONS, len(positions) + 1)
    st.session_state["portfolio_xray_results"] = None
    _queue_write()  # Remember which portfolio was last loaded in this browser.
    st.session_state[NS + "feedback"] = (
        "success", f"Loaded '{name}'. Click Analyze portfolio to refresh the chart."
    )


def _delete_selected():
    name = st.session_state.get(NS + "selected")
    portfolios = st.session_state[NS + "portfolios"]
    if name not in portfolios:
        return
    portfolios.pop(name)
    st.session_state[NS + "selected"] = next(iter(portfolios), None)
    _queue_write()
    st.session_state[NS + "feedback"] = ("success", f"Deleted saved portfolio '{name}'.")
    st.rerun()


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
        st.button(
            "Load", on_click=_load_selected, disabled=not names,
            use_container_width=True, key=NS + "load",
        )
    with save_col:
        with st.popover("Save portfolio", use_container_width=True):
            with st.form(NS + "save_form", clear_on_submit=True):
                name = st.text_input(
                    "Portfolio name", max_chars=MAX_NAME_LENGTH,
                    placeholder="e.g. Core ETFs",
                )
                st.caption("Saving an existing name replaces its saved positions.")
                submitted = st.form_submit_button("Save", use_container_width=True)
            if submitted:
                _save_current(name)
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
