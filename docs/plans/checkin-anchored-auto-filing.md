# Plan: Check-in-anchored automatic police filing (Go-only)

Date: 2026-11-27 | Owner: Josef | Scope: Go only (zero Python edits)

## Why

Today `DueForAutomaticSend` measures `scheduled` from `registration_completed_at` alone, and `SubmitCompletedStay` fires `immediate` on form completion with `IgnoreSchedule: true`. Any guest who fills the registration form before arrival gets reported to the Czech Foreign Police days before check-in. Cancellations, no-shows, guest swaps, and typos caught at arrival become irreversible `cancelled_after_report` records because UbyPort has no SOAP delete/cancel endpoint.

## Core design (Go-only, zero DB migration)

1. **Replace `scheduled`’s anchor — do not add a 4th mode.** Existing `scheduled` properties automatically inherit the new check-in-anchored behaviour with no DB migration and no user email (owner confirmed 2026-11-27).
2. **Unified per-guest send-time formula (`ScheduledSendAt` in `go/internal/ubyport/collect.go`):**
   - **Per-guest timer (owner confirmed 2026-11-27):** each complete reportable guest has their own timer and does **not** wait for missing co-guests (e.g. on a `2/3` stay, guests 1 & 2 file in Batch 1 at `check-in + 24h`, and guest 3 files separately in Batch 2 whenever they finish).
   - `guestAnchor` = guest's `stay_from` when set, else `reservation.date_from`.
   - `guestSubmittedAt` = guest's `COALESCE(NULLIF(filled_at,''), NULLIF(updated_at,''), NULLIF(created_at,''))` (falls back to `reservation.registration_completed_at` if blank).
   - `checkInHour` = `apartment.checkin_hour` when in `0..23`, else fallback `15` (Europe/Prague).
   - `checkInMoment` = `guestAnchor` at `checkInHour:00` in `Europe/Prague`.
   - `latest` = `ReportingDeadline(guestAnchor) - 6h` (hard statutory cap, decision 2026-11-09).
   - For `immediate`: `sendAt = min(max(checkInMoment, guestSubmittedAt), latest)`. Neither sweep nor `SubmitCompletedStay` sends before `checkInMoment`.
   - For `scheduled`: `sendAt = min(max(checkInMoment + H, guestSubmittedAt + H), latest)` where `H = submit_after_hours` (default `24`, valid `1..24`).
   - Guest with no parsable submit timestamp: falls back to `latest` (`deadline - 6h`, brief 1070).
   - Manual "Send now": unchanged — `IgnoreSchedule: true` always lets the host send early.
3. **Default delay = `24` hours (confirmed by owner 2026-11-27; not `72` hours) — why:**
   - Under decision D3 (`go/internal/deadlines/deadlines.go`), arrival day counts as working day 1 on Mon–Fri.
   - A Monday `15:00` check-in has statutory deadline **Wednesday `23:59`** (57 h), hard cap **Wednesday `17:59`** (51 h), and `deadline_at_risk` watchdog email at **Tuesday `23:59`** (`deadline - 24h`, only 33 h after check-in).
   - A `72` h default would clamp to 51 h on every Mon/Tue/Wed stay and fire false `deadline_at_risk` "file by hand" emails + `/fail` heartbeat alerts 18 h before UbyHost sends.
   - `24` h after check-in (even for a `23:00` check-in → Tue `23:00`) always fires **before** the `deadline - 24h` watchdog opens, gives a full day after check-in for review/edits, and leaves a full business day to recover from UbyPort rejections.
4. **Mandatory check-in / check-out hours (without breaking legacy TTLock safety):**
   - Add required `checkin_hour` / `checkout_hour` (preselected `15:00` / `10:00`) to `/apartments/new`, Copy-from-property, and Property settings (wizard Step 1 already requires them).
   - **Do NOT backfill legacy `NULL` rows in Postgres:** `go/internal/doorcodes` and `smart_locks.go` treat `checkin_hour IS NOT NULL AND checkout_hour IS NOT NULL` as host-confirmed door-code hours. Legacy `NULL` properties use `15:00` only inside the filing schedule and show a short prompt on Property settings until the host saves their times.
