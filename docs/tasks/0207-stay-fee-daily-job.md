# 0207: Daily job that confirms clean stay-fee periods and emails them

Status: todo
Depends on: 0206 | Base commit: after 0206 | Branch: claude/project-thread-9ov0nz
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [stay-fee-monthly-email](../plans/stay-fee-monthly-email.md) (brief 4 of 4)

## 1. Objective

Every morning, for hosts with the switch on (0205): seal each fee property's last period once it is clean, from the 2nd day after it ends, and email the report (0206). A blocked period gets one "what to fix" email and is checked again daily. A period the host saved or corrected by hand is emailed too, so every confirmed report reaches the operator's inbox.

## 2. Context

- `stay_fee_auto.emails_enabled(user_id)`, `check`, `confirm`, `period_label` (0205/0206). `mail_notify.queue_stay_fee_report(apartment, filing_row)`, `queue_stay_fee_blocked(apartment, group, issues)`.
- `stay_fee.cadence_of(apartment)`, `stay_fee.is_active(apartment)`, `stay_fee.previous_month(today)`, `stay_fee.period_bounds(cadence, month) -> (first, last)`, `stay_fee.shift_month(month, delta)`. `stay_fee_filing.latest(apartment_id, key)`, `stay_fee_filing.period_key(cadence, month)`. Prague date: `claim.prague_today()`.
- Scheduler: `App/app/scheduler.py`. Copy `_job_retention` (try / `_job_failed` / `_job_ok` / `_log_run`), add a key to `job_intervals()`, and an `add_job(..., "cron", hour=7, minute=0, id="stay_fee_mail", max_instances=1, coalesce=True)` in `start()`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/stay_fee_auto.py` | edit | `due_month`, `run` |
| `App/app/scheduler.py` | edit | the job |
| `App/tests/test_stay_fee_auto_job.py` | new | tests below |
| `App/tests/test_scheduler.py` | edit | only if it lists the job ids/intervals |

No other file may change.

## 4. Steps

1. `due_month(cadence, today) -> Optional[date]`: the first month of the period that ended most recently (monthly: `previous_month(today)`; quarterly: the first month of the previous calendar quarter). Return it only when `last + 2 days <= today <= last + 15 days` (`last` from `period_bounds`), else None. Why the window: the report goes out on the 2nd, blocked periods are retried until mid-month, and an old period is never sealed out of the blue (e.g. on the first deploy).
2. `run(today=None) -> dict` (counts `confirmed`, `reports`, `blocked`):
   - Hosts: `SELECT id FROM user_account WHERE role = 'host' AND deletion_due_at IS NULL AND COALESCE(stay_fee_emails_opt_out, 0) = 0`.
   - For each host's apartments (`owner_user_id = ?`, `archived_at IS NULL`, `stay_fee.is_active`; skip demo properties if `apartment` has a demo marker: grep `demo` in `db.py`/`demo.py`):
     a. `month = due_month(cadence_of(a), today)`; if set and no `latest(a.id, key)`: `filing_id = confirm(a, month, today)`; if `filing_id` → count `confirmed`; else `checked = check(a, month, today)`, and if `checked["issues"]` → `queue_stay_fee_blocked(a, checked["group"], checked["issues"])`, count `blocked` when it returned an id.
     b. Every live filing of this apartment (`superseded_at IS NULL`) with `created_at` in the last 3 days (`db.utcnow()` format; compare as ISO strings) → `queue_stay_fee_report(a, row)`, count `reports` when it returned an id. (The key includes the version, so a repeated run or a later day sends nothing twice, and a correction sends the new version.)
   - Wrap each apartment in `try/except Exception: log.exception(...)` so one broken property never stops the rest.
3. `scheduler.py`: `_job_stay_fee_mail()` calling `stay_fee_auto.run()`; `"stay_fee_mail": 24 * 60` in `job_intervals()`; cron at 07:00 (scheduler timezone is already Prague).
4. Tests `test_stay_fee_auto_job.py` (fixture from `tests/test_stay_fee_finalize.py`; console mail enabled as in 0206's tests). Pass `today` explicitly:
   - `due_month("monthly", date(2026,11,1))` is None; `date(2026,11,2)` → `date(2026,10,1)`; `date(2026,11,16)` → None. Quarterly `date(2026,10,2)` → `date(2026,7,1)`.
   - Clean period on the 2nd: one filing sealed, one `stay_fee_report` outbox row with the filing id; second `run` same day adds nothing.
   - Switch off (`stay_fee_auto.set_emails_enabled(uid, False, actor="t")`): nothing sealed, nothing queued.
   - Blocked (e.g. clear the property's VS): no filing, one `stay_fee_blocked` row; next day still one row; after fixing the VS, next run seals and queues the report.
   - Hand-saved filing created today → one report row.

## 5. Do not touch

`routes/`, templates, `mail.py`, `mail_notify.py`, i18n files. No git commit/stash/checkout/reset/clean.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_stay_fee_auto_job.py tests/test_stay_fee_auto.py tests/test_scheduler.py -q --tb=short -x 2>&1 | tail -30`
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`

## 7. Acceptance

- [ ] Tests pass; lint OK.

## 8. Stop and ask

As in [TEMPLATE](TEMPLATE.md) §8.

## 9. Report

Write `docs/tasks/0207-report.md` (600 tokens at most), set `Status: review`.

## Risk list (for the reviewer)

`stay_fee_auto.run` (window, opt-out filter, idempotency), scheduler `start()`.

## Owner steps

1. After deploy, check `/admin` Operations shows the job `stay_fee_mail` with a run time after 07:00 the next morning.
