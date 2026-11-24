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
