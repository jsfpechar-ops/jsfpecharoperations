# 0975-f01 report

Status: blocked

## Files changed

- App/app/templates/invoices.html (one line: passes `t('invoice.picker.lede')` to `empty_state`)
- App/tests/test_host_invoice_navigation.py (one new test `test_empty_list_says_invoices_come_from_a_stay`)
- docs/tasks/0975-f01-invoice-empty-state.md (status line only)
- Commit 39232feb `0975 step 1` (patch). This report commit follows it.

## Commands (last lines)

- `git apply --check /tmp/0975-f01.patch`: passed, no output.
- `pytest tests/test_host_invoice_navigation.py -k empty_list -q -x -rs`: `1 passed, 4 deselected in 8.99s`. Pass, 0 skipped.
- `pytest tests/test_invoice_*.py tests/test_stay_fee*.py -q -x`: `1 failed, 16 passed in 59.03s`. FAIL: `test_invoice_autofill.py::test_invoice_buyer_block_spacing_0896` (`selectNodeContents` TypeError in INVOICE_HELP_JS). Rerun on HEAD: fails again. Rerun with the base files (7b0355c4) restored: fails the same way. Pre-existing, not caused by F01.
- `pytest tests/test_host_*.py tests/test_host_geometry.py -q -x -rs`: `1 failed, 33 passed in 150.45s`. FAIL: `test_host_fee_navigation.py::test_frozen_report_order_and_forms` (`'Your records' not in page`). Rerun on HEAD and on base: fails the same way. Pre-existing.
- Not run: the test_design_guardrails / test_layout_lint / test_0710 row (row 4). Not run because of the stop rule.

## Section 7

- [x] `git apply --check` passed; diff touches only the two §3 files.
- [ ] Empty list shows title and sentence in EN (test passes); CS, no second button, wrapping: not verified.
- [ ] No horizontal scroll at 390/768/1280: not verified.
- [ ] All §6 commands green with 0 skipped: not met (rows 2 and 3 fail on base too).
- [ ] UX line per page in the PR: not done.

## Screenshots

None inspected. Row 4 (layout lint) was not run, so no empty-invoices PNG exists yet.

## Deviations

- The worktree had no venv. I created `App/.venv` (git-ignored) from `requirements.lock` (hash-pinned), then `requirements-dev.txt`, `requirements.txt`, and `playwright==1.63.0` with `playwright install chromium`, as ci.yml does. No change to any dependency file.
- Test runs used UBYHOST_DB under /tmp/ubyhost-b17 and UBYHOST_REQUIRE_BROWSER=1.
- git status was clean after all runs. No tracked PNG changed.
- Done: steps 1 and 2 (patch applied, step 1 committed), §6 row 1 passed. Left: §6 rows 2 to 4 (row 2 and 3 stopped on pre-existing failures), screenshots, §7 items.
- Checkpoint: this chat reached 25 tool calls, so the run stopped here. Brief 0975-a03 was not started in this chat (see its report).

## Questions

- Should the two pre-existing failures (`test_invoice_buyer_block_spacing_0896`, `test_frozen_report_order_and_forms`) get their own brief? They fail on the base commit as well, and are not in F01's scope.

## Owner steps left

- Triage the two pre-existing failures.
- Nothing to push or merge from this batch.
