# 1429: Go invoice pages: send the invoice by e-mail (POST /invoices/{id}/send)

Status: blocked — the Go mail package has no builder for the `invoice_issued` message (no `mail.BuildInvoiceIssued`), and `go/internal/mail/` is owned by the mail thread, which this thread may not edit
Depends on: 1427 and the mail thread adding `BuildInvoiceIssued` | Base commit: the working branch head | Branch: the current branch (one big PR)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier B (e-mail to a guest)

> **One big PR mode.** Work on the current branch: never create a branch, never push, never open a PR; commit `1429 step k` after each step. This brief is blocked: do not run it.

## 1. Objective

Port the last route of `App/app/routes/invoices.py`, `POST /invoices/{id}/send` (`invoice_send`, lines 961-1001), to the Go invoice package. Until this exists, the Go invoice detail page cannot be switched on by path (Caddy cannot send `/invoices/<id>` to Go without also sending `/invoices/<id>/send`), so the thread's detail page waits for this brief.

## 2. Context

**Why it is blocked (nothing was guessed or worked around):** the route builds its mail with `mail_notify.build_invoice_issued` (mail_notify.py 2166-2230: subject and body from the guest catalog keys `invoice_mail_issued_subject`, `invoice_mail_issued_subject_stay`, `invoice_mail_issued_intro`, `invoice_mail_issued_button`, `mail_invoice_title`, `mail_invoice_number`, `mail_invoice_property`, `mail_invoice_total`; a heading, a paragraph and a money panel with a button; a footer from `host_details`). The Go package `go/internal/mail` has builders for other kinds (`BuildBillingInvoice`, `BuildSubmissionProblem`, ...) but none for this one, and its HTML shell and block helpers (`shell`, `blockHeading`, `blockPanel`, ...) are unexported. Copying the shell into the invoice package would fork the mail layout and bypass the mail thread's golden tests, so this brief does not do it.

**What has to exist first (the mail thread's brief, new file `go/internal/mail/invoice_issued.go`):** `func BuildInvoiceIssued(publicBaseURL, lang, issuer, number, total, downloadURL string, host HostDetails, stayProperty string) Content` with the Python text and HTML (golden-tested against `mail_notify.build_invoice_issued`), where `Content{Subject, Text, HTML}` is the type the other builders return, and the guest strings above. Also needed: the `{{claim_secret}}` marker (`mail.ClaimSecretMarker`, already exported) and `claim_secret_enc` payload key (unexported `claimSecretKey` in outbox_markers.go; export it or add the helper that sets it).

**What this brief will do once unblocked** (the brief writer then writes the sidecar `send.go`, `send_test.go` and the route test, replays them on the merged tree and sets `Status: todo`):

| Python (routes/invoices.py 961-1001) | Go |
|---|---|
| `_load_invoice`; none: back to `/invoices` with `flash.error.no_such_invoice` | `loadInvoice` (exists, brief 1422) |
| no `buyer_email`: back to the invoice with `invoice.err.no_email` | same |
| `entity = access.entity(invoice.legal_entity_id)`; `token = invoice_links.download_token(id, pdf_sha256)` | `downloadTokenFor` (exists, brief 1424) with `secure.LoadSecret` |
| `url = PUBLIC_BASE_URL + "/invoice/d/" + mail.CLAIM_SECRET_MARKER`; content from `build_invoice_issued(lang=invoice.lang, property_name=entity.name or "UbyHost", number, total=money(total_haler), download_url=url, host=host_details(legal_entity_id), stay_property=_stay_property_name(invoice))` | `mail.BuildInvoiceIssued(...)` (blocked) |
| `payload = guest_payload({"legal_entity_id": ...}, content, lang)` (text, lang, html, `reply_to` = the operator's contact e-mail) and `payload["claim_secret_enc"] = db.encrypt_field(token)` | build the JSON payload; encrypt with `secure.LoadDataKeys(...).EncryptString` |
| `idempotency_key = invoice_issued:<id>:<count of earlier keys LIKE 'invoice_issued:<id>:%'>`; `mail.enqueue(kind="invoice_issued", to_email=buyer_email, subject, payload, owner_user_id)` | `ubyport.EnqueueMail` (exists) with `Payload` |
| `UPDATE invoice SET emailed_at = now`; audit `invoice_sent id=<id>`; back to the invoice with `invoice.sent_flash` | `UPDATE` (emailed_at is not in the issued-row guard), `c.audit`, `c.back` |

Routing and the registration test: add `POST /invoices/{id}/send` to the route table; `TestSendRouteIsNotThere` in `routes_test.go` (brief 1427) and the Python-side line in `register_web_invoices_test.go` are then replaced in the same brief (they name this brief). Personal data: the buyer's e-mail address is the recipient; it is never logged; the token is stored encrypted in the outbox payload and replaces the marker at send time, as in Python.

## 3. Files

Not final: `go/internal/web/invoices/send.go`, `send_test.go`, plus the two test files named above (replace). No other file.

## 4. Steps

Do not run this brief. When the mail thread has merged `BuildInvoiceIssued`, the orchestrator asks the brief writer to finish it (sidecars, hashes, steps) and sets `Status: todo`.

## 5. Do not touch

`go/internal/mail/` (mail thread), everything in brief 1427 §5.

## 6. Commands

None yet.

## 7. Acceptance

None yet.

## 8. Stop and ask

This brief is blocked: STOP at once and write nothing.

## 9. Report

None.

## Risk list (for the reviewer)

When unblocked: the payload (which fields leave the system: the guest's e-mail, the token), the idempotency key (a second click sends a second mail, key suffix 1), `emailed_at`, and that the download URL contains the marker and never the token.

## Owner steps

None now. Ask the mail thread owner for `BuildInvoiceIssued` (this is the only thing missing).
