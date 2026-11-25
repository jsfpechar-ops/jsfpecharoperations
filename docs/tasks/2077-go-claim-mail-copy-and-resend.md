# 2077: Restore localized claim and resend emails

Status: todo
Depends on: none | Base commit: f6be14e46b68677884e26533eef674b15cb89f6a | Branch: task/2077-go-claim-mail-copy-and-resend
Executor: Luna | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Restore Python claim and resend content, outbox kinds and host reply address. Preserve token protection, holds and rate rules.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests. Review the named anchors against the approved base or its prerequisite tip.

- `App/app/claim.py:346`

  ```text
  kind = "claim_resend" if resend or claim["state"] == CLAIMED else "claim"
  ```
- `App/app/claim.py:360`

  ```text
  payload = mail_notify.guest_payload(apartment, content, lang)
  ```
- `App/app/mail_notify.py:1345`

  ```text
  def guest_payload(
  ```
- `go/internal/web/stays/claim_seed.go:328`

  ```text
  func enqueueClaimStart(ctx context.Context, d claimOpsDeps, st *claimStay, apt *claimApt, addr, lang, secret string, version int64, stamp string) error {
  ```
- `go/internal/web/stays/claim_ops.go:783`

  ```text
  func enqueueClaimResend(ctx context.Context, d claimOpsDeps, st *claimStay, apt *claimApt, addr, lang, secret string, version int64, party int, stamp string) error {
  ```
- `go/internal/mail/outbox_markers.go:28`

  ```text
  ClaimSecretPayloadKey = "claim_secret_enc"
  ```

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/mailnotify/claim.go` | add | Shared localized claim/resend builder. |
| `go/internal/mailnotify/claim_i18n.go` | add | Exact Python labels missing from the Go catalogs. |
| `go/internal/mailnotify/claim_test.go` | add | Compare subject, text and HTML fixtures. |
| `go/internal/web/stays/claim_seed.go` | edit | Choose kind and build payload for guest start and resend. |
| `go/internal/web/stays/claim_ops.go` | edit | Use the shared payload for host resend. |
| `go/internal/web/stays/claim_seed_test.go` | edit | Verify guest start and resend rows. |
| `go/internal/web/stays/claim_ops_test.go` | edit | Verify host resend rows. |

The executor report and brief status follow section 9.

## 4. Steps

1. In `mailnotify` port the two Python `_guest_mail_content` branches from `App/app/claim.py:475` with the existing mail shell, language and date helpers. Match subject, lead text, property/date/host lines, CTA and completed-stay variation for each of the six languages. Put missing keys in `claim_i18n.go` using the Go catalog convention.
2. In `startClaimSeed`, pass its existing resend/claimed decision to the queue wrapper. Initial mail uses `claim:<reservation>:v<version>` and kind `claim`. Guest and host resends use `claim_resend:<reservation>:v<version>` and kind `claim_resend`. In `enqueueClaimResend`, call the same builder with the host route's existing validated recipient. Supply the scoped apartment owner's reply address via the same rules as Python `guest_payload`.
3. Both paths keep the existing secret marker in text and escaped HTML and queue the encrypted secret under `mail.ClaimSecretPayloadKey`. Preserve token expiry and rotation, recipient and version, mail enablement, cooldown, holds and dedupe. Keep existing Go delivery path and record any send-timing divergence from Python.
4. Add `TestClaimMailGolden` and `TestClaimMailOutbox` to the named files. Cover six languages, initial and both resend flows, completed stays, no eligible reply address, and a replay. Assert the payload protects the token. Run section 6 with delivery disabled.

## 5. Do not touch

Preserve SES configuration, claim routes and privacy. Guide links, entry codes and other mail kinds stay outside this brief. No live sending.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect the listed cases to run and pass. Required database and browser cases must show zero skips.

```sh
cd go && go test ./internal/mailnotify/ -run 'ClaimMailGolden|Golden|MatchesPython' -count=1 -v 2>&1 | tail -30
cd go && go test ./internal/web/stays/ -run 'ClaimMailOutbox|ClaimSeed|ClaimOps' -count=1 -v 2>&1 | tail -30
```

Use fixture credentials and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] Start and both resend paths queue the matching recipient, kind, subject, copy, language and Reply-To.
- [ ] Both parts carry the marker, with the secret stored encrypted and no change in version/hold/dedupe behavior.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2077-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/mailnotify/claim.go`, `go/internal/mailnotify/claim_i18n.go`, `go/internal/web/stays/claim_seed.go`, `go/internal/web/stays/claim_ops.go`

## Owner steps

1. This brief can run separately from the sequential guest work.
2. Review synthetic initial, guest resend and host resend examples.
