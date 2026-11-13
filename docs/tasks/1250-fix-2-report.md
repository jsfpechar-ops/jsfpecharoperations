# 1250-fix-2 report

Status: review

## Files changed
- `App/tests/test_sm_queues.py`: added `GOIMPORT` constant, four `IMPORT_SITES` entries, eight `IMPORT_MOVES` entries (guide_import writers in `go/internal/guideimport/job.go`).
- `docs/tasks/1250-fix-2-pin-go-guide-import-writers.md`: Status set to review.

## Commits
- `d50b6e7` 1250-fix-2 step 1: pin Go guide_import writers

## Commands
`cd App && .venv/bin/python -m pytest tests/test_sm_queues.py -q --tb=short 2>&1 | tail -30`
```
....                                                                     [100%]
4 passed in 0.30s
```

## Acceptance (§7)
- [x] test_sm_queues.py passes; only that file changed (plus the brief status and this report).

## Screenshots
Not applicable (no UI change).

## Deviations
- Commit message trailers use the Haiku 5.5 Co-Authored-By line and the session link from the orchestrator instructions.
- Not pushed and no PR opened: the orchestrator said do not push. Owner or orchestrator needs to push the branch and open the PR.

## Questions
None.

## Owner steps left
- Push `task/1250-go-guide-import` and open the PR, then let CI confirm `test_guide_import_writers_match_import_transitions`.
