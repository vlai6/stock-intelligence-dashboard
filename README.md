# Compact inputs, gold trendline, 60/40 stock comparison layout

This is a **targeted source patch**, not a replacement for your full project files. It preserves your current Gemini, custom-list, ETF, regression, and financial-metric calculations.

## Changes

1. **Recent Sentiment**: Makes the bordered **News Sentiment stock list** selector and the **Stock ticker / Analyze stock** form approximately half the page width, aligned left. Other page content remains full-width.
2. **Stock Intelligence / Price History**: Makes the optional trend line bright gold (`#FFD21F`), dashed, and 4px wide. It is applied immediately before the chart renders.
3. **Stock Intelligence / comparison panels**: Gives **AI Competitor Comparison 60%** of the available row width and **Financial Metrics 40%**. Existing metrics are preserved; the narrower table can still scroll horizontally.

## Install

1. Stop the existing Streamlit process with **Ctrl + C**.
2. Unzip `apply_layout_update.py` into the root of **StockIntelligenceDashboard**, alongside `app.py` (not into `pages/` and not into your standalone Regression Scanner).
3. In VS Code PowerShell, from your dashboard project root, run **one at a time**:

   ```powershell
   .\.venv\Scripts\python.exe apply_layout_update.py --check
   .\.venv\Scripts\python.exe apply_layout_update.py
   .\.venv\Scripts\python.exe -m py_compile pages\0_Stock_Intelligence.py pages\2_News_Sentiment.py
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```

No output from the `py_compile` command means syntax validation passed. `--check` does not change any source files.

The patch backs up the original two page files under `.layout_update_backups/<timestamp>/pages/` before writing. It checks for the expected Python code structures and stops without changing files if they don't match.

## If something looks wrong

Stop Streamlit. Copy the **two original page files** from the timestamped `.layout_update_backups` directory back into `pages/`, replacing the modified files. Restart Streamlit.

If `UPDATE NOT APPLIED` appears, upload the current exact versions of `pages/0_Stock_Intelligence.py` and `pages/2_News_Sentiment.py` rather than running earlier installers.

## Testing notes

Verified via `ast.parse`, a dry-run, a simulated install, repeated-install idempotence, and patch tests against three earlier source variants. No live Streamlit browser session or external API call was performed.
