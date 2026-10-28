# 0430 report: property slugs — mapper, migration 0028, redirects

Status: review

## Files

- `App/app/migrations/0028_property_slug.sql` (new): `property_slug`
  (live mapping + publish flag) and `property_slug_history` (301 trail),
  both cascaded with the apartment.
- `App/app/property_page.py` (new): `normalise_name`, `slug_for`
  (name + 4-char sha256 suffix — deterministic, no state),
  `ensure_slug` (rename moves the old slug to history), `resolve`
  (history 301 → live → published/missing), `publish`.
- `App/app/routes/property_page.py` (new): public `GET /p/<slug>` —
  301 from history, 404 when unpublished/unknown, rate-limited per the
  guide-QR pattern; 0431 replaced the stub with the real template.
- `App/app/main.py`: public router include.
- `App/tests/test_property_slug.py` (new): 9 tests.

## Commands (last lines)

- `pytest tests/test_property_slug.py` → 9 passed
- `migration_guard.py <base>` → OK
- Browser row: `/p/<slug>` pages join the CI shard with 0431's template.

## Findings

- Slugs are recomputed from the row: same name → same slug, forever;
  two properties with the same name get different hash suffixes (tested).
- Rename keeps a working 301; the 0345 QR codes keep resolving (tested).
- `db.insert` cannot be used for `property_slug_history` (no `id`
  column for RETURNING): plain `db.execute` INSERT.

## Owner steps

1. Confirm the slug shape in CI screenshots; merge when green.
