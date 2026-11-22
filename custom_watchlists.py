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


class BrowserGroupsPending(Exception):
    """Browser storage is still loading; the caller decides how to stop its page."""


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
            # Do not call st.stop() here: a shared helper can execute inside
            # the continuous dashboard, where that would abort all later
            # sections (scanner, metrics, sentiment), not just News Screener.
            raise BrowserGroupsPending()
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
    if st.session_state.get(NS + "selected") not in st.session_state[NS + "lists"]:
        # Preserve the user's pending dropdown choice until they explicitly Load.
        st.session_state[NS + "selected"] = st.session_state[NS + "active"]
    _write_to_browser()


def _load_group():
    """A Load click switches the active group before the News screen renders."""
    selected = st.session_state.get(NS + "selected")
    if selected in st.session_state[NS + "lists"]:
        if selected != st.session_state[NS + "active"]:
            st.session_state[NS + "active"] = selected
            _queue_write()
        st.session_state[NS + "feedback"] = (
            "success", f"Loaded '{selected}' for News Screener."
        )


def _create_group():
    """Create and activate a named empty group in a pre-render button callback."""
    name = str(st.session_state.get(NS + "new_group_name", "") or "").strip()
    lists = st.session_state[NS + "lists"]
    if not name or len(name) > 32:
        st.session_state[NS + "feedback"] = ("error", "Enter a group name (1–32 characters).")
    elif name in lists:
        st.session_state[NS + "feedback"] = (
            "error", f"'{name}' already exists. Choose that group and click Load."
        )
    elif len(lists) >= MAX_LISTS:
        st.session_state[NS + "feedback"] = (
            "error", f"You can save up to {MAX_LISTS} groups."
        )
    else:
        lists[name] = []
        st.session_state[NS + "active"] = name
        st.session_state[NS + "selected"] = name
        _queue_write()
        st.session_state[NS + "feedback"] = (
            "success", f"Created '{name}'. Add stock tickers below."
        )


def _delete_group():
    """Delete selected group in a callback, never mutate an instantiated selector."""
    lists = st.session_state[NS + "lists"]
    selected = st.session_state.get(NS + "selected")
    if selected not in lists:
        return
    if len(lists) <= 1:
        st.session_state[NS + "feedback"] = (
            "error", "Keep at least one group. Create another before deleting this one."
        )
        return
    lists.pop(selected)
    if st.session_state.get(NS + "active") == selected:
        st.session_state[NS + "active"] = next(iter(lists))
    st.session_state[NS + "selected"] = st.session_state[NS + "active"]
    _queue_write()
    st.session_state[NS + "feedback"] = ("success", f"Deleted group '{selected}'.")


def render_custom_list() -> list[str]:
    """Edit tickers in the loaded saved group; the News Screener owns its toolbar."""
    _init()
    lists = st.session_state[NS + "lists"]
    active = st.session_state[NS + "active"]
    current = list(lists[active])

    with st.form("ns_custom_add_stocks", clear_on_submit=True, border=False):
        ticker_col, add_col, unused = st.columns(
            [4.1, 1.3, 4.6], gap="small", vertical_alignment="bottom"
        )
        with ticker_col:
            typed = st.text_input("Add stock tickers", placeholder="MU, NVDA, TSM")
        with add_col:
            add = st.form_submit_button("Add", type="primary", use_container_width=True)
    if add:
        requested, invalid = parse_working_tickers(typed)
        if invalid:
            st.error("Invalid ticker(s): " + ", ".join(invalid[:8]))
        elif not requested:
            st.warning("Enter at least one ticker.")
        else:
            extras = [symbol for symbol in requested if symbol not in current]
            if len(current) + len(extras) > MAX_TICKERS:
                st.warning(f"Each group supports up to {MAX_TICKERS} stocks.")
            elif not extras:
                st.info("Those stocks are already in this group.")
            else:
                lists[active] = current + extras
                _queue_write()
                st.rerun()

    current = list(lists[active])
    st.caption(f"{active} · {len(current)} stock(s) · saved in this browser.")
    # Tickers are removed from the unified pill row on the News Screener.
    # Editing any displayed list creates an unsaved Custom List copy, so
    # saved groups and built-in scan/ETF presets stay unchanged.
    return current

def named_groups() -> list[str]:
    """Return names from the existing browser-backed saved-groups store."""
    _init()
    return list(st.session_state[NS + "lists"])


def active_named_group() -> str:
    _init()
    return st.session_state[NS + "active"]


def activate_named_group(name: str) -> bool:
    """Load one group before the News Screener renders its stock list."""
    _init()
    if name not in st.session_state[NS + "lists"]:
        return False
    if st.session_state[NS + "active"] != name:
        st.session_state[NS + "active"] = name
        st.session_state[NS + "selected"] = name
        _queue_write()
    return True


