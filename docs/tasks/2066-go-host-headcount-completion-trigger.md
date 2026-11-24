# 2066: Go host headcount correction and lead-in run the completion trigger

Status: todo
Depends on: 2065 (reuse its `CompletionHooks` shape and `completionHooks(pool)` adapter) | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls (stop at 25; commit after every step: `2066 step k`)
Executor trailers (every commit):
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf`

## 1. Objective

The two remaining Python sites that run `submit_stay_if_complete`, `on_registration_complete`, `maybe_notify_completion` after a lower headcount get the same calls in Go, and the stale "still Python-only (accepted diff)" comment goes.

## 2. Context (verified)

- Host: `App/app/routes/admin.py:4258-4266`: after `reporting.submit_stay_if_complete`, only `if config.HEADCOUNT_LEAD_LIVE:` run `door_codes.on_registration_complete`, re-read reservation and apartment, and if both exist `claim.maybe_notify_completion(fresh, apartment)` (force false). Go: `go/internal/web/stays/edit_posts.go` ~376-383: `editSubmitStayIfComplete` then an empty `if headcountLeadLive(c.getenv) { // door_codes.on_registration_complete and claim.maybe_notify_completion are still Python-only (accepted diff). }`. `RegisterEditPosts(mux,pool,getenv,now,wrap)` builds `postDeps{pool,getenv,now}` (positional literal at line 45).
- Lead-in (guest side): `App/app/headcount.py:253-259` `change_by_lead_in`: after the `reservation_headcount_lowered/restored` audit (only when code is LOWERED or RESTORED): `submit_stay_if_complete`, `on_registration_complete`, then re-read both rows and `maybe_notify_completion`. Go: `go/internal/web/guest/party.go` `changeByLead` (~281) updates `declared_guests` and commits but does NOT audit or submit (grep: no submit in party.go). Its handler is `leadCountHandler` (~525). Step 4 below adds only the three calls; if the audit rows `reservation_headcount_lowered`/`_restored` are also missing, record that as a finding in the report and do not add them here.
- Same errors rule as 2065: log and continue, never fail the response.

## 3. Files

| Path | Action |
|---|---|
| `go/internal/web/stays/edit_posts.go` | edit |
| `go/internal/web/stays/completion.go` | new: interface (same two methods as `guest.CompletionHooks`) |
| `go/internal/web/guest/party.go` | edit |
| `go/cmd/ubyhost-web/register_web_stays_edit_posts.go`, `register_web_guest_party.go` (find with `grep -rln 'RegisterEditPosts(\|RegisterParty' go/cmd`) | edit: pass `completionHooks(pool)` |
| `go/internal/web/stays/edit_posts_completion_test.go`, `go/internal/web/guest/party_completion_test.go` | new: DB tests |
| `docs/tasks/2066-report.md` | report |

## 4. Steps

1. Anchors: `grep -nF 'are still Python-only (accepted diff)' go/internal/web/stays/edit_posts.go`; `grep -nF 'editSubmitStayIfComplete(ctx, c.pool, c.getenv, d.now, st.apartmentID, id)' go/internal/web/stays/edit_posts.go`; `grep -nF 'func (d partyDeps) changeByLead' go/internal/web/guest/party.go`; `grep -n 'completionHooks' go/cmd/ubyhost-web/*.go | head -3` (must exist from 2065). Missing: STOP.
2. Host: add `completion.go` in package stays with the same interface; add a `hooks` field to `postDeps` (it is built positionally: change it to a keyed literal and update every `postDeps{` use, `grep -n 'postDeps{' go/internal/web/stays/*.go`) and a trailing `hooks` parameter to `RegisterEditPosts`. Replace the empty `if headcountLeadLive(...) { // ... }` body with: `d.hooks.OnRegistrationComplete(ctx, id)` then `d.hooks.MaybeNotifyCompletion(ctx, id, st.apartmentID, false)` (log an error, continue), guarded by `d.hooks != nil`. Delete the stale comment. Commit `2066 step 2`.
3. Wire `completionHooks(pool)` into the cmd registrations. Commit `2066 step 3`.
4. Lead-in: in `changeByLead`'s caller path (after the commit returns `codeSaved`, which here is both lowered and restored; check how the function distinguishes `codeUnchanged` and return only on a real change) call `formPagesSubmitStayIfComplete`-equivalent already used in package guest (`guestFormSubmitStayIfComplete`) with the stay's apartment id, then `runCompletion` from 2065 (`completion.go` in package guest). Add `hooks CompletionHooks` to `partyDeps` and to its Register function. Commit `2066 step 4`.
5. Tests (DB, fixtures from `party_test.go`, `party_claim_start_test.go`, and `internal/doorcodes/wire/confirmations_test.go`): host correction that makes the stay complete on a claimed stay without door codes -> one `completion:<res>:<n>` outbox row, on a ttlock apartment `OnRegistrationComplete` called before notify; lead-in lowering likewise; `HEADCOUNT_LEAD_LIVE` off on the host path -> no hook call; a change that leaves the stay incomplete -> no outbox row; unchanged count -> no hook call. Commit `2066 step 5`.
6. Report, `Status: review`, one draft PR.

## 5. Do not touch

`App/**`, doorcodes/wire logic, the 2065 guest-save files, templates, migrations.

## 6. Commands

Postgres check as in 2065 section 6. From `go/`: `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./internal/web/stays/ ./internal/web/guest/ -run 'Completion|Party|EditPosts|Headcount' -count=1 2>&1 | tail -30`, `go build ./cmd/ubyhost-web/ 2>&1 | tail -30`, `go vet ./internal/web/stays/ ./internal/web/guest/ 2>&1 | tail -30`, then `python3 scripts/context_lint.py 2>&1 | tail -3` from the root.

## 7. Acceptance

- [ ] `grep -rn 'accepted diff' go/internal/web/stays/edit_posts.go` finds nothing.
- [ ] Host and lead-in tests pass, 0 skipped; same order and `force=false` as Python.
- [ ] Missing lowered/restored audit rows (if any) are listed in the report, not fixed.

## 8. Stop conditions

An anchor is missing; 2065 is not merged; `changeByLead` cannot tell a real change from unchanged; a test fails twice.

## 9. Report

`docs/tasks/2066-report.md` (max 600 tokens). Owner steps: none.
