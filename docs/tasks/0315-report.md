# 0315 report: guide audit coverage table

Status: review

## Files changed

- `docs/plans/guide-coverage.md` (new): coverage table and order, as in brief step 2.
- `docs/tasks/0315-report.md` (new): this report.

## Commands

- Anchor checks (step 1): `grep -c "settings-account" App/tests/test_design_guardrails_browser.py` gives `1`; `grep -c "'door-codes', 'faster'" App/app/templates/guide.html` gives `1`.
- `grep -c '^| ' docs/plans/guide-coverage.md` gives `27`.
- `python3 scripts/context_lint.py 2>&1 | tail -3` gives `context lint: OK` (last lines: a RETENTION.md WARN about open briefs, `next free: task 0371 | migration 0020`, `context lint: OK`).

## Section 7 acceptance

- [x] `docs/plans/guide-coverage.md` exists with the table and the order, as in step 2.
- [x] The lint is OK.

## Deviations

- Base: the brief names 92646d3. `origin/main` is f311d3b; the worktree was already on `task/0315-guide-audit` at f311d3b, so step 1's `checkout -b` was skipped.
- No PR opened and no push, per the orchestrator's instruction.

## Questions

- None.

## Owner steps left

1. Read the table. If a page is missing that you want Havel to know about, say so before 0318 runs.