def save_named_group(name: str, symbols: list[str]) -> tuple[bool, str]:
    """Save a screenshot's displayed tickers; overwrite an existing name like X-Ray.

    Empty groups are valid so users can create one before adding stocks.
    Keeps the prior browser localStorage key, preserving all existing groups.
    """
    _init()
    name = str(name or "").strip()
    if not name or len(name) > 32:
        return False, "Enter a group name between 1 and 32 characters."
    if not isinstance(symbols, list):
        return False, "Invalid group stocks."
    clean = [valid_symbol(v) for v in symbols]
    if any(not symbol for symbol in clean):
        return False, "The displayed group contains an invalid ticker."
    clean = list(dict.fromkeys(clean))
    if len(clean) > MAX_TICKERS:
        return False, f"Groups support at most {MAX_TICKERS} tickers."
    lists = st.session_state[NS + "lists"]
    if name not in lists and len(lists) >= MAX_LISTS:
        return False, f"Only {MAX_LISTS} named groups are supported."
    replaced = name in lists
    lists[name] = clean
    st.session_state[NS + "active"] = name
    st.session_state[NS + "selected"] = name
    _queue_write()
    return True, f"{'Updated' if replaced else 'Saved'} group '{name}' ({len(clean)} tickers)."


def remove_named_group(name: str) -> tuple[bool, str]:
    """Delete a saved group; built-in screener presets never enter this store."""
    _init()
    lists = st.session_state[NS + "lists"]
    if name not in lists:
        return False, "Only saved groups can be deleted."
    lists.pop(name)
    if not lists:
        # Retain an editable empty default, compatible with older localStorage.
        lists["My Stocks"] = []
    if st.session_state[NS + "active"] == name:
        st.session_state[NS + "active"] = next(iter(lists))
    st.session_state[NS + "selected"] = st.session_state[NS + "active"]
    _queue_write()
    return True, f"Deleted group '{name}'."



# A working list is intentionally session-only until Save displayed as list.
DRAFT_KEY = "ns_working_stocks_v1"


def removable_stock_list(symbols: list[str], ticker: str) -> list[str]:
    """Build an editable copy excluding one clicked ticker, never mutate source."""
    target = valid_symbol(ticker)
    if not target:
        raise ValueError("Invalid stock ticker.")
    kept = []
    for raw in symbols:
        symbol = valid_symbol(raw)
        if symbol and symbol != target and symbol not in kept:
            kept.append(symbol)
    return kept


def parse_working_tickers(raw: str) -> tuple[list[str], list[str]]:
    parts = [v for v in re.split(r"[,;\s]+", str(raw or "").strip()) if v]
    normalized = [valid_symbol(p) for p in parts]
    return (list(dict.fromkeys(x for x in normalized if x)),
            [part for part, symbol in zip(parts, normalized) if not symbol])


def render_working_list() -> list[str]:
    """Edit immediately, without creating a named list or changing presets."""
    st.session_state.setdefault(DRAFT_KEY, [])
    current = list(st.session_state[DRAFT_KEY])
    st.caption("Custom List (Unsaved) · edit stocks freely, then use Save Group "
               "to keep your changes. Original scan and saved groups remain unchanged.")
    with st.form("ns_working_add_stocks", clear_on_submit=True):
        text_col, add_col = st.columns([5, 1.4], vertical_alignment="bottom", gap="small")
        with text_col:
            entered = st.text_input("Add tickers", placeholder="NVDA, MU, TSM",
                                    help="Separate ticker symbols with commas or spaces.")
        with add_col:
            add = st.form_submit_button("Add stocks", type="primary", use_container_width=True)
    if add:
        symbols, invalid = parse_working_tickers(entered)
        extras = [ticker for ticker in symbols if ticker not in current]
        if invalid:
            st.error("Invalid ticker(s): " + ", ".join(invalid[:8]))
        elif not symbols:
            st.warning("Enter at least one ticker.")
        elif len(current) + len(extras) > MAX_TICKERS:
            st.warning(f"Working lists support up to {MAX_TICKERS} tickers.")
        elif not extras:
            st.info("Those stocks are already included.")
        else:
            st.session_state[DRAFT_KEY] = current + extras
            st.rerun()
    st.caption(
        f"Custom List (Unsaved) · {len(st.session_state[DRAFT_KEY])} stock(s). "
        "Use Save Group to keep these changes."
    )
    return list(st.session_state[DRAFT_KEY])


def save_displayed_watchlist(name: str, symbols: list[str]) -> tuple[bool, str]:
    """Save a snapshot to browser storage, never overwrite existing named lists.

    _init may raise BrowserGroupsPending while awaiting browser storage;
    callers must preserve a pending save across that first rerun.
    """
    name = str(name or "").strip()
    if not name or len(name) > 32:
        return False, "Enter a list name between 1 and 32 characters."
    normalized = [valid_symbol(s) for s in symbols]
    if not normalized or any(not s for s in normalized):
        return False, "Add valid stocks before saving."
    unique = list(dict.fromkeys(normalized))
    if len(unique) > MAX_TICKERS:
        return False, f"A saved list supports up to {MAX_TICKERS} stocks."
    _init()
    lists = st.session_state[NS + "lists"]
    if name in lists:
        return False, f"'{name}' already exists. Use a different name."
    if len(lists) >= MAX_LISTS:
        return False, f"Only {MAX_LISTS} named lists are supported."
    lists[name] = unique
    st.session_state[NS + "active"] = name
    st.session_state[NS + "selected"] = name
    _queue_write()
    return True, f"Saved '{name}' with {len(unique)} stocks."
