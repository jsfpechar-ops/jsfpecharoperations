# 0031: Door code guest view and `ensure_row` tests

Status: in-progress
Depends on: none | Base commit: 1d2d58d6 | Branch: task/0031-door-code-view-tests
Executor: Cursor local agent (composer, Kimi or GLM) | Fits one session

## 1. Objective

Land the tests from the stale PR #316 on current `main`: the door code guest view and `ensure_row` eligibility. Tests only; no app code changes.

## 2. Context

Rules that apply: AGENTS.md hard rule 1 (filing correctness first; these tests protect the guest-facing door code path) and the CI lint step (`ruff check app tests tools --select E9,F63,F7,F82,F401,F841`).

PR #316 (closed in favour of this brief) held one commit, `abc38f4c` ("test: cover door code guest view and ensure_row eligibility"), on branch `cursor/test-coverage-door-codes-view`. It touched two test files. Only one is wanted now:

- `App/tests/test_door_codes_view.py` (new, 263 lines). Wanted. It fails the CI lint step with one error: `datetime.timezone` is imported but unused.
- `App/tests/test_staging_password_login.py` (+9 lines). **Not wanted**: it conflicts with `main`, which rewrote that file when staging login changed (#325). Do not bring it over.

The file's first lines must read exactly (if not, STOP, §8):

```python
"""Guest and host door-code display plus row creation eligibility (task 0009–0016)."""
from __future__ import annotations

from datetime import date, timedelta, timezone

import pytest

from app import config, db, door_codes
```

On `main`, `App/app/door_codes.py` defines `ensure_row(reservation_id: int) -> Optional[int]`, which the tests call.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_door_codes_view.py | create | taken from commit `abc38f4c`, with the `timezone` import removed |
| docs/tasks/0031-report.md | create | the report (§9) |

No other file may change.

## 4. Steps

1. `git fetch origin cursor/test-coverage-door-codes-view main`
2. `git checkout -b task/0031-door-code-view-tests origin/main`
3. `git checkout origin/cursor/test-coverage-door-codes-view -- App/tests/test_door_codes_view.py`
4. In that file change `from datetime import date, timedelta, timezone` to `from datetime import date, timedelta`.
5. From `App/`: `.venv/bin/ruff check app tests tools --select E9,F63,F7,F82,F401,F841` must print `All checks passed!`.
6. Run the commands in §6. If a test in the new file fails on `main` because the app code moved since the PR was written, do not change app code: note which test and why in the report, and STOP (§8).
7. Write `docs/tasks/0031-report.md`, set `Status: review`, open one PR.

## 5. Do not touch

Everything under `App/app/`, `App/tests/test_staging_password_login.py` and every other test file. AGENTS.md hard rule 3 (public repo: no real guest data in tests; the file's rows use the `dc-view-` prefix, keep it that way and report any value that looks real).

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_door_codes_view.py -q
.venv/bin/python -m pytest tests -q
```

Expected: both pass; the second with 0 skipped.
From the repo root: `python3 scripts/context_lint.py` passes.

## 7. Acceptance

- [ ] `git diff --stat origin/main` shows only `App/tests/test_door_codes_view.py` and the report.
- [ ] Ruff command in step 5 prints `All checks passed!`.
- [ ] Both pytest commands pass.
- [ ] CI on the PR is green (`gh pr checks`).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/0031-report.md` (1,500 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/tests/test_door_codes_view.py`: the `_purge` fixture deletes rows by the `dc-view-` username prefix only; check it cannot match real rows.

## Owner steps

1. Open the PR the executor made and wait for the checks to go green.
2. Merge it with `scripts/merge-pr-on-green.sh <pr-number>`.
3. The branch `cursor/test-coverage-door-codes-view` can be deleted in GitHub (Branches page) after the merge.
