# 2065 report

Status: review. Steps 1-6 done. Step 6 DB tests added (commit 1c01b6f). Fallback fixed (7f57955): a ttlock apartment is HELD when the door-code wiring fails, so the receipt is never sent without its code.

## Files
- go/internal/web/guest/completion.go (new): CompletionHooks interface, runCompletion helper.
- go/internal/web/guest/form_save.go: RegisterFormSave takes hooks; runCompletion after guestFormSubmitStayIfComplete on the main save path (savedID==0 branch untouched); redirect now matches Python (next guest, stay link, &saved=1, #fee-pay).
- go/cmd/ubyhost-web/completion_hooks.go (new): lazy adapter `completionHooks(pool)`, sync.Once build of the door-code service; fallback viewer `noDoorCodes` when the wiring cannot be built.
- go/cmd/ubyhost-web/register_web_guest_form_save.go: passes `completionHooks(pool)` instead of nil.
- go/cmd/ubyhost-web/completion_hooks_test.go (new): nil-pool no-panic test; noDoorCodes hold/without tests.
- go/cmd/ubyhost-web/completion_hooks_db_test.go (new): DB-backed receipt tests (4 cases below).
- go/internal/web/guest/form_save_test.go: extra nil arg only.

## Step 6 cases (UBYHOST_TEST_DATABASE_URL=.../guest_test, real hooks)
1. All declared guests complete: one `email_outbox` row (kind completion). Repeat save: still one. PASS.
2. One of two declared guests complete: zero rows. PASS.
3. Ttlock apartment with noDoorCodes fallback: zero rows (held). PASS.

Run: `go build ./...` clean. `go test ./internal/web/guest/... ./internal/doorcodes/... ./cmd/ubyhost-web/... -count=1` ok in all packages. 3 SKIPs: `TestJobProbe`, `TestJobRunProbe`, `TestRouteProbe` (env-gated, pre-existing). 0 new skips.

## Deviations
- Case 1 drain: the receipt row is queued, then `mail.Drain` stops at the `{{receipt_details}}` block with `ErrNoDetailsRenderer`. No send-time renderer is wired in Go yet (brief 1231b). The test tolerates that one error and checks the row count. Open finding: fee-enabled receipts stay queued until the renderer lands.
- The test calls the two hooks directly (OnRegistrationComplete, then MaybeNotifyCompletion force=false), the same order as `runCompletion`, because `runCompletion` is unexported in package guest. No HTTP form POST.
- The fallback case builds the adapter's fallback branch directly (a `sync.Once` pre-run in the test) because the real wiring builds successfully here.

## Owner steps
- Decide whether the fee-enabled receipt may stay queued until the receipt-details renderer (brief 1231b) lands.
- Decide the fallback door-code behaviour (ttlock held when wiring fails; see 7f57955).
