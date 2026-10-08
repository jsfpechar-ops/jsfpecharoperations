# 0014: Door codes follow cancellations and date changes

Status: todo
Depends on: 0013 | Base commit: after 0013 merges | Branch: task/0014-door-code-cancel-and-move
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

When a stay with a door code is cancelled, UbyHost deletes the code through the gateway and tells the host. When its dates or the property's hours change, UbyHost moves the code (or makes a new one) and mails the guest the result. When a code cannot be created at all, the host gets a mail as well as the in-app alert. All of it runs in the background job; the calendar sync is not touched.

## 2. Context

- Plan: `docs/plans/ttlock-door-codes.md` §6 (rules for cancelled and moved stays). Facts: `docs/TTLOCK.md` "What the FAQ adds" (a never-used random code may not be removable) and "How the gateway fits" (gateway calls: worker only, one at a time, 35 s).
- `door_codes.py` (tasks 0012 and 0013): `reconcile()`, `issue()`, `view()`, `send_code_mail(door_code_id)` (idempotency key `door_code:<reservation_id>:<valid_from>`, skips when `notified_at` is set), `BACKOFF_MINUTES`.
- `ttlock.py`: `stay_window(...)`, `change_code_period(account_id, lock_id, code_id, start_ms, end_ms, priority)`, `create_period_code(...)`, `delete_code(account_id, lock_id, code_id, priority=CRITICAL)`, `TTLockError` (`.kind`: `offline`, `transient`, `network`, `rate`, `budget`, `permission`, `reauth`, `bug`, ...).
- Host mail: `mail_notify.submission_problem` (near line 820) is the model: a `try/except` wrapper around a builder; `to_email = _entity_contact_email(apartment["legal_entity_id"])`; returns `None` if empty; `mail.enqueue(kind=..., idempotency_key=..., to_email=..., subject=..., payload={"text", "html", "lang"}, ...)`; host language from `HOST_MAIL_LANGUAGE`. `mail.HOST_KINDS` must contain every host kind.
- Calendar effects (read-only facts, do not edit `icalsync.py`): a cancellation sets `reservation.status = 'cancelled'`; a date change updates `date_from` / `date_to`; a stay can come back with `status = 'active'`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/door_codes.py` | edit | Steps 1 to 4 |
| `App/app/mail.py` | edit | Step 5: kind `door_code_notice` in `KINDS` and `HOST_KINDS` |
| `App/app/mail_notify.py` | edit | Step 5: one builder and one sender |
| `App/app/host_i18n.py` | edit | Step 6 |
| `App/tests/test_door_code_lifecycle.py` | create | Step 7 |
| `App/tests/test_claim_mail.py` | edit | Add `"door_code_notice"` to the pinned kinds set only |
| `App/tests/test_guest_mail.py` | edit | Add `"door_code_notice"` to the local HOST tuple only |

No other file may change. `App/app/icalsync.py` and `App/app/reporting.py` must not change.

## 4. Steps

1. **New states.** Add `REVOKE_PENDING = "revoke_pending"`, `REVOKED = "revoked"`, `REVOKE_FAILED = "revoke_failed"`. Rows in these states are never issued or moved.
2. **Cancellations**, a new step at the start of `reconcile()`:
   - Rows whose reservation is not active (`status != 'active'` or `archived_at IS NOT NULL`):
     - state `pending` or `retrying`: set `revoked`, `claimed_at = NULL`. Nothing was on the lock, so no call.
     - state `issued` with `valid_to` in the future: set `revoke_pending`, `attempts = 0`, `next_attempt_at = now`.
   - Each due `revoke_pending` row (`next_attempt_at <= now`, at most `BATCH`): claim it with the same conditional-UPDATE pattern as `issue` (into `revoke_pending` with `claimed_at = now`, `attempts = attempts + 1`, count must be 1), then `ttlock.delete_code(account_id, row.lock_id, row.provider_code_id)`.
     - Success: `revoked`, `revoked_at = now`, `pin_enc = NULL`, audit `door_code_revoked`, then `mail_notify.door_code_notice(row_id, "cancelled_deleted")`.
     - `TTLockError` of kind `offline`, `transient`, `network` or `rate` and `attempts < 3`: back off 1, 15, 60 minutes.
     - Otherwise: `revoke_failed`, keep `pin_enc` (the retention step wipes it after `valid_to`), audit `door_code_revoke_failed`, then `mail_notify.door_code_notice(row_id, "cancelled_not_deleted")`.
   - A cancelled stay that comes back `active` while its row is `revoked`: delete the row's `door_code` record (`DELETE FROM door_code WHERE id = ?`), so step 1 of `reconcile` creates a fresh one. Audit `door_code_reset`.
3. **Date or hour changes**, a step after cancellations, for rows `issued` whose reservation is active and whose stay has not ended:
   - Expected window: `ttlock.stay_window(r.date_from, r.date_to, a.checkin_hour, a.checkout_hour, config.DOOR_CODE_BUFFER_HOURS)`. If it equals the stored `valid_from` / `valid_to` (compare in ms), skip. If its end is in the past, skip.
   - Skip while `next_attempt_at` is in the future (move backoff).
   - Try `ttlock.change_code_period(account_id, row.lock_id, row.provider_code_id, start_ms, end_ms, ttlock.NORMAL)`.
     - Success: update `valid_from`, `valid_to`, `notified_at = NULL`, `next_attempt_at = NULL`, audit `door_code_moved`, then `send_code_mail(row_id)` (the new `valid_from` makes a new idempotency key, so the guest gets one new mail).
     - Kind `offline`, `transient`, `network` or `rate`: `next_attempt_at = now + 15 min`, `last_error` = kind.
     - Any other kind: create a new code for the new window with `ttlock.create_period_code(account_id, row.lock_id, start_ms, end_ms, f"UH-{row_id}-m", ttlock.NORMAL)` (cloud only), store the new `pin_enc`, `provider_code_id`, window, `notified_at = NULL`, audit `door_code_replaced`, then `send_code_mail(row_id)`. The old code belongs to the same guest, so leaving it is safe. If this also fails, set `next_attempt_at = now + 60 min`.
4. **Failure mail.** Where `issue` moves a row to `failed` (task 0012), also call `mail_notify.door_code_notice(row_id, "failed")` after raising the alert.
5. **Host notice mail.**
   - `mail.py`: add `"door_code_notice"` to `KINDS` and `HOST_KINDS`.
   - `mail_notify.py`: `door_code_notice(door_code_id, variant)` modelled on `submission_problem` (try/except wrapper, logs and returns `None` on error). `variant` is one of `failed`, `cancelled_deleted`, `cancelled_not_deleted`. To the entity contact address of the apartment; subject and body from the host strings in step 6 with `%(property)s` and `%(date)s` (the stay's `date_from` as `%d.%m.%Y`); idempotency key `f"door_code_notice:{door_code_id}:{variant}"`. No PIN in the mail: for `cancelled_not_deleted` the body names the code by its last two digits only (`••••93`, from `db.decrypt_field(pin_enc)[-2:]`).
6. **Host strings** (EN, CS):

   | Key | EN | CS |
   |---|---|---|
   | `mail.door_code_notice.failed.subject` | %(property)s: door code not created | %(property)s: kód ke dveřím nebyl vytvořen |
   | `mail.door_code_notice.failed.body` | UbyHost could not create the door code for the stay from %(date)s. Create a code in the TTLock app and send it to the guest. | UbyHost nemohl vytvořit kód ke dveřím pro pobyt od %(date)s. Vytvořte kód v aplikaci TTLock a pošlete ho hostovi. |
   | `mail.door_code_notice.cancelled_deleted.subject` | %(property)s: door code deleted after a cancellation | %(property)s: kód ke dveřím smazán po zrušení |
   | `mail.door_code_notice.cancelled_deleted.body` | The stay from %(date)s was cancelled after its door code was sent. UbyHost deleted the code from the lock. A code that was never typed may still open the door until its end date, so check the lock in the TTLock app. | Pobyt od %(date)s byl zrušen po odeslání kódu ke dveřím. UbyHost kód ze zámku smazal. Kód, který ještě nikdo nezadal, může dveře otevírat až do konce platnosti, proto zámek zkontrolujte v aplikaci TTLock. |
   | `mail.door_code_notice.cancelled_not_deleted.subject` | %(property)s: delete a door code in the TTLock app | %(property)s: smažte kód ke dveřím v aplikaci TTLock |
   | `mail.door_code_notice.cancelled_not_deleted.body` | The stay from %(date)s was cancelled after its door code (%(code)s) was sent, and UbyHost could not reach the lock to delete it. Delete it in the TTLock app. | Pobyt od %(date)s byl zrušen po odeslání kódu ke dveřím (%(code)s) a UbyHost se nepodařilo zámek kontaktovat, aby ho smazal. Smažte ho v aplikaci TTLock. |

   If host mails build their HTML with shared helpers (see `submission_problem`), use them; no new template system.
7. **Tests** (`App/tests/test_door_code_lifecycle.py`), seeded like `tests/test_door_codes_issue.py`, with `ttlock.delete_code`, `change_code_period` and `create_period_code` faked by recorders:
   - `test_cancelled_pending_row_is_revoked_without_a_call`.
   - `test_cancelled_issued_code_is_deleted_and_the_host_told` (one delete call with the stored code id; state `revoked`; `pin_enc` NULL; one `door_code_notice` outbox row, variant `cancelled_deleted`).
   - `test_unreachable_lock_retries_then_tells_the_host_to_delete` (three `offline` failures; then `revoke_failed`; notice `cancelled_not_deleted`; its text has `••••93` and not the full PIN).
   - `test_a_reactivated_stay_gets_a_fresh_code`.
   - `test_moved_dates_move_the_code_and_mail_the_guest_once` (one change call with the new window; a second `door_code` outbox row with a new key; running `reconcile()` again makes no call).
   - `test_changed_property_hours_move_the_code`.
   - `test_refused_change_creates_a_new_code` (fake raises `TTLockError(kind="bug")`; one `create_period_code` call; new PIN stored; one new guest mail).
   - `test_unreachable_change_waits_15_minutes`.
   - `test_failed_issue_mails_the_host` (variant `failed`).
   - `test_unchanged_stays_make_no_calls` (a run over 3 issued, unchanged stays calls nothing).
   - `test_lifecycle_never_touches_filing` (same snapshot check as task 0012).

## 5. Do not touch

Everything outside §3. `App/app/icalsync.py`, `App/app/reporting.py`, every UbyPort module, the guest templates.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests -q` (all pass) and `.venv/bin/python -m pytest tests/test_door_code_lifecycle.py tests/test_door_codes_issue.py tests/test_door_code_delivery.py -q`. From the repo root: `python3 scripts/context_lint.py` (last line `context lint: OK`).

## 7. Acceptance

- [ ] The 11 tests in step 7 pass, earlier door-code tests still pass, the full suite passes.
- [ ] `git diff App/app/icalsync.py App/app/reporting.py` is empty.
- [ ] No host notice contains a full PIN (test `test_unreachable_lock_retries_then_tells_the_host_to_delete`).
- [ ] `git diff --stat` shows only the files in §3.

## 8. Stop and ask

Stop, and write the report, if:

- a name or excerpt in §2 is not found;
- detecting a cancellation or a date change seems to need a change in `icalsync.py`;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0014-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/door_codes.py` (the cancel and move steps in `reconcile`)
- `App/app/mail_notify.py` (`door_code_notice`)

## Owner steps

None. Test mode stays on.
