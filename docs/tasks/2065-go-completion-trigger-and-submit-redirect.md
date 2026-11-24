# 2065: Go guest save runs the completion trigger and redirects like Python

Status: todo
Depends on: none | Runs before: 2066 | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls (stop at 25; commit after every step: `2065 step k`)
Executor trailers (every commit):
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf`

## 1. Objective

After the all-Go deploy, saving the last guest must (a) issue the door code now and (b) send the completion receipt (with the stay fee), as Python does. Today Go never calls `doorcodes.Service.OnRegistrationComplete` or `LiveConfirmations.MaybeNotifyCompletion` outside the door-code tick, so apartments without door codes get no receipt and door-code apartments get it a tick late. Also make the guest-save redirect equal Python's (`saved=1`, `#fee-pay`, next-guest rule).

## 2. Context (verified)

Python call sites of the pair (all in-process, same order: `submit_stay_if_complete`, then `door_codes.on_registration_complete`, then `claim.maybe_notify_completion`, always `force=False`):

| Site | Condition |
|---|---|
| `App/app/routes/guest.py:2731-2738` guest form save | always, after the `guest_form_saved` audit, for new and edited guests |
| `App/app/headcount.py:253-259` `change_by_lead_in` | only when code is LOWERED or RESTORED (brief 2066) |
| `App/app/routes/admin.py:4258-4266` host "headcount corrected" | only when `config.HEADCOUNT_LEAD_LIVE` (brief 2066) |
| `App/app/door_codes.py:344` `_release_confirmation` | tick, `force` passed through (Go already has it) |

Errors: `on_registration_complete` catches and logs (`door_codes.py:1698`); `maybe_notify_completion` returns early on its own guards (not claimed, already notified, incomplete, no email, `hold` mode without force). Neither fails the save. `maybe_notify_completion` only sends for a CLAIMED stay with a claim e-mail, so DB tests must seed `reservation_claim` (state `claimed`, email set).

Go today: `go/internal/web/guest/form_save.go` ~156-190 (`handleGuestFormSave`) calls only `guestFormSubmitStayIfComplete` and redirects to `GuestLink(token,resID,LangQuery(lang,""))`, or `/new` for every new guest. `RegisterFormSave(mux,pool,getenv,now,wrap)` (form_save.go:33) builds `saveDeps{pool,getenv,now}`. Go methods: `(*doorcodes.Service).OnRegistrationComplete(ctx,resID)` (reconcile.go:372, logs, never returns an error) and `doorwire.LiveConfirmations.MaybeNotifyCompletion(ctx,resID,aptID,force) error` (wire/confirmations.go:78). The full service (Mailer, Billing, Confirm) is built only in `newDoorCodesJob(pool)` (cmd/ubyhost-web/door_codes_wire.go:72, `job.rec.Svc`), lazily with `sync.Once` in `register_job_door_codes.go:41`. `stayDoorCodes(pool)` in register_web_staydetail.go builds a view-only Service: do not use it.

Python redirect (guest.py ~2757-2793): re-read the reservation, `missing = reservation_progress(fresh)["missing"]`; `continue_to_next = existing is None and missing is not None and missing > 0` -> `.../new`; otherwise the stay link; when not continuing and `missing == 0` and the fee-pay panel has rails -> fragment `#fee-pay`; query is `LangQuery(lang,"&saved=1")` style (`_lang_q(lang,"&saved=1")`: `?lang=x&saved=1` or `?saved=1`); status 303. Go's panel builder is in `go/internal/web/guest` (2063; `grep -n 'func.*[Ff]ee' go/internal/web/guest/stay_view.go go/internal/web/guest/*fee*.go`, template `templates/fee_pay.tmpl`), progress is `formPagesProgress` (form_pages.go:550).

## 3. Files

| Path | Action |
|---|---|
| `go/internal/web/guest/form_save.go` | edit: hooks field, calls, redirect |
| `go/internal/web/guest/completion.go` | new: `CompletionHooks` interface |
| `go/cmd/ubyhost-web/register_web_guest_form_save.go` | edit: pass the adapter |
| `go/cmd/ubyhost-web/completion_hooks.go` | new: lazy adapter |
| `go/internal/web/guest/form_save_completion_test.go` | new: DB tests |
| `docs/tasks/2065-report.md` | report |

## 4. Steps

