# 0103: Interactive dashboard booking calendar

Status: review
Report: docs/tasks/0103-report.md
Depends on: none | Base commit: 2662f404a40dc29dac3dcb888e83cf8e5b636f9d | Branch: feature/dashboard-interactive-calendar-20261015
Executor: Codex, explicitly authorized by the owner in this chat, 2026-10-15.

## 1. Objective
Replace routine dashboard stays with a functional reservation calendar and Gantt.
Support dragging nights to create a stay, clickable details, and automatic view selection.

## 2. Context
Owner requested staging first, UbyHost warm styling, removal of Waiting for guests
from the dashboard summary, and Google Calendar style creation/details interactions.
Owner then authorized Codex implementation and automatic Gantt at a property threshold.
Chosen threshold is 3 visible active properties; manual view selection persists.
Checkout is exclusive. Filing, guest data, deadlines and automation remain canonical.
Source anchor: dashboard handler uses access.owner_id(request), Prague today, and
reporting.dashboard_rows(days_ahead=30, overview=True). Calendar reads must not reuse
that truncated date horizon. Manual creation remains POST /reservations.

## 3. Files
- `App/app/routes/admin.py`
- `App/app/routes/dashboard_calendar.py`
- `App/app/templates/dashboard.html`
- `App/app/templates/_dashboard_calendar.html`
- `App/app/static/dashboard-calendar.js`
- `App/app/static/dashboard-calendar.css`
- `App/app/host_i18n.py`
- `App/app/cookie_inventory.py`
- `App/tests/test_dashboard_calendar.py`
- `App/tests/test_dashboard_calendar_browser.py`
- `App/tests/test_host_quiet_dashboard_browser.py`
- `App/tests/test_signed_in_chrome.py`
- `.github/workflows/ci.yml`
- `docs/HOST_APP_DESIGN.md`
- `docs/DESIGN.md`
- `docs/context/architecture.md`
- `docs/context/status.md`
- `docs/context/decisions.md`
- `docs/context/known-issues.md`
- `docs/context/ui-decisions.md`
- `docs/tasks/0103-dashboard-calendar.md`
- `docs/tasks/0103-report.md`

## 4. Steps
1. Add bounded, owner-scoped GET /dashboard/calendar with explicit event serialization.
2. Add calendar JSON responses to canonical manual creation, strict range/headcount
   validation and overlap confirmation. Preserve ordinary form behavior.
3. Render Month/Week/Year plus property Gantt. Default Auto: Month below 3 properties,
   Gantt at 3+. Preserve manual preference; filters recalculate only in Auto.
4. Add pointer and keyboard date selection, create/details/settings dialogs, native
   stay links, occupancy markers, stacked overlaps, retry and loading states.
5. Remove Waiting for guests summary; keep real urgency, three compact indicators,
   onboarding, and a useful no-JavaScript stay-list fallback.
6. Add policy/auth/creation and real browser interaction/geometry checks. Include
   calendar browser tests in required CI and a parallel feature check, enforce zero
   skips and retain synthetic screenshot artifacts.
7. Keep draft PR off main. Render staging requires reviewed green revision and
   verification of the deployed SHA. Never deploy production for this task.

## 5. Do not touch
No filing, scheduler, provider/lock, fee, invoice, guest-form, auth or schema changes.
No new application dependencies or outbound service calls.
No real guest/operator data in committed evidence. Never push or merge main.

## 6. Commands
From App: python -m pytest tests/test_dashboard_calendar.py -q
From App with required Chromium: UBYHOST_REQUIRE_BROWSER=1 python -m pytest
tests/test_dashboard_calendar_browser.py tests/test_host_quiet_dashboard_browser.py
tests/test_host_geometry.py -q -rs
Required full checks follow existing CI (coverage >=86%, ruff, browser, smoke,
Docker, shellcheck, secrets, context). Root: python3 scripts/context_lint.py.
The current chat has no shell tool; CI is the execution path. Do not report a
local application test or screenshot as completed.

## 7. Acceptance
- [x] 1–2 properties default Month, 3+ Gantt; manual selection wins and can reset.
- [x] Drag/keyboard selection prefills occupied nights with exclusive checkout.
- [x] Save persists a real manual stay via canonical protected POST.
- [x] Overlaps are visible and need confirmation for calendar creation.
- [x] Booking details and native full-stay links work.
- [x] Tenant isolation, archived/cancelled exclusions, date boundaries and >5 stays.
- [x] EN/CS at 360/390/760/1024/1280/1440/1680/1920/2048; no document overflow.
- [ ] CI green, browser/geometry zero skips, synthetic screenshot artifacts.
- [ ] Exact reviewed revision deployed and verified on Render staging.

## 8. Stop and ask
Record concrete blockers if a required check, browser, provider access, or data
contract is unavailable. No guessed deployment claims and no production action.
Implementation is already authorized; routine fixes do not need renewed approval.

## 9. Report
Record code changes, executed checks, failed/skipped checks, screenshot artifact
links, exact PR head and staging status in docs/tasks/0103-report.md.
