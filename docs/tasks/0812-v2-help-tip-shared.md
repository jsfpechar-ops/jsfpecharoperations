# 0812 brief: one shared v2 help-tip rule, finish 0809

Status: todo
Executor: Haiku 5.5, alone, in /home/claude/jsfpecharoperations on branch claude/project-thread-a41o7b (checked out; App/.venv exists). Do not commit, push, checkout, reset, stash or restore: the orchestrator commits.

## 1. Objective
0809 moved fine print under help "?" on the 0800-0804 pages. The 0800 browser test now fails on cleaning-shares (all widths), cleaning-new 1440, guest-guide, onboarding 390/768 because the "?" buttons are 23x21 px, overlap the h1, or push content under the phone tab bar. Fix it once, for all v2 pages, and remove the per-page copies.

## 2. Context
Read `docs/tasks/0809-report.md` (sections "Onboarding + wizard" and "Guest guide + cleaning"). Help-tip rules are scattered in `App/app/static/app2.css` (grep `help-tip`): lines near 692-695 (prop/havel), 1189/1236 (wizard), 1270-1271 (prop-new), 1292-1293 (onboarding), 1299-1302 (prop-new, wiz-page popover). Leave the stay-detail (602/606) and `details` (385, 947-949) rules alone.

## 3. Files
`App/app/static/app2.css` only.

## 4. Steps
Env (from App/): `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`.
a. Add a block `/* 0812 help tip (v2) */` at the end of app2.css: `body.v2 .help-tip` inline-flex, relative, vertical-align middle, margin-left 6px; `body.v2 .help-tip-btn` 24x24 min, round, inline-flex centred, padding 0, box-sizing border-box; below 1024 px min 44x44 (use negative margin -10px so the 44 px target does not add line height or push layout); `body.v2 .help-tip-body` hidden until `.is-open` or `:not([data-js]):focus-within`, then the popover style of line 1302 (absolute, z-index 70, width min(320px, 100vw - 32px)). `body.v2 .heading-with-tip` (and any wrapper 0809 added: grep templates for `-tip"` classes) display flex, align-items center, gap 6px, so the "?" never overlaps the h1.
b. Delete the now-duplicate per-page help-tip rules listed in section 2 (keep stay-detail and details rules). Do not change anything else in those blocks.
c. Run the failing groups with -k (cleaning, guest, onboarding) until green, then the full commands below.

## 5. Do not touch
Templates, tests, other rules, the cache key.

## 6. Commands
From App/, env above:
- `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py tests/test_onboarding_wizard_browser.py tests/test_property_create_browser.py -q --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed
- `UBYHOST_SHOTS_0800=1 .venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -q 2>&1 | tail -3`
- repo root: `python3 scripts/design_lint.py 2>&1 | tail -3`

## 7. Acceptance
Section 6 green; screenshots regenerated.

## 8. Stop and ask
Stop at 30 tool calls, or if a template change seems needed.

## 9. Report
Append "## 0812" to `docs/tasks/0809-report.md`: rules added, rules removed, final tails.
