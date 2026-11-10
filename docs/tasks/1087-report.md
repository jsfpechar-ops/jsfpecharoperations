# 1087 report: guest form draft UI

Status: review (steps 0 to 6 done; pushed to `claude/1087-guest-form-draft-ui`, no PR opened)

## Files changed

`App/app/routes/guest.py` (`_add_draft_keys`, two calls), `App/app/templates/guest/form.html` (three data attributes, the welcome line), `App/app/static/signature.js` (`initGuestDraft`, its init call), `App/app/templates/guest/base.html` and `_signature_script.html` (key `20261110-1087`), `App/tests/static_versions.json` (`--write`, only `signature.js`), `App/app/i18n.py`, `App/app/guest_uk_i18n.py` (`draft_welcome`), two new test files, six screenshots. No CSS change.

## Commands

- A: `115 passed in 5.46s`.
- B (`UBYHOST_REQUIRE_BROWSER=1`): first full run `1 failed, 79 passed in 718.10s`, 0 skipped. The failure was my own test 5f expecting an empty surname (see deviation 3). After the test fix, `tests/test_guest_form_draft_1087_browser.py`: `10 passed in 53.48s`; the other four files of B were not rerun on their own (three of them are in the guest row below).
- Guest row (`tests/test_guest_*.py`, `UBYHOST_REQUIRE_BROWSER=1`): `745 passed, 9 warnings in 539.76s`, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only about other briefs and status.md).

## Acceptance (section 7)

- [x] 1082 on main and merged in (step 0, merge of 4219424f, no conflict).
- [x] Close and return at 390 px shows the line and the typed fields; another device sees nothing; after a send the next person has no draft.
- [x] Debounce 2 s, one write per 15 s, allowlisted fields only; one flush on hide, none on a second; absent `party_size` skipped; never the photo, signature or tick.
- [x] Language switch flushes and keeps autosave on; relang and 422 carry the keys for new guests only.
- [x] No JavaScript: no post, no cookie, no line.
- [x] Design unchanged apart from the one line (5g at 390, 768, 1280); no CSS change; six languages.
- [x] Browser tests 0 skipped; layout lint ran green (guest pages are report-only; the run printed no guest-form finding in its tail, I did not dig further); six screenshots.
- [x] `git diff --stat origin/main...HEAD` touches section 3 files only (plus this brief and the status line the brief commits already carried).

## Screenshots (`docs/tasks/screenshots-1087/`)

- `fresh-390.png`: the form as today, one column, empty fields, no green line.
- `fresh-768.png`: two-column name and birth rows, empty, no green line.
- `fresh-1280.png`: rail on the left, form on the right, empty, no green line. The tall gap above the footer is there already.
- `welcome-back-390.png`: the green line under "Not your dates?" and above the stay line; typed values back; nothing clipped or wrapped badly.
- `welcome-back-768.png`: same line, full width of the column; fields in the same two columns.
- `welcome-back-1280.png`: the line sits in the form column only, the rail is untouched.

The visa box is missing on the restored pictures because the restored guest is Czech (existing behaviour), not because of the line.

## Deviations

1. `_draft_owned` on main takes `(request, reservation_id)`, not `(request)` as the brief's step 2 code has it. `_add_draft_keys` calls `_draft_owned(request, reservation_id)`, as `guest_form_new` does.
2. Test 5g: the welcome line is above the step-one card, not inside it, so the card's height cannot drop. The test checks that the `#first_name` top and the card's top drop by the line's height plus margins (within 1 px), that the card's height is unchanged, and that each `.g-field` keeps its left and width.
3. Test 5f: after a send, the next person's surname is not empty. That is the 0838 family prefill from the saved guest (upper-cased, no welcome line), not the draft. The test checks given name, birth date and document number are empty, and the owned count is 1.
4. Test 5c ticks `#legal_ack` by script (it is on the last, hidden step) and does it first, so the 15 s gap cannot hide a wrong post.
5. `playwright` was installed into `App/.venv` by hand (it is not in the requirements files); Chromium came from `UBYHOST_BROWSER_EXECUTABLE`.
6. `origin/main` moved again after step 0 (PRs #877 and #793). Not merged in; those commits touch none of this brief's files.

## Questions

None.

## Owner steps left

None until the diff review. Then one PR, merged with `scripts/merge-pr-on-green.sh`.
