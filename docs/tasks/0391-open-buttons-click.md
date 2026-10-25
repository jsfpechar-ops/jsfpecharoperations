# 0391: every "Open" button actually opens

Status: done (report: [0391-report](0391-report.md))
Branch: claude/project-thread-by10nz
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (took two)

## 1. Objective

Owner (Josef, 2026-10-25): "open button on stay dont work when i click it then i click pill and its alright, so check all open buttons and fix it". Every Open is a real link to the place its row opens. No look change: Open keeps the plain bordered style (MASTER 7.1 `open`), same size and position on desktop and phone cards.

## 2. Context

- `row_open()` in `App/app/templates/_components.html` rendered `<span class="row-open">`, always inside `td.row-actions`.
- `App/app/static/app.js` `initClickableRows` returns early for any click inside `.row-actions`, so a click on Open did nothing.
- The static "Guest links" card in `_property_overview.html` is a `div`; its `open_pill` was a span.
- Demo data has rows on /reservations, /apartments, /housebook and the property overview only; /entities, /invoices, /stay-fees, /submissions, /cleaning/properties are empty with demo data.

## 3. Files

| Path | Action |
|---|---|
| App/app/templates/_components.html | `row_open(href)` renders `<a class="row-open" href tabindex="-1" aria-hidden="true">` |
| App/app/templates/{reservations,reservation_detail,apartments,submission_detail,submissions,entities,settings_archived,housebook,invoices,stay_fees}.html | pass the row's own `data-href` |
| App/app/templates/_property_overview.html | Guest links Open is an `<a>` to the card's link target |
| App/app/templates/base.html | host2.css key `20261025-0391` |
| App/tests/test_0391_open_buttons_click_browser.py | new |
| docs/design/MASTER.md | 7.1 `open` row: Open is a real link |

## 4. Steps

1. Change the macro as in §3; keep the 0252 comment, updated.
2. Pass each caller its row's exact `data-href`. `grep -rn "row_open()" App/app/templates` returns nothing.
3. Guest links card: Open is `<a class="host-property-card-open">` to `{{ base_url }}?view=settings&amp;section=guests#communication`, `tabindex="-1" aria-hidden="true"`.
4. CSS: the `.host-workspace .row-open` rule in host2.css already sets `text-decoration: none; color: var(--ink)`; no edit needed.
5. Bump the host2.css key.
6. Browser test, widths 390 and 1280, every page required: `/reservations?range=all`, `/apartments`, `/housebook`, the first property overview. Real pointer click (`click(force=True)`), then the URL is the Open's href. Non-browser test: no `row_open()` without an argument, no `<span class="row-open">`, the macro renders `<a class="row-open" href=`.
7. MASTER 7.1 line.

## 5. Do not touch

Radio/option card rules (another branch changes them). Hover rules outside the 0284 block. `app.js`.

## 6. Commands

From `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0391_open_buttons_click_browser.py tests/test_0291_open_buttons.py tests/test_0375_needs_you_and_open.py tests/test_0385_phone_card_open_browser.py tests/test_0252_touch_sweep_browser.py tests/test_design_guardrails_browser.py tests/test_host_geometry.py -q --tb=short -x 2>&1 | tail -30`. Then `git checkout -- ../docs/tasks` evidence PNGs if rewritten. From the repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance

All listed tests pass with 0 skipped; no look change in 390/1280/2000 screenshots.

## 8. Stop and ask

A row with no `data-href`; any test that needs data demo does not have.

## 9. Report

`docs/tasks/0391-report.md`: files changed, test tail, deviations.
