# 2097: Dumbproof 5-step Stay Journey (SES email, link opened, form + housebook, TTLock, police + manual paths)

Status: done
Depends on: 2091, 2093, 2094 | Base commit: 446b58964 | Branch: task/2097-go-stay-journey-5step-ses-and-manual-paths
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Upgrade the Go stay journey status strip (`go/internal/web/stays/journey.go`) into a dumbproof, bulletproof chronological funnel with **2 separate steps for Email (AWS SES) and Link Opened**, folded **Domovní kniha** status inside Form, **TTLock-only** Door Code, **Calm Blue (`scheduled`)** auto-filing state on Police, and airtight handling of **every manual host action** so statuses never glitch.

Owner decisions (2026-11-27):
1. **Option B — 2 separate icons for Email (SES) and Link Opened everywhere:**
   - Chronological order: **`Email (mail)` -> `Opened (mail-open)` -> `Form (users + n/m)` -> `[TTLock Code (key-round)]` -> `Police (police)`**.
   - 4 icons normally; 5 icons when the property uses TTLock.
2. **Door Code (`code`) is TTLock-only:**
   - Show ONLY when `lock_provider = 'ttlock' AND lock_id <> ''`. Never show for static saved entry codes (`apartment_entry_code`); remove the unused `has_entry_code` subquery from `journeySignalsSQL`.
3. **Domovní kniha folded into Step 3 (`form`), NOT a separate icon:**
   - Complete & signed form (`done`) labels as `v domovní knize` / `in house book` / `đã ghi sổ lưu trú`; Stay Detail links directly to `/housebook`.
4. **Strict 5-tone color grammar (answers "do I need to do anything right now?"):**
   - `waiting` (grey) — relax, waiting on time or guest
   - `scheduled` (calm blue, `--info` bg / `#1f4e79` ink) — relax, UbyHost will file automatically at the scheduled time
   - `progress` (amber) — heads up / action soon (in-flight email, unopened link, partial form, manual send ready, ID check, check-in day still empty)
   - `done` (green) — finished (including Czech-only `not_required` and host manual overrides)
   - `bad` (red) — act now (SES failed/bounced/complained, UbyPort error, overdue deadline, missing UbyPort login when foreign guests are ready, TTLock failed, cancelled after already filed)
5. **Bulletproof manual-action handling (zero status glitches):**
   - Host adds guests manually without magic link (`unclaimed` + `filled > 0`): Steps 1 (`email`) and 2 (`opened`) resolve cleanly to `done` (`manual` = `zadáno ručně` / `added by host`), never stuck grey.
   - Host rescues a stay manually after an invite was sent or bounced (`provisional` + form complete): Steps 1 and 2 resolve cleanly to `done` (`manual`), never stuck red/amber.
   - Host marks stay filed by hand (`manual_filed_at != ""`): Step 5 (`police`) resolves to `done` (`filed_manual` = `nahlášeno ručně` / `filed by hand`), even without UbyPort credentials and even if filed late.
   - Host sends partial stay early (e.g. 2 of 3 guests reported while guest 3 is missing): Step 5 shows `progress` (`partial`, counter `2/3`) instead of dropping back to grey `waiting`.
   - Czech-only stays (`not_required`): Step 5 shows `done` (`not_required` = `netřeba (ČR)` / `not needed (CZ)`), fixing the current bug that says `odesláno` / `filed`, and checked BEFORE `!FilesUbyPort` so unconnected apartments never flash red for Czech guests.
   - Stay cancelled *after* guests were already reported to UbyPort (`status == "cancelled"` and `ReportedCount > 0`): do NOT hide the warning; render a single `bad` (`cancelled_after_report`) police step (`zrušeno po hlášení` / `cancelled after filing`).
6. **Zero DB migration:** all signals come from existing Postgres tables (`reservation_claim`, `email_outbox`, `guest`, `door_code`, `apartment`).

## 2. Context

- **Tier B + UX gate (Go-only):** Never touch `App/app/` Python code or templates (only `App/app/static/comfy*.css` for styles).
- Rules: `docs/context/go-first.md`, `docs/design/design-system.md` (rules 1–10), `docs/design/pages/stays.md`, `AGENTS.md` rules 1, 2, 6, 7, 9, 10, 11.
- Privacy rule (`AGENTS.md` rule 2): Journey labels, tooltips, and `aria-label` NEVER include raw PINs, entry codes, guest emails, or document numbers.
- Copy rule (`AGENTS.md` rule 9, `test_no_em_dashes.py`): zero em-dashes in CS, EN, VI strings (use commas, middle dots, or colons).

