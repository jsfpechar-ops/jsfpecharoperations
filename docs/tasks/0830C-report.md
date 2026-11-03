# 0830C report: Properties list and property detail (part C)

Status: blocked (tool-call cap reached; part C tests green, not committed)

## Files
- `App/app/templates/apartment_form.html`: editing header now uses `partials/settings_back_header.html` (back to /apartments + h1 title). Crumb, round back link and `h1.big` removed.
- `App/app/static/app2.css`: only inside the `0830C` markers. Covers: list sub-line hidden, table header hidden, bordered list container and phone cards, 16 px cell padding, help `?` summary with one marker (none) and body collapsed by default, guest card border and button gaps, editor label/input 12 px spacing, `p.ui-sub` / `.property-group-intro` / `.police-no-credentials` fine print hidden, back button 44 px, preview aside spacing, cancel/save gap.
- `App/tests/test_0830_airbnb_pages_browser.py`: appended `test_0830C_properties_regressions` at the end only (390 and 1280: sub-line, help collapsed, no native marker, no chevron, thead hidden, 1 px list border).
- `App/tests/test_0281_card_borders_browser.py`: one assertion updated from the old box-shadow ring (0px borders) to the new 1 px border look on `.props-phone .card.prop`.

## Tests
- `-k partC` (12 cases) and `test_0830C_properties_regressions`: 13 passed, 0 skipped.
- `test_0281_card_borders_browser.py`: 1 passed (after the assertion update).
- Old tests run before the last CSS round: 0530, 0531, 0534, 0250, 0199, 0251, 0284, 0300, 0399, 0525: 43 passed; 0281 failed (fixed above); 0284 failed (`/reservations?range=all`, no `a.chip` on that page; part D's file, not mine).
- `design_lint.py` (repo root): FAIL with findings in other parts' templates (invoice_*, entities, settings). Nothing listed for my files in the tail I read; not re-run after last change.
- Screenshots: `docs/tasks/screenshots-0830/partC-properties-{390,768,1280}.png`, `partC-property-detail-{390,768,1280}.png` (taken before the last coordinator-requested CSS round; retake one 390 shot per page after merge).

## Coordinator must-fix items (received mid-run)
1. Fine print under h1: hidden (`.props-head p.sub` display none). Done.
2. Two chevrons on help pill: native marker suppressed; svg chevron hidden; summary is a 24 px `?`-sized inline control. Done in CSS, not verified visually.
3. Help box expanded by default / bordered panel: body collapsed unless `open`; border removed when open. Verified by regression test (not open by default).
4. Beige table header and rows: thead hidden, container bordered 1 px radius 12, rows divided by 1 px lines. Not verified visually; the purple cover dot remains in the row.

## Deviations
- The help `?` is still a `details` element placed after the sub-line position in the template; I did not move it in the template, only restyled it.
- `apartments.html` not edited (all changes via CSS).

## Leftovers / owner steps
- `test_0284_states_browser.py` fails on `/reservations` (part D; check after part D lands).
- Full screenshot retake and visual check of items 2 to 4 on a real 390 and 1280 render.
- Orchestrator: bump cache key once at end.
