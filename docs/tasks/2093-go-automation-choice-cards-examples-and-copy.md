# 2093: Go automation choice cards, `?` examples, stay send time, and copy

Status: todo
Depends on: 2091, 2092 | Base commit: 52c418cf5 | Branch: task/2093-go-automation-choice-cards-examples-and-copy
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Give hosts crystal-clear explanations with concrete Monday `15:00` examples inside a `?` (`help_tip`) on **every** police-send option in both Property settings (replacing the `<select>` with the same 3 `choice_card` cards used in the wizard) and the onboarding wizard, show the exact computed automatic send time on Stay detail, and update all stale status pill, rehearsal, and `/guide#reporting` copy across `cs`, `en`, and `vi`.

## 2. Context

- **Tier C + UX gate (Go-only):** Never touch `App/app/` (owner 2026-11-27).
- Plan: `docs/plans/checkin-anchored-auto-filing.md`.
- Design rules: read `docs/design/design-system.md` before editing templates; light mode only; forms work without JS; Hard Rule 9 (one explanation in one place — short scannable card title, full rule + concrete example inside `?`); Hard Rule 10 UX gate (`test_go_pages_layout_lint_browser.py` + 390/768/1280 screenshots inspected per touched page).
- **Exact copy for each option's `?` tooltip** (translate naturally to `cs` and `vi`; no em-dashes per `test_no_em_dashes.py` — use commas or colons):
  1. `scheduled` — title: **Automatically after check-in (recommended)** (`Automaticky po příjezdu (doporučeno)` / `Tự động sau giờ nhận phòng (khuyên dùng)`)
     - `?`: `Sends each completed guest automatically after the delay you set from check-in time, or after that guest finishes the form if later, and always at least 6 hours before the 3-working-day police deadline. Example (check-in Mon 15:00, 24 h delay): form done Friday -> sends Tue 15:00; form done Tue 10:00 -> sends Wed 10:00; form done Wed 14:00 -> sends Wed 17:59. Never sent before check-in.`
  2. `immediate` — title: **Right after check-in** (`Ihned po příjezdu` / `Ngay sau giờ nhận phòng`)
     - `?`: `Sends each completed guest automatically as soon as check-in time starts. Example (check-in Mon 15:00): form done Friday -> waits and sends Mon 15:00; form done Mon 18:00 -> sends right away. You can still press Send earlier anytime.`
  3. `manual` — title: **Only when I press Send** (`Jen po stisknutí Odeslat` / `Chỉ khi tôi nhấn Gửi`)
     - `?`: `UbyHost never sends on its own. You review each stay and press Send yourself. Example (check-in Mon 15:00): stays wait for your click, and the police deadline is Wed 23:59. UbyHost still alerts you when the deadline is close.`
- Card order on both wizard and Property settings: `scheduled` (recommended, default 24 h) first, then `immediate`, then `manual`.
- **Stay detail computed send time:** call `ubyport.ScheduledSendAt(...)` in `go/internal/web/staydetail/` for unfiled active stays on `scheduled` / `immediate` apartments and display one compact fact line (e.g. `Scheduled to send: 12.11.2026 15:00` in Prague time) when `ok` is true and the stay is not yet reported.
- **Status pills (`status.ready_immediate` / `status.ready_scheduled`):** stop saying *"Complete (sending now)"* / *"measured from completion"*. Use *"Ready (auto at check-in)"* / *"Ready (scheduled)"* with accurate check-in-anchored tips so pre-arrival completed stays never look stuck.

Verbatim excerpt to match in `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl`:
```html
    <section class="panel property-section ui-section" id="automation">
      <div class="field-label-row"><h2 class="property-section-title">{{t "automation.timing_title"}}{{help_tip "automation-help" (t "automation.timing_help") "/guide#reporting"}}</h2></div>
      <p class="ui-sub">{{t "why.automation"}}</p>
      <div class="grid two">
        <div class="field">
          <label for="automation_mode">{{t "automation.timing_label"}}</label>
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl` | edit | Replace `#automation` `<select>` with the 3 `choice_card` options (`scheduled`, `immediate`, `manual`), each with its `?` (`help_tip`) and nested `submit_after_hours` input (`min="1" max="24"`) inside `scheduled` |
| `go/internal/web/properties/apartmentdetail/i18n.json` | edit | Update `automation.*` and `why.automation` strings in `cs`, `en`, `vi` with the §2 titles and `?` examples |
| `go/internal/web/onboarding/wizardtemplates/police.tmpl` | edit | Order choice cards `scheduled` (default), `immediate`, `manual`; ensure each card's `?` uses the §2 example copy |
| `go/internal/web/onboarding/wizardtext/i18n.json` | edit | Update `automation.mode.*`, `wizard.automation.*_detail`, `wizard.rehearsal.police_*`, `workflow.step.police_*` in `cs`, `en`, `vi` |
| `go/internal/web/staydetail/load.go` | edit | Load `a.checkin_hour` on the stay query and compute `ScheduledSendAt` (formatted Prague time) for unfiled auto stays |
| `go/internal/web/staydetail/templates/stay_detail.tmpl` | edit | Show the computed automatic send time line when present |
| `go/internal/web/staydetail/templates/comfy/stay_detail_comfy_lower.tmpl` | edit | Mirror the computed automatic send time line on the comfy stay view if applicable |
| `go/internal/web/staydetail/i18n.json` | edit | Add `stay.scheduled_send_at` label in `cs`, `en`, `vi` |
| `go/internal/hostweb/layout/i18n.json` | edit | Update `status.ready_immediate`, `status.ready_immediate_tip`, `status.ready_scheduled_tip` in `cs`, `en`, `vi` |
| `go/internal/web/stays/i18n.json` | edit | Keep `status.ready_immediate*` and `status.ready_scheduled_tip` identical to layout |
| `go/internal/web/hostweb/calendar_i18n.json` | edit | Keep `status.ready_immediate*` identical to layout |
| `go/internal/web/public/catalog_pages.json` | edit | Update `guide.reporting.immediate_detail` and `guide.reporting.scheduled_detail` in `cs`, `en`, `vi` |
| `go/internal/web/staydetail/view_test.go` | edit | Add test verifying computed automatic send time renders for a pre-arrival scheduled stay and hides for reported/manual stays |
| `go/internal/web/properties/apartment_detail_test.go` | edit | Verify the 3 `choice_card` radios + 3 `?` tooltips with examples render on Property settings |

