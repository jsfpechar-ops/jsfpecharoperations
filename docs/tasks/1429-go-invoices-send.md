# 1429: Go invoice pages: send the invoice by e-mail (POST /invoices/{id}/send)

Status: todo
Depends on: 1427, 1428 (`mail.BuildInvoiceIssued` merged) | Base commit: the working branch head | Branch: the current branch (one big PR) or `cursor/1429-go-invoices-send-dff7`
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (e-mail to a guest)

> **One big PR mode.** Work on the current branch: never create a branch, never push, never open a PR if the owner said one big PR; otherwise branch per coordinator. Commit `1429 step k` after each step.

## 1. Objective

Port `POST /invoices/{id}/send` (`invoice_send`, `App/app/routes/invoices.py` 961-1001) to Go. When this lands with the detail page on Go, Caddy can send `/invoices/<id>` and `/invoices/<id>/send` together.

## 2. Context

| Python | Go |
|---|---|
| `_load_invoice`; none: flash `flash.error.no_such_invoice` | `loadInvoice` |
| no `buyer_email`: `invoice.err.no_email` | same |
| `entity` + `download_token` + `PUBLIC_BASE_URL/invoice/d/{{claim_secret}}` | `entityForInvoice`, `downloadTokenFor`, `mail.BuildInvoiceIssued` |
| `guest_payload` + `claim_secret_enc` | `invoiceGuestPayload`, `ClaimSecretPayloadKey` + `EncryptString` |
| idempotency `invoice_issued:<id>:<count>`; `mail.enqueue` | `ubyport.EnqueueMail` |
| `emailed_at`, audit `invoice_sent` | same SQL + `c.audit` |

**Sidecars (exact-diff):** `docs/tasks/1429-files/`. Checksums:

| sha256 | file |
|---|---|
| `69cacb045a3b830994fa33a23cccf02e2e32339e869f3a0ab37b9fbd5636f3ff` | `go/internal/web/invoices/send.go` |
| `8fee049a3608378d8ae9b6cd9dec667da2e811a3219d6a0de1cd531c268089ad` | `go/internal/web/invoices/send_test.go` |

Full manifest: `docs/tasks/1429-files/MANIFEST.sha256` (executor generates after verifying sidecars on disk).

**Privacy:** buyer e-mail is the recipient only; never logged. Token is Fernet in the payload, not in the stored body in clear (marker in text/html).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/invoices/send.go` | create | `sendInvoice` handler |
| `go/internal/web/invoices/send_test.go` | create | route registration + DB send test |
| `go/internal/web/invoices/routes_test.go` | edit | allow send route; drop `TestSendRouteIsNotThere` |
| `go/cmd/ubyhost-web/register_web_invoices_test.go` | edit | expect `POST /invoices/{id}/send` |
| `docs/tasks/1429-files/**` | keep | sidecars |
| `docs/tasks/1429-report.md` | create | report |

No `UBYHOST_GO_PATHS` edit in this brief.

## 4. Steps

0. Checks: `grep -cF 'func BuildInvoiceIssued(' go/internal/mail/invoice_issued.go | tail -1` → `1`. `grep -cF 'async def invoice_send' App/app/routes/invoices.py | tail -1` → `1`. Sidecar count: `find docs/tasks/1429-files -name '*.txt' ! -name 'MANIFEST.sha256' | wc -l | tail -1` → `2`.

1. Copy sidecars:

   ```bash
   S=docs/tasks/1429-files && for f in $(cd "$S" && find . -name '*.txt' ! -name 'MANIFEST.sha256' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done
   ```

   Refresh `MANIFEST.sha256`. Commit `1429 step 1`.

2. Edit `routes_test.go`: nine routes including send; remove `TestSendRouteIsNotThere`. Update `register_web_invoices_test.go` pattern list. Commit `1429 step 2`.

3. Add DB test in `send_test.go`: issue invoice, POST send, assert outbox row (`kind`, idempotency key suffix `0`, marker in payload, `claim_secret_enc` present, no raw token in subject). Assert `emailed_at` and audit `invoice_sent`. Commit `1429 step 3`.

4. Run §6; write report.

## 5. Do not touch

`go/internal/mail/` (brief 1428), `App/app/`, `UBYHOST_GO_PATHS`.

## 6. Commands

From `go/`: `gofmt -l internal/web/invoices/ cmd/ubyhost-web/ 2>&1 | tail -5`
From `go/`: `go vet ./internal/web/invoices/... ./cmd/... 2>&1 | tail -20`
From `go/`: `UBYHOST_TEST_DATABASE_URL=<url> go test -count=1 ./internal/web/invoices/... ./cmd/ubyhost-web/... 2>&1 | tail -30`
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] Send POST queues exactly one `invoice_issued` row; second click uses suffix `1`.
- [ ] Payload uses marker in text/html; encrypted token under `claim_secret_enc`.
- [ ] Route tests list send; register_web test passes.

## 8. Stop and ask

Stop when: 1428 builder missing; anchor missing; golden/outbox shape differs from Python; file outside §3 needed.

## 9. Report

`docs/tasks/1429-report.md`, one PR.

## Risk list (for the reviewer)

Guest e-mail recipient; idempotency suffix on repeat send; `emailed_at` not guarded by issued-row trigger; download URL never holds the token at rest.

## Owner steps

Merge 1428 before 1429. Switch `/invoices/<id>/send` with the detail page in the cutover runbook.