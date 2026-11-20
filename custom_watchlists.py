"""Browser-local, individually editable named watchlists for General News Screen.

Stores names/tickers in this browser's localStorage. Does NOT overwrite the old
Main/POST lists, share data with other users, or write ticker lists to Git.
"""
from __future__ import annotations

import json
import re
import time

import streamlit as st

try:
    from streamlit_js_eval import streamlit_js_eval
except ImportError:
    streamlit_js_eval = None

STORAGE_KEY = "stock_intelligence_custom_watchlists_v1"
MAX_LISTS = 15
MAX_TICKERS = 50
TICKER_RX = re.compile(r"^[A-Z0-9^][A-Z0-9.\-^=]{0,14}$")
NS = "ns_custom_v1_"


def valid_symbol(raw: str) -> str:
    symbol = str(raw or "").strip().upper()
    # Yahoo uses BRK-B and BF-B, although investors often type BRK.B.
    if symbol in ("BRK.B", "BF.B"):
        symbol = symbol.replace(".", "-")
    return symbol if TICKER_RX.fullmatch(symbol) else ""


def _clean_lists(raw) -> dict[str, list[str]]:
    output = {}
    if not isinstance(raw, dict):
        return output
    for name, values in raw.items():
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 32:
            continue
        if not isinstance(values, list):
            continue
        tickers = []
        for v in values:
            if isinstance(v, str):
                ticker = valid_symbol(v)
                if ticker and ticker not in tickers:
                    tickers.append(ticker)
        output[name.strip()] = tickers[:MAX_TICKERS]
        if len(output) >= MAX_LISTS:
            break
    return output


def _queue_write():
    prior = int(st.session_state.get(NS + "revision", 0))
    revision = max(time.time_ns(), prior + 1)
    st.session_state[NS + "revision"] = revision
    st.session_state[NS + "pending"] = revision


def _read_from_browser():
    if streamlit_js_eval is None:
        return "unavailable"
    script = (
        "(function(){try{return JSON.stringify({ok:true,data:"
        "window.localStorage.getItem(" + json.dumps(STORAGE_KEY) + ")});}"
        "catch(e){return JSON.stringify({ok:false});}})()"
    )
    result = streamlit_js_eval(js_expressions=script, want_output=True,
                               key="ns_custom_read_browser_v1")
    if result is None:
        return None
    try:
        record = json.loads(result) if isinstance(result, str) else result
        if isinstance(record, dict) and record.get("ok"):
            return json.loads(record["data"]) if record.get("data") else {}
    except (TypeError, ValueError):
        pass
    return "unavailable"


def _write_to_browser():
    revision = st.session_state.get(NS + "pending")
    if revision is None or streamlit_js_eval is None:
        return
    payload = json.dumps({"version": revision,
                          "active": st.session_state[NS + "active"],
                          "lists": st.session_state[NS + "lists"]}, separators=(",", ":"))
    # Guard against out-of-order Streamlit component responses overwriting later edits.
    script = (
        "(function(){try{const k=" + json.dumps(STORAGE_KEY) + ";"
        "const v=" + json.dumps(payload) + ";"
        "const incoming=JSON.parse(v);"
        "const original=window.localStorage.getItem(k);"
        "let old=0;try{old=Number(JSON.parse(original).version||0)||0}catch(e){}"
        "if(Number(incoming.version)>=old)window.localStorage.setItem(k,v);"
        "return 'saved';}catch(e){return 'error';}})()"
    )
    result = streamlit_js_eval(js_expressions=script, want_output=True,
                               key=f"ns_custom_store_{revision}")
    if result == "saved" and st.session_state.get(NS + "pending") == revision:
        st.session_state.pop(NS + "pending", None)
    elif result == "error":
        st.warning("Browser storage is disabled; these custom lists may not persist.")
        st.session_state.pop(NS + "pending", None)


def _init():
    if not st.session_state.get(NS + "loaded"):
        persisted = _read_from_browser()
        if persisted is None:
            st.caption("Restoring your custom stock lists from this browser…")
            st.stop()
        if persisted == "unavailable":
            st.warning("Browser list storage is unavailable. Changes will last only for this session. "
                       "Install streamlit-js-eval if missing, or enable browser site storage.")
            persisted = {}
        named_lists = _clean_lists(persisted.get("lists", {})) if isinstance(persisted, dict) else {}
        if not named_lists:
            named_lists = {"My Stocks": []}
        selected = persisted.get("active") if isinstance(persisted, dict) else None
        if selected not in named_lists:
            selected = next(iter(named_lists))
        st.session_state[NS + "lists"] = named_lists
        st.session_state[NS + "active"] = selected
        st.session_state[NS + "selected"] = selected
        st.session_state[NS + "loaded"] = True
    active = st.session_state[NS + "active"]
    if active not in st.session_state[NS + "lists"]:
        st.session_state[NS + "active"] = next(iter(st.session_state[NS + "lists"]))
    if st.session_state.get(NS + "selected") != st.session_state[NS + "active"]:
        # Update widget state *before* rendering the selectbox (required by Streamlit).
        st.session_state[NS + "selected"] = st.session_state[NS + "active"]
    _write_to_browser()


