# 0029: CI green again: remove two unused test imports

Status: todo
Depends on: none | Base commit: `b79a9ec` (head of PR #326) | Branch: `task/0024-door-code-immediate-handover` (commit on top; never rebase or force-push)
Executor: Claude Haiku 5.5, effort high (or Cursor composer, Kimi, GLM) | Fits one session

## 1. Objective

CI's `test` job is red on `main` since PR #325 and on PR #326, because its lint step fails before any test runs: `ruff check app tests tools --select E9,F63,F7,F82,F401,F841` finds two unused imports in `App/tests/test_door_codes_safeguards.py`. Remove them in PR #326, so that PR is green and `main` is green after it merges.

## 2. Context

Reviewer's run of that command on `b79a9ec`:
```
tests/test_door_codes_safeguards.py:7:32: F401 [*] `fastapi.testclient.TestClient` imported but unused
tests/test_door_codes_safeguards.py:11:17: F401 [*] `app.alerts` imported but unused
Found 2 errors.
```
Anchor F1, `App/tests/test_door_codes_safeguards.py` (exactly once, with the blank line after it):
```python
from fastapi.testclient import TestClient

```
Anchor F2, same file (exactly once):
```python
from app import alerts, config, db, deadlines, door_codes, ttlock
```
Never delete or change a test to get green.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_door_codes_safeguards.py` | edit | two import lines |
| `docs/tasks/0029-report.md` | create | report |

No other file may change.

## 4. Steps

1. `git fetch origin task/0024-door-code-immediate-handover && git checkout task/0024-door-code-immediate-handover && git pull origin task/0024-door-code-immediate-handover`.
2. From `App/`: `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841` (if `.venv/bin/ruff` is missing: `.venv/bin/pip install -r requirements-dev.txt`). Expected: `Found 2 errors.` as in §2. Anything else: STOP (§8).
3. Delete anchor F1 (the import line and the blank line after it).
4. Replace anchor F2 with `from app import config, db, deadlines, door_codes, ttlock`.
5. Run §6, commit (`0029: remove two unused test imports so CI lint passes`), `git push origin task/0024-door-code-immediate-handover`.

## 5. Do not touch

Any test body; any file under `App/app/`.

## 6. Commands

From `App/`:
- `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841` → `All checks passed!`
- `.venv/bin/python -m pytest tests/test_door_codes_safeguards.py tests/test_door_code_handover.py -q` → 0 failed.

From the repo root: `python3 scripts/context_lint.py` → last line `context lint: OK`.

## 7. Acceptance

- [ ] Step 2 showed the 2 errors; §6 ruff shows `All checks passed!`.
- [ ] `git diff --stat b79a9ec` lists only §3 files.

## 8. Stop and ask

Stop, and write the report, if: an anchor is not found exactly once; step 2 shows other errors; a test fails; a file outside §3 needs a change; you need merge, secrets, SSH or deploy.

## 9. Report

`docs/tasks/0029-report.md` (600 tokens at most), `Status: review`: every numbered step with done or skipped, each command with its last 3 lines, §7 ticked.

## Risk list (for the reviewer)

Only the two import lines.

## Owner steps

1. After the push, open PR #326 on GitHub and wait for the checks. If `test` is still red, send the orchestrator the PR link: the next steps in that job are `pip-audit` and the 86 % coverage floor.
