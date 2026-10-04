# WP22: Retention alignment with the owner's legal decision

Commit `9571b63` on branch `wp22`, based on `wpbase`. Standalone; not stacked on another WP.

## Summary

Brings every retention job in line with section 4 of `04_legal_positions.md`. Only the classes that differed were changed.

Inventory (line numbers refer to `wpbase`):

| Data class | Current period in code (file:line) | Target period | Change needed |
|---|---|---|---|
| Passport/ID photos | Deleted on Verify (`reporting.py:801`, `routes/admin.py:2166`). Otherwise 30 days after the end of the stay (`passport_photos.py:136`, query at `:189`). No cap from upload. | Delete on verify, otherwise 7 days after check-in, never later than 30 days after upload | Yes. Sweep now deletes when `identity_verified_at` is set, or check-in was 7 or more days ago, or upload was 30 or more days ago. |
| Guest records (house book) | 6 years to the day after the end of the stay (`housebook.py:31`, `:421-426`, `:429-445`) | 6 years from the end of the stay, deleted on 31 January of the following year | Yes. `retention_cutoff` now moves once a year on 31 January. |
| Stay-fee evidence on the guest row (fee decision, reason) | Same as the guest row | Same as guest records | Covered by the guest change. |
| Stay-fee filings and adjustments (`stay_fee_filing`, `stay_fee_adjustment`) | Never deleted, except by workspace deletion (`retention.py:262-264`) | Same as guest records | Yes. New step `stay_fee_records` in `retention.py`. |
| Raw UbyPort request/response XML | 90 days after `created_at`, terminal states only (`reporting.py:1890`, `:1893-1932`) | 90 days | None to the period. Added a per-run audit line and a `now` parameter for tests. |
| Submission receipt row | Kept after XML purge. Deleted when no guest points at it and it is older than the guest cutoff (`housebook.py:483-516`) | 6 years, no personal fields | None. After the purge the row holds only `apartment_id`, `guest_ids` (ids), `created_at`, `finished_at`, `state`, error codes, `pseudo_stamp` (reference), the Dorucenka PDF, `endpoint`, `error_text`. It already qualifies, so nothing was added. It now follows the new 31 January guest cutoff. |
| Invoices (`invoice` table) | 10 years from the end of the year of issue (`invoices.py:542`). But the query used `owner_user_id IS ?` (`:546`), so the nightly global run only matched invoices with no owner. Host invoices never aged out unless the host pressed the Settings button. | 10 years from the end of the calendar year of issue | Period: none. Scope: fixed to `(? IS NULL OR owner_user_id = ?)`. An original whose correction is still inside its 10 years is kept, and corrections are deleted first. |
| Host account data | The closure flow exists: an admin schedules deletion (`routes/admin_accounts.py:657`, 30 days). Then `_delete_workspace` (`retention.py:231-298`) hard-deletes everything, including the account row, acceptance evidence, audit rows and the host's own invoices. | Anonymise 3 years after closure, except invoices | Not changed. Documented under Deviations. |
| Audit per deletion | One `retention_run` summary line with counts only (`retention.py:363`). Ad hoc lines in some purges. The photo sweep logged only when it found something (`passport_photos.py:207`). | Every deletion run writes class, count, cutoff | Yes. New `db.audit_retention`. Called once per step in `retention.run`, and by the photo sweep and the XML purge, including runs with a zero count. |
| Guest notice and privacy notice (`i18n.py:360, 372, 471, 507, 514`; CS `:967, 979, 1076, 1113, 1119`) | Said "six years from the last entry". Said photos are deleted "after your stay". | 6 years after the end of the stay. Photo: 7 days after check-in, 30 days after upload at most. | Yes, EN and CS. |
| Host DPA (`dpa_i18n.py:82, 187`; CS `:324, 401`) | No periods. Said photos are deleted "by the stale-file sweep". | DPA clause from the legal file | Yes. The clause is appended verbatim to section 15 in EN and CS, and the photo sentence in section 4 is aligned. |

