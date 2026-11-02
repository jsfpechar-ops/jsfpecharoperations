# 0528 report: stay page on the v2 shell, part 1

Status: blocked (rule 7 screenshot not taken; see Questions)
Branch: task/0528-v2-stay-detail. Commits: fac2c5da, ae50a808, 6986b780, 4bb6821d (step 1 and 3 parts), 8c7ae2ea (step 2), 641cf563 and the catalog commit (step 3). No push, no PR.

## Files changed
- App/app/templates/reservation_detail.html: guests section rebuilt (table on computer, list on phone), `guest_state` macro, count button and link-window line under the h2, claim line as `.card`.
- App/app/host_vi_i18n.py: `stay.detail.facts.nights` ("Đêm").
- App/app/static/app2.css: `/* 0528 stay page */` block extended (guest table and list show/hide, guest header row).
- App/app/static/host2.css: all `.guest-card*` and `.guest-cards` rules removed (0179 and 0525 blocks).
- App/app/templates/base.html: app2.css and host2.css keys 20261101-0528.
- App/tests/static_versions.json: `--write` (41 files).
- docs/design/catalog.json: removed guest-card entries (incl. guest-card-doc description), added the stay mockup classes to `classes`.

## Form count
`action="` total: 13 before, 13 after. `action="/reservations/`: 12 before, 12 after. Same forms.

## Commands
- `.venv/bin/python -m pytest tests/test_0525_stay_detail.py tests/test_design_stay_detail.py tests/test_overhaul.py tests/test_wp25_reported_bugs.py tests/test_static_versions.py -q --tb=line -rs`
  tail: `7 failed, 59 passed in 4.97s`, 0 skipped.
- `python3 scripts/design_lint.py`: OK (after catalog fix; first run had 80 T3 findings).
- `python3 scripts/context_lint.py`: OK.

## Failing tests (expected, old markup; not edited, 0529 updates them)
- test_0525: `test_door_code_is_in_its_own_section_not_in_the_now_panel` (no `id="now"`), `test_guest_row_shows_the_doc_type_label_and_never_the_document_number` (`guest-card-doc` gone), `test_header_copy_link_only_for_an_active_stay` (asserts index before `id="now"`).
- test_design_stay_detail: `test_stay_detail_has_the_v2_header_jump_tabs_and_one_coral_button` (`ui-ph-back`, `id="now"`, `class="btn` in main), `test_no_raw_style_or_legacy_control_in_the_template` (asserts no `class="btn`; the brief's mandated `.btn` markup conflicts).
- test_overhaul: `test_reservation_detail_shows_direct_guest_link` and `test_the_stay_page_reads_as_one_ordered_grammar` ("Next step" and `id="now"`).

## Deviations
1. Done: steps 1 to 4 (step 4 = commands and this report). Step 3 needed a second commit for the host2.css key, which the manifest writer required.
2. Guest table columns are the existing keys: Guest (`stays.table.guest`), Document (`stay.detail.guests.document`), Reporting (`stays.table.reporting`), not the literal Jméno / Doklad / Registrace.
3. The per-guest edit button is dropped (the row menu keeps "Edit details"). The guest facts list (birth date, citizenship, document number, purpose, residence, signature, entered by, staying) is no longer on the stay page; it stays on the guest edit page.
4. Guest rows show `guest.note` and validation issues as `<small>` under the name, as before.
5. The `ready` state renders as a plain `.pill` (no tone); restricted renders as `p-warn`.
6. Catalog: the 12 legacy entries for this template were not pruned (lean cleanup left for later).
7. The "Now" note text (`stay-command-note`) is not shown anywhere until 0529's police card.

## Questions
- Rule 7: no 390 px screenshot yet. A Playwright attempt through the `stay_actions_host` fixture failed on the cookie setup (scratch file in /tmp/shots0528, not in the repo). Owner or next executor: take one 390 px screenshot of `/reservations/{id}` before the PR.

## Owner steps left
- None until the PR. Merge only with `scripts/merge-pr-on-green.sh`.
