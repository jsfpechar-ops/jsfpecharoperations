# 0525 report
Status: blocked
Deviations: Done: steps 1 to 4, and step 5 up to the version bump. Left: step 5 screenshots (1280 and 390 px, `?lang=cs`), and the section 6 runs (pytest set, browser set with `-rs`, design_lint and context_lint tails). Stopped at the 25-call checkpoint.

Commits on task/0525-stay-detail-style after aee53c8: step 1, step 2, step 3, step 3b, step 4, step 5, this report.

Diff stat (aee53c8 to HEAD, before this report): 8 files changed, 156 insertions(+), 14 deletions(-) (includes the brief edit and the earlier report). Code and test files: host2.css, base.html, reservation_detail.html, static_versions.json, catalog.json, tests/test_0525_stay_detail.py (new, 6 tests, all pass).

Step 3b: resend form moved from the guests claim line into `secondary_actions`, after the copy button. Class `ui-btn-compact` dropped. Grid for `.guest-card-head` is now 3 tracks.

Step 4 test run: `tests/test_0525_stay_detail.py -q --tb=short -x -rs` -> `6 passed in 1.62s`, 0 skipped.

Step 5: `host2.css?v=20261101-0525a`; `tests/test_static_versions.py --write` -> `wrote .../static_versions.json (40 files)`.

Edited assertions in existing tests: none.

Deviations:
- Step 4 (g) Send button test: not written. `tests/test_design_stay_detail.py` has no existing send test to copy.
- Step 4 (d): door code state comes from a monkeypatched `door_codes.view` returning an issued dict; no real TTLock setup.
- Step 4 (e): the doc number check is scoped to the card head (up to `class="guest-facts"`). The existing guest-facts list below still prints the document number. Not changed, since the brief keeps the template to step 1.
- Step 4 (f): no `permalink_token` UPDATE needed; the header copy button renders for the seeded active stay.
- Step 4 (a): the lead guest name is "MINH NGUYEN" (seed data), not the "First Surname" wording of the brief.

Questions: whether the doc number in guest-facts (the expanded detail list) should also be hidden on the stay page. Brief does not say.
Owner steps left: none yet.
