# Reliable weekday Regression Email trigger

GitHub Actions scheduled events have not started this repository's email
workflow reliably. The scanner itself and SMTP were confirmed to work via
manual `workflow_dispatch`. Use an **independent scheduling service** to
dispatch the existing GitHub workflow each weekday at 8:30 a.m. New York time.

This requires a one-time user-side account and authorization setup; committing
this file does **not** activate an external scheduler.

## One-time setup (free cron-job.org option)

1. Create a free account at https://cron-job.org/ and enable two-factor
   authentication. Do not put your GitHub credential in the repository,
   Streamlit secrets, chat messages, or source files.
2. In GitHub, open Settings -> Developer settings -> Personal access tokens
   -> Fine-grained tokens and create a token scoped to **only**
   `vlai6/stock-intelligence-dashboard`. Give it repository **Actions:
   Read and write** permissions. Set a short expiration and renew it before
   expiration. (Use the minimum permissions GitHub allows for workflow
   dispatch.)
3. Create a new cron-job.org cron job with:
   - **Name:** Stock Intelligence Toolkit - Regression Email
   - **URL:**
     `https://api.github.com/repos/vlai6/stock-intelligence-dashboard/actions/workflows/cloud-email-scanner.yml/dispatches`
   - **Schedule:** Monday–Friday, **08:30**, time zone **America/New_York**
   - **HTTP method:** `POST`
   - **Content-Type:** `application/json`
   - **Header:** `Authorization: Bearer YOUR_FINE_GRAINED_GITHUB_TOKEN`
   - **Header:** `Accept: application/vnd.github+json`
   - **Request body:**
     ```json
     {"ref":"main","inputs":{"mode":"live","automated":"true"}}
     ```
4. Save the job, check the next scheduled times, and use the scheduler's
   test-run feature **only when you intend a live scan/email**. A successful
   GitHub dispatch returns HTTP **200** (with run details, on current API
   versions) or **204** (legacy response). This confirms only that GitHub
   accepted the request, not that the scan or email succeeded.
5. Verify the resulting workflow at
   https://github.com/vlai6/stock-intelligence-dashboard/actions and check
   for the scanner log line `[mail] Email sent successfully`. If the
   workflow run was skipped by the morning gate or the SMTP step failed,
   the scheduler's HTTP 204 alone does not establish email delivery.

## Safeguards already built into the workflow

- The external service only requests the **existing** GitHub Actions job.
  SMTP credentials remain entirely in GitHub Actions Secrets.
- External scheduled dispatches are accepted only Monday–Friday between
  **08:20 and 10:30 America/New_York**, including daylight-saving changes.
- GitHub's native 08:30 and 08:55 triggers remain as backups.
- **Only one live regression digest is intended per Eastern calendar day,**
  regardless of which scheduler triggered it. The 08:55 backup and any later
  external/native triggers skip after an earlier successful delivery.
- **Manual LIVE scans also count toward that same daily digest limit.** If you
  manually send the digest at 04:30 ET, the 08:30 scheduled attempt will skip.
  **Dry runs do not send email**; selecting `test-email` deliberately sends
  a separate SMTP diagnostic message.
- Scan failures are logged in GitHub Actions, **not emailed as an additional
  "cloud run failed" message**.
- Workflows still skip NYSE holidays and may include partial-scan warnings.
- The state marker is restored from the Actions cache; a cache outage/loss,
  concurrent external systems, or a crash between SMTP acceptance and saving
  the marker can break deduplication. This is best-effort one-email-per-day
  protection, not a mathematically strict delivery guarantee.

## If automatic triggering still does not work

- Confirm the workflow is **enabled** in Actions and located on the default
  `main` branch. A disabled workflow does not react to external dispatches
  or GitHub cron.
- Check the cron-job.org history: **401** usually indicates an invalid token;
  **403** can be missing Actions permission or policy; **404** can be a wrong
  URL, branch/workflow or inaccessible repository; **200/204** is accepted.
- Then check GitHub Actions logs separately: queueing, market-day gating,
  price source failures and SMTP can all prevent an email after a dispatch.

Sources:
- GitHub workflow dispatch: https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event
- GitHub scheduled event limits: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- External scheduler: https://docs.cron-job.org/creating-cron-jobs.html
