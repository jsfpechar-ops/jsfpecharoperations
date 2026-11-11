# 1103 report

Status: blocked
Branch: claude/project-thread-xhr13f (commits f1cc9b98 step 1, cb4f3b7b step 2, step 3 partial)

## Files changed

- `App/app/static/app2.css`: step 1 (focus ring, is-current colour, guest warn colour, pin and actions rules)
- `App/app/templates/base.html`: cache bump `20261111-1103a`
- `App/app/templates/_property_editor.html`: guest tile line 75 (PIN line, copy-both and copy-link buttons)
- `App/app/host_i18n.py`: key `property_page.guest_link.copy_both` (en, cs)
- `App/app/host_vi_i18n.py`: same key (vi)
- `App/tests/test_0534_property_page_v2.py`: new test `test_guest_link_tile_shows_pin_and_both_copy_buttons` appended (passes)

## Commands

- `python3 -c "import ast ...host_i18n.py host_vi_i18n.py"`: prints `PARSE_OK`
- `.venv/bin/python -m pytest tests/test_0534_property_page_v2.py -q --tb=short -x 2>&1 | tail -30`:
  `FAILED tests/test_0534_property_page_v2.py::test_0545_guest_card_shows_pin_and_copy_button`
  (`assert "482915" not in _guest_strip(html)`, line 189). `1 failed, 16 passed in 3.13s`.
  The new test was not reached because `-x` stopped at the failure. It was run separately and passes.
- Browser file (step 3.2), §5 runs 2 and 3, screenshots: not run. Stopped on the failure above.

## Checklist (brief §7)

- [x] Step 3.1 new 0534 test written (passes)
- [ ] Old test 0545 conflicts with the feature (see Questions)
- [ ] Step 3.2 browser test not written
- [ ] Test runs in §5 (runs 2 and 3) not run
- [ ] Screenshots at 390/768/1280 not taken
- [ ] PR not opened (owner instruction)

## Deviations

- Done: steps 1 to 2, and step 3.1 (new 0534 test). Left: the 0545 conflict, step 3.2 (browser test), test runs 2 and 3, screenshots, UX notes.
- The brief's empty-PIN second half was not added. The new test covers only the PIN-set state.
- Brief names branch `task/1103-guest-link-tile-pin`. Worked on `claude/project-thread-xhr13f` as instructed.
- CSS line 2642: the brief's quoted anchor did not match because the line has the `body.v2 nav.prop-strip` prefixes. The selector list was replaced with the brief's intended list.

## Questions

- Test `test_0545_guest_card_shows_pin_and_copy_button` (line 189) asserts `"482915" not in _guest_strip(html)`. The brief makes the PIN visible in that tile, so the assertion now fails by design. Options: (a) change line 189 to assert the PIN is shown in the tile (`data-guest-pin>PIN 482915<`), or (b) leave it and reconsider the brief. I did not edit it because the brief says not to weaken existing tests. Please decide; option (a) is the likely fix.
- No `App/.venv` issue now: `.venv` exists and runs.

## Owner steps left

- Decide the 0545 question above.
- After that, the executor (or owner) runs step 3.2, the §5 browser runs with `-rs` (0 skipped), and takes the three screenshots with UX notes before any merge (AGENTS rule 10).
