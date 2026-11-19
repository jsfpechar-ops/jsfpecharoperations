# 1860: Port GET /reservations/{id} to Go, part 1: data and view model

Status: todo
Depends on: none | Base commit: 1387c0cf4 (origin/main) | Branch: task/1860-go-stay-detail-data
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k; hand over per [workflow](../context/workflow.md#when-haiku-reaches-the-cap))
Tier: A (guest data and filing status shown; one write on GET, see step 6)
Pairs with 1861 (template, route, parity). 1860, then 1861, then 1862 (layout change, edits `stay_detail.tmpl` only).

> **One PR mode.** Commit each step as `1860 step k`. Never push, merge or deploy. Every command ends in `2>&1 | tail -30`. Anchors are quoted from the tip: if one is not found verbatim, STOP and report.

## Open questions

See 1861 "Open questions" (POST and the Caddy selector). Nothing in this brief depends on them: 1860 adds Go code that no route calls yet.

## 1. Objective

Create `go/internal/web/staydetail` with the read side of `GET /reservations/{reservation_id}`: load the stay for the signed-in owner, and build one `View` holding every value `reservation_detail.html` reads. No template and no route (1861); the output must equal Python's context for the same data.

## 2. Context

Rules 1 (filing correctness: guest submit states, send controls and the hand-filing panel must be read exactly as Python does), 2 (no new personal-data field), 5 (SQL Postgres-portable, through the Go db helpers the `stays` package uses), 11.

Python reference, READ-ONLY. `App/app/routes/admin.py` is 5510 lines: read only with `sed -n 4068,4152p App/app/routes/admin.py`. Anchor: `@router.get("/reservations/{reservation_id}")`. The context it builds (verbatim keys, all required):

```text
reservation      access.reservation(request, id, "r.*, a.internal_name, a.permalink_token, a.automation_mode, a.submit_after_hours")  -> 404 if None
progress         reporting.reservation_progress(reservation)
apartment        access.apartment(request, reservation["apartment_id"])
send_controls    reporting.send_controls(reservation, apartment, progress) if apartment else {}
guest_rows[]     per progress["guests"]: guest, issues=reporting.guest_issues(guest, reservation), complete=reporting.guest_is_complete(...),
                 verified=reporting.guest_identity_verified(guest), has_passport_photo=..., needs_verification=validation.guest_is_reportable(nat) and not verified
check_in         reporting.reservation_deadline_anchor(reservation)
deadline         deadlines.reporting_deadline(check_in) if check_in else None
submissions      SQL below, verbatim
return_to        _safe_return_to(request, "/reservations")
guest_link       f"{config.PUBLIC_BASE_URL}/l/{guest_slug.link_key(apartment) if apartment else reservation['permalink_token']}/{reservation_id}"
stay_claim       claim.ensure_row(reservation_id)
claim_resend     enabled = mail.mail_enabled() and not demo.is_demo_stay(r) and stay_claim["state"] == claim.CLAIMED and not stay_claim["guest_access_locked_at"]
is_demo_stay     demo.is_demo_stay(reservation)
hand_filing      {"count": 0, "candidates": 0} if demo stay else reporting.hand_filing_view(progress)
stay_invoice     invoices.active_invoice_for_stay(reservation_id)
door_code        door_codes.view(reservation, apartment) if apartment else None
```

Submissions SQL (copy the text exactly; `?` becomes the placeholder style of the Go helper in `go/internal/web/stays/query.go`):

```sql
SELECT id, created_at, state, pseudo_stamp,
       (receipt_pdf IS NOT NULL AND TRIM(receipt_pdf) != '') AS has_receipt
FROM submission WHERE id IN (
  SELECT DISTINCT submission_id FROM guest WHERE reservation_id = ? AND submission_id IS NOT NULL
  UNION SELECT DISTINCT receipt_submission_id FROM guest
  WHERE reservation_id = ? AND receipt_submission_id IS NOT NULL
) AND apartment_id = ? ORDER BY created_at DESC
```

Go helpers that already exist (found by grep at the base commit; confirm in step 0, never copy them): `go/internal/calendar/progress.go` (reservation progress, deadline anchor, reporting deadline), `go/internal/validation/validation.go` (guest issues, guest is complete, guest is reportable), `go/internal/web/stays/guests.go` (identity verified), `go/internal/web/stays/types.go` (send controls), `go/internal/palette/linkkey.go` (link key), `go/internal/web/invoices/store.go` (active invoice for stay), `go/internal/ubyport/submit.go` (is demo stay), `go/internal/ubyport/notify.go` (mail enabled). Not found in Go at the base commit: `reporting.hand_filing_view`, `door_codes.view`, `claim.ensure_row`, `_safe_return_to`. Those four are ported here, verbatim, from the Python named in step 0.

## 3. Files

Python is NOT changed (read-only reference; no go-first exception needed).

| Path | Action | What |
|---|---|---|
| `go/internal/web/staydetail/load.go` | new | `type Stay`, `LoadStay(ctx, pool, ownerID, id int64) (Stay, bool, error)`: the `access.reservation` SELECT with the four apartment columns, owner-scoped exactly as Python `access.reservation` |
| `go/internal/web/staydetail/view.go` | new | `type View` (one field per context key in §2, same names in Go case: `Reservation, Progress, SendControls, GuestRows, CheckIn, Deadline, Submissions, ReturnTo, GuestLink, StayClaim, ClaimResend, IsDemoStay, HandFiling, StayInvoice, DoorCode`), `func Build(ctx, deps, ownerID, id int64, r *http.Request) (View, bool, error)` |
| `go/internal/web/staydetail/panels.go` | new | ports of `hand_filing_view`, `door_codes.view`, `claim.ensure_row`, `_safe_return_to` |
| `go/internal/web/staydetail/view_test.go`, `panels_test.go` | new | table tests; DB tests skip without `UBYHOST_TEST_DATABASE_URL` like `go/internal/web/stays/query_test.go` |

No other file may change.

## 4. Steps

0. Anchors (one call): `cd /agent/repos/jsfpecharoperations 2>/dev/null || true; ls go/internal/web | tail -30; grep -nF '@router.get("/reservations/{reservation_id}")' App/app/routes/admin.py; grep -rn 'def hand_filing_view\|def view(\|def ensure_row\|def _safe_return_to\|def send_controls\|def reservation_progress' App/app/*.py App/app/routes/admin.py 2>&1 | tail -30`. Expect no `staydetail` dir and one line per def. If `staydetail` exists or a def is missing, STOP. Then `grep -n '^func [A-Z]' go/internal/calendar/progress.go go/internal/validation/validation.go go/internal/web/stays/guests.go go/internal/web/stays/types.go go/internal/palette/linkkey.go go/internal/web/invoices/store.go 2>&1 | tail -30` and write the exported names you will call into the report. If a helper Python uses is unexported or missing in Go, STOP (do not copy or export it; that is a file outside §3).
1. `load.go`: read `def reservation` in `App/app/access.py` (grep the line, read 40 lines). Port the SELECT and its owner filter verbatim with the columns `r.*, a.internal_name, a.permalink_token, a.automation_mode, a.submit_after_hours`. Unknown id or another owner's stay returns `ok=false` (the handler answers 404, as Python `HTTPException(404)`). Test: own stay found; other owner's stay not found; archived stay still found (Python does not filter it). Command: `cd go && go test ./internal/web/staydetail/... 2>&1 | tail -30`.
2. `view.go` progress and guest rows: call the Go progress helper, then build one `GuestRow{Guest, Issues, Complete, Verified, HasPassportPhoto, NeedsVerification}` per progress guest in the same order. `NeedsVerification = GuestIsReportable(nationality) && !Verified`. Same command.
3. `view.go` check-in, deadline, submissions (SQL in §2), stay invoice, guest link (`PUBLIC_BASE_URL` read through the `getenv` the handler gets, `+"/l/"+linkKey+"/"+id`; with no apartment use `permalink_token`). Test: a stay whose guest has `receipt_submission_id` on another submission lists both, newest first; a submission of another apartment is not listed.
4. `view.go` send controls and demo: `SendControls` only when the apartment loaded, else the zero value (Python `{}`: every field false/empty). `HandFiling` is `{Count:0, Candidates:0}` for a demo stay.
5. `panels.go` `safeReturnTo`: port `_safe_return_to` verbatim (read it with the grep line from step 0 plus 25 lines). Table test: missing returns `/reservations`; `//evil.example` and `https://evil.example` return `/reservations`; `/reservations?range=past` is kept.
6. `panels.go` `ensureClaimRow`: port `claim.ensure_row` verbatim, including its INSERT when the row is missing (Python writes on this GET; keep it, or later claim flows see no row). It must be idempotent: two calls give one row. Then `ClaimResend.Enabled` exactly as §2.
7. `panels.go` `handFilingView` and `doorCodeView`: port `reporting.hand_filing_view(progress)` and `door_codes.view(reservation, apartment)` verbatim, field names as the template reads them: `count, candidates, filed_at, reference, can_undo, undo_until, default_filed_at` and `state, pin, works_from, works_until`. Times in the zone Python uses (copy its conversion). Test each branch of each function once. Command: `cd go && go vet ./internal/web/staydetail/... 2>&1 | tail -30; go test ./internal/web/staydetail/... 2>&1 | tail -30; gofmt -l internal/web/staydetail | tail -30` (gofmt prints nothing).

Hand-over point if capped: steps 1 to 4 are the core; 5 to 7 may continue in `1860-cont-1.md`.

## 5. Do not touch

Every file under `App/`; `go/cmd/`; `go/internal/ubyport/` and every other existing Go package (call their exported functions only); `go/internal/hostweb/layout/`; Caddy files; `UBYHOST_GO_PATHS`; templates (1861). No new dependency. Never print guest names, birth dates, emails or PINs in test output or the report (rule 3).

## 6. Commands

From `go/`: `go vet ./internal/web/staydetail/... 2>&1 | tail -30`; `go test ./internal/web/staydetail/... 2>&1 | tail -30`; `gofmt -l internal/web/staydetail 2>&1 | tail -30` (empty). With the local Postgres: `UBYHOST_TEST_DATABASE_URL=... go test ./internal/web/staydetail/... 2>&1 | tail -30`. Root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Say how many tests skipped.

## 7. Acceptance

- [ ] `go vet` and `go test` pass; `gofmt -l` empty.
- [ ] With the test database: the DB tests pass with 0 skipped (owner-scope, submissions union, claim row idempotent, hand filing and door code branches).
- [ ] `git diff --stat origin/main` shows only `go/internal/web/staydetail/*`, this brief's status line and the report.
- [ ] The report lists the exported Go helper names used (step 0).
- [ ] Owner steps: none.

## 8. Stop and ask

As [TEMPLATE](TEMPLATE.md) §8, plus: a Python helper has no exported Go equivalent; porting a function would need more than the function body named in step 0 (another module's private helper); a Python value cannot be reproduced exactly (say which key).

## 9. Report

`docs/tasks/1860-report.md`, 600 tokens at most: files, each command's last 5 lines, §7 ticked, the helper names, skipped count, deviations, questions.

## Risk list (for the reviewer)

`load.go` (owner scope), `panels.go` (`ensureClaimRow` write, `handFilingView` undo window), the guest-row block of `view.go`.

## Owner steps

None.