Exact excerpts to verify verbatim before editing:

1. `go/internal/web/stays/journey.go` (lines 34-66):
```go
type JourneySignal struct {
	ClaimState           string
	CompletionNotifiedAt string
	DoorCodeState        string
	DoorCodeNotifiedAt   string
	HasTTLock            bool
	HasEntryCode         bool
	FilesUbyPort         bool
}
```
2. `go/internal/web/stays/types.go` (lines 16-28):
```go
type Progress struct {
	Filled        int
	Expected      *int
	Incomplete    int
	Status        string
	Guests        []Guest
	NotRegistered *int
	HasCell       bool
	Cell          layout.DeadlineCell
	Anchor        time.Time
	HasAnchor     bool
	Unreadable    bool
}
```
3. `go/internal/web/stays/row_build.go` (lines 40-44):
```go
		guests := byStay[r.Reservation.ID]
		rows[i].Progress = buildProgress(st, guests, at)
		rows[i].Journey = BuildJourney(r.Reservation, rows[i].Progress, signals[r.Reservation.ID], pragueToday(at))
		lp := listProgress(st, guests, today)
```
4. `go/internal/web/stays/templates/stays_list.tmpl` (lines 81-84):
```html
  <td class="stay-rep-td" data-card="badge" data-label="{{t "stays.table.reporting"}}">
    {{if ne $res.Status "active"}}<span class="pill p-n">{{t (printf "stays.filter.state.%s" $res.Status)}}</span>
    {{else}}<div class="stay-rep-grid">{{if $row.Journey.Steps}}{{journey_strip $root.Lang $row.Journey}}{{end}}<div class="stay-rep-status">{{if $prog.HasCell}}{{template "v2_status_pill" $row}}{{if and (ne $prog.Cell.Level "overdue") (ne $prog.Cell.State "filed_on_time") (ne $prog.Cell.State "filed_late")}}<small>{{deadline_badge $prog.Cell}}</small>{{end}}{{else}}{{progress_pill $prog.Status $res.AutomationMode (kv "is_demo" (is_demo $res.InternalName $res.Source) "step" (journey_step $prog.Status))}}{{end}}</div></div>{{end}}
  </td>
```
5. `go/internal/hostweb/layout/icons.go` (line 36):
```go
	"mail":                    `<path d="m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"/><rect x="2" y="4" width="20" height="16" rx="2"/>`,
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/hostweb/layout/icons.go` | edit | Add `"mail-open"` Lucide 0.552.0 SVG path |
| `go/internal/web/stays/types.go` | edit | Add `ReportedCount int`, `ReportableCount int`, `ScheduledSendLabel string` to `Progress` |
| `go/internal/web/stays/progress_list.go` | edit | Populate `ReportedCount`, `ReportableCount` in `listProgress` / `buildProgress`; compute `ScheduledSendLabel` via `ubyport.ScheduledSendAt` when `AutomationMode` is `scheduled`/`immediate` and stay has pending reportable guests |
| `go/internal/web/stays/journey.go` | edit | Add latest `email_outbox` (`kind IN ('claim','claim_resend')`) state to `JourneySignal` & `journeySignalsSQL` (single batched LATERAL join); drop unused `has_entry_code`; upgrade `BuildJourney` to 5-step Option B (`email`, `opened`, `form`, `code` [TTLock only], `police`), 5 tones including `scheduled` (calm blue), all manual-action edge cases, and single concise `SummaryText` |
| `go/internal/web/stays/journey_test.go` | edit | Comprehensive unit + DB tests covering SES states (`queued`, `sent`, `failed`, `bounced`, `complained`, purged >14d), link opened, manual guest entry (unclaimed + rescue after bounce), manual filed by hand, partial filing (2/3), Czech-only `not_required` (including without UbyPort login), auto-scheduled calm blue, cancelled-after-report red, TTLock-only gating, and privacy (zero email/PIN leaks) |
| `go/internal/web/stays/row_build.go` | edit | Pass `AutomationMode` and `CheckinHour` (loaded in stays query if not already on `Reservation`) into `buildProgress` / `BuildJourney` |
| `go/internal/web/stays/comfy_i18n.json` | edit | CS, EN, VI labels & states for the 5 steps, manual paths, domovní kniha, calm blue scheduled, legend, and single-line summary (zero em-dashes) |
| `go/internal/web/stays/templates/stays_list.tmpl` | edit | Desktop row: render `journey_strip` + one single concise status sub-line from `Journey` (remove duplicate competing status pill); render cancelled-after-report warning when present; phone header: add compact collapsible `?` Legend (`<details class="journey-legend ph-only">`) |
| `go/internal/web/staydetail/view.go`, `go/internal/web/staydetail/templates/comfy/stay_detail_comfy.tmpl` | edit | Pass `ScheduledSendAt` into `BuildJourney`, show labeled 5-step horizontal bar (`email`, `opened`, `form` + `/housebook` link when complete, `code`, `police`) + plain-language "Now" sentence |
| `go/internal/web/hostweb/templates/dashboard.tmpl` | edit | Desktop Today/7-day row: replace duplicate competing pill with `journey_strip` + single summary sub-line; keep phone property rail compact |
| `App/app/static/comfy.css`, `App/app/static/comfy-polish.css`, `App/app/static/comfy-responsive.css` | edit | Add `[data-tone="scheduled"]` using `--info` / `#1f4e79`, ensure 5-step strip fits cleanly inside 390 px phone cards and `<= 72 px` desktop rows, style collapsible phone `?` legend |
| `docs/design/pages/stays.md` | edit | Update journey strip documentation to the 5-step Option B model + 5 tones + phone legend |

