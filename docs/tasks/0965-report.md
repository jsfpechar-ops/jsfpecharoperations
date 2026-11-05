# 0965 report (B07: G02, G03, G04)

Status: blocked
Reason: the 0965 group passes (19/19, 0 skipped), but the guest baseline has 9 failures outside the 0965 tests, all from the new review and acknowledgement markup at 320, 360 and 1280 px (spacing rules from 0896). Brief section 8 says STOP for this, so the run stopped here. Base 89772982 passes the same test at en-320, so this is a regression from this batch.

## 1. Diff

`git diff --stat 89772982 HEAD`: 11 files, 1370 insertions, 19 deletions. Section 3 files are guest.css, signature.js, i18n.py, guest_uk_i18n.py, form.html, base.html, _signature_script.html, static_versions.json, the test file, and the report. The brief file is also listed.

Commits: earlier batch history up to `77d677fc` (0965 step 7), `144a1c49` (0965 step 8, test fix), this report (`0965 step 9`), and the brief status (`0965 status`).

## 2. Step 8: probe and fix

Probe (temporary file, deleted, never committed), en-390 and cs-390, read immediately and again after 400 ms:

- Unchecked: `.checkline` border rgb(201,201,194), background white. Only neutral rules match.
- After one failed submit (box empty): the row has class `is-invalid` and aria-invalid true. Red comes from `.g-legal-notice .legal-ack.is-invalid .checkline`: border rgb(180,35,24), background rgb(252,235,234).
- Checked: no red rule matches. `.checkline:has(input:checked)` (coral) is overridden by `.g-legal-notice .legal-ack:not(.is-invalid) .checkline:has(input:checked)`: background rgb(230,245,236), border color(srgb 0.518 0.676 0.588), which is green.
- Focus: outline solid 2px rgb(32,32,30) on `.checkline`, not red.

Cause of the failure: the row has `transition: border-color 0.14s, background 0.14s`. The test read the first frame, so the colours were the old ones (for example the failed-submit read was still the idle grey). Product CSS is unchanged. The fix adds a settle helper (`_b07_settle`) before each colour read. The assertions and expected values are unchanged. This is a judgement call outside the brief's decision tree: it reads the settled colour, not a different property.

Six acknowledgement variants pass, then the 0965 group passes.

## 3. Commands (fresh DB each run, zero skips in every row)

- 0965 group `-k 0965`: `19 passed, 26 deselected in 181.56s`, 0 skipped.
- Guest and host geometry `tests/test_guest_*.py tests/test_host_geometry.py`, no -x: `9 failed, 583 passed, 9 warnings in 933.08s`, EXIT=1, 0 skipped. With -x it stopped at the first failure.
- Failing IDs, from a rerun of `test_a_group_of_three_registers_everyone_on_one_phone`: en-320, en-390, en-1280, de-320, de-360, es-320, es-360 (7 of 9). The other 2 failures in the full run are not identified. Messages include `Save person`/`Back` at 1280 px `6.0 px apart (min 12)`, `text 4.1 to 4.5 px from a button (min 12)` (Change next to row text at 320 and 360), and `text 15.1 to 15.4 px from the edge of div#legal-notice (min 16)` (acknowledgement text).
- `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py`: 16 passed, 0 skipped. No `--write` run.
- `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are repo-wide open-brief names).
- `git diff --check` (working tree): no output. `git diff --check 89772982 HEAD` flags trailing whitespace in the brief file `docs/tasks/0965-guest-review.md` (lines 277 to 452), not in product code.
- A test run rewrote the tracked PNG `docs/tasks/screenshots-0402/guide-table-1280.png`. Restored with `git checkout --`, not staged.

## 4. Section 7 ticks

Ticked (passing 0965 tests and inspected screenshots): review rows, birth-date row EN and CS, one surface, acknowledgement states, short save label and quiet Back, sticky clearance, Edit returns to the right step, final save, step 4 diff, screenshots.

Not ticked: none beyond these; the blocker is the guest spacing failures above, which the brief does not list as an acceptance item.

## 5. Screenshots (inspected)

Viewed 16 of the named set: en-390 and cs-390 review-legal-closed, en-390 review-legal-open, en-390 ack-attempted-invalid, en-390 ack-checked-legal-open, cs-390 ack-checked-legal-open, en-390 ack-focus-empty and -checked, en-390 and cs-390 bottom, en-390 saved, en-768 review-legal-closed, cs-1280 review-legal-closed, en-768 and cs-1280 ack-attempted-invalid, en-1280 ack-checked-legal-open.

- Review, closed (390, 768, 1280): five rows, label above value, Change links on one right edge, long name and address wrap inside the row, one divider between rows, legal part is a divider line with no frame. cs-390 shows `1. ledna 1980`.
- Review, open (en-390): legal text sits inside the same card; no second rounded border. The sticky Save person bar covers the legal text while scrolling, which is expected sticky behaviour.
- Attempted invalid (en-390, en-768, cs-1280): row has red border and pink fill. The native "Please check this box if you want to proceed" bubble covers part of the acknowledgement text at en-390. Native browser behaviour, not a layout defect; the page hides nothing else.
- Checked (en-390, cs-390): green, no red or pink on the row.
- Focus (en-390): dark 2 px ring around the row, empty and checked. The checkbox itself shows a faint coral halo on focus from the global input style. Not red on the row; see section 6.
- Bottom (en-390, cs-390): Save person above a quiet text Back link, content not covered at rest.
- Saved (en-390): saved strip and the next person form, no error colour.

Not viewed: cs-390 and cs-768 attempted-invalid, cs-768 and en-1280 focus, en-1280 attempted-invalid.

## 6. Deviations and questions

1. Step 8 is a test-timing fix, not a property fix (section 2). The decision tree did not name timing; flagging it for review.
2. STOP (brief section 8): 9 guest spacing failures outside the 0965 tests (section 3). Fix options, all in guest.css, need a decision: give the flattened legal text at least 16 px inset (the acknowledgement box is 15 px); keep at least 12 px between the value and Change at 320 to 360 px; keep at least 12 px between Save and Back at 1280 px.
3. Question: the checkbox focus halo is coral (rgba 200,90,82 at 28%), from the global input style. The row focus ring is ink. Accept, or change the checkbox focus style?
4. The 2 unidentified failures in the full run need an ID check (full -rf rerun) before the owner decides.

## 7. Owner steps left

None. No push, merge, PR or deploy was made.
