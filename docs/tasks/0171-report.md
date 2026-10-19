# 0171 report

Status: blocked

## Files changed
- App/app/static/host2.css (step 1: 0169 rule now `outline: 2px solid var(--coral-600) !important; outline-offset: 2px;`), commit 8b6f394.

## Commands
- `python3 scripts/design_lint.py` : `design lint: OK`
- `pytest tests/test_a11y_guard_browser.py -k test_keyboard_focus_is_visible_and_not_covered` : 8 findings, unchanged after step 1 (`focus-obscured` 4, `focus-not-visible` 4).

## Diagnosis (not fixed)
- Date inputs (cleaning-from/to, stay_from/to): in the guard run, computed `outlineStyle: none`, `boxShadow: none`, and `document.activeElement.matches(':focus-visible') === false`. The 0169 rule needs `:focus-visible`, so it does not apply. A real Tab-key probe on /cleaning gave `:focus-visible` true, solid 2px, so the guard's focus path differs from a plain Tab (suspect: Chrome date-input inner fields, or focus set by the test's earlier click). Not resolved.
- A CSS fix using `input[type=date]:focus` was tried; the guard still reported the same 8 findings, so it was reverted.
- Signature file inputs (`input#new_signature_file`, `input#edit_signature_file`): the input is `sr-only` (template `_entity_business_fields.html:82`), 2x44 px at the label. `elementFromPoint` at its centre returns `BUTTON.btn` (the label), so `focus-obscured` fires. A `:has()` ring on the label did not clear it.
- app.css:1046 `input:focus { outline: none; box-shadow ... }` also applies to date inputs; not yet checked as a cause.

## Deviations
Done: steps 1 (committed). Left: steps 2 to 5. Step 2 did not reach a fix after two attempts; stopped per brief §8. A temporary diagnostic copy of the test was created and deleted; no test file is changed. host2.css key not bumped (step 3 not run). Nothing pushed; no PR opened.

## Questions
1. Should the date and file-input rings use `:focus` (show on mouse click too) instead of `:focus-visible`? Needed to pass the guard.
2. For sr-only file inputs, may the label carry the visible ring while the guard's obscured check is satisfied (for example by excluding `sr-only` inputs in the guard, which is a test change)?

## Owner steps left
None until the questions are answered.

## Update after 2b (Status: blocked)
Done: step 1 (8b6f394); step 2 partial (a85ece2): `.host-workspace input:focus-visible, .host-workspace input:focus` ring, label ring for `:has(+ input:focus-visible)`, and the allowed FOCUS_JS edit (hidden inputs: skip obscured, require label ring). File-input findings (new_signature_file, edit_signature_file) are now gone.
Still failing: 4 `focus-not-visible` on date inputs (cleaning-from/to, stay_from/to). Computed in the guard run: `document.activeElement` is the date input, but `matches(':focus')` is false, `matches(':focus-visible')` is false, outline `none`. Because `:focus` does not match, no CSS rule on `:focus` can add a ring. Likely a focus-state artifact of the guard's Tab sequence in Chromium (page not focused / focus inside the date input's inner fields), not a styling bug. Brief 2b item 2 says a guard bug means stop for that item. Owner or coordinator decision needed.
Not run: step 3 (key bump), step 4 (test suite), step 5 final commit. The 0169 report is committed as-is in the working tree (still `M`, not staged); include it in the final commit when resolved.
