# 0188: Sidebar toggle, collapsed account menu, tab motion

Status: blocked
Depends on: none | Base commit: 1ae7c9d | Branch: claude/project-thread-3xqb0b
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Three host-app bugs from the owner: (1) a collapsed sidebar cannot be expanded, (2) the collapsed account/Settings menu is clipped by the rail, (3) on Invoices, "Invoice settings" slides while "Stay fees" switches instantly.

## 2. Context

- Bug 1: `App/app/templates/_shell_sidebar.html` has one button `[data-sidebar-collapse]`. `initNavigation()` in `App/app/static/app.js` (~line 826) only calls `setCollapsed(true)`. There is no expand element in the v2 shell. Fix: the button toggles with `setCollapsed(!document.body.classList.contains("sidebar-collapsed"))`, keeps `aria-expanded` in sync, and switches `aria-label` between `a11y.hide_menu` and `a11y.show_menu` (add `a11y.show_menu` to both language files next to `a11y.hide_menu`; set via a `data-label-hide` / `data-label-show` pair on the button). It stays visible and usable in the collapsed rail (the brand column stacks it under the logo).
- Bug 2: `.ui-sidebar` in `host2.css` has `overflow-y: auto`, which also clips x, so `.host-account-menu` (220 px, from host.css 228) is cut by the 72 px rail. Fix in `host2.css` only: when collapsed (and in the 1024-1279 px auto-collapsed range) the menu escapes the rail (`overflow: visible` on the sidebar there, or `position: fixed` for the menu). The menu shows whole, labels not truncated, with a visible border, above content (z-index), inside the viewport at 1280 and 2000 px and on short windows.
- Bug 3: "Invoice settings" (route `/entities`, template `entities.html`) appears to slide. Reproduce first with Playwright (see `App/tests/test_design_shell_browser.py` for app launch). Sample main content and tab strip transforms, scrollLeft and opacity every 30 ms for 600 ms per tab. Suspects: `skeleton.js` / `.page-skeleton` swap, `.ui-tabs` overflow-x scrolling, a CSS transition or animation on the entities page, `lane-enter`, scroll restoration. Remove the cause so all tabs switch instantly. Any remaining motion on the page collapses under `prefers-reduced-motion: reduce`. Do not remove the skeleton for slow navigations unless it is the cause; if it is, change only its timing so a fast tab switch never shows it. State the cause in the report.
- Design: `docs/design/MASTER.md` (shell section). Light mode only.

## 3. Files

- `App/app/templates/_shell_sidebar.html`
- `App/app/static/app.js`
- `App/app/static/host2.css`
- `App/app/templates/base.html` (`?v=` key)
- `App/app/templates/entities.html` (only if it is the motion cause)
- `App/app/static/skeleton.js` (only if it is the motion cause)
- language files holding `a11y.hide_menu` (add `a11y.show_menu`)
- `App/tests/test_design_shell_browser.py`, `App/tests/static_versions.json`

## 4. Steps

1. Reproduce bug 3 with the sampling probe; record the cause.
2. Fix bug 1 (toggle, aria, label pair, language keys). Commit `NNNN step 1` style per step.
3. Fix bug 2 in `host2.css` only. Bump the `host2.css` `?v=` key in `base.html` and `App/tests/static_versions.json`.
4. Fix bug 3 at the cause. Add reduced-motion guard.
5. Add browser tests: collapse then expand via the same button; with the rail collapsed the account menu is fully inside the viewport and not clipped (scrollWidth vs clientWidth); tab switch shows no transform or scroll movement.
6. Screenshots (see section 9).

## 5. Do not touch

- No borderless look, no raw colors, tokens only. No PR (owner's instruction). No push to `main`.
- Do not change other pages, the UbyPort code, or the file-input focus rule added in 0188 step 6.

## 6. Commands

- `cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_design_shell.py tests/test_static_versions.py tests/test_a11y_guard_browser.py -q --tb=short -x -rs 2>&1 | tail -30`
- `python3 scripts/context_lint.py | tail -30`
- 0 skipped in the browser tests.

## 7. Acceptance

- Collapsed rail expands and collapses with the same button; `aria-expanded` and the label follow.
- Account menu fully inside the viewport at 1280 and 2000 px and short windows, labels not clipped.
- All Invoices tabs switch with no transform, scrollLeft or opacity movement in the 600 ms sample.
- Reduced motion collapses remaining motion.
- Tests in section 6 pass with 0 skipped; `context_lint` passes.

## 8. Stop and ask

- If a step's anchor is not found (`grep -nF` returns nothing), STOP.
- If the motion cause is outside the files in section 3, STOP and report.
- If two fixes are possible for the menu escape, STOP and ask the owner.

## 9. Report

- Screenshots to `/mnt/project-files/design-reset/checkpoint-4-shell-fixes/`: Invoices page, Stay fees and Invoice settings tabs, and the open account menu at 390, 1280 and 2000 px (sidebar open and collapsed; 390 px collapsed once), demo data, plus one reload with a stale cache.
- Report in under 15 lines: cause of bug 3, files changed, test output tail, screenshot paths.
