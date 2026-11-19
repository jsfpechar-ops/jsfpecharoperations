# 1860 report: Port GET /reservations/{id} to Go, part 1: data and view model

Status: blocked
Branch: `task/1860-1864-stay-page` | Base: `origin/main` a734a72f4 (brief written at 1387c0cf4)

## Blocked at step 0 (anchors)

Step 0 requires every Go helper named in §2 to exist and be exported. Six of the
eight do not. Step 0 says: "If a helper Python uses is unexported or missing in Go,
STOP (do not copy or export it; that is a file outside §3)." §8 repeats it: "a Python
helper has no exported Go equivalent". The series stops here, before any file under
`go/` is written.

### Missing or unexported

| §2 claim | Reality at a734a72f4 (and at 1387c0cf4) |
|---|---|
| `go/internal/calendar/progress.go` — reservation progress, deadline anchor | File exists; every func is unexported: `localNow`, `expectedCount`, `progress`, `progressWith`, `anchorDate`, `filing`, `stayCell`. No `ReservationProgress`, no `ReservationDeadlineAnchor`. |
| `go/internal/web/stays/guests.go` — identity verified | No exported func. Only unexported `loadProgGuests`, `displayGuests`, and an `identityVerifiedAt` field on unexported structs. |
| `go/internal/web/stays/types.go` — send controls | `types.go` holds only the types `Guest`, `Progress`, `Controls`. The function is unexported: `sendControls` at `progress_list.go:233`. |
| `go/internal/web/invoices/store.go` — active invoice for stay | Unexported `activeInvoiceForStay` at `store.go:194`. |
| `go/internal/ubyport/submit.go` — is demo stay | No `IsDemoStay`. Only unexported `isDemoApartment` (`sweep.go:239`), which takes an apartment, not a stay. |
| `go/internal/ubyport/notify.go` — mail enabled | No `MailEnabled` in `ubyport`. The only one in the repo is `billingjob.MailEnabled` (`go/internal/billingjob/send.go:82`), a different package from the one §2 names. |

### Present and exported (usable as §2 says)

- `validation.GuestIssues`, `validation.GuestIsComplete`, `validation.GuestIsReportable` — `go/internal/validation/validation.go:482,493,498`
- `palette.LinkKey` — `go/internal/palette/linkkey.go:13`
- `deadlines.ReportingDeadline` — `go/internal/deadlines`, used at `calendar/progress.go:178`

## Files changed

None under `go/`. Only this report and the brief's status line.

## Commands

`git checkout -b task/1860-1864-stay-page origin/main` + copy of the series briefs and
`docs/design/mockups/simple-white/` from `origin/cursor/simple-white-mockups-8575`:
```
Switched to a new branch 'task/1860-1864-stay-page'
branch 'task/1860-1864-stay-page' set up to track 'origin/main'.
A  docs/tasks/1860-go-stay-detail-data.md
A  docs/tasks/1864-go-stay-detail-switch.md
```
Committed as `1860 step 0` (c0a426977).

Step 0 anchors:
```
ai auth billing booking cleaning customers exports housebook invoices
onboarding privacy properties public settings stayfees stays
---ANCHOR---
4068:@router.get("/reservations/{reservation_id}")
---DEFS---
App/app/claim.py:104:def ensure_row(reservation_id: int):
App/app/door_codes.py:216:def view(reservation: dict, apartment: dict) -> Optional[dict]:
App/app/reporting.py:517:def reservation_progress(...)
App/app/reporting.py:768:def send_controls(...)
App/app/reporting.py:2836:def hand_filing_view(...)
App/app/routes/admin.py:164:def _safe_return_to(request: Request, default: str) -> str:
```
No `staydetail` directory; every Python def found. The Python side is fine — the Go
side is not.

Step 0 helper grep (`^func [A-Z]` over the six named files) returned only:
```
go/internal/validation/validation.go:482:func GuestIssues(...)
go/internal/validation/validation.go:493:func GuestIsComplete(...)
go/internal/validation/validation.go:498:func GuestIsReportable(...)
go/internal/palette/linkkey.go:13:func LinkKey(...)
```
The other four files returned nothing, which is what triggered the wider check above.

## §7 Acceptance

- [ ] `go vet` and `go test` pass; `gofmt -l` empty. — not reached, no code written.
- [ ] DB tests pass with 0 skipped. — not reached.
- [ ] `git diff --stat origin/main` shows only `go/internal/web/staydetail/*`, the status line and the report. — holds: no `go/` file changed.
- [x] The report lists the exported Go helper names used (step 0). — listed above.
- [x] Owner steps: none.

## Deviations

Done: step 0 (series setup + anchors). Left: steps 1 to 7 of 1860, then 1861, 1862,
1863, 1864. Nothing was written beyond the report and the status line.

## Questions

1. Six of the eight helpers §2 calls "already exist" are unexported or absent. Which
   does the owner want?
   - (a) A new brief that adds the missing exported wrappers in their own packages
     (`calendar`, `stays`, `invoices`, `ubyport`) as its own §3, then 1860 as written.
   - (b) A rewritten 1860 whose §3 includes those packages, so one brief owns the
     exports and the new `staydetail` package together.
   - (c) Something else the owner prefers.
2. `MailEnabled` lives in `billingjob`, not `ubyport`. Should 1860 call
   `billingjob.MailEnabled`, or does the brief want a `ubyport` equivalent?
3. `isDemoApartment` takes an apartment; Python's `demo.is_demo_stay` takes the stay.
   Is an apartment-based check acceptable, or does the stay-based one need porting?

## Owner steps

None for this brief. The series is stopped; see the questions above.