No other file may change (unless a test file in `stays`, `staydetail`, or `hostweb` asserts old 4-step markup/counts and needs updating to match). Do not edit Python files under `App/app/`.

## 4. Steps

1. **Icon (`go/internal/hostweb/layout/icons.go`):**
   - Add `"mail-open": `<path d="M21.2 8.4c.5.38.8.97.8 1.6v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V10a2 2 0 0 1 .8-1.6l8-6a2 2 0 0 1 2.4 0l8 6Z"/><path d="m22 10-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 10"/>`` right after `"mail"`.

2. **Progress & scheduled send time (`go/internal/web/stays/types.go`, `progress_list.go`, `row_build.go`):**
   - Add `ReportedCount`, `ReportableCount`, and `ScheduledSendLabel` to `Progress`.
   - In `listProgress`, record `sent` (only reportable guests with `submitState == "sent"`) and `len(res.reportable)`.
   - When `AutomationMode` is `"scheduled"` or `"immediate"` and stay is active with pending reportable guests, compute earliest pending `ubyport.ScheduledSendAt` in `Europe/Prague` and format compactly (e.g. `12.11. 15:00`) for `ScheduledSendLabel`.

3. **Batched SQL in `go/internal/web/stays/journey.go`:**
   - Replace `has_entry_code` (remove it) with a single `LEFT JOIN LATERAL` fetching the latest `email_outbox` row for `r.id` where `kind IN ('claim', 'claim_resend')`:
     ```sql
     LEFT JOIN LATERAL (
       SELECT COALESCE(o.state, '') AS claim_mail_state
       FROM email_outbox o
       WHERE o.reservation_id = r.id AND o.kind IN ('claim', 'claim_resend')
       ORDER BY o.id DESC
       LIMIT 1
     ) cm ON TRUE
     ```
   - Also fetch `COALESCE(a.automation_mode, 'manual')` and `a.checkin_hour` if not already on `Reservation`, so `BuildJourney` works uniformly on `/reservations`, `/reservations/{id}`, and `/`.

