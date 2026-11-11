# 1097 report

Status: blocked (F1 only; everything else done)

## Files changed
App/app/templates/_property_editor.html, App/app/police_letter.py (confirmed_fields only), App/app/routes/admin.py (the `if letter_unconfirmed:` block only), App/app/host_i18n.py, App/app/host_vi_i18n.py, App/app/static/app2.css, App/app/templates/base.html (`app2.css?v=20261111-1097c`), App/tests/static_versions.json, App/tests/test_police_letter_flow.py, App/tests/test_host_police_letter_browser.py, App/tests/test_host_police_letter_guard_browser.py, App/tests/test_police_letter_parser.py (its `letter_ok_` table moved to `letter_ok`), docs/tasks/screenshots-1097/.

## Commands
- Section 6 command 1 (browser, 8 files): 108 passed, 1 failed, 0 skipped. The failure is the known local-only `test_design_guardrails_browser.py` guest-new 390 "Cancel" 43 < 44.
- Command 2: 287 passed, 0 failed.
- Command 3 (`test_0710_v2_mockup_match_browser.py`): 183 passed, 0 skipped.
- design_lint OK, context_lint OK, ruff clean.

## Acceptance
- [x] One tick `letter_ok`; no `police_letter.confirm` key, no "Matches my letter" / "Souhlasí s dopisem".
- [x] Each found value shown once with its own Edit (`details`, no JavaScript, one-way); each name posts once; edited value saved; untouched save keeps all three; unfound value keeps its field.
- [x] Save and /test-connection without the tick: 400, nothing saved; old per-field ticks do not confirm.
- [x] 1085/1086/1096 behaviour intact (tests unchanged apart from the tick).
- [ ] **F1 not done (STOP).** F2 and F3 measured at 390; test button stays `ui-btn-secondary`; 768/1280 not full width.
- [x] cs, en, vi keys together; no new `automation.*` or `police_letter.edit` key; no em dash.
- [x] Layout lint green, 0 skipped, no new ALLOW.
- [x] `app2.css` key bumped (1097a, b, c within this branch); app.js and host.css keys unchanged.

## F1 STOP
The 44 px invisible box cannot sit on the label line without growing the row and without overlapping a neighbour. With the brief's -13 px block margins and a 6 px label gap, `test_0833_property_editor_browser.py::test_0833_property_editor_help_headings_and_width` reported "? overlaps INPUT internal_name" and "gap -4" (it also needs the box at least 12 px right of the label text), and the layout lint reported 16 `help-stranded`. Moving the box upward instead overlapped the H2 section title above (the gap from H2 to the input is about 38 px, less than 44). The 8 to 12 px ring offset also conflicts with 0833's "box at least 12 px from the label" rule. Fixing it needs an owner or orchestrator decision: either change the 0833 rule, or allow more space above labels. F1 CSS is reverted to main, so the help "?" looks as it does today.

## Screenshots (docs/tasks/screenshots-1097/)
find-390/768/1280 (find card open), check-390/768/1280 (one tick, three values, Edit closed), check-edit-390 (IDUB Edit open: input shown, text and Edit gone), error-390/768/1280 (one error under the tick), plain-390 (F2 short timing text, F3 full-width test button; F1 unchanged).

## Notes
- The F3 selector from the brief (`#ubyport .actions .ui-btn`) also makes "Read the letter" (paste row) full width on the phone.
- `--space-3` is 10.5 px on this page (root 14 px), so the new 12 px gaps use `12px`, like the existing rules near them.
- Owner to check the vi wording: confirm_all "Các thông tin này khớp với thư của tôi".
- Personal data: none new. Outbound requests: none new.
