# 2023: `/admin` works at 390, and stops being a wall of tables

Status: todo | Depends on: 2022 (only if the admin home shows claim state), 2027 | Branch: task/2023-admin-home-390
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: B (host page, rule 10)

## 1. Objective — measured on the Go stack, 2026-11-22

Source: `docs/tasks/2019-ux-gate-2011-2018.md`, the `/admin` row (verdict **FAIL**). Screenshots: `/tmp/ux-2011-2018/` — regenerate, they are not committed (rule 3).

| Width | What is wrong |
|---|---|
| 390 | a tab label is clipped at the right edge (x=334→424, renders "Sy…") |
| 390 | a money KPI wraps **mid-number** |
| 390 | 27 + 25 rows render as tables, so rows are unreadable and scroll sideways |
| 768 / 1280 | no pagination on either long list |
| all | 80 / 105 / 112 interaction targets are under 44 px |

Related, and **not** this brief: `/` as admin renders the host dashboard — there is no admin branch (see 2012's report). That is a routing question for the owner, not a geometry fix.

**Parity tension, read before you start.** `/admin` is DOM-identical to Python today (`docs/tasks/2019-ux-gate-2011-2018.md`: identical text, and Gate A is fail 0). A Go-only geometry fix therefore *breaks* `docs/plans/staging-prod-identical.md`. Per [go-first](docs/context/go-first.md) ("bug fix: fix it in Go … the brief's owner steps include the switch"), the fix is Go-only and the **owner step in §4.5 adds the path to prod `UBYHOST_GO_PATHS`** (`docs/ENVIRONMENT.md:190`), which restores 1:1 by construction. Do not edit Python to match.

## 2. Context

- `docs/design/design-system.md` — §1 rule 8 (44 px targets), §5 (table→cards at 390), §5b section cards. Read it before touching markup.
- Go: `go/internal/web/admin*` handlers and templates; `grep -rn 'Sy' go/internal/web/admin --include='*.tmpl' | head` to find the clipped tab; the KPI partial that prints money.
- Python reference (read-only) for what each block means: `App/app/templates/admin*`.
- Long lists: find the handler that renders the 27 and 25 row sets and the SQL that feeds them — pagination is a query limit, not a CSS trick.

## 3. Files

- The Go admin templates and handlers for `/admin`, plus their `*_test.go`. `go/internal/web/*/templates/` if a shared card partial is used.
- A CSS/Tailwind class change only through the repo's existing tokens — no new stylesheet, no new dependency.

## 4. Steps

1. Reproduce: 390 screenshot of `/admin` as admin, before you change anything. Record the clipped tab's box (`getBoundingClientRect`) so the fix is measured, not eyeballed.
2. Tab row: no item may be clipped at 390 — wrap, shrink, or move to an overflow at the width where it breaks; the label must never truncate to "Sy…".
3. Money KPI: format so a number never breaks mid-figure (non-breaking space or a wider grid cell; the value must stay selectable and copyable as one string).
4. Tables → cards at 390 for both long lists (design-system §5); ≥44 px targets everywhere (rule 8); keep the same cells and the same order.
5. Pagination on both lists at every width: page size, and the URL parameter — write what you chose in the report. Then the owner step: add `/admin` (and any sibling admin path you touched) to prod `UBYHOST_GO_PATHS`.
6. Tests: a Go render test for card mode, and the browser geometry test for the page.

## 5. Do not touch

`App/app/`, other pages, Caddy, deploy files, secrets, `UBYHOST_GO_PATHS` itself (**owner step**, §4.5). No new dependency. Light mode only (rule 6).

## 6. Commands

```bash
cd go && go build ./... && gofmt -l ./internal ./cmd 2>&1 | tail -30
cd go && go test ./internal/web/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
python3 scripts/go_parity_check.py --all 2>&1 | tail -30
```

## 7. Acceptance

- 390/768/1280 screenshots of `/admin` in the report, each opened, with a sentence per width on what you saw (rule 10).
- No clipped label, no mid-number wrap, no sideways scroll at 390; every target ≥44 px.
- Both long lists paginate, and the page size is stated.
- `test_layout_lint_browser.py` green with **0 skipped**; Go tests green; `go_parity_check.py --all` still 342/342.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if the tab-row fix needs a new component in the design system; if pagination changes a row count another test asserts; if a fix would require editing Python.

## 9. Report

`docs/tasks/2023-report.md`, ≤600 tokens: before/after per width, the pagination choice, the measured target sizes, the owner step, deviations.
