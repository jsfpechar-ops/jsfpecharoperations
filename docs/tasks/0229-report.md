# 0229 report: push privacy text

Status: review

## Commits (branch claude/project-thread-w35ftw)

- 0229 step 1: privacy_policy_i18n.py, 8 replacements (EN and CS), each anchor asserted once.
- 0229 step 2: subprocessors_i18n.py, `subprocessors.recipient_push` added before each `recipient_ttlock` entry (EN, CS).
- 0229 step 3: routes/legal.py, "push" added to RECIPIENT_IDS, hidden when `config.WEB_PUSH` is off, comment line added.
- 0229 step 4: tests/test_privacy_legal_positions.py, one new test.
- Report and Status commit (this file).

## Commands

- `cd App && .venv/bin/python -m pytest tests/test_privacy_legal_positions.py tests/test_privacy_*.py tests/test_no_em_dashes.py tests/test_owner_decisions.py tests/test_operator_naming.py -q --tb=short 2>&1 | tail -30`
  Last lines: `60 passed, 1 warning in 7.17s`
- `python3 scripts/context_lint.py 2>&1 | grep -v ^WARN | tail -3`
  Last lines: `next free: task 0209 | migration 0012` / `context lint: OK`

## Acceptance (section 7)

- [x] Commands pass.
- [x] `grep -c "Mozilla" App/app/privacy_policy_i18n.py` prints 2.

## Deviations

- Step 1 commit was first made without the Co-Authored-By and Claude-Session trailers; amended before any further commit to add them. No content change.
- No push, no PR, no message posted (orchestrator instruction).
- Step 4 test used the names already imported in the test file (`config`, `SUBPROCESSOR_STRINGS`, `_get`); no new imports were needed.

## Questions

None.

## Owner steps left

- Review and merge the branch with `scripts/merge-pr-on-green.sh` once a PR is opened.
- Production deploy is manual.
