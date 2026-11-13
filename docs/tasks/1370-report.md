# 1370 report: Go port of the privacy request POST handlers

Status: review

## 1. Diff stat (a83df54..HEAD)

12 files changed, 7888 insertions(+). Includes the brief and code file committed with the branch (docs/tasks/1370-go-privacy-requests.md, docs/tasks/1370a-go-privacy-requests-code.md). Also the 9 code files, golden JSON, and this report.

## 2. Commands

- Step 1 hashes: all 9 match §4 step 1.
- Step 2 golden hash: `caa2d1d1775ada5dabd6ea7bcbd1095cc682c4553b4e3ed73bb7bda57bf6ab1c` matches.
- Go (no DB URL): `ok` for `internal/web/privacy` and `cmd/ubyhost-web`.
- Go with `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55437/postgres`, `-v -run 'TestPrivacyRequestsGolden|TestListForOwnerDatabase'`: `--- PASS: TestPrivacyRequestsGolden (0.61s)`, `--- PASS: TestListForOwnerDatabase (0.45s)`, not skipped.
- pytest (3 files): `8 passed in 2.02s`.
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings are pre-existing).
- Golden freshness: no output from `git status --short go`.

## 3. Acceptance (§7)

All ticked. Commits: step 1 `3a55be9`, step 2 `d3d2696`, step 4 (this report) committed after.

## 4. Deviations

None.

## 5. Questions

None.

## 6. Owner steps

None. Routes are registered but off; do not add `/privacy-requests` to `UBYHOST_GO_PATHS` until brief 1371 is merged.
