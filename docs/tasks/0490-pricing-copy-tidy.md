# 0490: Ceník: one name per plan, clearer bands, no OCR row, no "10+ write to us"

Status: todo

## 1. Objective

Tidy the public pricing page copy (CS and EN). Prices do not change. Owner approved 2026-11-01 (signup review, points 1, 2, 4, 5 and the 10+ line).

## 2. Context

The page calls the plans "UbyHost" and "UbyHost Max"; the app calls them Standard and Max. The band labels "5–9" and "10+" read as volume pricing although the rates are marginal. "Napište nám" for 10+ contradicts the published 10+ rate. Max says both "5×" and "naplno". OCR is not built.

## 3. Files

`App/app/landing_i18n.py`, `App/app/templates/pricing.html`, `App/app/static/landing.css`, every template that links `landing.css?v=20261027-pricing-v3`, `App/tests/static_versions.json`, and the tests in §6 only where an assertion names a string changed here.

## 4. Steps

1. `App/app/landing_i18n.py`, English block (around line 136): set these values exactly.
   - `"pricing.std.name": "Standard"`
   - `"pricing.max.name": "Max"`
   - `"pricing.max.f1": "Everything in Standard"`
   - `"pricing.max.f2": "Leon AI concierge for guests, 24/7"`
   - `"pricing.max.f3": "Havel AI for you, 24/7"`
   - `"pricing.bands.title": "Standard rates per apartment"`
   - `"pricing.bands.b2": "from the 5th"`, `"pricing.bands.b3": "from the 10th"`
   - Delete the lines `pricing.max.f6`, `pricing.final.large`, `pricing.final.write`, `pricing.final.subject`.
2. Same file, Czech block (around line 419):
   - `"pricing.std.name": "Standard"`
   - `"pricing.max.name": "Max"`
   - `"pricing.max.f1": "Vše ze Standardu"`
   - `"pricing.max.f2": "AI concierge Leon pro hosty, 24/7"`
   - `"pricing.max.f3": "AI Havel pro vás, 24/7"`
   - `"pricing.bands.title": "Sazby Standard za apartmán"`
   - `"pricing.bands.b2": "od 5."`, `"pricing.bands.b3": "od 10."`
   - Delete `pricing.max.f6`, `pricing.final.large`, `pricing.final.write`, `pricing.final.subject`.
   - If any other language block in the file has these keys, apply the same deletions there and leave its other values.
3. `App/app/templates/pricing.html`, anchor `{% for n in (1, 2, 3, 4, 5, 6) %}<li{% if n == 6 %}`: replace the whole line with
   `            {% for n in (1, 2, 3, 4, 5) %}<li>{{ tick() }}{{ t('pricing.max.f' ~ n) }}</li>{% endfor %}`
4. Same file, anchor `<p>{{ t('pricing.final.large') }}`: delete from `<p>{{ t('pricing.final.large') }}` through the matching `</p>` on that line, keep `<div><h2>{{ t('pricing.final.title') }}</h2>` and the closing `</div>`.
5. `App/app/static/landing.css`: delete the line `.pricing-coming-soon { color: var(--ink-muted); }`. Then in `App/app/templates/` replace every `landing.css?v=20261027-pricing-v3` with `landing.css?v=20261101-pricing-v4` (`grep -rlF` then `sed -i`). Run `cd App && .venv/bin/python tests/test_static_versions.py --write`.
6. Run §6. Where a test asserts a removed or renamed string (`UbyHost Max`, `.pricing-coming-soon`, the 10+ mailto, `contact_click` on the pricing page), change only that assertion to the new copy, or drop it if the element is gone. Do not relax any other assertion.

## 5. Do not touch

Prices, `billing*.py`, the in-app subscription page, `host_i18n.py`, any other public page copy.

## 6. Commands

From `App/`:
`.venv/bin/python -m pytest tests/test_public_*.py tests/test_landing_*.py tests/test_0412_pricing_browser.py tests/test_umami_guard.py tests/test_static_versions.py tests/test_no_em_dashes.py -q --tb=short -x -rs 2>&1 | tail -30` (browser tests: 0 skipped). Then from the repo root `python3 scripts/context_lint.py | tail -3`.

## 7. Acceptance

- [ ] /cenik shows "Standard" and "Max", bands "od 5." / "od 10.", no OCR row, no "Napište nám" line, in CS and EN.
- [ ] §6 green, 0 skipped. One 390 px screenshot of /cenik (CS) in `docs/tasks/screenshots-0490/`.

## 8. Stop and ask

An anchor is missing, or a test fails for a reason other than the changed copy.

## 9. Report

`docs/tasks/0490-report.md`.
