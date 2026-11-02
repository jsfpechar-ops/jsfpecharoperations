# 0526: Stays list on the v2 shell: computer = mockup "stays" view, phone = mockup "pobyty" screen
Status: todo
Depends on: 0522, 0523, 0718 (all on the base) | Base commit: claude/project-thread-y2e49a | Branch: task/0526-v2-stays-list
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Move `/reservations` onto the v2 shell (like `/` in `dashboard.html`) and rebuild its markup 1:1 from the approved mockups: computer from `docs/design/mockup/ubyhost-redesign-v2.html` `<section data-v="stays">`, phone (< 1024 px) from `docs/design/mockup/ubyhost-phone-v1.html` `<section data-s="pobyty">`. Owner rule: match 1:1, using the mockup's own class names (`.head`, `.btn`, `.btn.ghost`, `.tools`, `.chip`, `.card`, `table`, `.pill`, `.top`, `.round`, `.big`, `.chips`, `.grp`, `.list`, `.row`, `.av`, `.t`, `.link`). Do not restyle the shared classes per page.

## 2. Context and decisions (orchestrator)
- Read first: `App/app/templates/dashboard.html` lines 1-60 (how a v2 page sets `{% set v2 = true %}`, empties the old header blocks and writes its own `.head`), the two mockup sections above, and the current `App/app/templates/reservations.html` (0522 columns).
- Keep from 0522: lead-guest name (`lead_name`, fallback summary / `stays.row.no_name`), property column, arrival + departure columns, the deadline under the pill, the row menu with "Request payment", the house book download, the add-stay panel, the filter panel form, pagination, empty state, onboarding banner. Pill: use `v2_status_pill(deadline_cell(progress, check_in), progress, reservation)` from `_components.html` (same as the Overview).
- **Header (computer):** `<div class="head"><div><h1>{{ t('stays.title') }}</h1></div><div style="display:flex;gap:8px">` + `<a class="btn ghost" href="/housebook.csv?{{ csv_export_params }}" data-stays-housebook>` house book + the bulk-send button when `manual_send` (as `.btn ghost`) + `<button class="btn" type="button" data-toggle-panel="add-stay-panel">` add stay `</div></div>`. Empty the `title`-adjacent old blocks (`page_title`, `meta`, `primary_action`, `secondary_actions`, `tabs`, `toolbar`) as `dashboard.html` does.
- **Section tabs go** (no tab strips, owner rule). Their two other targets move to the bottom of the page as one `.list` with two `a.link` rows, shown at every size: "Hlášení policii" → `/submissions`, "Domovní kniha" → `/housebook` (reuse the existing tab label keys; `grep -n "page_tabs\|section_tabs" App/app/templating.py` shows them).
- **Chips** (both sizes, one row, `.chips` wrapping `a.chip` / `a.chip.on`): Nadcházející (`range=upcoming`), Probíhá (`range=current`, new), Proběhlé (`range=past`), Chyba hlášení (`report=failed`, new), Archivované (`range=archive`). Then a dashed `button.chip` "Filtry" that toggles the existing filter panel (keep its `data-filter-toggle` / `aria-controls` attributes). Copy: set cs `stays.chip.upcoming` = "Nadcházející", `stays.chip.past` = "Proběhlé"; new `stays.chip.current` en "In house" / cs "Probíhá" / vi "Đang ở", `stays.chip.failed` en "Report failed" / cs "Chyba hlášení" / vi "Khai báo lỗi". No search box (guest names are encrypted; owner told).
- **Route** `reservations_list()` in `App/app/routes/admin.py`: add `"current"` to `RESERVATION_RANGES` and for it filter `r.date_from <= today AND r.date_to >= today`; read `report = request.query_params.get("report")` and when it is `"failed"` add `AND EXISTS (SELECT 1 FROM guest g WHERE g.reservation_id = r.id AND g.submit_state IN ('error','blocked'))` (check the guest column names in `App/app/db.py` schema first). Pass `report` to the template and keep it in chip/pagination URLs. Postgres-portable SQL only.
- **Computer body:** `.card` > `table` with `th` Host, Nemovitost, Příjezd, Odjezd, Hlášení, and an empty last `th` for the menu; `td` guest name with `<small>` guest count · source under it; deadline as `<small>` under the pill. Rows stay clickable (`data-href`, existing `row_open` not needed: drop it, the name is a link). Table hidden below 1024 px.
- **Phone body (< 1024 px):** `.top` with an empty `<span>` and `<button class="round" type="button" data-toggle-panel="add-stay-panel" aria-label="{{ t('stays.add_stay') }}">` + plus icon; `<div class="big">` title (hide the `.head` below 1024 the same way the Overview does, or reuse its rule if `.head h1` already becomes `.big`: check app2.css); chips; then rows grouped by `.grp` headings: Dnes (date_from or date_to == today, or in house), Tento týden (starts within 7 days), Později, and for past stays Dříve. Each row: `<a class="row" href="/reservations/{id}?return_to=...">` `.av` (first letter of the shown name) + `.t` (`<b>` name, `<small>` property · short dates like `1.–4. 11.`, the v2 pill) + chevron icon. Group copy keys `stays.grp.today|week|later|earlier`: en Today / This week / Later / Earlier, cs Dnes / Tento týden / Později / Dříve, vi Hôm nay / Tuần này / Sau đó / Trước đó. The house book `a.link` with `<small>` "CSV pro kontrolu" (`stays.housebook_hint`, en "CSV for checking", vi "CSV để kiểm tra") goes in the bottom `.list` on phone.
- Any CSS the mockup needs that app2.css lacks (`.grp`, `.chips` row on computer, table hide/show by width) goes into `App/app/static/app2.css` in one block headed `/* 0526 stays list */`, copied from the mockup's CSS values. Bump the app2.css key in `base.html` to `20261101-0526` and `--write` the manifest.

## 3. Files
`App/app/templates/reservations.html`, `App/app/routes/admin.py` (reservations_list only), `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/app/static/app2.css`, `App/app/templates/base.html` (key), `App/tests/static_versions.json` (`--write`), `docs/design/catalog.json` (new classes), report `docs/tasks/0526-report.md`. Tests are brief 0527; only run the commands below.

## 4. Steps
1. v2 switch, header, chips, bottom links, route filters, copy. Commit `0526 step 1`.
2. Computer table. Commit `0526 step 2`.
3. Phone top row and grouped rows, app2.css block, key, manifest, catalog. Commit `0526 step 3`.
4. Commands, report. Commit.

## 5. Do not touch
`_shell_v2.html`, `dashboard.html`, `menu.html`, any JS, the stay detail page, other routes.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0523_stays_list.py tests/test_design_stays.py tests/test_archive_stays_on_page.py tests/test_stays_empty_workspace.py tests/test_static_versions.py -q --tb=line 2>&1 | tail -20`. Repo root: `python3 scripts/design_lint.py | tail -3; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
Server tests pass except assertions on the removed old markup (tab strip, `ui-table`, `row-open`, old chip labels): list those in the report without editing them (0527 updates them).

## 8. Stop and ask
Stop if the guest table has no `reservation_id`/`submit_state` columns, or if the filter panel cannot open without the old toolbar.

## 9. Report
`docs/tasks/0526-report.md`: status, test tails, failing old assertions, departures from the mockups.
