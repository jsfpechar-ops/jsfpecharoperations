# 1008: Booking-site bookings list and photo tiles: spacing that passes the lint

Status: todo
Depends on: 1006 (same template) | Base commit: 6217fcc8 | Branch: task/0999-property-rules-map (same PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Round 2 of the PR 803 review, with real direct-pay rows seeded: on `/apartments/<id>/booking-site` the bookings list still fails `layout_lint.js` at 768 px (`tight-stack`: buttons of neighbouring rows sit 1 px apart), and at 390 px the buttons wrap raggedly ("Zamítnout" alone on a line, the next row's name glued under it). On `/apartments/<id>/page` the "Hlavní fotka" label widens the first photo tile, so its × floats off the image, and the photo grid still uses `style=""` (design-system rule 2). This brief fixes both with one CSS block and two template edits.

## 2. Context

Design system (`docs/design/design-system.md`): rule 2 tokens only, no `style=""`; rule 3 12 px minimum between neighbours. Tokens: `--space-3: 0.75rem` (12 px), `--space-2` (8 px).

`App/app/templates/booking_site_setup.html` (current):

```html
{% call ui_section(t('bsite.bookings.title')) %}
  {% if bookings %}
  <dl class="ui-facts">
```

and inside each row `<dd><div class="ui-btn-group"> {{ ui_badge(...) }} <form ...>...</form> ... </div></dd>`.

`App/app/templates/property_page_review.html` (current):

```html
  <div style="display:flex;flex-wrap:wrap;gap:8px;">
    {% for p in page_photos %}
    <div style="position:relative">
```

and

```html
      <div class="pp-photo-moves">
        {% if first %}<span class="ui-sub">{{ t('payments.page.photo_main') }}</span>{% endif %}
```

`App/app/static/host.css` ends with `.host-workspace .pp-photo-moves { display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-2); }`.

If any excerpt is not found verbatim, STOP.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/templates/booking_site_setup.html | edit | `bsite-bookings` class on the list |
| App/app/templates/property_page_review.html | edit | classes instead of `style=""`; main-photo label below the arrows |
| App/app/static/host.css | edit | one block |
| App/app/templates/base.html | edit | bump the `host.css?v=` key |
| App/tests/static_versions.json | regenerate | `test_static_versions.py --write` |

No other file may change.

## 4. Steps

1. `booking_site_setup.html`: `<dl class="ui-facts">` in the bookings section becomes `<dl class="ui-facts bsite-bookings">`.
2. `property_page_review.html`: replace `<div style="display:flex;flex-wrap:wrap;gap:8px;">` with `<div class="pp-photo-grid">` and `<div style="position:relative">` with `<div class="pp-photo-tile">`. Delete the line `{% if first %}<span class="ui-sub">...photo_main...</span>{% endif %}` inside `.pp-photo-moves`, and right after the closing `</div>` of `.pp-photo-moves` add `{% if first %}<p class="ui-sub pp-photo-main">{{ t('payments.page.photo_main') }}</p>{% endif %}`. Remove `style="object-fit:cover;border-radius:8px;"` from the `<img>` (step 3 styles it), and on the photo-delete `<form>` replace `style="position:absolute;top:4px;right:4px;"` with `class="pp-photo-del"`.
3. Append to `App/app/static/host.css`:

```css
.host-workspace .pp-photo-grid { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.host-workspace .pp-photo-tile { position: relative; width: 120px; }
.host-workspace .pp-photo-tile img { object-fit: cover; border-radius: var(--radius-2, 8px); }
.host-workspace .pp-photo-del { position: absolute; top: var(--space-1); right: var(--space-1); }
.host-workspace .pp-photo-main { margin: var(--space-1) 0 0; }
.host-workspace .bsite-bookings > div { padding-block: var(--space-3); }
.host-workspace .bsite-bookings dd .ui-btn-group { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-start; gap: var(--space-3); }
.host-workspace .bsite-bookings dd .ui-btn-group > form { margin: 0; }
```

   (If `--radius-2` is not in `tokens.css`, use the radius token the file already uses for cards: `grep -n "radius" App/app/static/tokens.css | head`.)
4. Bump the `host.css?v=` key in `base.html` to today, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`.
5. Seed check (do not commit): the layout lint has no direct rows. Run it with the scratch test from the round-2 review (`/mnt/project-files/pr803-review/round2/test_zz_r2_lint_direct.py`, copy into `App/tests/`, run, then delete it before committing).

## 5. Do not touch

`app2.css`, `_ui.html`, any guest template, any Python file. AGENTS.md rules 7, 10.

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_property_page_photos.py tests/test_booking_site_host.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30
UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_zz_r2_lint_direct.py tests/test_layout_lint_browser.py tests/test_host_geometry.py tests/test_design_guardrails_browser.py -q --tb=short 2>&1 | tail -30
```

Expected: pass, 0 skipped (the `guest-new` Cancel 43 px finding in test_design_guardrails is a known font-metric issue of non-CI machines; say so if you see it).

## 7. Acceptance

- [ ] Lint with direct rows: no `tight-stack` / `tight-side` on `booking-site` at any width.
- [ ] 390 and 768 px screenshots of the bookings list (requested, expired, paid direct, paid card rows): badge and buttons on one wrapping line, 12 px gaps, rows separated.
- [ ] 390 px screenshot of `/apartments/<id>/page` photos: × inside every image, all tiles the same width, "Hlavní fotka" under the first tile's arrows.
- [ ] `grep -n 'style="display:flex' App/app/templates/property_page_review.html` prints nothing.

## 8. Stop and ask

As in TEMPLATE.md §8.

## 9. Report

`docs/tasks/1008-report.md`, 600 tokens at most, `Status: review`, with the screenshots.

## Risk list (for the reviewer)

`host.css`, `property_page_review.html`.

## Owner steps

None.
