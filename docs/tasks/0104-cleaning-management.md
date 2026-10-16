# 0104: Cleaning management and accessible team schedule

Status: review
Report: docs/tasks/0104-report.md
Depends on: 0103 calendar on main | Base commit: e9fe5487ee31276aedf0d141c46ca3cbe584085c
Branch: feature/cleaning-management-staging
Executor: Codex, explicitly authorized by the owner in this chat on 2026-10-16.

## 1. Objective
Add Cleaning with a broom icon to the sidebar. Deliver host-controlled cleaning
events, calendar/Gantt above a readable chronological list, static instructions,
permanent/manual property codes and scoped account-free read-only sharing.

## 2. Context
Baseline: superhostem-ux-lessons-for-ubyhost.md section 3 and the later easy-fill
read-only cleaner-link plan under docs/plans/new_plan/. Owner approved the
adapted architecture, then requested implementation and easier Superhostem-style
use. Current main already contains the 0103 shared calendar.
No new application dependency. SQL through db helpers, numbered migration.
Use light warm UbyHost tokens, large essential text, 44px controls, EN/CS parity.
The selected cloud workspace fails startup, so edits use GitHub and execution
uses required CI. Never claim local pytest, screenshots or a staging deploy.

## 3. Files
- `.github/workflows/ci.yml`
- `App/app/cleaning.py`
- `App/app/cleaning_codes.py`
- `App/app/cleaning_i18n.py`
- `App/app/cookie_inventory.py`
- `App/app/main.py`
- `App/app/migrations/0010_cleaning.sql`
- `App/app/retention.py`
- `App/app/routes/cleaning.py`
- `App/app/scheduler.py`
- `App/app/static/cleaning.css`
- `App/app/static/cleaning.js`
- `App/app/static/dashboard-calendar.js`
- `App/app/templates/_cleaning_list.html`
- `App/app/templates/_cleaning_screen.html`
- `App/app/templates/_dashboard_calendar.html`
- `App/app/templates/base.html`
- `App/app/templates/cleaning.html`
- `App/app/templates/cleaning_edit.html`
- `App/app/templates/cleaning_properties.html`
- `App/app/templates/cleaning_settings.html`
- `App/app/templates/cleaning_shared.html`
- `App/app/templates/cleaning_shares.html`
- `App/app/ttlock.py`
- `App/tests/test_cleaning.py`
- `App/tests/test_cleaning_browser.py`
- `docs/HOST_APP_DESIGN.md`
- `docs/context/architecture.md`
- `docs/context/status.md`
- `docs/context/ui-decisions.md`
- `docs/privacy/RETENTION.md`
- `docs/privacy/ROPA.md`
- `docs/tasks/0104-cleaning-management.md`
- `docs/tasks/0104-report.md`

## 4. Steps
1. Add migration 0010; persist one automatic event per canonical checkout.
2. Reconcile on schedule reads and the existing minute worker. Preserve source
   dismissals and host date overrides. Never write reservation data.
3. Add protected host CRUD, instructions, explicit code setup, link management.
4. Extend the existing calendar with a data source, typed cleaning lane and
   read-only mode; synchronize the full server-rendered list from the same data.
5. Add permanent code creation through the existing serial TTLock worker:
   type 2, gateway add, no dates; encrypted stable candidate/reference before
   network writes; exact-name reconciliation after uncertain outcomes.
6. Add hashed 256-bit shares scoped to properties, rolling 30-day horizon and
   30-day expiry. Enforce token scope on every read; expose no guest identity.
7. Add lifecycle/tenant/time/timeout tests and real browser checks/captures.

## 5. Do not touch
No filing, guest registration, fees, invoices, reservation mutations or availability
changes. No claims, completion/checklist inputs, cleaner identities, photos,
comments, remote unlock, new dependencies, real credentials or production deploy.
Do not bypass CI, push main, or change the parallel calendar branch.

## 6. Commands
CI runs ruff, the full coverage suite (minimum 86%), browser/geometry checks with
UBYHOST_REQUIRE_BROWSER=1 and zero skips, smoke, Docker, secrets and context lint.
Focused feature job includes tests/test_cleaning.py and
tests/test_cleaning_browser.py alongside calendar regression tests.
Run python3 scripts/context_lint.py from the repository root in CI.

## 7. Acceptance
- Automatic checkout events, host CRUD/overrides and persistent dismissals.
- Static instructions and codes readable without opening any list item.
- Shared calendar/list filters and drag/date-form rescheduling.
- EN/CS, 360/390/1280px, no page overflow, visible keyboard focus, no-JS list.
- External scope/range/expiry/revocation checks and no write authority.
- Permanent/manual PINs independent of guest PIN retention.
- CI green on the exact reviewed revision; synthetic screenshot artifacts.
- Staging deployment SHA and physical TTLock acceptance recorded separately.

## 8. Stop and ask
Record concrete unavailable capabilities in the report. Do not invent test or
deployment results. Implementation is authorized; routine corrections continue
without repeated approval. Live secrets/server settings remain with the owner.

## 9. Report
Record actual CI results, screenshot artifact URLs, reviewed SHA, deviations and
remaining staging/physical-lock checks in docs/tasks/0104-report.md.

## Risk list (for the reviewer)
Migration 0010; cleaning.py; cleaning_codes.py; routes/cleaning.py; ttlock.py;
retention.py; shared calendar JS; external template; host/sidebar geometry.

## Owner steps
After green review, use the feature revision for Render staging. Keep UbyPort
mock. Disable staging no-login mode before generating real codes or team links.
Verify the deployed SHA, then test a designated lock's permanent PIN and revoke.
