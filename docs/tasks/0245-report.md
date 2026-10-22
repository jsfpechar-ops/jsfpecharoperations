# 0245 report

Status: review

## Files changed

- App/app/claim.py (step 1)
- App/app/mail_notify.py (steps 2, 3)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (step 4)
- App/tests/test_arrival_nudge_0245.py (new, step 5)
- docs/tasks/0245-report.md

## Commits

- a06b5be 0245 step 1
- 6d570bf 0245 step 2
- f23105e 0245 step 3
- e6d4fba 0245 step 4
- e67983f 0245 step 5

## Commands (last lines)

- Step 4: `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_host_i18n.py tests/test_guest_mail.py -q --tb=short` → `77 passed, 2 warnings in 3.22s`
- Step 5: `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_arrival_nudge_0245.py -q --tb=short` → `15 passed, 1 warning in 2.13s`
- §6.1: `.venv/bin/python -m pytest tests/test_alert_stack.py tests/test_arrival_nudge_0245.py tests/test_claim_mail.py tests/test_guest_mail.py tests/test_door_codes_safeguards.py tests/test_door_code_handover.py tests/test_confirmation_with_door_code.py tests/test_host_i18n.py tests/test_pii_encryption.py tests/test_retention_job.py -q --tb=short` → `208 passed, 3 warnings in 9.65s`
- §6.2: `.venv/bin/ruff check app tests --select E9,F63,F7,F82,F401,F841` → `All checks passed!`
- §6.3: `python3 scripts/context_lint.py` → `context lint: OK` (WARN lines are pre-existing brief-overlap notes)

## §7 acceptance

- [x] §6 commands 1 and 2 pass.

## Deviations

- Edits were applied by a script that asserts each anchor matches exactly once; the text applied is the brief's text. The first step 3 attempt hit a non-unique anchor and wrote nothing; it was re-run with line-start anchors.
- The working tree already had unrelated modified and untracked files under docs/tasks/0102-evidence. They were not touched or committed.
- No screenshot: this change is mail HTML, not a template, CSS or guest page.

## Questions

- In sweep_reminders, `summary["host_early"]` increments even when the stay has no host contact email (the enqueue is skipped, the count is not). The brief does this as written; please confirm it is the intended count.

## Owner steps left

- None.
