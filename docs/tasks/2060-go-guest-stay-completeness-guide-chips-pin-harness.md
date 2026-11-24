# 2060: Go stay completeness (encrypted columns), guide chips, PIN harness wait, door-card diagnosis

Status: todo
Executor: Haiku 5.5. One PR, draft. Commit trailers:
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014N5J8NCpdqN2TbR61gYRQf

## 1. Objective
Fix the real Go differences found after 2059 (stay completeness, guide chips), make the PIN parity row stable, find why the door card is missing, rerun the affected cases and the gate once.

## 2. Context (diagnosis, file:line)

1. **CRITICAL, g-stay-issued-done: Python "uloženo", Go "nevyplněno".** `go/internal/web/guest/stay_view.go:68-72` (`stayPeople`) selects only the PLAIN columns `birth_date, doc_number, visa_number, res_street, res_city, signature_png`. Production and the seed write these through `db.insert`, which redirects them to `*_enc` and blanks the plain column (`App/app/db.py` ENCRYPTED_GUEST_COLUMNS: doc_number, visa_number, signature_png, birth_date, res_street, res_city). Python reads them decrypted (`reporting.guest_issues`). So Go sees an empty birth date, document, residence and signature, and `GuestIsComplete` is false. Go also never loads `note`, `stay_from`, `stay_to`, which `reporting.guest_dict/_stay_dates` use (guest's own stay dates win over the reservation's; note is needed for INPASS). The filing path `ubyport.LoadGuests` (`go/internal/ubyport/collect.go:419`, `decryptOrPlain`) and the guest form (`form_pages.go:746 loadFormGuest`) already decrypt, so today the stay page can say "not filled in" for a person the filing would send. The same plain-only SELECT exists in `go/internal/web/guest/pick_data.go:~160` and `go/internal/web/guest/form_pages.go:~575` (progress counts). Fix all three with the decrypt helper `decryptGuestField(getenv, now, token, plain)` in `form_save.go:260`.
2. **Door-code card absent on both sides.** Python `door_codes.view` (`App/app/door_codes.py:216-262`) returns None unless apartment.lock_provider == "ttlock", source != "demo", and (DOOR_CODES_LIVE or source == "manual"); then a row state "issued" with a decryptable pin_enc gives the card (`stay.html:66`, `{% if door_code %}`). Go `doorcodes/view.go:115-119` is the same condition; Go also needs `d.doorCodes != nil` (`stay_claim.go:216`). The seed stay is `source="manual"` and sets ttlock and hours (`seed_parity_guest.py:126`), so on paper both conditions hold, yet neither side shows it. Cause not provable by reading (static); step 2 adds stderr diagnostics, step 9 reads them. Suspects: the `issued()` block raising after the guest insert (block() only prints a "skipped" line to stderr, `seed_parity_guest.py:24-28`), or the apartment UPDATE not landing on the apartment behind the token link.
3. **Python bug (report only, do not touch App/app):** `door_codes._stay_checkin_label` (`door_codes.py:210-213`) raises TypeError when `apartment.checkin_hour/checkout_hour` is NULL (`datetime(..., hour=None)`). Called from `view()` (`:259-260`, used by `routes/guest.py:1576` stay page and `routes/admin.py:4148` host stay page, so both return 500 for an issued code) and `ttlock.stay_window` callers (`:521`, `:1240`, `:1569`: issuing/notification jobs). Columns are nullable with no default (`00001_baseline.sql:290-291`). New codes need both hours set (`door_codes.py:193`), so only an apartment whose host cleared the hours after a code was issued can crash. Go (`doorcodes/view.go:170`) returns an error for NULL hours; the stay handler logs `door_code_view_failed` and renders the page without the card (`stay_claim.go:216-222`): no crash. No Go change needed.
4. **g-guide-apt / g-guide-stay:** the only content difference seen (cs 390, en 1280) is the Leon quick-reply chips: Go shows raw keys `leon_sit_cant_get_in, leon_sit_cold, leon_sit_checkout, leon_sit_emergency` (also broken, parking, trash) because `go/internal/web/guest/i18n.json` lacks those 7 keys (it has only `leon_sit_other`, `leon_sit_emergency_help`); `guide.tmpl:79-85` calls `.T`. Values exist in `go/internal/web/ai/leon_guest_i18n.json`. Chips wrap differently, so the cards differ in height and everything below shifts (the 6k-58k px diff). Layout, text and host card are otherwise identical.
5. **g-pin-hub:** same HTML (`pin.html:13-14` vs `pin.tmpl:11-12`, identical attributes), same JS (`guest-enhancements.js:44-75`). The difference is only the first cell: `.g-pin-cell.is-caret` (border + 4px ring) is removed by `paint()` on blur, but the cell has `transition: border-color/box-shadow 0.14s` (`guest.css:756-767`) and the screenshot is taken right after `blur()` (`page_parity_visual.py:163`), so each side is caught at a different point of the fade (Python pinkish border, Go dark border + ring). Harness timing issue, not a Go bug. Fix: wait after blur.

