# 2052 report: realistic parity seed and rerun (E, F)

Status: blocked

Stopped at the executor tool-call budget and at brief step 1's stop rule. Steps 1 to 6 are committed. Step 7 was folded into the step 8 rerun. Step 8 ran, but the submission seed block was skipped, so the submission cases did not get data. Step 9 (image review, PNG copy) was not done.

## Files changed

- `scripts/e2e/seed_parity_extra.py`: submission, questions, Leon, privacy and invite blocks rewritten (commits 2fb08ee, 0734977, 29c9b40, 8452b0c, 989520a).
- `scripts/e2e/parity_cases.py`: four submission cases and `guide-question-answered` added (commit 9591e89).
- `docs/tasks/2052-report.md`: this file.

## Seed result (group E/F run)

- Worked, no skip line: questions, Leon (`leon_block`), privacy, invite, cleaning, havel, property, unsub.
- Skipped: `submission` with `{"skipped": "submission", "reason": "no guests for the apartment; not seeded"}`. Brief step 1 says STOP when the guest list is empty. The rows `submission-draft`, `submission-sent`, `submission-ok`, `submission-transport`, `submission-running`, `submission-legacy-null` all printed `SKIPPED (seed block missing)`. So none of the submission cases were compared.
- Not verified: the questions, Leon, privacy and invite ids were not checked against the case rows; I did not open those pages.

## Command tails

- `source scripts/e2e/parity_env.sh`: exit ok, log at /var/tmp/parity_env.log.
- Rerun `PARITY_GROUP=E,F .venv/bin/python ../scripts/e2e/page_parity_visual.py` (exit 1, full log /var/tmp/parity_2052.log): `{"rows": 132, "verdicts": {"identical": 112, "invisible": 2, "visible": 18, "accepted": 0, "error": 0}}`. Report: /var/tmp/parity-visual/report-E-F.md.

## Visible rows (not described in plain words: no image review)

All 18 visible rows are at 390, 768 and 1280, cs and en:
- `apt-guide-full-cs`, `apt-guide-full-en`
- `guide-item-cs`, `guide-item-en` (brief note: ACCEPTED candidate, Go keeps one Save per form)
- `guide-questions-full-cs`, `guide-questions-full-en`

Invisible: `cleaning-edit-cs`, `cleaning-edit-en` at 390.

`submission-legacy-null` was not run, so I cannot say whether Go answers 200 or 500.

## Verdicts (the submission cases)

| case | verdict |
|---|---|
| submission-ok, submission-transport, submission-running, submission-legacy-null | not compared (seed block skipped) |
| submission-draft, submission-sent | not compared (seed block skipped; the old fake rows are gone, so these now also skip) |

## Folder

`/var/tmp/parity-visual/_visible-2052/` was not created. No PNGs were copied.

## Deviations

- Step 1 STOP: the apartment seeded by the parity run has no guest rows linked through a reservation, so the submission block cannot pick guest ids. Not guessed around.
- Step 2's commit also carried the import line for steps 4 and 5 (`dsr`, `auth`, `login_link`). Steps 4 and 5 are their own commits with the bodies.
- The compile check in step 1 removed `scripts/e2e/__pycache__`, a cache directory created by my own py_compile run. Not tracked in git.
- Commit trailer: the brief and your message say Claude Opus 5.5. I used that exactly, but I am running as Haiku 5.5.

## Questions

1. Which guest ids should the submission block use? The parity apartment has no guest rows under its reservations. Please check the seed in `scripts/e2e/seed.py` for how guests are linked, or give a reservation with guests.
2. Confirm the `ACCEPTED` classification for `guide-item` cs/en and `apt-guide-full` (brief 2052 note) after someone has looked at the PNGs.

## Follow-up

Step 1: `submission()` in `scripts/e2e/seed_parity_extra.py` now picks the first apartment of the owner that has guests, takes up to 2 guest ids from it, and inserts all submission rows there (commit "2052 follow-up step 1").

Step 2: `PARITY_ONLY='submission*' PARITY_GROUP=B,E page_parity_visual.py` (group E is needed for the submission cases). 48 rows (8 cases x cs/en x 390/768/1280): 48 identical, 0 visible, 0 error. Go logged HTTP 200 for all 48 submission requests (12 `/submissions`, 36 `/submissions/{submission_id}`). The log line does not name the stack, so the 200s are not split by Python vs Go; identical pixels show both sides render the same page. `submission-legacy-null`: Go 200, same as Python. Note: a single-case rerun overwrote `probe.json` and `report-E.md`; the final full rerun restored them (`report-B-E.md`).

Step 3 (per page, 1280 en; all widths identical, so no narrower check needed). Python and Go show the same content in every case:
- `submission-draft` (Report #2): Rejected, "Open the stay to fix" button, stamp E2E-STAMP-0002, finished 2026-11-24 15:52:39, 2 guests. Guest 1 Rejected with the E2E record problem text; guest 2 Accepted. Not a true draft row.
- `submission-sent` and `submission-ok` (Report #1): Accepted, "Download Doručenka (PDF)" button, stamp E2E-STAMP-0001, 2 guests both Accepted.
- `submission-transport` (Report #3): Not delivered, yellow "Transport error E2E connection refused" banner, stamp shown as dash, guests both Accepted.
- `submission-running` (Report #4): In progress, no stamp, no finished date, no button, guests both Accepted.
- `submission-legacy-null` (Report #5): Accepted, no button, empty help-icon row under the outcome, stamp dash, guests 0, text "Nothing reached UbyPort, so no guest was processed." Go 200. Accepted with 0 guests is a realism oddity to review, not a Python/Go difference.
- `submissions` and `submissions-full` (Police reports list): 5 rows (Accepted E2E-STAMP-0001, Rejected E2E-STAMP-0002, Not delivered, In progress, Accepted with 0 guests and no stamp); buttons "Guest register" and "Download Doručenka (ZIP)".

PNG folder: `/var/tmp/parity-visual/_visible-2052/` (8 files, 1280 en side PNG per case). Full set: `/var/tmp/parity-visual/<case>-<lang>/`.

Step 4: this section.
