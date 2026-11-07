# 0999 report

Status: review

## Files changed

- `App/app/migrations/0038_property_page_house_rules.sql`, `App/migrations_pg/00009_property_page_house_rules.sql`
- `App/app/property_page.py`, `App/app/routes/property_page.py`, `App/app/routes/payments.py`
- `App/app/templates/property_page.html`, `App/app/templates/property_page_review.html`
- `App/app/host_i18n.py`
- `App/tests/test_property_page_rules.py`, `App/tests/test_db_postgres.py`, `App/tests/test_migrations.py`
- `docs/context/test-map.md`

## Commands (last 5 lines each)

```
45 passed in 3.81s
```
(property pytest row)

```
33 passed in 63.64s
```
(browser/geometry)

```
4 passed in 204.66s
```
(layout lint)

```
context lint: OK
```

## Acceptance (§7)

- [x] Migration 0038 and pg twin 00009; schema asserts at 38
- [x] Prefill only when empty; host save overwrites
- [x] Public page: rules, map link, no street/number, no iframe/third-party script
- [x] §6 tests green, browser 0 skipped
- [x] 390/768/1280 screenshots inspected (public + host review)
- [x] Outbound: plain mapy.cz link on click only

## Deviations

- Owner approved: also `App/tests/test_migrations.py` max migration `38` and remaining `37`→`38` asserts in `test_db_postgres.py` (lines 318, 334, 345, 1055, 1068) beyond brief §3.

## Questions

- None.

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh <PR>` when CI is green.
2. Deploy; migration 0038 / 00009 on start.
3. Check `/apartments/<id>/page` after Airbnb import and public `/p/<slug>`.
