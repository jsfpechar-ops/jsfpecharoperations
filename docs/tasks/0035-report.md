# 0035 report

Status: review

## 1. Files changed

```
 docs/tasks/0035-posthog-sync.md
 App/app/migrations/0008_posthog_stage.sql
 App/app/posthog_sync.py
 App/app/scheduler.py
 App/app/host_i18n.py
 App/tests/test_posthog_sync.py
```

## 2. Commands

- `.venv/bin/python -m pytest tests/test_posthog_sync.py tests/test_admin_funnel.py -q` → `13 passed`
- `python3 scripts/context_lint.py` → same task-heading FAIL as 0034.

## 3. Acceptance

- [x] `sync()` no-ops when key unset; backfills stages; second run sends nothing for same host.
- [x] Failed HTTP does not advance `posthog_stage`.
- [x] Capture JSON has `$ip` null and no click-id fields.

## 4. Deviations

- `test_first_property_backfill_and_second_run_is_quiet` adjusted so a full-suite DB with other hosts does not assert global `skipped` count.

## 5. Questions

None.

## 6. Owner steps left

None until PostHog key is set on production.
