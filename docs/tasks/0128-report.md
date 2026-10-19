# 0128 report (executor: Haiku 5.5)

Status: review

## Files changed

- `App/app/static/tokens.css` (cont step 1: `--scrim` token). Commit `0128 cont step 1`.
- `scripts/design_lint.py` (cont step 2: `font-family` allowed as `var(`). Commit `0128 cont step 2`.
- `App/app/static/host2.css` (0128 step 2; backdrop uses `var(--scrim)`). Commit `0128 step 2`.
- `App/app/templates/base.html` (0128 step 3: loads host2.css after host-design0123.css). Commit `0128 step 3`.
- `App/tests/test_design_ui_macros.py` (0128 step 4, new). Commit `0128 step 5` with the other section 3 files.
- `App/app/templates/_ui.html` (0128 step 1, commit b940931).

## Commands (last lines)

- `python3 scripts/design_lint.py 2>&1 | tail -5`: `design lint: OK`
- `cd App && .venv/bin/python -m pytest tests/test_design_lint.py tests/test_design_tokens.py -q --tb=short 2>&1 | tail -3`: `6 passed, 1 warning in 0.15s`
- `cd App && .venv/bin/python -m pytest tests/test_skeleton_loaders.py tests/test_signed_in_chrome.py -q --tb=short -x 2>&1 | tail -30`: `26 passed, 1 warning in 1.44s`
- `cd App && .venv/bin/python -m pytest tests/test_design_ui_macros.py tests/test_design_lint.py tests/test_design_icons.py -q --tb=short -x 2>&1 | tail -30`: `50 passed, 1 warning in 0.39s`
- `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_button_contrast_browser.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30`: `3 passed, 1 warning in 7.11s` (no skips)

Screenshots: not taken (no visible change; brief says nothing visible changed yet).

## Section 7

- [x] The six macro tests pass; the design lint passes with `host2.css` enforced.
- [x] Existing host pages render unchanged: `test_host_geometry.py` passes with 0 skipped.
- [x] `git diff b940931^ --stat` lists only section 3 files, plus the two cont-brief edits (`tokens.css`, `design_lint.py`). `catalog.json` was not changed.

## Deviations

- Diff base is `b940931^` as the cont brief says; the 0128 brief's `df8b842` is not used.
- Executor.md says "open one PR"; not done, because the session rules say never open a PR. Owner or orchestrator opens it.

## Questions

None.

## Owner steps left

None. Merge via `scripts/merge-pr-on-green.sh` when the reviewer approves.
