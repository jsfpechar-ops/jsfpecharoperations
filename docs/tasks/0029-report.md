# 0029 report: CI green again: remove two unused test imports

Status: review
Branch: `task/0024-door-code-immediate-handover` (PR #326), base `b79a9ec`.

## Steps

1. Done. Fetched and checked out `task/0024-door-code-immediate-handover`, pulled. Already at `b79a9ec`.
2. Done. Ran the ruff command before the edit: `Found 2 errors.`, the two named in §2 (`TestClient` at line 7, `app.alerts` at line 11). No other errors.
3. Done. Deleted anchor F1 (`from fastapi.testclient import TestClient` and the blank line after it). Found exactly once.
4. Done. Replaced anchor F2 with `from app import config, db, deadlines, door_codes, ttlock`. Found exactly once.
5. Done. Ran §6 (below). Committed and pushed (see the end of this section).

## Commands

Before the edit: `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841 --output-format concise`, last 3 lines:

```
tests/test_door_codes_safeguards.py:11:17: F401 [*] `app.alerts` imported but unused
Found 2 errors.
[*] 2 fixable with the `--fix` option.
```

After the edit: same ruff command, last line:

```
All checks passed!
```

`.venv/bin/python -m pytest tests/test_door_codes_safeguards.py tests/test_door_code_handover.py -q`, last 3 lines:

```

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
22 passed, 1 warning in 0.72s
```

`python3 scripts/context_lint.py`, last line: `context lint: OK`

## Section 7

- [x] Step 2 showed the 2 errors; §6 ruff shows `All checks passed!`.
- [x] `git diff --stat b79a9ec` lists only §3 files (checked before the commit; see the commit).

## Deviations

None. No test body was touched.

## Questions

None.

## Owner steps left

1. After the push, open PR #326 on GitHub and wait for the checks. If `test` is still red, send the orchestrator the PR link: the next steps in that job are `pip-audit` and the 86 % coverage floor. Those were not checked in this run.
