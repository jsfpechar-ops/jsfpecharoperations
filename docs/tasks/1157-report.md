# 1157 report

Status: blocked

## 1. Diff stat
See git diff --stat bccafce..HEAD (commits 1157 step 1 to step 5).

## 2. Commands
- Step 1 golden script run: wrote go/internal/calendar/testdata/dsr_due_golden.json; sha256 of script and JSON match the brief.
- Step 2: gofmt empty, go vet clean; dsr_due.go sha256 matches.
- Step 3: gofmt empty, go vet clean, go test ./internal/calendar/ -count=1 ok (DB test skipped locally, no UBYHOST_TEST_DATABASE_URL).
- Step 4: .venv/bin/python -m pytest tests/test_dsr_due_golden.py tests/test_dsr_audit.py -q: 2 passed.
- Step 5: python3 scripts/context_lint.py: FAIL, "ERROR docs/context/test-map.md: ~1206 tokens > cap 1200". status.md now passes.

## 3. Section 7
- [x] sha256 values for steps 1-4 match.
- [x] gofmt, go vet, go test ./internal/calendar/ ok.
- [ ] Step 6 local PostgreSQL: not run (stopped at the tool-call limit).
- [x] pytest files pass. Freshness check not run.
- [ ] context_lint passes: FAIL (see below).
- [ ] Commits 1157 step 1 to step 6: steps 1 to 5 done.

## 4. Deviations
Done: steps 0 to 5. Left: step 6 (optional DB test), the freshness command, and the report commit.
Step 0 had a missing App/.venv, so I created it per step 0.
Blocker: context_lint fails on docs/context/test-map.md (~1206 > 1200). The step 5 edit added the test file name (about 6 tokens). I did not check whether the file was already over the cap before the edit. Fix needs compacting test-map.md, which the brief does not allow.

## 5. Questions
Should test-map.md be compacted (in this PR or a separate one) before lint can pass?

## 6. Owner steps left
None until the lint blocker is resolved. Nothing is wired; brief E adds the job kind.
