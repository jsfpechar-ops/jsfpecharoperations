# 0312 report: Havel page /havel

Status: blocked (screenshots not taken; all else passes)

Done: steps 1 to 8 (34 passed). Step 9: design guardrails browser test passed (0 skipped); a11y guard has no `havel` test (4 deselected). Left: screenshots at 390 and 1280 (not taken), then Status: review.

## Files changed
- App/app/host_i18n.py: havel.* copy en and cs (steps 1-2).
- App/app/routes/havel.py (new): route; `request.state.lang` replaced with `host_i18n.lang_from_request(request)` (commit 2384c53).
- App/app/main.py, App/app/templates/havel.html, _havel_thread.html, _havel_form.html (new), _icons.html, App/app/static/host2.css, App/app/templates/base.html, App/tests/static_versions.json, docs/design/catalog.json, docs/design/pages/havel.md (new), App/tests/test_design_guardrails_browser.py.
- App/tests/test_havel_page.py (new): simplified second test per step 8; `_post` and GET use `/havel?lang=en`.

## Commands (last lines)
- Step 8 run (after html.unescape fix): `34 passed in 2.11s` (test_havel_page, test_havel_engine, test_no_em_dashes, test_static_versions).
- Browser: `test_design_guardrails_browser.py -k every_host_page`: `1 passed, 9 deselected` (chromium-1243, 0 skipped). `test_a11y_guard_browser.py -k havel`: `4 deselected` (no havel test).
- Lint: `context lint: OK`.
- Earlier step 8 run: `1 failed, 4 passed` (`test_off_limit_and_failure_show_the_fixed_sentences`, line 78: `assert "I don't know that, and I don't want to guess" in page`). The page has lang="en" but the sentence is not found. Probable cause: Jinja autoescapes the apostrophe to `&#39;`, so the assertion needs the escaped form or `html.unescape(page)`. Not verified.
- tests/test_host_i18n.py alone: `3 failed, 11 passed` (the 3 known pre-existing failures).
- Step 7 earlier: `design lint: OK`.

## Deviations
- Step 8 lang fix: `request.state.lang` was not set before `_t` ran; now `host_i18n.lang_from_request(request)`. Brief §8 said to ask; orchestrator instructed the fix.
- Test isolation: without `?lang=en` the page rendered in Vietnamese (language cookie or saved state leaked between requests in the test client). Pinned to `en` in the helper.
- Coordinator approved the apostrophe fix: `html.unescape` on the three page reads in test_off_limit (commit pending in this WIP).
- Step 4 check: `app.routes` items have no `.path`; used `app.openapi()` instead.

## Questions
1. Fix the apostrophe assertion (escape or unescape) in test_havel_page.py, then rerun step 8? Approve and I continue.
2. Confirm the 3 pre-existing test_host_i18n failures are accepted.

## Owner steps left
None until steps 8 to 9 are done.