## 3. Files

- `go/internal/web/guest/stay_view.go`, `pick_data.go`, `form_pages.go`
- `go/internal/web/guest/i18n.json`, `go/internal/web/guest/i18n_keys.txt`
- `go/internal/web/guest/guest_fixes_2056_test.go` (key list) and one new test file `go/internal/web/guest/stay_complete_test.go`
- `scripts/e2e/seed_parity_guest.py`, `scripts/e2e/page_parity_visual.py`
- Not touched: anything under `App/app`.

## 4. Steps (one commit each, message `2060 step k`; every command ends `2>&1 | tail -30`)

1. **Shared helper.** In `stay_view.go` add (anchor: `func joinNonEmpty`, insert before it):
```go
// stayGuestSelect lists the columns stayPeople reads: plain and encrypted pairs, as reporting.guest_dict does.
const stayGuestSelect = `id, COALESCE(first_name,''), COALESCE(surname,''), COALESCE(nationality,''),
	COALESCE(birth_date,''), COALESCE(birth_date_enc,''), COALESCE(doc_number,''), COALESCE(doc_number_enc,''),
	COALESCE(visa_number,''), COALESCE(visa_number_enc,''), COALESCE(res_street,''), COALESCE(res_street_enc,''),
	COALESCE(res_city,''), COALESCE(res_city_enc,''), COALESCE(res_country,''), COALESCE(purpose,''),
	COALESCE(note,''), COALESCE(stay_from,''), COALESCE(stay_to,''), COALESCE(submit_state,''),
	COALESCE(restricted_at::text,''), COALESCE(signature_png,''), COALESCE(signature_png_enc,'')`

// stayGuestCols is one row of stayGuestSelect, still encrypted where the column is.
type stayGuestCols struct {
	ID                                                  int64
	First, Surname, Nat                                 string
	BirthP, BirthE, DocP, DocE, VisaP, VisaE            string
	StreetP, StreetE, CityP, CityE, Country, Purpose    string
	Note, StayFrom, StayTo, Submit, Restricted          string
	SigP, SigE                                          string
}

func (c *stayGuestCols) scanArgs() []any {
	return []any{&c.ID, &c.First, &c.Surname, &c.Nat, &c.BirthP, &c.BirthE, &c.DocP, &c.DocE, &c.VisaP, &c.VisaE,
		&c.StreetP, &c.StreetE, &c.CityP, &c.CityE, &c.Country, &c.Purpose, &c.Note, &c.StayFrom, &c.StayTo,
		&c.Submit, &c.Restricted, &c.SigP, &c.SigE}
}

// validationRow decrypts the encrypted columns (plain wins when there is no token) into the row GuestIsComplete reads.
func (c stayGuestCols) validationRow(getenv func(string) string, now func() time.Time) (validation.GuestRow, error) {
	row := validation.GuestRow{Surname: c.Surname, FirstName: c.First, Nationality: c.Nat, ResCountry: c.Country,
		Purpose: c.Purpose, Note: c.Note, StayFrom: c.StayFrom, StayTo: c.StayTo}
	for _, p := range []struct {
		token, plain string
		dst          *string
	}{{c.BirthE, c.BirthP, &row.BirthDate}, {c.DocE, c.DocP, &row.DocNumber}, {c.VisaE, c.VisaP, &row.VisaNumber},
		{c.StreetE, c.StreetP, &row.ResStreet}, {c.CityE, c.CityP, &row.ResCity}, {c.SigE, c.SigP, &row.SignaturePNG}} {
		v, err := decryptGuestField(getenv, now, p.token, p.plain)
		if err != nil {
			return row, err
		}
		*p.dst = v
	}
	return row, nil
}
```
Add `"time"` to the imports if missing. Run `cd go && go build ./internal/web/guest/ 2>&1 | tail -30`: builds (helper unused is fine, it is a package-level func).

