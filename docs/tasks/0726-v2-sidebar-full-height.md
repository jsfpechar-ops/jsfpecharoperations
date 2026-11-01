# 0726: v2 sidebar background reaches the bottom of long pages
Status: todo
Depends on: 0725 | Branch: task/0726-v2-sidebar-full-height (worktree /tmp/wt0726)
Executor: Haiku 5.5 | Fits one session: 12 tool calls

## 1. Objective
On v2 pages longer than the screen (e.g. a long property page), the white sidebar background stops after one screen height. Make it reach the bottom of the page while the sidebar stays sticky.

## 2. Context
Found by the properties thread. `App/app/static/app2.css` line 6: `.side{...position:sticky;top:0;height:100vh...}` inside `.app{display:flex;min-height:100vh}` (line 5). The sticky 100vh box is correct for the nav; only the colour column under it is missing. Decision: paint the column on `.app` at desktop widths, so nothing about the sticky nav changes.

## 3. Files
`App/app/static/app2.css`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, report `docs/tasks/0726-report.md`.

## 4. Steps
1. Add after line 6 of app2.css:
   `@media (min-width:1024px){.app{background:linear-gradient(90deg,var(--side) 0 219px,var(--line) 219px 220px,transparent 220px)}}`
   (219/220 px matches the 220 px sidebar width and its 1 px right border.)
2. Check in a browser at 1280 x 800 on a long v2 page: write a temporary test (or reuse the fixture in `tests/test_0710_v2_mockup_match_browser.py`) that opens `/` and sets `document.querySelector('.main').style.minHeight='3000px'`, scrolls to the bottom, and asserts the pixel colour at x=100, y=780 of a screenshot equals the sidebar colour (`getComputedStyle(document.querySelector('.side')).backgroundColor`). Run it, then delete the temporary test.
3. Bump the app2.css key in base.html to `20261101-0726` and run `.venv/bin/python tests/test_static_versions.py --write` from App/.
4. Commit with explicit paths.

## 5. Do not touch
Anything else; the phone layout (below 1024 px the sidebar is hidden).

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`)
`.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py -q --tb=line 2>&1 | tail -8`; repo root `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
Sidebar colour column reaches the page bottom at 1280; listed tests and lints pass.

## 8. Stop and ask
Stop if `--side` or `--line` is undefined in app2.css/tokens.css.

## 9. Report
`docs/tasks/0726-report.md`: change, the pixel check result, test tails. Restore any regenerated PNGs outside your task before committing (`git restore --pathspec-from-file`).
