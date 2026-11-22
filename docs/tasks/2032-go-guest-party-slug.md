# 2032: Resolve the guest party form through the same link as the guest page

Status: todo
Depends on: none | Base commit: bd961426570f07a214f9840bf165a0bca397b450 | Branch: task/2032-go-guest-party-slug
Executor: Haiku 5.5 | Tier: A | One session, hand off at 25 calls or about 50k tokens

## 1. Objective

Make the Go party form accept a valid property slug that already opened the guest stay. Preserve PIN handling, CSRF, and property/stay scoping.

## 2. Context

On Go staging `2528d7db4`, the synthetic stay's copied link was a current public slug. Its PIN and GET opened the party form. The browser submitted a non-wildcard CSRF value and received HTTP 404. On the base above, `stay_claim.go` resolves GET through `OpenLink` and builds the form action with the public link. `party.go` looks up only `a.permalink_token = $2`. The mail-backed claim-start work is tracked in [2033](2033-go-claim-start-staging-proof.md). The owner decision for device gates stays in [2022](2022-claim-device-gate.md).

Apply after the 1722 party-route port already present on the base. If 1722 is reopened, finish this brief before another change to the same handler.

Exact anchors:
- `go/internal/web/guest/party.go`: `stay, found, err := d.loadPartyStay(r.Context(), token, resID)` inside `partySizeHandler`.
- `go/internal/web/guest/stay_claim.go`: `func (d stayClaimDeps) pinRedirect(w http.ResponseWriter, r *http.Request, token, lang string, resID int64) bool {`.
- `go/internal/web/guest/csrf_forms_test.go`: `postPath := fmt.Sprintf("/l/%s/%d/party?lang=en", tok, resID)` and the immediately following form post.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/guest/party.go` | edit | Resolve the party action through the shared guest link resolver before the existing scoped lookup. |
| `go/internal/web/guest/csrf_forms_test.go` | edit | Cover current slug and exact success status with the existing database-backed CSRF round trip. |

Read only: `go/internal/web/guest/shell.go`, `go/internal/web/guest/stay_claim.go`, `go/internal/web/guest/shell_test.go`, `docs/UBYPORT_CORE.md` and the guest-page browser entry from `docs/context/test-map.md`.

## 4. Steps

1. In `partySizeHandler` only, replace the lines from `lang := r.URL.Query().Get("lang")` through `stay, found, err := d.loadPartyStay(r.Context(), token, resID)` with:

   ```go
   lang := langFromRequest(r)
   apartment, link, early := OpenLink(r, d.pool, token, lang)
   if early != nil {
       early.ServeHTTP(w, r)
       return
   }
   token = link
   gate := stayClaimDeps{pool: d.pool, getenv: d.getenv, now: d.now}
   if gate.pinRedirect(w, r, token, lang, resID) {
       return
   }
   stay, found, err := d.loadPartyStay(r.Context(), apartment.PermalinkToken, resID)
   ```

   The resolver supplies a stable lookup key and a public redirect key. Leave the existing registration wrapper in place. Run `gofmt -w go/internal/web/guest/party.go 2>&1 | tail -30` from repo root. Expect no output.

2. In `TestGuestFormCSRFRoundTrip`, in the party subtest only, insert these lines immediately after the `INSERT INTO apartment` helper call:

   ```go
   slug := fmt.Sprintf("party-%d-abc234", aptID)
   mustExecGuest(t, ctx, pool, `INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at)
       VALUES ($1, $2, 1, $3)`, slug, aptID, stamp)
   ```

   Change `getPath := st.getPath(tok, resID)` to `getPath := st.getPath(slug, resID)`. Replace the existing POST path/body/recorder/assertion block ending at `t.Fatalf("POST party rejected CSRF: %s", body)` and its closing brace with:

   ```go
   for _, key := range []string{slug, tok} {
       postPath := fmt.Sprintf("/l/%s/%d/party?lang=en", key, resID)
       postBody := url.Values{"_csrf": {csrf}, "party_size": {"2"}}
       postReq := httptest.NewRequest(http.MethodPost, postPath, strings.NewReader(postBody.Encode()))
       postReq.Header.Set("Content-Type", "application/x-www-form-urlencoded")
       postReq.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: cookie})
       postRec := httptest.NewRecorder()
       mux.ServeHTTP(postRec, postReq)
       if postRec.Code != http.StatusSeeOther {
           t.Fatalf("party POST did not redirect: status %d", postRec.Code)
       }
       if location := postRec.Header().Get("Location"); !strings.HasPrefix(location, fmt.Sprintf("/l/%s/%d", key, resID)) {
           t.Fatal("party POST did not redirect to the same guest stay")
       }
   }
   ```

   The `io` import is still used by the claim-confirm check. Run `gofmt -w go/internal/web/guest/csrf_forms_test.go 2>&1 | tail -30`. Expect no output. Run section 6 tests.

## 5. Do not touch

Other guest POSTs, CSRF signing, PIN policy, claim/device gates, mail settings, the registration data model, filing, production routing or any Python code. Preserve the existing active/archive filter and reservation/property match. Keep links, PINs and cookies out of reports and logs.

## 6. Commands

- From `go/`, with the disposable Postgres test setup already configured, `go test ./internal/web/guest -run '^TestGuestFormCSRFRoundTrip$' -count=1 -v 2>&1 | tail -30`. Expect okay, with both party subtests executed and no skips.
- For the changed guest pages, run the guest browser and geometry cases from the test map on the disposable stack. Report 0 skips.
- Browser on Go staging candidate. Start with a fresh, non-host browser session. Use the stay's copy-link action, enter the synthetic PIN and post the visible form. Repeat in EN and CS on separate fixtures or a clean fixture state.

## 7. Acceptance

- [ ] Expected redirect using the current slug and old opaque permalink. Valid CSRF token posted.
- [ ] Party count with mail disabled persists once and lands back on the same stay. Unknown link, wrong property/stay pair and archived stay stay unavailable. Missing PIN never writes. Cover these on disposable fixtures and record sanitized status.
- [ ] Screenshots of the form and post-submit state at 390 and 1280 px. No email, claim or registration pass claimed from the 303 alone.

## 8. Stop and ask

Stop if the current branch disagrees on the route or if the behavior indicates a different failing check. Resolve 2033 before declaring complete guest onboarding. Also stop on a missing anchor, two failures of the same check, a new dependency, out-of-scope files, or the session cap. Return the next exact action to the owner for credentials, SSH, merge or deploy.

## 9. Report

Write `docs/tasks/2032-report.md` (600 tokens max). Include files, commands and last five lines, acceptance, deviations, questions and owner steps. Use `Status: review` only with completed executor checks. Record any staging checks still pending. Use `Status: blocked` for an unmet dependency or missing acceptance evidence.

## Risk list (for the reviewer)

The two edited guest files, including the shared resolver call and the scoped lookup.

## Owner steps

1. Open the draft PR and verify the guest database test ran.
2. Deploy the branch to the isolated staging host with mock police reporting and the safe mail profile required by the case.
3. Give the auditor the staged SHA. Keep the Go guest cutover pending until [2033](2033-go-claim-start-staging-proof.md) clears.