# 0803 report: help guide and Havel page on the v2 look

Status: review

## Files changed (not committed; orchestrator commits)
- App/app/templates/guide.html: v2 opt-in, head with h1 and sub line, Havel launcher moved into head, desktop TOC (nav.guide-nav) and phone closed details (details.guide-toc-phone) built from one link loop, sections get class card. All ids and guide-nav-link / guide-section classes kept.
- App/app/templates/havel.html: v2 opt-in, head, chat section wrapped in div.havel-v2.
- App/app/static/app2.css: new block "/* 0803 help guide + Havel page (v2) */" appended at the end.
- docs/design/catalog.json: added guide-head, guide-toc-phone, guide-toc-summary, havel-v2.

## Commands
- `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_0800=1 .venv/bin/python -m pytest tests/test_0800_v2_remaining_pages_browser.py -k "(guide or havel) and not guest" -q --tb=short -rs`
  tail: `12 passed, 78 deselected` (0 failed, 0 skipped). Guide and Havel all 6 widths.
- Existing tests: tests/test_guide.py, test_guide_coverage.py, test_havel_page.py, test_havel_browser.py, test_0391_havel_topics_first_browser.py, test_havel_topics.py
  tail: `32 passed`.
- `python3 scripts/design_lint.py` tail: `design lint: OK`.

## Screenshots
- docs/tasks/screenshots-0800/guide-390.png, guide-1440.png (full-page, very tall; checked the layout, not readable at this scale)
- docs/tasks/screenshots-0800/havel-390.png, havel-1440.png (checked: white card, topics inside, no blank-only area)
- Also guide-320/768/1024/1280, havel-320/768/1024/1280.

## Deviations
- The Havel launcher now sits in the page head (guide.html) instead of the secondary_actions block, since v2 pages use the head.
- TOC is rendered twice from one Jinja loop (desktop nav and phone details) because a closed details cannot be shown on desktop with CSS alone.
- Havel: added .havel-name 13px and .havel-chip min-height 44px below 1024 px (the test required it).
- guest-guide cases matched by -k were not run; they belong to brief 0802.

## Questions
None.

## Owner steps left
None. Commit on the branch (orchestrator).
