# 0327 report

Status: review
Base: origin/main is 37ca614 (brief says 92646d3; branch was already merged with 0313). Steps 1 to 7 applied, plus review fixes.

## Files changed
- App/app/havel.py: 13 GUIDE_ANCHORS entries (count now 30; `guide_connect_calendar` in PAGES: True)
- App/app/havel_topics.py: three key lists (where, when, connect)
- App/app/host_vi_i18n.py: review fix, `guide.guest_links.find2` vi text lengthened
- App/tests/test_havel_topics.py: asserted key now `guide.guest_links.find1`
- App/tests/test_havel_engine.py: review fix, vi expects `<guide lang="vi">`
- App/tests/test_guide_coverage.py: new, four tests
- .github/PULL_REQUEST_TEMPLATE.md: Help & guide checklist line
- docs/tasks/0327-report.md

## Commands (last lines)
- `tests/test_guide_coverage.py tests/test_havel_topics.py -q`: `8 passed in 1.72s`
- `tests/test_havel_engine.py tests/test_havel_page.py tests/test_guide.py tests/test_host_i18n.py -q -rs`: `45 passed, 1 warning in 2.19s`
- `scripts/context_lint.py`: `context lint: OK` (run before the review fixes)

## Section 7
- [x] test_guide_coverage: 4 passed
- [x] quick help key fixes (answers asserted by tests; not visually checked)
- [x] guide ids added to PAGES (`guide_connect_calendar` True)
- [x] PR template line; lint OK

## Deviations
- Coordinator decision 1: `guide.guest_links.find2` vi text changed from "Nhấn chỗ ở." to "Nhấn hoặc bấm vào chỗ ở của bạn." (the 25-char threshold kept).
- Coordinator decision 2: test_havel_engine.py:73 now expects `<guide lang="vi">` for vi (0326 made the vi guide real).
- origin/main is 37ca614, not 92646d3 as the brief says.

## Questions
None open.
