# 2076: Clean up a removed guest and reassess filing

Status: todo
Depends on: 2075 | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2076-go-guest-removal-cleanup
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Delete the removed guest's passport photo, record the workspace owner on the audit row and check whether the remaining stay can file immediately.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/routes/guest.py:2265`

  ```text
  passport_photos.delete_photo(guest_id)
  ```
- `go/internal/web/guest/form_pages.go:942`

  ```text
  func formPagesDeletePhoto(ctx context.Context, pool *pgxpool.Pool, guestID int64) error { return nil }
  ```
- `go/internal/web/guest/form_pages.go:944`

  ```text
  func formPagesSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, aptID, resID int64) error {
  ```
- `go/internal/passportphotos/save.go:74`

  ```text
  func DeletePhoto(dataDir string, guestID int64) error {
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/web/guest/form_pages.go` | edit | Real cleanup, correct owner, shared completion filing. |
| `go/internal/web/guest/form_pages_test.go` | edit | Prove post-removal effects and unchanged refusals. |

The executor report and brief status follow section 9.

## 4. Steps

1. Replace `formPagesDeletePhoto` with `passportphotos.DeletePhoto` using the same effective `UBYHOST_DATA_DIR` as host photo access. Call only after the existing authorized DELETE succeeds. Missing photo is a success. Use safe diagnostics for I/O errors and keep the orphan sweeper available.
2. In the `guest_removed_by_guest` audit INSERT replace `apt.ID` in the `owner_user_id` argument with `apt.OwnerUserID`. Replace the `formPagesSubmitStayIfComplete` no-op with the 2075 helper after deletion and linked-child cleanup. Preserve the owned-cookie update, guest redirect and language.
3. Add `TestGuestRemovalCleanup` with different workspace/apartment IDs, a synthetic encrypted file and recording filing dependency. Verify allowed deletion, missing file, and refusal for another stay, a restricted or filed guest and an active filing lease. Assert refusal has no side effects. Run section 6.

## 5. Do not touch

Preserve route, cookie, lease checks, 2073 signer semantics and photo-retention fallback. Use no real guest files or live filing.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/web/guest/ -run 'GuestRemovalCleanup|FormPages' -count=1 -v 2>&1 | tail -30
```

For each changed guest-facing response, include a 390 px screenshot from the Go flow with synthetic data. For host page changes apply the 390/768/1280 host UX gate and report what you saw at each width.

## 7. Acceptance

- [ ] An eligible removal cleans the correct file, records the owner and requests a filing check on the same stay.
- [ ] The existing removal guards reject out-of-scope requests before side effects.
- [ ] The 390 px confirmation and checks are in the report.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2076-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/web/guest/form_pages.go`

## Owner steps

1. Open after 2075.
2. Review the phone screenshot and removal evidence.
