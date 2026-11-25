# 2071: Require the guest notice and save the first party size

Status: todo
Depends on: 2066, 2070 | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2071-go-guest-ack-and-first-party-size
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Reject guest submissions with missing acknowledgement and restore the first form's party-size rules. Save the count and admit the guest under one reservation transaction.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/routes/guest.py:2480`

  ```text
  if not form.get("legal_ack"):
  ```
- `App/app/routes/guest.py:2659`

  ```text
  count_code, count_old = headcount.apply_declared_in(
  ```
- `go/internal/web/guest/form_save.go:321`

  ```text
  exp := headcount.Expected(res.overrideGuests, res.declaredGuests, res.reducedGuests)
  ```
- `go/internal/web/guest/party.go:176`

  ```text
  func (d partyDeps) applyDeclared(ctx context.Context, resID int64, count int) (string, error) {
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/web/guest/form_save.go` | edit | Check acknowledgement and validate and persist party size. |
| `go/internal/web/guest/party.go` | edit | Extract only the existing declared-count transaction body for reuse. |
| `go/internal/web/guest/form_save_test.go` | edit | Assert notice and transactional admission behavior. |

The executor report and brief status follow section 9.

## 4. Steps

1. Before localization and the existing 422 branch, append the existing localized `legal_ack_missing` issue on `legal_ack` when the posted value is empty. Parse the same `party_size` field as Python. For an insert with an unknown expected total, require the inclusive 1–60 range using `party_size`/`error_party_size`. Preserve the submitted value on the rerender. Keep notice fields populated only on a successfully validated write.
2. In `party.go` keep `applyDeclared` as the transaction-owning wrapper for its current caller. Move its existing locked read, rules and declared-count write into a transaction-taking helper so form save can call the same code within its transaction. Preserve the current return codes and audit the successful count outside the transaction once. Keep 2066's lead-in callbacks in their original location.
3. In `insertGuestSaveRow`, replace the preloaded expected-count decision immediately after the advisory lock. Load the target reservation in the locked transaction, confirm its active state and apartment, apply the declared count only if the fresh expected count is nil, then re-read its effective count. Compare the fresh expected count with Python's filled-guest progress, using the existing Go completeness predicate over active guests. Keep that admission check and INSERT in the transaction. If a first count is saved but the fresh group is already full, commit that count, add the first-form audit once, request the existing completion filing check, and return the existing no-slot redirect. This matches the explicit Python branch at `App/app/routes/guest.py:2692–2707`. Roll back database errors. Run the 2065 success hooks only after commit in the paths where Python runs them.
4. Add `TestGuestSaveNoticeAndHeadcount` with accepted and missing notice, an existing guest edit, input below/above range, valid first count, host override, stale count, count saved for an already full group, incomplete stored guest, and two concurrent final-slot saves. Assert the post-commit audit and no duplicate guest insertion. Run section 6.

## 5. Do not touch

Preserve booking dates, claim versions, the existing headcount feature toggle, 2065/2066 hook order, field names and the declaration route's response. Keep retired payments out of scope.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/web/guest/ -run 'GuestSaveNoticeAndHeadcount|FormSave|Party' -count=1 -v 2>&1 | tail -30
```

For each changed guest-facing response, include a 390 px screenshot from the Go flow with synthetic data. For host page changes apply the 390/768/1280 host UX gate and report what you saw at each width.

## 7. Acceptance

- [ ] A missing notice returns the translated 422 and writes no acceptance or guest.
- [ ] The count and guest share one transaction. In the already-full case the valid count commits, there is no new guest and the existing completion check runs. Overrides and known counts are preserved.
- [ ] With two callers for one slot, only one inserts and the count stays consistent.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2071-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/web/guest/form_save.go`, `go/internal/web/guest/party.go`

## Owner steps

1. Open after 2066 and 2070 are both included.
2. Review the 390 px form error and the report's concurrent-save result.
