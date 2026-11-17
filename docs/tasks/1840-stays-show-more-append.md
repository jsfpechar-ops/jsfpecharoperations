# 1840: Stays on a phone: "Show more" appends rows, filters round-trip

Status: todo (blocked on open question 1)
Depends on: none | Base commit: tip of main | Branch: task/1840-stays-show-more-append
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k; hand over per [workflow](../context/workflow.md#when-haiku-reaches-the-cap))
Tier: B (host UI, no data change)
Pairs with 1841 (Turbo back cache). 1840 goes first.

> **One PR mode.** Commit each step as `1840 step k`. Never push, merge or deploy. Every command ends in `| tail -30`. Anchors are quoted from the tip: if one is not found verbatim, STOP and report.

## Open questions (orchestrator answers before `Status: ready`)

1. **Go first.** `GET /reservations` is served by Python only (go-full-move-remaining.md row 47: 20 Stays routes, 0 in Go; `grep -rn '/reservations' go --include=*.go` finds only palette/mail strings). A port brief must come first by [go-first](../context/go-first.md), but this is a UX bug, not a filing, security or data-loss bug, so none of the three Python exceptions applies. Recommended: owner approves one-off Python exception for this brief, recorded as a decision line. Answer: ____
2. **Approach.** Recommended: append (Step 2). Fallback if Step 2 exceeds 20 tool calls: Step 2b only (show Previous on phones). Answer: ____

## 1. Objective

On a 390 px phone the Stays "Show more" link replaces the list with page N+1 and there is no way back (the Prev/Next pager is `ph-hide`). Make it append the next rows in place, keep the plain link working without JavaScript, keep desktop Prev/Next unchanged, and prove the filter links keep their state.

## 2. Context

Hard rules: 6 (no-JS must work), 7 (browser tests, 0 skipped, 390 px screenshot), 9 (copy), 10 (UX gate, design-system checklist). Read [design-system](../design/design-system.md) first, then `grep -n '^## ' docs/design/MASTER.md` for the list section only.

## 3. Files

Files (Python is the only server for this page; see question 1):
- `App/app/templates/reservations.html` ~270-276: the `stays-pager ph-hide` nav and `<div class="list stays-more"><a class="link" href="{{ next_page_url }}" rel="next">`. The row loop sits above; find its container with `grep -n 'for item in rows' App/app/templates/reservations.html`.
- `App/app/routes/admin.py` ~3852: `query_params = [... if key != "page"]` and `page_url(number)` -> `"/reservations?" + urlencode([*query_params, ("page", number)])`. `previous_page_url`, `next_page_url` are passed to the template.
- Chips: `reservations.html` ~91-96 build hrefs `/reservations?range=X&status=<status>&apartment=<id>`; failed chip `?report=failed&status=..&apartment=..`; archive chip `range=archive`. Reset link ~102. Filter panel form ~108-135.
- JS: `grep -n 'data-stays\|stays' App/app/static/app.js | head -20` to find the existing Stays script; add the handler there, not a new file.

## 4. Steps

0. Anchors and size check. `grep -nF 'class="list stays-more"' App/app/templates/reservations.html | tail -30`; `grep -nF 'def page_url' App/app/routes/admin.py | tail -30`. Expect one hit each.
1. Filter audit (read-only, write findings in the PR). Add `App/tests/test_1840_stays_filters.py` (file name from this brief) using the client fixtures of `App/tests/test_0523_stays_list.py` (copy its setup). With more than one page of stays (RESERVATION_PAGE_SIZE + 1 rows), assert on the rendered HTML:
   a. Each range chip href keeps `apartment` and `status` and has no `page`, `from`, `to`.
   b. The failed chip (`report=failed`) has no `range` key, is the only chip marked current for `?report=failed`, and the list returns 200 with `range` absent.
   c. `?status=archived` (use a real status value from the route) round-trips through the chips and the summary line (`data-filter-summary`) names the same filter.
   d. `next_page_url` on page 1 contains every filter param and `page=2`; on `?page=2&range=upcoming&apartment=1` the Upcoming chip is current and the chip hrefs carry no `page`.
   Run: `cd App && .venv/bin/python -m pytest tests/test_1840_stays_filters.py -q --tb=short -x 2>&1 | tail -30`. Fix any failing check in `reservations.html` or `admin.py` with the smallest change; report each fix.
2. Append on phones (progressive enhancement). In `reservations.html` keep the `<a class="link" rel="next">` exactly as is and add `data-stays-more` to its wrapper div. In the Stays JS add one handler: on click of `[data-stays-more] a` (only when `matchMedia('(max-width: 640px)')` matches, plain left click, no modifier keys): `preventDefault`, `fetch(href, {headers:{'X-Requested-With':'fetch'}, credentials:'same-origin'})`, parse with `DOMParser`, move every row node from the fetched row container into the live container, replace the live `[data-stays-more]` with the fetched one (or remove it when absent), update `[data-filter-summary]` text. Then `history.replaceState(history.state, '', url)` so Back leaves Stays instead of stepping through pages. Skip a leading "EARLIER" divider when it duplicates the live one. On any error or non-200: `location.href = href` (the plain link). Set `aria-busy` on the wrapper while loading. No new visible string.
   Expected: no-JS click still loads `?page=2`; with JS the row count grows by the page size and the URL shows `page=2`.
2b. Fallback only (if Step 2 is too large): remove `ph-hide` from the Previous link so it shows on phones; add `stays-pager-phone` CSS only if the layout test fails. Say in the PR that 2b replaced 2.
3. Browser test in `App/tests/test_1840_stays_more_browser.py`: copy the Playwright setup from `test_0766_phone_stays_browser.py`; at 390 px seed PAGE_SIZE+1 stays, click Show more, assert row count = PAGE_SIZE+1, link gone, URL has `page=2`, no horizontal scroll; with JS disabled assert the click navigates to `?page=2` and shows Previous or a working back path. Assert the filters survive: start from `?apartment=<id>&range=upcoming`, click Show more, rows all belong to that apartment.
4. Copy: no new strings. If one is unavoidable add it to `App/app/host_i18n.py` in en, cs and vi, run `test_*_i18n.py`.

## 5. Do not touch

Other pages than Stays (`/reservations`); global Turbo behaviour outside the stated scope; any new dependency; unrelated tests.

## 6. Commands (test-map rows; never the full suite)

From `App/`, each ending `2>&1 | tail -30`, 0 skipped:
`.venv/bin/python -m pytest tests/test_1840_stays_filters.py tests/test_1840_stays_more_browser.py tests/test_0523_stays_list.py tests/test_0766_phone_stays_browser.py tests/test_1100_stays_in_house_first.py tests/test_archive_stays_on_page.py tests/test_design_stays.py -q --tb=short -x`
Host pages row: `tests/test_host_*.py tests/test_host_geometry.py`. Any host template/JS row: `tests/test_design_guardrails_browser.py`. UX gate: `tests/test_layout_lint_browser.py` green. Copy row if strings changed. Static files row: `tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py` (app.js changed).
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- Phone: Show more appends in place, URL becomes `?page=2` via replaceState, Back leaves Stays. No-JS: plain link works. Desktop pager unchanged.
- Chip, failed-chip, archive-chip, reset and Show more keep `apartment`/`status`; chips drop `page`, `from`, `to`; active chip right on page 2.
- PR body has: one 390 px screenshot per changed page, 390/768/1280 screenshots opened and one line per page on what you saw (rule 10), the design-system checklist ticked, decision line for question 1, test output tails with 0 skipped.
- Owner steps: none (merge with `scripts/merge-pr-on-green.sh`; Python path deploys on green; a Go switch is not involved).

## 8. Stop and ask

Stop at 30 tool calls or 60k tokens, if a step needs a file not named in section 3, or if the open questions above are unanswered.

## 9. Report

What changed; the last 30 lines of each test output; 390, 768 and 1280 px screenshots for each touched page; the design-system checklist ticked.
