# 1623 report: Go mail unsubscribe golden script (part 1)

Status: review

## 1. Files changed

- `App/scripts/public_unsubscribe_golden.py` (create, step 1, sha256 verified)
- `App/tests/test_go_public_unsubscribe.py` (create, step 1, sha256 verified)
- `go/internal/web/public/catalog_unsub.json` (generated, step 2)
- `go/internal/web/public/testdata/unsub/cases.json` and 21 `*.html` pages (generated, step 2)
- `docs/tasks/1623-go-public-unsubscribe-golden.md` (Status line only)
- `docs/tasks/1623-report.md` (this file)

Local only, not committed: `App/.venv` symlink to `/var/tmp/ubyvenv`.

## 2. Commands

- Phase 0 anchors: `grep -c` on the public_legal_golden.py anchors printed `7`; on mail_unsubscribe.py printed `2`. The venv log ended `done 0`.
- Step 1: `sha256sum -c` printed `OK` for both files.
- Step 2: `scripts/public_unsubscribe_golden.py` last lines: `wrote .../post-unknown-user.html`, `wrote .../post-forged-blocked.html`, `wrote .../cases.json`; `ls testdata/unsub | wc -l` printed `22`.
- Step 3: `public_unsubscribe_golden.py --check` printed no output (no `stale:` line), `rc=0`.
- Step 4: `.venv/bin/python -m pytest tests/test_go_public_unsubscribe.py -q -rs --tb=short -x` printed `1 passed in 4.97s`.
- Step 5: `grep -c '"name"' cases.json` printed `54` (at least 21); posthog grep over the HTML pages printed `0`; `python3 scripts/context_lint.py` printed `context lint: OK`, `lint_rc=0`.

## 3. Acceptance (section 7)

- [x] Commits `1623 step 1`, `1623 step 2` (and step 5 for the report).
- [x] Step 1: 2 files OK; step 2: 22; step 3: rc=0; step 4: 1 passed.
- [x] `"name"` count 54 >= 21.
- [x] PostHog count 0.

## 4. Deviations

- Step 1 copy: done per file with `cp` from the sidecar path instead of the brief's loop, which the worktree sandbox refused as a complex git-adjacent command. Same result, sha256 verified.
- Git commands were split into plain separate calls for the same sandbox guard.

## 5. Questions

None.

## 6. Owner steps left

None. Nothing here routes traffic.
