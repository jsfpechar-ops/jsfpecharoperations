# 1090 report: under-15 guests do not sign (guest form half)

Status: review

## Files changed

`App/app/routes/guest.py` (`_form_context` keys; the 422 echo), `templates/guest/form.html` (signature step), `static/signature.js` (`signatureWaived`, two guards, `initUnder15`), `static/guest.css` (one selector), `guest/base.html` and `_signature_script.html` (cache keys `20261111-1090`), `tests/static_versions.json` (two entries), `i18n.py`, `guest_uk_i18n.py` (five keys, six languages), new `tests/test_under15_signature_1090.py` (23 tests) and `tests/test_under15_signature_1090_browser.py` (10 tests), nine screenshots, and one edit in `tests/test_guest_browser_e2e.py` (see Deviations).

## Commands

- A: `110 passed in 4.45s`.
- Browser, one file at a time, `UBYHOST_REQUIRE_BROWSER=1`, 0 skipped: `test_under15_signature_1090_browser.py` 10 passed; `test_guest_browser_e2e.py` 55 passed; `test_guest_child_visa_1079_browser.py` 14; `test_guest_form_input_browser.py` 9; `test_guest_form_draft_1087_browser.py` 10; `test_guest_guide_browser.py` 2; `test_guest_guide_table_browser.py` 2; `test_guest_leon_browser.py` 9; `test_guest_ocr_geometry_browser.py` 9; `test_guest_scan_feedback_browser.py` 25; `test_a11y_guard_browser.py` 4; `test_host_geometry.py` 2; `test_layout_lint_browser.py` 4 passed.
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: All checks passed.
- `python3 scripts/context_lint.py`: `context lint: OK` (three older warnings, none from 1090).
- Not run: the test-map row `tests/test_guest_*.py` as one command (the browser files of it were run one by one; the non-browser guest files other than those in A were left to CI).

## Acceptance (section 7)

- [ ] 1089 on main and merged in: 1089 was not on main yet; its branch head 7e6ce0e1 is merged in (see Deviations).
- [x] Under 15: note instead of the pad; adult and role radios; nothing required.
- [x] Adult with pending children: sentence and two role radios under the pad; links on send.
- [x] 15 to 17 and other adults: the step as today (6c, 6g: wrapper has zero box, unwrapping moves nothing).
- [x] Without JavaScript a child's form sends and can carry the role.
- [x] A role tick survives a 422, not a language switch; only whitelisted values echoed.
- [x] Copy in six languages; one CSS selector; cache keys bumped; `static_versions.json` regenerated.
- [x] Browser tests 0 skipped; layout lint green; nine screenshots.
- [ ] `git diff --stat origin/main` touches only section 3 files: also `test_guest_browser_e2e.py`, and 1089's files until 1089 is on main.

## Screenshots (`docs/tasks/screenshots-1090/`, opened)

- `adult-390/768/1280.png`: the signature step as today: help line, pad, Clear, review list. Nothing added.
- `child-note-390/768/1280.png`: no pad; the note, the sentence with "Kid Testovic", two role rows in the tick-box look, "Parent or legal guardian" chosen. No sideways scroll.
- `adult-signs-for-390/768/1280.png`: pad with a drawing, then the sentence naming the child and the two role rows. The sentence sits close under the pad (about 8 px); `Guest.check_layout` and the layout lint do not flag it, and no CSS rule was added.

Design-system checklist: no new class, no inline style, no new colour; 390/768/1280 opened; lint green 0 skipped; all six languages added together; no em dash.

## Deviations

1. Step 0: 1089 was not on main, so `origin/claude/1089-under-15-signature` (7e6ce0e1) was merged instead, as the orchestrator instructed. No conflicts.
2. The catalog formats with `%(names)s`, not `{names}`. The keys are stored with `%(names)s`; the template passes `names='{names}'` for `data-template`, which the script fills.
3. The posted values never reach `_form_context` (its `values` are the text fields only), so the 422 block also sets the three `selected_*` context keys from the whitelisted values, next to the echo.
4. Both lists skip archived guests (1089's archived-adult rule).
5. `tests/test_guest_browser_e2e.py` (not in section 3): `fill_form` signed for every guest, and the pad is now hidden for the child born 2015. It signs only when the pad is shown and asserts the note otherwise. Without it 16 e2e tests fail.
6. "Host preview has neither block" is tested as people the host entered (no owned id); no separate preview route renders this form.
7. In the adult's sentence the child's name shows as stored (capitals), in the child's own sentence as typed.

## Questions

- Owner design call (section 1), kept: when the adult signed first, the adult confirms on the child's step with a role tick and nothing is drawn again. The link keeps its own time and wording version. Overrule it if the adult should draw again.
- Should the sentence under the pad get more space? That needs a CSS rule outside this brief.

## Owner steps left

Merge 1089 first, then this branch's PR with `scripts/merge-pr-on-green.sh`.

## Attempt 2 (review findings)

- B1: `origin/main` merged (1089 and 1091 now on main); `guest.css` and `signature.js` keys are `20261111-1090b`, `static_versions.json` regenerated.
- B2: four rules in `guest.css` (orchestrator allowed, over the one-selector limit): 16 px above `#sign-for-children`, 12 px between role rows, 16 px between the two groups, 12 px above the choice error. Plain px, as the rest of `guest.css`; it has no spacing tokens. Test 6g asserts row gaps and the gap under the pad are 12 px or more at 390, 768, 1280.
- S1: `#sign-for-who` (labelled by "Signing adult") and `#sign-for-role` (labelled by the sentence) are each a `radiogroup`; `#sign-for-child` no longer is one.
- S2: a valid role, no `signed_by` and more than one candidate returns the 422 with `sign_for_who_missing` on `signed_by` (six languages). This is a second edit in `guest_form_save`; the lists moved into `_under15_lists`, shared with `_form_context`.
- N1: `fillName` replaces with a function.
- New screenshot `child-two-adults-390.png`: the 422 with two adult rows, the red line "Choose the adult who is signing." under them, then the role rows; all rows 12 px apart. `adult-signs-for-*`: the sentence now clears the pad by 16 px. The top summary link for the new error has no field id to jump to.
- Commands, one file at a time, 0 skipped: `test_under15_signature_1090.py` 31 passed; `test_under15_signature_1090_browser.py` 11; `test_guest_browser_e2e.py` 55; `test_a11y_guard_browser.py` 4; `test_layout_lint_browser.py` 4; `test_guest_form_draft_1087_browser.py` 10; `test_static_versions.py` 3; `test_guest_title_1091_browser.py` 10; `test_guest_languages.py` 47; ruff: All checks passed.
- Acceptance: "1089 on main and merged in" now holds. `git diff --stat origin/main` still includes `tests/test_guest_browser_e2e.py` (deviation 5).
