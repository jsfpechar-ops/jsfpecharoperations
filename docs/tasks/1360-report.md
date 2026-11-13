# 1360 report (executor: Haiku 5.5)

Status: review
Start commit: 716c44139067b7c0c293de71cdc1ea08619a1337

## Files changed (git diff --stat 716c441)

- App/scripts/admin_customers_golden.py (new, 448 lines, sha256 00818e57... ok)
- App/tests/test_admin_customers_golden.py (new, 25 lines, sha256 ff4f93cf... ok)
- go/internal/web/customers/testdata/admin_customers_golden.json (new, generated, 2049 lines, sha256 d41b62be... ok)
- docs/tasks/1360-go-customer-admin-data.md (Status line only)
- docs/tasks/1360-report.md (this file)

## Commands

1. `.venv/bin/python scripts/admin_customers_golden.py` (run from App/): last line `wrote .../go/internal/web/customers/testdata/admin_customers_golden.json`; sha256 d41b62be79cd0a1bf2e0fe09c4612c4a19cb5dd6bccc36e8c46d20475900371b. Re-run: same sha256.
2. `git status --short`: empty after re-run (no modified file).
3. `.venv/bin/python -m pytest tests/test_admin_customers_golden.py -q --tb=short`: `1 passed in 2.27s`.
4. `python3 scripts/context_lint.py` (repo root): WARN lines about open briefs 0784/0851 and status.md not updated after App/ commits (not caused by this task); last lines `next free: task 1364 | migration 0046`, `context lint: OK`.

## Section 7 acceptance

- [x] The 3 files exist with the §4 sha256 values.
- [x] Golden re-run leaves the JSON unchanged; test passes.
- [x] Context lint OK.
- [x] Diff lists only §3 paths.

## Deviations

None. Script and test were extracted from the brief's §4 fences with sed (byte-exact, sha256 checked before commit).

## Questions

None.

## Owner steps left

None for this brief. Next: brief 1362 on the same branch.
