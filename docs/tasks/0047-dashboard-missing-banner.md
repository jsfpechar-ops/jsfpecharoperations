# 0047: One banner that says what blocks reporting

Status: todo
Depends on: none | Branch: task/0047-dashboard-missing-banner
Executor: Cursor local agent | Fits one session

## 1. Objective
The dashboard shows, at most once, an amber banner listing each property that can't report yet and the missing items by name, each linking to the field. When everything is ready the banner is absent (no "all done" card).

## 2. Context
- `App/app/routes/admin.py` `_readiness(apartment, entities, issues, has_stays)` and `_READINESS_REPORT_FIELDS` already compute per-property items with anchors.
- `App/app/templates/dashboard.html`; `docs/HOST_APP_DESIGN.md` §1 rules 3–5 and §4 (dashboard as a work queue).
- Rule: a status must come from persisted data.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/routes/admin.py | edit | in the dashboard handler, collect the report items that aren't done for active properties |
| App/app/templates/dashboard.html | edit | banner at the top: "{property}: missing {item}, {item}" → link `/apartments/{id}#{anchor}`; max 5 properties, then "and N more" → /apartments |
| App/app/host_i18n.py | edit | EN + CS keys |
| App/tests/test_dashboard_missing_banner.py | new | tests |

## 4. Steps
1. Reuse `_readiness` and `validation.validate_apartment`; don't duplicate field lists.
2. Only active properties; only report items (not invite items).
3. Tests: banner lists the missing item names in readiness order; absent when complete; the 6th property collapses into "and 1 more".

## 5. Do not touch
Other dashboard sections, CSS tokens (use existing alert classes from `_host_alerts.html`).

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Screenshots at 360, 390 and 1280 px with 1 and with 6 incomplete properties (demo data).

## 8. Stop and ask
1. The dashboard handler can't reach entities and issues without N+1 queries over 20 properties. Then report the query count and stop.

## 9. Report
Files, test tail, screenshots.
