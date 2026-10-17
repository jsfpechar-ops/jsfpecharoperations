# 0012: Issuing door codes

Status: done
Depends on: 0011 | Base commit: after 0011 merges | Branch: task/0012-door-codes-issuing
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

When every guest of a stay is registered, UbyHost creates one TTLock timed code for that stay and stores it encrypted. It tries right after the guest's last save and keeps trying from a background job. Until the owner switches door codes to live, only stays added by hand get a code, so the whole workflow can be tested in production first. No guest page or mail shows the code yet (task 0013).

## 2. Context

- Plan: `docs/plans/ttlock-door-codes.md` §6 (states and rules) and §9 (flow). Rule 1: UbyPort filing correctness beats every feature, so nothing here may change or delay filing, and nothing here may raise into a caller.
- Client (`App/app/ttlock.py`, tasks 0009 and 0010): `allowed_for`, `account_for`, `stay_window(date_from, date_to, checkin_hour, checkout_hour, buffer_hours)`, `create_period_code(account_id, lock_id, start_ms, end_ms, name, priority) -> (pin, code_id)`, `find_code_by_name(account_id, lock_id, name) -> (pin, code_id) | None`, `TTLockError` (`.kind`), priorities `NORMAL` and `CRITICAL`.
- Tables (task 0008): `door_code` (UNIQUE `reservation_id`; `state`, `pin_enc`, `provider_code_id`, `valid_from`, `valid_to`, `attempts`, `next_attempt_at`, `claimed_at`, `last_error`, `issued_at`, `code_kind`), `apartment.lock_provider/lock_id/checkin_hour/checkout_hour`. Reservation columns: `status` (`active`, `cancelled`, `ignored`), `archived_at`, `registration_completed_at`, `source` (`ical` or `manual`), `date_from`, `date_to`.
- DB helpers (`App/app/db.py`): `query`, `query_one`, `execute` (returns the row count), `utcnow()` (`2026-10-08T12:00:00+00:00`), `encrypt_field`, `audit(action, detail, actor=..., owner_user_id=...)`, and `with db.cursor() as cur:` for a transaction (commits on exit).
- Prague time: `deadlines.local_now()`.
- Alerts (`App/app/alerts.py`): `raise_alert(level, kind, message, detail="", dedupe_key=None, apartment_id=None, reservation_id=None, owner_user_id=None, params=None)`, `resolve(dedupe_key)`. A kind's card text comes from host strings `notification.<kind>.title` and `notification.reason.<kind>` (see `notification.feed_incomplete.*` in `App/app/host_i18n.py`).
- Scheduler (`App/app/scheduler.py`): jobs follow `_job_retention` (`started = time.perf_counter()`, `try/except`, `_job_ok`, `_job_failed`, `_log_run`). `_JOB_LEVELS` must list every job id. `job_intervals()` returns minutes per job. `start()` registers with `_scheduler.add_job(fn, "interval", minutes=..., id=..., max_instances=1, coalesce=True)`. A failing job needs host string `notification.job_name.<id>`. `tests/test_scheduler.py` has a `_JOBS` list used by `test_a_failing_job_alerts_the_host_and_the_next_success_resolves_it`.
- Guest save (`App/app/routes/guest.py`, `guest_form_save`, near line 1851): `await run_in_threadpool(reporting.submit_stay_if_complete, apartment["id"], reservation_id)`, then the 303 redirect to the stay page.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/config.py` | edit | Step 1 |
| `App/app/door_codes.py` | create | Steps 2 to 5 |
| `App/app/routes/guest.py` | edit | Step 6, two lines |
| `App/app/scheduler.py` | edit | Step 7 |
| `App/app/host_i18n.py` | edit | Step 8 |
| `App/tests/test_door_codes_issue.py` | create | Step 9 |
| `App/tests/test_scheduler.py` | edit | Add one `_JOBS` entry |
| `docs/ENVIRONMENT.md` | edit | One row: `UBYHOST_DOOR_CODES_LIVE` |

No other file may change. `App/app/reporting.py` must not change.

## 4. Steps

1. **Live switch.** In `config.py`, next to the other door-code settings:
   ```python
   # Until this is on, only stays added by hand (reservation.source = 'manual') get a door code.
   DOOR_CODES_LIVE = os.environ.get("UBYHOST_DOOR_CODES_LIVE", "0") in ("1", "true", "yes")
   ```
2. **Module skeleton** `App/app/door_codes.py`:
   ```python
   PENDING, ISSUING, RETRYING, ISSUED, FAILED, EXPIRED = "pending", "issuing", "retrying", "issued", "failed", "expired"
   BACKOFF_MINUTES = (1, 5, 15, 60, 240)   # after attempt 1..5; attempt 6 does not happen
   LEASE_MINUTES = 2                        # longer than any single TTLock call
   BATCH = 20
   ```
   Helpers: `_now()` (aware UTC `datetime`), `_iso(dt)` (same format as `db.utcnow()`), `_ms_to_iso(ms)`.
3. **Eligibility and the row.**
   - `_eligible_sql()` returns the WHERE clause shared by steps 3 and 5, over `reservation r JOIN apartment a ON a.id = r.apartment_id`:
     `r.status = 'active' AND r.archived_at IS NULL AND r.registration_completed_at IS NOT NULL AND r.date_to >= ? AND a.lock_provider = 'ttlock' AND a.lock_id IS NOT NULL AND a.checkin_hour IS NOT NULL AND a.checkout_hour IS NOT NULL`, plus `AND r.source = 'manual'` when `not config.DOOR_CODES_LIVE`. The parameter is today's Prague date as `YYYY-MM-DD`.
   - `ensure_row(reservation_id) -> Optional[int]`: if the reservation matches `_eligible_sql()`, `ttlock.allowed_for(a.owner_user_id)` is true, and the owner's `lock_account` has `status = 'ok'`, run
     `INSERT INTO door_code (reservation_id, apartment_id, lock_id, code_kind, state, attempts, next_attempt_at, created_at, updated_at) VALUES (?, ?, ?, 'random', 'pending', 0, ?, ?, ?) ON CONFLICT (reservation_id) DO NOTHING`
     and return the row id (select it back). Otherwise return `None`.
4. **`issue(door_code_id) -> bool`**, the only place that creates a code:
   - Claim: `UPDATE door_code SET state = 'issuing', claimed_at = ?, attempts = attempts + 1, updated_at = ? WHERE id = ? AND state IN ('pending', 'retrying') AND (next_attempt_at IS NULL OR next_attempt_at <= ?) AND (claimed_at IS NULL OR claimed_at < ?)` with the lease cutoff `now - LEASE_MINUTES`. Continue only if the row count is 1; else return `False`.
   - Re-read the row, its reservation, apartment and account. If the stay is no longer eligible (cancelled, archived, moved past, door codes off, feature off), set the row back to `pending` with `claimed_at = NULL` and return `False`.
   - Window: `start_ms, end_ms = ttlock.stay_window(r.date_from, r.date_to, a.checkin_hour, a.checkout_hour, config.DOOR_CODE_BUFFER_HOURS)`. If `end_ms` is in the past, set `expired` and return `False`.
   - Name `f"UH-{door_code_id}"`. Priority `ttlock.CRITICAL` if `start_ms` is less than 24 h away, else `ttlock.NORMAL`.
   - If `attempts > 1` (a retry), first call `ttlock.find_code_by_name(account_id, lock_id, name)` and adopt its result if it is not `None`; else call `ttlock.create_period_code(...)`.
   - Success, in one `with db.cursor() as cur:` block: `state = 'issued'`, `pin_enc = db.encrypt_field(pin)`, `provider_code_id = code_id`, `valid_from = _ms_to_iso(start_ms)`, `valid_to = _ms_to_iso(end_ms)`, `issued_at = now`, `claimed_at = NULL`, `last_error = NULL`. After the block: `alerts.resolve(f"door_code_failed:{reservation_id}")` and `db.audit("door_code_issued", f"door_code={door_code_id} reservation={reservation_id}", actor="system", owner_user_id=a.owner_user_id)`. Return `True`. The PIN never appears in a log line or in `detail`.
   - `TTLockError` with kind `reauth`, `permission`, `config` or `disabled`: `state = 'failed'` at once. Kind `budget`: `state = 'retrying'`, `next_attempt_at = now + 60 min`, and the attempt does not count (subtract the 1 again). Any other kind, or any other exception (log it with `log.exception`, no request data): if `attempts >= len(BACKOFF_MINUTES)` then `failed`, else `retrying` with `next_attempt_at = now + BACKOFF_MINUTES[attempts - 1]`. Always set `claimed_at = NULL` and `last_error` to the kind (at most 40 characters).
   - On `failed`: `alerts.raise_alert("warning", "door_code_failed", "Door code could not be created", dedupe_key=f"door_code_failed:{reservation_id}", apartment_id=a.id, reservation_id=reservation_id, params={"property": a.internal_name, "date": r.date_from})`.
5. **Entry points.**
   - `on_registration_complete(reservation_id) -> None`: if `config.DOOR_CODES_ENABLED`, call `ensure_row`, then `issue` on the returned id. Wrap the whole body in `try/except Exception: log.exception("door code hook failed reservation=%s", reservation_id)`. It never raises.
   - `reconcile() -> dict` (run by the job): return `{}` if `not config.DOOR_CODES_ENABLED`. Then:
     1. Every reservation matching `_eligible_sql()` that has no `door_code` row: `ensure_row`. This catches stays completed by the submit sweep or by the host.
     2. `SELECT id FROM door_code WHERE state IN ('pending', 'retrying') AND (next_attempt_at IS NULL OR next_attempt_at <= ?) ORDER BY next_attempt_at LIMIT ?` with `BATCH`: `issue` each.
     3. Rows `issuing` whose `claimed_at` is older than the lease (a crashed run): set `retrying`, `claimed_at = NULL`, `next_attempt_at = now`.
     4. Rows `issued` whose `valid_to` has passed: set `expired`.
     Return counts: `{"created", "issued", "failed", "expired"}`. Cancellations and date moves are task 0014.
6. **Guest save hook.** In `guest_form_save`, right after the `submit_stay_if_complete` line, add `await run_in_threadpool(door_codes.on_registration_complete, reservation_id)` and the `door_codes` import. Leave everything else as it is.
7. **Job.** In `scheduler.py`: import `door_codes`; add `"door_codes": "warning"` to `_JOB_LEVELS`; add `"door_codes": 1` to `job_intervals()`; add `_job_door_codes()` built like `_job_retention` around `door_codes.reconcile()`; register it in `start()` with `id="door_codes"`, `max_instances=1, coalesce=True`. In `tests/test_scheduler.py` add `{"id": "door_codes", "run": scheduler._job_door_codes, "target": (door_codes, "reconcile"), "level": "warning"}` to `_JOBS` (match the existing entries' exact shape).
8. **Strings** (EN and CS):

   | Key | EN | CS |
   |---|---|---|
   | `notification.job_name.door_codes` | door codes | kódy ke dveřím |
   | `notification.door_code_failed.title` | %(property)s: the door code for the stay from %(date)s could not be created. | %(property)s: kód ke dveřím pro pobyt od %(date)s se nepodařilo vytvořit. |
   | `notification.reason.door_code_failed` | Create a code in the TTLock app and send it to the guest. | Vytvořte kód v aplikaci TTLock a pošlete ho hostovi. |
9. **Tests** (`App/tests/test_door_codes_issue.py`). Seed like `tests/test_stale_submission.py` (`db.insert` of `apartment` and `reservation` with `source='manual'` unless a test says otherwise), plus a `lock_account` with `status='ok'`. Turn the feature on with `monkeypatch` (`DOOR_CODES_ENABLED`, client id and secret). Fake `ttlock.create_period_code` and `ttlock.find_code_by_name` with recorders. Freeze time where a test needs it. Tests, each asserting literal values:
   - `test_completed_stay_gets_one_code`: after `reconcile()`, one row `issued`, `db.decrypt_field(pin_enc) == "0563456"`, `provider_code_id == "10236"`, `valid_from`/`valid_to` equal the buffered window, the fake was called once with name `UH-<id>`.
   - `test_a_second_run_makes_no_second_call`.
   - `test_a_claimed_row_is_not_issued_twice` (set `claimed_at` to now on a `pending` row; `issue` returns `False`, no call).
   - `test_ineligible_stays_get_nothing`: parametrize over not completed, cancelled, archived, `date_to` yesterday, `lock_provider` NULL, hours NULL. No row, no call.
   - `test_live_off_skips_calendar_stays` (`source='ical'` gets nothing) and `test_live_on_includes_calendar_stays`.
   - `test_host_without_a_connected_account_gets_nothing`.
   - `test_transient_error_backs_off_1_then_5_minutes`.
   - `test_fifth_failure_marks_failed_and_raises_one_alert` (dedupe key `door_code_failed:<reservation_id>`; a later success resolves it).
   - `test_reauth_fails_at_once`.
   - `test_budget_refusal_waits_an_hour_and_does_not_count`.
   - `test_retry_adopts_a_code_created_before_a_timeout` (row with `attempts = 1`, `state = 'retrying'`: `find_code_by_name` returns a code, `create_period_code` is not called).
   - `test_a_crashed_claim_is_released`.
   - `test_issued_codes_expire_after_their_window`.
   - `test_hook_never_raises` (`ensure_row` monkeypatched to raise; `on_registration_complete` returns `None`).
   - `test_guest_save_calls_the_hook`: perform a guest save the way one of `tests/test_guest_*.py` already posts to `/l/{token}/{reservation_id}/save` (pick the simplest, say which in the report), with `door_codes.on_registration_complete` replaced by a recorder; it was called with the reservation id.
   - `test_door_codes_never_touch_filing`: snapshot `SELECT * FROM submission` and `SELECT id, submit_state FROM guest` before and after `reconcile()` plus `on_registration_complete()`; they are equal.
   - `test_no_pin_in_logs` (`caplog.text` does not contain the PIN).

## 5. Do not touch

Everything outside §3. `App/app/reporting.py`, `App/app/icalsync.py`, every UbyPort module. No guest template, no mail (task 0013). No cancellation or date-move handling (task 0014).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (all pass) and `.venv/bin/python -m pytest tests/test_door_codes_issue.py tests/test_scheduler.py -q`. From the repo root: `python3 scripts/context_lint.py` (last line `context lint: OK`).

## 7. Acceptance

- [ ] All tests in step 9 pass; the scheduler test passes with the new `_JOBS` entry; the full suite passes.
- [ ] `git diff App/app/reporting.py` is empty.
- [ ] `grep -n "log\." App/app/door_codes.py` shows no line that logs a PIN, token or request body.
- [ ] The PR description lists the outbound TTLock requests this task adds and why (rule 2).
- [ ] `git diff --stat` shows only the files in §3.

## 8. Stop and ask

Stop, and write the report, if:

- a name or excerpt in §2 is not found;
- `ON CONFLICT (reservation_id) DO NOTHING` does not work with the SQLite version in use;
- a guest save test cannot be written without changing a shared fixture;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0012-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/door_codes.py`, all of it (`issue`, `_eligible_sql`, `reconcile`)
- `App/app/routes/guest.py` (the two added lines)
- `App/app/scheduler.py` (the job)

## Owner steps

None. `UBYHOST_DOOR_CODES_LIVE` stays unset (test mode) until the acceptance test in the plan §12 passes.
