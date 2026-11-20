# 1428 report

Status: review

## PR

Branch `cursor/1428-go-mail-invoice-issued-dff7`.

## Commands

- `go test ./internal/mail/... -count=1` — ok
- `pytest tests/test_go_invoice_issued_golden.py` — 1 passed

## Acceptance

- Six golden cases byte-equal to Python `build_invoice_issued`.
- `ClaimSecretPayloadKey` exported in `outbox_markers.go`.
- No routes; no `UBYHOST_GO_PATHS`.

## Unblocks

Brief 1429 (`POST /invoices/{id}/send`).