# 1100 report: police paste autofill

Status: review. Steps 1 to 10 done (two sessions). Named `1100-police-paste-autofill-report.md`: main's `1100-report.md` belongs to the stays brief (number collision).

## What changed
- `police_letter.py`: `LetterResult.password` / `.facility` (`repr=False`); password read whole after a label and colon; IDUB/login-shaped or equal values `unreadable`; facility over 35 chars `unreadable`. `confirmed_fields` returns `(listed, [])`. `FIELDS` unchanged.
- `routes/admin.py`: `police_letter_read` answers JSON with `Accept: application/json` (`no-store`), else the no-JS page with five boxes filled. Tick refusals and `_letter_rows_*` gone. `letter_listed` blocks untouched.
- `_police_fields.html` (new partial), `_property_editor.html`: no check block or tick; password `type="text"`, `value` only in the read answer; `#police-letter-status`; timing hints and `automation.hours_delay`.
- `app.js`: paste fills at once; hours hidden unless delay; one leave guard per document; Discard leaves under a leaving flag. `app2.css`: an empty status line takes no room.
- i18n en/cs labels "property", new keys; vi deletions only. Keys `app.js?v=20261111-1100b`, `app2.css?v=20261111-1100a`.

## Discard root cause (proven)
Cases a-f in `test_host_unsaved_changes_browser.py` (`test_1100_*`, 390 and 1280), run against `c75db35d:App/app/static/app.js`:
- (d) page that loads dirty (no-JS read answer, `data-dirty-start="1"`) **failed at both widths**: Discard never left. `discard()` cannot clean a dirty-start form (`recomputeDirty`), so `link.click()` hit the capture handler again and the dialog reopened. Fixed by the leaving flag.
- (a) Stay, (b) Discard, (c) Save, (e) Turbo visit after a Save, (f) fill by hand with `letter_fields` set: passed on pre-fix code. Causes (2) and (3) did not block leaving; their fixes stay (one listener; `reset` restores `letter_fields` so a later Save is not a letter save).
- All 8 pass with the fix.

## Tests
- Server row (+ `test_remove_legacy_actions`, `test_required_stars`, `test_shortcut_hint_no_flash`): 713 passed, 57 skipped (browser files, run in the browser row).
- Filing row: 396 passed.
- Browser row: 332 passed, 4 failed, 0 skipped (22 min, merged head). None from 1100: `test_host_ux_acceptance` (known on clean main), `test_design_guardrails_browser` guest-new 390 "Cancel" 43<44 (known local-only), `test_host_flash_outcomes::test_browser_renders_saved_warning_as_sticky_amber` (fails the same on origin/main, checked in a main worktree), `test_host_filter_panels_browser` stays filter (flaky: passes alone). All 1100 browser files green: police_letter 18, guard 3, paste 17, unsaved 1100 cases 8.
- Layout lint 4 passed, 0 skipped, no new `ALLOW`. `design_lint` OK, `context_lint` OK.

## UX gate
`docs/tasks/screenshots-1100/{police-empty,police-after-paste,timing-delay,timing-manual,leave-dialog}-{390,768,1280}.png`, all opened.
- police-empty: read button hidden; one column at 390/768, pairs at 1280. Finding fixed: the empty status line left a double gap above IDUB.
- police-after-paste: status wraps above IDUB; five boxes filled, password readable; "Saved now" under four boxes, never the password; Save row shown.
- timing-manual: no hours field; manual hint under the select.
- timing-delay: delay hint, "Hours to wait (delay option only)" = 7; beside the select at 1280, below at 390/768.
- leave-dialog: three buttons stacked at 390/768, one row at 1280, inside the viewport.

## Deviations
- 10 existing test files edited (cap 8); the two over (`test_remove_legacy_actions`, `test_required_stars`) were CI reds the orchestrator asked to fix.
- Save with "manual": disabled hours are not posted (as on main) and the server stores its default 24 (`admin.py`, outside 1100). Brief expected the stored hours to stay; the test pins today's behaviour. Follow-up decision.
- Unrelated text: status is "Type the rest ..." (step 4 allows it). No-JS fill and save lives in `test_host_police_letter_browser.py`.
- Leftover "apartment": `wizard.guest_link.message_template` (guest message), `customers.actions.field_apartments` (operator admin).
