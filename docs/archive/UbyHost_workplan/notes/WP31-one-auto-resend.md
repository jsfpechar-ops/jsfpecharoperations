# WP31: Exactly one automatic resend per interrupted filing

Series step 0007, right after WP30. Commit `WP31: Exactly one automatic resend per interrupted filing`. HIGH RISK filing code.

## Summary
Bug found during integration: when the sweep's one automatic resend of an interrupted batch (crash or timeout) was itself unclear, PR 230's code made it a new `outcome_unknown` batch with `retried_at` empty, so the next sweep resent it again, every sweep, for as long as UbyPort timed out. Owner decision Q4: one automatic retry, then hold and alert the host.

Fix: `reporting._retry_outcome_unknown_batches` sends the resend with `submission.mode = 'auto_resend'` (`reporting.AUTO_RESEND_MODE`) and skips any batch with that mode. The mode is written when the resend's row is inserted, before anything goes on the wire, so a resend cut off by a crash is not resent either. An unclear resend stays `outcome_unknown`; its guests keep pointing at it, so the existing in-doubt filter keeps them out of the sweep, `apartment_in_doubt` keeps the card up, and the existing `submission_outcome_unknown` alert and mail fire for it. No schema change.

A send by the host (`ignore_automation=True`) is still allowed and is not the automatic one: it is a fresh batch, and if its own answer is unclear the sweep resends it once.

Unchanged: `claim_sendable` is still the only double-filing guard; collection, the in-doubt filter, `retried_at`, and duplicate answer code 150 counting as filed.

## Files changed
- `App/app/reporting.py`: `AUTO_RESEND_MODE`; the retry query excludes it (`COALESCE(mode, '') != ?`); the resend uses it; docstring.
- `App/app/host_i18n.py`: `reports.mode.auto_resend` (EN "resent automatically after an unclear answer", CS "automaticky odesláno znovu po nejasné odpovědi").
- `App/tests/test_host_labels.py`: the new mode in both mode lists.
- `App/tests/test_stale_submission.py`: 7 new tests.
- In the WP23 commit (0018): `App/app/filing_watchdog.py` docstring and one test in `App/tests/test_filing_watchdog.py`.

## Tests added
In `tests/test_stale_submission.py`:
- a crashed filing (running batch, no live claim) is resent exactly once, and not again on the next sweep;
- the resend times out: one resend over three sweeps, the resend stays `outcome_unknown` with `retried_at` empty, the guest stays pending and held on it, the apartment stays in doubt, the alert is open and one mail went out for the resend;
- a crash during the resend: never resent, recovered to `outcome_unknown`, alert open;
- a manual send after the unclear resend files the guest, clears the in-doubt state and the alert; modes are `auto`, `auto_resend`, `manual`; a later sweep sends nothing;
- an unclear manual send still gets its one automatic resend;
- an accepted resend (`ok`) and a duplicate one (code 150, `ok_duplicate`) resolve everything, with no further sends.

In `tests/test_filing_watchdog.py` (WP23 commit): a stay held on an unclear `auto_resend` batch is at risk once that batch's grace (two sweep intervals) is over, and still at risk five grace windows later.

Without the fix (retry query reverted) 3 of the new resend tests fail.

## Test commands and results (exact counts)
From `App/`, with `LD_LIBRARY_PATH=/tmp/libs/root/usr/lib/aarch64-linux-gnu /tmp/pr230/App/.venv/bin/python -m pytest -q -p no:cacheprovider`:
- `tests/test_stale_submission.py tests/test_host_labels.py tests/test_submission_retry_cap.py` on the WP31 commit: 47 passed.
- `tests/test_report_detail_next_step.py tests/test_report_detail_polish.py tests/test_submission_mail.py tests/test_sweep_containment.py tests/test_ubyport_dorucenka.py tests/test_ubyport_outcome_unknown.py tests/test_ubyport_sample_pdf.py tests/test_claim_resend_complete.py`: 99 passed.
- `tests/test_filing_watchdog.py` on the amended WP23 commit: 39 passed.
- Full suite on the final 33-patch tree: 2775 passed, 2 skipped (see `series/INTEGRATION_NOTES.md`). Ruff: all checks passed.

## Deviations from the spec and why
- The marker is the batch's `mode` instead of a `retry_of_submission_id` link or a per-guest counter. It is the smallest change: no new column (so nothing for WP18's frozen baseline), no new parameter through `submit_for_apartment`/`submit_batch`, and it is set at insert time, which also covers a crash during the resend. It names the batch's origin in the reports list, which is where the host sees modes.
- The WP23 watchdog code is unchanged. A stay held on an unclear resend is "awaiting" for one grace window after the resend finishes, then at risk; the host already has the outcome-unknown alert and mail from the resend itself.
- Guide text (WP03) unchanged: "sends that batch once more at the next automatic check" and "you get an alert whenever an answer is unclear" are now exactly true.

## What Cursor must verify or adapt when applying on the real main
- That nothing else on main writes or filters `submission.mode` with a fixed list that should include `auto_resend` (admin reports, exports). In this tree only the label lookup reads it.
- That the manual send routes still pass `ignore_automation=True` (routes/admin.py), so held guests can be sent by hand.

## Manual steps for the owner
- None. On staging with the mock UbyPort set to time out, one resend should appear in Reports as "resent automatically after an unclear answer", and no further sends until the host sends by hand.
