# 0036 — Retire the in-app dashboard

Status: review
Depends on: 0035 | Base commit: 0035's commit | Branch: same branch
Executor: Composer 2.5 | Fits one session

(Copied from [posthog-analytics plan](../plans/posthog-analytics.md) §5.)

## 1. Objective

`/admin/funnel` stops being a dashboard. It becomes a short admin page with one link to the PostHog project. The CSV route goes away. `admin_funnel.rows()` stays, because 0035's job calls it.

## 2. Context

See [posthog-analytics plan](../plans/posthog-analytics.md) §5 and `docs/tasks/0036-report.md`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/admin_funnel.html` | edit | Link to PostHog; remove dashboard table |
| `App/app/routes/admin_accounts.py` | edit | Drop CSV route; pass `posthog_url` |
| `App/app/config.py` | edit | `POSTHOG_APP_URL` |
| `App/app/static/app.css` | edit | Remove funnel dashboard styles |
| `App/app/host_i18n.py` | edit | Trim funnel copy |
| `App/tests/test_admin_funnel.py` | edit | CSV 404; page shape |
| `App/tests/test_skeleton_loaders.py` | edit | Funnel page loaders |

## 4. Steps

Implement the file list; details in the plan and report.

## 5. Do not touch

`admin_funnel.py` query logic (0035 depends on it).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_admin_funnel.py tests/test_posthog_sync.py -q`, then full suite.

## 7. Acceptance

- [x] `/admin/funnel.csv` → 404.
- [x] `/admin/funnel` has no `<table>`; shows PostHog sentence.
- [x] `posthog_sync` tests still pass.

## 8. Stop and ask

As in [TEMPLATE](TEMPLATE.md) §8.

## 9. Report

`docs/tasks/0036-report.md` (includes screenshots).
