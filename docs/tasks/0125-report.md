# 0125 report: design v2 tokens

Status: blocked

## Files changed
- `App/app/static/tokens.css` (step 1, commit 1df8e26): v2 layers appended inside `:root`, reduced-motion rule extended.
- `docs/tasks/0125-design-v2-tokens.md`: Status set to blocked.
- `App/tests/test_design_tokens.py`: created (step 2), NOT committed (fails, see below).

## Commands
- `cd App && .venv/bin/python -c "...count('--coral-600'), count('--skeleton-min')"` prints `3 1` (as expected).
- `cd App && .venv/bin/python -m pytest tests/test_design_tokens.py -q --tb=short -x 2>&1 | tail -30`:
  - Test 1 failed on `--motion-2` (defined twice). Fixed once by counting only the main `:root` block (before the `@media` rule). Rerun failed on `--surface-2`:
    `AssertionError: --surface-2 assert 2 == 1`
  - Not rerun further: STOP per executor rules.
- Not run: contrast and skeleton tests (blocked before §6 checks).

## Acceptance (§7)
- [ ] test_design_tokens.py passes: NO (blocked).
- [ ] `git diff --stat` = two files: not checked, step 2 not committed.
- [ ] Removed-line count: `git diff df8b842 -- App/app/static/tokens.css | grep '^-' | grep -v '^---' | wc -l` prints `1`, not `2` (the `}` closing line is aligned by diff; only the old reduced-motion `:root` line is removed).

## Deviations
- Done: step 1. Left: steps 2 to 3. Blocked by a conflict in step 1 (below).
- Step 1 duplicates two existing definitions in the same `:root` block:
  - `--surface-2`: existing at `App/app/static/tokens.css:105` as `var(--canvas)`; brief adds `--surface-2: var(--sand-150)` at line 139. Later wins, so the value changes.
  - `--ink-2`: existing at line 107 as `var(--ink-secondary)`; brief adds `--ink-2: var(--ink-700)` at line 140. Later wins, so the value changes.
- 36 uses of `var(--surface-2)` / `var(--ink-2)` in `App/app` static and templates would change colour. This is visible, contrary to §7 "no existing token line changed".
- Step 1 is committed on the branch (1df8e26). Not reverted.

## Questions
1. For `--surface-2` and `--ink-2`: keep the existing definitions (drop the v2 lines), or let v2 override them (accept the visible change)? Which?

## Owner steps left
None.
