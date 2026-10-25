# 0327 report

Status: blocked
Base: origin/main is 37ca614 (brief says 92646d3; branch was already merged with 0313). Steps 1 to 7 applied.

## Files changed
- App/app/havel.py: 13 GUIDE_ANCHORS entries (count now 30; `guide_connect_calendar` in PAGES: True)
- App/app/havel_topics.py: three key lists (where, when, connect)
- App/tests/test_havel_topics.py: asserted key now `guide.guest_links.find1`
- App/tests/test_guide_coverage.py: new, four tests
- .github/PULL_REQUEST_TEMPLATE.md: Help & guide checklist line
- docs/tasks/0327-report.md

## Commands (last lines)
- `tests/test_guide_coverage.py tests/test_havel_topics.py`: `1 failed, 7 passed`. Failure: `test_quick_help_answers_read_real_guide_text_in_every_language`, `('vi', 'guest_link', 'where', 'Nhấn chỗ ở.')` (11 chars, the Vietnamese guide step text is short).
- `tests/test_havel_engine.py tests/test_havel_page.py tests/test_guide.py tests/test_host_i18n.py`: `1 failed, 44 passed`. Failure: `test_havel_engine.py:73` expects `<guide lang="en">` for `system_blocks("vi")`; it now emits `<guide lang="vi">` (Vietnamese guide from 0326). Not touched by this brief.
- `scripts/context_lint.py`: `context lint: OK`

## Section 7
- [ ] test_guide_coverage: 3 of 4 pass; 4th blocked (see Questions)
- [x] quick help key fixes (test asserts answers; not visually checked)
- [x] guide ids added to PAGES (`guide_connect_calendar` True)
- [x] PR template line; lint OK

## Deviations
- Did not change the 11-char Vietnamese text or test_havel_engine.py (not in the brief's files).

## Questions
1. Vietnamese `guest_link.where` answer is one short step ("Nhấn chỗ ở."). Lengthen the vi guide text (0326 owner) or lower the test's 25-char threshold for short steps?
2. `test_havel_engine.py:73` should expect `<guide lang="vi">` for vi. Approve that one-line fix?
