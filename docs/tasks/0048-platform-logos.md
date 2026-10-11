# 0048: Show the platform logo next to each booking source

Status: done
Depends on: owner logo files in App/app/static/platforms/ | Branch: task/0048-platform-logos
Executor: Cursor local agent | Fits one session

## 1. Objective
Wherever UbyHost shows where a stay or calendar comes from, it shows the platform's small logo before the name ("[logo] Airbnb"), like Superhostem does. The host recognises the source at a glance. With no logo file, the text name shows alone, as today.

## 2. Context
- Rule 2 (privacy): no third-party requests. Logos are served from our own `/static/`; never hotlink a platform URL.
- Rule 9 and HOST_APP_DESIGN §3: a text label carries the meaning; the image is decoration (`alt=""`, `aria-hidden="true"`).
- `App/app/templating.py` `_source_label(context, reservation)` (line ~229) returns the source name; registered as `source_label` (line ~377).
- `App/app/icalsync.py` `PLATFORM_HINTS` keys: airbnb, booking, agoda, vrbo, expedia, tripadvisor, trip, google, apple.
- Places: `App/app/templates/reservations.html` (`stay-col-source` cell, line ~169), `reservation_detail.html` (where the source appears; grep `source_label`), `apartment_form.html` feed table "portal" cell (`feed.label`, line ~517), the landing "works with" line (`landing_i18n.py` key `landing.benefit.calendar.body` area; find the template that renders it).
- Do NOT draw, trace or recreate any logo. Use only the files the owner placed in `App/app/static/platforms/`.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/icalsync.py | edit | add `("echalupy", ("e-chalupy", "echalupy"))` to `PLATFORM_HINTS` (labelling only; no other sync change) |
| App/app/static/platforms/airbnb.svg, booking.svg, echalupy.svg | add | owner-supplied files (already prepared: square icons, checked for scripts) |
| App/app/templating.py | edit | `source_mark(key)` helper: returns the `<img>` markup when `static/platforms/{key}.svg` (or .png) exists, else ""; checked once at startup |
| App/app/templates/_components.html | edit | macro `source_badge(key, label)` = mark + label in one inline-flex span |
| App/app/templates/reservations.html | edit | use `source_badge` in the source cell |
| App/app/templates/reservation_detail.html | edit | same |
| App/app/templates/apartment_form.html | edit | feed table portal cell |
| the landing template that shows supported platforms | edit | logo row, text names kept |
| App/app/static/components.css | edit | `.source-badge img { width:16px; height:16px; }` plus a 6 px gap; landing row 20 px |
| App/tests/test_source_badge.py | new | tests |

## 4. Steps
1. `source_mark(key)`: key is lower-case `[a-z]+`, otherwise "". Look up an existing file once (cache a dict at import). Markup: `<img src="/static/platforms/{key}.svg" alt="" aria-hidden="true" width="16" height="16" loading="lazy">`.
2. Manual and unknown sources: no image, label only.
3. Feed table: derive the key from the stored portal or label with `icalsync.platform_of(feed.url)` (pure function; no fetch).
4. Tests: badge has an img for a key whose file exists (create a temp file in the test or monkeypatch the cache); label-only for missing files and for "manual"; no `http` in the img src; alt is empty.

## 5. Do not touch
Sync logic, migrations, guest pages, tokens.css.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped (rule 7).

## 7. Acceptance
- [ ] Stays list, stay detail and the calendar table show logo + name for Airbnb and Booking (demo data), at 360, 390 and 1280 px.
- [ ] `test_privacy_first.py` still passes (no external host in any page).

## 8. Stop and ask
1. No files exist in `App/app/static/platforms/`: stop; the owner must add them (do not create images).
2. The landing page has no single place that lists platforms: skip it and say so.

## 9. Report
Files, test tail, screenshots.
