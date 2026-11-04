# 0912: Stay detail: one aligned action row, clean header, tidy sections

Status: todo. Source: UX review 2026-11-04 (Stay detail rows), plus the coordinator's header note with the screenshot `/root/.claude/uploads/0ff240ee-6d60-5813-a0fa-6d621cad033a/0cb691c5-Screenshot_2026-11-04_at_14.04.45.png` (the owner can attach it to the PR). Executor: Haiku 5.5, one run. Run after 0911 is merged.
Read first: AGENTS.md, docs/context/executor.md, docs/design/MASTER.md (the buttons/header section only: `grep -n '^## ' docs/design/MASTER.md`), this brief.

## 0. Before you start
Start only after PR #772 is merged, because this brief edits `App/tests/layout_lint.js`. Branch from a fresh `origin/main`. Do not edit `_components.html` (`row_menu_begin` and `row_menu_end` stay as they are). Do not touch any `/payments` template or route. Keep the existing payment link in the menu exactly as it is.

## 1. Objective
In every state (reported, overdue, no guests), at 390, 768 and 1280 px:
- The stay detail header is the title, then one line with the status badge and the property and dates, then one action row. The action row holds the primary button, the secondary buttons and ⋮, aligned on one baseline.
- What does not fit goes into ⋮ instead of wrapping.
- The sections below get spacing, one name order, one "all reported" line and one Save.

## 2. Context (verified 2026-11-04, `App/app/templates/reservation_detail.html`, 402 lines)
- Header: lines 60-~95. `<div class="head" id="now">` holds the crumb, then `<p class="sub">` (line 63) with the pill plus `<span class="stay-sep">` (property link · dates). Then `<div class="stay-head-actions">` (line 65) holds `<div class="stay-head-cta">{{ stay_cta() }}` + the "Copy guest form link" button (`ph-hide`), then the claim-resend `<form>` (line 68, `stay.claim.resend`, no `ph-` class), then `{{ row_menu_begin() }}` ... `row_menu_end()`. The menu already has a `ph-only` copy-link item (pattern to reuse).
- The phone header duplicate is at line 31 (`.stay-pill-line ph-hide`): leave its markup.
- Guest name: line ~202 `<b>{{ guest.surname or '—' }} {{ guest.first_name or '' }}</b>`. The title uses `lead_name` (first name first).
- "All guests are reported. Nothing left to send." is `hint.all_reported`, rendered at line 347 (`<div class="allgood">`). A second copy shows inside the police reporting section.
- Door code: lines 348-355, `.stay-door-card` with `.code` and a separate `.ic` key icon.
- Stay settings: `<details class="card stay-settings" id="stay-quick-edit">` ~357-400. It holds a quick-edit form (`action="/reservations/{{ reservation.id }}/quick-edit"`, fields `summary` and `expected_guests_override`, its own Save) and the main form (`action="/reservations/{{ reservation.id }}"`, `class="settings-grid"`, its own Save). The main POST handler is `routes/admin.py` `@router.post("/reservations/{reservation_id}")` at ~3644-3680.
- Styles: find the stay-detail rules with `grep -n "stay-head-actions\|stay-head-cta\|stay-door-card\|stay-settings\|stay-sep" App/app/static/*.css`. Edit the file that already holds them.

## 3. Files
`templates/reservation_detail.html`, the CSS file found above (plus its `?v=` key), `routes/admin.py` (the two stay POST handlers only), `App/tests/layout_lint.js`, `App/tests/test_layout_lint_browser.py`, a new test file.

