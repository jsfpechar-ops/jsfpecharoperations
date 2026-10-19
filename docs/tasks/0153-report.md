# 0153 report

Status: review

## Files changed (git diff 79252fd --stat)
- App/app/templates: 9 files, 12 cache-key lines bumped to `20261019-0153` (base, auth_base, public_legal_base, cleaning_shared, guest/base, landing, public_guide, product, pricing)
- App/tests/test_static_versions.py (new), App/tests/static_versions.json (new, 32 files)
- App/tests/test_shell_lane_browser.py (new)
- docs/context/test-map.md: one row after A10
- App/app/static: untouched (diff empty)

## Commands (last lines)
- Step 2 `pytest tests/test_wp07_cache_heartbeats.py -k static`: `4 passed, 9 deselected` (brief expected 5 passed; see Deviations)
- Step 3 `pytest tests/test_static_versions.py`: `2 passed`. Negative check (blank line appended to tokens.css): 2 failed; file restored with git checkout.
- Step 3 ruff: `All checks passed!`
- Step 4 `pytest tests/test_shell_lane_browser.py -rs`: `4 passed`, no skips
- Step 5 `context_lint.py`: `context lint: OK`
- Step 5 three browser files: `76 passed, 1 warning in 150.17s`, no skips

## Section 7
- [x] Step 1: no stale keys left; static diff empty
- [~] Step 2: passed, but count is 4 not 5
- [x] Step 3
- [x] Step 4: 4 passed, 0 skipped
- [x] Step 5: 76 passed, 0 skipped; context lint OK; 4 screenshots viewed

## Screenshots (all at 1280/2000, collapsed)
- /tmp/claude-0/-home-user-jsfpecharoperations/3c6f1ec6-a025-553c-863a-9c0748d5832e/scratchpad/shots/0153/dashboard-1280-collapsed.png: rail 64 px, lane starts right of it with gutter, `+ Add cleaning` outlined, `+ Add stay` coral.
- .../shots/0153/onboarding-1280-collapsed.png: lane clear of rail, step 2 "DO THIS NOW" whole, `Add operator` coral.
- .../shots/0153/dashboard-2000-collapsed.png: same, lane centred within max width.
- .../shots/0153/onboarding-2000-collapsed.png: same; steps 1 to 3 numbered and whole.

## Deviations
- Step 2 expected 5 passed; `-k static` selects 4 in this checkout. No test failed or was skipped; not changed.
- Shot script ran with `-p tests.conftest`, as the brief says.

## Questions
- Is the step 2 count of 5 correct? The selector may be stale in the brief.

## Owner steps left
- Staging: hard reload (Ctrl/Cmd+Shift+R) on the Overview after the merge and deploy.
- Production gets the fix with the next manual deploy.
- Not pushed. No PR opened by the executor.
