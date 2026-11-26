# 2087: Calm dashboard notifications, iCal backfill cutoff, and bulk archive old unfilled stays

Status: done
Depends on: none | Base commit: 43f2d0182 | Branch: task/2087-go-dashboard-calm-notifications
Executor: medium | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Stop the Dashboard (`GET /`) from spamming hosts with permanent `Needs you` rows when they connect iCal calendars before pasting the UbyHost guest link into Airbnb/Booking messages. Keep every real UbyPort filing failure/overdue (stays with submitted guest data) prominent (AGENTS.md rule 1).

Concrete changes (all in Go):
1. **iCal backfill cutoff:** Do not generate `Needs you` rows for non-manual, non-demo stays with 0 submitted guests (`filled == 0`) whose `date_from` is earlier than the apartment's earliest `ical_feed.created_at` (converted to Prague `YYYY-MM-DD`).
2. **Past unfilled horizon:** Do not generate `Needs you` rows for stays with `filled == 0` whose `date_to` is more than 7 days before `today` (`date_to < today - 7d`). Stays with `filled > 0` that have failed or overdue UbyPort filings MUST still appear regardless of age or feed date.
3. **Root-cause collapse (`0 claims` setup nudge):** When an apartment has 0 claimed stays ever (`NOT EXISTS (SELECT 1 FROM reservation_claim rc JOIN reservation r ON r.id = rc.reservation_id WHERE r.apartment_id = a.id AND rc.state = 'claimed')`) and >=2 active stays missing guest forms that would otherwise create missing-form `Needs you` lines, replace all those per-stay missing-form lines with **one** dismissible setup card (combined across all affected properties, showing property count + stay count, linking to `/apartments/{first_id}?view=guests`, with a `POST /dashboard/dismiss-guest-link-nudge` form that persists a dismissal timestamp in `settings` under key `dash_guest_link_nudge_dismissed:{owner_id}` for 14 days or until reset).
4. **Strict cap:** Show at most **3** visible items in `#needs-action` (down from 5), collapsing the rest inside the existing `<details class="needs-you-more">`.
5. **1-click bulk archive of old unfilled stays:** Add a quiet secondary action on `/reservations` (shown only when count > 0) backed by `POST /reservations/archive-old-unfilled` (CSRF-protected) that archives active, non-archived stays belonging to the owner where `date_to < today - 7d` AND the stay has 0 non-archived `guest` rows, with an audit row and flash message reporting how many stays were archived.

## 2. Context

Plan: `docs/plans/host-ux-comfy-refresh.md`.
Rules: `docs/context/go-first.md`, `docs/design/design-system.md` (rules 1, 2, 4, 7, 9), `docs/design/pages/dashboard.md`, `docs/design/pages/stays.md`, AGENTS.md rules 1, 2, 5, 10, 11.

Exact excerpts (verify verbatim before editing; if not found, STOP per section 8):

- `go/internal/web/hostweb/dashboard_data.go:269-280`:
  `WHERE r.status = 'active' AND a.active = 1 AND a.archived_at IS NULL AND r.archived_at IS NULL`
  `AND a.owner_user_id IS NOT DISTINCT FROM $1 AND r.date_from <= $2`
- `go/internal/web/hostweb/dashboard_data.go:857-880`:
  `func stayLine(row stays.Row, today time.Time, lang string, t func(string, map[string]any) string, files bool) (nyLine, bool)`
  Notice `if files && row.Progress.Cell.Level == "overdue"` runs BEFORE `if okD && !departure.After(today)`.
- `go/internal/web/hostweb/templates/dashboard.tmpl:32-39`:
  `{{- range $i, $line := $d.NyLines}}{{if lt $i 5}}{{template "dash.ny_row" (kv "line" $line "first" (eq $i 0))}}{{end}}{{end}}`
  `{{- if gt (len $d.NyLines) 5}}`
