# 1860: Port GET /reservations/{id} to Go, part 1: data and view model

Status: todo
Depends on: none | Base commit: a734a72f4 (origin/main; every Go name below was checked there with `git grep`) | Branch: task/1860-1864-stay-page (series, see below)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens (checkpoint at 60k; hand over per [workflow](../context/workflow.md#when-haiku-reaches-the-cap))
Tier: A (guest data and filing status shown; one write on GET, `ensureClaimRow`)
Pairs with 1861 (template, route, parity). 1860, then 1861, then 1862 (layout, edits `stay_detail.tmpl` only), then 1863 (POST save), then 1864 (switch tooling, the one PR).

> **Series mode (owner 2026-11-19).** One executor runs 1860 to 1864 in order on one branch with no owner check in between; 1864 opens the one PR. Never push to `main`, merge or deploy. Every command ends in `2>&1 | tail -30`. Anchors are quoted from a734a72f4: if one is not found verbatim, STOP and report. Commit each step as `1860 step k`. At the cap: commit, write the report as `blocked` with `Done: steps 0 to k. Left: ...`; a fresh session continues on the same branch.

## Open questions

None. The first run stopped at step 0 because the old §2 named Go helpers that are unexported or missing. Orchestrator decisions 2026-11-19 (final): thin exported wrappers in the helpers' own packages; mail is `billingjob.MailEnabled`; demo is a local `isDemoStay(source)`. Logic is never copied into `staydetail`.

## 1. Objective

Create `go/internal/web/staydetail` with the read side of `GET /reservations/{reservation_id}`: load the owner's stay and build one `View` with every value `reservation_detail.html` reads. No template and no route (1861); values must equal Python's for the same data.

## 2. Context

Rules 1 (filing state, send controls and the hand-filing panel read exactly as Python), 2, 3 (never print guest data), 5, 11.

Python reference, READ-ONLY: `sed -n 4068,4152p App/app/routes/admin.py` (anchor `@router.get("/reservations/{reservation_id}")`). What the template reads (grep of `reservation_detail.html`): `progress.{status, expected, filled, guests, not_registered}`; `row.{guest, issues, complete}` (Python also computes `verified`, `has_passport_photo`, `needs_verification`; the template never reads them, so Go leaves them out); `send_controls.{send_enabled, send_hint_key, pending_count}`; `stay_claim.{state, email_masked, guest_access_locked_at}`; `hand_filing.{count, candidates, filed_at, reference, can_undo, undo_until, default_filed_at}`; `door_code.{state, pin, works_from, works_until}`; `stay_invoice.{id, number}`; `submission.{id, created_at, state, pseudo_stamp, has_receipt}`; plus `check_in`, `deadline`, `return_to`, `guest_link`, `claim_resend.enabled`, `is_demo_stay`.

`access.apartment` uses the same owner predicate as `access.reservation`, so when the stay loads, its apartment loads too: Python's `if apartment else` branches never run on this page and Go has none.

**Go used, verified at a734a72f4.** Call these; never edit the files they live in.

| Python | Go | Where |
|---|---|---|
| `reservation_progress`, `reservation_deadline_anchor`, `deadline_cell`, `send_controls["send_enabled"]` | unexported `loadProgGuests`, `listProgress`, `buildProgress` (gives `Progress.Anchor`, `.Cell`), `sendControls` | `go/internal/web/stays/guests.go:47`, `progress_list.go:44,182,233`; exported by the new `stays.StayProgress` |
| `send_controls["send_hint_key", "pending_count"]` | **none** (`stays.Controls` has only `SendEnabled`) | ported as `stays.sendHint` next to `sendControls` (`reporting.py` 768-845) |
| `guest_issues`, `guest_is_complete` | `validation.GuestIssues(g GuestRow, dateFrom, dateTo string, today time.Time) []Issue`, `validation.GuestIsComplete(...) bool` | `go/internal/validation/validation.go:482,493` |
| `invoices.active_invoice_for_stay` | unexported `activeInvoiceForStay` | `go/internal/web/invoices/store.go:194`; exported by the new `invoices.ActiveInvoiceForStay` |
| `door_codes.view` | `(*doorcodes.Service).View` (exported) takes `doorcodes.Reservation`/`Apartment`; the loaders `loadReservation`, `loadApartment` are unexported | `go/internal/doorcodes/view.go:115,83,99`; exported by the new `(*doorcodes.Service).ViewForStay` |
| `mail.mail_enabled` | `billingjob.MailEnabled() bool` | `go/internal/billingjob/send.go:82` |
| `config.PUBLIC_BASE_URL` | `billingjob.PublicBaseURL() string` | `go/internal/billingjob/send.go:91` |
| `guest_slug.link_key(apartment)` | `palette.LinkKey(ctx, pool, apartmentID int64, internalName, permalinkToken string) (string, error)` | `go/internal/palette/linkkey.go:13` |
| `deadlines.reporting_deadline` | `deadlines.ReportingDeadline(checkIn time.Time) time.Time` | `go/internal/deadlines/deadlines.go:70` |
| `deadlines.local_now`, `_as_utc`, `db.utcnow` | `deadlines.LocalNow`, `ubyport.ParseStoredUTC` (`collect.go:387`), `ubyport.UTCNow` | used in `stays/progress_list.go:140,126`, `ical/reconcile.go:416` |
| `_safe_return_to` = `security.safe_local_path(return_to, default)` | `ai.HavelSafeLocalPath(value, def string) string` | `go/internal/web/ai/havel_pages.go:281` |
| `demo.is_demo_stay(r)` = `(r.source or '') == 'demo'` (`App/app/demo.py:81`) | none; local `isDemoStay` in `types.go` | |
| `claim.ensure_row` (`claim.py:104`), `reporting.hand_filing_view` (`reporting.py:2836`) | none in Go (`git grep` empty) | ported in `panels.go` |

**Pre-written code.** Every file in §3 marked "sidecar" is written in `docs/tasks/1860-files/<repo path>.txt` and was dry-run by the brief writer on a734a72f4 (`gofmt -l` empty, `go vet` clean, `go test` passes for `staydetail`, `stays`, `invoices`, `doorcodes`; 5 new non-DB tests pass). Checksums: `docs/tasks/1860-files/MANIFEST.sha256`. Copy them byte for byte; never retype or edit a copied file. What they hold:

- `stays/detail_export.go`: `StayGuest`, `StayDetail{Progress, Controls, SendHintKey, PendingCount, Guests}`, `StayProgress(ctx, pool, getenv, res stays.Reservation, at) (StayDetail, error)`, which calls `loadProgGuests`, `listProgress`, `buildProgress`, `sendControls` exactly as `row_build.go` does, plus the `sendHint` port.
- `stays/detail_export_test.go`: `TestStayDetailEqualsListHelpers` (wrapper output `reflect.DeepEqual` to `buildProgress`/`sendControls` on a fixture), `TestSendHint` (13 branches).
- `invoices/stay_export.go` + test: `StayInvoice{ID, Number}`, `ActiveInvoiceForStay(ctx, q, id)`; the test checks the wrapper against `activeInvoiceForStay` with a fake row (found, and `pgx.ErrNoRows`).
- `doorcodes/view_stay.go`: `(*Service).ViewForStay(ctx, reservationID, apartmentID)` = `loadReservation` + `loadApartment` + `View`.
- `staydetail/types.go`: `DoorCodeViewer`, `Deps{Pool, Getenv, DoorCodes}`, `GuestRow{Guest, Issues, Complete}`, `Guest{stays.StayGuest; DocType, EnteredBy, LastErrors, RestrictedAt, ManualMarkedAt, ManualReference}`, `Submission`, `View{Reservation, Progress, SendControls, GuestRows, CheckIn, Deadline, Submissions, ReturnTo, GuestLink, StayClaim, ClaimResend, IsDemoStay, HandFiling, StayInvoice, DoorCode}`, `SendControls{SendEnabled, SendHintKey, PendingCount}`, `isDemoStay`.
- `staydetail/load.go`: `Stay{stays.Reservation; ArchivedAt, GuestEmail, HostNote}`, `LoadStay(ctx, pool, ownerID, id) (Stay, bool, error)` (owner predicate `a.owner_user_id IS NOT DISTINCT FROM $2`, as `access.reservation`).
- `staydetail/panels.go`: `StayClaim`, `ensureClaimRow` (select, else insert `unclaimed`/`token_version 0`, then select), `HandFiling`, `handFilingView(rows, now)`.
- `staydetail/panels_test.go`: `TestIsDemoStay`, `TestHandFilingView` (empty, candidates, two marks 2 h and 30 h old, one old mark).

## 3. Files

Python is NOT changed.

| Path | Action | What |
|---|---|---|
| `go/internal/web/stays/detail_export.go`, `detail_export_test.go` | new (sidecar) | `stays` wrapper and `sendHint` |
| `go/internal/web/invoices/stay_export.go`, `stay_export_test.go` | new (sidecar) | `invoices` wrapper |
| `go/internal/doorcodes/view_stay.go` | new (sidecar) | `doorcodes` wrapper |
| `go/internal/doorcodes/view_stay_test.go` | new | step 3 (DB test) |
| `go/internal/web/staydetail/types.go`, `load.go`, `panels.go`, `panels_test.go` | new (sidecar) | types, loader, claim row, hand filing |
| `go/internal/web/staydetail/view.go` | new | step 4: `Build` |
| `go/internal/web/staydetail/view_test.go` | new | step 5 (DB tests) |

No other file may change. No existing function in `stays`, `invoices` or `doorcodes` changes.

## 4. Steps

0. **Branch** (orchestrator decision 5, one call): `git fetch origin task/1860-1864-stay-page cursor/simple-white-mockups-8575 2>&1 | tail -3 && git checkout task/1860-1864-stay-page 2>&1 | tail -3 && git pull origin task/1860-1864-stay-page 2>&1 | tail -3 && git checkout origin/cursor/simple-white-mockups-8575 -- docs/tasks/1860-go-stay-detail-data.md docs/tasks/1861-go-stay-detail-page.md docs/tasks/1862-stay-page-layout.md docs/tasks/1863-go-stay-detail-post.md docs/tasks/1864-go-stay-detail-switch.md docs/tasks/1860-files docs/tasks/1863-files docs/tasks/1864-files 2>&1 | tail -3 && git rm -q docs/tasks/1860-report.md 2>&1 | tail -3; git commit -qm '1860 step 0: refresh briefs' 2>&1 | tail -3; git log --oneline -2 2>&1 | tail -3`. If `git rm` says the report is not there, that is fine.
1. **Anchors** (one call): `ls go/internal/web/staydetail 2>&1 | tail -2; git grep -c 'func loadProgGuests(ctx context.Context, pool \*pgxpool.Pool, ids \[\]int64, getenv func(string) string)\|func buildProgress(s listStay, guests \[\]progGuest, at time.Time) Progress\|func sendControls(res Reservation, automationMode string, p listProg, guests \[\]progGuest) Controls\|^func activeInvoiceForStay(ctx context.Context, q interface {\|func (s \*Service) loadReservation(ctx context.Context, id int64) (\*Reservation, error)\|func (s \*Service) loadApartment(ctx context.Context, id int64) (\*Apartment, error)\|^func MailEnabled() bool\|^func PublicBaseURL() string\|^func HavelSafeLocalPath(value, def string) string\|^func LinkKey(ctx context.Context, pool \*pgxpool.Pool, apartmentID int64, internalName, permalinkToken string)\|^func ReportingDeadline(checkIn time.Time) time.Time' -- go/internal 2>&1 | tail -12`. Expect "No such file" for `staydetail` and these counts: `stays/guests.go:1`, `stays/progress_list.go:2`, `invoices/store.go:1`, `doorcodes/view.go:2`, `billingjob/send.go:2`, `ai/havel_pages.go:1`, `palette/linkkey.go:1`, `deadlines/deadlines.go:1`, `ubyport/collect.go:1` (12 in all). Anything else: STOP and list it.
2. **Copy and verify the sidecars** (one call): `S=docs/tasks/1860-files; for f in $(cd $S && find . -name '*.txt' | sed 's|^\./||; s|\.txt$||'); do mkdir -p "$(dirname "$f")" && cp "$S/$f.txt" "$f"; done; sha256sum -c $S/MANIFEST.sha256 2>&1 | tail -10; cd go && gofmt -l internal/web/staydetail internal/web/stays internal/web/invoices internal/doorcodes 2>&1 | tail -5; go vet ./internal/web/staydetail/ ./internal/web/stays/ ./internal/web/invoices/ ./internal/doorcodes/ 2>&1 | tail -10; go test ./internal/web/staydetail/ ./internal/web/stays/ ./internal/web/invoices/ ./internal/doorcodes/ 2>&1 | tail -10`. Expect 9 `OK`, no gofmt output, vet clean, four `ok`. Any failure: STOP (the sidecars are dry-run; a failure means the base moved).
3. **`doorcodes/view_stay_test.go`** (package `doorcodes`, DB test). Find the fixtures: `grep -n '^package\|func testPool\|INSERT INTO apartment\|INSERT INTO reservation' go/internal/doorcodes/issue_test.go 2>&1 | tail -10`. If it is not `package doorcodes`, STOP. Write `TestViewForStay`: `pool := testPool(t)`; (a) `(&Service{Pool: pool}).ViewForStay(ctx, 999999, 999999)` returns `nil, nil`; (b) insert one apartment with `lock_provider = 'ttlock'` and one `source = 'manual'` stay, copying that file's INSERT column lists; `s := &Service{Pool: pool, Settings: Settings{Enabled: true, Live: true}}`; `r, _ := s.loadReservation(ctx, rid)`; `a, _ := s.loadApartment(ctx, aid)`; `want, werr := s.View(ctx, *r, *a)`; `got, gerr := s.ViewForStay(ctx, rid, aid)`; fail unless `reflect.DeepEqual(got, want)` and both errors are nil. Command: `cd go && go vet ./internal/doorcodes/ 2>&1 | tail -10; go test ./internal/doorcodes/ -run TestViewForStay -v 2>&1 | tail -10`.
4. **`staydetail/view.go`**: one function, `func Build(ctx context.Context, d Deps, ownerID, id int64, rawReturnTo string, at time.Time) (View, bool, error)`. Each value comes from the §2 table and nothing else. In this order:
   - `s, ok, err := LoadStay(ctx, d.Pool, ownerID, id)`. If not ok, return `View{}, false, nil`.
   - `det, err := stays.StayProgress(ctx, d.Pool, d.Getenv, s.Reservation, at)`.
   - Guest extras keyed by id: `SELECT id, COALESCE(doc_type,''), COALESCE(entered_by,''), COALESCE(last_errors,''), COALESCE(restricted_at,''), COALESCE(manual_marked_at,''), COALESCE(manual_reference,'') FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`.
   - One `GuestRow` per `det.Guests` item, in that order: `Issues = validation.GuestIssues(g.Row, s.DateFrom, s.DateTo, today)` and `Complete = validation.GuestIsComplete(g.Row, s.DateFrom, s.DateTo, today)`, where `today` is the UTC date of `at` at 00:00 UTC (as `stays.StayProgress`).
   - `Progress = det.Progress`; `SendControls{det.Controls.SendEnabled, det.SendHintKey, det.PendingCount}`.
   - `CheckIn` is `&det.Progress.Anchor` when `det.Progress.HasAnchor`; then `Deadline = deadlines.ReportingDeadline(*CheckIn)`.
   - Submissions: the SQL below with `$1, $2, $3` = id, id, `s.ApartmentID`.
   - `ReturnTo = ai.HavelSafeLocalPath(rawReturnTo, "/reservations")`.
   - `GuestLink = billingjob.PublicBaseURL() + "/l/" + key + "/" + strconv.FormatInt(id, 10)`, where `key, err := palette.LinkKey(ctx, d.Pool, s.ApartmentID, s.InternalName, s.PermalinkToken)`.
   - `StayClaim, err = ensureClaimRow(ctx, d.Pool, id)`; `IsDemoStay = isDemoStay(s.Source)`.
   - `ClaimResend = billingjob.MailEnabled() && !IsDemoStay && StayClaim.State == "claimed" && StayClaim.GuestAccessLockedAt == ""`.
   - `HandFiling` is `HandFiling{}` for a demo stay, else `handFilingView(rows, at)`.
   - `StayInvoice, err = invoices.ActiveInvoiceForStay(ctx, d.Pool, id)`.
   - `DoorCode, err = d.DoorCodes.ViewForStay(ctx, id, s.ApartmentID)` only when `d.DoorCodes != nil`.

   Any `err` is returned as `View{}, false, err`.

```sql
SELECT id, COALESCE(created_at,''), COALESCE(state,''), COALESCE(pseudo_stamp,''),
       (receipt_pdf IS NOT NULL AND TRIM(receipt_pdf) != '') AS has_receipt
FROM submission WHERE id IN (
  SELECT DISTINCT submission_id FROM guest WHERE reservation_id = $1 AND submission_id IS NOT NULL
  UNION SELECT DISTINCT receipt_submission_id FROM guest
  WHERE reservation_id = $2 AND receipt_submission_id IS NOT NULL
) AND apartment_id = $3 ORDER BY created_at DESC
```

   Command: `cd go && go vet ./internal/web/staydetail/ 2>&1 | tail -10`.
5. **`staydetail/view_test.go`** (DB tests; skip without `UBYHOST_TEST_DATABASE_URL`; copy the pool helper of `go/internal/web/stays/query_test.go`, renamed `stayDetailPool`). Cases:
   - `LoadStay`: the owner's stay is found; another owner's stay is not found; an archived stay is still found.
   - `Build` on a stay whose guest has `receipt_submission_id` on a second submission lists both, newest first; another apartment's submission is not listed.
   - `ensureClaimRow` called twice leaves `SELECT COUNT(*) FROM reservation_claim WHERE reservation_id = $1` at 1 and the state `unclaimed`.

   Never print guest values. Command: `cd go && go vet ./internal/web/staydetail/ 2>&1 | tail -10; go test ./internal/web/staydetail/... 2>&1 | tail -10; gofmt -l internal/web/staydetail internal/doorcodes 2>&1 | tail -5`.

Hand-over point if capped: steps 0 to 3 first; 4 and 5 may continue in `1860-cont-1.md`.

## 5. Do not touch

- Every file under `App/` and `go/cmd/`.
- Every existing file in `go/internal/web/stays/`, `go/internal/web/invoices/` and `go/internal/doorcodes/`; add only the new files in §3.
- `go/internal/calendar/`: its progress copy serves the alert job. The page uses the `stays` copy, which the list already matches to Python.
- Call only, never edit: `go/internal/ubyport/`, `billingjob/`, `web/ai/`, `palette/`, `deadlines/`.
- `go/internal/hostweb/layout/`, Caddy and `UBYHOST_GO_PATHS`.
- The copied sidecar files after step 2.

No new dependency. Never print guest names, birth dates, emails or PINs (rule 3).

## 6. Commands

From `go/`:
- `go vet ./internal/web/staydetail/... ./internal/web/stays/... ./internal/web/invoices/... ./internal/doorcodes/ 2>&1 | tail -30`
- `go test` on the same packages, `2>&1 | tail -30`; then the same `go test` again with `UBYHOST_TEST_DATABASE_URL=...` for the local Postgres
- `gofmt -l internal/web/staydetail internal/web/stays internal/web/invoices internal/doorcodes 2>&1 | tail -30` (prints nothing)

Root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Say how many tests skipped.

## 7. Acceptance

- [ ] `sha256sum -c` gives 9 `OK`; vet, test and gofmt are clean; the existing `stays`, `invoices` and `doorcodes` tests still pass.
- [ ] `TestStayDetailEqualsListHelpers`, `TestSendHint`, `TestActiveInvoiceForStayWrapsUnexported`, `TestIsDemoStay` and `TestHandFilingView` pass without a database.
- [ ] With the test database, 0 skipped: `TestViewForStay`, owner scope, the submissions union, and the claim row created once.
- [ ] `git diff --stat origin/main` shows only the §3 files, the refreshed series briefs and folders (step 0), this brief's status line and the report.
- [ ] Owner steps: none.

## 8. Stop and ask

As [TEMPLATE](TEMPLATE.md) §8, plus:
- step 1 finds other counts than the expected ones;
- a sidecar fails `sha256sum`, vet or test;
- a step would change an existing function;
- a Python value cannot be reproduced exactly (say which key).

## 9. Report

`docs/tasks/1860-report.md`, 600 tokens at most: files, each command's last 5 lines, §7 ticked, skipped count, deviations, questions.

## Risk list (for the reviewer)

- `stays/detail_export.go`: check the `sendHint` branch order against `reporting.py` 768-845, and that pending comes from `p.reportable`.
- `doorcodes/view_stay.go`.
- `staydetail/load.go`: the owner scope.
- `panels.go`: the `ensureClaimRow` write on GET, and the 24 h undo window.
- The `Build` order in `view.go`.

**Known difference (not fixed here; for the orchestrator).** The existing `stays.sendControls` computes `send_enabled` from `pendingReportable(guests)`, which counts all live guests. Python uses `pending_reportable(progress["reportable"])`, which counts complete guests only. The two differ only for a `failed` stay that also has an incomplete, signed, foreign guest: Go shows Send, Python does not. The wrapper keeps `sendControls` as it is (no logic change), so the stays list and the stay page agree with each other. The 1861 parity fixtures do not include that case.

## Owner steps

None.
