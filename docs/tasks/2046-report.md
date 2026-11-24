# 2046 report

Status: blocked

Done: steps 1 to 5 (anchors found, template, row menu, Go test, CSS back arrow). Step 6 partly done. Left: layout lint browser test (needs DB), screenshots, 390/768/1280 review.

## Files changed

- `go/internal/web/staydetail/templates/stay_detail.tmpl`: header "Generate invoice" / "Invoice N" button (`btn ghost ph-hide`); row-menu invoice item now `ph-only`.
- `go/internal/web/staydetail/layout_1862_test.go`: two new asserted substrings.
- `App/app/static/app2.css`: back arrow no longer hidden on desktop (`grid-row:1`); crumb, title, sub and header actions moved one row down (rows 2, 3, 4, 3).

Commits: `2046 step 2`, `2046 step 3`, `2046 step 4`, `2046 step 5`.

## Commands (last lines)

- `go test ./internal/web/staydetail/...`: `ok` (pass).
- `UBYHOST_REQUIRE_BROWSER=1 ... pytest tests/test_go_pages_layout_lint_browser.py`: ERROR at setup, `UBYHOST_TEST_DATABASE_URL not set`. 0 passed, 1 error. Not run.
- `pytest tests/test_host_geometry.py tests/test_design_guardrails_browser.py -rs`: stopped at first failure. `1 failed, 2 passed`. Finding: `guest-new` at 390 px, `a.ui-btn.ui-btn-quiet "Cancel"` tap target 43x44 px (`tap-target-small`). This page is not touched by 2046. Per brief section 8, not fixed. Not checked whether it fails on the base commit.

## Screenshots

None taken. Visual check and rule 7 screenshots are not done.

## Acceptance (section 7)

- [x] `go test` ok.
- [x] Header invoice button with Python's classes and links; row-menu item has `ph-only`.
- [ ] 1280 arrow visual check not done (no screenshot).
- [ ] 390 / 768 unchanged: not verified.
- [ ] Browser tests: 1 failure (guest-new, untouched page), 1 error (no DB URL). Not 0 skipped and passing.
- [x] Only section 3 files changed.

## Deviations

- Browser tests stopped per section 8 (failure on an untouched page). The layout lint test could not run without `UBYHOST_TEST_DATABASE_URL`.
- The brief's step 6 (screenshots) was not run.

## Questions

- Is `guest-new` Cancel tap-target failure known on the base commit? Owner or a later task should confirm.
- Which environment provides `UBYHOST_TEST_DATABASE_URL` for the layout lint test?

## Owner steps left

- Provide a test database URL, then run the layout lint test and the parity screenshots (`source scripts/e2e/parity_env.sh`, then `PARITY_GROUP=B PARITY_ONLY=reservation-detail-en`).
