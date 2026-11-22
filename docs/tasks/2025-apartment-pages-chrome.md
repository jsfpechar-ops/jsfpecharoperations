# 2025: the two `/apartments/{id}` pages join the rest of the product

Status: todo | Depends on: 2027 | Branch: task/2025-apartment-pages-chrome
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier: B (host pages, rule 10)

## 1. Objective — measured on the Go stack, 2026-11-22

Source: `docs/tasks/2019-ux-gate-2011-2018.md`, the 2014 rows (both **FAIL**). Screenshots in `/tmp/ux-2011-2018/` — regenerate, they are not committed (rule 3). Both pages are the ones brief 2014 just brought to DOM parity, so their *content* is right and their *chrome* is not.

**`/apartments/{id}/booking-site`**

1. A **stray unstyled property name** ("Fee Flat A") renders above the page chrome — it belongs inside the layout, not above it.
2. "See plans" is **39 px**, under the 44 px of design-system §1 rule 8.

**`/apartments/{id}/guide/questions`**

3. The **wordmark is used as the H1**, and a second heading follows it — two H1s, so the page has no single name.
4. The heading is **coral**, unlike every other host page heading.
5. A **third tab-bar variant** — the product now has three; this page must use the canonical one.

**Parity tension.** Both pages are DOM-identical to Python (Gate A fail 0), so a Go-only fix breaks `docs/plans/staging-prod-identical.md`. Per [go-first](docs/context/go-first.md), fix in Go; the **owner step in §4.5** adds both paths to prod `UBYHOST_GO_PATHS` (`docs/ENVIRONMENT.md:190`). Do not edit Python to match.

## 2. Context

- `docs/design/design-system.md` — §1 rules 3 (one H1), 4 (canonical header), 8 (44 px), §5b section cards; `docs/design/MASTER.md` for the tab bar and page-header components, `docs/design/pages/` for the property page add-on.
- Go: `go/internal/web/booking/templates/booking_site_setup.tmpl`, `go/internal/web/guest/leon_questions.go` (2014's file), the templates behind `/guide/questions`, and the shared page-header/tab-bar partials.
- The other two tab-bar variants: find them first (`grep -rn 'tab' go/internal/web --include='*.tmpl' | head -20`) and name them in the report — the fix is to converge on one, not to add a fourth.

## 3. Files

- The Go templates and handlers named above for both pages, the shared header/tab-bar partial they converge on, and their `*_test.go`.

## 4. Steps

1. Reproduce both pages at 390/768/1280 before changing anything.
2. Booking site: move the property name into the layout where its siblings put it; no unstyled block above the chrome. Say where it came from (an `{{if}}` branch, a base template, a leftover).
3. Booking site: "See plans" ≥44 px.
4. Guide questions: one H1 only — the page's own name, not the wordmark; the second heading becomes the section heading it is. Heading colour to the canonical token. Tab bar: switch to the canonical variant and **delete or fold the third one** if nothing else uses it; if something does, record it in the report and leave it, naming the owner question.
5. Owner step: add `/apartments/*/booking-site` and `/apartments/*/guide/questions` to prod `UBYHOST_GO_PATHS`.
6. Tests: render tests asserting one `<h1>` per page and the canonical tab-bar class.

## 5. Do not touch

`App/app/`, other pages, Caddy, deploy files, secrets, `UBYHOST_GO_PATHS` itself (owner step). No new dependency. Light mode only. Do not change the guide question **content** — 2014 settled it.

## 6. Commands

```bash
cd go && go build ./... && gofmt -l ./internal ./cmd 2>&1 | tail -30
cd go && go test ./internal/web/booking/... ./internal/web/guest/... ./cmd/ubyhost-web/... -count=1 2>&1 | tail -30
cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30
cd App && UBYHOST_E2E_PG=postgresql://postgres@127.0.0.1:5433 .venv/bin/python ../scripts/e2e/page_parity_audit.py 2>&1 | tail -5
```

## 7. Acceptance

- 390/768/1280 screenshots of **both** pages in the report, opened, one sentence per width per page (rule 10).
- No unstyled block above the chrome; one H1 per page; canonical heading colour; canonical tab bar; all targets ≥44 px.
- Lint green, 0 skipped; the two 2014 audit rows do not regress below fail 0.

## 8. Stop and ask

At the 25-call / 50k-token checkpoint; if the third tab-bar variant is used by a page outside these two (that is a design-system decision, not a local fix); if removing the wordmark-as-H1 changes the page's SEO/title in a way another test asserts.

## 9. Report

`docs/tasks/2025-report.md`, ≤600 tokens: per page before/after per width, the fate of the third tab bar, the owner step, deviations.
