# 2071 report

Status: review

Branch: claude/nice-hawking-fw98ct (worktree agent-acb44b3ebb01287d6). Not pushed.

## Commits

- `99911e1` step 1: notice and party-size checks on new guest save.
- `b583e18` step 1 fix: notice and party-size text now from the guest i18n catalogue (`error_party_size`, `legal_ack_missing`, all six languages), not English copies.
- `c3b6798` step 2: `applyDeclared` body moved into `applyDeclaredTx(ctx, tx, resID, count)`; the wrapper keeps the same return codes and commits only on `codeSaved`.
- `3df784c` step 3: `insertGuestSaveRow` takes the party size, reads the reservation FOR UPDATE under the advisory lock, applies the count only when the fresh expected count is nil, then inserts the guest in the same transaction. Returns `guestInsert` (id, count code, old count, saved flag). The first-form audit (`reservation_declared_guests_set` or `_refused`) runs after commit in the caller.
- `0ecad6c` step 4: `TestGuestSaveNoticeAndHeadcount` (DB-backed, five subtests).

## Commands

- `go build ./...` (in `go/`): clean.
- `go vet ./internal/web/guest/`: clean.
- `go test ./internal/web/guest/ -run 'GuestSaveNoticeAndHeadcount|FormSave|Party' -count=1 -v`: all PASS, 0 skips.
- `go test ./internal/web/guest/... ./internal/web/stays/... -count=1`: `ok` for both packages.
- `go test -v` on the same packages: 3 SKIPs (`TestClaimOpsSignedOutRedirects`, `TestGuestEditSignedOutRedirects`, `TestGuestLifecycleSignedOutRedirects`). They skip because no pool is passed to hostweb.Login. These files were not touched in 2071.

## Section 7 acceptance

- Missing notice returns the translated 422: implemented (step 1). Not covered by a DB-backed HTTP test. The step 4 test calls `insertGuestSaveRow` directly.
- Count and guest share one transaction: done. Already-full group commits the count with no new guest, and the completion check runs (caller, when `countSaved`). Overrides are kept.
- Two concurrent final-slot saves: covered by the test. One guest is inserted and the count stays at 2.

## Deviations

- Full-group check uses the live guest count (`liveGuestRows`), not the Python `reservation_progress` filled count. The Go completeness predicate lives in unexported `calendar` code that takes a pool, not a transaction. Python filters by completeness. Worth a follow-up.
- No Go headcount audit helper existed. `auditHeadcountCount` writes the same audit action and detail as Python's `headcount.record`.
- Step 4 cases not covered: stale-count refusal, below-floor refusal, and the HTTP-level 422 for a missing notice.

## Owner steps left

- Review the 390 px form error in the browser (the translated notice and party-size text now come from the catalogue).
- Decide whether the full-group check should use the completeness predicate (see Deviations).
