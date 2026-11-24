# 2065 report

Status: blocked. Steps 1-5 done; step 6 partial (adapter unit tests only, no DB handler tests).

## Files
- go/internal/web/guest/completion.go (new): CompletionHooks interface, runCompletion helper.
- go/internal/web/guest/form_save.go: RegisterFormSave takes hooks; runCompletion after guestFormSubmitStayIfComplete on the main save path (savedID==0 branch untouched); redirect now matches Python (next guest, stay link, &saved=1, #fee-pay).
- go/cmd/ubyhost-web/completion_hooks.go (new): lazy adapter `completionHooks(pool)`, sync.Once build of the door-code service; fallback viewer `noDoorCodes` when the wiring cannot be built.
- go/cmd/ubyhost-web/register_web_guest_form_save.go: passes `completionHooks(pool)` instead of nil.
- go/cmd/ubyhost-web/completion_hooks_test.go (new): nil-pool no-panic test; noDoorCodes reports "without".
- go/internal/web/guest/form_save_test.go: extra nil arg only.

## Per step
- Step 1 anchors: found, no commit.
- Step 2 done (3cb139a). Step 3 done (6d6e5ca). Step 4 done (8f0c7cc).
- Step 5 done (aaf2fd7). Callers now pass the adapter.
- Step 6 partial (7926739): only the two unit tests above. NOT done: DB-backed handler tests (claimed stay with email on no-door-code apartment, exactly one outbox row on last save, none on non-last, dedupe on second save), hook-order test, redirect-shape tests, 390 px screenshots (not applicable, no template change).

## Commands (last lines)
- go build ./... : clean.
- go vet ./cmd/ubyhost-web/ : clean.
- go test ./internal/web/guest/... ./internal/doorcodes/... ./cmd/ubyhost-web/... -count=1 (UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test): all ok.
- SKIP count for the new cmd tests: 0.

## Deviations
- Step 6 DB handler tests not written. A complete guest row needs the full validation.GuestIsComplete field set plus expected_guests fixtures; the executor ran out of budget before mapping them. Existing wire tests (`TestMaybeNotifyCompletionSendsOnce`, `TestMaybeNotifyCompletionGuards`) already cover LiveConfirmations with a no-code viewer at the DB level.
- Owner decision needed: if the door-code wiring fails to build while UBYHOST_DOOR_CODES is on, the fallback sends the receipt WITHOUT a code even for apartments that do have door codes. The brief asked for the no-code viewer; a safer alternative is to hold receipts for apartments with door codes in that case.
- Postgres was down; sourcing parity_env.sh was refused by the sandbox, so I ran its pg_ctl start line directly.
- Fee panel cash default passed as "" (only affects a note, not rail presence).

## Owner steps
None yet. Step 6 DB tests must land before this PR can merge; decide the fallback door-code behaviour above.
