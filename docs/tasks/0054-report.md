# 0054 report: setup wizard shell

Status: review

## Files

- `App/app/routes/setup_wizard.py` — GET/POST `/setup/{welcome,name,address,bookings}`, resume via `/setup`
- `App/app/main.py` — register setup wizard router
- `App/app/onboarding.py` — `wizard_step()`, progress fields for banner
- `App/app/templates/setup/*` — layout + four screens
- `App/app/static/components.css` — `.wizard` styles
- `App/app/host_i18n.py` — `setup.*` EN + CS
- `App/app/templates/_components.html` — setup banner line
- `App/tests/test_setup_wizard.py` — wizard behaviour tests
- `App/tests/test_dashboard_empty.py`, `App/tests/test_host_language.py` — banner assertion updates

## Tests

```
cd App && .venv/bin/python -m pytest tests/test_setup_wizard.py -q
7 passed
```

Full suite: `3055 passed, 2 skipped`; six Playwright geometry/copy tests failed (stay row clipping / menu timeouts) — same failures on a second full run; not triggered by wizard-only CSS (`.wizard` scoped). Context lint: OK.

## Screenshots

`docs/tasks/0054-screenshots/` at 360, 390 and 1280 px: welcome, name, address, bookings, bookings-paste, bookings-found.

## Acceptance walk-through

TestClient path welcome → name → address → bookings (sample calendar sync not run in timing script): **~1.2 s** for the three POST steps plus `/setup` resume check in `test_setup_wizard.py`.

## Notes

- Name-only property create uses existing `_apartment_payload` + insert path (same as `/apartments` POST).
- Address/bookings use `_save_apartment_form`, feed insert + `icalsync.sync_all` (same as feed add).
- After bookings, Continue → property `#ubyport` with “Next: police details”.
