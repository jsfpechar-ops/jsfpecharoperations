# 0807 brief: finish setup wizard v2 browser-test parity

Status: blocked
Executor: Haiku 5.5, alone, in /home/claude/jsfpecharoperations on branch claude/project-thread-a41o7b (checked out; App/.venv exists). Do not commit, push, checkout, reset, stash or restore: the orchestrator commits.

## 1. Objective
The last 33 failures in `App/tests/test_onboarding_wizard_browser.py` pass, without changing wizard behaviour or the approved v2 wizard look. Then the app2.css cache key is bumped.

## 2. Context
Follows 0806 (read `docs/tasks/0806-report.md`, section "Remaining failures"). The wizard's look lives in the `/* 0801 setup wizard (v2) */` block of `App/app/static/app2.css` (lines ~1150-1228, it ends right before `/* 0800 new property + onboarding (v2) */`). Old rules for reference only: `App/app/static/host.css` ~1329-1363, `App/app/static/host2.css` 695 and 1127-1128.

## 3. Files
`App/app/static/app2.css` (only at the end of the 0801 block), `App/tests/test_onboarding_wizard_browser.py` (only the one assertion in step c), `App/app/templates/base.html` (cache key only), the static-versions manifest that `tests/test_static_versions.py --write` rewrites.

## 4. Steps
Env for every test run (from App/): `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`.
a. Lede colour (test line ~1451, 0212 decision): the lede must have the same colour as the h1. Add `body.v2 .wiz-page .setup-wizard-lede{color:var(--ink)}`. Leave `.setup-wizard-instruction` as it is.
b. Focus outline (line ~1563): port host2.css 1127-1128 as `body.v2 .wiz-page .ui-choice-card input:focus-visible{outline:none}` and `body.v2 .wiz-page .ui-choice-card:has(input:focus-visible){outline:2px solid var(--acc);outline-offset:2px}`. The asserted `outlineStyle == none` on the input itself must stay true.
c. Exit button vs header (line ~1169): the v2 head puts the h1 and the exit button side by side on purpose (approved screenshots). Replace the single assertion `assert header["y"] + header["height"] <= exit_button["y"] + 1` with a no-overlap check: `assert header["x"] + header["width"] <= exit_button["x"] + 1 or header["y"] + header["height"] <= exit_button["y"] + 1`. Keep everything else in `check_controls` unchanged.
d. Copy buttons (line ~1421): the three `.setup-wizard-copy` buttons must have equal width and height (tolerance 1 px). Run `-k "guest_sharing and 390 and en and False" -x --tb=short`, then in a short Playwright snippet or via the failure print each button's computed `width`, `box-sizing`, `padding` and which rule wins. Fix it in the 0801 block, e.g. raise specificity to `body.v2 .wiz-page .ui-btn.setup-wizard-copy{box-sizing:border-box;width:200px;max-width:100%;min-height:42px;justify-content:center}` and drop any phone rule that stretches only some of them. Never loosen the tolerance.
e. Run the whole file. Anything still red: same approach, CSS first.
f. Cache key: in `App/app/templates/base.html` change `app2.css?v=20261102-0800` to `app2.css?v=20261102-0807`, then from App/ run `.venv/bin/python -m pytest tests/test_static_versions.py --write -q 2>&1 | tail -3` and then without `--write`.

## 5. Do not touch
Other app2.css blocks, the old stylesheets, templates, other tests, screenshot folders (tests rewrite PNGs in docs/tasks/0102-evidence etc.: leave them, do not restore).

## 6. Commands
From App/, env above:
- `.venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py -q --tb=line -p no:cacheprovider 2>&1 | tail -15` → 0 failed
- `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -k setup -q 2>&1 | tail -3` → 0 failed
- `.venv/bin/python -m pytest tests/test_design_setup_wizard_browser.py tests/test_static_versions.py -q --tb=line 2>&1 | tail -5` → 0 failed
- repo root: `python3 scripts/design_lint.py 2>&1 | tail -3` and `python3 scripts/context_lint.py 2>&1 | tail -3`

## 7. Acceptance
All commands in section 6 green.

## 8. Stop and ask
Stop at 30 tool calls, or if a fix would change wizard behaviour, the approved layout, or another page.

## 9. Report
`docs/tasks/0807-report.md`: per step the rule added, the changed assertion, final tails of section 6.
