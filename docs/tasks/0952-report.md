# 0952 report

Status: blocked

## Files changed
- docs/tasks/0952-report.md (this report only)

## Commands
- No code command run. Grep and read only: anchors in `App/app/templates/_property_editor.html`, `App/app/static/app.js` (2090-2097, 2125-2136, 2143, 2208-2247), `App/app/static/app2.css` (366-373).

## Deviations
Done: none. Left: steps 1 to 6.
Step 1 stopped before any edit (brief §8). Reason: the unsaved-changes guard in `App/app/static/app.js` (`form[data-unsaved-guard]`, listeners `input`/`change` on the form element, ~2090-2096 and ~2246-2247) only sees events bubbling through the form's DOM subtree. The door-code controls (`lock_checkin_hour`, `lock_checkout_hour`, `door_codes`, `lock_id`, hidden `door_codes_fields`, `door_code_section`) moved outside the form with `form="property-settings-form"` would still submit, but edits to them would no longer mark the form dirty, so leaving the page would not warn. This is a silent regression that `test_host_unsaved_changes_browser.py` should catch.
Brief branch note: brief header says new branch `claude/0952-single-lock-section`; I stayed on `par-0952` as the executor instruction said.

## Questions
1. Approve a small guard change in `app.js` (also attach the `input`/`change` listeners to `document.querySelectorAll('[form="' + form.id + '"]')`), or keep door-code controls inside the form?
2. Step 2 (`openSection` for `#door-code` and `#smart-locks`) still needs its JS change; it was not applied.

## Owner steps left
None.

## Decision line for orchestrator
none (not applied).

## Next step
Orchestrator answers question 1. Then rerun step 1 from `App/app/templates/_property_editor.html` lines 230-285 and 424-438, and step 2 in `App/app/static/app.js` ~2125-2136.