## 4. Steps
1. **Header line.** Give `#now .sub` (line 63) `display:flex; flex-wrap:wrap; align-items:center; gap:4px 12px`, and `.stay-sep` `min-width:0`. The pill and the property line then wrap as two clean items, never mid-pill.
2. **Action row.** Make `.stay-head-actions` `display:flex; flex-wrap:nowrap; align-items:center; justify-content:flex-end; gap:12px`. Make `.stay-head-cta` `display:flex; flex-wrap:nowrap; align-items:center; gap:12px`. Make the claim-resend form `display:contents` or `margin:0`. Below 1024 px, the header resend form gets `ph-hide`. Add a `ph-only` menu item inside the row menu, right after the copy-link item, with the same `stay.claim.resend` label, as a `<form method="post" class="row-menu-form">` copied from the archive/restore pattern at ~80. At 390 px the row is then: primary + ⋮. At 768 and 1280: primary, Copy link, Resend, ⋮ on one line. If the row still overflows at 768, give the copy button `ph-hide` at under 1024 px through the same class approach and report it.
3. **Orphan check in the lint.** In `App/tests/layout_lint.js`, add a check `action-row-orphan`. For each `.stay-head-actions` that is visible, collect its visible `button, a.btn, .row-menu > summary, details > summary` descendants. Flag the row when their `getBoundingClientRect().top` values differ by more than 4 px. Add a case to `test_the_lint_catches_the_known_regressions` in `test_layout_lint_browser.py` (a fixture HTML where ⋮ wraps). Follow the file's existing check pattern (`grep -n "function \|id:" App/tests/layout_lint.js | head -40`). If the lint has no fixture mechanism, STOP after the CSS steps and report.
4. **Guest table spacing.** Give the guests section card (`grep -n "id=\"guests\"" templates/reservation_detail.html`) `margin-top:12px` from the card above.
5. **One name order.** Change line ~202 to `{{ guest.first_name or '' }} {{ guest.surname or '—' }}` (matches the title).
6. **One "all reported" line.** `grep -rn "all_reported\|nothing_left" App/app/templates/reservation_detail.html App/app/templates/_workflow.html App/app/reporting.py`. Remove the line 347 `<div class="allgood">`, provided the police section shows the same sentence in the same state. If it does not, STOP.
7. **Door code on one line.** `.stay-door-card { display:flex; align-items:center; justify-content:space-between; gap:12px }`. Move the key icon `<div class="ic acc">` before the code block so icon, code and dates read left to right. Code font: the body heading token (`var(--size-24)` or the nearest existing token; check tokens.css), not smaller than 20 px.
8. **One Save in Stay settings.** Move the `summary` and `expected_guests_override` labels and inputs into the main `settings-grid` form, as two `ui-field` blocks before `guest_email`. Delete the quick-edit form and its Save, but keep `<details id="stay-quick-edit">` so the anchor works. In the POST `/reservations/{reservation_id}` handler, when `summary` or `expected_guests_override` is in the form, apply them exactly as the quick-edit handler does: find it with `grep -n "quick-edit" App/app/routes/admin.py` and call the same helper, or copy its validation lines unchanged. Keep the quick-edit route itself, because other pages may use it (`grep -rn "quick-edit" App/app/templates App/app/static | head`).
9. **Field spacing.** `.stay-settings .settings-grid { display:grid; gap:12px }` and `.stay-settings .ui-field label { display:block; margin-bottom:4px }`.
10. Bump the CSS `?v=` key. Follow `test_static_versions.py`.

## 5. Do not touch
`_components.html`, `base.html`, Payments, guest templates, `reporting.py` logic.

## 6. Commands (from `App/`, `2>&1 | tail -30`)
- New `tests/test_0912_stay_detail.py`:
  - POST `/reservations/<id>` with `summary` and `expected_guests_override` saves both;
  - the stay page has one Save inside `#stay-quick-edit`;
  - `hint.all_reported` text appears once on a reported stay;
  - the guest row reads first name first.
- `.venv/bin/python -m pytest tests/test_0912_stay_detail.py tests/test_host_*.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py tests/test_static_versions.py -q --tb=short -x -rs`, 0 skipped.
- Filing row tests that render the stay page: `tests/test_filed_by_hand.py tests/test_police_*.py`.
- UX gate: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs`, 0 skipped, zero host findings including the new check. Open the stay detail shots at 390/768/1280. If the lint seeds only one stay state, add the reported, overdue and no-guests stays to the new test with a Chromium screenshot each at 390/768/1280 under `/tmp/shots/0912/` and look at all nine. PR body: per state "390: ...; 768: ...; 1280: ...".
- `python3 scripts/context_lint.py`.

## 7. Acceptance
- [ ] In all three states and three widths, the action buttons and ⋮ share one row and nothing sits alone on a line. The badge and property line align under the title.
- [ ] The new lint check fails on the fixture and passes on the real page.
- [ ] One name order, one "all reported" line, door code and icon on one line, one Save, 12 px gaps.
- [ ] No new dependency, light mode only.

## 8. Stop and ask
An anchor is missing; the quick-edit handler's validation can't be reused without changing its behaviour; the police section does not show the all-reported sentence.

## 9. Report
`docs/tasks/0912-report.md` with the nine state screenshots listed by path.
