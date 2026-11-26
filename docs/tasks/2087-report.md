# 2087 Report — Calm dashboard notifications, iCal backfill cutoff, bulk archive old unfilled

- Implemented in Go (`go/internal/web/hostweb/calm_needs_you.go`, `go/internal/web/stays/archive_old.go`).
- Suppressed pre-iCal-connection backfill and >7-day-past unfilled stays from Dashboard `Needs you` while preserving Rule 1 (overdue/failed filings with submitted guests always visible).
- Collapsed 0-claim apartments with >=2 unfilled-form nags into one 14-day snoozable setup card (`POST /dashboard/dismiss-guest-link-nudge`).
- Lowered `#needs-action` visible cap from 5 to 3 and added 1-click bulk archive of old unfilled stays (`POST /reservations/archive-old-unfilled`).
- Verified with Go unit/Postgres tests and Chromium layout-lint + geometry tests (`App/tests/comfy_host_ux_checks.py` via `App/tests/test_go_pages_layout_lint_browser.py`) at 390/768/1280 px.
