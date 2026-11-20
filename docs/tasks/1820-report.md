# 1820 report

Status: review

## Files

- `App/scripts/go_page_parity_screenshots.py`
- `App/tests/test_go_page_parity_screenshots.py`
- `docs/tasks/1820-go-page-screenshot-parity-tool.md`
- `docs/context/executor.md` (§6 snippet pointer)

## Commands

1. `pytest tests/test_go_page_parity_screenshots.py -q -x`: `2 passed, 1 skipped` (login smoke skipped: no `UBYHOST_TEST_DATABASE_URL` here).
2. `python3 scripts/context_lint.py`: pass after report added; workflow/test-map kept under cap with short §6 pointer to brief 1820.

## §7

- [x] Script + report outputs at 390/768/1280.
- [x] `--fail-on-visible` exits 1 on visible diffs.
- [x] Pytest smoke.
- [x] Brief holds full §6 snippet for page ports; workflow links brief 1820.

## Deviations

None.

## Questions

None.

## Owner steps

Use §6 from brief 1820 on page-port PRs; attach `/tmp/parity-NNNN` artefacts before merge guard.