# 0047 report: Dashboard missing-report banner

## Files

- `App/app/routes/admin.py` — build `missing_report_display` / `missing_report_more` from `_readiness(..., invite=False)` and `_apartment_issues()` for active properties only; `_readiness` accepts `invite=False` so the dashboard does not load controller data.
- `App/app/templates/dashboard.html` — single amber `notification-bubble warning` at the top of the work queue (hidden while the onboarding banner shows); per-property lines with linked missing report fields; cap at five properties plus “and N more” → `/apartments`.
- `App/app/host_i18n.py` — `dashboard.missing_banner.missing`, `dashboard.missing_banner.and_more` (EN + CS).
- `App/tests/test_dashboard_missing_banner.py` — readiness order, absent when complete, sixth property collapse, inactive omitted; optional `UBYHOST_CAPTURE_0047=1` screenshot helper.

## Tests

From `App/`:

```text
$ .venv/bin/python -m pytest tests/test_dashboard_missing_banner.py tests/test_dashboard_empty.py tests/test_query_budget.py -q
....................                                                     [100%]
20 passed, 1 warning in 2.95s
```

Root: `python3 scripts/context_lint.py` — OK.

## Screenshots

Captured with `UBYHOST_CAPTURE_0047=1 .venv/bin/python -m pytest tests/test_dashboard_missing_banner.py::test_capture_banner_screenshots` (demo-style incomplete properties, onboarding dismissed).

| Case | 360px | 390px | 1280px |
|---|---|---|---|
| 1 incomplete property | `generated_images/0047-evidence/one-incomplete-360.png` | `one-incomplete-390.png` | `one-incomplete-1280.png` |
| 6 incomplete properties | `six-incomplete-360.png` | `six-incomplete-390.png` | `six-incomplete-1280.png` |
