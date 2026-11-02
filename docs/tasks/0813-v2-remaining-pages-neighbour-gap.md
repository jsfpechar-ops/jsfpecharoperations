# 0813 brief: no element touches its neighbour on the 0800-0804 pages

Status: todo
Executor: Haiku 5.5, alone, in /home/claude/jsfpecharoperations on branch claude/project-thread-a41o7b (checked out; App/.venv exists). Do not commit, push, checkout, reset, stash or restore: the orchestrator commits.

## 1. Objective
Owner rule (Josef, 2026-11-02 14:38): no element may crowd its neighbour (his example: the mock/production tag too close to the search pill). On the pages of `App/tests/test_0800_v2_remaining_pages_browser.py`, controls and cards keep at least 12 px from each other, and a geometry test enforces it at all 6 widths.

## 2. Context
The shared sidebar/top bar (mock tag, search pill, workspace card) is being fixed in another thread: exclude `.side`, `.tabs`, the top bar and the mock banner from this check. Help "?" buttons sit 6 px after their label on purpose (0808 step a): exclude a `.help-tip` from its own label/heading.

## 3. Files
`App/tests/test_0800_v2_remaining_pages_browser.py`, `App/app/static/app2.css` (blocks 0800-0804, 0808, 0812 only).

## 4. Steps
Env (from App/): `export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`.
a. Add a test (or a check in the existing per-page test) that, inside `main`, collects visible "boxes": `button, a.ui-btn, .ui-btn, input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea, .ui-pill, .badge, .ui-chip, .ui-card, .card, section` with nonzero size. For every pair that does not contain the other and whose boxes overlap on one axis (side by side or stacked), the gap on the other axis must be >= 12 px; overlapping boxes (gap < 0) also fail, except a box inside its own card. Report the pair (selectors, gap) in the failure message. Pairs where one is a `.help-tip-btn` and the other is the text it belongs to are not checked (they are not in the list anyway).
b. Run it on all pages and widths, and list the findings first (do not fix blindly).
c. Fix each finding with spacing in the page's own app2.css block (gap/margin 12-16 px). Never shrink a tap target below 44 px on phone.
d. Rerun the whole file and regenerate screenshots.

## 5. Do not touch
Templates, the sidebar/top bar/tabs/mock banner rules, other tests, the cache key.

## 6. Commands
From App/, env above:
- `.venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py tests/test_onboarding_wizard_browser.py -q --tb=line -p no:cacheprovider 2>&1 | tail -8` → 0 failed
- `UBYHOST_SHOTS_0800=1 .venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -q 2>&1 | tail -3`
- repo root: `python3 scripts/design_lint.py 2>&1 | tail -3`

## 7. Acceptance
Section 6 green; the new check is in the 0800 test file.

## 8. Stop and ask
Stop at 30 tool calls, or if a fix needs a template change.

## 9. Report
`docs/tasks/0813-report.md`: findings (page, width, pair, gap), rules changed, final tails.
