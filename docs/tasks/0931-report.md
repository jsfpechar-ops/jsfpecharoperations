# 0931 report: layout lint checks for the design system

Status: blocked

## Files changed
None. No step was applied.

## Blocker
- `App/.venv` does not exist (`App/.venv/bin/python` missing). `python3` on PATH has no `pytest` or `playwright`.
- The brief (§6) and executor.md require the App venv. Per the brief's instruction "if missing, report blocked", I stopped before editing.
- Browser is present: `/opt/pw-browsers/chromium-1243`.

## Steps
- Step 1 (header-actions-misaligned): not started.
- Step 2 (multiple-save-in-form): not started.
- Step 3 (duplicate-heading): not started.
- Step 4 (tests and allow-list): not started.
- Step 5 (decisions line): not started.

## §7 checklist
- [ ] Three new rules fire on the bad sample
- [ ] `test_layout_lint_browser.py` passes, 0 skipped
- [ ] Context lint green

## Real findings per rule
None. No host page was run through the new rules.

## Deviations
Done: none. Left: steps 1 to 5.

## Questions
- Should the venv be created from `App/requirements-dev.txt` (and playwright installed), or should the owner set it up? I did not create it, because executor.md says never add a dependency.

## Owner steps left
1. Provide or create `App/.venv` with `requirements-dev.txt` and playwright, then start a new executor session on brief 0931.
2. No PR opened (status blocked; brief says no push).
