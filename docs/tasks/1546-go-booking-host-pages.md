# 1546: Go host pages of the booking site (not written)

Status: blocked — not written yet: the host pages need a brief writer to read booking_setup.py, property_page publish/slug code and the photo pipeline (store_photo); nothing here is a rule blocker except the photo re-encode, which needs a decision on stdlib image/jpeg. Do not run.
Depends on: 1540, 1544 | Base commit: none (one big PR) | Branch: the current branch
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier B (host pages, publishing a public page). Review: Opus orchestrator.

**One big PR mode.** Work on the current branch. Never create a branch, never push, never open a PR. Commit `1546 step k` after each step that changes a file. Acceptance checks use `git log --oneline --grep='^1546 step'`, not a fixed base commit.

## 1. Objective

Port the eleven host routes of `payments.py` that no Go handler serves yet, on the host layout (`go/internal/hostweb/layout`).

## 2. Context

Verified against the Go registrations (2026-11-14): none of these has a Go pattern.

| Route | Python function (payments.py) | Notes found while scoping |
|---|---|---|
| `GET /booking-sites` | `booking_sites` 530-551 | redirects to the apartment's page when the host has one active apartment |
| `GET /apartments/{id}/booking-site` | `booking_site_setup` 554-593 | uses `booking_setup.steps`, `can_publish`, `notice_options`, `booking_rails.setup_view`, `booking_manage.host_rows`, an iCal token (Go has `ICalToken`), a QR of the page URL (`payments.QRDataURI` of 1543) and `property_page.ensure_slug` (slug minting, not in Go) |
| `POST /apartments/{id}/booking-site` | `booking_site_save` 596-632 | publish, unpublish, calendar-done, settings (`booking_setup.parse_form`, `booking_site.save_settings`) |
| `POST .../booking-site/pay` | `booking_site_pay` 635-656 | `booking_rails.parse_form` (needs `stay_fees.revolut_link_ok`, Go has `RevolutLinkOK`) |
| `POST .../booking-site/confirm`, `.../decline` | `_direct_action` 659-695, `booking_direct.confirm/decline` | creates the reservation and mails the guest |
| `POST .../booking-site/cancel` | `_direct_action` / `booking_cancel.cancel(by_host=True)` | refund and invoice: see 1553 |
| `GET /apartments/{id}/page`, `POST` it, `POST .../page/photo-move`, `.../photo-delete` | `property_page_review`, `_save`, `_photo_move`, `_photo_delete` 412-518 | photo upload re-encodes and strips EXIF (`property_page.store_photo`, pipeline 0343) |

Path collisions to close in the same work: `/apartments/{id}/page` and `/apartments/{id}/booking-site` carry GET and POST in Python; Go must serve both before either path is switched. Existing Go `properties` pages own `/apartments/*` patterns: check `go/internal/web/properties/` for overlaps before registering.

Rules for the writer: host UX gate (rule 10), design-system checklist, hostweb layout read-only, no Python edits, tenancy as `access.owner_id` (`_bsite_apartment` checks `owner_user_id`).

## 3. Files

None yet (blocked).

## 4. Steps

None yet.

## 5. Do not touch

Everything. This brief must not be run.

## 6. Commands

None.

## 7. Acceptance

- [ ] Not applicable until written.

## Risk list (for the reviewer)

- Ownership check on every apartment route; publishing a page; photo files.

## Owner steps

None.


## 8. Stop and ask

Stop, and write the report, if: a file outside section 3 needs a change; a step is unclear; a new dependency seems needed; you reach 25 tool calls or about 50k tokens (report as `blocked`); you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1546-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with its last 5 lines, section 7 ticked, deviations, questions, owner steps left.
