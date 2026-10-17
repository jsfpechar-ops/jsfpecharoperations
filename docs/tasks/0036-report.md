# 0036 report

Status: review

## 1. Files changed

```
 docs/tasks/0036-posthog-funnel-page.md
 App/app/templates/admin_funnel.html
 App/app/routes/admin_accounts.py
 App/app/config.py (POSTHOG_APP_URL)
 App/app/static/app.css (funnel dashboard block removed)
 App/app/host_i18n.py (funnel strings trimmed)
 App/tests/test_admin_funnel.py
 App/tests/test_skeleton_loaders.py
 App/tests/test_posthog_sync.py (isolation tweak)
```

## 2. Commands

- `.venv/bin/python -m pytest tests/test_admin_funnel.py tests/test_posthog_sync.py -q` → `13 passed`
- `.venv/bin/python -m pytest tests -q` → `2980 passed, 2 skipped` (after posthog sync test fix).

## 3. Acceptance

- [x] `/admin/funnel.csv` → 404.
- [x] `/admin/funnel` has no `<table>`; shows PostHog sentence.
- [x] `posthog_sync.sync` tests still pass.
- [x] Screenshots: `docs/tasks/0036-screenshots/admin-funnel-{360,390,1280}.png` (rendered HTML with admin session).

## 4. Deviations

None.

## 5. Questions

None.

## 6. Owner steps left

Open PostHog from `/admin/funnel` after setting `POSTHOG_PROJECT_API_KEY` (link uses `POSTHOG_APP_URL`, default `https://eu.posthog.com`).