1. Anchors: `grep -nF 'func RegisterFormSave' go/internal/web/guest/form_save.go`; `grep -nF 'guestFormSubmitStayIfComplete(ctx, d.pool, d.getenv, d.now, res.apartmentID, resID)' go/internal/web/guest/form_save.go` (two hits: the savedID==0 branch and the main path); `grep -nF 'newDoorCodesJob(pool)' go/cmd/ubyhost-web/register_job_door_codes.go`; `grep -n 'Doors' go/internal/doorcodes/wire/confirmations.go | head`. Missing: STOP.
2. New `completion.go` in package guest:
```go
// CompletionHooks is door_codes.on_registration_complete then claim.maybe_notify_completion (force=false).
// Nil means off (tests). Errors are logged by the adapter, never raised: the save must not fail.
type CompletionHooks interface {
	OnRegistrationComplete(ctx context.Context, reservationID int64)
	MaybeNotifyCompletion(ctx context.Context, reservationID, apartmentID int64, force bool) error
}
```
Add a helper `func runCompletion(ctx, h CompletionHooks, aptID, resID int64)` that returns when `h == nil`, else calls `h.OnRegistrationComplete(ctx,resID)` then `h.MaybeNotifyCompletion(ctx,resID,aptID,false)` and on error `slog.Error("completion notify failed","reservation",resID,"error",err)`. Commit `2065 step 2`.
3. `form_save.go`: add `hooks CompletionHooks` to `saveDeps`; change `RegisterFormSave` to take `hooks CompletionHooks` as its last parameter. After the main-path `guestFormSubmitStayIfComplete(...)` (the one after `auditGuestFormSaved`) add `runCompletion(ctx, d.hooks, res.apartmentID, resID)`. In the `savedID == 0` (duplicate) branch call it too ONLY IF Python's equivalent does: Python has no such branch, so leave that branch unchanged. Commit `2065 step 3`.
4. Redirect: replace the `loc` block (after `rememberOwnedGuestIDs`) with: read progress via `formPagesProgress` for a fresh reservation row (reuse the loader `form_pages.go` uses for `formResRow`; grep `formResRow` to find it) -> `missing`; `continueNext := existing == nil && missing != nil && *missing > 0`; `loc = GuestLink(token,resID,"")`, `/new` appended when `continueNext`; query `LangQuery(lang,"&saved=1")` exactly as Python's `_lang_q` shape (check `LangQuery`'s contract with `grep -n 'func LangQuery' -A12 go/internal/web/guest/*.go`; if it cannot take the `&saved=1` form, STOP and ask); fragment `#fee-pay` only when `!continueNext && missing == 0` and the existing fee panel builder returns rails. Keep `WithLang` and 303. Commit `2065 step 4`.
5. Adapter in `cmd/ubyhost-web/completion_hooks.go`: `func completionHooks(pool *pgxpool.Pool) guest.CompletionHooks` returning a struct that builds the job once via the same `sync.Once` pattern as `register_job_door_codes.go:41` (reuse the shared once/variable if it is package-level; otherwise a second `newDoorCodesJob(pool)` is acceptable since it only builds structs). `OnRegistrationComplete` -> `job.rec.Svc.OnRegistrationComplete`; `MaybeNotifyCompletion` -> `job.rec.Svc.Confirm.MaybeNotifyCompletion`. If the job fails to build (no TTLock/mail env), log once and make both methods no-ops; if `wire/confirmations.go` shows `Doors` may be nil, additionally build a bare `doorwire.LiveConfirmations{Pool,Mailer,Billing,Doors:nil}` so the receipt still goes for apartments without door codes; if `Doors` nil would panic, STOP and report. No package-level mutable globals beyond the once. Pass `completionHooks(pool)` in `register_web_guest_form_save.go`. Fix any other caller of `RegisterFormSave` (`grep -rn 'RegisterFormSave(' go | head`). Commit `2065 step 5`.
6. Tests in `form_save_completion_test.go`. Use the DB fixtures of `shell_test.go` (~152) and `form_save_test.go`; hooks are a recording fake plus one test with real `doorwire.LiveConfirmations` over the pool (as `wire/confirmations_test.go` `newConfirmations` does). Cases: (a) last guest on an apartment WITHOUT door codes, claimed stay with email: exactly one `email_outbox` row with key `completion:<res>:<filled>`; saving again changes nothing; (b) ttlock door-code apartment (Settings enabled): `OnRegistrationComplete` ran first (fake records order: on_registration_complete, then notify) and the receipt follows the hold rule (held when `hold` and not forced); (c) non-last guest: hooks run but `MaybeNotifyCompletion` sends nothing (no outbox row) and no new door_code row; (d) redirects: new guest with `missing>0` -> `.../new?saved=1`; last guest, no rails -> `?saved=1` without fragment; last guest with fee rails -> `?saved=1#fee-pay`; edit of an existing guest -> stay link `?saved=1`; with `lang=en` -> `?lang=en&saved=1`; (e) a hook that returns an error still yields 303. Commit `2065 step 6`.
7. Report (section 9), `Status: review`, one draft PR.

## 5. Do not touch

`App/**`, `go/internal/web/stays/**` and party/lead code (brief 2066), doorcodes/wire logic, templates, migrations.

## 6. Commands

Postgres first: `pg_isready -h 127.0.0.1 -p 5433 2>&1 | tail -3`. If down: `source scripts/e2e/parity_env.sh > /var/tmp/parity_env.log 2>&1` (never pipe a `source`), then `pg_isready` again.
From `go/`: `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./internal/web/guest/ -run 'Completion|FormSave' -count=1 2>&1 | tail -30`, then `go build ./cmd/ubyhost-web/ 2>&1 | tail -30` and `go vet ./internal/web/guest/ ./cmd/ubyhost-web/ 2>&1 | tail -30`, then `go test ./internal/doorcodes/... -count=1 2>&1 | tail -30`, then from the repo root `python3 scripts/context_lint.py 2>&1 | tail -3`. 0 skipped for the DB tests (`-v 2>&1 | grep -c SKIP` must be 0 for the new file).

## 7. Acceptance

- [ ] Hooks run after submit, in Python's order, `force=false`, errors logged not raised.
- [ ] Case (a)-(e) tests pass, 0 skipped.
- [ ] Redirect equals Python for all five shapes.
- [ ] No new global state, no new dependency, no template change.

## 8. Stop and ask

An anchor is missing; `LangQuery` cannot express `&saved=1`; `LiveConfirmations` panics with nil `Doors`; Postgres cannot start; a test fails twice.

## 9. Report

`docs/tasks/2065-report.md` (max 600 tokens): files, command tails, section 7 ticked, deviations, questions. Owner steps: none (PR merges via `scripts/merge-pr-on-green.sh`).
