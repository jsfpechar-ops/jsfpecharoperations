# 0522: Stays list redesign, part 1: header buttons and mockup columns
Status: todo
Depends on: none | Base commit: origin/main | Branch: task/0522-stays-list
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Make the stays list (`/reservations`) follow the approved computer mockup (`ubyhost-redesign-v2.html`, view "stays", owner approved 2026-11-01): header with a quiet "Download house book" button and the primary "Add stay"; table columns Guest (name, then guests count and source), Property, Arrival, Departure, Reporting, a quiet "Request payment" button, and the row menu. No money figures.

## 2. Context
- Template `App/app/templates/reservations.html`. The rows loop starts at `{% for row in rows %}` (about line 143). `row.progress.guests` is the stay's guest list (each has `first_name`, `surname`, `is_lead`). Check the shape once with a test print if unsure, then remove the print.
- Keep `progress_pill(...)` and the `stay-report-deadline` block exactly as they are: the police deadline must stay visible on every row (filing correctness, rule 1).
- Translations: en and cs in `App/app/host_i18n.py` (next to `stays.table.reporting`), vi in `App/app/host_vi_i18n.py`.

## 3. Files
Edit `App/app/templates/reservations.html`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`. Report `docs/tasks/0522-report.md`. Nothing else (CSS and tests are brief 0523).

## 4. Steps
1. **Header.** In `{% block secondary_actions %}` keep the `bulk_send_ready` call and add after it, inside `{% if apartments %}`: `<a class="ui-btn ui-btn-secondary" href="/housebook.csv?{{ csv_export_params }}" data-stays-housebook>{{ t('stays.housebook_download') }}</a>`. Copy: en "Download house book", cs "Stáhnout domovní knihu", vi "Tải sổ lưu trú". Commit `0522 step 1`.
2. **Guest name.** At the top of the row loop add:
   `{% set lead = (progress.guests | selectattr('is_lead') | first) or (progress.guests | first) %}`
   `{% set lead_name = ((lead.first_name or '') ~ ' ' ~ (lead.surname or '')) | trim if lead else '' %}`
   In the first cell replace the visible text of the `stay-identity-link` anchor with `{{ lead_name or (reservation.summary if reservation.source == 'manual' and reservation.summary and reservation.summary.strip() else t('stays.row.no_name')) }}`. Keep the anchor, its classes and href, and keep `property_identity(...)`. Remove the `{% if stay_label != reservation.internal_name %}` sub line (the property gets its own column). Move `{{ guest_count(progress, placeholder=true) }}` into the existing `stay-col-source` div, before the source badge, joined by ` · `. Header text of this column: `stays.table.guest` (en "Guest", cs "Host", vi "Khách"). Copy `stays.row.no_name`: en "No name yet", cs "Zatím bez jména", vi "Chưa có tên". Keep `aria-label` of the `<tr>` as it is. Commit `0522 step 2`.
3. **Property column.** Add `<th class="stay-col-property">{{ t('stays.table.property') }}</th>` after the first `<th>` and a matching cell `<td class="stay-col-property" data-card="meta" data-label="{{ t('stays.table.property') }}">{{ reservation.internal_name }}</td>`. Copy: en "Property", cs "Nemovitost", vi "Chỗ ở" (reuse an existing key with the same text if `grep -n '"Nemovitost"' App/app/host_i18n.py` finds one under `stays.`/`host.`). Commit `0522 step 3`.
4. **Arrival and departure.** Replace the one dates column with two: `<th class="stay-col-dates">{{ t('stays.table.arrival') }}</th>` holding the existing `stay-date-link` anchor with only `{{ reservation.date_from | date_cz }}` inside, and `<th class="stay-col-departure">{{ t('stays.table.departure') }}</th>` holding `{{ reservation.date_to | date_cz }}` plus the existing `ui-sub` div (nights and in-house badge) moved here unchanged. Both cells `nowrap`, `data-card="secondary"`, `data-label` = their header key. Copy: arrival en "Arrival", cs "Příjezd", vi "Ngày đến"; departure en "Departure", cs "Odjezd", vi "Ngày đi" (reuse `calendar.arrival`/`calendar.departure` if they have exactly this text). Remove the old `stay-col-guests` `<th>` and `<td>` (the count moved in step 2). Commit `0522 step 4`.
5. **Request payment.** Before the actions cell add `<th class="stay-col-pay"><span class="sr-only">{{ t('stays.row.request_payment') }}</span></th>` and `<td class="stay-col-pay" data-card="actions" data-label="">{% if not show_archive and reservation.status == 'active' %}<a class="ui-btn ui-btn-secondary ui-btn-compact" href="/payments?reservation_id={{ reservation.id }}#new-request">{{ t('stays.row.request_payment') }}</a>{% endif %}</td>`. Copy: en "Request payment", cs "Požádat o platbu", vi "Yêu cầu thanh toán". Commit `0522 step 5`.

## 5. Do not touch
The add-stay panel, filter panel, chips, toolbar, tabs, pagination, empty state, row menu items, `progress_pill`, deadline badge, any route, CSS, JS or test file.

## 6. Commands (from `App/`)
`.venv/bin/python -m pytest tests/test_design_stays.py tests/test_archive_stays_on_page.py tests/test_stays_empty_workspace.py -q --tb=short -x 2>&1 | tail -30`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -10` and `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass. `git diff --stat origin/main` lists only section 3 files.

## 8. Stop and ask
If a server test asserts the removed guests column or the old dates text, update only that assertion and list it in the report. Stop if `progress.guests` does not hold the guests, or if design_lint asks for catalog entries (brief 0523 adds them): then note it in the report and continue.

## 9. Report
`docs/tasks/0522-report.md`: Status, test and lint tails, `git diff --stat origin/main`, deviations.