- `go/internal/web/hostweb/dashboard.go`: registers/handles `GET /`; check `go/cmd/` or router registration for where `DashboardHandler` and `stays.RegisterEditPosts` are mounted.
- Schema verified in `App/migrations_pg/00001_baseline.sql`:
  `ical_feed` has `apartment_id bigint NOT NULL`, `created_at text NOT NULL`.
  `reservation_claim` has `reservation_id bigint NOT NULL`, `state text` (`unclaimed`, `provisional`, `claimed`).
  `settings` table stores `(key, value)` pairs (see `go/internal/web/onboarding/wizard_post.go`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/hostweb/dashboard_data.go` | edit | load earliest `ical_feed.created_at` per apartment + claimed-stay counts + nudge dismissal setting; apply backfill cutoff, 7d past-unfilled cutoff, `0 claims` collapse, and keep `filled > 0` UbyPort errors |
| `go/internal/web/hostweb/dashboard.go` | edit | add `DismissGuestLinkNudgeHandler` (`POST /dashboard/dismiss-guest-link-nudge`) |
| `go/internal/web/hostweb/templates/dashboard.tmpl` | edit | cap visible `NyLines` at 3 (not 5); render dismissible setup nudge line with CSRF hidden input |
| `go/internal/web/hostweb/i18n.json` | edit | add CS, EN, VI keys for collapsed guest-link nudge & dismiss action |
| `go/internal/web/hostweb/dashboard_test.go`, `go/internal/web/hostweb/needs_you_nofiles_test.go` | edit | unit + HTTP tests for backfill cutoff, >7d unfilled cutoff, `filled > 0` overdue preserved, `0 claims` collapse + dismiss, cap of 3 |
| `go/internal/web/stays/edit_posts.go` | edit | add `ArchiveOldUnfilledHandler` (`POST /reservations/archive-old-unfilled`) + route registration |
| `go/internal/web/stays/handlers.go`, `go/internal/web/stays/templates/stays_list.tmpl`, `go/internal/web/stays/i18n.json`, `go/internal/web/stays/i18n_keys.txt` | edit | count old unfilled stays for the owner and render quiet bulk-archive form in toolbar/banner when count > 0 (CS, EN, VI keys) |
| `go/internal/web/stays/edit_posts_test.go` | edit | test bulk archive archives only owner's active stays with `date_to < today - 7d` and 0 non-archived guests, never touches stays with guests |
| Go router registration file under `go/cmd/` or `go/internal/` where `DashboardHandler` is wired | edit | mount `POST /dashboard/dismiss-guest-link-nudge` |
| `docs/design/pages/dashboard.md` | edit | note the 3-row cap, backfill cutoff, and collapsed guest-link nudge |

No other file may change. Do not edit Python files.

## 4. Steps

1. **Inspect router wiring.** Grep `DashboardHandler` in `go/` to find the exact mux registration file.
2. **Load apartment metadata in `loadDashboard`.** In `go/internal/web/hostweb/dashboard_data.go`, extend the apartment query (or add one batched query) to fetch per active apartment:
   - `earliestFeedDate`: `MIN(f.created_at)` from `ical_feed f WHERE f.apartment_id = a.id` converted to Prague `YYYY-MM-DD` (empty if no feed).
   - `hasAnyClaim`: `EXISTS (SELECT 1 FROM reservation_claim rc JOIN reservation r ON r.id = rc.reservation_id WHERE r.apartment_id = a.id AND rc.state = 'claimed')`.
   Also read `settings` key `dash_guest_link_nudge_dismissed:{owner}` and compare to `today.AddDate(0, 0, -14)` so a dismissal snoozes the nudge for 14 days (auto-clears if the host starts getting claims).
3. **Update `stayLine` and `needsYouLines`.**
   - Pass apartment metadata (`earliestFeedDate`, `hasAnyClaim`) into `needsYouLines` / `stayLine`.
   - Define `hasGuests := row.Progress.Filled > 0 || len(row.Progress.Guests) > 0`.
   - **Rule 1 guard:** If `hasGuests`, NEVER suppress `failed` or `overdue` UbyPort filing lines.
   - **Backfill guard:** If `!hasGuests && r.Source != "manual" && !isDemoStay(r) && earliestFeedDate != "" && r.DateFrom < earliestFeedDate`, return `false`.
   - **Past unfilled guard:** If `!hasGuests && okD && departure.Before(today.AddDate(0, 0, -7))`, return `false`.
   - **Root-cause collapse:** Track stays whose line would be a missing-guest / unfilled-overdue reminder on apartments where `!hasAnyClaim`. If an apartment has >=2 such stays, omit those individual per-stay lines and accumulate `(affectedProperties, affectedStays, firstAptID)`. If `affectedStays > 0` and the nudge is not snoozed, insert ONE `nyLine` with `Kind: "guest_link_nudge"`, `Tone: "amber"`, `Href: "/apartments/" + itoa(firstAptID) + "?view=guests"`, and a flag `DismissAction: "/dashboard/dismiss-guest-link-nudge"`.
4. **Update `dashboard.tmpl` & handler.**
   - Change the visible cap in `dashboard.tmpl` from `5` to `3` (`lt $i 3`, `gt (len $d.NyLines) 3`, `add (len $d.NyLines) -3`, `ge $i 3`).
   - Support `DismissAction` with CSRF token `<input type="hidden" name="_csrf" value="{{csrf}}">` in `dash.ny_row`.
   - Implement `DismissGuestLinkNudgeHandler` (`POST /dashboard/dismiss-guest-link-nudge`, authenticated, CSRF-verified via standard hostweb middleware/wrapper, upserts `settings` key `dash_guest_link_nudge_dismissed:{owner}` to UTC ISO timestamp, redirects `303` to `/`).
5. **Add bulk archive of old unfilled stays on `/reservations`.**
   - In `go/internal/web/stays/edit_posts.go`, register `POST /reservations/archive-old-unfilled` using the same auth + CSRF wrapper as `ArchiveHandler`.
   - Execute one owner-scoped `UPDATE reservation SET archived_at = $1, updated_at = $1 WHERE ...`: `status = 'active'`, `archived_at IS NULL`, apartment belongs to owner & not archived, `date_to < $2` (`today - 7d`), and `NOT EXISTS (SELECT 1 FROM guest g WHERE g.reservation_id = reservation.id AND g.archived_at IS NULL)`. Write an audit entry and flash message with count. Redirect `303` to `/reservations`.
   - In `stays/handlers.go` + `stays_list.tmpl`, count matching old unfilled stays (only on active non-archive view); when `count > 0`, show one quiet banner/strip (`ui-note-strip` or `onboarding-banner`-style quiet row, never coral primary) with `Archive N old unfilled stays` button behind `data-confirm`.
6. **Add i18n keys (CS, EN, VI together, no em dash).** Update `go/internal/web/hostweb/i18n.json`, `go/internal/web/stays/i18n.json`, and `go/internal/web/stays/i18n_keys.txt`. Refresh golden files only if existing tests assert the exact 5->3 threshold, and document why.
7. **Tests & UX gate.** Run Go tests, run the Go browser layout-lint harness (1668) on `/` and `/reservations` at 390/768/1280 px, inspect the screenshots, and run `python3 scripts/context_lint.py`.

## 5. Do not touch

Any Python file under `App/app/`, SQLite code, `App/migrations_pg/` (no schema migration), guest pages, UbyPort submission logic, `UBYHOST_GO_PATHS`, or `main`.

## 6. Commands

From `go/`: `go test ./internal/web/hostweb/... ./internal/web/stays/... -count=1 2>&1 | tail -30`
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -20`
Browser UX gate (see brief 1668 harness): run layout-lint + capture 390/768/1280 screenshots of `/` and `/reservations`.

## 7. Acceptance

- [ ] Non-manual stays with `filled == 0` and `date_from < earliest_feed_created_date` never appear in Dashboard `Needs you`.
- [ ] Stays with `filled == 0` and `date_to < today - 7d` never appear in Dashboard `Needs you`.
- [ ] Stays with `filled > 0` and failed or overdue UbyPort filing ALWAYS appear in Dashboard `Needs you` (Rule 1).
- [ ] Properties with `0 claims` and >=2 unfilled stays collapse into 1 dismissible setup card; dismissing snoozes it for 14 days via `settings`.
- [ ] `#needs-action` displays at most 3 items before the `+ N more` disclosure.
- [ ] `POST /reservations/archive-old-unfilled` archives only owner's old unfilled stays (`date_to < today - 7d`, 0 non-archived guests) and never touches stays with guests.
- [ ] CS, EN, VI keys added together with no em dashes; all Go tests and layout-lint pass with 0 skipped; 390/768/1280 screenshots inspected and described in PR.

## 8. Stop and ask

Stop and write the report if: an excerpt in §2 is not found verbatim; a test fails twice; you reach 25 tool calls or ~50k tokens; a schema migration seems required; or any file outside §3 needs editing.

## 9. Report

Write `docs/tasks/2087-report.md` (<=600 tokens), set `Status: review`, open one PR (include per-page 390/768/1280 screenshot notes and design-system checklist). Report: `git diff --stat`, command tails, §7 ticked, deviations, questions, owner steps.
