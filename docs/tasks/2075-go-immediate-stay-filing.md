# 2075: File the completed stay immediately

Status: todo
Depends on: 2074 | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2075-go-immediate-stay-filing
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Replace the general sweep requested from web writes with Python's immediate, stay-scoped filing. Use the Go filing engine to keep claims, outcomes and receipts consistent.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/reporting.py:1185`

  ```text
  mode="completion_immediate",
  ```
- `go/internal/web/guest/form_save.go:584`

  ```text
  func guestFormSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) error {
  ```
- `go/internal/web/stays/guest_edit.go:720`

  ```text
  func guestSubmitStayIfComplete(ctx context.Context, d guestEditDeps, apartmentID, reservationID int64) error {
  ```
- `go/internal/web/stays/edit_posts.go:191`

  ```text
  func editSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) error {
  ```
- `go/internal/web/staydetail/filing.go:19`

  ```text
  var enqueueJob = scheduler.Enqueue
  ```
- `go/internal/ubyport/sweep.go:316`

  ```text
  func SubmitForApartment(ctx context.Context, d SweepDeps, aptID int64, o CollectOptions, mode string) ([]BatchResult, error) {
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/ubyport/completion_submit.go` | add | Shared stay-scoped entry point. |
| `go/internal/web/guest/form_save.go` | edit | Use it for guest save and the existing lead-in adapter. |
| `go/internal/web/stays/guest_edit.go` | edit | Use it for existing host guest edit/create/lifecycle calls. |
| `go/internal/web/stays/edit_posts.go` | edit | Use it from existing stay/headcount hooks. |
| `go/internal/web/staydetail/filing.go` | edit | Replace global enqueue for the detail route. |
| `go/internal/web/staydetail/post_test.go` | edit | Adjust the injection point and confirm route behavior. |
| `go/internal/ubyport/completion_submit_test.go` | add | Test scope, gates, results and duplicate protection. |

The executor report and brief status follow section 9.

## 4. Steps

1. In the new `ubyport.SubmitCompletedStay` follow `App/app/reporting.py:1152–1197`. Check the apartment, refresh completion, require `immediate`, honor `ubyport_auth_failed:<apartment>` and confirm the active reservation belongs to that apartment. Read non-archived guest IDs for only that stay. Return before the collector when the ID list is empty, because that means apartment-wide scope.
2. Reuse `NewSweepDeps` and send through `SubmitForApartment` with `CollectOptions{OnlyGuestIDs: ids, IgnoreSchedule: &yes, Now: now}` and mode `completion_immediate`. Use the existing injected fake sender for tests. Preserve ordinary claims, idempotency, retry caps and outcome writes. Call outside the booking write transaction. On a returned filing exception raise the existing `submission_immediate` warning with safe diagnostics. A committed guest save must keep its existing success flow.
3. Replace the bodies of the four existing wrappers in the named web files. Preserve their signatures and the stay detail boolean contract. Leave 2065/2066 callback order and redirects intact. Update the `post_test.go` injection formerly using `enqueueJob` to use the scoped helper. Check the four paths have no direct global submit enqueue and run the web command in section 6.
4. Add `TestSubmitCompletedStay` with two stays in the same apartment and an injected fake sender. Cover incomplete/manual/paused stays, empty scope, a scoped success with receipt, a failed send and a concurrent or repeated call. Assert the other stay is untouched and the same accepted guest is never sent twice.

## 5. Do not touch

Keep Python, the SOAP builders, job scheduler, codebook, historic outcomes and receipt storage unchanged. Guest removal belongs to 2076. Use test senders only.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/ubyport/ -run 'SubmitCompletedStay|GoldenEnvelopes|PlanOutcome' -count=1 -v 2>&1 | tail -30
cd go && go test ./internal/web/guest/ ./internal/web/stays/ ./internal/web/staydetail/ -run 'Completion|FormSave|GuestEdit|EditPosts|SubmitStay|Update' -count=1 -v 2>&1 | tail -30
```

Use fixture credentials and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] Immediate-mode filing is stay-scoped and reuses the existing claims and outcome writes.
- [ ] Authentication pause and failure cause the expected behavior. Six XML fixtures pass unchanged.
- [ ] Existing completion hooks and the scheduled sweep pass focused checks.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2075-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/ubyport/completion_submit.go`, `go/internal/web/guest/form_save.go`, `go/internal/web/stays/guest_edit.go`, `go/internal/web/stays/edit_posts.go`, `go/internal/web/staydetail/filing.go`

## Owner steps

1. Open after 2074 is included.
2. Review the fake-sender scope and duplicate-protection evidence.
