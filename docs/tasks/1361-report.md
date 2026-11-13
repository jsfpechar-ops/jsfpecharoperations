# 1361 report

Status: review

## Files changed (`git diff --stat f40b2f5`, all §3 paths)
- App/scripts/go_customers_pages_golden.py (created, sha256 740061f3...c9a5e4, matches)
- App/tests/test_go_customers_pages_golden.py (created, sha256 2db4d1dd...a1b91, matches)
- go/internal/web/customers/pages_test.go (created, sha256 5a8f5f63...4b7a, matches)
- go/internal/web/customers/testdata/customers_pages_golden.json (generated, sha256 33b2b9d0...c7f2a, matches; second run unchanged)
- go/internal/web/customers/templates/i18n_keys.txt, templates/i18n.json, templates/admin_customers.tmpl, pages.go, query.go, go/cmd/ubyhost-web/register_web_customers.go (steps 2 to 4)
- docs/tasks/1361-go-customer-admin-pages.md (Status line only: todo to review)

## Commits
- step 2 `4294123`, step 3 `2bd0e77`, step 4 `adad256`
- step 5 `653ee0f`, step 6 `cc27c25`, step 7 (this report, brief Status) committed after this file

## Commands (last lines)
- Go gofmt, vet, `go test ./internal/web/customers/ ./cmd/ubyhost-web/`: `ok ... customers 4.073s`, `ok ... cmd/ubyhost-web 0.011s`
- SKIP count (`-v`, `grep -c SKIP`): `0`
- New tests (`-v -run`): `PASS` TestVisibleLines, TestPagesMatchPython, TestPagesNeedAdmin, TestStampMatchesUTCNow; `ok`
- `.venv/bin/python -m pytest tests/test_go_customers_pages_golden.py tests/test_go_host_i18n.py tests/test_admin_customers_golden.py -q`: `4 passed in 5.63s`
- `python3 scripts/context_lint.py`: `next free: task 1381 | migration 0046`, `context lint: OK` (WARN lines are pre-existing notices about other briefs and commits touching App/)

## §7 acceptance
- [x] Every §3 file has the sha256 in §4 (checked for step 5 and 6 files; generated JSON matches)
- [x] TestPagesMatchPython, TestVisibleLines, TestPagesNeedAdmin, TestStampMatchesUTCNow and older tests pass; SKIP count 0
- [x] Golden script run twice leaves JSON unchanged; pytest 4 passed; lint OK
- [x] `grep -c 'mux.Handle' go/cmd/ubyhost-web/register_web_customers.go` prints `3`
- [x] `git diff --stat f40b2f5` lists only §3 paths

## Deviations
Done: steps 1 to 7. Step 1 skipped (Postgres already up on 127.0.0.1:55436). Step 3 was committed before step 4 as the brief orders it. Patch written to the session scratchpad instead of /tmp.

## Questions
None.

## Owner steps left
None for this brief. Push and the draft PR are for the orchestrator (brief says PR after 1364). No UX gate run (no Go page routed; see brief risk list).
