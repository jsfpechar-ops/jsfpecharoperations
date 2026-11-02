# 0525 report
Status: review

Commits on task/0525-stay-detail-style after aee53c8: step 1, step 2, step 3, step 3b, step 4, step 5 (version bump), step 5 screenshots, step 6 (standing-rule test edits), this report.

Files changed (code and tests): host2.css, base.html, reservation_detail.html, static_versions.json, catalog.json, tests/test_0525_stay_detail.py (new, 6 tests), tests/test_host_stay_detail_layout_browser.py, tests/test_onboarding_followup_browser.py. Screenshots: docs/tasks/screenshots-0525/.

Commands:
- Server set: `.venv/bin/python -m pytest tests/test_0525_stay_detail.py tests/test_design_stay_detail.py tests/test_overhaul.py tests/test_wp25_reported_bugs.py tests/test_static_versions.py -q --tb=short -x` -> `66 passed in 4.81s`
- Browser set (`UBYHOST_REQUIRE_BROWSER=1`, `-rs`): `42 passed in 382.87s (0:06:22)`, 0 skipped
- `python3 scripts/design_lint.py` -> `design lint: OK`
- `python3 scripts/context_lint.py` -> `context lint: OK` (warnings only: open briefs name the same files; 14 App/ commits after last status.md update)

Screenshots (fake guest names, lang=cs, three guests on a ready stay): docs/tasks/screenshots-0525/stay-detail-cs-1280.png, docs/tasks/screenshots-0525/stay-detail-cs-390.png. Each viewed once. The 390 full-page capture shows the fixed bottom tab bar mid-page; that is a fixed-position capture artifact, not a layout fault.

Edited assertions in existing tests (section 8 standing rule):
- tests/test_host_stay_detail_layout_browser.py: `nav.stay-jump a` count 4 -> 0; the jump-tab nav geometry block (bounding box and extents) removed, since the tabs were removed in 0524.
- tests/test_onboarding_followup_browser.py: lane-alignment selector list `.stay-property-line`, `.stay-jump` dropped; now `.ui-ph` and `#now` only. Geometry thresholds unchanged.

Deviations:
- Step 4 (g) Send button test: not written. `tests/test_design_stay_detail.py` has no existing send test to copy.
- Step 4 (d): door code state comes from a monkeypatched `door_codes.view` returning an issued dict; no real TTLock setup.
- Step 4 (e): the doc number check is scoped to the card head (up to `class="guest-facts"`). The guest-facts list below still prints the document number. Not changed, since the brief keeps the template to step 1.
- Step 4 (f): no `permalink_token` UPDATE needed; the header copy button renders for the seeded active stay.
- Step 4 (a): the lead guest name is "MINH NGUYEN" (seed data), not the "First Surname" wording of the brief.
- Screenshot helper: a temporary test file added two guests to the ready stay; it was deleted before commit and is not in the diff.

Questions: whether the doc number in guest-facts (the expanded detail list) should also be hidden on the stay page. Brief does not say.
Owner steps left: none. Not pushed, no PR opened.
