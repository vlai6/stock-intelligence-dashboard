# Regression scanner email automation — migration

The old regression-scanner email automation is now staged in the main Stock
Intelligence Dashboard repository under `regression_scanner/`. The workflow is
`.github/workflows/cloud-email-scanner.yml`.

## Preserved behavior

* Five market-cap scans (USD 2–5B, 5–10B, 10–25B, 25–50B, 50B+).
* Original 10-year / 2,500-session linear regression, with -3σ and -4σ
  thresholds; the 50B+ bucket also qualifies at -2.75σ.
* Same HTML and text email reports, intrinsic value estimates, diagnostic
  details, and manually selectable `test-email`, `dry-run-small`,
  `dry-run-full`, and `live` modes.
* Weekday 8:30 AM America/New_York schedule, subject to GitHub Actions delay,
  scanner execution time, and NYSE trading-day checks.

The scanner has its own Python dependencies and runs from the scanner folder.
The root Streamlit application and root requirements.txt are unchanged.

## Required cutover

1. Merge the migration PR into `vlai6/stock-intelligence-dashboard` main.
2. In destination repository Settings > Secrets and variables > Actions >
   Secrets, configure the same SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
   and ALERT_TO values as in the old repo. Use an email app password, not an
   account login password. Secrets do NOT migrate between repositories.
3. From destination repository Actions > Stock Intelligence - Regression Email
   Alerts > Run workflow, run `test-email` and verify receipt; then use
   `dry-run-small` on a trading day and inspect the diagnostic artifact.
4. After testing, disable the OLD repo's automatic schedule (set the old
   repo Actions variable `ENABLE_CLOUD_SCHEDULE=false` or disable the old
   workflow). Then set the destination repo Actions variable
   `ENABLE_CLOUD_SCHEDULE=true`. Do not enable both schedules at once.
5. Manually run `live` when you want to verify a full report. A first
   destination live run may mark prior symbols as new because the GitHub Actions
   cache and deduplication state are repo-specific. The old state cache is not
   copied automatically.

## Watchlist snapshot

After a successful live email, `publish_watchlist.py` publishes
`state/alerts.json` to the dashboard repository using the built-in GitHub
Actions token with Contents: write permission. The snapshot contains the stocks
ACTUALLY EMAILED, session, z-scores, scan coverage, and timestamp; it is not
the deduplication state.

IMPORTANT: This dashboard repo is PUBLIC. Snapshot tickers and scores will
be publicly visible, but no email credentials or API tokens are published.
The existing News Screen uses its own browser-saved watchlist and does not yet
automatically read this file. That integration is separate from moving the
GitHub Actions emailer.

The workflow runs Python from `regression_scanner/` and stores scan reports
under `regression_scanner/scheduled_scans/`. Its action cache keys use a
dashboard-specific prefix. Check uploaded `scan-coverage-*` artifacts for
data errors and missing market-cap buckets.

Source repo is not deleted or archived by this migration.
