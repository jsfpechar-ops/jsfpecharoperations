# 2037: Run signup and release acceptance on the actual Go candidate

Status: todo
Depends on: none. Start with steps 1–3. Close §7 only after 2022, 2032–2036 and 2038–2039. | Base commit: bd961426570f07a214f9840bf165a0bca397b450 | Branch: task/2037-go-staging-candidate-and-signup
Executor: Haiku 5.5 | Tier: A | One session, hand off at 25 calls or about 50k tokens

## 1. Objective

Make the staging results attributable to the same Go build intended for release. Exercise signup in a staging profile that behaves like production login and never sends real mail.

## 2. Context

Staging `/healthz` returned `2528d7db434f113e527b4e33bd32a75fbe7f0d09` twice. The fetched main above includes PR #1277 for guest-pay. With the login bypass active, `/login` returned the dashboard and `/signup` returned a blank 404. Go intentionally gates signup. The stage-wide no-login profile also makes any result under an authenticated host unrepresentative of signup.

Exact anchors: `if !signup.Enabled(d.getenv) {` and `if h != nil {` inside `signupForm` in `go/internal/web/auth/signup_pages.go`. Both flags are passed to Go by `deploy/lightsail/docker-compose.yml`. Deploy behavior is described in `.github/workflows/deploy-staging.yml`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `docs/tasks/2037-report.md` | new | Candidate, sanitized profiles, route ownership and release verdict. |

Read only: `.github/workflows/deploy-staging.yml`, `deploy/lightsail/docker-compose.yml`, `deploy/lightsail/caddy/Caddyfile.acme`, `deploy/lightsail/caddy/Caddyfile.cloudflare`, `go/internal/web/auth/signup_pages.go`, the Accounts, UbyPort and Mail sections in `docs/ENVIRONMENT.md`, `docs/LIGHTSAIL.md` deploy section, and `docs/tasks/2022-claim-device-gate.md`.

## 4. Steps

1. Compare the green published main SHA, the successful staging deploy run's SHA and the staging `/healthz` version. Confirm the expected Go containers and effective route split for `/l/*`, properties, `/signup`, public booking, webhook and AI paths. Check whether any response used Python fallback. Use the owner's sanitized routing evidence and §6. Expected: one matching build and known Go ownership for each route.
2. Ask the owner to prepare two staging acceptance profiles on that same SHA. Host click-through uses `UBYHOST_STAGING_NO_LOGIN=1`. Auth and signup acceptance uses it off and `UBYHOST_SIGNUP_ENABLED=1`, a fresh anonymous browser and isolated console/test mail. If only one instance exists, sequence the profiles under owner control. Verify the approved auth/profile rollback after the run. Expected: signup and login forms visible, localized and operable with JavaScript off where designed. If signup still 404s with the flag on and no host cookie, return route and status for an auth brief.
3. In the auth profile verify signup form, consent, synthetic submit, challenge handling, first-login link issuance and redemption, normal login, logout and session recovery/expiry on controlled test accounts. Check disabled signup returns the deliberate disabled state. Record separately any unaudited 2FA, passkeys, invitations or real SES delivery. Expected: production-like flows with a test sink only.
4. Complete A–F from the audit against the green candidate using 2032–2036 and 2038–2039. Recheck the device-gate decision, published synthetic property with retirement set, neutral dummy Stripe reply, the 307/405/branded-404/static cases, and complete police test filing with Doručenka via the owner-approved test gate if a Go cutover is requested. Expected: an evidence-backed yes/no tied to the exact SHA. Release readiness stays pending with any required gap.
5. Reset to the owner's intended isolated staging config after the auth pass. Add the SHA and report to the release review. Expected: stage and test-state changes documented with no production actions.

## 5. Do not touch

App code, deployments or env files as executor. No auth bypass, live booking, real card, actual email recipient, production CLI/SSH or real police filings. Never include environment dumps, image credentials, test PINs or guest links in the report. Staging-only test flags cannot justify weakening production guards.

## 6. Commands

- Repo root, `git rev-parse origin/main | head -1` after the approved fetch. Record the full candidate SHA.
- Chromium staging `/healthz`. Record status and only the version. Recheck before and after the flow.
- Chromium staging `/signup` and `/login` from a clean profile. Check EN/CS at 390/1280 px. Use synthetic fixtures and the test sink for any write.

## 7. Acceptance

- [ ] Health version agrees with the accepted deploy and release candidate. No unexpected fallback on routes claimed as Go.
- [ ] Signup renders and completes in the intended enabled/auth profile. The disabled profile result is explained. Auth verification covers the sequence in §4.
- [ ] Guest claim gate, delivery handoff, registration, wizard persistence, retired-payment behavior, guide and test filing have separate evidence and explicit results. Every actual page reported has 390/1280 screenshots in EN/CS where applicable.
- [ ] Reviewer can see the exact unresolved items and the release verdict without assuming a production deploy.

## 8. Stop and ask

Stop at SHA drift, missing safe mail fixture, unidentified route ownership, or an unmet claim-device or filing gate. Report the staged subset instead of assuming parity. Also stop on a missing anchor, two failures of the same check, a new dependency, out-of-scope files, or the session cap. Return the next exact action to the owner for credentials, SSH, merge or deploy.

## 9. Report

Write `docs/tasks/2037-report.md` (600 tokens max). Include files, commands and last five lines, acceptance, deviations, questions and owner steps. Use `Status: review` only with completed executor checks. Record any staging checks still pending. Use `Status: blocked` for an unmet dependency or missing acceptance evidence.

## Risk list (for the reviewer)

Any future diff to auth, Caddy or deploy config requires its own scope and review. Read the staging logs and evidence at matching SHA.

## Owner steps

1. Open GitHub → Actions → Deploy staging. Open the run for green main. If the candidate hasn't deployed, select Run workflow, choose the candidate branch and use mock police reporting.
2. Open staging's health page and compare the version to that run. Share the SHA and sanitized Go route ownership.
3. On the staging instance only, use the existing settings to prepare the auth-test profile in §4. Tell the auditor its window and how to access the test sink. Restore the intended isolated staging profile afterward.
4. Keep production promotion on hold until the exact candidate report clears the required gates.

