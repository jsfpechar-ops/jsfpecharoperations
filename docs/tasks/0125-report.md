# 0125 report: design v2 tokens

Status: review

## Files changed (this brief)
- `App/app/static/tokens.css`: v2 layers added in `:root`; reduced-motion rule extended; two older lines removed (step 1b).
- `App/tests/test_design_tokens.py`: created (step 2).
- `docs/tasks/0125-report.md`, `docs/tasks/0125-design-v2-tokens.md` (Status: review).

Commits: 1df8e26 (step 1), 5ae5ca0 (step 1b), 12b04be (step 2), this report commit (step 3).
Note: `git diff df8b842 --stat` also lists files from earlier commits on this branch (not from 0125).

## Commands and last lines
- `pytest tests/test_design_tokens.py -q` : `3 passed, 1 warning in 0.07s`
- `pytest tests/test_design_tokens.py tests/test_host_button_contrast_browser.py -q -rs` : `4 passed, 1 warning in 3.16s` (0 skipped)
- `pytest tests/test_skeleton_loaders.py -q -rs` : `10 passed, 1 warning in 0.75s` (0 skipped)
- `python3 scripts/context_lint.py` : `context lint: OK` (warnings only, pre-existing)

## Acceptance (section 7)
- [x] test_design_tokens.py passes (3 tests).
- [ ] `git diff df8b842 --stat` lists exactly the two files: not met on the branch as a whole (other commits on the branch); the 0125 files are the two named in section 3 plus the report and brief.
- [x] Removed-line count in tokens.css: `3`, not `2`. Two are the older `--surface-2` and `--ink-2` lines (step 1b, accepted); one is the old reduced-motion `:root` line, replaced by the extended one.

## Deviations
- Step 1 duplicated `--surface-2` and `--ink-2` already defined earlier in `:root`. Orchestrator decision: keep the v2 definitions and delete the two older lines (step 1b, 5ae5ca0). Effects: `--ink-2` resolves to the same #50504c; `--surface-2` moves from #f7f7f5 to #f1f1ef (near-invisible, accepted).
- Test fix: `test_every_v2_token_is_defined_once` counts definitions only in the main `:root` block, because the reduced-motion block redefines motion tokens on purpose.
- Rule 7 screenshots: not taken. No template or guest page changed; the only visible effect is the `--surface-2` shift above.

## Questions
None.

## Owner steps left
None.
