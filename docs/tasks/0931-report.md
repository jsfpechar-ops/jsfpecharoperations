# 0931 report: layout lint checks for the design system

Status: blocked

## Files changed
- `App/tests/layout_lint.js`: rules header-actions-misaligned (step 1), multiple-save-in-form (step 2), duplicate-heading (step 3). Commits 64bb4be, af5595f, 1fec034.
- `App/tests/test_layout_lint_browser.py`: BAD_PAGE samples for the two rules, a separate BAD_HEADER_PAGE at 1024 px for the header rule, and the expected set. Commit d2827e6.
- `docs/context/decisions.md`: not changed (see Blocker 2).

## Commands
- `App/.venv/bin/python -m pytest tests/test_layout_lint_browser.py -rs`: NOT RUN. Conftest fails: `ModuleNotFoundError: No module named 'requests'`. `requests` is a runtime dependency in `App/requirements.txt`, but the venv does not have it.
- `App/.venv/bin/python -m py_compile App/tests/test_layout_lint_browser.py`: OK.
- `node --check App/tests/layout_lint.js`: OK.
- `python3 scripts/context_lint.py`: OK at HEAD. With the step 5 line it FAILS (decisions.md ~2244 tokens > cap 2200), so the line was reverted.
- Standalone Playwright check (scratch script, not committed; bad markup taken from the test file): `multiple-save-in-form` and `duplicate-heading` fire on BAD_PAGE at 390 px. `header-actions-misaligned` fires on BAD_HEADER_PAGE at 1024 px (button "Create a new invoice": heights differ).

## §7 checklist
- [x] Three new rules fire on the bad sample (standalone check)
- [ ] `test_layout_lint_browser.py` passes, 0 skipped (not run)
- [ ] Context lint green (fails only if step 5 is added; HEAD is green)

## Real findings per rule
None. The host-page lint test did not run, so no real page was checked.

## Deviations
- The header rule runs only at 768 px and up, so its sample is a separate 1024 px page in the test, not part of BAD_PAGE (390 px).
- Step 4 test run: not done (Blocker 1). KNOWN_FINDINGS was not added, since nothing is known to fail yet.
- Step 5 decision line: not committed (Blocker 2).

## Blockers
1. `requests` is missing from `App/.venv`. Install it from `App/requirements.txt` (`App/.venv/bin/pip install -r App/requirements.txt`) and rerun the step 4 command.
2. `docs/context/decisions.md` is at the token cap. Compact or split it first, then append: `2026-11-04 [workflow] design-system.md is the front door for host UX rules; layout lint gained header-actions-misaligned, multiple-save-in-form, duplicate-heading (brief 0931).`

## Questions
- Should the venv be fixed by the orchestrator, or should the executor install into it? I did not install, because executor.md forbids adding dependencies.

## Owner steps left
- None needed for the code. Fix the two blockers above, then run step 4 and step 5 in a new session. No PR yet. No push.
