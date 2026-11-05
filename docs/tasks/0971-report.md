# 0971 report (batch B13)

Status: blocked

Reason: 6c host row was not green. Run 1 gave 85 passed, 3 failed, 0 skipped. The 3 failures are in `test_host_wide_geometry_browser.py`, which is not on the known list, so no deselection applies. Those 3 pass when run alone, but the two full-row reruns died silently before the summary, so no clean full run exists.

## Changed files

- Commit `b5068b75` (step 1): 9 files, 353 insertions, 22 deletions. Code, test and static files only. Git status is clean.

## Commands

- 6c, host and guardrail row, run 1 (`/tmp/ubyhost-b13/host-row.log`): 85 passed, 3 failed, 0 skipped. Last lines:
  ```
  tests/test_host_wide_geometry_browser.py:1070: in test_tablet_rail_toggle_slides_the_overlay_only
      assert opened["width"] == 240 and opened["marginLeft"] == 64 and not opened["iconFlipped"], opened
  E   AssertionError: {'display': 'flex', 'width': 230.296875, ...}
  E   assert (230.296875 == 240)
  3 failed, 85 passed in 2154.15s (0:35:54)
  ```
  Failed: `test_direct_fee_backlinks_align_with_page_lane` (networkidle timeout), `test_sidebar_click_slides_the_rail_and_flips_the_toggle` (no transition), `test_tablet_rail_toggle_slides_the_overlay_only` (width 230 vs 240).
- 6c isolated rerun of the 3 tests (`/tmp/ubyhost-b13/rerun3.log`): 3 passed, 0 skipped.
- 6c file alone, `test_host_wide_geometry_browser.py` (`/tmp/ubyhost-b13/wide-geo.log`): 10 passed, 0 skipped.
- 6c full-row reruns (`host-row-rerun.log`, `host-row-rerun2.log`): both died silently after 42 and 10 progress characters, with no summary and no OOM in dmesg. Cause not found.
- 6d `pytest tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py`: 16 passed, 0 skipped.
- `python3 scripts/context_lint.py`: OK, with pre-existing open-brief WARN lines only.
- `git diff --check`: clean.
- 6a and 6b were not rerun in this session. The handover reports 170 of 170 passing.

## Deselections

- None. The known base failures were not deselected, because the full row was run without `--deselect`.

## Section 7 ticks

- [ ] Property save notice: not verified. Injected markup only; the Chromium tests pass per 6a/6b handover, not re-run here.
- [ ] Stay save toast: not verified.
- [ ] Cleaning `?notice=saved`, one dismiss: screenshots show one notice; click behaviour not re-tested.
- [ ] Copy link: screenshots show label swap to Copied/Zkopírováno. Size and live-region checks not re-run.
- [ ] Dismiss by pointer and keyboard: not verified.
- [ ] No stacking: not verified.
- [ ] Cleaning settings two cards and separate saves: screenshots show two cards and two Save buttons, all sizes. Database read-back not verified.
- [ ] 0 skipped: met for 6c rerun, 6d and the wide-geometry file. Not met for the full 6c run because of the 3 failures.
- [ ] Screenshots exist: all 20 named PNGs present and opened.

## Screenshot observations

- `cleaning-0971-settings-en-390.png`: two cards with red Save buttons "Save instructions" and "Save manual code". The fixed tab bar and the "Add a second way in?" sheet cover the manual-code heading and top of its input in this scrolled capture. Flag for review.
- `cleaning-0971-notices-en-390.png`: four notices with check circle, border and X. The long unbroken text wraps inside its box. The first notice has a dark outline here and in every notices shot, probably a focus ring; not verified.
- `cleaning-0971-list-notice-390.png`: one "Saved." row above the calendar.
- Other settings shots (en and cs, 768 and 1280): two cards, two Save buttons, no clipping.
- Copy shots (en and cs, 390, 768, 1280): label reads Copied / Zkopírováno, button size unchanged. In `cleaning-0971-copy-cs-1280.png` the button label is faint, probably mid-transition.

## Deviations

- The step 1 commit carries both the Codex trailer and the Claude attribution lines.
- Full 6c row not green; see Reason.

## Questions

- Why do the 3 wide-geometry tests fail under the full row and load, but pass alone?
- Why do full-row reruns die silently?

## Done / Left

- Done: steps 1 to 4 (6c run, 6d, lint, diff check, screenshots).
- Left: a clean full 6c run with 0 failures and 0 skipped; section 7 acceptance items marked "not verified" above; 6a and 6b re-run if the owner wants them confirmed here.

## Owner steps left

- None. Merge and deploy remain owner steps after review (brief, Owner steps).