How the 6-year rule is read: both statutes count "6 years from the last entry" of the book. For an electronic book kept continuously, a literal reading means nothing is ever deleted. As the legal file decides, the code counts per record: 6 years from the end of each stay, which is the rule § 101(4) applies to paper forms. The run is yearly: a stay that ended in year Y is deleted on 31 January of Y+7. This is written in the `housebook.py` retention comment, and the DPA now states it.

## Files changed
- `App/app/db.py`: new `audit_retention(data_class, count, cutoff, owner_user_id, dry_run)`. It writes an audit line with action `retention_delete` and a JSON detail.
- `App/app/passport_photos.py`: new photo rules (verified, check-in plus 7 days, upload plus 30 days). `PHOTO_GRACE_DAYS`/`stale_cutoff` are replaced by `checkin_cutoff`/`upload_cutoff`. Every sweep writes an audit line.
- `App/app/housebook.py`: `retention_cutoff` uses the 31 January rule; the comment documents the interpretation; the purge audit text gives the cutoff.
- `App/app/invoices.py`: new `retention_cutoff`. `expired_ids` covers all workspaces on a global run, keeps an original while its correction is live, and orders corrections first.
- `App/app/reporting.py`: `purge_submission_payloads` takes `now=`, writes an audit line on every run, and its docstring says what the receipt row keeps.
- `App/app/retention.py`: new `stay_fee_records` step. `_cutoffs()` supplies the cutoff text for each step, and `run()` writes one audit line per step.
- `App/app/i18n.py`: guest legal notice and privacy notice periods, EN and CS.
- `App/app/dpa_i18n.py`: DPA section 15 clause and section 4 photo sentence, EN and CS.
- `App/tests/test_retention_alignment.py`: new tests.
- `App/tests/test_retention_job.py`: due-notice test now uses a fixed date (10 January 2027).
- `App/tests/test_overhaul.py`: old-guest test uses `retention_cutoff` instead of "6 years and 30 days ago".
- `App/tests/test_guest_navigation.py`: updated the expected passport notice copy.

## Tests added
In `tests/test_retention_alignment.py` (19 tests). Every test fixes the date by passing `today=` or `now=`:
- an unverified photo is deleted 7 days after check-in and kept at 6 days;
- a photo uploaded 30 days ago is deleted even though check-in is in the future; one uploaded 29 days ago is kept;
- a verified guest keeps no photo even when the Verify route was not used;
- the photo sweep writes its audit line with both cutoffs when it deletes nothing;
- the guest cutoff, checked at 5 dates across 31 January and a leap day;
- a stay that ended 31 Dec 2020 is kept on 30 Jan 2027 and deleted on 31 Jan 2027; a stay that ended 2 Jan 2021 is kept;
- stay-fee filing `2020-Q4` and its adjustment are deleted on 31 Jan 2027, not on 30 Jan; `2021-01` is kept; a dry run deletes nothing;
- raw XML is deleted at 91 days and kept at 89; the receipt fields survive; the audit cutoff is exactly now minus 90 days;
- an invoice issued 31 Dec 2015 is kept on 31 Dec 2025 and deleted on 1 Jan 2026; one issued 1 Jan 2016 is kept;
- a global run includes host-owned invoices;
- an original invoice stays while its correction is live, and both go once the correction expires;
- every `retention.run` step writes class, count, cutoff, dry_run and owner;
- the DPA clause and the guest notice periods are present in EN and CS.

## Test commands and results (exact counts)
Run from `/tmp/wp/wp22/App` with `/tmp/pr230/App/.venv/bin/python -m pytest -q`:
- `tests/test_retention_alignment.py tests/test_retention.py tests/test_retention_job.py tests/test_scheduler.py tests/test_invoice_immutability.py tests/test_p3_review_repro.py tests/test_overhaul.py tests/test_guest_navigation.py`: 129 passed.
- Broad run, because `db.py` and `i18n.py` changed:
  - `tests/test_[a-f]*.py`: 600 passed, 2 skipped.
  - `tests/test_[g-o]*.py`: 774 passed, 5 skipped, 1 failed.
  - `tests/test_[p-s]*.py`: 656 passed, 1 failed.
  - `tests/test_[t-z]*.py`: 152 passed.
