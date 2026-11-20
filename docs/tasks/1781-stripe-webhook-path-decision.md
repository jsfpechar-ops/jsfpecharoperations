# 1781: Go-native Stripe booking webhooks (no Python forward)

Status: review — exact-diff sidecars ready (2026-11-20).
Depends on: 1350, 1542, 1543 | Base commit: current tip of `main` | Branch: `cursor/1781-exact-diff-dff7`
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: B (Sonnet writes the exact-diff pass; orchestrator reads the diff of the risk-listed files)

> **One big PR mode.** Work on the current branch. After each step that changes a file, commit with the message `1781 step k`. Acceptance checks use `git log --oneline --grep='^1781 step'`.

## 1. Objective

Make Go handle booking-site Stripe events (`metadata.site_booking_id`) on `POST /webhooks/stripe` without forwarding to Python. Remove `UBYHOST_PY_WEBHOOK_URL`, the `UBYHOST_GO_BOOKING_WEBHOOK` switch, and forward tests. Update cutover docs so `/webhooks/stripe` may join `UBYHOST_GO_PATHS` once tests are green.

## 2. Context

Hard rules (AGENTS.md): 1 filing correctness first; 2 privacy first; 3 no secrets; 4 no new dependency; 5 Postgres through `pgxpool`; 11 Go first.

**Python source of truth:** `App/app/booking_webhook.py` (parity golden already in Go).

**Risk:** Paid booking confirmation and clash refunds.

**Sidecars:** `docs/tasks/1781-files/<repo path>.txt`. Manifest: `docs/tasks/1781-files/MANIFEST.sha256`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/payments/webhook.go` | edit | always `BookingWebhook.Process`; drop forward |
| `go/internal/payments/booking_webhook.go` | edit | drop switch env helpers |
| `go/internal/payments/webhook_forward_test.go` | delete | forward-only tests |
| `go/internal/payments/webhook_test.go` | edit | shared `fwdPost`/`fwdSigned` helpers |
| `go/internal/payments/booking_webhook_test.go` | edit | single in-Go booking handler test |
| `deploy/lightsail/docker-compose.yml` | edit | remove `UBYHOST_PY_WEBHOOK_URL` |
| `docs/ENVIRONMENT.md` | edit | remove forward row; update `UBYHOST_GO_PATHS` text |
| `docs/plans/go-cutover-runbook.md` | edit | section 5 `/webhooks/stripe` sequence |
| `docs/plans/go-cutover-env-commands.md` | edit | allow path in waves |
| `docs/tasks/1781-files/**` | keep | sidecars from the exact-diff pass (do not edit) |
| `docs/tasks/1781-report.md` | create | the report (§9) |

## 4. Steps

0. Checks (repo root): anchors in `docs/tasks/1781-files/ANCHORS.txt` (expected: `1` for positives, `0` for `forwardToPython`, `BookingSwitchEnv`, compose and ENVIRONMENT `UBYHOST_PY_WEBHOOK_URL`). Anything else: STOP (§8).
1. Apply the §3 file changes (or copy sidecars where they match).
2. Run §6; fix only what the brief names.
3. Write the report (§9).

## 5. Do not touch

Python `App/app/booking_webhook.py`; filing code; unrelated plans.

## 6. Commands

- `cd go && gofmt -l internal/payments/*.go | tail -5` prints nothing
- `cd go && go vet ./internal/payments/... 2>&1 | tail -20` is silent
- `cd go && go test ./internal/payments/ -count=1 -run 'Booking|Webhook' 2>&1 | tail -30` passes (DB tests may skip without `UBYHOST_TEST_DATABASE_URL`)
- `python3 scripts/context_lint.py 2>&1 | tail -10` is clean

## 7. Acceptance

- No `forwardToPython`, `UBYHOST_PY_WEBHOOK_URL`, or `BookingSwitchEnv` in Go or compose.
- `grep -n webhooks/stripe docs/plans/go-cutover-*.md | tail -10` shows Go-native handling, not Python forward.
- `git diff --stat` lists only §3 paths.

## 8. Stop and ask

Stop and write the report when: an anchor fails; a golden differs outside the accepted list; a file outside §3 must change; tests need a skip for a reason you cannot explain.

## 9. Report

`docs/tasks/1781-report.md`: commits, command outputs (last 30 lines), accepted differences, owner steps left.

## Rollout wave and rollback

- **Rollout:** Add `/webhooks/stripe` to live `UBYHOST_GO_PATHS` (if not already there) after deploy; send a Stripe test booking event and confirm paid status and mails.
- **Rollback:** Remove `/webhooks/stripe` from `UBYHOST_GO_PATHS` and `caddy reload` so Python serves the route again (Python handler remains until deleted in a later brief).

## Owner steps

1. Deploy this branch.
2. Ensure `/webhooks/stripe` is in `UBYHOST_GO_PATHS` (double-quoted list).
3. `caddy reload`.
4. Stripe Dashboard → Webhooks → send test `checkout.session.completed` with `metadata.site_booking_id`; confirm 200 and app logs show Go handling (no Python forward).