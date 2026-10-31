# 0458: Police deadline counts holidays as working days
Status: todo
Depends on: none | Base commit: main | Branch: task/0458-deadline-weekends-only
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens
## 1. Objective
Owner decision 2026-10-31: the 3-working-day UbyPort deadline skips weekends only. Public holidays count as working days. This only ever makes a deadline earlier, never later.
## 2. Context
`App/app/deadlines.py` computes Czech public holidays per year and `is_working_day()` excludes them. Rule 1 (filing correctness) is kept: filing earlier is always compliant. Plan: [migration-plan-v4](../plans/postgresql/migration-plan-v4.md) step 2.
## 3. Files
`App/app/deadlines.py`, `App/tests/test_deadlines.py`, `docs/UBYPORT_CORE.md` (the one sentence that describes the deadline), guest-facing copy only if a template states "public holidays" (grep `holiday` in `App/app/templates` and `App/app/i18n` first; report hits, change only the deadline sentence).
## 4. Steps
1. Make `is_working_day()` return `day.weekday() < 5`. Delete `public_holidays`, `holiday_set` and the Easter helper if nothing else imports them (`grep -rn "holiday" App/app`).
2. Update the 25 deadline tests: cases that landed on a holiday now expect the earlier date. Keep weekend cases unchanged.
3. Edit the deadline sentence in `docs/UBYPORT_CORE.md`.
4. Run the test-map row for `deadlines.py`.
## 5. Acceptance
Tests pass, 0 skipped. No remaining reference to holidays in `App/app`.
## 6. Report
`docs/tasks/0458-report.md`: diff summary, test tail, list of copy hits found.
