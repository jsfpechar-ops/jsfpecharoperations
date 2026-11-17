# 1840: Stays on a phone: "Show more" appends rows, filters round-trip (Go)

Status: todo (depends on 1843, which depends on 1842)
Depends on: 1843 | Base commit: tip after 1843 | Branch: task/1840-stays-show-more-append
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k; hand over per [workflow](../context/workflow.md#when-haiku-reaches-the-cap))
Tier: B (host UI, no data change)
Pairs with 1841 (Turbo back cache). Order: 1842, 1843, 1840, 1841.

> **One PR mode.** Commit each step as `1840 step k`. Never push, merge or deploy. Every command ends in `| tail -30`. Anchors are quoted from the tip: if one is not found verbatim, STOP and report.

## Open questions (ANSWERED by the owner 2026-11-17: "No python only go, do the recommended")

1. **Go first.** ANSWERED: no Python exception. The fix ships in Go only, after the port briefs 1842 and 1843. Recorded in decisions.
2. **Approach.** ANSWERED: phone "Show more" appends the next page's rows in place; the plain `rel="next"` link works without JavaScript; desktop Prev/Next unchanged. The fallback "show Previous on phones" is not used.

## 1. Objective

On a 390 px phone the Stays "Show more" link replaces the list with page N+1 and there is no way back (the Prev/Next pager is `ph-hide`). Make it append the next rows in place, keep the plain link working without JavaScript, keep desktop Prev/Next unchanged, and prove the filter links keep their state.

## 2. Context

Hard rules: 6 (no-JS must work), 7 (browser tests, 0 skipped, 390 px screenshot), 9 (copy), 10 (UX gate, design-system checklist), 11 (Go first). Read [design-system](../design/design-system.md) first, then `grep -n '^## ' docs/design/MASTER.md` for the list section only. Python serves this page only until the owner switch of 1843 is done; this brief assumes `/reservations` is in `UBYHOST_GO_PATHS`. The JS file below is a static asset served to Go and Python pages alike; the handler is inert on any page without `[data-stays-more]`, so no Python file changes (go-first: no `App/app/*.py` or template edit).

## 3. Files

- `go/internal/web/stays/templates/stays_list.tmpl` (from 1843): the `stays-pager ph-hide` nav and `<div class="list stays-more"><a class="link" href=".." rel="next">`; add `data-stays-more` to that wrapper div. Find the row container with `grep -n 'stays-list\|for .*Rows' go/internal/web/stays/templates/stays_list.tmpl | tail -30`.
- `go/internal/web/stays/view.go` (from 1842): `pageURL`, chips, `NextURL`; fix only what the Step 1 tests prove wrong.
- `App/static` JS: `App/app/static/host.js` (loaded by `go/internal/hostweb/layout/shell.html` line 50 as `/static/host.js?v=...`). Add the handler there; bump its `?v=` in `shell.html` and in `go/internal/hostweb/layout/testdata/*.html` goldens only if `go test ./internal/hostweb/layout/...` fails on the version, and run `App/tests/test_static_versions.py`.
- New `go/internal/web/stays/filters_test.go` (Step 1) and `App/tests/test_1840_stays_more_browser.py` (Step 3, Playwright runs against the Go-served page).

## 4. Steps

0. Anchors and size check. `grep -nF 'stays-more' go/internal/web/stays/templates/stays_list.tmpl | tail -30`; `grep -n 'func.*pageURL' go/internal/web/stays/view.go | tail -30`; `grep -n 'stays' App/app/static/host.js | head -20`. Expect the first two to hit once; if 1843 is not merged STOP.
1. Filter audit in Go. In `filters_test.go` seed RESERVATION page size + 1 stays (page size is 5, so 6) and assert on the rendered HTML: (a) each range chip href keeps `apartment` and `status`, has no `page`, `from`, `to`; (b) the failed chip (`report=failed`) has no `range` key and is the only current chip for `?report=failed`; (c) `?status=cancelled` round-trips through chips and `data-filter-summary`; (d) `NextURL` on page 1 has every filter param and `page=2`; on `?page=2&range=upcoming&apartment=1` the Upcoming chip is current and chip hrefs carry no `page`. Run `cd go && go test ./internal/web/stays/... 2>&1 | tail -30`. Fix failures in `view.go` or the template with the smallest change and report each fix.
2. Append on phones (progressive enhancement). Keep the `<a class="link" rel="next">` as is; add `data-stays-more` to its wrapper. In `host.js` add one handler: on click of `[data-stays-more] a` (only when `matchMedia('(max-width: 640px)')` matches, plain left click, no modifier keys): `preventDefault`, `fetch(href, {headers:{'X-Requested-With':'fetch'}, credentials:'same-origin'})`, parse with `DOMParser`, move every row node from the fetched row container into the live container, replace the live `[data-stays-more]` with the fetched one (or remove it when absent), update `[data-filter-summary]` text, then `history.replaceState(history.state, '', url)` so Back leaves Stays. Skip a leading "EARLIER" divider when it duplicates the live one. On any error or non-200: `location.href = href`. Set `aria-busy` on the wrapper while loading. No new visible string.
3. Browser test `App/tests/test_1840_stays_more_browser.py`: copy the Playwright setup from `test_0766_phone_stays_browser.py`; at 390 px seed 6 stays, click Show more, assert 6 rows, link gone, URL has `page=2`, no horizontal scroll; with JS disabled the click goes to `?page=2` and a back path exists; from `?apartment=<id>&range=upcoming` all appended rows belong to that apartment.
4. Copy: no new strings. If one is unavoidable add it to `go/internal/web/stays/i18n.json` in en, cs, vi and run the Go i18n key test of the package.

## 5. Do not touch

Any `App/app/*.py` or `App/app/templates/*`; other pages; global Turbo behaviour; any new dependency; unrelated tests.

## 6. Commands (test-map rows; never the full suite)

From `go/`: `go test ./internal/web/stays/... ./internal/hostweb/... 2>&1 | tail -30`. From `App/`, 0 skipped: `.venv/bin/python -m pytest tests/test_1840_stays_more_browser.py tests/test_0766_phone_stays_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`. Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- Phone: Show more appends in place, URL becomes `?page=2` via replaceState, Back leaves Stays. No-JS: plain link works. Desktop pager unchanged.
- Chip, failed-chip, archive-chip, reset and Show more keep `apartment`/`status`; chips drop `page`, `from`, `to`; active chip right on page 2.
- `git diff --stat` shows no `App/app/*.py` or `App/app/templates` file.
- PR body: one 390 px screenshot per changed page, 390/768/1280 screenshots opened and one line per page (rule 10), design-system checklist ticked, test tails with 0 skipped.
- Owner steps: none beyond the 1843 switch (merge with `scripts/merge-pr-on-green.sh`).

## 8. Stop and ask

Stop at 30 tool calls or 60k tokens, if a step needs a file not named in section 3, or if 1843 is not merged and switched on.

## 9. Report

What changed; the last 30 lines of each test output; 390, 768 and 1280 px screenshots for each touched page; the design-system checklist ticked.
