# 2065 report (partial, executor stopped at tool cap)

Status: blocked. Steps 1-4 done, step 5 partial, step 6 not done.

## Files
- go/internal/web/guest/completion.go (new): CompletionHooks interface, runCompletion helper.
- go/internal/web/guest/form_save.go: RegisterFormSave takes hooks; runCompletion after guestFormSubmitStayIfComplete on the main save path (savedID==0 branch untouched); redirect now matches Python (next guest, stay link, &saved=1, #fee-pay).
- go/cmd/ubyhost-web/register_web_guest_form_save.go: passes nil hooks (NOT wired yet).
- go/internal/web/guest/form_save_test.go: extra nil arg only.

## Per step
- Step 1 anchors: found, no commit.
- Step 2 done (3cb139a). Step 3 done (6d6e5ca). Step 4 done (8f0c7cc).
- Step 5 NOT done: no completion_hooks.go adapter. Callers pass nil, so the receipt and door-code call are still NOT run from Go. Do not deploy as the fix.
- Step 6 NOT done: no receipt-without-door-codes test, no hook-order test, no redirect-shape tests.

## Commands (last lines)
- go build ./... : clean.
- go test ./internal/web/guest/... ./internal/doorcodes/... ./cmd/ubyhost-web/... -count=1 : all ok.
- FormSave -v SKIP count: 0.

## Deviations
- Postgres was down; sourcing parity_env.sh was refused by the sandbox, so I ran its pg_ctl start line directly.
- Fee panel cash default passed as "" (only affects a note, not rail presence).
- Tool cap reached before steps 5-6.

## Owner steps
None yet. Next executor needs brief steps 5-6 before this PR can merge.
