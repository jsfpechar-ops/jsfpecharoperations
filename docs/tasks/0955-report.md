# 0955 report (chat 1 of 4)
Status: blocked

## Files changed
- App/app/templating.py (inline_flash_section from ?sec=, property page only)
- App/app/templates/_section_notice.html (new macro)
- App/app/templates/base.html (toast suppressed for inline section; ?v=20261104-0955a)
- App/app/templates/_property_editor.html (import, 7 notice calls, sec-* open conditions)
- App/app/routes/admin.py (_lock_property_return: sec=lock, #sec-lock; _lock_tab_url own branch: #sec-lock)
- App/app/static/app.js (initSectionNotice; ?v=20261104-0955a), App/app/static/app2.css (section-notice block)
- App/tests/test_smart_locks_page.py (line 189: anchor #door-code to #sec-lock), App/tests/static_versions.json, docs/design/catalog.json

## Commands (last 5 lines)
- test_smart_locks_page.py: `16 passed in 2.13s`
- test_static_versions.py + test_smart_locks_page.py: `19 passed in 2.33s`
- design_lint.py: 3 DESIGN findings (apartment_form airbnb-actions, setup_wizard req-star, section-note); same 3 on HEAD before step 3, not from 0955

## Old designs (checked in git)
- Toast: old `.toast-stack` was `position: fixed; bottom: 20px` centred (app.css:553, c7dab2b1). Viewport-fixed, so it can sit over the tab bar and help bubble. Inline banner chosen: confirmed.
- Save bar: 0851 (e4423c27) was sticky inside the form: Cancel text left, coral Save right, white bar. That is the look to keep. Pre-0851 `position:fixed; right:24px; bottom:20px` is not restored. Confirmed.
- Actual anchors: savebar at _property_editor.html ~352, form closes ~357, calendars and lock after it. Brief lines (~413) are stale.

## Deviations
- Step 1: Jinja macro import needs `with context`; used it.
- Step 2: calendars and lock notices sit in _property_editor.html fields-wrap, not the child partials.
- Step 2: `_lock_property_return` anchor now #sec-lock; one assertion updated (allowed). admin.py ~1402 and ~2414 still `#door-code` (not in brief).
- Commits signed Claude Haiku 5.5 (system attribution), not Sonnet 5.5.
- Done: steps 1 to 3. Left: steps 4 to 10.

## Questions
1. The fixed bottom toast is not restored; the inline banner replaces it. Right?
2. Should other pages' results get the same inline notice later?

## Owner steps left
None.

## Next step
Step 4 (Save row structure), chat 2: `grep -n "savebar\|</form>" App/app/templates/_property_editor.html`, then move the savebar after the last `</details>` with `form="property-settings-form"`.
