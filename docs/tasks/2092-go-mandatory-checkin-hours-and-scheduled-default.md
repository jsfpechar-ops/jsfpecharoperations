# 2092: Go mandatory check-in/out hours and scheduled 24 h default

Status: todo
Depends on: 2091 | Base commit: 52c418cf5 | Branch: task/2092-go-mandatory-checkin-hours-and-scheduled-default
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make check-in and check-out hours mandatory on `/apartments/new`, Copy-from-property, and Property settings (closing every gap where properties were saved with `NULL` hours, without backfilling legacy DB rows), and default new properties to `scheduled` with `24` hours (`1..24` range everywhere) while leaving existing properties' saved modes untouched.

## 2. Context

- **Tier B (Go properties & onboarding):** Go only — never touch `App/` (owner 2026-11-27).
- Plan: `docs/plans/checkin-anchored-auto-filing.md`.
- **Why legacy `NULL` rows stay untouched:** `go/internal/doorcodes/helpers.go` and `go/internal/web/properties/smart_locks.go` treat non-NULL `checkin_hour`/`checkout_hour` as host-confirmed door-code times. Do NOT write a migration backfilling `NULL` rows.
- Current gaps verified in code:
  1. `/apartments/new` (`apartment_new.tmpl`, `apartment_create.go`) omits `checkin_hour` / `checkout_hour` and redirects to `/setup/calendar` (skipping Step 1 `/setup/property`).
  2. `apartmentCopyKeys` (`apartment_create.go:58`) and `apartmentNewSourceSQL` (`apartment_new.go:203`) omit `checkin_hour` / `checkout_hour`.
  3. `apartment_create.go:202-212` defaults `automation_mode` to `"manual"` and clamps `submit_after_hours` to `48`.
  4. `go/internal/web/onboarding/wizard_pages.go:29-35` defaults `AutoMode()` to `"manual"`; `wizard_post.go:75,86-97` validates `1..48` and falls back to `"manual"`.
  5. `apartment_detail.tmpl:293-300` leaves `checkin_hour` / `checkout_hour` optional (`<option value="">`) and `apartment_update.go` allows saving them blank unless TTLock is active; `apartment_detail.tmpl:489` allows `min="0" max="48"` even though `0` silently meant `24`.

Verbatim excerpts to match before editing:

`go/internal/web/properties/apartment_create.go`:
```go
var apartmentCopyKeys = []string{"automation_mode", "submit_after_hours", "default_purpose", "permalink_window_days",
	"permalink_reachback_days", "stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_authority_name",
	"stay_fee_authority_address", "stay_fee_authority_contact", "stay_fee_payee", "stay_fee_instruction",
	"stay_fee_council_account"}
```
```go
	mode := formStr(r, "automation_mode")
	if !truthy(r, "automation_mode") {
		mode = "manual"
	}
	if mode != "immediate" && mode != "scheduled" && mode != "manual" {
		mode = "manual"
	}
	hours := int64(24)
	if h := int64Of(ints["submit_after_hours"]); h != 0 {
		hours = min(h, 48)
	}
```

`go/internal/web/onboarding/wizard_pages.go`:
```go
func (v *wizardView) AutoMode() string {
	switch v.Values.AutomationMode {
	case "manual", "scheduled", "immediate":
		return v.Values.AutomationMode
	}
	return "manual"
}
```

`go/internal/web/onboarding/wizard_post.go`:
```go
	if mode == "scheduled" {
		if h := wizardFormInt(r, "submit_after_hours"); h == nil || *h < 1 || *h > 48 {
			return "flash.properties.timing_hours"
		}
	}
```

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/web/properties/apartment_new.go` | edit | Add `CheckinHour`/`CheckoutHour` to `ApartmentNewForm` / `apartmentNewView` (preselected `15`/`10` when unset), select and prefill them in `apartmentNewSourceSQL` |
| `go/internal/web/properties/apartmentnew/apartment_new.tmpl` | edit | Render required `checkin_hour` and `checkout_hour` `<select>` pickers (00:00–23:00, preselected `15:00`/`10:00`) in Basics card |
| `go/internal/web/properties/apartmentnew/i18n.json` | edit | Ensure check-in / check-out hour labels and required-times error key exist in `cs`/`en`/`vi` |
| `go/internal/web/properties/apartment_create.go` | edit | Parse/validate required `checkin_hour` and `checkout_hour` (`0..23`), include in `apartmentCopyKeys` & insert columns; default `automation_mode` to `"scheduled"`, `submit_after_hours` to `24` (clamped `1..24`) |
| `go/internal/web/properties/apartment_update.go` | edit | Refuse blank `checkin_hour`/`checkout_hour` on settings save (`sharedTimeError`); validate `submit_after_hours` in `1..24` when `automation_mode == "scheduled"` |
| `go/internal/web/properties/apartmentdetail/apartment_detail.tmpl` | edit | Mark `checkin_hour`/`checkout_hour` `required` (preselect `15`/`10` only visually if `NULL`, plus show a short inline note when stored `CheckinHour == nil` that auto-filing uses 15:00 until saved); set `submit_after_hours` `min="1" max="24"` |
| `go/internal/web/onboarding/wizard_pages.go` | edit | Default `AutoMode()` to `"scheduled"`; set `submit_after_hours` input `min="1" max="24"` and default value `"24"` when empty/zero |
| `go/internal/web/onboarding/wizard_post.go` | edit | Validate `1..24` in `wizardAutomationChoiceError`; default `wizardAutomationTiming` to `"scheduled"` + `24` (clamped `1..24`) |
| `go/internal/web/properties/apartment_create_test.go` | edit | Update/add tests for required `checkin_hour`/`checkout_hour`, copy-from-property hours, and `scheduled` 24 h default |
| `go/internal/web/properties/apartment_update_test.go` | edit | Update/add tests refusing blank `checkin_hour`/`checkout_hour` and out-of-range `submit_after_hours` (`0` or `25`) |
| `go/internal/web/properties/apartment_new_test.go` | edit | Assert `checkin_hour` / `checkout_hour` selects render required with `15:00` / `10:00` selected |
| `go/internal/web/onboarding/wizard_test.go` | edit | Assert default `AutoMode == "scheduled"`, default hours `24`, range `1..24` |

No other file may change. (If golden JSON test fixtures in `go/internal/web/properties/testdata/` or `go/internal/web/onboarding/testdata/` fail because of these deliberate changes, STOP per §8 or update only the affected assertions noted in the tests — do not edit `App/`.)

## 4. Steps

1. In `go/internal/web/properties/apartment_new.go` and `apartmentnew/apartment_new.tmpl`:
   - Add `checkin_hour, checkout_hour` to `apartmentNewSourceSQL` and prefill from copied property (else default `15` and `10`).
   - Render both `<select required>` fields (`00:00`..`23:00`) under `#basics` using the same markup and labels as `wizardtemplates/property.tmpl` (works without JS).
   - Add any missing label/error keys to `apartmentnew/i18n.json` (`cs`, `en`, `vi`).
