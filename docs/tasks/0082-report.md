# 0082 report: fee list and report detail

Start SHA 4dd10e0 (merged claude/quirky-lamport-9svmd1). Mode: combined staging lane, exact-patch gate lifted. Anchors `/stay-fees/{id}/pdf` and `/finalize` unchanged. No backend, route, fee engine or schema edits.

## What changed
- `stay_fees.html`: one summary line for the selected period ("2 of 3 properties set up"); a real Status column (it had no header); an Open report link per row (the row stays clickable); Not set up is a state pill with the existing Set up action, with em dashes instead of blank totals.
- `stay_fee_detail.html`: order is now identity/period and actions, totals, "Fix before saving" blockers (with the scope-ruling form inside), data-box/send panel, council payment, guests, adjustments. Blockers and totals precede the adjustment form. Guest decision form is a single macro rendered visibly (the folded `<details>` "Change" is gone). Variable-symbol hint is the 0093a `?` help (`field_label`, `aria-describedby="fee-vs-help"`). Manual sent/paid forms sit under a "Your records" heading. Inline style removed.
- `host.css`: one `/* 0082 */` block at the end. `host_i18n.py`: `# 0082` group, EN+CS (4 keys). `_components.html`: not touched (no new macro needed).
- Not reintroduced: the data-box shortcut. Untouched: stay_fee_setup.html, _stay_fee_fields.html.

## Unchanged by design
Form names, actions, CSRF fields, finalize/adjustment/decision/sent/paid handlers, PDF/CSV links, frozen snapshots, arithmetic, "Payment details ready" meaning.

## Deviations
- Fix links still go to `/apartments/{id}#stay-fee-settings` and `/entities` (the 0077 canonical editor does not exist yet). Return to the exact report period needs a handler change in `routes/stay_fees.py`, outside §3; left for 0077.
- Rate-0 properties appear as Not set up with the existing action (no change).

## Tests (from App, staging/mock/REQUIRE_BROWSER)
- New `tests/test_host_fee_navigation.py`: 4 passed (ordering, blockers, Fix link, forms present, no `<details>` in guests, help wiring, geometry at 360/390/1280 EN/CS for list, blocked detail, saved detail).
- All `test_stay_fee*.py`, `test_host_copy_corrections.py`, `test_host_i18n.py`: pass.
- `test_host_wide_geometry_browser.py`: 3 failures (`test_host_wide_lanes_align`, `test_stay_row_actions_fit_midwidth_lanes`, `test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned`), identical on the untouched base and listed in the 0087 baseline file; stays-row related, not fees.
- ruff (E9,F63,F7,F82,F401,F841): clean. No skips.

## Evidence
`docs/tasks/0082-evidence/` (18 PNGs: list, detail-blocked, detail-saved x EN/CS x 360/390/1280, synthetic data). Not measured: widths to 2048 and collapsed rail (only the pre-existing wide test covers them; fee pages not added there).

## Owner steps
Review staged pages; 0077 should add the period-aware return link.
