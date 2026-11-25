# 2046 report

Status: review

Done: steps 1 to 6. Step 7 (report) written here.

## Files changed

- `go/internal/web/staydetail/templates/stay_detail.tmpl`: header "Generate invoice" / "Invoice N" button (`btn ghost ph-hide`, same classes as Python); row-menu invoice item now `ph-only`.
- `go/internal/web/staydetail/layout_1862_test.go`: two new asserted substrings.
- `App/app/static/app2.css`: back arrow no longer hidden on desktop; crumb, title, sub and header actions moved one grid row down.
- `docs/tasks/screenshots-2046/`: stay-2046-390.png, -768.png, -1280.png.

Commits: `2046 step 2`, `2046 step 3`, `2046 step 4`, `2046 step 5`, `2046 step 6` (screenshots).

## Commands (last lines)

- `go test ./internal/web/staydetail/...`: `ok`.
- `pytest tests/test_go_pages_layout_lint_browser.py -rs` (layout_test DB): `6 passed, 1 warning`. 0 skipped. Note: this file does not list the stay page; see the stay run below.
- `pytest tests/test_host_geometry.py tests/test_design_guardrails_browser.py -rs`: `1 failed, 12 passed`, 0 skipped. The failure is the known pre-existing `guest-new` 390 px `tap-target-small` (Cancel 43x44). Not fixed.
- Stay detail screenshot run (scratch pytest outside the repo, `go_web` fixture, `lint_go_paths` on `/reservations/{id}` at 390/768/1280): `FINDINGS []`, `1 passed`, 0 skipped.

## Per-width notes (Go stay detail)

- 1280: back arrow visible above the "Stays > Layout lint flat" crumb, no overlap. "Generate invoice" sits in the header next to the copy/menu actions. Title, status and guest card are clear of each other. No horizontal scroll.
- 768: back arrow visible. "Generate invoice" is not visible: `ph-hide` hides it below 1024 px, the same as Python (the brief asked to confirm it at 768; it is hidden by design, it is not a defect). The invoice item is in the row menu (⋯). No overlap, no horizontal scroll. The fixed bottom nav is captured mid-page in the full-page shot; a capture artifact.
- 390: back arrow visible. No header invoice button (correct, `ph-hide`). The invoice item is in the ⋯ menu (`ph-only`). Layout stacks cleanly, no overlap, no horizontal scroll. Same fixed-bottom-nav capture artifact as 768.

Python parity at 1280: the header button and arrow now match. Section order ("Stay" link rows, Police reporting card) differs by owner decision (option 1); not changed.

## Acceptance (section 7)

- [x] `go test ./internal/web/staydetail/...` ok.
- [x] Header invoice button with Python's classes and links; row-menu item `ph-only`.
- [x] 1280 arrow visible, no overlap.
- [x] 390 and 768 checked from the screenshots (no new overlap). The 390 and 768 screenshots are in the repo folder, not a side-by-side against the base commit.
- [x] Layout lint and guardrail browser tests: 0 skipped. One known failure (`guest-new`, pre-existing, untouched page).
- [x] Only section 3 files plus the screenshots folder changed.

## Deviations

- Run from the main checkout's `App/.venv` (the worktree has no `.venv`). Used `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/layout_test`. The parity scripts (`parity_tpl`, `parity_run`) were not touched, so `page_parity_visual.py` was not run. Screenshots were taken with a scratch pytest outside the repo instead.
- Scratch test (`scratchpad/test_2046_stay_shots.py`) inserts one `reservation` row (id 900002046) into the layout_test DB. Not committed.

## Questions

- Is the `guest-new` Cancel tap-target failure known on the base commit? Orchestrator said yes; not re-checked here.

## Owner steps left

- None for 2046. Merge goes through the usual PR path.