4. **Exact 5-step state machine in `BuildJourney` (pure function, zero DB calls):**
   - **Non-active stays (`res.Status != "" && res.Status != "active"`):**
     - If `res.Status == "cancelled" && prog.ReportedCount > 0 && !isDemo`: return a 1-step `StayJourney` with `Key: "police"`, `Icon: "police"`, `Tone: "bad"`, `StateKey: "cancelled_after_report"`.
     - Otherwise return empty `StayJourney{}`.
   - Compute helpers:
     - `isCheckInDayOrPast`: `today >= checkInDate` (parsed from `res.DateFrom`, fallback false).
     - `formComplete`: `prog.Filled > 0 && prog.Incomplete == 0 && (prog.Expected == nil || prog.Filled >= *prog.Expected)`.
     - `hostEntered`: `sig.ClaimState != "claimed" && (prog.Filled > 0 || prog.Incomplete > 0)`.
     - `manualRescue`: `(sig.ClaimState == "unclaimed" && hostEntered) || (sig.ClaimState == "provisional" && formComplete)`.
   - **Step 1 (`email`, icon `mail`):**
     - If `manualRescue`: `done` / `manual` (`zadáno ručně` / `added by host`).
     - Else if `sig.ClaimState == "claimed"`: `done` / `sent` (`odeslán` / `sent`).
     - Else if `sig.ClaimMailState` in `{"failed", "bounced", "complained"}`: `bad` / `failed` (`nedoručen` / `delivery failed`).
     - Else if `sig.ClaimMailState` in `{"queued", "sending"}`: `progress` / `sending` (`odesílá se` / `sending`).
     - Else if `sig.ClaimMailState == "sent"` or `sig.ClaimState == "provisional"`: `done` / `sent` (`odeslán` / `sent`) — *(SES sent succeeded! Step 2 shows whether guest opened it; if `provisional` and outbox row purged >14d, still shows `sent` rather than glitching back to grey)*.
     - Else (`unclaimed`, no claim mail): if `isCheckInDayOrPast` -> `progress` / `not_sent` (`nevyplněn e-mail` / `no email yet`), else `waiting` / `not_started` (`čeká` / `not started`).
   - **Step 2 (`opened`, icon `mail-open`):**
     - If `manualRescue`: `done` / `manual` (`zadáno ručně` / `added by host`).
     - Else if `sig.ClaimState == "claimed"`: `done` / `opened` (`otevřen` / `opened`).
     - Else if `sig.ClaimMailState` in `{"failed", "bounced", "complained"}`: `waiting` / `not_opened` (`neotevřen` / `not opened`) — *(Step 1 is already red so only one icon screams red)*.
     - Else if `sig.ClaimState == "provisional"` or `sig.ClaimMailState` in `{"queued", "sending", "sent"}`: `progress` / `unopened` (`neotevřen` / `not opened yet`).
     - Else: `waiting` / `not_opened` (`neotevřen` / `not opened`).
   - **Step 3 (`form`, icon `users`, Counter `n/m` or `n`):**
     - If `formComplete`: `done` / `complete` (`v domovní knize` / `in house book`).
     - Else if `prog.Filled > 0 || prog.Incomplete > 0`: `progress` / `partial` (`rozpracován` / `in progress`).
     - Else if `isCheckInDayOrPast`: `progress` / `missing_today` (`chybí` / `missing today`).
     - Else: `waiting` / `empty` (`nevyplněn` / `empty`).
   - **Step 4 (`code`, icon `key-round`) — ONLY when `sig.HasTTLock`:**
     - `failed` -> `bad` / `failed`; `delayed|retrying|issuing` -> `progress` / `issuing`; `issued` + notified -> `done` / `sent`; `issued` not notified -> `progress` / `ready`; else (`""`, `revoked`, etc.) -> `waiting` / `waiting`.
   - **Step 5 (`police`, icon `police`) — every non-demo stay:**
     - Order matters (strict precedence):
       1. `prog.Status == "not_required"` -> `done` / `not_required` (`netřeba (ČR)` / `not needed (CZ)`) — **checked before `!sig.FilesUbyPort`**!
       2. `prog.Status == "reported" || prog.Cell.State == "filed_on_time" || prog.Cell.State == "filed_late"` -> `done` / (`filed_manual` if `prog.Cell.ByHand` else `filed`).
       3. `prog.Status == "failed" || prog.Cell.Level == "overdue"` -> `bad` / (`overdue` if overdue else `failed`).
       4. `!sig.FilesUbyPort` -> `not_connected`: tone `bad` if `prog.ReportableCount > 0 || prog.Status == "ready" || prog.Status == "awaiting_verification"`, else `waiting`.
       5. `prog.Status == "awaiting_verification"` -> `progress` / `verify_id` (`ověřit doklad` / `verify ID`).
       6. `prog.ReportedCount > 0 && (prog.Status == "incomplete" || prog.ReportedCount < prog.ReportableCount)` -> `progress` / `partial` (Counter `fmt.Sprintf("%d/%d", prog.ReportedCount, max(prog.ReportableCount, deref(prog.Expected)))`).
       7. `prog.Status == "ready"`:
          - If `sig.AutomationMode` in `{"scheduled", "immediate"}`: **`scheduled`** (calm blue!) / `scheduled` (show `prog.ScheduledSendLabel` in sub-line/tooltip, e.g. `naplánováno · 12.11. 15:00`).
          - Else (`manual`): `progress` (amber) / `ready_manual` (`k odeslání` / `ready to send`).
       8. Default -> `waiting` / `waiting` (`čeká na hosty` / `waiting for guests`).

