# 0793 report: Domovní kniha (/housebook) on the v2 look

Status: blocked

## Files changed (not committed, per the orchestrator's instruction)
- `App/app/templates/housebook.html`: rewritten on the v2 shell (`v2`, empty blocks, head with export menu and `/submissions` ghost button, filter card, `.card.stays-desk.housebook-scroll` table, `.stays-phone` cards, `ph-hide` on archived section and guide link). All values, labels, forms, menus and the PDF dialog are kept.
- `App/app/static/app2.css`: only the `/* 0793 housebook v2 */` block.
- `App/tests/v2_mockup.py`: one `housebook` PAGES entry (from the brief) and five `housebook:` BOX_OVERRIDES keys for text-dependent phone widths (h1 167.469px, `.stay .in b` 119.422px, `.stay .in small` 210px at 390).

## Tests
- `test_0710_v2_mockup_match_browser.py -k housebook`: 10 passed, 2 failed. Failures: horizontal page scroll at 1024 px and 1280 px (scrollWidth 1408 > innerWidth). Last lines:
  `horizontal page scroll: scrollWidth 1408 > innerWidth 1024`
  `2 failed, 10 passed, 106 deselected in 17.87s`
- Not run: `test_host_filter_panels_browser.py`, the other housebook test files, screenshots at 390 and 1440.

## Deviations
- Browser run stopped at the 25-tool-call checkpoint.
- Export menu moved into the head (brief). The filter toolbar keeps only the toggle and summary.
- Toggle and export buttons use `min-height:44px` (the 768 px tap-target finding).
- Added `_host_alerts.html` include in the body, because base.html skips alerts when `v2` is set.

## Questions
- None.

## Left to do
1. Find the element that makes the page 1408 px wide at 1024 and 1280 px. Probe with `getBoundingClientRect` on the page, then fix in the 0793 block only.
2. Rerun `-k housebook` until 12 passed, 0 skipped.
3. Update `App/tests/test_host_list_page_layout_browser.py:171` (expects `tabs.stays.register` on /housebook, the old tab strip) to the new markup, without weakening content assertions.
4. Run `test_host_filter_panels_browser.py` and the other housebook test files (`grep -ln '/housebook' App/tests/*.py`), `-rs`.
5. Screenshots at 390 and 1440 px.

## Owner steps left
- None yet.