No other file may change.

## 4. Steps

1. Update `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl` and `i18n.json`:
   - Replace the `<select id="automation_mode">` grid with the same `.choice-cards` pattern used in `wizardtemplates/police.tmpl`:
     1. `scheduled` (with nested `submit_after_hours` `min="1" max="24"`)
     2. `immediate`
     3. `manual`
   - Each card carries its own `help_tip` (`?`) with the §2 explanation + Mon `15:00` example (no em-dashes).
   - Keep `default_purpose` field below untouched.
2. Update `go/internal/web/onboarding/wizardtemplates/police.tmpl` and `wizardtext/i18n.json`:
   - Match card order (`scheduled`, `immediate`, `manual`) and exact `?` example copy (`cs`, `en`, `vi`).
   - Update `wizard.rehearsal.police_scheduled` (e.g. `With a real stay it goes out automatically %(hours)s hours after check-in (never before).`) and `wizard.rehearsal.police_immediate` (`With a real stay it goes out automatically once check-in starts.`).
3. Update `go/internal/web/staydetail/load.go`, `stay_detail.tmpl`, `stay_detail_comfy_lower.tmpl`, and `staydetail/i18n.json`:
   - Select `a.checkin_hour`, call `ubyport.ScheduledSendAt` when stay is active and has unfiled reportable guests, and format as `DD.MM.YYYY HH:MM` in `Europe/Prague`.
   - Render the compact line next to the filing status (omit for `manual`, demo, or already-reported stays).
4. Update `status.ready_immediate*` / `status.ready_scheduled_tip` in `go/internal/hostweb/layout/i18n.json`, `go/internal/web/stays/i18n.json`, and `go/internal/web/hostweb/calendar_i18n.json`, and update `guide.reporting.{immediate,scheduled}_detail` in `go/internal/web/public/catalog_pages.json` across `cs`, `en`, `vi`.
5. Add Go tests in `apartment_detail_test.go` and `staydetail/view_test.go`.
6. Run §6 Go tests + UX gate (`test_go_pages_layout_lint_browser.py`), inspect 390/768/1280 screenshots of Property settings, Wizard Step 3, and Stay detail, and record findings in the report and PR.

## 5. Do not touch

- Anything under `App/app/` (Python is retired).
- `go/internal/ubyport/` (already completed in 2091).
- Hard rules: light mode only; no em-dashes in copy; works without JS; UX gate mandatory (Hard Rule 10); no new dependency.

## 6. Commands

Run from `go/`:
```bash
go test ./internal/web/properties/... ./internal/web/onboarding/... ./internal/web/staydetail/... ./internal/web/stays/... ./internal/hostweb/... ./internal/web/public/... 2>&1 | tail -30
```
Expected: `ok` for all 6 packages.

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

- [ ] Property settings and Onboarding wizard Step 3 both show the 3 `choice_card` options (`scheduled`, `immediate`, `manual`) in identical order, each with a `?` tooltip containing the rule and Mon `15:00` example in `cs`, `en`, `vi`.
- [ ] Stay detail shows the computed Prague automatic send time for unfiled stays on `scheduled`/`immediate` properties.
- [ ] Status pills, wizard rehearsal, and `/guide#reporting` accurately describe check-in-anchored timing in `cs`, `en`, `vi` (zero em-dashes).
- [ ] `test_go_pages_layout_lint_browser.py` passes with 0 skipped, and 390/768/1280 screenshots of Property settings, Wizard Step 3, and Stay detail are checked with findings noted in the report/PR.
- [ ] Zero files under `App/app/` changed; all §6 commands pass.

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

Write `docs/tasks/2093-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked + UX gate screenshot notes per page (390/768/1280).
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl`
- `go/internal/web/staydetail/load.go`
- 390/768/1280 screenshots for Property settings, Wizard Step 3, and Stay detail (Hard Rule 10)

## Owner steps

1. After CI is green and the UX gate checklist is ticked in the PR, merge with `scripts/merge-pr-on-green.sh <PR>`.
2. Spot-check Property settings `#automation` and Wizard Step 3 on phone (390 px) and desktop: tap each `?` and verify examples read cleanly in Czech and English.
