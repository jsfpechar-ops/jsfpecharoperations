# 0725: finish 0724 (motion test, calendar cell, screenshots, report)
Status: todo
Depends on: 0724 steps 1-5 (committed) | Branch: task/0723-v2-overview-polish (worktree /tmp/wt0723)
Executor: Haiku 5.5 | Fits one session: 25 tool calls

## 1. Objective
Finish brief 0724: steps 6, 7, 8, plus lint, using the exact changes below.

## 2. Steps
1. Motion test. Cause found by the orchestrator: on this branch `_rail_page` (App/tests/test_host_wide_geometry_browser.py:943) defaults to `/settings`, which has no help fold-out; on main it defaulted to `/`. In `App/tests/test_motion_browser.py` line 70, change `page = _rail_page(context, wide_base)` to `page = _rail_page(context, wide_base, "/")`. Leave `details.ui-how` as is (the Overview's `<details class="ui-how ov-how ph-hide">` matches at 1280). Run `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_motion_browser.py -q --tb=short 2>&1 | tail -15` from App/. If `heights[0] < full` or the sorted assertion fails, delete the line `.ov-head details.ui-how:not([open]) .ui-how-body{display:none}` from App/app/static/app2.css (line ~207; `display:none` stops the fold-out animation, and a closed details hides its body anyway) and re-run. Commit.
2. Calendar cell (`App/tests/test_dashboard_calendar_browser.py:353`, `.cal-day-number` 43 px vs >= 43.9 at phone widths). Run that test once with `--tb=short | tail -15` to see the exact width and locale. Then `grep -n "cal-day-number" App/app/static/*.css` and compare with `git show origin/main:App/app/static/<file>`. If the only difference is the 20 px phone padding of `body.v2 .main`, add in app2.css: `@media (max-width:767px){body.v2 .cal-day-number{min-width:44px}}` (or min-width on the rule the test measures) and re-run. If the number box still measures under 44, stop on this item and report the widths. Commit if fixed.
3. Screenshots: from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_V2=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots -q 2>&1 | tail -5`. Copy the overview 390, 768 and 1280 images from docs/tasks/screenshots-0710/ into docs/tasks/screenshots-0724/ as overview-390.png, overview-768.png, overview-1280.png. Read overview-390.png. Restore every other modified PNG: `git status --porcelain | awk '$1=="M"{print $2}' | grep '\.png$' > /tmp/pngs0725; git restore --pathspec-from-file=/tmp/pngs0725`. Remove untracked PNGs that the run created outside screenshots-0724 (`git status --porcelain | grep '^??'` first; delete only *.png).
4. If step 1 or 2 changed app2.css: bump the key in App/app/templates/base.html from `20261101-0724` to `20261101-0724b` and run `.venv/bin/python tests/test_static_versions.py --write`.
5. Checks, from App/: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_motion_browser.py tests/test_dashboard_calendar_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_0201_tabbar_safe_area_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_needs_you_0240.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -15`; `.venv/bin/python -m ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -3`. Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.
6. Write `docs/tasks/0724-report.md` with: 390 gaps before/after (date to heading 6 -> 28 px; card to card 24 -> 12 px; "Show N more" to "Today" 28 px; "Today" to first card 12 px; no negative margins), 0724 commits 4f0195a 73b687d 790f155 bd09c01 2fbbee1 and their items, deviations (literal 84px scroll-padding because `--tabbar-h` is set on body; per-width pill override), this brief's results, the test tails. Set Status: done in both 0724 and 0725 briefs. Commit with explicit paths.

## 3. Do not touch
`app.js`, routes, templates, other tests.

## 4. Stop and ask
Stop on an item (not the whole brief) if its anchor is missing; write it in the report and continue.