2. **Use it in stayPeople.** Anchor `rows, err := d.pool.Query(ctx, \`SELECT id, COALESCE(first_name,'')` in `stay_view.go`. Replace the query with ``"SELECT "+stayGuestSelect+" FROM guest WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY is_lead DESC, id"``. In the loop: `var c stayGuestCols; if err := rows.Scan(c.scanArgs()...); err != nil {...}`, then `gr, err := c.validationRow(d.getenv, d.now)` (return the error), `complete := validation.GuestIsComplete(gr, stay.dateFrom, stay.dateTo, today)`, and rewrite the rest of the loop body to read `c.ID, c.First, c.Surname, c.Nat, c.Submit, c.Restricted` and `gr.DocNumber, gr.ResStreet, gr.ResCity` (summary: `Residence: joinNonEmpty(", ", gr.ResStreet, gr.ResCity, gr.ResCountry)`, `BirthDate: validation.DisplayBirthDate(gr.BirthDate, today)`, doc "INPASS" still blanked, purpose `c.Purpose`). Behaviour otherwise unchanged. Run `cd go && go build ./internal/web/guest/ 2>&1 | tail -30`.
3. **pick_data.go (~line 160) and form_pages.go (~line 575).** In each, replace the plain-only SELECT + Scan with the same `stayGuestSelect`/`stayGuestCols` pair (keep `nationality, submit_state, manual_filed_at` semantics: add `COALESCE(manual_filed_at,'')` by a second query column only if the file needs it; otherwise read `c.Submit` and keep the existing `manual` column as an extra scan target after `c.scanArgs()`... if that is awkward, STOP and report). Use `gr, err := c.validationRow(<getenv>, <now>)` with the getenv/now the function already has or its receiver exposes; on error skip counting that person and `log.Printf`. Then `go build` as above. If either function has no getenv in reach, STOP and report which.
4. **Chips i18n.** Run this once from the repo root, then show `git diff --stat`:
```bash
python3 - <<'PY'
import json
g=json.load(open("go/internal/web/guest/i18n.json")); a=json.load(open("go/internal/web/ai/leon_guest_i18n.json"))
keys=["leon_sit_broken","leon_sit_cant_get_in","leon_sit_checkout","leon_sit_cold","leon_sit_emergency","leon_sit_parking","leon_sit_trash"]
for lang in g:
    for k in keys:
        assert k in a[lang], (lang,k)
        g[lang][k]=a[lang][k]
    g[lang]=dict(sorted(g[lang].items()))
json.dump(g,open("go/internal/web/guest/i18n.json","w"),ensure_ascii=False,indent=1); open("go/internal/web/guest/i18n.json","a").write("\n")
PY
```
Then `git diff --stat go/internal/web/guest/i18n.json | tail -5`: only added lines expected (about 7 per language). If the diff touches more than ~60 lines (formatting drift), `git checkout` the file and instead insert the 7 keys per language by hand-editing. Append the 7 keys to `go/internal/web/guest/i18n_keys.txt` (one per line, sorted into place).
5. **Tests.** (a) In `guest_fixes_2056_test.go` append the 7 keys to `fixes2056Keys` (anchor: `leon_sit_emergency_help leon_sit_other`). (b) New `stay_complete_test.go`, package `guest`: table test of `stayGuestCols.validationRow` with a nil-token complete record (plain values: birth `01011990`, doc `E2E000000`, street/city, country `CZE`, purpose `99`, nationality `DEU`, and a valid PNG data URL built in the test with `image/png` + base64), expecting `validation.GuestIsComplete(row, "2030-01-10", "2030-01-13", time.Now())` true; a second case with an empty birth date expecting false; a third with an invalid token (`SigE: "not-a-token"`, getenv returning a valid-looking key env as other tests in this package do; if no helper exists, expect an error from `validationRow` when keys are missing) expecting a non-nil error. Run `cd go && go test ./internal/web/guest/ 2>&1 | tail -30`: PASS.
6. **Harness wait.** `scripts/e2e/page_parity_visual.py:163`: after the blur `page.evaluate(...)` line add `page.wait_for_timeout(400)` (transition is 0.14 s). `python3 -c "import ast,sys;ast.parse(open('scripts/e2e/page_parity_visual.py').read())" 2>&1 | tail -30`: no output.
7. **Seed diagnostics (door card).** In `seed_parity_guest.py`, replace the debug `print(json.dumps({"issued_done_issues"...}))` block (lines 144-147) with one that also prints, to stderr, counts only: `lock_provider` of apt, `checkin_hour`, the `door_code` row state for `res_issued_done` (or "none"), and `door_codes.view(res, apartment_row)` result `state` (import `door_codes` from `app`, wrap in try/except printing the exception class). No guest data. Syntax check as in step 6.
8. **Rerun exactly the affected cases** (glob filter from 2059): `cd /home/user/jsfpecharoperations && PARITY_ONLY='g-stay-issued-done*' <the command 2059 step 5 used> 2>&1 | tail -30`, then the same with `g-guide-*` and `g-pin-hub*`. Expected: g-stay-issued-done shows "uloženo" on both sides; g-guide-apt/stay identical or only within noise; g-pin-hub identical.
9. **Door card.** Read the seed stderr line from step 8. (a) If `view` state is "issued" and the card still does not render on Go: check `d.doorCodes` wiring (`grep -n "doorCodes" go/internal/web/guest/*.go go/cmd/ubyhost-web/*.go | head -20`) and set the env the harness needs (`UBYHOST_DOOR_CODES`, see `go/cmd/ubyhost-web/cleaning_queue_kick.go:38`) in the Go server env in `scripts/e2e` only. (b) If `view` is None or the door row is "none": fix the seed (the cause is visible in the printed fields, e.g. lock_provider not ttlock). (c) If neither explains it: STOP, write the printed fields in the report.
10. **Full gate once.** After steps 8-9 are clean: `scripts/e2e/parity_gate.sh 2>&1 | tail -30`. Expected: guest pages 0 visible differences (or list each remaining row in the report; do not silence).
11. `python3 scripts/context_lint.py 2>&1 | tail -3`: OK. Write `docs/tasks/2060-report.md` per executor.md. Open a draft PR.

