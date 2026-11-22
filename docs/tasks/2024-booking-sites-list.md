# 2024: `/booking-sites` names every row, and its title is not singular

Status: todo | Depends on: 2027 | Branch: task/2024-booking-sites-list
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens | Tier: C (labels and targets)

## 1. Objective — measured on the Go stack, 2026-11-22

Source: `docs/tasks/2019-ux-gate-2011-2018.md`, the `/booking-sites` row (verdict **FAIL**), screenshots in `/tmp/ux-2011-2018/` (regenerate; not committed, rule 3).

1. **The last row has no property name.** Every other row names its property; one does not, so the reader cannot tell whose row it is. Find out why before styling: a missing join, a null property, or a template branch — the answer belongs in the report, because a missing name may be a **data** bug, not a label bug.
2. **The title is singular** on a list that shows several sites.
3. **"Set up" is 30 px**, four times — under the 44 px of design-system §1 rule 8.

**Parity tension.** The page is DOM-identical to Python today (Gate A fail 0), so a Go-only fix breaks `docs/plans/staging-prod-identical.md`. Per [go-first](docs/context/go-first.md), fix in Go and let the **owner step in §4.4** add the path to prod `UBYHOST_GO_PATHS` (`docs/ENVIRONMENT.md:190`). Do not edit Python to match.

## 2. Context

- `docs/design/design-system.md` §1 rule 8 (targets), §4 copy rules; rule 9 in [AGENTS.md](AGENTS.md) (@copy: one explanation lives in one place, never a sentence the button already says).
- Go: `go/internal/web/booking/templates/booking_sites.tmpl` (2014 touched it: `booking_sites.title`), the handler that feeds the rows, and its i18n catalog (`go/internal/web/booking/i18n.json`, regenerated with `App/scripts/go_host_i18n.py` — never hand-edited).
- Python reference (read-only): `App/app/templates/booking_sites.html` and its route, to see whether Python has the same unnamed row.

## 3. Files

- `go/internal/web/booking/templates/booking_sites.tmpl`, the handler and query behind it, `go/internal/web/booking/i18n.json` + `i18n_keys.txt` (regenerated), and their tests.

## 4. Steps

1. Reproduce at 390/768/1280 and identify the unnamed row. Query the seeded DB for its property id and say what you found.
2. Fix the name: if it is data, fix the query/template so a propertyless row either names its property or is not listed — **say which you chose and why**; do not print "—" silently.
3. Title: plural when the list has more than one row, singular at one. Use the catalog's existing plural forms; do not concatenate strings.
4. Raise "Set up" to ≥44 px; then the owner step: add `/booking-sites` to prod `UBYHOST_GO_PATHS`.
5. Tests: a render test with 0, 1 and 2 rows covering the title form and the name on every row.

## 5. Do not touch

`App/app/`, other pages, Caddy, deploy files, secrets, `UBYHOST_GO_PATHS` itself (owner step). No new dependency. Light mode only.

## 6. Commands

```bash
cd go && go build ./... && gofmt -l ./internal ./cmd 2>&1 | tail -30
cd go && go test ./internal/web/booking/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
cd App && .venv/bin/python scripts/go_host_i18n.py --check 2>&1 | tail -10
cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
```

## 7. Acceptance

- 390/768/1280 screenshots of `/booking-sites` in the report, opened, one sentence per width (rule 10).
- Every row names its property, or the report justifies the exception with the DB evidence.
- Title correct at 0 / 1 / many; "Set up" ≥44 px; `go_host_i18n.py --check` clean; lint green, 0 skipped.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if the unnamed row turns out to be a **data** problem that reaches beyond this page (a property with no name anywhere); if `booking_sites.title` is also used by another page.

## 9. Report

`docs/tasks/2024-report.md`, ≤600 tokens: what the unnamed row was, the wording chosen, before/after per width, the owner step, deviations.