- The 2 failures also fail on `wpbase` without this change (checked with `git stash`):
  - `test_host_geometry.py::test_the_month_filter_shares_its_page_edges`
  - `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`. This one depends on test order: it passes when run alone, and fails the same way on base.
- Ruff (`E9,F63,F7,F82,F401,F841`): all checks passed.
- Not run: `test_guest_browser_e2e.py` with Chromium. Only translation strings changed, no markup, CSS or JS.

## Deviations from the spec and why
- **Host account data: no code change.** A closure flow exists, but it hard-deletes the whole workspace 30 days after an admin schedules it, including the account row. That is shorter than "3 years, then anonymise", not longer, so nothing is kept beyond the legal file's maximum. Making it "keep 3 years, then anonymise" would reverse decision G-D11 and needs a redesign: keep a disabled `user_account` and `legal_entity`, then anonymise both, while deciding what happens to `legal_acceptance` and audit rows. The brief forbids inventing a larger design, so this is listed as future work. Note also that the app's `invoice` table holds the host's invoices to its guests (the host is controller), not invoices UbyHost issues to hosts. UbyHost does no billing in the app. Deleting the host's invoices at closure therefore matches DPA section 15 (delete or return) after the export the flow already offers. If UbyHost billing is added later, its invoices need the 10-year rule and must survive closure.
- **Stay-fee filings and adjustments** were never deleted outside workspace deletion. They are stay-fee book evidence, so they now follow the guest rule (period year before the cutoff year). This adds data that gets deleted, which the WP's "guest records (guest book and stay-fee evidence)" requires.
- **Invoice global scope bug** fixed (see table). The protection for corrections was added because a global purge that deletes an original while its correction still refers to it would fail every night.
- **The photo sweep also deletes the photo of any guest with `identity_verified_at` set.** A host editing a foreign guest sets that flag (`routes/admin.py:2047`) without deleting the photo.
- **Deletion boundaries:** check-in day plus 7 and upload day plus 30 are treated as "due", so a file is never kept past the stated day. Day granularity; the sweep runs every 12 hours.
- **Scope of the audit line:** the owner id goes in the JSON detail, not the `owner_user_id` column, matching the existing `retention_run` line. A system record then does not depend on an account that workspace deletion may remove. This also avoids a foreign-key failure seen in test cleanup.
- **Dry runs** also write per-class lines, marked `"dry_run": true`.
- **Privacy policy section 11** (UbyHost's own data) was not rewritten: it is outside "guest notice / DPA" and does not contradict the decision. The legal file's privacy-policy paragraph can go in with the WP that publishes the privacy policy.

## What Cursor must verify or adapt when applying on the real main
- `retention_cutoff` changed meaning. Any new caller on main that assumes "today minus 6 years" must be checked. Today's callers are `due_guest_ids`, `due_guest_counts`, `purge_orphan_submissions` and `_empty_reservation_step`. With the yearly rule, the due notice fires for a whole year's cohort in January.
- Any test on main that seeds a guest "6 years and N days ago" and expects deletion now needs `retention_cutoff(today) - timedelta(...)` or a fixed date (see the `test_overhaul.py` change).
- If another WP edits `dpa_i18n.py` section 15 or the guest notice strings, merge the text by hand.
- `stay_fee_filing.period_key` must stay `YYYY-MM` or `YYYY-Qn`, because the new step compares `substr(period_key, 1, 4)`.
- Check that no code path on main stores guest names in `submission.error_text` or `record_errors`. Today they hold exception text and UbyPort codes only.
- Confirm that the UbyPort Dorucenka PDF holds no guest personal data, as the existing code comment claims. If it does, the receipt row needs that column dropped at 90 days as well.

## Manual steps for the owner
- Decide whether to bump `UBYHOST_DPA_VERSION` (currently 1.5) and the effective date. The DPA text now states retention periods, which may count as a material change needing re-acceptance. This WP does not bump it, so it does not clash with other DPA work.
- Deletion of guest records, stay-fee records and invoices still runs only with `UBYHOST_RETENTION_AUTOPURGE=1`. The photo sweep and the XML purge run regardless.
- Decide the closure design for host account data (keep 3 years, then anonymise, or keep the current immediate deletion) before UbyHost starts billing hosts.
