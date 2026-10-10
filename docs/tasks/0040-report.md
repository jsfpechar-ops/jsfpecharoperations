# 0040 report: door code unchanged during stay

## Files changed

- `App/app/door_codes.py` — `_handle_moves` skips TTLock replace when the code window or stay window has already started; queues `moved_during_stay` host notice.
- `App/app/host_i18n.py` — EN and CS copy for `mail.door_code_notice.moved_during_stay`.
- `App/tests/test_door_codes_safeguards.py` — two new tests; four existing move tests use future stay dates so they still assert pre-window replace behaviour.
- `docs/tasks/0040-door-code-no-change-during-stay.md` — brief (Status: review).

## Commands (last 5 lines)

`App/`: `.venv/bin/python -m pytest tests/test_door_codes_safeguards.py tests/test_door_code_handover.py -q`

```
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
35 passed, 1 warning in 1.33s
```

`App/`: `.venv/bin/python -m pytest tests -q`

```
    grey_pixels = sum(1 for px in crop.getdata() if px < 235)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
3002 passed, 2 skipped, 7 warnings in 330.88s (0:05:30)
```

Repo root: `python3 scripts/context_lint.py`

```
next free: task 0041 | migration 0009
context lint: OK
```

## Acceptance (§7)

- [x] A change after the window has started makes no TTLock call, keeps the code, and mails the host once.
- [x] A change before the window starts still replaces the code.
- [x] Full pytest and context lint pass.

## Deviations

- Adjusted `test_a_date_change_calls_create_period_code_not_change`, `test_permission_on_a_move_does_not_add`, and `test_an_undeleted_old_code_after_a_move_tells_the_host` to use reservation dates in the future so `start_ms > now_ms` and pre-window replace behaviour is what is exercised (same file as Step 3).

## Questions

None.

## Owner steps

1. Merge with `scripts/merge-pr-on-green.sh` after the tests are green. Deploy staging.
2. Hand-add a stay that started yesterday, register it, and type its code. Move its end date one day earlier. Within 2 minutes you get "change the door code in the TTLock app", and the code still opens the door.
