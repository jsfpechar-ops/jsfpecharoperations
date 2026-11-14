# 1545: Go QR pages: host preview and guest bank-transfer page (blocked)

Status: blocked — the guest page /pay/{id}/{token} needs the guest-language catalog (App/app/i18n.py, language rule in routes/guest.py _language: ?lang, cookie, then Accept-Language) and no Go package has it; it belongs to the guest-registration thread. Written as a plan only; do not run.
Depends on: 1540 and the guest-language port | Base commit: none (one big PR) | Branch: the current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier B (guest-facing bank details). Review: Opus orchestrator.

**One big PR mode.** Work on the current branch. Never create a branch, never push, never open a PR. Commit `1545 step k` after each step that changes a file. Acceptance checks use `git log --oneline --grep='^1545 step'`, not a fixed base commit.

## 1. Objective

Serve `GET /payments/qr/{id}` (host QR preview) and `GET /pay/{id}/{token}` (guest bank-transfer page) from Go and close the collision with the PNG routes of `register_web.go`, so `/payments/qr/*` and `/pay/*` can be switched as whole paths.

## 2. Context

Verified facts (2026-11-14):

- Python: `App/app/routes/payments.py` `payment_request_qr` 386-409, `_guest_qr_row` 761-767, `guest_qr_page` 782-808, template `payments_qr.html` (14 lines). The two PNG routes are live on Go (`register_web.go` lines `GET /payments/qr/{file}` and `GET /pay/{id}/{file}`); Go's ServeMux panics on a second registration of those patterns, so the HTML pages need a dispatcher, not new patterns.
- Blocker: the guest page shows `i18n.translator(_language(request))("pay_no_account")` when the host has no bank account. That string comes from the guest catalog (`App/app/i18n.py`, many languages) and the language is chosen by `routes/guest.py` `_language` (`?lang`, cookie, then the browser's `Accept-Language`). Go has neither (checked: no Go file mentions Accept-Language or a guest catalog). The page body itself uses `host_i18n` keys (`payments.qr.*`, `payments.status.paid`, `payments.czk`), which `go_host_i18n.py` can generate.
- Everything else exists: `payments.qrPayload`, `guestToken`, `QRPNGHandler`, `GuestQRPNGHandler` (`go/internal/payments/qrpng.go`, `paylink_routes.go`), the guest shell of 1540, `payments.QRDataURI` of 1543.

Design for whoever unblocks this (not to be run as is):

1. New file `go/internal/payments/qrpage.go`: exported `HostQRPage` (owner and rail checks as `payment_request_qr`, refusal flashes `payments.err.invalid` / `payments.err.no_iban` with `fix=bank` through `hostweb.Back`) and `GuestQRPage` (rail `qr`, status not `cancelled`, `hmac.Equal` on `guestToken`, `X-Robots-Tag: noindex`).
2. Two dispatchers wrapping the existing PNG handlers: `/payments/qr/{file}`: `<digits>.png` goes to `QRPNGHandler`, anything else to the page; `/pay/{id}/{file}`: a name ending `.png` goes to `GuestQRPNGHandler`, anything else is the token for the page. The edit to `register_web.go` is two lines and changes nothing for `.png` requests (live traffic).
3. The no-account sentence for the guest page: a generated catalog of the `pay_no_account` key for the languages `i18n.py` has, and the Accept-Language rule, taken from the guest thread's Go package once it exists.

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

- The dispatcher edit in `go/cmd/ubyhost-web/register_web.go` (live PNG routes).
- Token check on the guest page (`hmac.Equal`, same 404 for every refusal).

## Owner steps

1. Keep `UBYHOST_GO_PATHS` entries for these two areas in the `*.png` form (`/payments/qr/*.png`, `/pay/*/*.png`) so the HTML pages stay on Python.


## 8. Stop and ask

Stop, and write the report, if: a file outside section 3 needs a change; a step is unclear; a new dependency seems needed; you reach 25 tool calls or about 50k tokens (report as `blocked`); you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1545-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.
