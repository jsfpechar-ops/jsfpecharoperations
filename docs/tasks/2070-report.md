# 2070 report: guest write encryption

Status: review

## Changed paths

- `go/internal/secure/guest_write.go`: shared Python-equivalent mapping for protected guest fields; preserves unrelated values, clears legacy fields, and fails before writes on wrong types or encryption errors.
- `go/internal/web/stays/guest_edit.go`: host guest insert and compare-and-set update use the shared mapping; update query/encryption errors reach the host server-error path while no-row CAS remains a normal refusal.
- `go/internal/web/guest/form_save.go`: guest self-save uses the shared mapping, clearing touched legacy columns with ciphertext updates.
- `go/internal/web/stays/guest_edit_test.go`, `go/internal/web/guest/form_save_test.go`: synthetic isolated-database coverage for host and guest writes.

## Checks

- `go test ./internal/web/stays/ -run 'GuestWriteEncryption|GuestEdit' -count=1 -v`: 3 passed; 1 existing `TestGuestEditSignedOutRedirects` skip, unrelated to encryption. The new database test passed.
- `go test ./internal/web/guest/ -run 'GuestWriteEncryption|EncryptSaveFields|GuestSaveInsertCols' -count=1 -v`: 3 passed, 0 skipped.
- `git diff --check`: passed.

## Acceptance evidence

- Synthetic host and guest rows contain protected values in `_enc` columns and cleared legacy columns. Hydration returns new ciphertext values, explicit empty values clear, and fields omitted from edits keep their legacy fallback.
- Wrong-type encryption fails before a host or guest update. The guest fixture also verifies insert encryption and the `fee_host_reason` shared mapping.
- No sensitive test values are emitted in test failures. No UI or template changed.

## Owner steps

- Review this diff and the existing skipped signed-out redirect test separately. No deployment, push, PR, or live data was used.
