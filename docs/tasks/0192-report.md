# 0192 report

Status: review

## Files changed
- App/app/static/host2.css: `.ui-ph` margin-bottom at <=760 px is `var(--space-6)` (was `var(--space-4)`), so the gap above tabs is 16 px at every width
- App/app/templates/base.html, App/tests/static_versions.json: host2.css `?v=20261020-0191a`, sha256 updated

## Commands
- `cd App && .venv/bin/python -m pytest tests/test_static_versions.py tests/test_host_list_page_layout_browser.py -q --tb=short -x -rs | tail -30` -> `5 passed` (layout file), static tests passed
- `python3 scripts/context_lint.py | tail -30` -> `context lint: OK` (WARN lines only)

## Section 7
- [x] list layout rhythm test passes with 0 skipped
- [x] context lint passes (step 2): `context lint: OK`
- [ ] step 3 and step 4 pending

## Deviations
- Done: step 1. Left: steps 2 to 4 (in progress in this report).
