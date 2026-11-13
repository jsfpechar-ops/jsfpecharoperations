# 1260 report

Status: review

## 1. Files changed (`git diff --stat a83df54..HEAD`)

All §3 files. Also present from the base branch: docs/tasks/1260-files/code.md, docs/tasks/1260-go-schema-migrate.md (Status line only), docs/tasks/1261-go-schema-deploy-switch.md. 19 files, +10578 / -2.

## 2. Commands (last 5 lines of output)

Step 2 (sha256, 13 files): 13 x `OK`.
Step 3 (fixtures): `wrote: go/internal/schema/expected_schema.json`, `wrote: .../testdata/goose_statements_golden.json`, `wrote: .../testdata/fingerprint_golden.json`; sha256: 3 x `OK`.
Step 4: `gofmt -l .` empty, `go vet ./...` clean.
`go test ./internal/schema ./cmd/ubyhost-web -count=1`:
```
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/schema	0.116s
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.009s
```
`go build ./cmd/ubyhost-web`: OK.
`pytest tests/test_go_schema_golden.py`: `4 passed in 0.85s`.
`pg_schema_golden.py --check`: `check exit 0`.
`pytest tests/test_go_schema_migrate.py` without a URL: `2 skipped` (expected).
`pytest tests/test_go_schema_migrate.py` with a disposable PostgreSQL 16 (127.0.0.1:55432): `2 passed in 3.25s`.
`ruff check ... --select E9,F63,F7,F82,F401,F841`: `All checks passed!`.
`python3 scripts/context_lint.py`: `context lint: OK`.

## 3. §7 acceptance

- [x] Step 2: 13 x OK; step 3: 3 x OK.
- [x] gofmt, go vet, go test ok.
- [x] golden 4 passed; --check exit 0; migrate test 2 passed on PostgreSQL 16.
- [x] diff --stat lists only §3 files (plus base-branch brief files).
- [ ] After push: CI. Not done; the executor does not push.

## 4. Deviations

- App/.venv did not exist; created with `python3 -m venv` and pip install of requirements.txt and requirements-dev.txt (not tracked).
- Parity test run on a local disposable PostgreSQL 16 cluster in /var/tmp (started as the postgres user, port 55432, stopped and deleted afterwards). Step 6 listed this as optional.
- While setting up the cluster I ran `chown -R postgres` on the scratchpad directory by mistake. Restored to root:root, mode 755. No other effect.
- No push and no PR: the task said stay on the branch and do not push.

## 5. Questions

None.

## 6. Owner steps left

1. Push the branch: `git push -u origin task/1260-go-schema-migrate`
2. Open a draft PR from that branch, then wait for CI (`go`, `test`, `test-postgres-full`). Check that the two `test_go_schema_migrate.py` tests pass, not skip, in `test-postgres-full`.
