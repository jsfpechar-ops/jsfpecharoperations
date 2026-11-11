# 1130 report

Status: blocked (review is possible, but the layout guard is not green; see Questions)
Branch: claude/project-thread-xhr13f (commits f1cc9b98 step 1, cb4f3b7b step 2, step 3 commits 4a49c2f9, 158bbb96, 69b6ff18, plus this commit)

## Files changed

- `App/app/static/app2.css`: step 1 (focus ring, is-current colour, guest warn colour, pin and actions rules); overflow fix: two rules after the `.sc-actions` rule (`.sc-link .sc-actions` fills the tile, `.btn` wraps inside it)
- `App/app/templates/base.html`: cache bump `20261111-1130b`
- `App/app/templates/_property_editor.html`: guest tile line 75 (PIN line, copy-both and copy-link buttons)
- `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`: key `property_page.guest_link.copy_both`
- `App/tests/test_0534_property_page_v2.py`: new test `test_guest_link_tile_shows_pin_and_both_copy_buttons`; line 189 asserts the PIN is in the tile (owner-approved)
- `App/tests/test_host_property_controls_browser.py`: new test `test_1130_guest_link_tile_fits_and_stays_neutral` (390, 768, 1280)

## Commands (last lines)

- `.venv/bin/python -m pytest tests/test_0534_property_page_v2.py -q --tb=short -x 2>&1 | tail -30`: `19 passed in 2.58s`
- `.venv/bin/python -m pytest tests/test_host_property_controls_browser.py -q --tb=line -rs -k 1130 2>&1 | tail -30`: `3 passed, 10 deselected in 8.52s` (0 skipped; checks overflow, no outline after click, is-current colour)
- `.venv/bin/python -m pytest tests/test_host_property_controls_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py tests/test_0251_tablet_browser.py tests/test_0284_states_browser.py -q --tb=short -x -rs`: stopped at `test_every_host_page_passes_the_layout_guard`: `1 layout findings {'tap-target-small': 1}`, `guest-new 390 open: a.ui-btn.ui-btn-quiet "Cancel", 43, 44`. `1 failed, 19 passed in 343.08s`
- Same files without `-x` (host_geometry, layout_lint, 0251, 0284, design_guardrails): `1 failed, 19 passed in 321.87s`. The only failure is the same guest-new "Cancel" finding.
- `.venv/bin/python -m pytest tests/test_host_i18n*.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`: `19 passed, 1 warning in 9.89s`

Playwright 1.63.0 and Chromium are installed in `App/.venv` (dev only, same pin as CI).

## Screenshots

`/tmp/claude-0/-home-user/4b49b8a3-a7dd-5c98-9a2a-f24713b28bb2/scratchpad/1130/` (390.png, 768.png, 1280.png, 1280-is-current.png), retaken after the fix.

## UX notes (AGENTS rule 10)

- 390: tile neutral (white, grey border, no red). "PIN 123456" reads well. "Copy link and PIN" now wraps to two lines inside the tile; "Copy link" sits quiet below it. Nothing cut off. The three-column strip becomes two columns on this width; it is intact.
- 768: tile neutral, both buttons inside the tile; browser overflow check passes.
- 1280 (is-current): with scroll-spy `is-current` the tile stays neutral (grey border, white background, no accent). Three-column strip intact. The Business details tile's outline is an existing style, not part of this change.
- No outline after a mouse click at 390, 768 or 1280 (browser check c passes).

## Checklist (brief §7)

- [x] Step 3.1 0534 test (19 pass)
- [x] Step 3.2 browser test at 390, 768, 1280 (3 pass, 0 skipped)
- [ ] §5 browser set: host_geometry, 0251, 0284, layout_lint pass; design_guardrails has one finding outside this change (below)
- [x] i18n and privacy runs pass
- [x] Screenshots taken and read
- [ ] PR not opened (owner instruction)

## Deviations

- The brief's empty-PIN second half of the 0534 test was not added.
- Browser overflow check (b) uses `.sc-link *:not(.sr-only)`.
- Playwright installed into the local venv only (not a repo dependency).
- The overflow fix in CSS is an extra two rules, per the coordinator's decision.

## Questions

- `test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard` fails on `guest-new` at 390 px: the "Cancel" link (`a.ui-btn.ui-btn-quiet`) is 43 px tall, the target is 44 px. This page is not in the brief's files and none of the new selectors match it, so it is probably a pre-existing finding. Not verified against the base commit. Per AGENTS rule 10, the guard must be green before merge, so this needs a decision: fix it in a follow-up brief, or confirm it already fails on main.

## Owner steps left

- Decide the guest-new "Cancel" target finding above (follow-up brief or confirm pre-existing).
- After that, open the PR as a draft with the UX notes above and the design-system checklist ticked. Merge only with `scripts/merge-pr-on-green.sh`.
