# 1103 report

Status: blocked
Branch: claude/project-thread-xhr13f (commits f1cc9b98 step 1, cb4f3b7b step 2, step 3 (this commit))

## Files changed

- `App/app/static/app2.css`: step 1 (focus ring, is-current colour, guest warn colour, pin and actions rules)
- `App/app/templates/base.html`: cache bump `20261111-1103a`
- `App/app/templates/_property_editor.html`: guest tile line 75 (PIN line, copy-both and copy-link buttons)
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`: key `property_page.guest_link.copy_both`
- `App/tests/test_0534_property_page_v2.py`: new test `test_guest_link_tile_shows_pin_and_both_copy_buttons`; line 189 changed to assert `data-guest-pin>PIN 482915<` in the tile (owner-approved via coordinator)
- `App/tests/test_host_property_controls_browser.py`: new test `test_1103_guest_link_tile_fits_and_stays_neutral` (widths 390, 768, 1280)

## Commands

- `.venv/bin/python -m pytest tests/test_0534_property_page_v2.py -q --tb=short 2>&1 | tail -30`: `19 passed in 2.49s`
- `.venv/bin/python -m pytest tests/test_host_property_controls_browser.py -q --tb=line -rs -k 1103 2>&1 | tail -30`:
  - 390: FAILED, `assert [69.5, ...] == []` (7 elements past the tile's right edge)
  - 768: FAILED, `assert [3.5, 3.5] == []` (2 elements past the tile's right edge)
  - 1280: PASSED
  - `2 failed, 1 passed`, 0 skipped
- Playwright 1.63.0 and Chromium were installed into `App/.venv` (dev environment only, same pin as CI; no repo dependency change). Without it the browser file skipped.
- Not run: the other §5 browser runs (test_host_geometry, test_layout_lint_browser, test_design_guardrails_browser, test_0251, test_0284) and `test_host_i18n*`, `test_privacy_first`. Stopped on the second failure of the browser test.

## Screenshots

`/tmp/claude-0/-home-user/4b49b8a3-a7dd-5c98-9a2a-f24713b28bb2/scratchpad/1103/` (390.png, 768.png, 1280.png, 1280-is-current.png). Requested folder was the scratchpad path, which is the same folder.

## UX notes (AGENTS rule 10)

- 390: tile is neutral (white, grey border, no red). The PIN line `PIN 123456` reads well. The "Copy link and PIN" button is wider than the tile and is cut off at the right edge. This is the failing overflow. "Copy link" wraps under it. Needs a fix (button width or wrap inside the tile); not in the brief.
- 768: tile neutral, button fits visually, but the browser check finds 3.5 px past the tile edge. Needs a look at the same button sizing.
- 1280 (is-current): the tile is neutral when scroll-spy adds `is-current` (grey border, white background, no accent). Three-column strip intact. No red pill seen. The Business details tile has a grey outline from existing styles, not from this change.
- Not checked: the red pill after a mouse click (the browser assertion (c) passed at 390 and 768 only because it runs after the overflow assertion, which failed first).

## Checklist (brief §7)

- [x] Step 3.1 new 0534 test (passes), line 189 updated
- [ ] Step 3.2 browser test: written, 2 of 3 widths fail
- [ ] §5 other browser runs and i18n/privacy runs not run
- [ ] Screenshots: taken; UX notes written above
- [ ] PR not opened (owner instruction)

## Deviations

- Overflow check (b) in the browser test uses `.sc-link *:not(.sr-only)`. A first version without the `:not(.sr-only)` filter failed at 390 px; with the filter the 390 px failure is unchanged, so the offending elements are visible (the "Copy link and PIN" button), not the hidden copy fields.
- Empty-PIN second half of the 0534 test was not added (PIN-set state only).

## Questions

- Owner or orchestrator to decide the fix for the "Copy link and PIN" button at 390 and 768 px (wrap, shrink, or a shorter label). I did not change CSS because the brief does not name it and the rule is to stop on a second failure.

## Owner steps left

- Fix the button width (new brief or a small CSS follow-up), then rerun `test_host_property_controls_browser.py -k 1103` and the other §5 runs with `-rs` (0 skipped).
- Write the PR UX notes after the rerun (AGENTS rule 10).
