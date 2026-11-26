# 2088: 4-step Stay Journey Status Strip (Link, Form, Code, Police)

Status: done
Depends on: 2087 | Base commit: 43f2d0182 | Branch: task/2088-go-stay-journey-status-strip
Executor: medium | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Give hosts an instant, dumbproof visual readout of every stay's progress on both phone and desktop — replacing guesswork about whether a guest opened the magic link, completed the guest form, received an entry/door code, or was reported to UbyPort.

Owner decision (2026-11-26, Option 1A):
- Render a compact chronological **4-step status strip**: `Link -> Form -> Code -> Police`, using existing Lucide icons (`mail`, `users`, `key-round`, `shield`).
- Four semantic tones using existing design tokens (never raw hex):
  - `waiting` (grey) — not started / waiting
  - `progress` (amber) — in progress / awaiting click / ready for manual send / issuing
  - `done` (green) — verified / complete / sent / filed on time
  - `bad` (red) — failed / overdue (action required)
- **Hide unconfigured steps:**
  - Omit `Code` when the apartment has neither TTLock (`lock_provider = 'ttlock' AND lock_id IS NOT NULL`) nor any active saved entry code (`apartment_entry_code` row not past `valid_until`, or non-empty legacy `apartment.entry_code_enc` not past `entry_code_until`).
  - Omit `Police` when the apartment does not have all three UbyPort login fields (`uby_idub`, `uby_ws_user`, `uby_ws_password_enc`) or the stay is a demo stay.
- **Zero mystery-meat:**
  - On list views (`/reservations` desktop table & phone cards, and Dashboard today table), the strip carries a clean `title` / accessible `aria-label` listing all visible steps in plain language (e.g., `Odkaz ověřen · Formulář 2/2 · Kód odeslán · Policie nahlášeno`) plus a tiny numeric counter beside the `users` icon (`1/2`, `2/2`).
  - On Stay Detail (`/reservations/{id}`), render the **exact same 4 icons as a labeled horizontal checklist** near the top (`Odkaz` · `Formulář` · `Kód` · `Policie`) with each step's short status line, so after opening one stay every host knows the icons permanently.
- **Privacy rule (AGENTS.md rule 2):** Strip labels and tooltips NEVER include raw PINs, entry codes, guest emails, or document numbers.

## 2. Context

Plan: `docs/plans/host-ux-comfy-refresh.md`.
Rules: `docs/context/go-first.md`, `docs/design/design-system.md` (rules 1, 2, 3, 8, 9, 10), `docs/design/pages/stays.md`, AGENTS.md rules 1, 2, 6, 7, 10, 11.

Exact excerpts (verify verbatim before editing; if not found, STOP per section 8):

- Icons already exist in `go/internal/hostweb/layout/icons.go`:
  - `"mail"` (line 34)
  - `"users"` (line 50)
  - `"key-round"` (line 16)
  - `"shield"` (line 18)
- `go/internal/web/stays/row_build.go:13-38`: `enrichRows(ctx, pool, getenv, rows, at)` batches guest loading for both `/reservations` and Dashboard (`EnrichDashboardRows`).
- `go/internal/web/stays/templates/stays_list.tmpl`:
  - `stays_phone_card` (lines 48-59)
  - `stays_desk_row` (lines 60-107), reporting column at line 80.