def _choose_list():
    selected = st.session_state.get(NS + "selected")
    if selected in st.session_state[NS + "lists"] and selected != st.session_state[NS + "active"]:
        st.session_state[NS + "active"] = selected
        _queue_write()


def render_custom_list() -> list[str]:
    """Render management widgets; return selected list's tickers (no network calls)."""
    _init()
    lists = st.session_state[NS + "lists"]
    active = st.session_state[NS + "active"]

    # Compact three-part row: create a list | add stocks | select saved list.
    # Keep separate Streamlit forms so each action is independent.
    create_col, ticker_col, list_col = st.columns(
        [3.35, 4.15, 2.9], gap="small", vertical_alignment="bottom"
    )
    with create_col:
        with st.form("ns_custom_new_list", clear_on_submit=True):
            name_input_col, create_button_col = st.columns(
                [2.1, 1.25], gap="small", vertical_alignment="bottom"
            )
            with name_input_col:
                name = st.text_input(
                    "New list name", max_chars=32, placeholder="e.g. AI stocks",
                    help='Name your list first, then click "Create List", then add your stocks.'
                )
            with create_button_col:
                create = st.form_submit_button("Create List", use_container_width=True)

    with ticker_col:
        with st.form("ns_custom_add_stocks", clear_on_submit=True):
            ticker_input_col, add_button_col = st.columns(
                [4.0, 1.25], gap="small", vertical_alignment="bottom"
            )
            with ticker_input_col:
                typed = st.text_input("Add stock tickers", placeholder="MU, NVDA, TSM")
            with add_button_col:
                add = st.form_submit_button("Add", type="primary", use_container_width=True)

    with list_col:
        st.selectbox("Your saved custom lists", list(lists),
                     key=NS + "selected", on_change=_choose_list)

    if create:
        name = name.strip()
        if not name:
            st.error("Enter a name for your list.")
        elif name in lists:
            st.warning("That list name already exists.")
        elif len(lists) >= MAX_LISTS:
            st.warning(f"You can create up to {MAX_LISTS} custom lists.")
        else:
            lists[name] = []
            st.session_state[NS + "active"] = name
            _queue_write()
            st.rerun()

    if add:
        requested = [v for v in re.split(r"[,;\s]+", typed.strip()) if v]
        invalid = [value for value in requested if not valid_symbol(value)]
        if invalid:
            st.error("Invalid ticker(s): " + ", ".join(invalid[:8]))
        elif not requested:
            st.warning("Enter at least one ticker.")
        else:
            current = lists[active]
            extras = [valid_symbol(value) for value in requested]
            extras = list(dict.fromkeys(t for t in extras if t not in current))
            if len(current) + len(extras) > MAX_TICKERS:
                st.warning(f"Each custom list supports up to {MAX_TICKERS} stocks.")
            elif not extras:
                st.info("Those stocks are already in this list.")
            else:
                current.extend(extras)
                _queue_write()
                st.rerun()

    st.caption("Custom lists are stored in this browser. They are independent of ETF and regression scan stocks.")
    current = lists[active]
    st.markdown("**" + active.replace("*", "\\*") + "** · " + str(len(current)) + " stocks")
    if current:
        # Wrapping stock buttons, with a maximum of five per row.
        for start in range(0, len(current), 5):
            segment = current[start:start+5]
            cols = st.columns(5, gap="small")
            for col, symbol in zip(cols, segment):
                with col:
                    if st.button(f"{symbol} ×", key=f"ns_custom_remove_{active}_{symbol}",
                                 help=f"Remove {symbol} from {active}", use_container_width=True):
                        lists[active] = [t for t in lists[active] if t != symbol]
                        _queue_write()
                        st.rerun()
    else:
        st.info("This list has no stocks yet. Add tickers above to start.")

    if len(lists) > 1:
        with st.popover("Delete this list"):
            st.warning(f"Delete '{active}' and its saved tickers? This cannot be undone.")
            if st.button("Confirm delete", key="ns_custom_confirm_delete", type="primary"):
                lists.pop(active)
                st.session_state[NS + "active"] = next(iter(lists))
                _queue_write()
                st.rerun()
    return list(current)
