# 1100 report

Status: blocked (tool-call cap reached, brief section 8). Done: steps 1 to 4 (server side and JS), the P5 fix and P6 in code, step 7 (labels, app.js cache key, static_versions.json), step 8. Left: step 4 browser test file `test_host_police_paste_browser.py`, steps 5 and 6 browser tests (Discard cases a-f, timing), the rewrite of the old browser files, step 9 (layout lint, 15 screenshots, UX notes), and the step 10 browser command.

## What changed
- `App/app/police_letter.py`: `LetterResult.password` and `.facility` (`repr=False`); password after a label and a colon, one token of 6 to 64 printable ASCII characters, read whole (a trailing `.` is kept); an IDUB- or login-shaped value or one equal to the IDUB or login is `unreadable`; two values `ambiguous`. Facility: the first line after `Ubytovací zařízení:` at the start of a line; over 35 characters stays `unreadable` (orchestrator decision: no truncation). `confirmed_fields` always returns `(listed, [])`. `FIELDS` unchanged.
- `App/app/routes/admin.py`: `police_letter_read` answers JSON with `Accept: application/json` (status, fields, filled, missing, message, `no-store`), else the HTML page as before with the five boxes filled. Tick refusals, `_letter_rows_from_*` and `_letter_form_text` removed. `letter_listed` blocks in `apartment_update` and `test_connection` untouched.
- `App/app/templates/_police_fields.html` (new partial, variables listed at its top), `_property_editor.html` includes it; check block, tick and `letter_shown` wrappers gone; password box `type="text"`, `value` only in the read answer; status line `#police-letter-status`. Timing select: per-option `data-hint`, `#automation_mode-hint`, label `automation.hours_delay`.
- `App/app/static/app.js`: paste fills at once (fetch JSON, abort earlier, no overwrite of hand edits, `reset` restores `letter_fields`); hours field `hidden` unless delay; one leave-guard click listener per document reading the current forms and dialog; Discard marks forms as leaving and follows the link under a `document._ubyLeaving` flag.
- `host_i18n.py`: property labels (en, and the cs lines in the table), new police and automation keys, five old police keys deleted; `host_vi_i18n.py`: deletions only (the five keys and `police_letter.paste_help`, which said the password is never read).
- `base.html` app.js `?v=20261111-1100a`; `static_versions.json` regenerated. app2.css unchanged.

## Discard root cause
Fixed in code for causes (1) dirty-start re-catch, (2) stale per-visit listeners and (3) hidden `letter_fields` not reset. The failing-first browser test (step 5) was not written yet.

## Tests
See the PR body for the counts.

## Existing test files edited
`test_police_letter_parser.py` (confirmed_fields table, new P1 tests), `test_police_letter_flow.py` (tick tests replaced by no-tick saves, JSON test, password-value test, browser helper now pastes), `test_first_setup_open_section.py` (dropped `letter_ok`). Still to edit: `test_host_police_letter_browser.py`, `test_host_police_letter_guard_browser.py` (they click the read button, now hidden with JS, and wait for `#police-letter-check`).
