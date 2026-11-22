"""Offline checks for the News Screener saved-groups controls."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_watchlists import (
    NS, _clean_lists, _create_group, _delete_group, _load_group,
    named_groups, active_named_group, activate_named_group,
    save_named_group, remove_named_group, parse_working_tickers,
    removable_stock_list, valid_symbol,
)

# Existing browser-saved groups remain compatible with the new UI.
assert _clean_lists({
    "My Stocks": ["NVDA", "MU"],
    "AI theme": ["NVDA", "TSM", "NVDA"],
}) == {
    "My Stocks": ["NVDA", "MU"],
    "AI theme": ["NVDA", "TSM"],
}
assert valid_symbol("nvda") == "NVDA"
assert parse_working_tickers("NVDA MU,TSM") == (["NVDA", "MU", "TSM"], [])

# Clicking × creates an editable copy; stock groups/ETF presets stay unchanged.
etf_source = ["AAPL", "NVDA", "MSFT", "BRK-B"]
copied = removable_stock_list(etf_source, "nvda")
assert copied == ["AAPL", "MSFT", "BRK-B"]
assert etf_source == ["AAPL", "NVDA", "MSFT", "BRK-B"]
assert removable_stock_list(copied, "MSFT") == ["AAPL", "BRK-B"]
assert removable_stock_list(["NVDA"], "NVDA") == []
try:
    removable_stock_list(etf_source, "NVDA;DROP")
except ValueError:
    pass
else:
    raise AssertionError("Invalid removable ticker should be rejected")

state = {
    NS + "lists": {"My Stocks": ["NVDA", "MU"], "Other": ["AAPL"]},
    NS + "active": "My Stocks",
    NS + "selected": "Other",
    NS + "revision": 0,
}

# Merely selecting a group must not load it until Load is clicked.
assert state[NS + "selected"] != state[NS + "active"]
with patch("custom_watchlists.st.session_state", state):
    _load_group()
assert state[NS + "active"] == "Other"
assert state[NS + "selected"] == "Other"
assert state[NS + "pending"] == state[NS + "revision"]

# Creating a group activates it immediately (empty groups can be filled later).
state[NS + "new_group_name"] = "Technology"
with patch("custom_watchlists.st.session_state", state):
    _create_group()
assert state[NS + "lists"]["Technology"] == []
assert state[NS + "active"] == "Technology"
assert state[NS + "selected"] == "Technology"

# Duplicate names never silently overwrite a saved group.
state[NS + "new_group_name"] = "Technology"
with patch("custom_watchlists.st.session_state", state):
    _create_group()
assert state[NS + "feedback"][0] == "error"
assert state[NS + "lists"]["Technology"] == []

# Deleting the selected active group switches to another existing saved group.
with patch("custom_watchlists.st.session_state", state):
    _delete_group()
assert "Technology" not in state[NS + "lists"]
assert state[NS + "active"] in state[NS + "lists"]
assert state[NS + "selected"] == state[NS + "active"]

# Deleting a group that is selected but not active does not switch loaded news.
state[NS + "selected"] = "Other"
state[NS + "active"] = "My Stocks"
with patch("custom_watchlists.st.session_state", state):
    _delete_group()
assert "Other" not in state[NS + "lists"]
assert state[NS + "active"] == "My Stocks"

# The last remaining group cannot be deleted.
with patch("custom_watchlists.st.session_state", state):
    _delete_group()
assert state[NS + "lists"] == {"My Stocks": ["NVDA", "MU"]}
assert state[NS + "feedback"][0] == "error"

# Unified toolbar saves a displayed preset into a named editable group.
with patch("custom_watchlists.st.session_state", state), patch("custom_watchlists._init"):
    assert named_groups() == ["My Stocks"]
    ok, message = save_named_group("Research", ["nvda", "MU", "NVDA"])
assert ok and "Saved" in message
assert state[NS + "lists"]["Research"] == ["NVDA", "MU"]
assert state[NS + "active"] == "Research"

# Overwriting an existing name follows the Portfolio X-Ray save semantics.
with patch("custom_watchlists.st.session_state", state), patch("custom_watchlists._init"):
    ok, message = save_named_group("Research", ["AAPL"])
assert ok and "Updated" in message
assert state[NS + "lists"]["Research"] == ["AAPL"]

# Empty groups can be created and edited later.
with patch("custom_watchlists.st.session_state", state), patch("custom_watchlists._init"):
    ok, _ = save_named_group("Empty", [])
    assert ok and active_named_group() == "Empty"
    assert activate_named_group("Research")
assert state[NS + "active"] == "Research"

# Delete never touches predefined News Screener source options. If deleting
# the last group, restore the editable empty default instead of leaving None.
with patch("custom_watchlists.st.session_state", state), patch("custom_watchlists._init"):
    ok, _ = remove_named_group("Research")
    assert ok
    ok, _ = remove_named_group("Empty")
    assert ok
    ok, _ = remove_named_group("My Stocks")
    assert ok
assert state[NS + "lists"] == {"My Stocks": []}
assert state[NS + "active"] == "My Stocks"
with patch("custom_watchlists.st.session_state", state), patch("custom_watchlists._init"):
    ok, _ = remove_named_group("Not a real group")
assert not ok

print("PASS: saved groups create/load/save/overwrite/delete, legacy data and active flags")
