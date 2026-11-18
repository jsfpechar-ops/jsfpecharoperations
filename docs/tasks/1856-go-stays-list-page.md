# 1856: Port GET /reservations to Go, part 2: template, route, parity

Status: todo (depends on 1855)
Depends on: 1855 | Base commit: tip after 1855 | Branch: task/1856-go-stays-list-page
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k)
Tier: B (host UI, read-only; switch is an owner step)
Pairs with 1857 and 1858, which both wait for this brief.

> **One PR mode.** Commit each step as `1856 step k`. Never push, merge or deploy. Every command ends in `| tail -30`. Anchors quoted from the tip: if one is missing, STOP.

## Open questions

None. Owner decision 2026-11-17: Go only, no Python exception.

## 1. Objective

Serve `GET /reservations` from Go behind `UBYHOST_GO_PATHS` with the same HTML as Python: chips, filter form, rows, the `stays-pager ph-hide` nav and the `list stays-more` link with `rel="next"`. Parity tests prove it.

## 2. Context

Rules 6, 7, 9, 10. Python reference, READ-ONLY: `App/app/templates/reservations.html` (chips ~91-96, reset ~102, filter form ~108-135, row loop, pager ~269-276; use `grep -n 'for item in rows\|stays-pager\|stays-more' ...` then 150-line ranges). Go host layout: `go/internal/hostweb/layout/shell.html` (`layout.base`, `.Head`, `.Nav`, `V2`), usage example `go/internal/web/customers/pages.go` (`layout.MustParse`, `layout.Render`). Registration pattern: `go/cmd/ubyhost-web/register_*.go` (find the page-route one with `grep -rn 'customers\.' go/cmd/ubyhost-web --include=*.go | head`). A GET answered 501 with `X-Ubyhost-Not-Ported` falls back to Python ([ENVIRONMENT](../ENVIRONMENT.md), `UBYHOST_GO_PATHS`); POST routes under `/reservations` stay on Python, so register only exact `GET /reservations`.

## 3. Files

- New `go/internal/web/stays/templates/stays_list.tmpl` and `i18n.json` + `i18n_keys.txt` (copy every string key the Python template uses from `App/app/host_i18n.py` for en, cs, vi; no new copy).
- New `go/internal/web/stays/handlers.go`: `Register(mux, deps)` for `GET /reservations`, calls `List` from 1855, renders with `layout.Render`, `Nav` as Python's `reservations.html` sets it.
- `go/cmd/ubyhost-web/register_stays.go` (new) plus the one call line in the existing wiring file you find in step 0.
- New `go/internal/web/stays/handlers_test.go` and `go/internal/web/stays/parity_test.go`.
- `docs/ENVIRONMENT.md`: add `/reservations` to the `UBYHOST_GO_PATHS` example only after the owner steps; this brief documents it, does not enable it.
- Read-only: the Python files above, `App/tests/test_0523_stays_list.py`, `App/tests/test_0766_phone_stays_browser.py`.

## 4. Steps

0. Anchors. `grep -rn 'web/stays' go/cmd | tail -30` (expect none); `ls go/internal/web/stays | tail -30` (expect 1855 files). Find the wiring file as described in section 2.
1. Template: port `reservations.html` block by block. Keep class names, `data-filter-summary`, `rel="next"`, `ph-hide`, `stays-pager`, `stays-more` byte-for-byte. Normalise whitespace only.
2. Handler: login guard like the customers handlers (no session: same redirect as Python). Unknown account data: same empty state as Python.
3. Register and wire. Anything not listed (POSTs, `/reservations/{id}`) is not registered, so Python keeps it.
4. Parity test: render a fixed fixture (6 stays, one failed report, one archived) in Go and compare the normalised HTML of `.stays-list` rows, chips, pager and more-link with a golden file `testdata/stays_page1.html`; generate the golden from Python once with `App/tests/test_0523_stays_list.py` helpers (copy the fixture, write the HTML out, commit it). Also golden for `?page=2` and `?report=failed`.
5. Tests: `cd go && go test ./internal/web/stays/... ./cmd/ubyhost-web/... 2>&1 | tail -30`.
6. Browser and geometry rows from the test-map with `UBYHOST_GO_PATHS` containing `/reservations` in the local compose (steps in [workflow](../context/workflow.md#ux-gate)): `tests/test_0766_phone_stays_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py`, 0 skipped; 390/768/1280 screenshots.

## 5. Do not touch

Any non-static file under `App/`; POST routes; Caddy config; templates of other pages; `go/internal/hostweb/layout` (1858 owns it).

## 6. Commands

From `go/`: `go vet ./internal/web/stays/... ./cmd/ubyhost-web/... 2>&1 | tail -30`; `go test ./internal/web/stays/... ./cmd/ubyhost-web/... 2>&1 | tail -30`. From `App/`: the browser row above, `2>&1 | tail -30`. Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- Parity goldens pass; Go answers `GET /reservations` with HTML equal to Python after normalisation.
- PR body: 390/768/1280 screenshots opened with one line per page (rule 10), design-system checklist ticked, test tails, 0 skipped.
- Owner steps (numbered, plain words), after the PR is merged and deployed: 1. Open the server `.env`. 2. Add `/reservations` (exact, no star) inside the quotes of `UBYHOST_GO_PATHS`. 3. Run `docker compose up -d caddy` as in [LIGHTSAIL](../LIGHTSAIL.md). 4. Open Stays on a phone and a laptop; if it looks wrong remove the path again and reload caddy (rollback).

## 8. Stop and ask

Stop at 30 tool calls or 60k tokens, if a Python template include has no Go equivalent in `layout`, or if a step needs a file not named in section 3.

## 9. Report

What changed; last 30 lines of each test output; 390, 768, 1280 px screenshots; checklist ticked; the exact `UBYHOST_GO_PATHS` line for the owner.
