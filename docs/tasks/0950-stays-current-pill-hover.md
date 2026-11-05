# 0950: Stays filter pill: the current pill keeps its dark fill and white text on hover and after a tap
Status: todo
Depends on: none | Branch: new branch from `main`, name `claude/0950-current-pill-hover`
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens. If you reach the cap, commit what passes and list exactly which step is left (one commit per step).

## 1. Objective
Owner screenshot, Stays (`/reservations`): after clicking "Upcoming & current" or "In house" the selected pill is pale grey with white, nearly invisible text. The current pill must keep the dark fill and white text in every state (hover, focus, active, sticky hover after a tap on a phone).

## 2. Context (root cause verified)
- `App/app/static/app2.css` line 1871: `body.v2 .settings-pill.is-current{background:var(--ink);color:#fff}` (specificity 0,3,1).
- `App/app/static/app2.css` line 1938: `body.v2 .stays-pills .settings-pill:hover{background:#e4e4e4}` (0,4,1) beats it. The pointer is still on the pill after the click (and `:hover` sticks after a tap on touch devices), so the current pill turns #e4e4e4 while its text stays white.
- The pill markup is the shared `App/app/templates/partials/settings_pills.html` (`<a class="settings-pill is-current">`). Users: `reservations.html:98` (wrapped in `.stays-pills`), `settings.html:464` (audit filter), `settings_archived.html:22` (archive pills). `grep -rn "settings-pill\|stays-pills" App/app --include=*.css` shows NO other hover, focus or active rule for the pill, so only the Stays page is affected; the other two pages need only a regression test. There is no `:focus`/`:active` colour rule to fix.
- Only colour in the hover rule is the literal `#e4e4e4`, kept as is (non-current hover is unchanged, owner decision).

## 3. Files
`App/app/static/app2.css`, `App/app/templates/base.html` (`?v=` bump), `App/tests/static_versions.json` (via `--write`), `App/tests/test_host_filter_panels_browser.py` (or, if it has no login/server helper, copy the helper pattern from `App/tests/test_host_button_contrast_browser.py`, `parse_rgb` and server/login setup, into a NEW file `App/tests/test_host_pill_state_browser.py`; check with `grep -n "def \|settings-pill" App/tests/test_host_filter_panels_browser.py | head -30`), `docs/design/pages/` none, screenshots `docs/tasks/screenshots-0950/`, report `docs/tasks/0950-report.md`, `docs/context/status.md`.

## 4. Steps
1. CSS. In `app2.css` change line 1938 exactly:
   - from `body.v2 .stays-pills .settings-pill:hover{background:#e4e4e4}`
   - to `body.v2 .stays-pills .settings-pill:not(.is-current):hover{background:#e4e4e4}`
   Anchor not found verbatim: stop. Bump `app2.css` `?v=` in `base.html` line 22 (now `20261104-0960m`, use the next free letter; `grep -n "app2.css" App/app/templates/base.html`). From `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5` (if not how it works, `grep -n -- '--write' tests/test_static_versions.py`). Commit `0950 step 1`.
2. Browser test (Playwright, 0 skipped: run with `export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`). Log in as a host with at least one property, as the existing browser tests do. Test A, `/reservations`: locator `.stays-pills .settings-pill.is-current`; `.hover()` it; assert computed `background-color` equals the computed `getComputedStyle(document.documentElement).getPropertyValue('--ink')` colour (read `--ink` by setting it on a probe element's `background` and reading back computed, so hex converts to rgb), and contrast between computed `color` and `background-color` >= 4.5 (WCAG relative luminance, same formula as in `test_host_button_contrast_browser.py`). Also assert a NON-current `.stays-pills .settings-pill:not(.is-current)` hovered has background `rgb(228, 228, 228)`. Then `.focus()` the current pill and repeat the colour assertion. Test B, same assertions for the current pill (no hover rule exists, so it passes already) on `/settings/archived` (`settings_archived.html`; find its URL with `grep -n "archived" App/app/routes/*.py | head`). Run at 390 and 1280. Run test A against the OLD css once (`git stash` is not allowed: just temporarily check that line 1938 reverted fails) only if you have spare calls; otherwise skip. Commit `0950 step 2`.
3. UX gate (`docs/context/workflow.md#ux-gate`). From `App/`: `export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_SHOTS_DIR=/tmp/shots`, then `.venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_static_versions.py <the test file from step 2> -q --tb=short -rs -p no:cacheprovider 2>&1 | tail -30` (0 skipped). In the new test, take a screenshot of `/reservations` with the current pill hovered at 390, 768 and 1280 into `UBYHOST_SHOTS_DIR` (only when that env var is set), open the three, copy to `docs/tasks/screenshots-0950/`. Never silence a lint finding. Commit `0950 step 3`.
4. Docs. Known-issues and decisions: no line (a one-selector bug fix). `docs/context/status.md` at most 5 lines: 0950 done. Write `docs/tasks/0950-report.md`: status, test tails (0 skipped), per-width notes (current pill dark with white text while hovered; other pills grey on hover; nothing clipped), the design-system checklist from `docs/design/design-system.md` ticked for the PR text. From the repo root `python3 scripts/context_lint.py | tail -30`; fix errors. Commit `0950 step 4`.

## 5. Do not touch
Other CSS rules, `settings_pills.html`, the pill colours, JS, other templates. No new dependency, no new personal data, no new outbound request.

## 6. Commands
Test-map row "Host pages, host templates, host CSS": `test_host_*.py` and `test_host_geometry.py`; run only the files named in steps 2-3 (plus `test_host_geometry.py` if time allows). Final: `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5`. Do not run the full suite.

## 7. Acceptance
Hovered and focused current pill on Stays has computed background equal to `--ink` and contrast >= 4.5; non-current hover is `rgb(228, 228, 228)`; the same holds for the current pill on the archive page; screenshots at 390/768/1280 show a dark current pill; listed tests pass with 0 skipped.

## 8. Stop and ask
Stop if the line 1938 anchor is not found verbatim, if the browser test cannot log in with the existing helpers, or if a lint finding appears that is not about the pill.

## 9. Report
`docs/tasks/0950-report.md` as in step 4. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push.
