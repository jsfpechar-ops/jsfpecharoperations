# 0830 brief: the Airbnb pattern on every remaining host page (Josef 16:22)

Status: todo
Executor: Haiku 5.5, alone, on branch `claude/project-thread-tx2a49`, in the main checkout (never a worktree: they branch from a stale base). Do not commit; the orchestrator commits. Each run does ONE part (A to F) named in its prompt. Part A runs first, alone; B to F then run in parallel, so each edits only the files of its part and its own CSS block.

## 1. Objective

Josef: "Airbnb everywhere", phone, tablet and desktop. References in `/mnt/project-files/settings-area/airbnb-ref/` (open IMG_2199 index rows, IMG_2197 pill tabs + value cards). The settings thread (this branch already contains its 0789 work) built the shared pieces; reuse them, do not copy them:

- `partials/settings_back_header.html`: round 40 px grey back button (`.airbnb-back`) + big bold title (`.airbnb-title`, 32 px phone).
- `partials/settings_index_row.html`: 24 px line icon, label 17 px, chevron, 64 px row (`.airbnb-index-row`).
- `partials/settings_pills.html`: scrollable pills 44 px, grey, current black with `aria-current` (`.settings-pill`).
- `partials/settings_value_card.html`: 1 px border, radius 12, padding 20, label + big bold value (`.settings-value-card`).
- `partials/settings_toggle_row.html`: label left, switch right (`.settings-toggle-row`).

Rules for every page in this brief:
1. Top: list pages keep the big bold title (32 px phone, 28 to 32 desktop); every detail or sub-page gets the back header (back goes to its list page).
2. Tab strips and filter chips become pills. Read-only numbers and states become value cards. Link lists become index rows. On/off settings become toggle rows (same form, same POST).
3. List items: a bordered card (1 px #e5e5e5, radius 12, padding >= 16) or a plain row with a 1 px divider; no shadows, no coloured backgrounds except status badges.
4. No fine print: any description or sub-line moves under a help `?` (8 px after the label's last word) or is dropped. No money metrics.
5. Geometry: 12 px minimum between any two neighbouring elements (text, buttons, pills, tags); 24 px after a block-ending button; card text >= 16 px from the card edge; row buttons and the `⋯` menu share one height and centre line.
6. Behaviour unchanged: same routes, forms, field names, POST targets, JS hooks (`data-*`), Turbo. No Python logic change except passing a value a template already has.
7. Tablet layout stays as the shell gives it (64 px rail from 768, bottom bar below, lane max 1080). Do not hard-code phone looks at 768.

If a partial's CSS is scoped to `.settings-lane` (for example `.airbnb-index-row`), add your page's selector in your own block; never edit the settings blocks.

## 2. Parts

| Part | Pages (route) | Templates |
|---|---|---|
| A | shared test + CSS markers | `App/tests/test_0830_airbnb_pages_browser.py`, end of `App/app/static/app2.css` |
| B | Overview `/`, Menu `/menu` | `dashboard.html` (NOT `_dashboard_calendar.html`), `menu.html` |
| C | Properties `/apartments`, property detail `/apartments/{id}` (editing) | `apartments.html`, `_property_editor.html`, `_property_identity_fields.html`, `_property_address_fields.html`, `_property_operator.html`, `_property_calendars.html`, `_smart_locks_panel.html`, `_smart_lock_share.html`; in `apartment_form.html` only the editing header (another PR changes its top lines) |
| D | Stays `/reservations`, stay detail | `reservations.html`, `reservation_detail.html`, `_door_code_window.html` |
| E | Invoice detail, invoice form + stay picker, submission detail | `invoice_detail.html`, `invoice_form.html`, `invoice_stay_picker.html`, `submission_detail.html` (these are not v2 yet: set `v2 = true` and port what the old CSS gave them into your block) |
| F | Sub-pages: guest questions, Leon settings + setup, cleaning settings, subscription `/predplatne`, payments (look only: header, pills, cards; flows unchanged) | `guest_questions.html`, `guest_question.html`, `leon_settings.html`, `leon_setup/*.html`, `cleaning_settings.html`, `billing_plan.html`, `payments.html`, `payments_share.html`, `payments_consent.html` (not v2 yet: set `v2 = true` and port old CSS) |

Out of scope (other PRs own them): settings and its sub-pages, entities, privacy requests, archive; calendar and cleaning calendar (`_dashboard_calendar.html`, `cleaning.html`, `dashboard-calendar.*`); wizard, onboarding, new property, guest guide, Průvodce `/guide`, Havel, cleaning new/shares/properties; submissions, invoices list, housebook, stay fees. Guest-facing, public, login and admin pages.

## 3. Part A (runs first)

1. Append to the end of `App/app/static/app2.css` six empty marker pairs, one per part B to F plus shared: `/* 0830 shared (start) */` `/* 0830 shared (end) */`, `/* 0830B overview+menu (start) */` ... `(end)`, and the same for C, D, E, F. Parts write only between their own markers.
2. Write `App/tests/test_0830_airbnb_pages_browser.py`, modelled on `App/tests/test_0786_settings_geometry_browser.py` and `geometry_findings` in `App/tests/v2_mockup.py`. Seed data the way `App/tests/test_0800_v2_remaining_pages_browser.py` does (one property, one stay, one invoice, one submission). Parametrise over pages (one id per route above, marked with its part letter, so `-k partB` works) and widths 320, 390, 768, 1024, 1280, 1440. Checks per page and width:
   - `body.v2`, exactly one visible h1, no horizontal overflow, `geometry_findings` empty;
   - detail and sub-pages: `.airbnb-back` visible, >= 40 px, left of the h1 or above it;
   - pills (where present): >= 44 px tall, >= 12 px apart, exactly one with `aria-current`;
   - value cards and list cards: border 1 px, radius >= 12, text >= 16 px from the edge;
   - 12 px neighbour rule: no two visible interactive or text boxes in the main lane closer than 12 px (reuse the 0786 helper if it exists);
   - no visible `p`, `small` or `.muted` text longer than 60 characters outside help bodies.
   - With `UBYHOST_SHOTS_0830=1`, save `docs/tasks/screenshots-0830/<page>-<width>.png` (390, 768, 1280 only).
3. Run it once: expected mostly red (record counts per part in the report). Do not fix pages.

## 4. Parts B to F

1. Run your part's tests (`-k part<X>`), note the reds.
2. Rebuild your templates with the partials and rules in section 1. Port old CSS needed by pages that become v2.
3. Run your part's tests plus the old tests that touch your templates (`grep -l` the template name or route in `App/tests/`), until green, 0 skipped. If an old test asserts the old look, update the assertion to the new look; never delete a behaviour test.
4. Report `docs/tasks/0830<X>-report.md`: files, test counts, anything left.

Do not bump the cache key or `static_versions.json`; the orchestrator does that once at the end.

## 5. Commands

From `App/`: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0830_airbnb_pages_browser.py -k partB -q --tb=line -p no:cacheprovider 2>&1 | grep -E "^(FAILED|ERROR)|^E  |passed|failed" | cut -c1-240 | tail -20` (no `-n`). From the repo root: `python3 scripts/design_lint.py`.

## 6. Do not touch

`App/app/static/app.js`, other parts' files and CSS blocks, files listed as out of scope, `base.html`.

## 7. Stop and ask

A Python logic change; a form that would need JS; a test that can only pass by changing an out-of-scope file.
