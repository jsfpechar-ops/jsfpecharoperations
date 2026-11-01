# 0727: a single "Today" stay card fills the width on phone
Status: todo
Depends on: 0726 | Branch: task/0727-v2-lone-stay-card (worktree /tmp/wt0727)
Executor: Haiku 5.5 | Fits one session: 15 tool calls

## 1. Objective
Owner, 20:02: the lone "Today" check-in card on the phone Overview "looks a bit weird, it's just a bit and doesn't fill properly". When there is exactly one stay today, the card fills the row; with two or more, cards keep the 272 px sideways scroll of the mockup.

## 2. Context
`App/app/static/app2.css` line 245: `body.v2 .hs .card{margin:0;flex:0 0 272px;...}` inside the phone media block. The `.hs` row has `margin:0 -20px;padding:4px 20px 16px` (line 244), so a full-width card lines up with the other cards on the page.

## 3. Files
`App/app/static/app2.css`, `App/tests/v2_mockup.py`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, `docs/tasks/screenshots-0727/overview-390.png`, report `docs/tasks/0727-report.md`.

## 4. Steps
1. In app2.css, directly after line 245 (same media block, same indentation), add:
   `  body.v2 .hs .card:only-child{flex:1 1 auto}`
2. Run `tests/test_0710_v2_mockup_match_browser.py`. The fixture has one stay today, so `.hs .card` width at 320/390 will now differ from the mockup's 272 px. Add to BOX_OVERRIDES in `App/tests/v2_mockup.py`, with the comment `# a lone stay card fills the row (owner 20:02); the mockup shows several cards at 272 px`, entries `".hs .card@320": {"width": "<measured>px"}` and `".hs .card@390": {"width": "<measured>px"}` using the widths the failure prints (expected 280 at 320 and 350 at 390). If `.hs .card@320` or `@390` already exists in BOX_OVERRIDES, add the width key to that entry instead. Re-run until green.
3. Bump the app2.css key in base.html to `20261101-0727`; run `.venv/bin/python tests/test_static_versions.py --write` from App/.
4. Screenshot: `UBYHOST_SHOTS_V2=1 ... pytest tests/test_0710_v2_mockup_match_browser.py -k screenshots`, copy the overview 390 image from docs/tasks/screenshots-0710/ to docs/tasks/screenshots-0727/overview-390.png, Read it. Restore every other modified PNG (`git status --porcelain | awk '$1=="M"{print $2}' | grep '\.png$' > /tmp/pngs0727; git restore --pathspec-from-file=/tmp/pngs0727`) and delete untracked PNGs the run made outside screenshots-0727.
5. Write the report, set Status: done, commit with explicit paths.

## 5. Do not touch
Templates, other CSS rules, desktop layout.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`)
`.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py tests/test_0520_overview_today.py -q --tb=line -rs 2>&1 | tail -10`; repo root `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
At 390 the single stay card spans the content width; tests and lints pass, 0 skipped.

## 8. Stop and ask
Stop if line 245 does not hold the `.hs .card` rule.

## 9. Report
`docs/tasks/0727-report.md`: change, measured widths, test tails, screenshot path.
