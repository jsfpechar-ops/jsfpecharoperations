# 0187: Operator digest at most every 72 hours

Status: todo
Depends on: none | Base commit: 106d3bb | Branch: claude/project-thread-ci1gpz
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make the filing watchdog operator digest (kind `deadline_digest`) at most once every 72 hours instead of 6, in the repository itself. The owner's 2026-10-15 server-only edit is lost on every deploy, which is why the digest came back every 6 hours (K-OPS72).

## 2. Context

- `App/app/filing_watchdog.py:57`: `DIGEST_INTERVAL = timedelta(hours=6)`
- `App/app/filing_watchdog.py` module docstring says "at most one digest per six hours".
- `App/app/host_i18n.py:1033` (EN) and `:2588` (CS) say "at most every 6 hours" / "jednou za 6 hodin".
- `App/tests/test_filing_watchdog.py:5` docstring says "every six hours"; test `test_the_operator_digest_is_throttled_to_one_per_six_hours` (~line 255) uses `timedelta(hours=6)` and `5 * 60 + 59` minutes.
- `docs/OPERATIONS.md:34` and `docs/ENVIRONMENT.md:63` mention "72 h in production (owner-applied server override ... repository default remains 6 h)".
- `docs/context/known-issues.md:94` row K-OPS72; `docs/context/status.md:7`.
- Host mails (`deadline_at_risk`) and the heartbeat do not change.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/filing_watchdog.py | edit | constant to 72 h, docstring wording |
| App/app/host_i18n.py | edit | the two intro strings: 6 hours -> 3 days |
| App/tests/test_filing_watchdog.py | edit | rename test, 6 h -> 72 h, docstring |
| docs/OPERATIONS.md, docs/ENVIRONMENT.md | edit | drop "server override / repository default 6 h", say 72 h |
| docs/context/known-issues.md, docs/context/status.md, docs/context/decisions.md | edit | close K-OPS72, drop status line, append decision |

No other file may change.

## 4. Steps

1. filing_watchdog.py: `DIGEST_INTERVAL = timedelta(hours=72)`; docstring "per six hours" -> "per 72 hours". Command: `cd App && .venv/bin/python -c "from app import filing_watchdog as f; print(f.DIGEST_INTERVAL)" 2>&1 | tail -30` prints `3 days, 0:00:00`.
2. host_i18n.py: EN "at most every 6 hours" -> "at most every 3 days"; CS "jednou za 6 hodin" -> "jednou za 3 dny".
3. Test: rename to `test_the_operator_digest_is_throttled_to_one_per_72_hours`; minutes loop `(30, 60, 71 * 60 + 59)`; final resend at `timedelta(hours=72)`; docstring "every six hours" -> "every 72 hours".
4. Docs: OPERATIONS.md and ENVIRONMENT.md state "at most every 72 hours" with no override note. known-issues K-OPS72: mark closed (follow the file's own convention for closed rows). status.md: delete line 7. decisions.md: append `- 2026-10-20 | Watchdog digest interval is 72 h in the repository (closes K-OPS72) | owner | [OPERATIONS](../OPERATIONS.md)`.
5. Run §6.

## 5. Do not touch

Host mail logic, heartbeat, other jobs, any other file. No new dependency.

## 6. Commands

- `cd App && .venv/bin/python -m pytest tests/test_filing_watchdog.py -q --tb=short -x 2>&1 | tail -30`
- `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] Both commands pass.
- [ ] `grep -rn "6 hours\|six hours" App/app/filing_watchdog.py App/tests/test_filing_watchdog.py` finds nothing about the digest.

## 8. Stop and ask

An excerpt is not found, a test fails twice, a file outside §3 needs a change, 25 tool calls reached.

## 9. Report

`docs/tasks/0187-report.md` (600 tokens max), then `Status: review`. Commit on the current branch; do not push (the orchestrator pushes).