5. **Clear UI explanations with concrete examples in `?` at each option:**
   - Default new properties to `scheduled` + `24` h (keep existing saved modes untouched).
   - Property settings uses the same 3 `choice_card` cards as onboarding wizard Step 3, each with its own `?` (`help_tip`) containing the rule and a Monday `15:00` example.
   - Stay detail shows the exact computed automatic send time; status pills (`ready_immediate`, `ready_scheduled`), wizard rehearsal, and `/guide#reporting` are updated across `cs`, `en`, `vi`.
6. **Complete 5-stage host alarm & email net (closing the check-in-time gap in 100% Go):**
   - Stage 1 (day before, `18:00` Prague): day-before host email (`reminder_host:day_before:{id}:{date}`) when forms are incomplete (unclaimed or unfinished).
   - Stage 2 (at `checkInMoment` = `checkin_hour` ?? `15:00` Prague on check-in day): **second** host email (`reminder_host:checkin:{id}:{date}` — distinct key so day-before never suppresses it) + `guest_incomplete_checkin` alert, running in Go's live `deadlines` job (`calendar/checkin_alarm.go`) and aligned with `mailjob/reminders.go`.
   - Stage 3 (`<24h` to statutory deadline): existing `deadline_at_risk` email + push (`filing_watchdog.go`).
   - Stage 4 (`deadline - 6h`): hard auto-send cap (`ubyport/collect.go`).
   - Stage 5 (`deadline - 3h`): existing critical `filing_stalled` alert + email + `/fail` heartbeat (`filing_stalled.go`).

## Ordered briefs (all Go-only)

| Brief | Tier | Branch | Summary |
|---|---|---|---|
| [2091](../tasks/2091-go-checkin-anchored-auto-filing.md) | A | `task/2091-go-checkin-anchored-auto-filing` | `ScheduledSendAt` / `DueForAutomaticSend` + `SubmitCompletedStay` pre-check-in gate + unit/DB tests |
| [2092](../tasks/2092-go-mandatory-checkin-hours-and-scheduled-default.md) | B | `task/2092-go-mandatory-checkin-hours-and-scheduled-default` | Required `checkin_hour`/`checkout_hour` on create/copy/settings + `scheduled` 24 h default + `1..24` validation |
| [2093](../tasks/2093-go-automation-choice-cards-examples-and-copy.md) | C + UX | `task/2093-go-automation-choice-cards-examples-and-copy` | Choice cards with `?` examples on Property settings & wizard, computed send time on Stay detail, pills/guide/rehearsal copy (`cs`/`en`/`vi`), UX gate |
| [2094](../tasks/2094-go-checkin-time-incomplete-alarm-and-mail.md) | B | `task/2094-go-checkin-time-incomplete-alarm-and-mail` | Check-in-time `guest_incomplete_checkin` alert + distinct second host email (`reminder_host:checkin:...`) in Go `deadlines` + `mailjob` |
| [2095](../tasks/2095-go-duplicate-guest-prevention-and-alert.md) | B | `task/2095-go-duplicate-guest-prevention-and-alert` | 3-layer duplicate-guest guard: guest form block, `duplicate_guest_in_stay` host alert + email (zero PII), and auto-filing duplicate skip |

## Risks and verification

- **UbyPort filing (Tier A):** Brief 2091 changes when automatic batches become due. Never breaks `ReportingDeadline`, `-6h` cap, `filing_stalled` (`-3h`), or manual send. Verify with `go test ./internal/ubyport/... ./internal/web/staydetail/... ./internal/calendar/...` and Gate 2 spot-check in `test` mode.
- **No Python edits:** per owner 2026-11-27 ("everything in Go, we don't do Python anymore") and `go-first.md`.
