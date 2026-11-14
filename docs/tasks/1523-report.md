# 1523 report: Go business editor and Fill from register

Status: review. One big PR mode: commits `1523 step 1`, `1523 step 3`, `1523 step 4` on the local branch `go-wave3`; no push, no PR.

## Files changed (git show --stat)
- step 1: `go/internal/web/properties/{ares.go, entity_editor.go, entity_editor_test.go, bank_codes.csv, templates/entity_editor.tmpl}` (new)
- step 3: `lists.go`, `lists_test.go`, `templates/lists.tmpl`, `testdata/lists_cases.json` (patch, 4 files, +20 -69)
- step 4: `i18n_keys.txt` (+49), `i18n.json` (+140, sha256 a5079e6b0856bc96d09d4fa39e1159a97e2838dbb45fe507707fc5e88f21afa6, matches brief)

## Commands
- sha256 checks (step 2): 6 of 6 OK.
- `git apply --check` and `git apply` of lists.patch.txt: OK, 4 files changed.
- gofmt, `go build ./...`, `go vet`: clean.
- `go test -count=1 -v ./internal/web/properties/ ./cmd/ubyhost-web/`: both `ok`, 0 FAIL, 0 SKIP (UBYHOST_TEST_DATABASE_URL pointed at a disposable PostgreSQL 16 on port 5628, stopped and removed afterwards). Named tests PASS: TestMapAres, TestAresLookup, TestRegisterLookupLimit, TestBankAndPhoneParts, TestEntityEditorPage, TestFillFromRegister, TestListsMatchPython.
- `python3 scripts/context_lint.py`: context lint OK.

## Deviations
- App/.venv was missing; created it before step 4 with the brief's default command (not committed).
- Step 4 commit message is `1523 step 4: editor, ARES, catalog` (brief text). Step 1 and step 3 were committed separately per One big PR mode.
- The Status line is set to `review`.

## Owner steps left
- Screenshots of `/entities?edit=<id>` at 390/768/1280 px after staging (reviewer, rule 10).
- Confirm the container reaches `ares.gov.cz`.
