# 0366 report

Status: review. Executor: Sonnet. Tests only; no app file changed.

## Failures
- `test_property_create_browser.py::test_create_page_is_short_and_has_each_field_once`: stale. 0277 step 1 (313d2d0) added the closed "How does this work?" `<details class="ui-how" data-how="property">` to `host_page.html`, and 0277 set `how_key` on `apartment_form.html`. Test now allows only that one fold; any other `<details` still fails.
- `test_property_navigation_browser.py::test_three_views_four_groups_one_editor_and_unique_ids`: stale. 0284 step 2 (4ee708d) added `data-setup-status` to the readiness `<details>` and the `fee-more` fold in the shared `_stay_fee_fields.html` partial (council fold, already excepted in the test comment). Allowlist updated for both exact tags.

## Results (Chromium, 0 skipped)
- create browser: 13 passed (twice)
- navigation browser: 12 passed (twice)
- guardrails + a11y browser: 14 passed

## Files changed
App/tests/test_property_create_browser.py, App/tests/test_property_navigation_browser.py, docs/tasks/0366-report.md, docs/tasks/0366-property-pages-browser.md (status).
No template/CSS change, so no screenshot.
