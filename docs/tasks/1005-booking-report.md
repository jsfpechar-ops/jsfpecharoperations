# 1005: Photo reorder row and phone nav

Status: review

## Files changed

- `App/app/templates/property_page_review.html` — `pp-photo-moves`, `_csrf` on move/delete, regular arrow buttons
- `App/app/static/host.css` — `.pp-photo-moves`; `base.html` cache bump `host.css?v=20261107-2337a`
- `App/app/templates/_shell_tabbar.html` — Booking site in More menu + `more_nav`
- `App/tests/test_property_page_photos.py`, `App/tests/test_booking_site_host.py`

## Commands (last lines)

```
38 passed, 1 warning in 1.93s
6 passed in 214.65s (layout + geometry, 0 skipped)
design lint: OK
context lint: OK
```

## §7

- [x] No `style=` on reorder row; regular `ui-btn` arrows (44 px on phone).
- [x] Move POST with `_csrf` from HTML only (no JS header).
- [x] Phone More lists Booking site (`external-link` icon).
- [x] Screenshots reviewed (path below).

## Screenshots

`/opt/cursor/artifacts/pr803-after-1005/` (REVIEW.md absent on VM; captured locally).

390 `/apartments/<id>/page`: five photo thumbs wrap; `pp-photo-moves` under each with Main photo label, full-size ↑/↓; delete × overlay unchanged; bottom tab bar visible. Lint: one `tight-side` between delete × and ↑ (overlay positioning, not arrow pair).

768/1280: same photo row; arrows spaced with `--space-3`; sidebar on 1280. Same ×/↑ lint on 768 only; no arrow-pair `tight-side` at 1280.

390 More sheet: Booking site between Payments and Settings.

## Deviations

- `base.html` bumped for `host.css` cache (brief step 1).
- Owner fixture in `test_property_page_photos.py` uses `auth.create_account` + extra cleanup rows for login/audit FKs.

## Questions

None.
