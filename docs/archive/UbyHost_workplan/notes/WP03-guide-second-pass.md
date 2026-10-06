# WP03: Guide second pass for the owner decisions

Patch: `WP03-guide-second-pass.patch` (commit on top of `wpbase`, applies on `wpbase` alone; independent of WP01 and WP02 in code). The text describes behaviour from WP01 and from the PR 230 fix items 2, 3 and 4, so merge it after those.

## Summary
Help & guide text updated in EN and CS:
- `guide.reporting.failure`: a send with no answer is sent once more on its own at the next automatic check; if still unclear the stay is held and the host gets an alert; a guest the police already hold counts as reported.
- `guide.faq.twice_a`: same rule in the FAQ (it said the guests always wait for the host).
- New `guide.settings.deletion`: banner with the date (30 days ahead), e-mail and 7-day reminder, sign-in kept until the date, the "Download everything (ZIP)" button and what the ZIP holds (guest register CSV, signed registration forms, police receipts, invoices, saved stay-fee filings as PDF and CSV), permanent deletion on the date.
- New `guide.stays.dates_changed`: guests do not sign again; each guest's dates are shortened to fit the new booking, or set to the new booking if they fall outside it; each change goes to the activity log; a reported guest keeps the filed dates and the host gets a warning.
- WP01 sentence: new `guide.reporting.filed` ("After a stay is reported, its deadline shows when it was filed, or how late..."), and `guide.overview.deadline` now starts "Until a stay is reported, ...".
- Text fix: Czech `guide.settings.body` said "protokol činnosti"; the Settings menu says "Protokol aktivit". Now matches.

## Files changed
- `App/app/guide_i18n.py`: the keys above, EN and CS.
- `App/app/templates/guide.html`: renders `guide.stays.dates_changed`, `guide.reporting.filed`, and `deletion` in the Settings list.
- `App/tests/test_guide.py`: two tests added.

## Tests added
- `test_the_guide_has_the_same_keys_in_english_and_czech`: EN and CS key sets of `GUIDE_STRINGS` are equal and no value is empty (no such test existed for the guide file).
- `test_the_guide_describes_the_owner_decisions`: the four new or changed paragraphs render on `/guide` in EN and CS, carry the key facts, and the deletion text names the real banner button label in both languages.

## Test commands and results
From `App/`, with `/tmp/pr230/App/.venv/bin/python -m pytest -q`:
- On `wpbase` + this patch alone: `test_guide.py test_host_i18n.py test_public_guide_freshness.py`: 14 passed.
- Every test that references the guide: `test_admin_route_split.py test_guide.py test_host_i18n.py test_host_redesign.py test_logo_placements.py test_onboarding.py test_public_chrome.py test_public_copy_i18n.py test_public_guide_freshness.py test_stay_labels_cs.py`: 111 passed.
- Broad run on the final stack: see WP01 notes.
- Ruff: all checks passed.

## Deviations from the spec and why
- The WP01 guide sentence is here, not in WP01, so all guide edits are in one patch.
- `guide.overview.deadline` also changed (it said every row shows the time left, which is wrong after WP01).

## Further mismatches found (not changed, not text only or not certain)
1. `guide.reporting.scheduled_detail` says "0 to 48" hours. The form allows 0 (`min="0"`), but `routes/admin.py` saves `_form_int(...) or 24`, so 0 is stored as 24. Code bug, not text. Either fix the code (`0` kept) or change the text to "1 to 48".
2. `guide.statuses.failed` says red includes "the outcome is unknown". On `wpbase` a stay whose batch has an unknown outcome keeps its guests pending, so the stay pill is "Ready" (blue); only the report row (`submission_pill`) and the alert are red. Check after PR 230 item 2 and reword if the stay pill is not red.
3. The new retry text assumes the item 2 retry runs for every automation mode through `sweep()`. If the retry skips Manual properties, add "(automatic modes only)".
4. The date-change text says each change is written to the activity log. That is the PR 230 item 3 audit row; check it is written with the host's `owner_user_id` so it appears in the host's Settings activity log. If not, drop that sentence.
5. The deletion text says the deletion date is 30 days ahead (`WORKSPACE_DELETION_DAYS = 30`) and the reminder comes 7 days before (`WORKSPACE_REMINDER_DAYS = 7`). If counsel changes the 30 days, update the text.

## What Cursor must verify or adapt when applying on the real main
- Merge after PR 230 items 2, 3 and 4 and after WP01; reread the four paragraphs against the merged code (points 2 to 4 above).
- The ZIP list assumes PR 230 item 4 adds stay-fee PDFs and CSVs.
- Open `/guide?lang=en` and `/guide?lang=cs` once and read the new paragraphs in place.

## Manual steps for the owner
Read the Czech text of the four paragraphs once. No server steps.
