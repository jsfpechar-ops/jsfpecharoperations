# 0810 report: read guard hook

Status: blocked (context lint fails on docs/context/decisions.md)
Branch: claude/project-thread-vqgq98. Not committed, not pushed.

## Files changed

- Created: scripts/hooks/read_guard.py, .claude/settings.json, App/tests/test_read_guard_hook.py, docs/tasks/0810-report.md
- Edited (one line each): AGENTS.md, docs/context/test-map.md, docs/context/workflow.md, docs/context/decisions.md

## Commands

- `cd App && .venv/bin/python -m pytest tests/test_read_guard_hook.py -q --tb=short -rs -x`: 6 passed, 0 skipped
- `python3 scripts/context_lint.py`: FAIL. `ERROR docs/context/decisions.md: ~2238 tokens > cap 2200`. The new decisions line pushes the file over the cap.
- Live block: `docs/OPERATIONS.md` (599 lines) without limit exits 2 with the block message.
- `python3 -m json.tool .claude/settings.json`: valid.

## Deviations

- Done: steps 1 to 6. Not committed (owner instruction).
- Lint: the decisions.md line is required by §3 but makes the file exceed the 2200-token cap. Only compacting older decisions lines (outside §3) fixes it.

## Questions

- Compact an older line in docs/context/decisions.md (or move older entries to the archive) so lint passes, or drop the decisions line?

## Owner steps left

- After one week, compare token use per chat with and without the hook.
