# 2063: Go guest stay page: port the stay-fee box (`_fee_pay.html`, `_fee_why.html`)

Status: todo
Depends on: 2055 to 2062 merged (stay.tmpl exists) | Base commit: HEAD | Branch: current
Executor: Haiku 5.5 | Fits one session: 30 tool calls (stop at 25; commit after every step: `2063 step k`)
Run order: this brief first, then [2064](2064-go-guest-stay-fee-parity-case.md) (parity case). Different files, no overlap.
Executor trailers (every commit):
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf`

## 1. Objective

Production has `UBYHOST_STAY_FEE_GUEST_PAY=on` and 2 apartments with `stay_fee_collect=1`, so guests see Python's fee box on the claimed-stay page. Go renders none (2055 section 10 deferred it). Show the same box, same text, same classes, before the Go guest deploy (owner Option 1).

## 2. Context (orchestrator findings; all verified by grep)

- Python: `stay_overview` (App/app/routes/guest.py ~1580) sets `fee_panel = _fee_pay_panel(apartment, reservation, t)` **only when `remaining is not None and remaining <= 0`**; else None. `_fee_pay_panel` (guest.py:2904): None unless `apartment.stay_fee_collect` and `config.STAY_FEE_GUEST_PAY` (`UBYHOST_STAY_FEE_GUEST_PAY` lowercased/stripped `== "on"`, config.py:401) and `charge.total_czk > 0`. Fields: `total`, `rate`, `persons` (one `{days, amount}` per guest with liable nights > 0), `rails` (iban: account + QR data URI of the SPAYD, QR only when spayd non-empty; revolut: link; cash: note or `t("fee_cash_default")`), `vs` (reservation id), `payee`.
- stay.html: `{% if fee_panel %}{% include "guest/_fee_pay.html" %}{% endif %}` sits right after the `just_removed` card and before the party stepper. `_fee_pay.html` includes `_fee_why.html`. The all-done paragraph uses `all_done_body_fee if fee_panel else all_done_body`.
- **Go already has everything but the view glue (reuse, do not reimplement):**
  - `stayfee.CompletionFeeOf` / `stayfee.LoadCompletionFee` (`go/internal/stayfee/completion_fee.go:50` / `:184`) = Python `_completion_fee`: same gates (Collect, guestPay, active rate, total > 0), `Total`, `Rate`, `Lines [][2]int` (liable nights, amount; liable > 0 only), `VS`, `Ways []CompletionWay` (iban: `Payee`, `Account` already `FormatIBAN`, `SPAYD` empty unless a CZE/SVK guest; revolut: `Link`; cash: `Note`), built with `payoutAccount`, `usableRails`, `SPAYD(account,total,vs,"Stay fee "+vs)` (`go/internal/stayfee/report.go:184`). It is golden-tested against Python (`completion_fee_test.go`, `testdata/completion_fee_golden.json`).
  - Callers to copy the call shape from: `go/internal/mailjob/feeupdate.go:308`, `go/internal/doorcodes/wire/billing.go:110`. Guest-pay switch read in Go the same as Python: `go/cmd/ubyhost-web/door_codes_wire.go:93` (`strings.ToLower(strings.TrimSpace(env)) == "on"`); the host side has `guestPayOn` (`go/internal/web/stayfees/guestpay_preview.go:34`, unexported: do not call).
  - QR image: `payments.QRDataURI(payload)` (`go/internal/payments/qrdatauri.go:11`), same as Python `qr_data_uri` (medium EC, 6 px modules).
  - Apartment row: `stayfee.LoadApartment(ctx, q, id)` (`loader.go:78`). Decrypter: `stayfee.FernetDecrypter(keys)` (`loader.go:26`); `guestSaveDecrypter(getenv)` in `go/internal/web/guest/stay_claim.go:654` shows how the guest package gets its keys: STOP and ask if no `*secure.MultiFernet` is reachable from `stayClaimDeps` (step 2 says how to look).
- Go page: `renderStayPage` (`go/internal/web/guest/stay_view.go:173`) builds `stayView`; `Remaining`/`HasRemaining` are set at about line 226. `stay.tmpl` has no fee block yet (the comment in `stay_view.go:18-19` says so; remove it in step 3). The all-done paragraph is `{{.T "all_done_body"}}` at stay.tmpl:41.
- i18n: every key the partials use already exists in `go/internal/web/guest/i18n.json` for cs, de, en, es, fr, uk (checked: `fee_amount fee_amount_label fee_box_group fee_calc_group fee_cash_default fee_guest_n fee_iban fee_law_link fee_no_rails fee_now_body fee_now_title fee_payee fee_per_person fee_person_line fee_qr_alt fee_rail_cash fee_rail_iban fee_rail_revolut fee_rate_line fee_revolut_button fee_vs_label fee_why fee_why_body`). **No key copying is needed**; step 5 only proves it. `all_done_body_fee` exists (2055).
- Guest CSS (`.g-fee-*`) is the shared `App/app/static/guest.css`: no CSS change.

## 3. Files

| Path | Action |
|---|---|
| `go/internal/web/guest/stay_fee_panel.go` | new: `feePanel` types, `buildFeePanel` (pure), `loadFeePanel` (DB) |
| `go/internal/web/guest/stay_view.go` | edit `stayView` (+`FeePanel *feePanel`), `renderStayPage` (call `loadFeePanel` when remaining <= 0), drop the "not ported" comment |
| `go/internal/web/guest/stay_claim.go` | only if `stayClaimDeps` lacks what step 2 needs (a `keys`/decrypter field): add it and set it where `stayClaimDeps{` is built |
| `go/internal/web/guest/templates/stay.tmpl` | edit: fee block after `JustRemoved`; `all_done_body_fee` |
| `go/internal/web/guest/templates/_fee_pay.tmpl` | new (port of `_fee_pay.html` + `_fee_why.html`) |
| `go/internal/web/guest/pages.go` | edit `staySet` to include the new partial (see `pageSet(...)`) |
| `go/internal/web/guest/stay_fee_panel_test.go` | new: unit test of `buildFeePanel` + DB-backed render test |
| `docs/tasks/2063-report.md` | report |

## 4. Steps

1. **Anchors.** `grep -nF 'func (d stayClaimDeps) renderStayPage' go/internal/web/guest/stay_view.go`; `grep -nF 'view.DoorCode = doorCodeCardFrom(door)' go/internal/web/guest/stay_view.go`; `grep -nF '{{.T "all_done_body"}}' go/internal/web/guest/templates/stay.tmpl`; `grep -n 'staySet' go/internal/web/guest/pages.go`; `grep -n 'stayClaimDeps{' -r go/ | head`; `grep -n 'MultiFernet\|FernetDecrypter' go/internal/web/guest/*.go go/cmd/ubyhost-web/*.go | grep -v _test | head`. Any missing: STOP.
2. **Decrypter + today.** Read `feeupdate.go` 295-312 and `billing.go` 95-112 (ranges of 20 lines). Use the same `today` rule (Prague date, `stayfee.Day`/`ISO`; `d.now()` is the clock here). Decrypter: reuse whatever `stayClaimDeps`/`d.getenv` already gives `guestSaveDecrypter` (the Fernet keys come from env); wrap with `stayfee.FernetDecrypter`. Do not add a dependency.
3. **`stay_fee_panel.go`.**
   - `type feeRail struct{ Key, IBAN, QR, Link, Note string; HasQR bool }` (iban groups: split into 4-char groups in Go: `strings.Fields` when it has a space, else chunks of 4 of the space-stripped value: same as the Jinja line in `_fee_pay.html`; expose `IBANGroups []string`), `type feePerson struct{ Days, Amount int }`, `type feePanel struct{ Total, Rate int; Persons []feePerson; Rails []feeRail; VS, Payee string; Group bool; Guests, Days int }`.
   - `func buildFeePanel(fee *stayfee.CompletionFee, qr func(string) (string, error), cashDefault string) *feePanel`: nil in, nil out. `Persons` from `fee.Lines`. `Group = len(persons) > 1 && all persons have the same Days` (Python: `nights|length == 1`), `Guests = len(persons)`, `Days = persons[0].Days`. `Payee` = the iban way's `Payee`. Rails in `fee.Ways` order: iban -> `IBAN: way.Account`, `QR` = `qr(way.SPAYD)` only when `SPAYD != ""` (error: leave QR empty, never fail the page); revolut -> `Link`; cash -> `Note`, or `cashDefault` (the translated `fee_cash_default`) when empty. Pass `payments.QRDataURI` as `qr` from the caller.
   - `func (d stayClaimDeps) loadFeePanel(ctx, apt *Apartment (guest pkg) / apartment id, reservationID int64, lang string, t func(key string) string) *feePanel`: guestPay switch as in section 2; load `stayfee.LoadApartment`; call `stayfee.LoadCompletionFee(ctx, d.pool, dec, ap, resID, guestPay, today)`; any error: `log.Printf("stay_fee_panel_failed reservation=%d err=%v", ...)` and return nil (Python drops the box on a read failure the same way). Never log amounts, accounts or names.
   - Commit `2063 step 3`.
4. **View + template.** In `renderStayPage`, right after the `HasRemaining` block: `if view.HasRemaining && view.Remaining <= 0 { view.FeePanel = d.loadFeePanel(...) }` (Python builds it only then). Add `FeePanel *feePanel` to `stayView`; delete the two-line "not ported" comment. In `stay.tmpl` after the `{{end}}` of the `JustRemoved` block insert `{{if .FeePanel}}{{template "fee_pay" .}}{{end}}` and change line 41 to `{{if .FeePanel}}{{.T "all_done_body_fee"}}{{else}}{{.T "all_done_body"}}{{end}}`. Write `_fee_pay.tmpl` as `{{define "fee_pay"}}...{{end}}`, a line-for-line port of `_fee_pay.html` (read it in one go, 70 lines) plus `_fee_why.html` inlined at the end: same classes/ids/order; `fee_amount` with `amount=.FeePanel.Total`; the calc line is `fee_calc_group` (`guests`, `days`, `rate`) when `.Group` else `fee_rate_line` (`rate`); `fee_person_line` (`days`, `rate`, `amount`); `fee_guest_n` (`n` = 1-based index: Go templates have no `loop.index`, use `{{range $i, $p := ...}}` with a registered `add1`-style func if one exists: `grep -n 'Funcs' go/internal/web/guest/*.go | head`; else precompute `N` in `feePerson`); `fee_revolut_button` (`amount`); payee row only when non-empty; QR `<img>` only when `HasQR`; IBAN `<span>` groups each followed by a space; the `{{if .Rails}}...{{else}}fee_no_rails{{end}}`. Escape rules: `src=` needs `template.URL` for the data URI (see how `ReadyQRURL` does it in `onboarding/wizard_finish.go:40`). Add the partial to `staySet` in `pages.go`. Run `cd go && go build ./internal/web/guest/ 2>&1 | tail -30`. Commit `2063 step 4`.
5. **Tests** (`stay_fee_panel_test.go`; same style as `stay_page_test.go`, which has `testPool`, `mustExec`, the seeding shape and the `Skip` guard; 0 skips are required when `UBYHOST_TEST_DATABASE_URL` is set):
   - `TestBuildFeePanel`: (a) 3 lines of (2 nights, 100) with rate 50 -> `Group` true, `Guests` 3, `Days` 2, `Total` copied; (b) lines (2,100) and (3,150) -> `Group` false (rate line); (c) payload: build a `CompletionFee` with an iban way whose `SPAYD` is `stayfee.SPAYD(account, total, vs, "Stay fee "+vs)`, call `buildFeePanel` with `payments.QRDataURI`, assert the rail `QR` equals `payments.QRDataURI(thatSameSPAYD)` and the SPAYD starts with `SPD*1.0*ACC:`; (d) no SPAYD -> rail has no QR; (e) cash with empty note -> default text; (f) nil fee -> nil.
   - `TestStayPageFeeBox`: seed (new ids, e.g. 2063xx) an apartment with `stay_fee_collect=1`, a positive `stay_fee_rate_czk`, an IBAN account the way `completion_fee_test.go`/`golden` does (`grep -n 'iban\|bank_account\|legal_entity' go/internal/stayfee/completion_fee_test.go | head`), one claimed reservation with `declared_guests` = 1 and one complete CZE guest (copy the guest insert from `stay_page_test.go`). With env `UBYHOST_STAY_FEE_GUEST_PAY=on` (the deps' `getenv`): body contains `g-fee-box`, `g-fee-amt` with the amount, `g-fee-qr-img` and `data:image/png;base64,`, and not the plain `all_done_body` text. With the env `off` (or unset): no `g-fee-box`. With `declared_guests` = 2 and one guest (remaining 1): no `g-fee-box` even when on.
   - `TestFeeKeysAllLanguages`: load `i18n.json` through the package's catalogue and assert every key listed in section 2 resolves non-empty for cs, de, en, es, fr, uk.
   - Run (section 6). Commit `2063 step 5`.
6. **Report** `docs/tasks/2063-report.md` (600 tokens max), `Status: review`, open one PR (draft).

## 5. Do not touch

`App/**`, `scripts/e2e/**` (that is 2064), `stay_claim.go` except step 2's field, `go/internal/stayfee/**` (reuse only; a gap there: STOP and ask), `go/internal/web/stayfees/**`, `go/internal/web/properties/**`, CSS.

## 6. Commands

```
cd go && go build ./internal/web/guest/ 2>&1 | tail -30
cd go && go vet ./internal/web/guest/ 2>&1 | tail -30
cd go && go test ./internal/web/guest/ ./internal/stayfee/ -run 'FeePanel|FeeBox|FeeKeys|Stay|Completion' -count=1 -v 2>&1 | tail -30   # needs UBYHOST_TEST_DATABASE_URL, 0 skipped
cd App && .venv/bin/python -m pytest tests/test_guest_browser_e2e.py tests/test_host_geometry.py -q -rs --tb=short -x 2>&1 | tail -30   # rule 7: 0 skipped (shared guest.css, template untouched on the Python side; run once)
```
Guest page change (rule 7): the guest browser and geometry tests with 0 skipped, plus one 390 px screenshot of the claimed stay page with the fee box (seeded as in 2064, or the DB test's page rendered by the Go parity tool when 2064 is done) in the PR. Do not run the parity tool in this brief.

## 7. Acceptance

- [ ] `buildFeePanel` unit test passes; QR payload equals the existing `stayfee.SPAYD` output through `payments.QRDataURI`.
- [ ] DB test: box shown (amount, QR) with guest pay on and all guests in; hidden with it off; hidden while someone is missing.
- [ ] Key test passes for six languages.
- [ ] Guest browser and geometry tests: 0 skipped.
- [ ] 390 px screenshot of the box in the PR.
- [ ] Nothing in `stayfee/` or `App/` changed (`git diff --stat`).

## 8. Stop and ask

Any anchor not found; no way to get the Fernet decrypter from `stayClaimDeps`; `LoadCompletionFee` not returning the data the box needs (`git grep` shows a missing field); a `fee_*` key missing in one language (do NOT invent text: report it, 2056 owns catalogue copying); 25 tool calls (commit, report `Done: steps 1 to k`).

## 9. Report

`docs/tasks/2063-report.md`, 600 tokens at most. Owner steps left: none for this brief (merge via `scripts/merge-pr-on-green.sh` once 2064 shows `g-stay-fee` is not `visible`).
