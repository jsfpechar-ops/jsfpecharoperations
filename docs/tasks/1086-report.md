# 1086 report

Status: review (two findings need an `app.js` or flow decision; see Deviations)

## Files
- `App/tests/test_host_police_letter_browser.py` (new, 12 tests), `App/tests/test_host_police_letter_guard_browser.py` (new, 3 tests)
- `App/app/static/app2.css` (2 rules), `App/app/templates/_property_editor.html` (wrapper `div.police-letter-helpers`), `App/app/templates/base.html` (`app2.css?v=20261110-1086b`), `App/tests/static_versions.json`
- `docs/tasks/screenshots-1086/` (9 PNGs)

## Commands
1. Section 6.1 (browser, `-rs`): 106 passed, 1 failed, 0 skipped. The failure is `test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard`: `guest-new 390: tap-target-small "Cancel" 43 < 44`, also on clean main, not a page of this brief. The four `field-button-misaligned` findings for "Read the letter" that main also has are fixed here.
2. Section 6.2: 252 passed.
3. Section 6.3 (`test_0710`): passed, 0 skipped (run together with part of 6.1: 222 passed, 1 failed as above).
4. `design_lint.py`: OK. `context_lint.py`: OK. ruff: all checks passed.

## Acceptance
- [x] Paste, check block, 400 refusal and confirmed save work with Turbo loaded and with JavaScript off, at 390, 768, 1280.
- [x] No password: no client built. With one: exactly one, read-only calls, plain flash.
- [x] Discard warning for edits or a typed password; cancel keeps the page. Check-answers page has `data-dirty-start="1"` (but see Deviation 1).
- [x] Password and pasted marker never in the page.
- [x] Geometry green; layout lint green, no new `ALLOW`; nine screenshots; checklist ticked (in the PR).
- [x] `test_police_letter_flow.py` untouched and green. The flush rows of 1085 are restored at 768 and 1280.
- [x] 0 skipped; only section 3 files; key bumped.

## Screenshots (`docs/tasks/screenshots-1086/`)
- `find-390/768/1280`: figure readable, rows flush, legend wraps, no sideways scroll.
- `check-390/768/1280`: three rows with source and tick, focus ring on the first tick, no password row.
- `lint-check-390/768/1280`: full page of the same state; no overlap; no Save row before the first tick.
- Layout lint shots of the property page open on Basic details at 768 and 1280, so this card was judged from the shots above.

## Deviations
1. **Fix needs `app.js` (not done, section 8):** `data-dirty-start="1"` is read only on the first `input`/`change`. Before the first tick the Save row is hidden and `beforeunload` does not warn. The tests tick once, then assert the block of Save by `required` and the warning.
2. **No Turbo in-place render:** "Read the letter" is a full page load to `/police-letter` (422). The block shows and is in view; the tests assert Turbo is loaded, not an in-place render.
3. Two CSS changes, so the key went `1086a` then `1086b`.
4. Screenshots are written only with `UBYHOST_SHOTS_1086=<dir>`, so a plain test run does not rewrite them.

## Questions
- Should a new brief make the check-answers page dirty at load (Save row and leave warning before the first tick)?
- Who owns the `guest-new` Cancel 43 px finding on main?
