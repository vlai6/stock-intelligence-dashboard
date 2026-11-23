"""The user-facing regression scan error should stay compact."""
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_failed_scan_shows_short_message_not_backend_traceback():
    text = APP.read_text(encoding="utf-8")
    assert '"Error: Try a smaller market cap range."' in text
    assert '"Error: ETF scan failed. Please try again later."' in text
    assert 'logging.getLogger(__name__).exception("Regression scan failed")' in text
    assert "SCAN FAILED — {type(exc).__name__}" not in text
    assert 'st.session_state["last_run_complete"] = False' in text


def test_old_results_are_not_misrepresented_as_new():
    text = APP.read_text(encoding="utf-8")
    assert 'st.session_state["last_scan_error"]' in text
    assert 'render_saved_results(' in text
