# 0043 report: Police setup asks for 3 fields, fills the rest

Status: review

## Files changed

- `App/app/validation.py` — `mark_from_ws_user()` for production `uby-ws` logins only
- `App/app/routes/admin.py` — `_apply_police_defaults()` on create and update
- `App/app/templates/apartment_form.html` — IDUB + login/password first; derived fields in `details.police-derived`
- `App/app/host_i18n.py` — EN/CS `derived_*` strings
- `App/tests/test_police_defaults.py` — new coverage per brief §4
- `App/tests/test_flash_next_step.py` — save flash no longer lists facility name when auto-filled
- `App/tests/test_ubyport_sample_pdf.py` — asserts new derived hints on the property form
- `docs/tasks/0043-police-setup-fewer-fields.md` — Status: review
- `docs/tasks/0043-evidence/` — property page screenshots (closed/open × 360/390/1280)

## Commands (last 5 lines each)

Focused:

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
8 passed, 1 warning in 1.07s
```

Full pytest (`App/`):

```
FAILED tests/test_host_wide_geometry_browser.py::test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned
6 failed, 3056 passed, 2 skipped, 7 warnings in 420.02s (0:07:00)
```

Context lint:

```
WARN  2 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 0063 | migration 0009
context lint: OK
```

## §7 acceptance

- [x] New property: IDUB + login + password + property name + operator → readiness can clear police fields via defaults on save (see `test_create_applies_defaults_from_login_and_operator`)
- [x] Existing typed values preserved (`test_typed_police_fields_are_never_replaced`)
- [x] Screenshots: `docs/tasks/0043-evidence/property-ubyport-{closed,open}-{360,390,1280}.png`

## §8

1. **OWNER CHECK (§8.1):** Confirmed 2026-10-11. Production login `UBY-WS_MLJNO` → abbreviation `MLJNO` (the characters after `UBY-WS_`). `mark_from_ws_user` uses that form, and still accepts a six-character suffix with no underscore. Test logins (`uby-tws`) are not used.
2. §2 excerpts: found as described.
3. Entity list: `access.entities(request)` in both handlers; no new SQL.

## Deviations

- Six browser geometry / dashboard tests failed on stay-row action clipping at 1280px (`test_host_wide_geometry_browser`, `test_host_stay_actions_browser`, `test_host_quiet_dashboard_browser`, `test_host_feedback_browser`). Failures are on the stays list, not the property police section; likely pre-existing in this environment (Copy/More actions extend past panel right edge). Re-run those modules locally if CI requires zero failures.

## Screenshots

| File | Viewport | Derived block |
|---|---|---|
| `0043-evidence/property-ubyport-closed-360.png` | 360 | closed |
| `0043-evidence/property-ubyport-closed-390.png` | 390 | closed |
| `0043-evidence/property-ubyport-closed-1280.png` | 1280 | closed |
| `0043-evidence/property-ubyport-open-360.png` | 360 | open |
| `0043-evidence/property-ubyport-open-390.png` | 390 | open |
| `0043-evidence/property-ubyport-open-1280.png` | 1280 | open |
