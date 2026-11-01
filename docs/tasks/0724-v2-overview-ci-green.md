# 0724: Overview phone spacing done right, CI green
Status: todo
Depends on: 0723 | Branch: task/0723-v2-overview-polish (worktree /tmp/wt0723, continue there)
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Phone Overview (390 px) spacing matches the phone mockup without negative margins, and the CI failures on 15df9de are fixed. One commit per step.

## 2. Context (orchestrator, decided)
- Phone mockup rhythm (`docs/design/mockup/ubyhost-phone-v1.html`): `h2.sec{margin:28px 20px 12px}`, cards 12 px apart, `.hs{padding:4px 20px 16px}`. In the app the phone Overview column `body.v2 .ui-body:has(> .ov-month)` is a flex column (0722, for the month-line order), so child margins add up instead of collapsing. Decision: below 1024 px, zero the vertical margins of the column's direct children and let `h2.sec` margins (28/12) and the cards' 12 px give the rhythm.
- `.hs .pill` in `missing_ok` (v2_mockup.py line 110) stays as is; step 4 adds a separate BOX_OVERRIDES entry.
- WebKit is not installed locally: run browser tests with chromium only where the test is parametrised by browser; say so in the report.

## 3. Steps
1. Measure (no commit). Write `/tmp/measure0724.py` that reuses the fixtures of `tests/test_0710_v2_mockup_match_browser.py` (simplest: add a temporary test function at the end of that file, run it with `-k measure -s`, then `git checkout -- tests/test_0710_v2_mockup_match_browser.py`). At 390 px on `/`, print for every direct child of `.ui-body`, of `#needs-action` and of the today section, plus `h2.sec` and `.hs`: selector, top, bottom, margin-top, margin-bottom, padding-top, padding-bottom. Keep the output for the report ("before").
2. Spacing. In `App/app/static/app2.css` replace the line
   `@media (max-width:1023px){body.v2 .ov-head{margin-bottom:-22px}body.v2 details.needs-you-more.ov-section{margin-bottom:0}}`
   with
   `@media (max-width:1023px){body.v2 .ui-body:has(> .ov-month) > *{margin-top:0;margin-bottom:0}body.v2 #needs-action > .todo > .card.need{margin-bottom:12px}body.v2 details.needs-you-more{margin:0}}`
   Then re-run step 1's measurement. Targets: date line to "What needs you" heading 20-32 px; card to card 12 px; "Show N more" to "Today" heading 24-32 px; "Today" heading to first stay card 12-16 px. If a gap is still off, the step-1 output shows which element carries the extra margin/padding: add that element to the same media rule with margin/padding 0 (never a negative value). Remove the temporary test. Commit (app2.css only).
3. Item G, `App/tests/test_0201_tabbar_safe_area_browser.py` lines 49-51. v2 pages use `.tabs` (84 px, `--tabbar-h` in app2.css line 341), not `.ui-tabbar` (56 px). Replace `document.querySelector('.ui-tabbar')` with `document.querySelector('body.v2 .tabs') || document.querySelector('.ui-tabbar')`, and make the height checks depend on it: `expected = 84 if page.evaluate("!!document.querySelector('body.v2 .tabs')") else 56`, then `assert round(bar["h"]) == expected` and `scrollPaddingBottom == f"{expected}px"`. Apply the same replacement to any other `.ui-tabbar` query in that file's lines 45-77. If `scrollPaddingBottom` is not 84px on v2, add `@media (max-width:1023px){html:has(body.v2){scroll-padding-bottom:var(--tabbar-h)}}` to app2.css instead of loosening the test. Commit.
4. Item I, `App/tests/v2_mockup.py` BOX_OVERRIDES (line 47 on): add
   `    # the pill width follows its status label text, which differs from the mockup demo copy (0724)`
   `    ".hs .pill": {"width": None},`
   only if `box_diffs` (around line 362) skips a property whose override value is None; read that function first. If it does not, add the exact width per width instead: `".hs .pill@320": {"width": "143px"}, ".hs .pill@390": {"width": "143px"}` with the same comment. Commit.
5. Item H, `App/tests/test_host_quiet_dashboard_browser.py` lines 359-365. Replace the cap logic with:
   `cap = 2 if width < 1024 else 4  # 0722: phone shows two needs-you cards`
   `shown = page.locator("#needs-action > .todo > .card.need").evaluate_all("nodes => nodes.filter(n => n.offsetParent).length")`
   `assert shown == min(total, cap), (label, shown, total)`
   `assert more.count() == (1 if total > cap else 0), label`
   `if total > cap: assert str(total - cap) in more.inner_text(), (label, more.inner_text())`
   (keep the existing `total` and `more` lines; keep indentation). Commit.
6. Item J, `App/tests/test_motion_browser.py` lines 71-76 and 139-140: the v2 Overview fold-out is `details.ov-how` with body class to be checked in `App/app/templates/dashboard.html` (grep `ov-how`). Replace `details.ui-how` with `details.ui-how, details.ov-how` and `.ui-how-body` with `.ui-how-body, <the ov-how body selector>`. If the `::details-content` overflow or animation assertion fails, add `details.ov-how` next to `details.ui-how` in the "v2 shared: motion" block of app2.css (grep `v2 shared: motion`). Commit.
7. Item K, `App/tests/test_dashboard_calendar_browser.py:353`: `.cal-day-number` is 43 px wide, asserted >= 43.9 at phone widths. Measure `.cal-day-number` width at 360 on this branch and on origin/main (`git stash` not allowed; use `git show origin/main:App/app/static/app2.css` only to compare rules). If v2's 20 px main padding is the cause, add a phone rule in app2.css that gives the calendar the old width (e.g. `body.v2 #calendar{margin-inline:-8px}` is NOT allowed; prefer reducing `.cal-week` gap/padding below 768 px so the cell reaches 44 px). If you cannot find the cause in 4 calls, leave it and write what you measured.
8. Bump the app2.css key in `App/app/templates/base.html` to `20261101-0724`, run `.venv/bin/python tests/test_static_versions.py --write`. Screenshots: `UBYHOST_SHOTS_V2=1 ... pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots`, copy overview 390/768/1280 into `docs/tasks/screenshots-0724/`, Read the 390 one. Restore other PNGs. Write `docs/tasks/0724-report.md` (before/after gaps from steps 1-2, each item, test tails), set Status: done. Commit.

## 4. Do not touch
`app.js`, routes, templates (except reading), other pages.

## 5. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`)
After each step, only that step's test file: `.venv/bin/python -m pytest <file> -q --tb=line -rs 2>&1 | tail -15`. Final: all five files plus `tests/test_0710_v2_mockup_match_browser.py tests/test_needs_you_0240.py tests/test_static_versions.py`. Ruff: `.venv/bin/python -m ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -3`. Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 6. Acceptance
No negative margins; 390 gaps within the step-2 targets; listed tests pass (WebKit-only cases excepted and named).

## 7. Report
`docs/tasks/0724-report.md`.

## 8. Stop and ask
Stop on an item (not the whole brief) if its anchor is missing; note it and continue with the next step.
