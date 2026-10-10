# 0035 — Host profiles and stage events

Status: in-progress
Depends on: 0033 | Base commit: 0034's commit | Branch: same branch
Executor: Composer 2.5 | Fits one session

(Copied from [posthog-analytics plan](../plans/posthog-analytics.md) §5.)

**Objective.** A scheduler job sends each host's reached funnel stages and person properties to PostHog. This is the in-app analytics move. Failures never block filing, sign-up or login.

**Files.**

- [App/app/migrations/0008_posthog_stage.sql](App/app/migrations/0008_posthog_stage.sql)
- [App/app/posthog_sync.py](App/app/posthog_sync.py) — new. `sync() -> dict` with integer counts `sent`, `skipped`, `failed`.
- [App/app/scheduler.py](App/app/scheduler.py) — job id `posthog`, every 15 minutes
- [App/app/host_i18n.py](App/app/host_i18n.py) — `notification.job_name.posthog`
- [App/tests/test_posthog_sync.py](App/tests/test_posthog_sync.py) — new.

(See plan for full behaviour, tests and acceptance.)
