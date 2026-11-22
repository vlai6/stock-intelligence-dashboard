"""Offline checks for the News Screener saved-groups controls."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_watchlists import (
    NS, _clean_lists, _create_group, _delete_group, _load_group, valid_symbol,
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

print("PASS: saved groups create/load/delete, existing data and loaded-group state")
