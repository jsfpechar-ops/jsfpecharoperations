# 0035 — Host profiles and stage events

Status: review
Depends on: 0033 | Base commit: 0034's commit | Branch: same branch
Executor: Composer 2.5 | Fits one session

(Copied from [posthog-analytics plan](../plans/posthog-analytics.md) §5.)

## 1. Objective

A scheduler job sends each host's reached funnel stages and person properties to PostHog. This is the in-app analytics move. Failures never block filing, sign-up or login.

## 2. Context

Full behaviour, tests and acceptance are in [posthog-analytics plan](../plans/posthog-analytics.md) §5.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0008_posthog_stage.sql` | new | `posthog_stage` column on `user_account` |
| `App/app/posthog_sync.py` | new | `sync() -> dict` with counts `sent`, `skipped`, `failed` |
| `App/app/scheduler.py` | edit | job id `posthog`, every 15 minutes |
| `App/app/host_i18n.py` | edit | `notification.job_name.posthog` |
| `App/tests/test_posthog_sync.py` | new | sync tests |

## 4. Steps

See the plan §5 and `docs/tasks/0035-report.md` for the implemented behaviour.

## 5. Do not touch

Guest tables, `ad_click`, Umami remnants outside this slice.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_posthog_sync.py tests/test_admin_funnel.py -q`, then full suite.

## 7. Acceptance

- [x] `sync()` no-ops when key unset; backfills stages; second run quiet for same host.
- [x] Failed HTTP does not advance `posthog_stage`.
- [x] Capture JSON has `$ip` null and no click-id fields.

## 8. Stop and ask

As in [TEMPLATE](TEMPLATE.md) §8.

## 9. Report

`docs/tasks/0035-report.md`.
