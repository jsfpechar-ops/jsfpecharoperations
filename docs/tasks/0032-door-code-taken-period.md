# 0032: A taken door-code period gets a custom code from the worker

Status: todo
Depends on: none | Base commit: main | Branch: task/0032-door-code-taken-period
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

When TTLock already holds a type-3 code for a stay's hours, UbyHost creates a custom code for that stay instead of asking for the same random code again. A change of dates or check-in hour creates a new code the same way, and never calls `keyboardPwd/change`.

## 2. Context

Rules that apply: AGENTS.md rule 2 (this adds one outbound call, `POST /v3/keyboardPwd/add`, only after `-1026`; no guest name or e-mail is sent; say that in the PR), rule 4 (no new dependency), rule 5 (no schema change; `door_code.code_kind` already exists), rule 9 (the 24-hour sentence is omitted for a custom code; no new sentence).

The behaviour is decided in [plan §6](../plans/ttlock-door-codes.md#6-states) and [TTLOCK](../TTLOCK.md) (rows `-1026` and `-3008`). Do not re-open it. `-1026` is not in TTLock's published list. Treat only that number as "period taken".

Anchor A, `App/app/ttlock.py`, the error map. Found verbatim once:

```python
    -3008: "unused_code",
}
```

Anchor B, `App/app/ttlock.py`, the path sets. `"/v3/keyboardPwd/add"` is absent from both. Found verbatim once each:

```python
        "/v3/keyboardPwd/get",
        "/v3/keyboardPwd/change",
        "/v3/keyboardPwd/delete",
```

```python
        "/v3/keyboardPwd/change",
        "/v3/keyboardPwd/delete",
```

Anchor C, `App/app/door_codes.py`, the move still calls change. Found verbatim once:

```python
            ttlock.change_code_period(
```

Anchor D, `App/app/door_codes.py`, the issued view always sets a first-use deadline. Found verbatim once:

```python
        "first_use_by": _fmt_local(_ms_to_iso(_iso_to_ms(valid_from) + 24 * 3_600_000)) if valid_from else "",
```

Anchor E, `App/app/templates/guest/stay.html`. Found verbatim once:

```html
        <p class="g-intro">{{ t('door_code_first_use', deadline=door_code.first_use_by) }}</p>
```

`on_registration_complete` calls `issue(row_id)` with no gateway flag. The minute job calls `issue` from `_issue_due`. Gateway calls stay in the worker: the guest save must not call `add`.

Delete the known-issues row `K-D01` in this change. It describes the bug this brief fixes.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/ttlock.py` | edit | Steps 1 and 2 |
| `App/app/door_codes.py` | edit | Steps 3 to 6 |
| `App/app/mail_notify.py` | edit | Step 7 |
| `App/app/templates/guest/stay.html` | edit | Step 6 |
| `App/tests/test_ttlock.py` | edit | Step 8 |
| `App/tests/test_door_codes_safeguards.py` | edit | Step 8 |
| `docs/context/known-issues.md` | edit | Delete the `K-D01` row |

No other file may change.

## 4. Steps

1. In `ERROR_KINDS`, add `-1026: "period_taken",` and `-3007: "duplicate",` next to the `-3008` line. Leave `-3008` as `unused_code`. `-2018` stays `permission`.

2. Add `"/v3/keyboardPwd/add"` to `ALLOWED_PATHS` and to `GATEWAY_PATHS` (35 s, worker only). Add `add_custom_code(account_id, lock_id, start_ms, end_ms, name, priority=NORMAL) -> Tuple[str, str]`. It checks whole hours the same way `create_period_code` does. It posts `/v3/keyboardPwd/add` with `lockId`, `keyboardPwd` (7 digits, first digit 1-9, from `secrets`), `keyboardPwdName=name`, `keyboardPwdType=3`, `startDate`, `endDate`, `addType=2`. On `TTLockError` with `code == -3007`, draw one new PIN and post once more. A second `-3007` raises. Return `(pin, str(keyboardPwdId))`. Log nothing but what `_post` already logs. Never log the PIN.

3. `issue(door_code_id, *, allow_gateway=False)`. `on_registration_complete` keeps `issue(row_id)` so `allow_gateway` is false. `_issue_due` calls `issue(int(row["id"]), allow_gateway=True)`.

   Before `create_period_code`: if `attempts > 1`, keep the existing `find_code_by_name` adopt. If that misses and `(row["last_error"] or "").startswith("period_taken")`, call `add_custom_code` instead of `create_period_code`, and set `code_kind` to `custom` on the issued update. A random success still sets `code_kind` to `random`.

   On `TTLockError` whose `kind == "period_taken"`: if `allow_gateway` is false, set `state` back to `retrying`, `last_error` to `period_taken:<code>`, `next_attempt_at` to now, `claimed_at` NULL, and return False. Do not send the failure mail. If `allow_gateway` is true, call `add_custom_code` with the same window and name, store it as `custom`, and return True. If that `add` raises `TTLockError` with kind `offline`, `transient`, `network`, `rate` or `budget`, keep `last_error` starting with `period_taken` and use the existing backoff (budget: 60 minutes, and that attempt does not count). Kind `permission`, `reauth`, `config`, `disabled`, `storage` or `duplicate` goes to `failed` and the existing host mail. Any other kind from `add` uses the same backoff and keeps the `period_taken` prefix so the next run calls `add`, not `get`.

4. In `_handle_moves`, delete the `change_code_period` call. For a row whose `last_error` starts with `permission`, `reauth`, `config` or `disabled`, skip the row. Otherwise call `create_period_code`. On `kind == "period_taken"`, call `add_custom_code` in this same run (this function runs only in the worker). On `permission`, `reauth`, `config` or `disabled`, set `last_error` to `kind:code`, do not call `add`, and call `mail_notify.door_code_notice(door_code_id, "failed")` once. On success, set `code_kind` to `random` or `custom`, store the new pin and id, clear `notified_at`, best-effort `delete_code` of the previous id when it differs, audit `door_code_replaced`, and `send_code_mail`. A gateway failure on `add` (`offline`, `transient`, `network`, `rate`, `budget`) sets `next_attempt_at` 15 minutes ahead (60 for budget) and `last_error` starting with `period_taken`, and does not delete the old code.

5. The issued `UPDATE` in both `issue` and `_handle_moves` writes `code_kind`.

6. In `view`, when `row["code_kind"] == "custom"`, set `first_use_by` to `""`. In `guest/stay.html`, wrap the first-use paragraph in `{% if door_code.first_use_by %}`.

7. In `build_door_code` and in `build_completion` (the block that uses `door_code["first_use_by"]`), omit the first-use paragraph and the first-use text line when `first_use_by` is empty. `send_code_mail` already passes `shown["first_use_by"]`.

8. Tests:
   - `test_ttlock.py`: `add` is allowed, uses `timeout=35`, sends `addType=2` and `keyboardPwdType=3`, and the passcode does not start with 0. A `-3007` then a success uses a second passcode. The allowlist source scan still passes.
   - `test_door_codes_safeguards.py`: replace `test_a_never_used_code_is_replaced_not_retried_forever` so a date change calls `create_period_code` and does not call `change_code_period`. Add `test_a_taken_period_is_not_retried_from_the_guest_save`: `create_period_code` raises `TTLockError("taken", code=-1026, kind="period_taken")` during `on_registration_complete`; `add_custom_code` is not called; the row is `retrying` with `last_error` `period_taken:-1026`. Add `test_the_worker_adds_a_custom_code_when_the_period_is_taken`: the next `reconcile` calls `add_custom_code`, stores `code_kind=custom`, and `view` has `first_use_by == ""`. Add `test_permission_on_a_move_does_not_add`: `create_period_code` raises `-2018` / `permission` from `_handle_moves`; `add_custom_code` is not called; a second `reconcile` does not call TTLock again.

## 5. Do not touch

`App/app/migrations/`, filing, UbyPort, `change_code_period` (leave the function; nothing in `door_codes.py` calls it), guest copy keys, the host property page's 24-hour hint. No new dependency. No call to `keyboardPwd/change`. No shifting of `startDate` or `endDate`. No reading of another stay's PIN.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_ttlock.py tests/test_door_codes_safeguards.py tests/test_door_codes_view.py tests/test_door_code_handover.py tests/test_guest_mail.py -q`

Then `.venv/bin/python -m pytest tests -q`

From the repo root: `python3 scripts/context_lint.py`

Expected: all pass, last lint line `context lint: OK`.

## 7. Acceptance

- [ ] A guest save whose `get` returns `-1026` makes no `add` call, and the row's `last_error` is `period_taken:-1026`.
- [ ] The next `reconcile` calls `add` once, sets `code_kind` to `custom`, and the guest view's `first_use_by` is empty.
- [ ] A date change does not call `change_code_period`.
- [ ] `-2018` on that date change does not call `add`, and the following reconcile makes no TTLock call for that stay.
- [ ] `grep -n "keyboardPwd/change" App/app/door_codes.py` prints nothing.
- [ ] `grep -n "log\." App/app/ttlock.py` shows no PIN, token or response body.
- [ ] `K-D01` is gone from `docs/context/known-issues.md`.
- [ ] Full pytest and context lint pass.

## 8. Stop and ask

Stop, and write the report, if an anchor is missing, a test fails twice, a file outside §3 needs a change, or a step is unclear. Do not push, merge, deploy, or add a dependency.

## 9. Report

Write `docs/tasks/0032-report.md` (1,500 tokens at most) and set `Status: review`. The report has the files changed, each command with its last 5 lines, §7 ticked, deviations, questions, and owner steps.

## Risk list (for the reviewer)

`App/app/ttlock.py` (`add_custom_code`, allowlist), `App/app/door_codes.py` (`issue`, `_handle_moves`), `App/app/templates/guest/stay.html`.

## Owner steps

1. Merge this PR with `scripts/merge-pr-on-green.sh` after the tests are green.
2. Deploy staging.
3. On the demo lock, cancel a stay that already has a code, then register a new hand-added stay for the same dates and hours. The guest page should show a code within about a minute. The TTLock app should show a custom passcode for that period. The 24-hour warning should be absent on that stay.
4. Register a different stay on free dates. The code should still appear on the save itself, and the 24-hour sentence should still be there.
