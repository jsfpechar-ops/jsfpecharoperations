# 2066 report (continuation: steps 4-6)

Status: review

## Commits

- `79c2777` 2066 step 4: lead-in lowered/restored change runs submit then completion hooks.
- `aa17f8c` 2066 step 5: DB tests for the lead-in hooks.
- Step 6: no stale "still Python-only (accepted diff)" anchor left in `go/internal/web/stays/edit_posts.go`; nothing to remove.

## Call sites

- `go/internal/web/guest/party.go` `leadCountHandler`: on `codeLowered` or `codeRestored` only, calls `d.afterLeadChange` which runs `guestFormSubmitStayIfComplete` (errors logged) then `runCompletion` (OnRegistrationComplete, then MaybeNotifyCompletion force=false).
- `RegisterParty` takes `hooks CompletionHooks`; `go/cmd/ubyhost-web/register_web_guest_party.go` passes `completionHooks(pool)`. Two test call sites pass `nil`.

## Tests

- `go/internal/web/guest/party_lead_hooks_test.go` (new): lowered then restored run the hook pair in order; unchanged and feature-off run nothing; nil hooks do not panic.
- `go build ./...`: pass.
- `go test ./internal/web/guest/... ./internal/web/stays/... ./cmd/ubyhost-web/... -count=1` with `UBYHOST_TEST_DATABASE_URL` on 127.0.0.1:5433/guest_test: all three `ok`.
- Skips: 6, all pre-existing (signed-out redirect parity tests needing a pool, and env-gated probes). None added by this brief.

## Deviations

- Host-side `HEADCOUNT_LEAD_LIVE` on/off hook tests (step 5) are not written. The host hook in `edit_posts.go` is inline in the handler closure, so it cannot be called directly. A test needs either an HTTP harness or extracting a helper. Owner decision needed.
- Lead-in submit is not asserted by a submission row or fake. `guestFormSubmitStayIfComplete` enqueues only when registration is complete and automation is immediate. The test only checks the hook pair.
- Lead-in tests call `changeByLead` and then the same branch, not the HTTP handler.

## Finding

- Python `change_by_lead_in` writes `reservation_headcount_lowered` / `reservation_headcount_restored` audit rows. The Go `changeByLead` path writes none. Recorded only, not fixed.
