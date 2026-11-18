# 1858: Back to Stays restores from the Turbo cache (Go)

Status: todo (depends on 1857 merged; 1857 depends on 1856, 1855)
Depends on: 1857 | Base commit: tip after 1857 | Branch: task/1858-stays-turbo-back-cache
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k)
Tier: B (host UI behaviour; stale-data risk, orchestrator reads the diff)
Order: 1855, 1856, 1857, 1858.

> **One PR mode.** Commit each step as `1858 step k`. Never push, merge or deploy. Every command ends in `| tail -30`. Anchors quoted from the tip: if one is missing, STOP.

## Open questions (ANSWERED by the owner 2026-11-17: "No python only go, do the recommended")

1. **Go first.** ANSWERED: no Python exception; the change lands in the Go layout and the Go Stays template only.
2. **Scope.** ANSWERED: the Stays list only, not global. Every other page keeps `no-cache`.

## 1. Objective

Browser back, swipe and backspace to `/reservations` reload and re-render the whole page and lose the scroll position, because the host layout sets `<meta name="turbo-cache-control" content="no-cache">` globally. Let Turbo restore Stays from its snapshot cache (instant, scroll kept) without showing stale state.

## 2. Context

`go/internal/hostweb/layout/shell.html` line 46: Turbo 8.0.13 (`/static/vendor/turbo-8.0.13.js`), `turbo-cache-control` = `no-cache`, `view-transition same-origin`, `turbo-prefetch true`. Turbo sets `history.scrollRestoration = "manual"` and restores scroll only from a cached snapshot (vendor file ~line 3713: `cacheControlValue != "no-cache"`). `App/app/static/skeleton.js:114` and `App/app/static/host.js` (find with `grep -n 'pageshow\|healInert' App/app/static/host.js | tail -30`) have `pageshow` handlers that heal flash and inert state; `turbo:before-cache` and `turbo:load` are the Turbo equivalents. The Python `base.html` is not changed: Python no longer serves this page once 1856 is switched on, and every other page keeps its current behaviour.

Risks to name in the PR: a cached snapshot can show flashes, a send-state badge, the "Send all ready" count or a stay status that changed after leaving. Mitigation (Step 3): clear transient nodes on `turbo:before-cache` and revalidate in the background.

## 3. Files

- `go/internal/hostweb/layout/shell.html` line 46: add a field `TurboCache` on the layout page struct (find it with `grep -rn 'WrapClass' go/internal/hostweb/layout/*.go | head`), default empty meaning `no-cache` (Step 2).
- `go/internal/web/stays/handlers.go` (from 1856): set `TurboCache: "cache"` on the Stays page (Step 3).
- `App/app/static/host.js` (static asset loaded by the Go layout line 50): `turbo:before-cache`, `turbo:load`, `pageshow` handlers, scoped to a page that has `[data-stays-more]` or `body[data-page="stays"]` (Step 3). `skeleton.js` read-only.
- `go/internal/hostweb/layout/testdata/*.html` goldens: must stay unchanged (default is `no-cache`).
- New `go/internal/web/stays/cache_test.go` and `App/tests/test_1858_stays_back_cache_browser.py` (Step 4).
- Read-only: `App/app/static/vendor/turbo-8.0.13.js`, `App/tests/test_0766_phone_stays_browser.py`.

## 4. Steps

1. Dependency scan (read-only). `grep -rn 'turbo-cache-control\|data-turbo-cache\|turbo:before-cache\|turbo:load\|turbo:render\|pageshow' go/internal/hostweb App/app/static/*.js 2>&1 | grep -v vendor | tail -30`. List in the PR every place that assumes a fresh page after Back (flash banners, `inert`, skeleton overlay, forms with CSRF tokens, saved views, the unsaved-dialog init). If any item cannot be healed in Step 3, STOP and report: do not change the cache.
2. In `shell.html` line 46 replace only the content value: `<meta name="turbo-cache-control" content="{{if .TurboCache}}{{.TurboCache}}{{else}}no-cache{{end}}">`. Do not touch other attributes of line 46. Run `cd go && go test ./internal/hostweb/... 2>&1 | tail -30`; goldens must pass unchanged.
3. In `stays/handlers.go` set `TurboCache: "cache"`. In `host.js` add: on `turbo:before-cache` remove flash banners and the skeleton overlay and reset `aria-busy`; on `turbo:load` and `pageshow` re-run the same heal as the existing `healInert`, and if the snapshot is older than 60 s (store `Date.now()` on `turbo:load` in a `data-loaded-at` attribute) call `Turbo.visit(location.href, {action:'replace'})` to refresh in the background. Bump the `host.js` `?v=` as in 1857.
4. Tests. `cache_test.go`: Stays HTML contains `content="cache"`; a second host page (e.g. customers) still contains `content="no-cache"`. Browser test `App/tests/test_1858_stays_back_cache_browser.py` (setup from `test_0766_phone_stays_browser.py`, 390 px): open Stays, scroll 600 px, click a stay, `page.go_back()`, assert scroll Y within 50 px of 600 and no flash banner and no inert nodes. Second case: change a stay status in another request, go back, wait 2 s, assert the new status shows.

## 5. Do not touch

Any `App/app/*.py` or `App/app/templates/*`; other pages (they keep `no-cache`); the vendor Turbo file; any new dependency; unrelated tests.

## 6. Commands (test-map rows; 0 skipped)

From `go/`: `go test ./internal/hostweb/... ./internal/web/stays/... 2>&1 | tail -30`. From `App/`: `.venv/bin/python -m pytest tests/test_1858_stays_back_cache_browser.py tests/test_0766_phone_stays_browser.py tests/test_1857_stays_more_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_layout_lint_browser.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py -q --tb=short -x 2>&1 | tail -30`. Root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- Back to Stays keeps scroll and is instant; every other page still uses no-cache (`grep -rn 'TurboCache' go | tail -30` shows only the layout and the Stays handler).
- No new copy (rule 9).
- PR body: Step 1 list, stale-data note, 390/768/1280 screenshots opened with one line per page (rule 10), design-system checklist ticked, test tails with 0 skipped.
- Owner steps: none beyond the 1856 switch.

## 8. Stop and ask

Stop at 30 tool calls or 60k tokens, if a step needs a file not named in section 3, or if 1857 is not merged.

## 9. Report

What changed; the last 30 lines of each test output; 390, 768 and 1280 px screenshots for each touched page; the design-system checklist ticked.
