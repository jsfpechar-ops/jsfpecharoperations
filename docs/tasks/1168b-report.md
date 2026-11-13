# 1168b report: door-code notice accuracy

Status: review

## Files changed

- App/app/mail_notify.py: optional `key_suffix` on `door_code_notice` and `_door_code_notice`, appended to the idempotency key.
- App/app/door_codes.py: `moved_failed` passes `key_suffix=f"{start_ms}-{end_ms}"`.
- App/app/host_i18n.py: en and cs `pin_unverified` and `moved_failed` bodies (cs word order fixed).
- App/app/host_vi_i18n.py: vi `pin_unverified` and `moved_failed` bodies.
- App/tests/test_door_code_host_notices.py: `_mails` matches the suffixed key; new test `test_a_failed_move_mails_again_only_for_a_different_target_window`.
- docs/tasks/1168b-report.md: this report.

## Commands (last 5 lines)

`.venv/bin/python -m pytest tests/test_door_code_host_notices.py -q --tb=short -x`
```
................                                                         [100%]
16 passed in 0.80s
```

`.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock_lock_setup.py tests/test_0280_short_notifications.py tests/test_alert_language.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py -q --tb=short`
```
319 passed, 1 skipped, 1 warning in 8.35s
```

`.venv/bin/python -m pytest tests/test_door_code_host_notices.py tests/test_0280_short_notifications.py tests/test_alert_language.py tests/test_host_i18n.py tests/test_go_host_i18n.py tests/test_no_em_dashes.py -q -rs`
```
71 passed, 1 warning in 4.56s
```

`.venv/bin/ruff check app tests --select E9,F63,F7,F82,F401,F841`
```
All checks passed!
```

`python3 scripts/context_lint.py` (repo root)
```
next free: task 1167 | migration 0046
context lint: OK
```

Acceptance grep for old wording (`every hour until the stay`, `did not answer when UbyHost`, `kód hosta tam je`): no output.

## Section 7 checklist

- [x] Two different target windows give two `moved_failed` mails; the same window retried gives one.
- [x] en, cs and vi bodies match section 4; old-wording grep is empty.
- [x] Section 6 commands pass; no em dashes in the diff.

## Revert-bite

FAIL (old source restored from `291b6f60^`):
```
tests/test_door_code_host_notices.py:138: in test_a_failed_move_mails_again_only_for_a_different_target_window
    assert len(_mails(stay, "moved_failed")) == 2
E   AssertionError: assert 1 == 2
1 failed in 0.50s
```

PASS (change restored):
```
1 passed in 0.34s
```

## Deviations

- The revert-bite used `git checkout 291b6f60^ -- <2 files>` instead of `git stash push`, because the source edits were already committed by steps 1 and 2. The working tree was restored with `git checkout HEAD -- <2 files>` before the PASS run.
- Step commits are `1168b step 1` to `1168b step 5`.

## Questions

None.

## Owner steps left

- Review and open the PR from `task/1168b-notice-accuracy` (not done here, per instructions). No merge or deploy was run.
