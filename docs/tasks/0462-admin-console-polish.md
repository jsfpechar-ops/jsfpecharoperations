# 0462: Operator console polish (phone first)

Status: todo
Depends on: 0461 merged | Base commit: main | Branch: task/0462-admin-console-polish
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Make `/admin` (Operator console) and the other admin pages calmer and easier to scan on a phone, using only existing components. Scope is fixed to the six items in section 4; anything beyond them is a new brief.

## 2. Context
Owner screenshot (iPhone, 390 px): stat row shows 3 tiles then a lonely 4th ("On trial") on its own row; three empty queues each repeat the same "Nothing needs attention here." in a full-height card; the page title and date line sit far above the first content; the floating help button covers the right edge of the last card. Rules: MASTER 5.1 (page template), 7 (closed component catalog, no new components), 8 (copy tone), 10 (never do), [admin_customers add-on](design/pages/admin_customers.md).

## 3. Files
`App/app/templates/admin_home.html`, `admin_operations.html`, `admin_funnel.html`, `admin_incidents.html`; `App/app/host_i18n.py` (strings, en/cs/vi); CSS only if a defect cannot be fixed with existing classes: then one rule in the existing host CSS file the page already uses (find with `grep -rn "ui-stats" App/app/static/*.css | head -3`), bump its cache key (`test_static_versions.py`).

## 4. Steps
1. Screenshot first: `/admin`, `/admin/operations`, `/admin/funnel`, `/admin/incidents` at 390 px, before (use the browser test fixtures in `test_design_guardrails_browser.py` for the login helper).
2. Stat tiles on `/admin`: 2 × 2 on phone (4 tiles) via the existing `ui_stats` behaviour; if it only supports 3 columns, show exactly the 3 most important (MRR, Overdue, On trial) and put ARR in the MRR tile's label. Pick whichever needs no CSS and say which.
3. Empty queues: when a queue is empty, collapse its card to one quiet line (title plus the existing `home.admin.queue.none` text on one row). Non-empty queues unchanged. Order the queues: Overdue, Trials ending, Unverified, Ending.
4. Same collapsed-empty rule on `/admin/operations` sections that already have an empty branch.
5. Tighten the header: `home.admin.meta` shows the date once; no extra divider lines above the first block.
6. Check the floating help button does not hide the last row's action at 390 px (bottom padding per MASTER 6.2 point 6); fix with the existing page padding only.
7. Copy: no sentence that the button already says (rule 9); keep keys, edit values in all three languages.

## 5. Do not touch
Routes, queries, billing logic, auth, the tab strip from 0461, the More sheet, any other host page, migrations, dependencies, colour tokens, dark mode (none).

## 6. Commands
From `App/`:
`.venv/bin/python -m pytest tests/test_admin_customers.py tests/test_admin_operations.py tests/test_admin_funnel.py tests/test_billing_admin.py tests/test_0419_admin_billing_browser.py tests/test_design_admin.py tests/test_design_guardrails_browser.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`
0 skipped. Repo root: `python3 scripts/context_lint.py | tail -30`.

## 7. Acceptance
- Before and after 390 px screenshots for the 4 pages in the report; no horizontal scroll; no clipped text in cs and vi (add one screenshot of `/admin?lang=vi`).
- Tests above pass, 0 skipped.
- The change list matches section 4 exactly.

## 8. Stop and ask
If a step needs a new component or a token change, skip that step and list it under "Owner decisions". Do not redesign beyond section 4.

## 9. Report
`docs/tasks/0462-report.md`, under 100 lines, with the before/after screenshots and an "Owner decisions" list.
