# 0040 dashboard audit

Status: review

The actual dashboard template is `App/app/templates/dashboard.html`. The original wide mismatch came from the shared `.wrap.with-sidebar > .page-header { max-width: none; }` override in `App/app/static/host.css`: the dashboard title/header stretched across the workspace while stat cards and queue sections retained the centered 1080px lane. The shared CSS owner removed that override and restored a common lane. No dashboard template presentation change was needed.

The dashboard now passes wide checks with a synthetic rich queue at 1440, 1680, 1920, and 2048px in EN and CS. Header, stats, and needs-action edges are asserted within 2px. Open/More remain aligned in every row; row action columns stay fixed. Synthetic active calendar and demo records verify the Add stay, Update calendars, and Clear demo data controls are present and aligned at desktop sizes, with 44px mobile targets at 360/390px. Queue status, urgency, unique five-row cap, overflow count, menus, hover, and keyboard focus remain covered.

Validation:

- `UBYHOST_BROWSER_EXECUTABLE=/usr/bin/chromium UBYHOST_REQUIRE_BROWSER=1 ... pytest tests/test_host_quiet_dashboard_browser.py -q -k rich_queue` — 1 passed, 0 skipped across EN/CS at 360, 390, 1280, 1440, 1680, 1920, and 2048px.
- Existing dashboard geometry/menu test — 1 passed, 0 skipped at 360, 390, and 1280px EN/CS.
- Screenshots: `generated_images/host-quiet-dashboard-wide/` (mixed-state, positive amber/taupe/blue/red counts, old overdue row, five displayed rows, overflow, demo/sync controls, plus hover/focus captures).

Only `App/tests/test_host_quiet_dashboard_browser.py` was changed for this dashboard audit; app markup and queue logic were untouched.