5. **Single concise sub-line + phone legend + Stay Detail:**
   - Add `JourneySummary(lang string, j StayJourney, prog Progress) (text, tone string)` returning **one** short plain-language line (e.g. `E-mail nedoručen`, `Naplánováno · 12.11. 15:00`, `K odeslání`, `V domovní knize · netřeba (ČR)`, `Nahlášeno`, `Čeká na hosty`, `Zrušeno po hlášení`).
   - On `/reservations` desktop rows (`stays_list.tmpl`) and Dashboard desktop table (`dashboard.tmpl`), render the icon strip + that single sub-line (removing the duplicate competing `v2_status_pill` / `dash.pill` when `Journey.Steps` is present).
   - On `/reservations` phone header, add a compact `<details class="journey-legend ph-only">` (`?` Legenda) listing the 5 icons + 5 color meanings cleanly without JS.
   - On Stay Detail (`stay_detail_comfy.tmpl`), render the labeled 5-step bar (`RenderJourneyBar`) and when Step 3 (`form`) is `done`, include a quiet `/housebook` link; keep the plain-language "Now" summary aligned with `JourneySummary`.

6. **CSS (`comfy.css`, `comfy-polish.css`, `comfy-responsive.css`):**
   - Add `[data-tone="scheduled"]` using existing `--info` background (`#eaf3fb`) and `#1f4e79` text (matching `.b-now` in `app2.css`).
   - Verify 5 icons + `n/m` counter stay on one single line on 390 px phone cards (no overflow, no wrap) and desktop rows remain `<= 72 px`.

7. **i18n (`comfy_i18n.json`, plus any key lists checked by tests):**
   - Keep CS, EN, VI in full parity; zero em-dashes; zero PII in labels/tooltips.

8. **Tests & UX gate:**
   - Run §6 Go unit/DB tests, `test_go_pages_layout_lint_browser.py`, inspect 390/768/1280 screenshots of `/reservations`, `/reservations/{id}`, and `/`, and run `python3 scripts/context_lint.py`.

## 5. Do not touch

- Anything under `App/app/` Python code or Jinja templates (only `App/app/static/comfy*.css`).
- `App/migrations_pg/` (zero DB migrations).
- Guest form pages, UbyPort submission workers, door-code workers, or `main`.
- Hard rules: light mode only; works without JS; no em-dashes; no new dependency; UX gate mandatory (Hard Rule 10).

## 6. Commands

Run from `go/`:
```bash
go test ./internal/web/stays/... ./internal/web/staydetail/... ./internal/web/hostweb/... ./internal/hostweb/layout/... -count=1 2>&1 | tail -30
```
Expected: `ok` for all 4 packages.

UX gate (from `App/`):
```bash
.venv/bin/python -m pytest tests/test_go_pages_layout_lint_browser.py -q --tb=short -x 2>&1 | tail -30
```
Expected: passes with `0 skipped`.

From repo root:
```bash
python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: `context lint: OK`.

## 7. Acceptance

- [ ] 5-step Option B strip (`email`, `opened`, `form`, `code` [TTLock only], `police`) renders across `/reservations` (desktop + phone), `/reservations/{id}`, and `/`.
- [ ] `email` step reads latest `email_outbox` (`claim`/`claim_resend`) in the single batched query (zero N+1) and surfaces `sending`, `sent`, and red `failed`/`bounced`/`complained`.
- [ ] `code` step shows ONLY for TTLock properties (`has_entry_code` subquery removed).
- [ ] `form` step shows `n/m` and `v domovní knize` / `in house book` when complete (with `/housebook` link on Stay Detail); no 6th icon.
- [ ] `police` step uses calm blue (`scheduled`) with formatted send time for auto-filing, green `netřeba (ČR)` for Czech-only stays (never flashes red without UbyPort), amber for manual ready / verify ID / partial (e.g. `2/3`), and red for `cancelled_after_report` / failed / overdue / not connected.
- [ ] All manual host actions (manual guest add, manual rescue after bounce, manual filed by hand, manual headcount change, partial early send) produce clean, non-glitching statuses tested in `journey_test.go`.
- [ ] Duplicate status pill removed on desktop `/reservations` & `/` rows; collapsible phone `?` legend works without JS.
- [ ] Privacy check: no raw email, PIN, entry code, or doc number appears in strip markup or tooltips.
- [ ] All §6 commands pass with 0 skipped; 390/768/1280 screenshots inspected and described in PR & report.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt in §2 is not found verbatim;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see `docs/context/executor.md`);
- a new dependency or DB migration seems needed;
- a file outside §3 needs a change;
- §5 would be touched.

## 9. Report

Write `docs/tasks/2097-report.md` (<=600 tokens), set `Status: review`, open one PR (include per-page 390/768/1280 screenshot notes and ticked design-system checklist). Report: `git diff --stat`, command tails, §7 ticked, deviations, questions, owner steps.
