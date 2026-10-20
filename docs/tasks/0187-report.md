# 0187 report

Status: blocked

## Files changed
- App/app/filing_watchdog.py: DIGEST_INTERVAL 72 h, docstrings "per 72", "last 72 hours"
- App/app/host_i18n.py: EN "at most every 3 days", CS "jednou za 3 dny"
- App/tests/test_filing_watchdog.py: test renamed `..._to_one_per_72_hours`, loop `71 * 60 + 59`, resend at 72 h, docstring
- docs/OPERATIONS.md, docs/ENVIRONMENT.md: override note removed, "72 h" / "72 hours"
- docs/context/known-issues.md: K-OPS72 row deleted (file convention: fixed rows are deleted)
- docs/context/status.md: line 7 deleted
- docs/context/decisions.md: decision line appended

Commits: 0187 step 1 to 4 (ac81d47, c573cc8, 1227f86, 94e5310). Not pushed.

## Commands
- `cd App && .venv/bin/python -c "...DIGEST_INTERVAL" | tail -30` -> `3 days, 0:00:00`
- `cd App && .venv/bin/python -m pytest tests/test_filing_watchdog.py -q --tb=short -x | tail -30` -> `39 passed, 1 warning in 2.00s`
- `python3 scripts/context_lint.py | tail -30` -> `ERROR docs/context/decisions.md: ~2229 tokens > cap 2200` and `context lint: FAIL`. The WARN lines (open briefs naming shared files, 7 commits after status.md) are not errors.

## Section 7
- [x] pytest passes
- [ ] context lint passes (fails on the decisions.md token cap)
- [x] grep for digest "6 hours"/"six hours": nothing about the digest (only "36 hours" test comments remain)

## Deviations
- Created App/.venv (git-ignored) and installed requirements.txt and requirements-dev.txt; the brief's commands need it.
- Also changed filing_watchdog.py `send_operator_digest` docstring "last six hours" to "72 hours", because §7's grep requires it.
- No PR opened and no push: the owner's instruction was not to push, and brief §9 says the orchestrator pushes.
- Done: steps 1 to 4. Left: step 5 lint pass (blocked, see Questions).

## Questions
- decisions.md is over the lint cap by about 29 tokens because of the appended line. Stopped per brief §8, since fixing it needs a compaction (workflow.md#compaction, which creates an archive file outside §3) or a shorter decision line. Which one?

## Owner steps left
- Decide the compaction or shorter line, then the orchestrator pushes the branch.
- No deploy action is needed for the repo change. The server-only 72 h override now matches the repository.
