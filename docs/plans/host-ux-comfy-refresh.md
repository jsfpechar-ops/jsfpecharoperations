# Plan: Comfy Host UX Refresh (Status Strip, Mobile Calendar, Calm Dashboard)

Status: 2026-11-26, main at `43f2d0182`. Go only ([go-first](../context/go-first.md)).

Goal: make UbyHost calm, scannable, and comfortable on phone and desktop without losing UbyPort filing correctness (AGENTS.md rule 1).

## Decisions (owner, 2026-11-26)

1. **Per-stay journey status strip (Option 1A):** 4 chronological icons left to right (`Link -> Form -> Code -> Police`) in four states (grey = waiting, amber = in progress / check, green = done, red = action / failed). Hide `Code` when the property has neither TTLock nor saved entry codes; hide `Police` when UbyPort login is not configured. Desktop hover/focus shows the 4-line text breakdown; Stay Detail renders the same 4 icons as a labeled horizontal checklist at the top so hosts learn them immediately. Privacy rule: list views never expose raw PINs, codes, or full emails.
2. **Mobile Calendar (Option 2A, Airbnb-minimal):** On phone (`<768 px`), `Kalendář` (`/?cal_view=calendar`) shows a calm **Property List** when the host has 2+ active properties: each card shows the **property color badge + property name** on the left and a server-rendered **5-week mini-month dot/bar SVG** on the right. **No** operational subtitle line on the card and **no** cross-property timeline toggle. Tapping a card opens that property's **Single-Property Month Calendar** (`/?cal_view=calendar&apartment_id=...`) with a back link and quick property switcher. If the host has only **1 active property**, skip the picker and open that property's calendar directly. Desktop keeps the full calendar / Gantt view.
3. **Kill Dashboard notification spam:**
   - **iCal backfill cutoff:** non-manual, non-demo stays with `filled == 0` whose `date_from` predates the earliest `ical_feed.created_at` (Prague date) for that apartment never appear in Dashboard `Needs you`.
   - **Past unfilled cutoff:** stays with `filled == 0` whose checkout (`date_to`) is more than 7 days in the past never appear in Dashboard `Needs you` (they remain accessible in `/reservations` with a 1-click bulk "Archive old unfilled stays" action).
   - **Legal safety preserved (Rule 1):** any stay that *has* guest data (`filled > 0`) with a failed or overdue UbyPort filing ALWAYS stays visible in `Needs you`.
   - **Root-cause collapse:** if one or more properties have 0 claimed stays ever (`reservation_claim.state = 'claimed'`) and >=2 stays missing guest forms, collapse all of those missing-form nags into **one** dismissible setup card (persisted in `settings`) pointing the host to add the guest link to Airbnb/Booking messages.
   - **Strict cap:** show at most 3 `Needs you` items before collapsing the rest under a summary toggle.
4. **Comfy Dashboard (Phone + Desktop):**
   - **Phone (`<768 px`):** Capped `Needs you` -> **one compact horizontal swipeable stay carousel per property** (~96 px tall, ~285 px wide peeking cards, no giant 72 px avatar circle). Each property header has its color dot, property name, and `Kalendář >` link jumping directly to that property's single-property month calendar. Each card shows guest/source + arrival/in-house/departure tag, dates/nights/guests, and the 4-icon status strip. Cap at 5 stays per rail + a slim `Další pobyty >` card; sort properties by soonest action/arrival; cap at 5 property rails with a `Všechna ubytování (N) >` link; show a quiet 1-line empty card when a property has no upcoming stays. Do not duplicate a second property list on Dashboard.
   - **Desktop (`>=1024 px`):** Keep capped `Needs you` + 14-day multi-property Gantt (clicking a property name jumps to its single-property calendar) + upgrade the Today table with `Dnes / Příštích 7 dní` tabs and the 4-icon status strip column.

## Briefs and Execution Order

| # | Title | Status | Depends on | Scope |
|---|---|---|---|---|
| [2087](../tasks/2087-go-dashboard-calm-notifications.md) | Calm dashboard notifications + iCal backfill cutoff + archive old unfilled | todo | none | Go `hostweb`, `stays`, CSS, i18n |
| [2088](../tasks/2088-go-stay-journey-status-strip.md) | 4-step Stay Journey Status Strip (Link, Form, Code, Police) | todo | 2087 | Go `stays`, `staydetail`, `hostweb`, CSS, i18n |
| [2089](../tasks/2089-go-mobile-calendar-property-index.md) | Mobile Calendar Property Index + Single-Property Month View | todo | 2088 | Go `hostweb`, `calendar`, JS/CSS, i18n |
| [2090](../tasks/2090-go-dashboard-property-carousels.md) | Comfy Dashboard: phone per-property carousels + desktop 7-day tab | todo | 2089 | Go `hostweb`, CSS, i18n, docs |

Run strictly in order **2087 -> 2088 -> 2089 -> 2090** so shared files in `go/internal/web/hostweb/` never conflict.

## Zero-Migration Guarantee

All four briefs use existing Postgres tables and columns:
- `ical_feed.created_at` (baseline `00001_baseline.sql`) for backfill cutoff.
- `settings` key/value table for persisting the collapsed guest-link setup nudge dismissal.
- `reservation_claim.state`, `reservation_claim.completion_notified_at`, `door_code.state`, `door_code.notified_at`, `apartment.lock_provider`, `apartment.lock_id`, `apartment_entry_code` (`00023_apartment_entry_code.sql`, with fallback check on `apartment.entry_code_enc` from `00022`) for the 4-step strip.
- Existing Lucide icons in `go/internal/hostweb/layout/icons.go`: `mail`, `users`, `key-round`, `shield`.

## Verification Standard (UX Gate)

Every brief that changes templates or CSS must pass:
1. Go unit/HTTP tests (`go test ./internal/web/...`).
2. Local Go layout-lint + browser geometry harness (brief `1668`) with 0 skipped, plus inspecting Chromium screenshots at `390`, `768`, and `1280` px and describing each touched page in the PR body (AGENTS.md rule 10).
3. `python3 scripts/context_lint.py` from repo root.
