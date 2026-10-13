# 0080 report: stay detail organization

Start 00e5c4e (integration head, merged into this lane); end: see `git log`. Status: review. Dependency on 0079 waived; dashboard.html and reservations.html untouched.

## Changes
- `reservation_detail.html`: property line (link to the property) and a visible in-page jump row (Next step, Guests, Reporting, Stay settings) via local macro `stay_jump_nav` (_components.html is another lane's file; no shared primitive added). Guest facts split into two visible rows (identity: born, nationality, document/visa, purpose; stay: residence, stay dates, signature, entered by). Stay settings is now a visible `<section>` with an h2, no longer a closed `<details>` (rule: visible not folded); `#stay-quick-edit` anchor, class and every field/form unchanged. Placeholder "Copy guest form link" hidden on cancelled/archived stays (no link to offer).
- `host.css`: one `/* 0080 */` block. `host_i18n.py`: `# 0080` keys `stay.detail.nav.label`, `stay.detail.property` (EN+CS).
- New `tests/test_host_stay_detail_layout_browser.py` (EN/CS, 360/390/1280; no horizontal overflow, section order, nothing folded, facts visible, submit form action/CSRF/return_to intact).

## Not changed
All submit, claim, reopen, release, verify, archive, remove-empty-slot, hand-filing and quick-edit forms: same names, CSRF, targets, confirmations; only moved/grouped. `#file-by-hand` stays a `<details>` (pinned by test_wp28_ui_sweep; it is a filing confirmation form, so left alone, flagged for the owner). No admin.py change.

## Tests (from App, staging/mock/REQUIRE_BROWSER)
- New test: 1 passed, 0 skipped.
- All 47 test files mentioning `reservation_detail` or `/reservations/`: 707 passed, 24 failed. 5 failures are the baseline ones, identical on clean 00e5c4e (test_wp28_geometry calendar_remove, 3 in test_host_wide_geometry_browser, test_host_stay_actions_browser guest_link_copy). The 19 test_endtoend failures appear only in that combined ordering (shared state); test_endtoend alone: 28 passed. Not caused by the template.
- Full suite, ruff, context lint not run (lane scope limited).

## Evidence
`docs/tasks/0080-evidence/stay-detail-{en,cs}-{360,390,1280}.png` (synthetic data, UBYHOST_CAPTURE_0080=1). Widths up to 2048 and rail states not measured.

## Risks
Stay settings no longer collapsed, so the page is longer on mobile. 0079 can reuse `stay-jump` if a shared primitive is wanted.
