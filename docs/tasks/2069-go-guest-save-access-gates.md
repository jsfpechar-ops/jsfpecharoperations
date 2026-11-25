# 2069: Apply the guest access rules before saving a form

Status: todo
Depends on: 2065 | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2069-go-guest-save-access-gates
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make Go form save use the same stay eligibility and email-claim checks as Python. Preserve the guest link, PIN, request protection and language flow.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/routes/guest.py:804`

  ```text
  def _reservation_for_guest(apartment, reservation_id: int, request: Optional[Request] = None):
  ```
- `App/app/routes/guest.py:2377`

  ```text
  claim_guard = _require_claim_session(request, reservation, token, lang)
  ```
- `go/internal/web/guest/form_save.go:105`

  ```text
  cfg, res, ok := reservationForGuest(ctx, d.pool, apt, resID, d.getenv)
  ```
- `go/internal/web/guest/form_pages.go:835`

  ```text
  func (d formPageDeps) formPagesRequireClaim(w http.ResponseWriter, r *http.Request, apt *Apartment, res formResRow, token, lang string) bool {
  ```
- `go/internal/web/guest/pick_data.go:73`

  ```text
  func visibleReservations(ctx context.Context, pool *pgxpool.Pool, apt pickApartment, today time.Time) ([]pickReservation, error) {
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/web/guest/form_save.go` | edit | Gate the existing POST before form processing. |
| `go/internal/web/guest/form_save_test.go` | edit | Replace the obsolete blanket demo assumption and cover allowed and denied rows. |

The executor report and brief status follow section 9.

## 4. Steps

1. In `handleGuestFormSave`, keep `OpenLink`, the PIN and the POST protection. Replace the current `reservationForGuest` lookup with a request-aware lookup scoped to the resolved apartment. Use the full algorithm at `App/app/routes/guest.py:804–849` as the oracle. Apply Python's visible-picker fast path and fallback in order. Reuse `visibleReservations`, Prague date normalization and `registrationComplete` from `pick_data.go`. On the fallback require active, unarchived and matching apartment. Permit a demo only for its signed-in host with guest access open. For a non-demo enforce the property's normalized reachback inclusive boundary, guest access open, and device claim or signed owned-guest proof for a completed stay outside the visible window. Treat read errors according to the existing unavailable/server-error helpers. Compare the fallback with the exact Python order. Then run the focused `FormSaveAccess` command in section 6.
2. After the existing throttle and before `postForm`, call the existing `formPagesRequireClaim` via a `formPageDeps` constructed from `d.pool`, `d.getenv` and `d.now`. Pass the resolved stay ID/status and the canonical token/language, and return if it wrote a response. Retain Python's mail-disabled and owning-host exemptions. Run the same command and confirm the denied cases leave guest, audit and outbox rows untouched.
3. Add `TestFormSaveAccess` in `form_save_test.go`. Exercise the registered handler with signed cookies from existing fixtures. Cover wrong apartment, unknown or revoked token, wrong PIN, expired or missing email claim with mail enabled, stale claim generation, access locked, owning host demo, outsider demo, mail-off behavior, reachback boundary and completed-stay device proof. Assert the existing 303/404 shape and language. Record the 390 px rejection and return path.

## 5. Do not touch

Preserve the 2065 completion hooks and redirect, CSRF/PIN middleware, claim-cookie format, and reservation scope. Keep Python, public templates and live services read-only.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/web/guest/ -run 'FormSaveAccess|FormSaveRoutePattern' -count=1 -v 2>&1 | tail -30
```

For each changed guest-facing response, include a 390 px screenshot from the Go flow with synthetic data. For host page changes apply the 390/768/1280 host UX gate and report what you saw at each width.

## 7. Acceptance

- [ ] Every grant/refusal case has the Python-equivalent result and protected data remains untouched on refusal.
- [ ] Legitimate guest, owning host and mail-off cases can still save.
- [ ] Required focused tests pass without skips.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2069-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/web/guest/form_save.go`

## Owner steps

1. Open this brief after 2065 is in the executor base.
2. Review the report and the phone screenshot before accepting the fix.
