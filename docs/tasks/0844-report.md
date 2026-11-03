# 0844 report

Status: blocked

## Files changed
- App/app/host_i18n.py: 19 EN lines (after the EN anchor) and 19 CS lines (after the CS anchor)
- App/app/host_vi_i18n.py: 19 VI lines (after the VI anchor)
- No commits, no push (launcher instruction overrides executor.md commit-per-step).

## Checks
- Step 1 pre-check: `grep -c` for stay_fees.bulk.confirm / invoice.price_use / housebook.preset.label = 0 in both files. Anchors found.
- §7: `"stay_fees.bulk.confirm"` host_i18n.py = 2, host_vi_i18n.py = 1. `"housebook.preset.this_year"` = 2 and 1. Both ticked.
- §6 command 1 (import app.host_i18n, app.host_vi_i18n): no output, exit 0. Ticked.
- §6 command 2 (copy row): FAILED twice, same test.
  Last lines:
  `sqlite3.OperationalError: no such table: apartment`
  `FAILED tests/test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects`
  `1 failed, 4 passed in 1.92s`
- Baseline check: with my two files stashed, the same test fails with the same error. So the failure predates this change (test DB not initialized when the test runs alone or in this row). Stash restored; git status shows only the two files modified.

## Deviations
- Done: steps 1 to 4. Left: step 5 (run §6 row, passes, commit). Blocked on command 2.
- Not committed and not pushed, per launcher instruction.
- Brief Depends-on says base is main after PR #707 on branch task/0844-speed-copy-keys. Ran on claude/project-thread-2t66ph as instructed. Anchors matched, so #707 content appears present here.
- No PR opened (blocked).

## Questions
- The test_host_i18n language-endpoint test needs an initialized DB. Does the owner's CI run this row with a DB fixture that this sandbox lacks, or is this a known pre-existing failure? Needs a decision before 0844 can be marked review.

## Owner steps left
- Decide on the pre-existing `no such table: apartment` failure (see Questions), then have the executor finish step 5 and the commit.