2. In `go/internal/web/properties/apartment_create.go`:
   - Add `"checkin_hour", "checkout_hour"` to `apartmentCopyKeys`.
   - Parse and validate `checkin_hour` and `checkout_hour` as integers `0..23`; refuse create (HTTP 400 re-render with `flash.error.times_required`) if missing or invalid.
   - Insert `checkin_hour` and `checkout_hour` on `POST /apartments`.
   - Change default `automation_mode` from `"manual"` to `"scheduled"` and clamp `submit_after_hours` to `1..24` (default `24`).
3. In `go/internal/web/properties/apartment_update.go` and `apartmentdetail/apartment_detail.tmpl`:
   - On settings save, whenever `checkin_hour` or `checkout_hour` is posted blank/invalid (or stored `NULL` when saving `#arrival-departure`), refuse with `sharedTimeError` (`flash.error.times_required`) so a host cannot clear times back to `NULL`.
   - When `automation_mode == "scheduled"`, validate `submit_after_hours` is `1..24` (refuse with `flash.properties.timing_hours` on `0` or `>24`).
   - In `apartment_detail.tmpl`: add `required` on `checkin_hour` and `checkout_hour`; when stored `CheckinHour == nil` show a compact `.hint` noting automatic filing uses `15:00` until saved; set `submit_after_hours` to `min="1" max="24"`.
4. In `go/internal/web/onboarding/wizard_pages.go` and `wizard_post.go`:
   - Change `AutoMode()` fallback to `"scheduled"`.
   - Ensure `HoursField()` uses `min="1" max="24"` and defaults empty/`"0"` to `"24"`.
   - Update `wizardAutomationChoiceError` (`*h < 1 || *h > 24`) and `wizardAutomationTiming` (default `"scheduled"`, `24`, clamp `1..24`).
5. Update and add Go unit tests in §3; run §6 commands.

## 5. Do not touch

- Anything under `App/` (Python is retired).
- `go/migrations/` (no migration, no silent backfill of legacy `NULL` hours).
- `go/internal/doorcodes/` (door code `IS NOT NULL` guards remain intact).
- Hard rules: light mode only; forms work without JavaScript; no new dependency.

## 6. Commands

Run from `go/`:
```bash
go test ./internal/web/properties/... ./internal/web/onboarding/... 2>&1 | tail -30
```
Expected: `ok` for both packages.

Run from repo root:
```bash
python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: `context lint: OK`.

## 7. Acceptance

- [ ] `/apartments/new` requires check-in and check-out hours (preselected `15:00` / `10:00`), Copy-from-property copies them, and `POST /apartments` persists them and defaults new properties to `scheduled` + `24` h.
- [ ] Property settings refuses clearing check-in/check-out hours to blank and refuses `submit_after_hours` outside `1..24`.
- [ ] Legacy properties with `NULL` `checkin_hour` are NOT silently backfilled in Postgres and show the inline `15:00` fallback note until saved.
- [ ] Onboarding wizard Step 3 defaults to `scheduled` + `24` h with `min="1" max="24"`.
- [ ] Zero files under `App/` changed; all §6 commands pass.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change (including any golden fixture file not listed in §3);
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/2092-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/web/properties/apartment_create.go`
- `go/internal/web/properties/apartment_update.go`
- `go/internal/web/onboarding/wizard_post.go`

## Owner steps

1. Merge PR after green CI with `scripts/merge-pr-on-green.sh <PR>`.
2. Spot-check `/apartments/new` on staging: verify `15:00` / `10:00` preselected and newly created property lands on `scheduled` / `24` h.
