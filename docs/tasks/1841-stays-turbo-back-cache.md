# 1841: Back to Stays restores from the Turbo cache

Status: todo (blocked on 1840 merged and open question 1)
Depends on: 1840 | Base commit: tip after 1840 | Branch: task/1841-stays-turbo-back-cache
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k)
Tier: B (host UI behaviour; stale-data risk, orchestrator reads the diff)

> **One PR mode.** Commit each step as `1841 step k`. Never push, merge or deploy. Every command ends in `| tail -30`. Anchors quoted from the tip: if one is missing, STOP.

## Open questions (orchestrator answers before `Status: ready`)

1. **Go first.** Same as 1840 question 1 (page and base.html are Python-only). Recommended: same one-off exception. Answer: ____
2. **Scope.** Recommended: Stays list only. A global change is allowed only if Step 1 finds no dependency on no-cache. Answer: ____

## 1. Objective

Browser back, swipe and backspace to `/reservations` reload and re-render the whole page and lose the scroll position, because `base.html` line 44 sets `<meta name="turbo-cache-control" content="no-cache">` globally. Let Turbo restore Stays from its snapshot cache (instant, scroll kept) without showing stale state.

## 2. Context

`App/app/templates/base.html` line 44: Turbo 8.0.13 (`/static/vendor/turbo-8.0.13.js`), `turbo-cache-control` = `no-cache`, `view-transition same-origin`, `turbo-prefetch true`. Turbo sets `history.scrollRestoration = "manual"` and restores scroll only from a cached snapshot (vendor file line ~3713: `cacheControlValue != "no-cache"`). `App/app/static/skeleton.js:114` and `App/app/static/app.js:907` (healInert) and `:1972` have `pageshow` handlers that heal flash and inert state; `turbo:before-cache` / `turbo:load` are the Turbo equivalents. Meta changes made by a page override the layout default (Turbo reads the meta of the page being left).

Risks to name in the PR: a cached snapshot can show flashes, a send-state badge, "Send all ready" count or a stay status that changed after leaving. Mitigation (Step 3): clear transient nodes on `turbo:before-cache` and revalidate in the background.

## 3. Steps

1. Dependency scan (read-only). `grep -rn 'turbo-cache-control\|no-cache\|data-turbo-cache\|turbo:before-cache\|turbo:load\|turbo:render\|pageshow' App/app/templates App/app/static/*.js 2>&1 | grep -v vendor | tail -30`. List in the PR every place that assumes a fresh page after Back (flash banners, `inert`, skeleton overlay, forms with CSRF tokens, `data-saved-views`, `initUnsavedDialog` at app.js ~2640). If any item cannot be healed in Step 3, STOP and report: do not change the cache.
2. Make the meta overridable: in `base.html` line 44 keep `no-cache` as the default but wrap it so a page can set its own: `<meta name="turbo-cache-control" content="{{ turbo_cache_control | default('no-cache') }}">`. Do not touch other attributes of line 44.
3. In `App/app/templates/reservations.html` pass the value by a `{% set turbo_cache_control = 'cache' %}` placed before `{% extends %}` output is rendered (use the same mechanism other templates use to set `show_nav`; `grep -n 'show_nav' App/app/templates/*.html | tail -30`). In the Stays JS add: on `turbo:before-cache` remove `[data-flash]`/flash banners and the skeleton overlay and reset `aria-busy`; on `turbo:load` and `pageshow` re-run the same heal as app.js:907 and, if the snapshot is older than 60 s (store `Date.now()` on `turbo:load` in a `data-loaded-at` attribute), call `Turbo.visit(location.href, {action:'replace'})` to refresh in the background.
4. Browser test `App/tests/test_1841_stays_back_cache_browser.py` (setup from `test_0766_phone_stays_browser.py`, 390 px): open Stays, scroll down 600 px, click a stay, `page.go_back()`, assert scroll Y is within 50 px of 600 and no network request for `/reservations` full document was needed within 1 s (or the page has a `data-turbo-preview`-free restore); assert no flash banner and no inert nodes. Second case: change a stay status in another request, go back, wait 2 s, assert the new status shows.

## 4. Tests (test-map rows; 0 skipped)

From `App/`, `2>&1 | tail -30`: `.venv/bin/python -m pytest tests/test_1841_stays_back_cache_browser.py tests/test_0766_phone_stays_browser.py tests/test_0523_stays_list.py tests/test_1840_stays_more_browser.py -q --tb=short -x`; host pages row `tests/test_host_*.py tests/test_host_geometry.py`; `tests/test_design_guardrails_browser.py`; `tests/test_layout_lint_browser.py` green; static row `tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py`. Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 5. Acceptance

- Back to Stays keeps scroll and is instant; every other page still uses no-cache (grep shows only `reservations.html` sets `cache`).
- No new copy (rule 9); if a string is unavoidable it is in `host_i18n.py` for en, cs, vi.
- PR body: Step 1 list, stale-data note, 390/768/1280 screenshots opened with one line per page (rule 10), design-system checklist ticked, test tails with 0 skipped.
- Owner steps: none.