- `go/internal/web/staydetail/view.go` and `go/internal/web/staydetail/templates/stay_detail.tmpl`: loads `StayClaim`, `Progress`, `DoorCode`, and apartment details.
- Schema verified in `App/migrations_pg/00001_baseline.sql` and `00023_apartment_entry_code.sql`:
  - `reservation_claim(reservation_id, state, completion_notified_at, guest_access_locked_at)`
  - `door_code(reservation_id, state, notified_at, issued_at)`
  - `apartment(lock_provider, lock_id, uby_idub, uby_ws_user, uby_ws_password_enc, entry_code_enc, entry_code_until)`
  - `apartment_entry_code(apartment_id, valid_until)`

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/stays/journey.go` | create | `JourneyStep` / `StayJourney` types + batched loader `LoadJourneys(ctx, pool, reservationIDs, today)` + pure `BuildJourney(...)` state mapper |
| `go/internal/web/stays/journey_test.go` | create | unit + DB tests covering all 4 steps, tone mapping, hidden Code/Police capability gating, and privacy (no PIN/email leaked) |
| `go/internal/web/stays/types.go`, `go/internal/web/stays/row_build.go` | edit | attach `Journey StayJourney` to `stays.Row` inside `enrichRows` (single batched query, zero N+1) |
| `go/internal/web/stays/tpl.go`, `go/internal/web/stays/templates/stays_list.tmpl` | edit | render compact `.stay-journey` strip on both `stays_phone_card` and `stays_desk_row` |
| `go/internal/web/stays/i18n.json`, `go/internal/web/stays/i18n_keys.txt` | edit | CS, EN, VI labels & tooltip strings for the 4 journey steps |
| `go/internal/web/staydetail/view.go`, `go/internal/web/staydetail/types.go`, `go/internal/web/staydetail/templates/stay_detail.tmpl`, `go/internal/web/staydetail/i18n.json`, `go/internal/web/staydetail/i18n_keys.txt` | edit | render labeled `.stay-journey-bar` at top of Stay Detail using the same `stays.BuildJourney` mapper |
| `go/internal/web/hostweb/dashboard.go`, `go/internal/web/hostweb/templates/dashboard.tmpl`, `go/internal/web/hostweb/i18n.json` | edit | expose compact journey strip on Dashboard desktop today table rows (reusing `Row.Journey` from `EnrichDashboardRows`) |
| `App/app/static/app2.css` | edit | add token-only `.stay-journey`, `.stay-journey-step`, `.stay-journey-bar` styles (respecting 12 px spacing rules & 72 px desktop row height) |
| `docs/design/pages/stays.md` | edit | document the 4-step journey strip on list & stay detail |

No other file may change. Do not edit Python code or templates.

## 4. Steps

1. **Implement `stays/journey.go` (pure mapping + batched query).**
   - Define `JourneyStep`: `Key` (`"link"`, `"form"`, `"code"`, `"police"`), `Icon` (`"mail"`, `"users"`, `"key-round"`, `"shield"`), `Tone` (`"waiting"`, `"progress"`, `"done"`, `"bad"`), `Counter` (optional, e.g. `"1/2"` on `form`), `StateKey` (i18n key suffix).
   - Batched query for `reservationIDs` (using `ANY($1::bigint[])`):
     - Join `reservation r` -> `apartment a`, `LEFT JOIN reservation_claim rc ON rc.reservation_id = r.id`, `LEFT JOIN door_code dc ON dc.reservation_id = r.id`, plus capability subqueries:
       - `has_ttlock`: `COALESCE(a.lock_provider,'') = 'ttlock' AND COALESCE(a.lock_id,'') <> ''`
       - `has_entry_code`: `EXISTS (SELECT 1 FROM apartment_entry_code c WHERE c.apartment_id = a.id AND (c.valid_until IS NULL OR c.valid_until = '' OR c.valid_until >= $2)) OR (COALESCE(a.entry_code_enc,'') <> '' AND (a.entry_code_until IS NULL OR a.entry_code_until = '' OR a.entry_code_until >= $2))`
       - `files_ubyport`: `COALESCE(TRIM(a.uby_idub),'') <> '' AND COALESCE(TRIM(a.uby_ws_user),'') <> '' AND COALESCE(TRIM(a.uby_ws_password_enc),'') <> ''`
   - **Exact step state rules (only for `r.Status == "active"`; cancelled/archived stays omit the strip):**
     - **Step 1 (`link`, icon `mail`):**
       - `rc.state == "claimed"` -> `done` (`verified`)
       - `rc.state == "provisional"` -> `progress` (`sent`)
       - else -> `waiting` (`unclaimed`)
     - **Step 2 (`form`, icon `users`):**
       - Counter: `fmt.Sprintf("%d/%d", filled, *expected)` when `expected != nil && *expected > 0`, else `strconv.Itoa(filled)`.
       - `filled == 0` -> `waiting` (`empty`)
       - `incomplete > 0 || (expected != nil && filled < *expected)` -> `progress` (`partial`)
       - else -> `done` (`complete`)
     - **Step 3 (`code`, icon `key-round`) — shown ONLY when `has_ttlock || has_entry_code`:**
       - If `has_ttlock`:
         - `dc.state == "failed"` -> `bad` (`failed`)
         - `dc.state` in `{"delayed", "retrying", "issuing"}` -> `progress` (`issuing`)
         - `dc.state == "issued"` and (`dc.notified_at != ""` or `rc.completion_notified_at != ""`) -> `done` (`sent`)
         - `dc.state == "issued"` (not yet emailed) -> `progress` (`ready`)
         - else -> `waiting` (`waiting`)
       - Else (`has_entry_code` only):
         - `rc.completion_notified_at != ""` -> `done` (`sent`)
         - `rc.state == "claimed"` and today is in `[date_from - 1d, date_to]` -> `done` (`available`)
         - else -> `waiting` (`waiting`)
     - **Step 4 (`police`, icon `shield`) — shown ONLY when `files_ubyport && !isDemo`:**
       - `progress.Status == "failed"` or `progress.Cell.Level == "overdue"` -> `bad` (`action`)
       - `progress.Status` in `{"reported", "not_required"}` or `progress.Cell.State == "filed_on_time"` -> `done` (`filed`)
       - `progress.Status` in `{"ready", "awaiting_verification"}` or `progress.Cell.State == "filed_late"` -> `progress` (`pending`)
       - else -> `waiting` (`waiting`)
2. **Wire into `enrichRows`.** Call `LoadJourneys` inside `enrichRows` in `go/internal/web/stays/row_build.go` so `/reservations` and `/` both receive `Row.Journey` with 1 batched SQL query.
3. **Render compact strip on `/reservations` and Dashboard desktop table.**
   - Create a reusable template block rendering `<span class="stay-journey" role="group" aria-label="...">` with each visible step `<span class="stay-journey-step is-{{.Tone}}" title="...">` containing `{{icon .Icon 15}}` and optional `<span class="stay-journey-count">{{.Counter}}</span>`.
   - Keep desktop rows <= 72 px tall (`docs/design/pages/stays.md`). On phone cards (`stays_phone_card`), place `.stay-journey` cleanly on its own row inside `.in` with >= 12 px spacing from neighbours.
4. **Render labeled 4-step bar on Stay Detail.**
   - In `go/internal/web/staydetail/view.go`, populate `v.Journey` using `stays.LoadJourneys` for `[id]` + `stays.BuildJourney`.
   - In `stay_detail.tmpl`, place `<ol class="stay-journey-bar card">` right under the header / Now strip showing each visible step with icon, short label (`Odkaz`, `Formulář`, `Kód`, `Policie`), and concise status word (`Ověřen`, `2/2`, `Odeslán`, `Nahlášeno`). Stacks 2x2 cleanly on 390 px phone without truncation (design-system rule 8).
5. **CSS (`App/app/static/app2.css`).**
   - Token-only styles using existing palette tokens (`--ok` / `--oks` green, `--warn` / `--warns` amber, `--bad` / `--bads` red, `--ink3` / `--line` grey). Never use coral (`--acc`) for missing/waiting states (design-system rule 9). No `<style>` or `style=""` in templates.
6. **i18n (CS, EN, VI together, no em dashes).** Add keys for step names and states in `stays/i18n.json`, `staydetail/i18n.json`, and `hostweb/i18n.json` (and update `i18n_keys.txt` files where checked by tests).
7. **Tests & UX gate.** Run Go tests, run the Go browser layout-lint harness (1668) on `/reservations`, `/reservations/{id}`, and `/` at 390/768/1280 px, inspect all screenshots, and run `python3 scripts/context_lint.py`.

## 5. Do not touch

Python files under `App/app/`, `App/migrations_pg/`, guest pages, UbyPort submission workers, door-code worker logic, `UBYHOST_GO_PATHS`, or `main`.

## 6. Commands

From `go/`: `go test ./internal/web/stays/... ./internal/web/staydetail/... ./internal/web/hostweb/... -count=1 2>&1 | tail -30`
From repo root: `python3 scripts/context_lint.py 2>&1 | tail -20`
Browser UX gate (brief 1668 harness): run layout-lint + capture 390/768/1280 screenshots of `/reservations`, `/reservations/{id}`, and `/`.

## 7. Acceptance

- [ ] `stays.BuildJourney` maps all 4 steps accurately and omits `code` when unconfigured and `police` when UbyPort is unconfigured or demo.
- [ ] Single batched SQL query in `enrichRows` (no N+1 per stay).
- [ ] Compact 4-step strip renders on `/reservations` (desktop + phone) and `/` desktop table with accessible `aria-label` + hover `title`; desktop rows stay <= 72 px.
- [ ] Labeled 4-step checklist bar renders at top of `/reservations/{id}` with zero truncated labels at 390/768/1280 px.
- [ ] Privacy check: no raw PIN, entry code, or email string appears in strip markup or tooltips.
- [ ] All Go tests + layout-lint pass with 0 skipped; 390/768/1280 screenshots inspected and described in PR.

## 8. Stop and ask

Stop and write the report if: an excerpt in §2 is not found verbatim; `apartment_entry_code` table is missing in the test DB fixture (check goose 00023); a test fails twice; you reach 25 tool calls or ~50k tokens; or any file outside §3 needs editing.

## 9. Report

Write `docs/tasks/2088-report.md` (<=600 tokens), set `Status: review`, open one PR (include per-page 390/768/1280 screenshot notes and design-system checklist). Report: `git diff --stat`, command tails, §7 ticked, deviations, questions, owner steps.
