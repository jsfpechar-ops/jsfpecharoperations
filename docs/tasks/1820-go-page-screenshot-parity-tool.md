# 1820: Go page screenshot parity tool

Status: review
Depends on: none | Base commit: main | Branch: cursor/1820-page-parity-screenshots-dff7
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `App/scripts/go_page_parity_screenshots.py` so page-port executors and reviewers capture the same URL on Python FastAPI and Go, compare 390/768/1280 px screenshots, and get an allowed-invisible-diff report. Page PRs do not start merge guard until this passes.

## 2. Context

Owner merge gate 2026-11-20 ([internal note](/cursor/stores/bc-6e0cc745-51a8-434b-ae3b-2eb8d63269b1/internal/merge-review-gate-2026-11-20.md)): page ports need side-by-side Python vs Go shots at 390, 768, 1280 px, pixel-identical or each diff explained as invisible. Pillow is already pinned (`App/requirements.lock`). Playwright is dev-only (same as browser tests). `App/tests/go_stack.py` starts `ubyhost-web` when `UBYHOST_TEST_DATABASE_URL` is set.

## 3. Files

| Path | Action | What |
| --- | --- | --- |
| `App/scripts/go_page_parity_screenshots.py` | create | CLI + library: capture, side-by-side, diff PNGs, JSON/Markdown report |
| `App/tests/test_go_page_parity_screenshots.py` | create | Pillow helper smoke + optional `/login` browser smoke |
| `docs/context/executor.md` | edit | Pointer to this brief’s §6 snippet |
| `docs/tasks/1820-report.md` | create | Executor report |

No other file may change.

## 4. Steps

1. Add the script (done in this PR).
2. Add the pytest smoke file (done in this PR).
3. Add the executor pointer in `docs/context/executor.md`.
4. Run §6.
5. Write `docs/tasks/1820-report.md`, open PR, run merge guard when self-test is green.

**Page port §6 snippet** (paste into host page-port briefs):

```markdown
## 6. Commands

From `App/`, with Postgres for Go (`export UBYHOST_TEST_DATABASE_URL=...`) and `UBYHOST_GO_PATHS` listing only the paths this brief ports:

1. `.venv/bin/python scripts/go_page_parity_screenshots.py --name <page> --path '<exact-path>' --out /tmp/parity-NNNN --fail-on-visible 2>&1 | tail -30`
   Expected: each width `identical` or `invisible`; `parity-report.md` lists any allowed invisible diffs; no `visible` without an explanation in the report.
2. `.venv/bin/python -m pytest tests/test_go_page_parity_screenshots.py -q -x 2>&1 | tail -30`
   Expected: helper tests pass; browser smoke passes or skips when Go/Postgres missing.
3. If the PR touches host layout: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30` (0 skipped).
```

## 5. Do not touch

`App/app/`, `go/`, deploy, secrets. No new dependency.

## 6. Commands

From `App/`:

1. `.venv/bin/python -m pytest tests/test_go_page_parity_screenshots.py -q -x 2>&1 | tail -30`
2. From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`

## 7. Acceptance

- [ ] Script writes py/go/side/diff PNGs at 390, 768, 1280 and a parity report.
- [ ] `visible` diffs fail when `--fail-on-visible` is set.
- [ ] §6 pytest passes (skips allowed when no Postgres).
- [ ] Workflow documents the §6 snippet for page ports.

## 8. Stop and ask

Missing Playwright in CI image, Postgres URL unset (report skip), or Go build failure.

## 9. Report

`docs/tasks/1820-report.md`

## Risk list

`App/scripts/go_page_parity_screenshots.py`, `App/tests/test_go_page_parity_screenshots.py`

## Owner steps

1. After merge, page-port orchestrators paste §6 snippet into each host page brief.
2. On a page PR, executor attaches `/tmp/parity-NNNN` shots to the PR body before merge guard.