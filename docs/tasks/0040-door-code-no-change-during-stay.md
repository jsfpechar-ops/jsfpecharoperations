# 0040: A stay that has started keeps its door code; the host is told about the change

Status: in-progress
Depends on: 0038 | Base commit: main | Branch: task/0040-door-code-no-change-during-stay
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

When a stay's dates or hours change after its door code window has started, UbyHost no longer replaces the code. The guest keeps the code they are using. The host gets one mail saying to adjust the code in the TTLock app. Changes before the window starts keep today's behaviour.

## 2. Context

Rules: AGENTS.md rule 2 (no new outbound call), rule 5 (no schema change), rule 9.

Why: `_handle_moves` replaces a moved stay's code even mid-stay. A new type-3 code keeps the original start, which is in the past, and a type-3 code must be first used within 24 h of its start, so it can be dead on arrival. The old code, which the guest is using, is then deleted, and the guest is locked out.

Anchor A, `App/app/door_codes.py`, in `_handle_moves`. Found verbatim once:

```python
        if row["valid_from"] and row["valid_to"]:
            if _iso_to_ms(row["valid_from"]) == start_ms and _iso_to_ms(row["valid_to"]) == end_ms:
                continue
```

Anchor B, `App/app/host_i18n.py`, once in `en` and once in `cs`: the key `"mail.door_code_notice.moved_not_deleted.body"`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/door_codes.py` | edit | Step 1 |
| `App/app/host_i18n.py` | edit | Step 2 |
| `App/tests/test_door_codes_safeguards.py` | edit | Step 3 |

No other file may change.

## 4. Steps

1. Right after anchor A, add: if `row["valid_from"]` is set and `_iso_to_ms(row["valid_from"]) <= now_ms`, or `start_ms <= now_ms`, then call `mail_notify.door_code_notice(int(row["id"]), "moved_during_stay")` and `continue`. No TTLock call. The notice's idempotency key already makes it one mail per stay.

2. In `host_i18n.py`, after anchor B:
   - `en`: `"mail.door_code_notice.moved_during_stay.subject": "%(property)s: change the door code in the TTLock app"` and `"mail.door_code_notice.moved_during_stay.body": "The stay from %(date)s changed its dates or hours while the guest is staying. UbyHost left the guest's door code as it was, with its old end. If the stay got shorter, shorten or delete the code in the TTLock app. If it got longer, give the guest a longer code there."`
   - `cs`: `"mail.door_code_notice.moved_during_stay.subject": "%(property)s: upravte kód ke dveřím v aplikaci TTLock"` and `"mail.door_code_notice.moved_during_stay.body": "Pobyt od %(date)s změnil termín nebo hodiny během pobytu hosta. UbyHost hostovi ponechal jeho kód ke dveřím beze změny, s původním koncem platnosti. Pokud se pobyt zkrátil, zkraťte nebo smažte kód v aplikaci TTLock. Pokud se prodloužil, dejte hostovi delší kód tam."`

3. Tests (monkeypatch every TTLock function; no real `_call`):
   - `test_a_change_during_the_stay_keeps_the_code`: an issued row whose `valid_from` is in the past; the reservation's `date_to` moves one day earlier; `reconcile` calls no TTLock function, the row keeps its pin, `provider_code_id`, `valid_from` and `valid_to`, and exactly one `moved_during_stay` notice is queued; a second `reconcile` queues no second notice.
   - `test_a_change_before_the_stay_still_replaces_the_code`: `valid_from` in the future; a date change still calls `create_period_code` and stores the new window (today's behaviour).

## 5. Do not touch

`issue`, `_revoke_one`, `_handle_cancellations`, `ttlock.py`, migrations, filing, guest copy.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_door_codes_safeguards.py tests/test_door_code_handover.py -q`, then `.venv/bin/python -m pytest tests -q`. From the repo root: `python3 scripts/context_lint.py`.

## 7. Acceptance

- [ ] A change after the window has started makes no TTLock call, keeps the code, and mails the host once.
- [ ] A change before the window starts still replaces the code.
- [ ] Full pytest and context lint pass.

## 8. Stop and ask

Stop and write the report if an anchor is missing, a test fails twice, a file outside §3 needs a change, or a step is unclear. Do not push to main, merge, deploy, or add a dependency.

## 9. Report

Write `docs/tasks/0040-report.md` (1,500 tokens at most) and set `Status: review`. The report has the files changed, each command with its last 5 lines, §7 ticked, deviations, questions, and owner steps.

## Risk list (for the reviewer)

`App/app/door_codes.py` (`_handle_moves`), `App/app/host_i18n.py`.

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh` after the tests are green. Deploy staging.
2. Hand-add a stay that started yesterday, register it, and type its code. Move its end date one day earlier. Within 2 minutes you get "change the door code in the TTLock app", and the code still opens the door.
