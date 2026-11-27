# 2095: Go duplicate-guest prevention, host alert, and auto-filing guard

Status: todo
Depends on: 2091 | Base commit: 52c418cf5 | Branch: task/2095-go-duplicate-guest-prevention-and-alert
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Stop the real production failure where a guest accidentally registers themselves twice instead of entering the second guest: block exact same-person re-submissions on the Go guest form, raise a `duplicate_guest_in_stay` host warning alert + email (zero guest PII in alert text/logs) whenever duplicate guest rows exist on a stay, and hold the duplicate row(s) out of automatic UbyPort filing while still filing the first row on time.

## 2. Context

- **Tier B (Go guest form, host alerts, UbyPort collect guard):** Go only — never touch `App/` (owner 2026-11-27).
- Plan: `docs/plans/checkin-anchored-auto-filing.md`.
- **Privacy hard rule (AGENTS.md #2 & #3):** Never write guest names, birth dates, or document numbers into `alert.message`, `alert.detail`, `alert.params`, or logs. Alert text says only property/dates and that duplicate guest records were found on the stay.
- **Duplicate matching rules (shared pure helper `go/internal/ubyport/duplicate_guest.go`):**
  - Normalize helper: `normText(s)` = lowercase + trim + collapse internal whitespace; `normDoc(s)` = uppercase + remove spaces and hyphens.
  - **`IsSamePerson(a, b GuestIdentity) bool`** (used to **hard-block** on guest form AND hold duplicate auto-filing):
    - Both non-empty `normText(surname)`, `normText(first_name)`, and `birth_date` match; **OR**
    - Both non-empty `normDoc(doc_number)` and `birth_date` match.
    - *(Never false-positives on parent + child sharing a passport because `birth_date` and `first_name` differ.)*
  - **`IsPossibleDuplicate(a, b GuestIdentity) bool`** (used for **host alert** — catches both exact duplicates AND same `doc_number + nationality` even if a birth date typo occurred):
    - `IsSamePerson(a, b)` **OR** (both non-empty `normDoc(doc_number)` and `normText(nationality)` match).
- **Three layers:**
  1. **Layer 1 — Guest form block (`go/internal/web/guest/form_save.go`):** before inserting or updating a guest on `resID`, decrypt all other live (`archived_at IS NULL AND id != existingID`) guests of `resID` and check `ubyport.IsSamePerson`. If matched, refuse save (HTTP 400 re-render with field-level/form error in guest language: *"This guest is already registered for this stay. Please enter the next guest's details instead."*).
  2. **Layer 2 — Host alert + email (`duplicate_guest_in_stay`):**
     - Check live guests of a stay on host guest save/edit (`go/internal/web/stays/guest_edit.go`), on guest save if `IsPossibleDuplicate` (non-blocking same-doc warning), AND inside `go/internal/calendar/deadlines_job.go` (catches stays already in Postgres before this deploy!).
     - Raise warning alert `duplicate_guest_in_stay` (`dedupe_key = "duplicate_guest_in_stay:<resID>"`, `apartment_id`, `reservation_id`, zero guest PII).
     - Enqueue one host email (`kind = "duplicate_guest_in_stay"`, idempotency key `duplicate_guest_in_stay:<resID>:<sorted-dup-ids>`) linking straight to `/reservations/<resID>`.
     - Auto-resolve `duplicate_guest_in_stay:<resID>` as soon as no live duplicate pair remains on that stay.
     - Register `duplicate_guest_in_stay` in `go/internal/hostweb/layout/alerts.go` (`computedKinds`, `reasonKinds`, `switch a.Kind`) + `layout/i18n.json` (`cs`/`en`/`vi`) + `go/internal/web/auth/opspage/i18n.json`.
  3. **Layer 3 — Auto-filing duplicate guard (`go/internal/ubyport/collect.go`):**
     - In `CollectSendable`, for each reservation, track the lowest-`id` live guest for each `IsSamePerson` group.
     - On automatic sends (`!o.IgnoreAutomation`), **allow the lowest-`id` row to file normally** and **skip any higher-`id` duplicate row** (so Guest #1 is still legally filed on time while UbyPort is not hit with a guaranteed code `150` duplicate error). Manual host send (`IgnoreAutomation: true`) remains under host control.

Verbatim excerpts to match before editing:

`go/internal/hostweb/layout/alerts.go`:
```go
var computedKinds = map[string]bool{
	"deadline": true, "guest_incomplete_checkin": true, "headcount_mismatch": true,
	"dates_changed_resign": true, "moved_after_report": true, "submission_stuck": true,
	"job_failed": true, "feed_incomplete": true, "feed_duplicate_uid": true, "feed_recurring_event": true,
}
```
```go
var reasonKinds = map[string]bool{"deadline": true, "guest_incomplete_checkin": true, "headcount_mismatch": true}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/ubyport/duplicate_guest.go` | create | `GuestIdentity`, `IsSamePerson`, `IsPossibleDuplicate`, `DuplicateGuestIDs(guests)` pure helpers |
| `go/internal/ubyport/duplicate_guest_test.go` | create | Unit tests covering identical name+DOB, identical doc+DOB, identical doc+nationality, parent+child different DOB, whitespace/hyphen/case normalization, lowest-ID kept |
| `go/internal/ubyport/collect.go` | edit | Skip higher-`id` `IsSamePerson` duplicate rows during automatic sends (`!o.IgnoreAutomation`) |
| `go/internal/ubyport/collect_test.go` | edit | Test that on a stay with two identical guests, automatic `CollectSendable` returns only the first guest (lowest `id`) |
| `go/internal/web/guest/form_save.go` | edit | Before insert/update, check existing live guests on `resID` with `ubyport.IsSamePerson`; refuse with localized error when duplicate; trigger/resolve `duplicate_guest_in_stay` alert for `IsPossibleDuplicate` |
| `go/internal/web/guest/i18n.json` | edit | Add localized duplicate-guest form error string across all supported guest languages (no em-dashes) |
| `go/internal/web/guest/form_save_test.go` | edit | Add test verifying submitting the same person twice on one stay is refused (HTTP 400) while a second distinct guest succeeds |
| `go/internal/calendar/duplicate_guest.go` | create | `RunDuplicateGuestCheck(ctx, pool, getenv, at)`: scans active non-demo stays with >=2 live guests, decrypts identities, raises/resolves `duplicate_guest_in_stay` alerts and queues one host email per duplicate set (zero PII in alert/mail) |
| `go/internal/calendar/deadlines_job.go` | edit | Wire `RunDuplicateGuestCheck` into `RunDeadlinesJob` (errors logged without blocking `watchdog` or `stalled` heartbeat) |
| `go/internal/calendar/duplicate_guest_test.go` | create | DB tests verifying existing duplicate stay raises alert + queues 1 email, repeat run is idempotent, and editing/archiving the duplicate resolves the alert |
| `go/internal/hostweb/layout/alerts.go` | edit | Add `duplicate_guest_in_stay` to `computedKinds`, `reasonKinds`, and stay-card reason switch |
| `go/internal/hostweb/layout/i18n.json` | edit | Add `notification.reason.duplicate_guest_in_stay` and `notification.mail_kind.duplicate_guest_in_stay` in `cs`, `en`, `vi` |
| `go/internal/web/auth/opspage/i18n.json` | edit | Add `ops.alert_kind.duplicate_guest_in_stay` in `cs` and `en` |

No other file may change.

## 4. Steps

1. Create `go/internal/ubyport/duplicate_guest.go` and `duplicate_guest_test.go` with `GuestIdentity`, `IsSamePerson`, `IsPossibleDuplicate`, and `DuplicateGuestIDs` (which returns the set of higher-`id` duplicate guest IDs while keeping the lowest `id` per duplicate group).
2. In `go/internal/ubyport/collect.go`:
   - In `CollectSendable`, build the per-reservation `DuplicateGuestIDs` map from the decrypted live guests of that reservation.
   - When `!o.IgnoreAutomation && dupIDs[c.id]`, `continue` (hold duplicate row out of automatic filing while letting the first row file on schedule).
   - Add test in `go/internal/ubyport/collect_test.go`.
3. In `go/internal/web/guest/form_save.go` and `i18n.json`:
   - Before writing a guest row, load & decrypt other live (`archived_at IS NULL AND id != existingID`) guests of `resID`.
   - If any matches `ubyport.IsSamePerson`, return the refused form response (HTTP 400) with the new localized duplicate error message.
   - Add test in `go/internal/web/guest/form_save_test.go`.
4. Create `go/internal/calendar/duplicate_guest.go` and `duplicate_guest_test.go`, and wire it into `go/internal/calendar/deadlines_job.go`:
   - Query active non-archived non-demo stays having `COUNT(*) >= 2` live guests (bounded to stays from the last 14 days onward so old archived stays are never re-scanned).
   - Decrypt each guest's `birth_date` and `doc_number` using `secure.LoadDataKeys(getenv)` (same pattern as `ubyport`).
   - If any pair satisfies `ubyport.IsPossibleDuplicate`:
     - Raise warning alert `duplicate_guest_in_stay` (`dedupe_key = "duplicate_guest_in_stay:<resID>"`, `apartment_id`, `reservation_id`, title `"<property> · duplicate guest"`, detail `"Two guest records look like the same person"` — **no guest names/DOBs/doc numbers**).
     - Enqueue one host email to legal entity `contact_email` with `kind = "duplicate_guest_in_stay"` and idempotency key `"duplicate_guest_in_stay:<resID>:<sorted-dup-ids>"` (direct link to `/reservations/<resID>`, zero guest PII).
   - Resolve `duplicate_guest_in_stay:<resID>` for any stay that had an open alert and no longer has any duplicate pair.
   - Wire into `RunDeadlinesJob` without ever blocking `watchdog`, `stalled`, or the filing heartbeat.
5. Update `go/internal/hostweb/layout/alerts.go`, `go/internal/hostweb/layout/i18n.json`, and `go/internal/web/auth/opspage/i18n.json` to display `duplicate_guest_in_stay` cleanly in `cs`, `en`, `vi`.
6. Run §6 commands.

## 5. Do not touch

- Anything under `App/` (Python is retired; owner 2026-11-27).
- `go/migrations/` (no schema change).
- Hard rules: **zero guest PII** in `alert` rows, email subjects, or logs; never block `filing_watchdog` / `filing_stalled` heartbeat; no new dependency.

## 6. Commands

Run from `go/`:
```bash
go test ./internal/ubyport/... ./internal/web/guest/... ./internal/calendar/... ./internal/hostweb/... 2>&1 | tail -30
```
Expected: `ok` for all 4 packages.

Run from repo root:
```bash
python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: `context lint: OK`.

## 7. Acceptance

- [ ] Guest form refuses submitting the same person twice on the same stay (HTTP 400 + clear localized message), while still allowing distinct guests (including parent + child with different birth dates).
- [ ] Existing or host-entered duplicate guest pairs on an active stay raise `duplicate_guest_in_stay` alert (visible in "What needs you") and queue 1 host email (zero guest PII).
- [ ] Editing or removing the duplicate guest automatically resolves `duplicate_guest_in_stay`.
- [ ] Automatic `CollectSendable` files the first guest on time and skips the duplicate row so UbyPort is not sent a guaranteed `150` duplicate.
- [ ] Zero files under `App/` changed; all §6 commands pass.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/2095-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/ubyport/duplicate_guest.go` and `go/internal/ubyport/collect.go` (confirm first guest always files; no false positive on parent+child)
- `go/internal/web/guest/form_save.go` (confirm guest form never leaks existing guest PII in the error message)
- `go/internal/calendar/duplicate_guest.go` and `deadlines_job.go` (confirm zero PII in alerts/emails and heartbeat never blocked)

## Owner steps

1. Merge PR after green CI with `scripts/merge-pr-on-green.sh <PR>`.
2. On staging, try submitting the same guest twice on one stay and verify the form refuses the second submit with a clear message.
3. After deploy to production, check the open alert for the real stay that had the duplicate guest today and confirm it surfaces cleanly in "What needs you".
