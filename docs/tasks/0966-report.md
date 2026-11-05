# 0966 report (executor step 2)

Status: blocked. Reason: two literal acceptance checks did not return the expected value (see Deviations). No code defect found; no production code changed.

## Changed files (code, as briefed: 5)
App/app/routes/guest_guide.py, App/app/templates/guest_guide_quick_done.html, App/app/templates/guest_questions.html, App/app/host_i18n.py, App/tests/test_quick_answers_browser.py.
`git diff --stat 7b0355c4..HEAD` lists 6 files: the same 5 plus docs/tasks/0966-guide-truth.md (brief, commit ae1f8aae).

## Commands (rerun in this session, UBYHOST_DB=/tmp/ubyhost-b08/db-e.sqlite, db.init_db() pre-run, UBYHOST_SHOTS_DIR=/tmp/ubyhost-b08)
1. quick_answers_browser + quick_answers: 11 passed, 0 skipped. Last lines: `...........  [100%]` / `11 passed in 94.21s`.
2. guest_guide* + test_guide: 120 passed, 0 skipped. Last lines: `120 passed in 151.46s`.
3. host_i18n + no_em_dashes + copy_cleanup: 27 passed (1 DeprecationWarning, unrelated). `27 passed, 1 warning in 9.40s`.
4. host_geometry + layout_lint_browser + design_guardrails_browser: 17 passed, 0 skipped. `17 passed in 1072.13s`.
After run 4 one tracked PNG (docs/tasks/screenshots-0402/guide-table-1280.png) was modified; reverted with git checkout. Tree clean.

## Acceptance (section 7)
- [ ] Diff stat is 5 code files: 6 listed (brief file included). Deviation.
- [x] Section 6 commands green, 0 skipped.
- [x] All 30 PNGs in /tmp/ubyhost-b08 opened (24 done-*, 6 questions-empty).
- [x] Opening the page changes nothing: covered by test.
- [ ] Em-dash check: `git diff 7b0355c4..HEAD | grep -c '—'` prints 1, not 0. The only match is the acceptance line inside the brief file itself. App code diff: 0.

## Screenshot observations (all 390/768/1280, EN and CS)
- none: amber banner says no answers were added and guide not yet available; buttons Change answers + Back to the guide; no answers section; no "Write the next card". Correct at all widths.
- saved: amber banner "answers saved, guests cannot see them yet"; Write the next card shown; quick answers section shown. Correct.
- partial: neutral banner "saved and guests can see them; some cards still need your words"; 5 of 17 answered; open list. Correct.
- live: neutral banner "guests can see them inside the right cards"; Back to the guide; "Every card is answered" in Still to write. Correct.
- questions-empty (EN and CS, all widths): one empty state, one button, no summary card. Correct.
- No clipped or wrapped copy seen. At 390 the floating help button and bottom tab bar overlap list text in full-page captures (fixed elements); not verified on untouched pages.

## Observation (not changed)
saved-cs-390 and saved-en-390 show "0 of 17 cards answered" next to a populated quick-answers list. The subline counts guide cards (progress.answered); quick answers come from guide_facts. The brief keeps the subline (risk list: out of scope). Recommend a follow-up.

## Copy check
EN and CS strings for all four states and empty Questions match the brief's copy. No em dashes in copy. Czech read once: natural.

## Deviations
- Pre-run db.init_db() on the unique DB before the tests.
- Earlier last-five-lines output was not available in this session, so the four rows were rerun (results above).
- The two acceptance checks above.

## Done / Left
Done: patch applied (step 1), tests green, screenshots reviewed.
Left: owner decision on the two literal checks (reword brief line 536 or accept the 6-file stat); orchestrator review. No owner steps expected.
