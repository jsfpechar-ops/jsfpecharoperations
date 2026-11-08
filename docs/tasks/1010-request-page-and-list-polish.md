# 1010: Request page centred, guest buttons styled, bookings list wraps cleanly on phone

Status: todo
Depends on: 1009 | Base commit: 22613010 | Branch: task/0999-property-rules-map (same PR #803)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Round 3 of the PR 803 review, layout only:
- The "Poptávka odeslána" request page sits left of centre at 768 and 1280 px (other guest booking pages are centred). It also nests a second `<main>` inside the base `<main>`.
- In its IBAN card, the paragraphs keep the browser's default margins on top of the card gap, so there is about 40 px between the IBAN and the variable-symbol line.
- Guest buttons on `/p/<slug>` and on the request page ("Zobrazit cenu", "Pokračovat", "Odeslat poptávku", "Zaplatit přes Revolut") show the browser's default button chrome: a bevelled border, square corners and normal weight.
- On the host bookings list at 390 px, the status badge shares a wrapping row with the buttons, so "Zamítnout" sometimes ends up alone on a line ("Vypršelo" row).

## 2. Context

Rules: AGENTS.md rule 7 (guest page: browser and geometry tests green, 0 skipped, 390 px screenshot per changed page) and rule 10 (host page: layout lint, 390/768/1280 screenshots, per-page notes).

`App/app/templates/property_page_requested.html` (current) opens with `<main class="pp"><section class="pp-bk">` and closes with `</section></main>`.

`App/app/templates/_pp_booking_css.html` (current lines):

```css
.pp-bk { display: flex; flex-direction: column; gap: var(--space-4); max-width: 520px; margin-top: var(--space-6); }
.pp-bk .ui-btn { width: 100%; min-height: 44px; }
.pp-bk-page { max-width: 520px; margin: var(--space-6) auto; padding: 0 var(--space-4); }
```

`App/app/static/host.css` (end of file, added by 1008):

```css
.host-workspace .bsite-bookings dd .ui-btn-group { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-start; gap: var(--space-3); }
```

The badge is the first child of that `.ui-btn-group` (`<span class="ui-badge ...">`), followed by one or two `<form>`s.

If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/property_page_requested.html | edit | one wrapper, centred |
| App/app/templates/_pp_booking_css.html | edit | button chrome; card paragraph margins |
| App/app/static/host.css | edit | phone grid for the bookings row |
| App/app/templates/base.html | edit | bump the host.css `?v=` key |
| App/tests/static_versions.json | edit | refresh as the static-versions test asks |

## 4. Steps

1. `property_page_requested.html`: replace `<main class="pp"><section class="pp-bk">` with `<div class="pp-bk pp-bk-page pp-bk-req">` and `</section></main>` with `</div>`. Change nothing inside.
2. `_pp_booking_css.html`: change the `.pp-bk .ui-btn` rule to
   `.pp-bk .ui-btn { width: 100%; min-height: 44px; border: 1px solid transparent; border-radius: var(--radius-2); font: inherit; font-weight: 600; cursor: pointer; }`
   (it must stay above the `.pp-bk .ui-btn-primary` and `.pp-bk .ui-btn-secondary` rules so their colours and borders still win). Then append before `</style>`:
   `.pp-bk-req .pp-bk-card p { margin: 0; }`
3. `host.css`, append:
   ```css
   @media (max-width: 639px) {
     .host-workspace .bsite-bookings dd .ui-btn-group { display: grid; grid-template-columns: repeat(2, max-content); justify-items: start; }
     .host-workspace .bsite-bookings dd .ui-btn-group > .ui-badge { grid-column: 1 / -1; }
   }
   ```
4. Bump the `host.css?v=` value in `base.html` (today's date and `1010a`), then update `tests/static_versions.json` the way `test_static_versions.py` tells you.
5. Run §6. Then take screenshots at 390, 768 and 1280 px with Playwright (`chromium.launch()`, no options) of: `/p/<slug>` with a stay selected, for a host with Stripe and the direct rails; the request page of a direct request; and `/apartments/<id>/booking-site` with requested, expired, paid and declined direct rows. Seed them like `test_layout_lint_browser.py`'s `wide_host` and `booking_checkout.start_direct`. Save the screenshots to `/mnt/project-files/pr803-review/after1010/` and open each one.

## 5. Do not touch

Copy, Python, other templates, `host.css` rules above the end of the file. AGENTS.md rules 6, 7, 10.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_static_versions.py tests/test_booking_site_host.py tests/test_property_page.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py tests/test_booking_site_page_browser.py tests/test_booking_manage_browser.py tests/test_booking_site_host_browser.py -q --tb=short -rs 2>&1 | tail -30
```

## 7. Acceptance

- [ ] Request page is centred at 768 and 1280; only one `<main>` element on it; the IBAN and variable-symbol lines are 12 px apart.
- [ ] Guest buttons have rounded corners, no bevel, weight 600, height ≥ 44 px.
- [ ] Bookings list at 390: the badge sits alone on its own line, and the buttons are on the next line(s) and left-aligned. At 768 and 1280 every row is still one line.
- [ ] The browser files pass, 0 skipped. Write notes per page and per width in the report.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/1010-report.md`, 600 tokens at most, `Status: review`.

## Risk list (for the reviewer)

`_pp_booking_css.html` button rule (all `/p/` booking pages), the host.css phone grid.

## Owner steps

None.
