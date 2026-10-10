# 0038: A cancelled stay's custom code is deleted, however long the gateway is down

Status: review
Depends on: 0037 | Base commit: 0037's merge | Branch: task/0038-custom-code-revoke
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

A custom code (`code_kind = 'custom'`, from 0037) is stored on the lock and works until it is deleted. When its stay is cancelled, UbyHost keeps trying the delete until the code's end time, and tells the host once if the first three tries fail. A random code keeps today's behaviour.

## 2. Context

Rules that apply: AGENTS.md rule 2 (no new outbound call: `keyboardPwd/delete` already exists), rule 5 (no schema change).

Today `_revoke_one` gives up after 3 tries (1, 15 and 60 minutes) and sets `revoke_failed`. A gateway that is offline for about 80 minutes therefore leaves a cancelled guest with a working custom code until its end date. For a custom code the lock does know the code, so a later delete does work ([TTLOCK](../TTLOCK.md), "Custom codes").

Anchor A, `App/app/door_codes.py`, in `_revoke_one`. Found verbatim once:

```python
        if kind in ("offline", "transient", "network", "rate") and attempts < 3:
            delays = (1, 15, 60)
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/door_codes.py` | edit | Steps 1 and 2 |
| `App/tests/test_door_codes_safeguards.py` | edit | Step 3 |

No other file may change.

## 4. Steps

1. In `_revoke_one`, for `row["code_kind"] == "custom"` and a kind in `("offline", "transient", "network", "rate", "budget")`: stay in `revoke_pending`. `next_attempt_at` is 1, 15, then 60 minutes ahead, then every 60 minutes. When `attempts == 3`, call `mail_notify.door_code_notice(row_id, "cancelled_not_deleted")` once (its idempotency key already prevents a second mail). When now is past `valid_to`, set `revoke_failed` and stop: the code no longer opens the door. Any other kind keeps today's `revoke_failed` branch.

2. A random code (`code_kind` not `custom`) keeps exactly today's branch.

3. Tests:
   - `test_a_custom_code_delete_keeps_trying`: a cancelled `custom` row, `delete_code` raises `offline` on five runs (advance `next_attempt_at`). The row stays `revoke_pending`, exactly one `cancelled_not_deleted` notice is queued, and the sixth run (success) sets `revoked` and clears `pin_enc`.
   - `test_a_custom_code_delete_stops_after_the_end`: `valid_to` in the past, `delete_code` raises `offline`; the row becomes `revoke_failed` and no further call is made.
   - The existing random-code revoke tests pass unchanged.

## 5. Do not touch

`issue`, `_handle_moves`, `ttlock.py`, mail copy, migrations, filing.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_door_codes_safeguards.py tests/test_door_code_handover.py -q`, then `.venv/bin/python -m pytest tests -q`. From the repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance

- [x] A cancelled custom code is retried hourly until `valid_to`, with one host mail after the third failure.
- [x] A random code's revoke is unchanged.
- [x] Full pytest and context lint pass.

## 8. Stop and ask

Stop and write the report if the anchor is missing, a test fails twice, a file outside §3 needs a change, or a step is unclear. Do not push, merge, deploy, or add a dependency.

## 9. Report

Write `docs/tasks/0038-report.md` (1,500 tokens at most) and set `Status: review`. The report has the files changed, each command with its last 5 lines, §7 ticked, deviations, questions, and owner steps.

## Risk list (for the reviewer)

`App/app/door_codes.py` (`_revoke_one`).

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh` after the tests are green. Deploy staging.
2. On a lock with a gateway: give a stay a custom code (0037 owner step 3), unplug the gateway, archive the stay. After about 80 minutes you get "delete a door code in the TTLock app". Plug the gateway back in. Within an hour, typing that code no longer opens the door.
