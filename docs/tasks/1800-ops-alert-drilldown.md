# 1800: Admin Operations alert drill-down

Status: todo
Depends on: none | Base commit: 26e20e4 | Branch: task/1800-ops-alert-drilldown
Executor: Haiku 5.5 | Fits one session: no. Do chunk A (Go) first, commit, report; a fresh Haiku does chunk B (Python), then chunk C (screenshots, PR).

## 1. Objective

The "Open host alerts" table on /admin/operations shows only Kind, Level, Count, Oldest per group, so the operator cannot see which stays the 8 critical `deadline_at_risk` alerts concern. Add a drill-down page that lists every open alert of a group with message, property, stay (guest, dates, link), level and age, and a kind filter.

## 2. Context

- `alert` table already has `apartment_id`, `reservation_id`, `message`, `detail`, `params`, `created_at`, `resolved_at`, `level`, `kind`. **No schema change.**
- Go summary query: `loadAlerts` in `go/internal/web/auth/opspage/data.go` (GROUP BY kind, level). Template `go/internal/web/auth/opspage/templates/admin_operations.tmpl` section `id="ops-alerts"`. Page code `go/internal/web/auth/opspage/page.go`, strings `go/internal/web/auth/opspage/i18n.json` (+ `i18n_keys.txt`). Route registered in `go/internal/web/auth/auth.go` line ~85 (`GET /admin/operations`).
- Python mirror: `open_alerts()` in `App/app/admin_ops.py`, template `App/app/templates/admin_operations.html` section `ops-alerts`, route `operations_admin` in `App/app/routes/admin_accounts.py` (~929), strings in `App/app/host_i18n.py` (and `host_vi_i18n.py` if the keys exist there).
- Stay page URL is `/reservations/{id}`. Stay columns: `reservation.date_from`, `date_to`, `apartment_id`; lead guest = `guest.is_lead=1` for that `reservation_id`. Alert join pattern to copy: `openAlertsSQL` in `go/internal/hostweb/layout/alerts.go`.
- Rules: Go first (docs/context/go-first.md), design-system checklist (docs/design/design-system.md), light mode, 3 languages for new strings (copy the language set of the existing `ops.*` keys), "one explanation in one place".

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/web/auth/opspage/{data.go,alerts.go,alerts_test.go,templates/*.tmpl,i18n.json,testdata} | edit/new | Go drill-down loader, page, tests |
| go/internal/web/auth/{auth.go,auth_test.go,operations.go} | edit | route and handler |
| App/app/{admin_ops.py,host_i18n.py,host_vi_i18n.py,routes/admin_accounts.py} | edit | Python loader, route, strings |
| App/app/templates/admin_operations*.html, App/app/static/app2.css | edit/new | page, summary links, 768 stack width |
| App/tests/test_admin_operations.py, test_design_guardrails_browser.py | edit | tests |

No other file may change.

### Design (exact)

New admin-only page `GET /admin/operations/alerts` with optional query `kind` and `level`. Same admin guard and same shell/tabs (System tab open) as `/admin/operations`. Page content:

1. Heading "Open alerts" and a back link to `/admin/operations#ops-alerts`.
2. Kind filter: a row of links (`ui-chip` style if the design system has one, else plain links), one per kind with its open count, plus "All". The active one is marked `aria-current="page"`. Plain GET links, no JavaScript.
3. A table (class `ui-table ui-table-stack`, `data-label` on every cell), oldest first, max 200 rows with a line "Showing 200 of N" when capped. Columns: Level, Kind (label + code), Message (the alert `message`), Property (apartment `internal_name` from `alert.apartment_id`, else from the stay's apartment), Stay (lead guest name, `date_from` to `date_to`, link `/reservations/{id}`; "none" when no `reservation_id`; "stay removed" when the id has no row), Status ("open"), Age (reuse the existing age helper/format of the Oldest column).
4. In the existing summary table each Kind cell becomes a link to `/admin/operations/alerts?kind=KIND&level=LEVEL`. The Count cell links to the same URL.
5. Unknown `kind`/`level` values simply give an empty list with the "none" line. Bind all values as SQL parameters.

Do the same in Python (`/admin/operations/alerts`, same columns, same strings, same ordering) so both stacks match. Reuse existing i18n keys where they exist (`ops.col.kind`, `ops.col.level`, `ops.col.oldest`, `ops.none`, `ops.alert_kind.*`).

## 4. Steps

Chunk A (Go): 1) `data.go`: add `LoadAlertDetails(ctx, pool, now, kind, level)` returning rows plus total and kind counts. 2) `page.go` + new template `admin_operations_alerts.tmpl` + route in `auth.go` + strings + `i18n_keys.txt`. 3) Edit summary template so kind/count link. 4) Go tests in `page_test.go` (follow its existing fixtures): detail rows include stay link/dates/guest, kind filter narrows, no-stay and removed-stay rows, non-admin gets the same denial as `/admin/operations`, cap line. Update goldens only if the summary markup change requires it.
Chunk B (Python): same in `admin_ops.py`, template, route, strings; tests next to the existing admin operations tests (grep `open_alerts` in `App/tests`). Keep Python and Go output equivalent.
Chunk C: layout-lint browser test run for the pages, screenshots of the new page and the summary section at 390, 768 and 1280 (Go build), save under `docs/tasks/1800-files/shots/` is NOT allowed (public repo): attach to the PR via the report only if no guest data shows; use test fixtures with fake names. Open one draft PR.

## 5. Do not touch

Alert creation/resolution, schema, migrations, `layout/alerts.go` host cards, mail, servers, deploy, secrets. No new dependency. Never print real guest data.

## 6. Commands

Go: `cd go && go test ./internal/web/auth/... 2>&1 | tail -30`. Python (from `App/`): `.venv/bin/python -m pytest <test-map rows for admin_operations and host i18n> -q --tb=short -x 2>&1 | tail -30`. Layout: `.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs 2>&1 | tail -30` (0 skipped). Lint: `python3 scripts/context_lint.py | tail -30`.

## 7. Acceptance

- [ ] Summary rows link to the drill-down; drill-down lists each alert with message, property, stay link, dates, guest, status, age.
- [ ] Kind filter works without JavaScript on Go and Python.
- [ ] Go and Python tests, layout lint green, 0 skipped.
- [ ] Screenshots at 390, 768, 1280 viewed and described per page in the PR; design-system checklist ticked.

## 8. Stop and ask

As in TEMPLATE.md. Also stop if the stay page `/reservations/{id}` is not reachable by the operator account (then report it; do not change auth).

## 9. Report

`docs/tasks/1800-report.md`, 600 tokens, `Status: review`.
