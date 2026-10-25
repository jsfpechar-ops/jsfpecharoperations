# 0317 report: Guide: Cleaning, Guest links and PIN, Stays and calendars

Status: review

## Files changed

- App/app/guide_i18n.py (en and cs keys, 57 each)
- App/app/templates/guide.html (sections list, stays additions, cleaning and guest_links sections)
- App/tests/test_guide.py (section list)
- App/tests/test_guide_browser.py (SECTIONS)
- docs/tasks/screenshots-guide/guide-cleaning-390.png, guide-guest_links-390.png, guide-stays-390.png (new)
- docs/tasks/0317-report.md (this file)

## Commands (last lines)

- `pytest tests/test_guide.py -q -k same_keys`: `1 passed, 2 deselected`
- `pytest tests/test_guide.py -q --tb=short -x`: `3 passed`
- `pytest tests/test_guide_browser.py -q -rs`: `2 passed`, 0 skipped
- `pytest tests/test_guide.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py -q --tb=short -x`: `30 passed, 1 warning`
- `python3 scripts/context_lint.py`: `context lint: OK` (warning: 19 commits touched App/ after last status.md update; orchestrator to update status at review)

## Section 7 acceptance

- [x] Cleaning and Guest links and PIN sections in /guide, each with what, when, numbered steps, and "If something goes wrong".
- [x] Stays & calendars has `#connect-calendar` and `#add-stay` with steps and a trouble list; the four old paragraphs are unchanged.
- [x] en and cs have the same keys; no dashes; three screenshots looked at; browser tests 0 skipped.

## Screenshots

- guide-cleaning-390.png: heading, paragraphs, numbered steps and trouble list all visible, nothing cut off.
- guide-guest_links-390.png: heading, How to do it and Change the PIN steps, trouble list visible.
- guide-stays-390.png: the two new headings with numbered steps and trouble list below the old paragraphs.

## Deviations

- Insertions were made by matching text anchors, not line numbers: the brief's line numbers had shifted (for example the stays paragraph is at line 68 in guide.html, not 54). Content is as specified.
- The browser test used chromium-1243 (per the orchestrator note), not chromium-1194.
- Step 10 screenshots were committed as a separate commit ("0317 step 10 screenshots"). Tracked guide-finding and guide-glossary pngs that the test rewrote were restored, not committed.
- Copy contains no "guide." outside "/guide"; "this page" and "Help" were not needed.

## Questions

None.

## Owner steps left

1. On your phone, follow "Add a stay by hand" and "Guest links and PIN" step by step on staging. Say where a step does not match the screen.
2. Read the Cleaning section. If your cleaner uses the shared link, check that "shown only once" matches what you saw.
