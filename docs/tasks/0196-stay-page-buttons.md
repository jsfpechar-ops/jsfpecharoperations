# 0196: Stay page buttons on one grid

Status: done
Depends on: none | Base commit: fea8bee | Branch: claude/project-thread-xo8dql
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

On the stay page (`/reservations/<id>`) the buttons look messy: "Edit count" is an old underlined text link (twice), "+ Add a guest" does not line up with the "Add by hand" buttons below it, and "Generate invoice" plus the ⋮ menu float without a clear group. Make every action a bordered button from the existing button system, one height per row, right edges aligned.

## 2. Context

Rules: WCAG 2.2 AA (targets at least 24x24 px, visible focus), no borderless design (buttons keep a visible border), light mode only. Use only existing classes `ui-btn ui-btn-secondary ui-btn-compact` (see `App/app/templates/_components.html` / `docs/design/MASTER.md`); no new colours.

`App/app/templates/reservation_detail.html`:
- line 74 (Now panel note): `<a href="#stay-quick-edit" data-open-details>{{ t('host.edit_count') }}</a>` right after `{{ tp('host.missing', progress.not_registered) }}`.
- line 78: the same pattern with `t('stay.detail.change_guest_count')`.
- `<div class="stay-command-actions">` (line ~88) holds the primary action / Generate invoice and the row menu (`row_menu_end()` at ~line 165).
- line 174 (Guests header):
  `<div class="ui-form-actions"><a href="#stay-quick-edit" data-open-details>{{ t('host.edit_count') }}</a><a class="ui-btn ui-btn-secondary ui-btn-compact" href="/reservations/{{ reservation.id }}/guests/new">+ {{ t('stay.detail.cta.add_guest') }}</a></div>`
- line ~304 placeholder guest row: `<a class="ui-btn ui-btn-secondary ui-btn-compact" ...>{{ t('stay.detail.guests.add_by_hand') }}</a>` inside `.guest-card-state`.

Stay-page CSS lives in `App/app/static/host-design0123.css` (rules scoped `body.host-workspace .host-stay-detail ...`, e.g. line 74 `.stay-command-panel`). It is linked from the host base template with `?v=20261020-0189c`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/reservation_detail.html | edit | buttons as below |
| App/app/static/host-design0123.css | edit | append one block at the end (marked `/* 0196 */`) |
| every template that links `host-design0123.css?v=20261020-0189c` | edit | new key `?v=20261021-0196` |
| App/tests/static_versions.json | regenerate | `.venv/bin/python tests/test_static_versions.py --write` |
| App/tests/test_send_controls.py, App/tests/test_design_stay_detail.py | edit only if an assertion depends on the old link markup | |

No other file may change.

## 4. Steps

1. Now panel (lines 74 and 78): remove the inline `<a ... data-open-details>` links from the sentence. Instead, inside `.stay-command-actions`, as its FIRST child, add (only when the note offered it, i.e. the `progress.not_registered` branch or the `hint.missing_guests` branch):
   `<a class="ui-btn ui-btn-secondary" href="#stay-quick-edit" data-open-details>{{ t('host.edit_count') }}</a>`
   Use a Jinja variable set in the note branches (e.g. `{% set offer_count_edit = true %}`; note Jinja scoping: set it with a namespace `{% set ns = namespace(count_edit=false) %}` before the note and `{% set ns.count_edit = true %}` inside).
2. Guests header (line 174): change the Edit count link to `<a class="ui-btn ui-btn-secondary ui-btn-compact" href="#stay-quick-edit" data-open-details>{{ t('host.edit_count') }}</a>`, keep "+ Add a guest" after it.
3. CSS block appended to host-design0123.css:
   ```css
   /* 0196: stay page actions on one grid. */
   body.host-workspace .host-stay-detail .stay-command-main { align-items:center; }
   body.host-workspace .host-stay-detail .stay-command-actions { display:flex; align-items:center; justify-content:flex-end; gap:8px; flex-wrap:wrap; }
   body.host-workspace .host-stay-detail .stay-command-actions > :is(a,button,form,details,.row-menu) { margin:0; }
   body.host-workspace .host-stay-detail .stay-command-actions :is(.ui-btn,.btn) { min-height:40px; }
   body.host-workspace .host-stay-detail #guests .ui-section-h { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
   body.host-workspace .host-stay-detail #guests .ui-section-h .ui-form-actions { display:flex; align-items:center; gap:8px; margin:0; }
   ```
   Then make the right edge of "+ Add a guest" equal the right edge of the "Add by hand" buttons: measure both with the browser (step 5) and remove the difference by giving the placeholder rows the same right padding as the header (adjust `#guests .guest-card.placeholder` padding-right, or the header's padding). Same for the left edge of the "Guest 1..." titles vs the "Guests" heading if they differ by more than 2 px. The ⋮ menu trigger must be the same height as Generate invoice (40 px) with a visible border.
4. Check the mobile rule in `app.css` line ~1174 (`.stay-command-actions { justify-content:flex-start }` below some width) still makes sense; at 390 px buttons wrap to full-width rows, left aligned, not overflowing.
5. Verify with Playwright (Chromium at `/opt/pw-browsers`): demo login is how the existing browser tests do it; copy the setup from `tests/test_design_stay_detail.py` or another `*_browser.py` stay test. At 1280 px assert: Edit count, Generate invoice, ⋮ share one vertical centre (±1 px); "+ Add a guest" right edge == "Add by hand" right edge (±1 px); every button has a non-zero border width. Save screenshots at 390/1280/2000 to `/mnt/project-files/design-reset/checkpoint-6/stay/` named `stay-<width>.png`.

## 5. Do not touch

Copy keys and translations, routes, other pages. No new colours or tokens. Never push.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_send_controls.py tests/test_design_stay_detail.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance

- [ ] No underlined "Edit count" text link remains on the stay page.
- [ ] Alignment checks in step 5 pass; screenshots saved.
- [ ] Tests above pass.

## 8. Stop and ask

If an excerpt is not found, stop and report. Do not commit; the orchestrator commits.

## 9. Report

[0196-report.md](0196-report.md)
