# 1620 report: Go public pages golden script (executor run)

Status: review. One-big-PR mode: commits on branch go-wave3, no push, no PR.

## 1. Files changed
- `App/scripts/public_pages_golden.py` (create, 143 lines, sha256 verified)
- `App/tests/test_go_public_pages.py` (create, 22 lines, sha256 verified)
- `go/internal/web/public/catalog_pages.json` (generated)
- `go/internal/web/public/testdata/pages/cases.json` and 28 `.html` files (generated; 29 files in the directory)
- `docs/tasks/1620-go-public-pages-golden.md` (Status line only)
- `docs/tasks/1620-report.md` (new)

Commits: `1620 step 1` (d472cd953), `1620 step 2` (891564a48), step 5 (report and status).

## 2. Commands (last lines of output)
- Phase 0 anchors: `7` and `2`, as expected. Dependency check `ls go/internal/web/public | head -4` listed files.
- Venv: `App/.venv` was missing; created with pip install of requirements and requirements-dev (rc=0, not committed).
- Step 1 sha256sum: `App/scripts/public_pages_golden.py: OK`, `App/tests/test_go_public_pages.py: OK`.
- Step 2: `wrote go/internal/web/public/testdata/pages/cases.json`; then `29`.
- Step 3 `--check`: `rc=0`, no `stale:` line.
- Step 4 pytest: `1 passed in 1.61s`.
- Step 5 `python3 scripts/context_lint.py`: `context lint: OK`.
- `grep -l phc_golden_key ... | wc -l`: `5`.

## 3. Section 7
- [x] Steps 1, 2 and 5 listed by `git log --grep='^1620 step'`.
- [x] Step 2 stat lists `catalog_pages.json` and the 29 files of `testdata/pages`.
- [x] Step 1 `: OK` for 2 sidecar files (brief said 4 in §7; only 2 sidecars exist in §3); step 3 `rc=0`; step 4 `1 passed`.
- [x] PostHog key count is 5.

## 4. Deviations
- Brief §7 says `: OK` for 4 files; §3 lists 2 files. Checked the 2 listed.
- No `go test -v` run (brief has none). SKIP count: 0 (not run).
- Added the venv (environment only).

## 5. Questions
None.

## 6. Owner steps left
None.
