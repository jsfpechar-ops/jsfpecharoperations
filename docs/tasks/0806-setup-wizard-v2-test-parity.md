# 0806 brief: setup wizard v2 browser-test parity

Status: todo
Executor: Haiku 5.5, alone, in /home/claude/jsfpecharoperations on branch claude/project-thread-a41o7b (checked out; App/.venv exists). Do not commit, push, checkout, reset, stash or restore: the orchestrator commits.

## 1. Objective
`App/tests/test_onboarding_wizard_browser.py` passes again after 0801 moved the setup wizard to the v2 shell. 46 tests fail; they fall into the groups in section 4. The wizard is restyle-only: every behaviour these tests check (hidden fields, alignment, radio colour) must still work.

## 2. Context
0801 set `{% set v2 = true %}` in `App/app/templates/setup_wizard/_layout.html`, so wizard.css, host.css, components.css are no longer loaded; the wizard's look lives in the `/* 0801 setup wizard (v2) */` block at the end of `App/app/static/app2.css`. Reports: docs/tasks/0801-report.md, docs/tasks/0805-report.md. The old rules the tests relied on are still in `App/app/static/wizard.css`, `host.css`, `components.css`, `host-controls.css` (read only, grep the class names).

## 3. Files
`App/app/static/app2.css` (only inside the 0801 block, extend it at its end; never edit other blocks), `App/app/templates/setup_wizard/*.html` (class additions only), `App/tests/test_onboarding_wizard_browser.py` (only selectors that name removed old-shell markup, e.g. `.ui-ph h1`), `docs/design/catalog.json`.

## 4. Steps
Run once to get the list (from App/): `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1; .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py -q --tb=line -p no:cacheprovider 2>&1 | grep -E "^E |^FAILED|\.py:[0-9]+:" | sed -E 's/\[.*\]//' | sort | uniq -c | sort -rn | head -30`. Then per group, read the test lines named and port the missing rule from the old CSS into the 0801 block (scoped `body.v2 .wiz-page …` or whatever scope the block already uses):
a. `test_choice_card_selects_from_anywhere` (line ~1553, `accentColor != 'auto'`): radios in choice cards need `accent-color: var(--acc)` (v2 sets it for checkboxes only). Also keep outline none / box-shadow none as asserted.
b. `test_phone_guest_sharing_and_clear_setup_actions` and `test_wizard_polish_and_overview_cards` (line ~1250 `assert other.is_hidden()` on `#label_other` in the calendar step, and alignment asserts `abs(a.y - b.y) <= 1` at lines ~1193 wait/save and ~1393 phone prefix/number): find the old rule that hides `#label_other` until "other" is chosen and the rules that put those controls on one row; port them.
c. `test_deferred_police_journey_without_javascript` (bounding_box timeout): find which locator times out (`-x --tb=short -k deferred_police`); if it names old header markup (`.ui-ph h1`), point it at the v2 header h1 of the wizard; if an element is now hidden by v2 CSS, fix the CSS.
d. Anything else left: same approach. Change an assertion only when it names markup that 0801 replaced on purpose; never loosen a numeric tolerance.

## 5. Do not touch
Other app2.css blocks, wizard.css and the other old stylesheets, other pages, the static cache key, screenshot folders (tests rewrite PNGs in docs/tasks/0102-evidence etc.: leave them unstaged, do not restore).

## 6. Commands
From App/, with the env vars above:
- `.venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py -q --tb=line -p no:cacheprovider 2>&1 | tail -15` → 0 failed
- `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -k setup -q 2>&1 | tail -3` → 36 passed
- `.venv/bin/python -m pytest tests/test_design_setup_wizard_browser.py tests/test_onboarding.py tests/test_quick_answers_browser.py tests/test_design_shell_browser.py -q --tb=line 2>&1 | tail -8` → 0 failed (these check 0805's edits too)
- repo root: `python3 scripts/design_lint.py 2>&1 | tail -3`

## 7. Acceptance
All commands in section 6 green.

## 8. Stop and ask
Stop at 30 tool calls, or if a fix would change wizard behaviour or another page.

## 9. Report
`docs/tasks/0806-report.md`: each failing group, the rule ported (from which file), changed assertions with the reason, final tails.
