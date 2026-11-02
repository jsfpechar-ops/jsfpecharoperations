# 0524: Stay detail redesign, part 1: guest-name title, status line, door code section
Status: todo
Depends on: none | Base commit: origin/main | Branch: task/0524-stay-detail-header
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Make the stay page (`/reservations/{id}`) header follow the approved computer mockup (`ubyhost-redesign-v2.html`, view "stay", owner approved 2026-11-01): back link "Back to stays", title = the lead guest's name, a sub line with the reporting pill, then property and dates; a quiet "Copy guest link" button in the header; no tab strip; the door code gets its own section. The "Now" panel with the Send/Fix buttons, the guests, police reporting and settings sections keep their content and logic (filing correctness, rule 1).

## 2. Context
- Template `App/app/templates/reservation_detail.html` (479 lines; read only the ranges named here). Blocks `page_title`, `meta` near the top (lines 8-19); `stay_jump_nav` macro lines 12-17 and its call about line 28; `stay-property-line` about line 26; the door code paragraph `id="door-code-line"` in the "Now" panel about line 86; the reports section starts at `<section class="ui-section" id="reports">`; settings at `id="stay-quick-edit"`.
- `guest_rows` (list of rows with `.guest`, each guest has `first_name`, `surname`, `is_lead`) is already in the template context. The header shell is `App/app/templates/host_page.html` (blocks `secondary_actions`, `meta`); do not edit it.
- `progress_pill(...)` call to copy: in `App/app/templates/reservations.html`, the `stay-col-reporting` cell.
- Translations: en and cs in `App/app/host_i18n.py` (next to `stay.detail.back`), vi in `App/app/host_vi_i18n.py`.

## 3. Files
Edit `App/app/templates/reservation_detail.html`, `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`. Report `docs/tasks/0524-report.md`. Nothing else (CSS and tests are brief 0525).

## 4. Steps
1. **Title.** Before `{% block title %}` add `{% set lead_row = (guest_rows | selectattr('guest.is_lead') | first) or (guest_rows | first) %}` and `{% set lead_name = ((lead_row.guest.first_name or '') ~ ' ' ~ (lead_row.guest.surname or '')) | trim if lead_row else '' %}`. Change `page_title` to `{{ lead_name or reservation.internal_name }}`. Leave `{% block title %}` (the browser tab) as it is. Commit `0524 step 1`.
2. **Sub line.** Change the `meta` block to: the `progress_pill(...)` (same arguments as on the list; when `reservation.status != 'active'` the grey state badge instead, as on the list), then ` · `, then `<a href="/apartments/{{ reservation.apartment_id }}">{{ reservation.internal_name }}</a>`, then ` · `, then the existing `stay_lede`. Delete the `<p class="stay-property-line">…</p>` paragraph (the property is now in the sub line). Commit `0524 step 2`.
3. **No tab strip.** Delete the `stay_jump_nav([...])` call and the `stay_jump_nav` macro with its comment (dead after the call goes). Commit `0524 step 3`.
4. **Header button.** Add `{% block secondary_actions %}{% if reservation.permalink_token and not (reservation.status != 'active' or reservation.archived_at) %}<button class="ui-btn ui-btn-secondary" type="button" data-copy="stay-link" data-copied-label="{{ t('stay.detail.link_copied') }}" data-stay-header-copy>{{ t('host.copy_guest_form_link') }}</button>{% endif %}{% endblock %}` after the `meta` block. The `#stay-link` input it copies already exists at the top of the body. Commit `0524 step 4`.
5. **Door code section.** Cut the whole `{% if door_code %}<p class="ui-sub" id="door-code-line">…</p>{% endif %}` out of the "Now" panel. Paste it, inside `{% if door_code %}`, as a new section directly before `<section class="ui-section stay-settings" id="stay-quick-edit">`: `<section class="ui-section" id="door-code"><div class="ui-section-h"><h2>{{ t('stay.detail.door_code.title') }}</h2></div><div class="ui-card stay-door-card">` + the paragraph (keep its id, drop the `ui-sub` class) + `</div></section>`. Copy `stay.detail.door_code.title`: en "Door code", cs "Kód ke dveřím", vi "Mã cửa". Commit `0524 step 5`.

## 5. Do not touch
The "Now" panel's buttons, menu and logic, guests section, money group, reports section and file-by-hand, settings section, banners, any route, CSS, JS or test file, `host_page.html`.

## 6. Commands (from `App/`)
`.venv/bin/python -m pytest tests/test_design_stay_detail.py tests/test_overhaul.py tests/test_wp25_reported_bugs.py tests/test_host_invoice_navigation.py -q --tb=short -x 2>&1 | tail -30`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -10` and `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass. `git diff --stat origin/main` lists only section 3 files plus section 8 test edits.

## 8. Stop and ask
If a server test asserts the jump tabs (`stay-jump`), the property line, the property name as the `<h1>`, or `door-code-line` inside the "Now" panel, update only that assertion to the new place and list it in the report. Stop if any test about sending, fixing, receipts or filing changes result. If design_lint asks for catalog entries, note it in the report (brief 0525 adds them) and continue.

## 9. Report
`docs/tasks/0524-report.md`: Status, test and lint tails, `git diff --stat origin/main`, deviations.
