# 0036 — Retire the in-app dashboard

Status: in-progress
Depends on: 0035 | Base commit: 0035's commit | Branch: same branch
Executor: Composer 2.5 | Fits one session

(Copied from [posthog-analytics plan](../plans/posthog-analytics.md) §5.)

**Objective.** `/admin/funnel` stops being a dashboard. It becomes a short admin page with one link to the PostHog project. The CSV route goes away. `admin_funnel.rows()` stays, because 0035's job calls it.
