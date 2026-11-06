# 0988: PR #790: entity card buttons, property "?" with an accessible H1, final verification

Status: todo
Depends on: 0987 | Base commit: origin/codex/ux-remediation-handoff | Branch: codex/ux-remediation-handoff
Executor: Haiku 5.5 | Fits one session: 25 tool calls. At 21 calls stop, write the report, commit, push.

## 1. Objective
Three last items before the owner merges PR #790: (A) the Edit / Invoice settings buttons on the Business & legal details page overlap the "Properties" row at 390 px; (B) on the property page the "?" must sit right after the title (main's look) while staying outside the H1 (test_0972 rule: the H1 text is only the name); (C) the verification 0987 did not finish.

## 2. Context
- Owner decisions (docs/context/decisions.md): property page = main's layout plus the "Continue setup" card; everything else in the PR is accepted. Lock: connected + off shows "Turn on".
- A: page `/entities` (template `App/app/templates/entities.html` ~line 94, `<td class="nowrap row-actions" data-label="">` with two `ui-btn-compact` links and a row menu). At 390 px the table is shown as a stacked card; the buttons cell rides up over the "Properties 2" cell (screenshot: owner circled it). On origin/main the same card has the buttons on their own line below "Properties". Find the cause by comparing computed styles of `td.row-actions` and its previous sibling on main and branch (main: `git worktree add -q ../m0988 origin/main`, run the app from there with the same venv, remove the worktree at the end), or by diffing the stacked-table rules: `git diff origin/main HEAD -- App/app/static/app2.css App/app/static/admin2.css App/app/static/host2.css | grep -n "data-label\|row-actions\|ui-table\|td" | head -30`. Fix with the smallest CSS change that restores main's stacking (buttons on their own row, 8 px or more below the last cell). Check the same card on `/admin/customers` if it uses the same markup.
- B: 0987 restored main's `App/app/templates/partials/settings_back_header.html`, which puts the help INSIDE `<h1 class="airbnb-title">`. That fails 9 cases of `App/tests/test_0786_settings_geometry_browser.py::test_0972_property_h1_stays_short_while_its_help_is_open` (it requires `.airbnb-header > .page-help-wrap` and no `details`/`.page-help-body` inside the H1: screen readers must not read the help text as part of the heading). Keep that rule. Do this instead: in the partial, render `<div class="airbnb-title-row"><h1 class="airbnb-title">{{ title }}</h1>{{ help }}</div>` when `help` is a page help (`'page-help-wrap' in help`), and keep main's inline `tip-nowrap` form for other helps. CSS in app2.css: `body.v2 .airbnb-title-row{display:flex;align-items:flex-end;gap:8px;flex:1 1 100%;min-width:0}` and `body.v2 .airbnb-title-row>.airbnb-title{flex:0 1 auto;width:auto;min-width:0}` and `body.v2 .airbnb-title-row>.page-help-wrap{flex:none;margin-bottom:6px}`. Then update the test's selector list to also accept `.airbnb-title-row > .page-help-wrap .page-help > summary` (add, do not remove the existing selectors, do not change any other assertion). Add `airbnb-title-row` to docs/design/catalog.json (classes + class_notes). Delete now-unused branch rules only if grep shows no user.
- Cache: any app2.css change bumps the key in App/app/templates/base.html to `20261106-0988` and regenerates App/tests/static_versions.json (`cd App && .venv/bin/python tests/test_static_versions.py --write | tail -3`, as in 0986).

## 3. Files
App/app/templates/entities.html (only if markup must change), App/app/static/app2.css, App/app/templates/partials/settings_back_header.html, App/app/templates/base.html, App/tests/static_versions.json, App/tests/test_0786_settings_geometry_browser.py (selector list only), docs/design/catalog.json, docs/tasks/0988-report.md, docs/tasks/screenshots-0988/.

## 4. Steps
1. `git fetch origin codex/ux-remediation-handoff | tail -3 && git checkout -B codex/ux-remediation-handoff origin/codex/ux-remediation-handoff | tail -3`.
2. Part B (template + CSS + test selector), then run `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0786_settings_geometry_browser.py -q --tb=line -rs | tail -15` from App/: 0 failed. Commit `0988 B: property help beside the H1, outside it`.
3. Part A, then commit `0988 A: entity card buttons below the last row`.
4. Cache key + static_versions (if CSS changed). Commit.
5. Verification (section 6). Copy from /tmp/shots-0988/layout-lint/ the -390 PNGs for property-detail-configured, stays, settings, dashboard, operators, invoice-settings into docs/tasks/screenshots-0988/.
6. Report, set Status, push `git push -u origin codex/ux-remediation-handoff` (no force, never main, no PR).

## 5. Do not touch
UbyPort, validation, routes, migrations, guest pages. No assertion is weakened.

## 6. Commands
From App/, each in one call:
- `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -5`
- `.venv/bin/python -m pytest tests -q -x --ignore-glob='*browser*' -p no:cacheprovider 2>&1 | tail -8` (owner allowed: CI's `test` job runs this)
- `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots-0988 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_0786_settings_geometry_browser.py tests/test_host_property_controls_browser.py -q --tb=line -rs 2>&1 | tail -10`
- `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "propert or overview or stays or settings or operator" -q --tb=line -rs 2>&1 | tail -10`
From the repo root: `python3 scripts/design_lint.py | tail -3`, `python3 scripts/context_lint.py 2>&1 | grep -v ^WARN | tail -2`.

## 7. Acceptance
- [ ] All commands in section 6: 0 failed, 0 skipped in browser files.
- [ ] 390 px: property "?" right after the title's last line; entity card buttons below "Properties", nothing overlapping.

## 8. Stop and ask
A v2_mockup pin fails for the property title or entity card: set it to the measured value with `# 0988` only if the page now matches main visually; otherwise stop. Any other failure in a file this brief did not touch: stop and report it.

## 9. Report
docs/tasks/0988-report.md, 300 tokens: Status (review only if section 7 is all ticked), commits, each command's counts, what caused A, screenshot names.
