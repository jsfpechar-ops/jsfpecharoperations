# 1553: Go guest cancel and invoice PDFs (blocked)

Status: blocked — guest cancel needs a Go stay-invoice engine (booking_invoice.ensure, invoices.download_pdf, storno and correction invoices), Stripe refund with the intent key, and the cancellation mails; Go has no stay-invoice code (go/internal/pdf is a library, billingjob only issues subscription invoices). Do not run.
Depends on: 1544 and the stay-invoice port | Base commit: none (one big PR) | Branch: the current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A candidate (money out: refunds, invoices). Review: Opus orchestrator.

**One big PR mode.** Work on the current branch. Never create a branch, never push, never open a PR. Commit `1553 step k` after each step that changes a file. Acceptance checks use `git log --oneline --grep='^1553 step'`, not a fixed base commit.

## 1. Objective

Serve `POST /p/{slug}/b/{id}/{token}/cancel`, `GET .../invoice.pdf` and `GET .../correction.pdf` from Go.

## 2. Context

Python: `property_page.py` `booking_invoice_pdf` 414-440, `booking_correction_pdf` 443-472, `booking_manage_cancel` 536-549; `booking_cancel.py` `cancel` 33-77 (refund amount, intent key `site_booking_refund_intent:<id>`, free the reservation, Stripe refund, storno or partial correction invoice, mails), `booking_invoice.py` `ensure` (79 lines), `invoices.download_pdf`.

Blocker (verified by search of `go/internal`): no Go code issues or renders a stay invoice or a correction. `go/internal/pdf` is the PDF library; `go/internal/billingjob/invoicer.go` issues the host's subscription invoices only. The Go booking webhook says the same (`booking_webhook.go` header: `booking_invoice.ensure` is not ported). The refund call and idempotency key exist in `payments/booking_webhook.go` (`refund`), the cancel mails do not.

Consequence kept in the plan: the three paths stay on Python (`/p/*/b/*/*/cancel`, `.../invoice.pdf`, `.../correction.pdf` are not in `UBYHOST_GO_PATHS`). The manage page of 1544 posts its cancel form there. With the Go booking webhook switched on (1554) the invoice is issued when the guest first opens `invoice.pdf`, on Python.

## 3. Files

None yet (blocked).

## 4. Steps

None yet.

## 5. Do not touch

Everything. This brief must not be run.

## 6. Commands

None.

## 7. Acceptance

- [ ] Not applicable until unblocked.

## Risk list (for the reviewer)

- Refund amount and idempotency key; invoice numbering; token check; the 404 for every refusal.

## Owner steps

1. Keep these three paths off `UBYHOST_GO_PATHS`.


## 8. Stop and ask

Stop, and write the report, if: a file outside section 3 needs a change; a step is unclear; a new dependency seems needed; you reach 25 tool calls or about 50k tokens (report as `blocked`); you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1553-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.
