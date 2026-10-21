# 0201: Phone tab bar clears rounded screen corners and the home indicator

Status: done
Depends on: 0200 | Base commit: e5692a4 | Branch: claude/project-thread-xo8dql
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On a real phone the bottom tab bar sits flush with the screen edge, so the rounded corners and the iPhone home indicator cover part of it. host2.css already pads the bar with `env(safe-area-inset-bottom)`, but iOS reports every safe-area inset as 0 unless the viewport meta has `viewport-fit=cover`. Turn the insets on, give the bar a small minimum bottom gap for phones that report 0 (Android with rounded corners), and keep the left/right edges clear in landscape.

## 2. Context

- `App/app/templates/base.html` line 6: `<meta name="viewport" content="width=device-width, initial-scale=1">`. base.html serves the host workspace (and any page that extends it).
- `App/app/static/host2.css`, `@media (max-width: 1023px)` blocks: line 107 (`.ui-sticky-actions` bottom), 117 (`.ui-menu-panel` padding), 306 (`scroll-padding-bottom`), 307 (`.wrap.with-sidebar` padding), 309 (`.ui-topbar`), 310 (`.ui-tabbar`). `--tabbar-h: 56px` is in tokens.css.
- Rules: one `?v=` bump per changed CSS file, then `.venv/bin/python tests/test_static_versions.py --write`. Light mode only. No template changes except the meta.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/base.html | meta gets `, viewport-fit=cover`; host2.css key -> `?v=20261021-0201` |
| App/app/static/host2.css | append one `/* 0201 */` block at the end |
| App/tests/static_versions.json | regenerate |
| App/tests/test_0201_tabbar_safe_area_browser.py | new test |

## 4. Steps

1. Edit the meta in base.html only (not guest, auth, landing, legal: they have no fixed bottom bar).
2. Append to host2.css:
   ```css
   /* 0201: with viewport-fit=cover the phone shell keeps clear of rounded corners, the notch and the home indicator. */
   .host-workspace { --tabbar-safe: max(var(--space-2), env(safe-area-inset-bottom)); }
   @media (max-width: 1023px) {
     html:has(.host-workspace) { scroll-padding-bottom: calc(var(--tabbar-h) + var(--tabbar-safe)); }
     .host-workspace .ui-tabbar { height: calc(var(--tabbar-h) + var(--tabbar-safe)); padding: 0 env(safe-area-inset-right) var(--tabbar-safe) env(safe-area-inset-left); }
     .host-workspace .wrap.with-sidebar, body.host-workspace.sidebar-collapsed .wrap.with-sidebar { padding-left: calc(var(--space-4) + env(safe-area-inset-left)); padding-right: calc(var(--space-4) + env(safe-area-inset-right)); padding-bottom: calc(var(--tabbar-h) + var(--tabbar-safe) + var(--space-6)); }
     .host-workspace .ui-topbar { padding-left: calc(var(--space-4) + env(safe-area-inset-left)); padding-right: calc(var(--space-2) + env(safe-area-inset-right)); }
     .host-workspace .ui-sticky-actions { bottom: calc(var(--tabbar-h) + var(--tabbar-safe)); }
   }
   ```
   Check `--space-2` is 8px in tokens.css. If `.ui-topbar` is `position: sticky/fixed` at the top, also add `padding-top: env(safe-area-inset-top)` and matching height (`calc(var(--topbar-h) + env(safe-area-inset-top))`) only if it is fixed; report what you found.
3. Bump the key, regenerate the manifest.
4. New test (copy fixtures from `tests/test_design_shell_browser.py` or `tests/test_design_guardrails_browser.py`): at 390x844 and 360x780, en and cs, on `/dashboard` and one stay page:
   - the viewport meta content contains `viewport-fit=cover`;
   - the tab bar bottom == innerHeight (±1), height == 64 (56 + 8 minimum, since Chromium reports insets as 0), every tab link's bottom <= bar bottom - 8;
   - the last main content element's bottom, after scrolling to the end, is above the tab bar top;
   - `document.documentElement.scrollWidth <= innerWidth`;
   - at 1280 the tab bar is not displayed.
   Save 390 screenshots (en, cs) of `/dashboard` to `/mnt/project-files/design-reset/checkpoint-6/mobile/tabbar/` (`mkdir -p`, trailing slash).

## 5. Do not touch

Other templates, Python, copy, other CSS files. No git commit/stash/checkout/reset/clean.

## 6. Commands

From `App/` with `export UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome UBYHOST_REQUIRE_BROWSER=1`:
`.venv/bin/python -m pytest tests/test_0201_tabbar_safe_area_browser.py tests/test_static_versions.py tests/test_design_shell_browser.py tests/test_shell_lane_browser.py tests/test_design_guardrails_browser.py -q --tb=line -rfs 2>&1 | grep -E "FAILED|passed|failed|^E " | tail -10`

## 7. Acceptance

- [ ] Meta has `viewport-fit=cover`; bar measures as in step 4 at 360/390 en+cs.
- [ ] Tests above pass, 0 skipped.

## 8. Stop and ask

If a listed test fails for a reason other than the 56 -> 64 px bar height, stop and report. If a test asserts the old 56 px bar height, update that assertion and say so. Do not commit.

## 9. Report

[0201-report.md](0201-report.md)

Follow-up: 8 px minimum dropped (bar is 56 px + the phone's inset). CI showed the wizard's Add calendar button under the bar: `--tabbar-safe` was set on body but read on html, so scroll-padding-bottom fell to 0. Now set on :root.