## 5. Do not touch
Anything under `App/app`; other Go packages; the Python door-code bug (section 10).

## 6. Commands
`cd go && go test ./internal/web/guest/ 2>&1 | tail -30`. Guest page screenshots at 390 px for g-stay-issued-done and g-guide-apt (cs), from the harness PNGs.

## 7. Acceptance
- [ ] g-stay-issued-done: both sides "Osoba 1 · uloženo".
- [ ] Guide chips show translated text in Go (cs, en).
- [ ] g-pin-hub identical in all rows.
- [ ] Door card shown on both sides, or the report states the printed diagnostics.
- [ ] parity_gate.sh output pasted (last 5 lines).
- [ ] No change under `App/app`.

## 8. Stop and ask
Any anchor missing, step 3 not feasible without a signature change, or a Go test failing twice: STOP, report `blocked`.

## 9. Report
`docs/tasks/2060-report.md` per executor.md.

## 10. For the owner (report only, no code here)
Python bug: `App/app/door_codes.py:210-213` `_stay_checkin_label` crashes (TypeError, HTTP 500 on the guest stay page and the host stay page) when an apartment with an issued door code has NULL `checkin_hour` or `checkout_hour`. Production runs door codes, and hours are nullable; new codes require both hours (`door_codes.py:193`), so exposure is limited to a host who clears the hours after a code was issued. Ask for a separate Python brief: fall back to the code's `valid_from/valid_to` or hide the times when an hour is NULL.
