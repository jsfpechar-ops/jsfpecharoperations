# 2073: Preserve the under-15 signer relationship

Status: todo
Depends on: 2072 | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2073-go-guest-child-signer
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Restore Python's child and adult signer validation and recorded relationship on guest save. Link and clear signatures as the same stay is updated.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/routes/guest.py:411`

  ```text
  def _sign_for_fields(request, reservation, signer_raw, role_raw, now) -> Dict[str, Any]:
  ```
- `App/app/routes/guest.py:1907`

  ```text
  def _under15_lists(request, reservation, guest_id):
  ```
- `App/app/routes/guest.py:2599`

  ```text
  "signed_for_guest_id": None,
  ```
- `go/internal/web/guest/form_save.go:225`

  ```text
  func buildSavePayload(v validation.GuestRow, stayFrom, stayTo, sig string, child bool, lang, noticeVer, now string, existing *guestSaveRow) map[string]any {
  ```
- `go/internal/web/guest/form_pages.go:362`

  ```text
  _, _ = d.pool.Exec(ctx, `UPDATE guest SET signed_for_guest_id = NULL, signed_for_role = NULL,
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/web/guest/form_save.go` | edit | Validate the signer and restore persistence and reverse link. |
| `go/internal/web/guest/form_save_test.go` | edit | Cover child, adult and age-correction flows. |

The executor report and brief status follow section 9.

## 4. Steps

1. In the form-save validation block implement the Python `_under15_lists` and `_sign_for_fields` checks using loaded, same-stay guests and the signed owned-guest device proof. Use the existing form field names `signed_by`, `child_sign_role` and adult child-selection fields as defined by Python and the Go template. Use exact localized keys for missing or invalid choices; allow unknown signer only where Python does.
2. In `buildSavePayload`, for a child store `signed_for_guest_id`, `signed_for_role`, `signed_for_at` and `signed_for_wording` computed as Python does. For a record corrected to age 15 or over, clear those four fields and require the adult's own signature. Add the four columns to `guestSaveInsertCols` so inserts and updates agree.
3. After a successful adult signature, update only eligible selected children of the same reservation as at `guest.py:2717–2724`. Revalidate device ownership and active/filing conditions where Python does. Keep signature writes and relationship changes consistent, and perform the post-save filing/completion checks after the links are in place. Confirm there is no change to which birth dates, document values, or signatures are reportable.
4. Add `TestGuestSaveChildSigner` covering zero/one/multiple eligible signers, another stay's signer, adult signs for selected children, child ages out on correction and archived guests. Assert the four stored fields rather than the visual state alone. Run section 6 and capture the child form at 390 px.

## 5. Do not touch

Keep the six language catalogs as the source of existing copy. Preserve outbound filing rules, passport handling, schema, and route shape.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/web/guest/ -run 'GuestSaveChildSigner|FormSave' -count=1 -v 2>&1 | tail -30
```

For each changed guest-facing response, include a 390 px screenshot from the Go flow with synthetic data. For host page changes apply the 390/768/1280 host UX gate and report what you saw at each width.

## 7. Acceptance

- [ ] The under-15 relationship matches Python, including the wording and timestamps.
- [ ] An adult links only eligible children of this stay, and age correction clears the previous signer.
- [ ] The age rule and signed/unsigned house-book and filing behavior match the fixture.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2073-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/web/guest/form_save.go`

## Owner steps

1. Open after 2072.
2. Review the child and adult fixture results and the screenshot.
