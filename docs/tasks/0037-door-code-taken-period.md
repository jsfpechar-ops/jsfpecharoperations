# 0037: A taken door-code period gets a custom code, and the host is warned

Status: todo
Depends on: none (runs before 0038) | Base commit: main | Branch: task/0037-door-code-taken-period
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

When TTLock already holds a type-3 code for a stay's hours (`-1026`), the worker creates a custom code for that stay at once, and mails the host (support in copy) that an older code for the same hours may still open the door. `get` is never retried for that window. If the custom code cannot be made within a few minutes, the host is told to create one in the TTLock app. A change of dates or hours creates a new code and never calls `keyboardPwd/change`. When the old code of a moved stay cannot be deleted, the host is told.

## 2. Context

Rules that apply: AGENTS.md rule 2 (one new outbound call, `POST /v3/keyboardPwd/add`, only after `-1026`; it sends lock id, window, code name `UH-<id>` and the new digits; no guest name or e-mail; say that in the PR), rule 4 (no new dependency), rule 5 (no schema change; `door_code.code_kind` exists), rule 9.

Behaviour is decided in [plan §6](../plans/ttlock-door-codes.md#6-states) and [TTLOCK](../TTLOCK.md) (rows `-1026`, `-3008`). Do not re-open it. Treat only `-1026` as "period taken".

Why the host mail: `-1026` means another type-3 code covers exactly these hours, usually a cancelled or moved stay's. A deleted code no longer opens (owner test 2026-10-10), but a delete can fail, so the host checks.

Why the retry limit changes: `ISSUE_MAX_ATTEMPTS` is 2 (`door_codes.py` line 27). The guest save uses attempt 1 and the first worker `add` is attempt 2, so with today's code one busy-gateway answer on `add` would mark the code failed. Period-taken rows get their own short limit. Retrying only helps when the gateway is busy (`-3037`) or the network dropped; `-2012` (no gateway connected) will not fix itself, so it hands over at once. Retrying `get` never helps: it returns `-1026` again (Render staging retried it and never got a code).

Anchor A, `App/app/ttlock.py`. Found verbatim once:

```python
    -3008: "unused_code",
}
```

Anchor B, `App/app/ttlock.py`, `ALLOWED_PATHS`. Found verbatim once:

```python
        "/v3/keyboardPwd/get",
        "/v3/keyboardPwd/change",
        "/v3/keyboardPwd/delete",
```

Anchor B2, `App/app/ttlock.py`, `GATEWAY_PATHS`. Found verbatim once:

```python
        "/v3/keyboardPwd/delete",
        "/v3/lock/queryDate",
        "/v3/lock/updateDate",
    }
)
```

Anchor C, `App/app/door_codes.py`. Found verbatim once:

```python
            ttlock.change_code_period(
```

Anchor D, `App/app/door_codes.py`. Found verbatim once:

```python
        "first_use_by": _fmt_local(_ms_to_iso(_iso_to_ms(valid_from) + 24 * 3_600_000)) if valid_from else "",
```

Anchor E, `App/app/templates/guest/stay.html`. Found verbatim once:

```html
        <p class="g-intro">{{ t('door_code_first_use', deadline=door_code.first_use_by) }}</p>
```

Anchor F, `App/app/host_i18n.py`, once in `en` and once in `cs`: the key `"mail.door_code_notice.cancelled_not_deleted.body"`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/ttlock.py` | edit | Steps 1, 2, 3 |
| `App/app/door_codes.py` | edit | Steps 4 to 8 |
| `App/app/mail_notify.py` | edit | Step 9 |
| `App/app/host_i18n.py` | edit | Step 10 (four new strings, one changed body in `en` and `cs`) |
| `App/app/templates/guest/stay.html` | edit | Step 8 |
| `App/tests/test_ttlock.py` | edit | Step 11 |
| `App/tests/test_door_codes_safeguards.py` | edit | Step 11 |
| `docs/context/known-issues.md` | edit | Delete the `K-D01` row |

No other file may change.

## 4. Steps

1. In `ERROR_KINDS`, next to `-3008`, add `-1026: "period_taken",` and `-3007: "duplicate",`. `-2018` stays `permission`.

2. Add `"/v3/keyboardPwd/add"` to `ALLOWED_PATHS` and to `GATEWAY_PATHS` (35 s). Add `add_custom_code(account_id, lock_id, start_ms, end_ms, name, priority) -> Tuple[str, str]` (priority has no default). It calls `_whole_hour` on both ends like `create_period_code`. It posts `lockId`, `keyboardPwd` (7 digits, first digit 1 to 9, from `secrets`), `keyboardPwdName=name`, `keyboardPwdType=3`, `startDate`, `endDate`, `addType=2`. On `TTLockError` with `code == -3007`, draw one new PIN and post once more; a second `-3007` raises. Return `(pin, str(keyboardPwdId))`. Never log the PIN.

3. `find_code_by_name` gains `start_ms: int, end_ms: int` and returns a match only when `keyboardPwdName == name` and `int(startDate) == start_ms` and `int(endDate) == end_ms`. Update its one caller in `issue`. A code with the right name and the wrong window is never adopted.

4. Constants in `door_codes.py`: `PERIOD_TAKEN = "period_taken"`, `PERIOD_TAKEN_RETRY_MINUTES = (1, 5)`, `PERIOD_TAKEN_MAX_ATTEMPTS = 4` (the guest save, then at most three `add` tries, about 6 minutes). `GATEWAY_RETRY_KINDS = ("offline", "transient", "network", "rate", "budget")`.

5. `issue(door_code_id, *, allow_gateway=False)`. `on_registration_complete` keeps `issue(row_id)`. `_issue_due` calls `issue(int(row["id"]), allow_gateway=True)`. Let `taken = (row["last_error"] or "").startswith(PERIOD_TAKEN)`. Set a local `via_add = False`, and set it to True right before every `add_custom_code` call. Do not call `add` from inside an `except` clause. Replace the body of the `try` so it runs at most two steps, all inside the existing outer `try` and its existing `except` clauses:
   - First, if `attempts > 1`: `find_code_by_name(..., name, start_ms, end_ms)`. On a hit, use it with `kind = "custom" if taken else "random"` and skip the cases below. On a miss, go on with the first case below that matches.
   - If `taken` and `allow_gateway`: `add_custom_code(..., priority)`, `kind = "custom"`.
   - Else if `taken` (a guest save on a taken row): release the claim with `_release_issue_claim(door_code_id, decrement_attempt=True)` and return False. No TTLock call.
   - Else: `create_period_code(..., priority)`, `kind = "random"`. If that raises `TTLockError` with `kind == "period_taken"`, catch it right there (a small inner `try` around this one call). Mail the host once with `mail_notify.door_code_notice(door_code_id, "period_taken")`. Then, if `allow_gateway`, call `add_custom_code(..., priority)` and set `kind = "custom"`. If not, set the row to `RETRYING`, `last_error = "period_taken:-1026"`, `next_attempt_at` = now, `claimed_at` NULL, and return False without the failure mail.
   - The issued `UPDATE` writes `code_kind = kind`. Before `send_code_mail`, re-read `reservation.status` and `archived_at`. If the stay is no longer active, keep the stored code and skip the mail. The next reconcile revokes it.

   In the existing `except ttlock.TTLockError` handler, when `taken` or `via_add` is true: write `last_error` as `"period_taken:" + reason` (cut to 40 characters). `exc.code == -2012` goes to `FAILED` at once with the existing alert and host mail. For another kind in `GATEWAY_RETRY_KINDS` or any kind not listed below, set `RETRYING` with `next_attempt_at` = now + `PERIOD_TAKEN_RETRY_MINUTES[min(max(attempts - 2, 0), 1)]` (1, then 5 minutes; a stay first seen by the worker starts at `attempts` 1) until `attempts >= PERIOD_TAKEN_MAX_ATTEMPTS`, then `FAILED` with the existing alert and host mail. Budget keeps its 60 minutes and does not count an attempt. Kinds `permission`, `reauth`, `config`, `disabled`, `storage` and `duplicate` go to `FAILED` at once with the existing alert and mail. Rows that are not period-taken keep today's handling exactly.

6. `issue` passes its local `priority` (CRITICAL when the stay starts within 24 h) to `create_period_code` and `add_custom_code`. `_handle_moves` uses the same rule for the new window.

7. `_handle_moves`. Delete the `change_code_period` call and its `except` branch. Skip a row whose `last_error` starts with `permission`, `reauth`, `config` or `disabled`. Otherwise call `create_period_code` for the new window. On `period_taken`, mail `door_code_notice(row["id"], "period_taken")` once and call `add_custom_code` in the same run. On success: store the new pin, id, window and `code_kind`, clear `notified_at`, `next_attempt_at` and `last_error`, audit `door_code_replaced`, `send_code_mail`. Then delete the previous code id when it differs. If that delete raises `TTLockError`, audit `door_code_move_old_not_deleted` and call `door_code_notice(row["id"], "moved_not_deleted")`. On a create or add failure: a kind in `GATEWAY_RETRY_KINDS` sets `next_attempt_at` 15 minutes ahead (60 for budget) and `last_error` to the kind (prefixed `period_taken:` when it came from `add`); `permission`, `reauth`, `config` or `disabled` sets `last_error` to `kind:code`, calls `door_code_notice(row["id"], "failed")` once, and does not call `add`; any other kind is treated like the gateway group. The old code stays untouched until a new one exists.

8. In `view`, when `row["code_kind"] == "custom"`, set `first_use_by` to `""`. In `guest/stay.html`, wrap the anchor E paragraph in `{% if door_code.first_use_by %}`.

9. `mail_notify.py`. In `build_door_code` and in the `build_completion` block that uses `door_code["first_use_by"]`, omit the first-use paragraph and text line when `first_use_by` is empty. In `_door_code_notice`, pass `cc_email=config.SUPPORT_EMAIL` to `mail.enqueue` for the variants `period_taken`, `moved_not_deleted` and `failed` (the same CC `door_code_delayed_notice` uses), so the owner sees each one. The two new variants use only `property` and `date`. Where `issue` sends the `period_taken` notice, also `log.error("DOOR_CODE_PROBLEM stage=period_taken reservation=%s door_code=%s", ...)`.

10. `host_i18n.py`, after anchor F in `en`:
   - `"mail.door_code_notice.period_taken.subject": "%(property)s: an older door code covers the stay from %(date)s"`
   - `"mail.door_code_notice.period_taken.body": "TTLock reported that another code already covers exactly the hours of the stay from %(date)s, for example the code of a cancelled or moved stay. UbyHost is giving this guest a new code of their own. If the older code was not deleted, it still opens the door during this stay. Check this lock's passcodes in the TTLock app."`
   - `"mail.door_code_notice.moved_not_deleted.subject": "%(property)s: delete an old door code in the TTLock app"`
   - Replace the value of `"mail.door_code_notice.cancelled_deleted.body"` with `"The stay from %(date)s was cancelled after its door code was sent. UbyHost deleted the code from the lock, so it no longer opens the door."` (the old last sentence is disproved by the owner's lock test).
   - `"mail.door_code_notice.moved_not_deleted.body": "The stay from %(date)s changed its dates or hours and got a new door code. UbyHost could not delete the old code from the lock. Its old dates may be booked by someone else, so delete it in the TTLock app."`

   After anchor F in `cs`:
   - `"mail.door_code_notice.period_taken.subject": "%(property)s: pobyt od %(date)s pokrývá i starší kód ke dveřím"`
   - `"mail.door_code_notice.period_taken.body": "TTLock hlásí, že přesně hodiny pobytu od %(date)s už pokrývá jiný kód, například kód zrušeného nebo přesunutého pobytu. UbyHost dává tomuto hostovi jeho vlastní nový kód. Pokud starší kód nebyl smazán, otevírá dveře i během tohoto pobytu. Zkontrolujte kódy tohoto zámku v aplikaci TTLock."`
   - `"mail.door_code_notice.moved_not_deleted.subject": "%(property)s: smažte starý kód ke dveřím v aplikaci TTLock"`
   - Replace the value of `"mail.door_code_notice.cancelled_deleted.body"` with `"Pobyt od %(date)s byl zrušen po odeslání kódu ke dveřím. UbyHost kód ze zámku smazal, takže už dveře neotevře."`
   - `"mail.door_code_notice.moved_not_deleted.body": "Pobyt od %(date)s změnil termín nebo hodiny a dostal nový kód ke dveřím. UbyHost se nepodařilo starý kód ze zámku smazat. Jeho původní termín může mít rezervovaný někdo jiný, proto ho smažte v aplikaci TTLock."`

11. Tests. Monkeypatch every TTLock function a test reaches; no test may make a real `_call`.
   - `test_ttlock.py`: `add` is allowed and in `GATEWAY_PATHS` (timeout 35); it sends `addType=2` and `keyboardPwdType=3`; the passcode is 7 digits and does not start with 0; `-3007` then success posts two different passcodes; two `-3007` raise. `find_code_by_name` ignores a same-name code whose `startDate` differs. The allowlist source scan still passes.
   - `test_door_codes_safeguards.py`: replace `test_a_never_used_code_is_replaced_not_retried_forever` with a test that a date change calls `create_period_code` and never `change_code_period`. Add:
     - `test_a_taken_period_is_not_retried_from_the_guest_save`: `create_period_code` raises `TTLockError("taken", code=-1026, kind="period_taken")` in `on_registration_complete`; `add_custom_code` is not called; the row is `retrying` with `last_error` `period_taken:-1026`; one `period_taken` host notice is queued.
     - `test_the_worker_adds_a_custom_code_when_the_period_is_taken`: `find_code_by_name` returns None and is called before `add_custom_code`; the row ends `issued`, `code_kind` `custom`; `view` has `first_use_by == ""`.
     - `test_a_busy_gateway_on_add_is_retried_twice`: `add_custom_code` raises `code=-3037, kind="transient"` on two worker runs (advance `next_attempt_at`); the row stays `retrying`, `last_error` starts with `period_taken`, no failure mail; the third run succeeds and the row is `issued` `custom`.
     - `test_add_gives_up_after_the_limit`: `add_custom_code` always raises `-3037`; after the third `add` the row is `failed` and one `failed` host notice is queued, with support in CC.
     - `test_no_gateway_hands_over_at_once`: `add_custom_code` raises `code=-2012, kind="offline"`; after that one call the row is `failed` and one `failed` notice is queued.
     - `test_an_adopted_custom_code_stays_custom`: a period-taken row whose `find_code_by_name` hits ends `code_kind` `custom`.
     - `test_permission_on_a_move_does_not_add`: `create_period_code` raises `-2018`/`permission` in `_handle_moves`; `add_custom_code` is not called; one `failed` notice; a second `reconcile` makes no TTLock call for that stay.
     - `test_an_undeleted_old_code_after_a_move_tells_the_host`: the move issues a new code, `delete_code` raises `offline`; one `moved_not_deleted` notice is queued and the new code is stored.
     - `test_a_cancelled_stay_does_not_get_the_mail`: the reservation is cancelled while `add_custom_code` runs (set the status inside the fake); the code is stored and no `door_code` guest mail is queued.

## 5. Do not touch

`App/app/migrations/`, filing, UbyPort, `change_code_period` (leave the function; nothing in `door_codes.py` calls it), the existing guest copy keys, `_revoke_one`, `_handle_cancellations`, the host property page's 24-hour hint. No new dependency. No call to `keyboardPwd/change`. No shifting of `startDate` or `endDate`. No reading of another stay's PIN.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_ttlock.py tests/test_door_codes_safeguards.py tests/test_door_codes_view.py tests/test_door_code_handover.py tests/test_confirmation_with_door_code.py tests/test_guest_mail.py -q`

Then `.venv/bin/python -m pytest tests -q`

From the repo root: `python3 scripts/context_lint.py`

Expected: all pass, last lint line `context lint: OK`.

## 7. Acceptance

- [ ] A guest save whose `get` returns `-1026` makes no `add` call, leaves `last_error` `period_taken:-1026`, and queues one `period_taken` host notice.
- [ ] The next `reconcile` calls `add` once, stores `code_kind` `custom`, and the guest view and mail have no first-use sentence.
- [ ] `-2012` on `add` fails at once; a busy gateway gets two more `add` tries (1 and 5 minutes), then `failed`. Each failure is one host mail with support in CC.
- [ ] `find_code_by_name` never adopts a code whose window differs.
- [ ] A date change never calls `change_code_period`. `-2018` on it does not call `add`, and the next reconcile makes no TTLock call for that stay.
- [ ] A failed delete of a moved stay's old code queues one `moved_not_deleted` notice.
- [ ] `grep -n "keyboardPwd/change" App/app/door_codes.py` prints nothing.
- [ ] `grep -n "log\." App/app/ttlock.py` shows no PIN, token or response body.
- [ ] `K-D01` is gone from `docs/context/known-issues.md`.
- [ ] Full pytest and context lint pass.

## 8. Stop and ask

Stop and write the report if an anchor is missing, a test fails twice, a file outside §3 needs a change, or a step is unclear. Do not push, merge, deploy, or add a dependency.

## 9. Report

Write `docs/tasks/0037-report.md` (1,500 tokens at most) and set `Status: review`. The report has the files changed, each command with its last 5 lines, §7 ticked, deviations, questions, and owner steps.

## Risk list (for the reviewer)

`App/app/ttlock.py` (`add_custom_code`, `find_code_by_name`, allowlist), `App/app/door_codes.py` (`issue`, `_handle_moves`), `App/app/host_i18n.py` (four new strings), `App/app/templates/guest/stay.html`.

## Owner steps

These need a lock **with a gateway**. `add` and `delete` go through the gateway, and the staging lock has none today. Without one, step 3 ends at once with the code `failed` and a host mail, which is the designed fallback, not a pass.

1. Merge with `scripts/merge-pr-on-green.sh` after the tests are green. Deploy staging.
2. Hand-add a stay, register it, and **do not type its code**. Archive the stay. Wait for the "door code deleted" mail.
3. Hand-add a new stay for the same dates and hours and register it. Within about a minute: you get the "an older door code covers" mail, the guest page shows a code, the TTLock app lists a custom passcode for that period, and the page has no 24-hour sentence.
4. Optional repeat of the security check (passed 2026-10-10): type the code from step 2 inside the window. It must not open.
5. Register a stay on free dates. The code appears on the save itself, and the 24-hour sentence is there.
