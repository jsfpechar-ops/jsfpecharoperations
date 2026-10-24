# 0342 report: guest guide pages (executor)

Status: review

## 1. Files changed

Code and tests (all steps of brief §3 applied exactly):
- App/app/routes/guest_guide.py (new)
- App/app/templates/guest_guide.html (new)
- App/app/templates/guest_guide_card.html (new)
- App/tests/test_guest_guide_pages.py (new)
- App/app/host_i18n.py (edit: _GUEST_GUIDE_STRINGS, en and cs)
- App/app/main.py (edit: import and include_router)
- App/app/templates/apartment_form.html (edit: one tab link, no data-property-tab)
- docs/design/catalog.json (edit: two enforced_templates entries)
- App/tests/test_design_guardrails_browser.py (edit: one ROUTES entry)
- docs/tasks/0292-report.md, docs/tasks/0292-guest-guide-pages.md (status line)

## 2. Commands (last lines)

- `pytest tests/test_guest_guide_pages.py tests/test_guest_guide.py -q`: `20 passed, 1 warning in 3.60s`
- `pytest tests/test_*_i18n.py ... tests/test_design_*.py -q -rs`: `3 failed, 180 passed`. The 3 failures are the known environment failures in tests/test_host_i18n.py (test_language_endpoint_sets_cookie_and_rejects_open_redirects, test_a_signed_in_dashboard_keeps_vietnamese, test_language_endpoint_accepts_vietnamese). No SKIPPED lines.
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_design_guardrails_browser.py -k every_host_page -rs`: `1 passed, 9 deselected`, no skips.
- `python3 scripts/design_lint.py`: `design lint: OK`
- `python3 scripts/context_lint.py`: `context lint: OK`

## 3. Acceptance (§7)

- [x] Diff lists the nine §3 files plus the report.
- [x] 20 guide tests pass; copy and design rows pass except the 3 known i18n failures; layout guard passes with 0 skipped.
- [x] Both lints OK.

## 4. Deviations

- Done: steps 1 to 10 (all). Left: 390 px screenshots (see Questions).
- Commit: one commit at the end, not one per step, as the lead asked.
- Screenshots: the in-process render (TestClient HTML loaded into Playwright) returned the login page, not the guide, because the session did not carry over. The scrollWidth 390 / clientWidth 390 numbers came from that login page, so they are not evidence for the guide pages. Not claimed as passed.

## 5. Questions

- Session setup for the screenshot script: login_as does not put a usable session cookie into the TestClient jar for Playwright. A reviewer or the next session should take the two 390 px screenshots (guide and card) on a real running server.

## 6. Owner steps left

1. Review the PR once a fresh executor (or you) has taken the 390 px screenshots of the two pages.
2. Merge when CI is green.

## Review (orchestrator, 2026-10-24)
- Code identical to the brief's verified files. 390 px screenshots taken on a live server by a second Haiku run: list and card, scrollWidth 390 = clientWidth 390, nothing overlaps (the bottom tab bar sits mid-page only because the capture is full-page).
