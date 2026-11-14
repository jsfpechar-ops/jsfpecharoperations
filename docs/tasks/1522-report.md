# 1522 report

Status: review
Mode: one big PR (commits on go-wave3, no push, no PR).

## Files changed (`1522 step 3` commit)
- go/internal/web/properties/entities.go (new, 621 lines)
- go/internal/web/properties/entities_test.go (new, 321 lines)
- go/cmd/ubyhost-web/register_web_properties_entities.go (new, 20 lines)
- go/internal/web/properties/i18n_keys.txt (appended 9 lines)
- go/internal/web/properties/i18n.json (regenerated, 21 lines)

## Commands
- sha256sum -c (3 sidecar files): OK, OK, OK
- i18n.json sha256: 6c71ed7c4bfbd28d1e3b25f48985d8ac7586df9c2b1f44a948210c2e52fd5756 (matches)
- gofmt, go build ./..., go vet: clean (no output)
- go test -count=1 -v ./internal/web/properties/ ./cmd/ubyhost-web/: ok, ok; 54 PASS, 0 FAIL, SKIP lines: 0
  - named tests PASS: TestNormaliseAccount, TestInvoiceDetailPayload, TestWithCountryCode, TestDrawnSignature, TestEntitySave, TestEntitySignature, TestEntityUpdate
- python3 scripts/context_lint.py: context lint: OK

## Acceptance (section 7)
- [x] Step 2: 3 OK; step 3: sha256 matches
- [x] gofmt, vet, build clean; tests pass
- [x] Only section 3 paths touched (plus the Status line and this report)

## Deviations
- Step 3 was first committed before the catalog was regenerated (python3 lacked fastapi). Created App/.venv, regenerated, and amended the local step 3 commit (unpushed) so it holds the final i18n.json.
- PostgreSQL 16 started on port 5625 (data /var/tmp/pg5625, database ubyhost_test) as user postgres. Stop it and delete /var/tmp/pg5625 when done.

## Questions
- None.

## Owner steps left
- Do not add /entities to UBYHOST_GO_PATHS until briefs 1523, 1524, 1525 are done (see brief section 2).
- Ship 1522 and 1523 in the same deploy.
