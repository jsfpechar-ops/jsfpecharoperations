# 2033: Complete and verify the Go email-claim-to-registration chain

Status: blocked
Depends on: 2032 and owner decision in 2022 | Base commit: bd961426570f07a214f9840bf165a0bca397b450 | Branch: task/2033-go-claim-start-staging-proof
Executor: Haiku 5.5 | Tier: A | One session, hand off at 25 calls or about 50k tokens

## 1. Objective

Confirm mail-backed claim start issues a usable guest confirmation link, binds it under the approved device policy, and lets the guest submit registration. The observed 404 and the mail-backed start gap have independent acceptance checks.

## 2. Context

`go/internal/web/guest/party.go` ends the mail-enabled branch at `// Claim path stays on stay_claim.go (brief 1721); without mail we only set declared.` and a redirect. `go/internal/web/guest/stay_claim.go` registers `POST /l/{token}/{reservation_id}/claim/confirm` and the GET claim landing. Neither proves a party POST starts a claim. Compare `App/app/routes/guest.py` `async def set_party_size(token: str, reservation_id: int, request: Request):` and its `claim.start_claim` call. The staging audit did not reach the confirmation or registration forms. [2022](2022-claim-device-gate.md) still records an unresolved claim-device rule. Production depends on guest consent and filing correctness. Follow `docs/UBYPORT_CORE.md`, the claim state section in `docs/OPERATIONS.md`, and guest/privacy rules.

## 3. Files

No application edits are authorized by this blocked brief. Author the subsequent exact diff against the next published main. Read only: `go/internal/web/guest/party.go`, `go/internal/web/guest/stay_claim.go`, `go/internal/web/guest/form_pages.go`, `go/internal/web/guest/csrf_forms_test.go`, `go/internal/mail/outbox_config.go`, `go/internal/ubyport/claim.go`, `App/app/routes/guest.py` and `App/app/claim.py` if present at the verified base. The report is `docs/tasks/2033-report.md`.

## 4. Steps

1. Ask the owner to settle [2022](2022-claim-device-gate.md) and record its decision before drafting a behavior change. Use an isolated console or test mail sink and synthetic addresses. Verify the provider refuses external delivery on the chosen staging stack. Expected: one safe test workspace with an approved claim gate.
2. As a Tier A exact-diff author, map the old start-claim service to existing Go claim state and mail primitives. Prove the mail backend used by the guest GET and POST agrees for console, disabled and production SES. Specify transactional claim/outbox creation, duplicate-click and resend behavior, party size validation, chosen locale, existing throttle/Turnstile policy and expiry. Require precise implementations and approved test files in the follow-up brief. Expected: one reviewable diff with the gate decision and a passing and failing case for each transition.
3. After the owner deploys that diff to staging, open the guest link, enter PIN, submit a party and test address, open the test sink's confirmation in a fresh guest context, complete claim, and submit a synthetic registration. Repeat in EN/CS. Test the disabled-mail branch and host readback. Expected: post statuses and visible confirmations for all three forms, exactly one completed registration, no CSRF failures or real notifications.

## 5. Do not touch

Live mail, production, device-gate policy outside the owner's recorded decision, retention, schemas and police filing. No shortcuts through signed tokens, claims, CSRF, PIN, Turnstile or access policy. No claim links, e-mails, credentials or form data in public artifacts.

## 6. Commands

- From `go/`, on the preconfigured test database, `go test ./internal/web/guest -run '^TestGuestFormCSRFRoundTrip$' -count=1 -v 2>&1 | tail -30`. The test is a baseline. A representative database-backed test of the start-to-submit chain is required in the exact-diff brief.
- Chromium on the deployed candidate, 390/1280 px. Use the real visible controls and test sink. Record only path shapes, status, result and masked screenshots.

## 7. Acceptance

- [ ] Mail enabled issues one valid claim message for the first submit. A retry behaves as the approved existing claim state rules require.
- [ ] Browser follows party, claim confirm and registration in EN/CS, persists one registration, and reopens the stay without sending real mail.
- [ ] Mail disabled uses the approved no-email flow. Unknown link/foreign stay and invalid or expired submissions stay refused with localized feedback.
- [ ] Owner's device-gate decision and passing evidence attached to the release gate.

## 8. Stop and ask

Stop until the owner settles the device-gate decision and a Tier A author produces an exact diff. A source-only walk or a form-load check cannot clear this brief. Also stop on a missing anchor, two failures of the same check, a new dependency, out-of-scope files, or the session cap. Return the next exact action to the owner for credentials, SSH, merge or deploy.

## 9. Report

Write `docs/tasks/2033-report.md` (600 tokens max). Include files, commands and last five lines, acceptance, deviations, questions and owner steps. Use `Status: review` only with completed executor checks. Record any staging checks still pending. Use `Status: blocked` for an unmet dependency or missing acceptance evidence.

## Risk list (for the reviewer)

The follow-up diff's claim start and confirm handlers, state transition and mail enqueue code, policy checks and database-backed tests.

## Owner steps

1. Read brief 2022 and record the device-gate decision.
2. Confirm the staging console/test sink and provide a safe way to read only the audit recipient's message.
3. Assign the exact-diff author. After review deploy only to staging, then request the end-to-end re-audit.