# 2074: Restart filing attempts when a guest corrects a record

Status: todo
Depends on: 2073 | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2074-go-guest-filing-correction
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Restore the guest self-correction transition and retry budget. Preserve a duplicate refusal when the guest changed none of the fields UbyPort receives.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/reporting.py:1320`

  ```text
  def edit_keeps_duplicate_block(stored, proposed, reservation) -> bool:
  ```
- `App/app/reporting.py:1357`

  ```text
  def guest_correction_resets_attempts(existing) -> bool:
  ```
- `go/internal/web/guest/form_save.go:246`

  ```text
  if existing != nil && existing.submitState == "blocked" && strings.Contains(existing.lastErrors, "duplicate") {
  ```
- `go/internal/web/stays/guest_edit.go:297`

  ```text
  func ubyGuestPayload(g hostGuest, res hostReservation) map[string]any {
  ```
- `go/internal/ubyport/collect.go:284`

  ```text
  func blockedAsDuplicate(lastErrors string) bool {
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/web/guest/form_save.go` | edit | Use current decrypted values and exact correction rules. |
| `go/internal/ubyport/collect.go` | edit | Expose the existing duplicate classifier if needed. |
| `go/internal/web/guest/form_save_test.go` | edit | Proof for duplicate, correction and refused concurrent writes. |

The executor report and brief status follow section 9.

## 4. Steps

1. In the Go UbyPort package make the existing duplicate classifier callable from guest form save. Keep its condition and all existing collector calls. Build old and new inputs for the same exported UbyPort payload function that `ubyGuestPayload` calls. Keep that canonical field mapping shared. Read `App/app/reporting.py:filed_record_changed` for the exact comparisons. If reproducing that comparison would require a second field list, reuse the existing mapper rather than maintaining another list.
2. In guest save load the old normalized, decrypted reportable fields and preserve the initial compare-and-set state. Replace the substring-only branch. For a blocked duplicate with no reportable changes, omit `submit_state`, `last_errors` and `submit_attempts` from SET. Otherwise retain the existing nationality-based next state and reset attempts to zero only for an existing error, blocked or not-required record, as Python does. Keep the existing sent/restricted and active submission-claim protections.
3. Add `TestGuestSaveFilingCorrection`. Verify an unchanged or note-only duplicate, changed UbyPort field, non-duplicate error at the attempt cap, nationalities that move between required and not required, and a sent/leased record. Compare the final stored state, error and attempts. Run section 6.

## 5. Do not touch

Keep the nationalities, error codebook, lease duration, scheduler cap and XML contract fixed. No live UbyPort calls.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/web/guest/ -run 'GuestSaveFilingCorrection|FormSave' -count=1 -v 2>&1 | tail -30
cd go && go test ./internal/ubyport/ -run 'Collect|GoldenEnvelopes' -count=1 -v 2>&1 | tail -30
```

Use fixture credentials and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] Only an eligible correction restarts the budget; note-only duplicates stay blocked.
- [ ] Stored police fields, not display text or case alone, determine whether there was a correction.
- [ ] Sent and actively claimed records stay protected. The SOAP request goldens pass.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2074-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/web/guest/form_save.go`, `go/internal/ubyport/collect.go`

## Owner steps

1. Open after 2073.
2. Check that the report distinguishes an unchanged duplicate from a genuine correction.
