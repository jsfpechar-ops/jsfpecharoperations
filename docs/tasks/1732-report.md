# 1732 report: Go claim ops and filed-by-hand

Status: review

## Commits

- `1732 step 1` — copy sidecars (7 checksums OK)
- `1732 step 2` — `go_claim_ops_golden.py` rewrite of `claim_ops_golden.json`
- `1732 step 3` — `go/internal/web/stays/i18n_keys.txt` + `i18n.json` (flash keys for `claim_ops.go`; step 3 / parity with 1731)
- `1732 step 4` — route registration sidecar (`register_web_stays_claim_ops.go`, dormant)

## Commands (tail)

**gofmt -l .:** empty.

**go vet ./internal/web/... ./cmd/...:** silent.

**go test ./internal/web/stays/... ./cmd/ubyhost-web/...:** `stays` ok; `cmd/ubyhost-web` FAIL on `TestStayDetailRoutesRegistered` only (accepted, same as 1731).

**go test ./internal/web/... ./cmd/ubyhost-web/...:** additionally `settings` FAIL without `UBYHOST_TEST_DATABASE_URL` on this VM (pre-existing; CI has DB).

**pytest tests/test_go_claim_ops_golden.py:** `1 passed`.

**context_lint.py:** `context lint: OK`

**Host browser lint:** N/A — no host page templates in §3 (POST handlers only, dormant until 1737).

## Accepted differences

- **`TestStayDetailRoutesRegistered`:** `POST /reservations/7/filed-by-hand` now hits Go mux via `register_web_stays_claim_ops.go` `init()`; expectation fix deferred to brief **1737** (per 1731 pattern).
- **`TestClaimOpsSignedOutRedirects`:** skips without pool; signed-out cases covered in `claim_ops_golden.json` / `TestClaimOpsGoldenHTTP`.
- **DB parity:** `claim_ops_test` PG replay needs `UBYHOST_TEST_DATABASE_URL` (CI).

## Deviations

- **i18n:** Sidecars did not include catalog lines; step 3 added five keys to `go/internal/web/stays/i18n_keys.txt` and regenerated `i18n.json` via `go_host_i18n.py` (not listed in brief §3 file table; required for `TestEveryKeyTheCodeReadsIsInTheCatalog`).

## §7 acceptance

- [x] Sidecar checksums OK; golden freshness green
- [x] `TestClaimOpsGoldenHTTP`, `TestClaimOpsPostForm`, registration test green
- [x] No `UBYHOST_GO_PATHS` change
- [x] Commits `1732 step 1–4`
- [ ] Full `go test ./internal/web/...` green locally (settings DB; cmd staydetail test deferred to 1737)

## Screenshots

None (no host page changes).

## Owner steps

None.