# 0055 report: ARES lookup (Fill from register)

Status: review

## Files changed

- `App/app/ares.py` — ARES client: IČO validation, 4 s timeout, 24 h cache, court/registry mapping, rate-limit helpers
- `App/app/routes/admin.py` — operator form re-render on `fill_from_register` (no save)
- `App/app/routes/invoices.py` — invoice settings and buyer fill paths
- `App/app/templates/entities.html`, `invoice_settings.html`, `invoice_form.html` — secondary button + ARES notes
- `App/app/host_i18n.py` — `ares.*` EN + CS strings
- `App/tests/test_ares.py` — mocked `requests.get`, fill/merge/rate-limit/court/i18n coverage

Decision line in `docs/context/decisions.md` was already present; not edited.

## Outbound request (PR)

On **Fill from register**, the app sends **only the typed IČO** to the Czech public register:  
`GET https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}`  
Reason: pre-fill operator, invoice settings, and buyer fields from free public data; nothing is stored until Save.

## Commands (last 5 lines each)

Targeted pytest:

```
  /uby-0055/App/.venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 1 warning in 1.11s
```

Full pytest:

```
FAILED tests/test_host_wide_geometry_browser.py::test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned
6 failed, 3060 passed, 2 skipped, 7 warnings in 459.20s (0:07:39)
```

(Failures are existing stays/dashboard geometry clipping; no changes in those templates.)

Context lint:

```
WARN  3 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
next free: task 0063 | migration 0009
context lint: OK
```

## §7 acceptance

- [x] `/entities` fill with valid IČO (mocked) fills fields, shows ARES note, does not persist without Save (`test_entities_fill_does_not_save`)
- [x] Screenshots after a live fill of IČO 27074358 at 360, 390 and 1280 px: `docs/tasks/0055-evidence/{entities,invoice-settings,invoice-buyer}-{360,390,1280}.png`
- [x] PR documents outbound ARES request and reason (above)

## Stop conditions

- No other IČO outbound path or CSP/egress block found for `ares.gov.cz`.
- Entities POST re-render without save works via early return before `db.insert` / `db.update`.

## Questions

None.
