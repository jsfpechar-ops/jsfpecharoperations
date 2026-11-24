# 2073: Preserve the under-15 signer relationship

Status: review
Depends on: 2072 | Base commit: ab87118cde548fb9e5ddd441bc7cd3619f1e071c | Branch: task/2073-go-guest-child-signer
Executor: Gemini 4 Neon (medium) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Restore Python's child and adult signer validation, 422 re-render parity, and recorded `signed_for_*` relationship on guest save. Link eligible unsigned children when a signed adult saves, preserve existing links on child edits without a new signer, and clear links when a child ages out on birth-date correction.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests (`UBYHOST_TEST_DATABASE_URL`). Every anchor below is verified against `ab87118cde548fb9e5ddd441bc7cd3619f1e071c`; stop if any anchor diverges.

### Python reference anchors

- `App/app/reporting.py:273` — `UNDER_SIGN_AGE = 15`, `ADULT_SIGNER_AGE = 18`, `SIGN_FOR_WORDING_VERSION = "u15-2026-11-10"`, `SIGN_FOR_ROLES = {"parent": ..., "responsible_adult": ...}`, `_stay_dates` (:176), `guest_under_15` (:282).
- `App/app/validation.py:180` — `_birth_bounds(raw, latest=True)` (`00` month → `12`, `00` day → last day of month), `certainly_at_least_age` (:208), `is_valid_signature` (:901, rejects `""`, `"imported"`, and invalid image blobs).
- `App/app/routes/guest.py:411` — `def _sign_for_fields(request, reservation, signer_raw, role_raw, now) -> Dict[str, Any]:`
- `App/app/routes/guest.py:443` — `def _link_signed_children(request, reservation, adult_id, ids_raw, role_raw, now) -> None:`
- `App/app/routes/guest.py:1907` — `def _under15_lists(request, reservation, guest_id):`
- `App/app/routes/guest.py:2473` — multi-adult `signed_by` missing refusal (`sign_for_who_missing`).
- `App/app/routes/guest.py:2540` — 422 whitelisted echo (`signed_by`, `child_sign_role`, `sign_for_role`, `signature`, `legal_ack`).
- `App/app/routes/guest.py:2587` — `if child:` merge `_sign_for_fields(...)` (empty adds nothing so edits keep prior link); `else:` set all four `signed_for_*` columns to `None`.
- `App/app/routes/guest.py:2717` — `if not child and validation.certainly_at_least_age(...)` → `_link_signed_children(request, reservation, saved_id, form.getlist("sign_for_ids"), form.get("sign_for_role"), now)` before audit and stay completion.

### Go anchors (HEAD `ab87118cd`)

- `go/internal/validation/validation.go:231` — `func certainlyUnderAge(raw string, when time.Time, years int) bool {`
- `go/internal/validation/guest_form.go:331` — `func CertainlyUnderAge(birth string, when *time.Time, years int) bool {`
- `go/internal/validation/guest_form.go:366` — `func GuestFormSignatureIssue(value string, under15 bool) *Issue {`
- `go/internal/web/guest/form_pages_fill.go:41` — `func formPagesFillU15(ctx context.Context, d formPageDeps, view *formView, res formResRow, guest *formGuestRow, r *http.Request) {`
- `go/internal/web/guest/form_pages_fill.go:65` — `func formU15Lists(ctx context.Context, pool *pgxpool.Pool, resID, guestID int64, owned map[int64]bool, getenv func(string) string, now func() time.Time, stayFrom string) (adults, pending []formChildEntry) {`
- `go/internal/web/guest/form_pages.go:362` — `handleRemovePost` already clears all four `signed_for_*` columns when an adult is removed; no edit needed in `form_pages.go`.
- `go/internal/web/guest/form_save.go:165` — `stayFrom, stayTo := lockedStayDates(res, existing)`
- `go/internal/web/guest/form_save.go:203` — `issues = localizeIssues(nameLatinIssues(issues, lang), lang)`
- `go/internal/web/guest/form_save.go:209` — `payload := buildSavePayload(values, stayFrom, stayTo, sig, child, lang, cfg.noticeVersion, nowS, existing)`
- `go/internal/web/guest/form_save.go:255` — `if err := auditGuestFormSaved(ctx, d.pool, savedID, resID, cfg.ownerUserID, lang, d.now); err != nil {`
- `go/internal/web/guest/form_save.go:397` — `func buildSavePayload(v validation.GuestRow, stayFrom, stayTo, sig string, child bool, lang, noticeVer, now string, existing *guestSaveRow) map[string]any {`
- `go/internal/web/guest/form_save.go:661` — `var guestSaveInsertCols = []string{`
- `go/internal/web/guest/form_save.go:706` — `func renderGuestForm422(w http.ResponseWriter, r *http.Request, d saveDeps, apt *Apartment, token, lang string, resID int64, existing *guestSaveRow, raw map[string]string, values validation.GuestRow, stayFrom, stayTo string, issues []validation.Issue) {`
- `go/internal/web/guest/templates/form_content.tmpl:313` — `{{range $.ChildSigners}}`

### Key Python parity rules

1. **Exact form field names** (matching `App/app/templates/guest/form.html` and `go/internal/web/guest/templates/form_content.tmpl`):
   - Child form: `signed_by` (hidden input when 1 eligible adult, radio group when >1) and `child_sign_role` (`"parent"` or `"responsible_adult"`).
   - Adult form: `sign_for_ids` (repeated hidden inputs — **must read `r.PostForm["sign_for_ids"]`**, never `form["sign_for_ids"]` which drops all but the first) and `sign_for_role` (`"parent"` or `"responsible_adult"`).
2. **`_under15_lists` eligibility**: same `reservation_id`, `archived_at IS NULL`, `id` in device's signed `ubyhost_guest_ids` cookie, `id != guestID`, ordered deterministically (`ORDER BY id`). Decrypt `birth_date_enc` / `signature_png_enc` via `decryptGuestField`. Per-row arrival date is `row.stay_from` if valid ISO date, else `res.date_from`.
   - `adults` (`child_signers`): `validation.IsValidSignature(sig) && validation.CertainlyAtLeastAge(birth, arrival, 18)` (rejects `"imported"`, invalid blobs, and 15–17-year-olds).
   - `pending` (`pending_children`): `else if signed_for_guest_id IS NULL && validation.CertainlyUnderAge(birth, arrival, 15)`.
3. **422 validation rule (`signed_by`)**: ONLY refuses with 422 when `child == true` AND `strings.TrimSpace(form["child_sign_role"])` is `"parent"` or `"responsible_adult"` AND `strings.TrimSpace(form["signed_by"]) == ""` AND `len(signers) > 1`. With 0 or 1 eligible signer, or with no role, or with an invalid/ineligible `signed_by` (wrong stay, unowned, archived, 17-year-old, `"imported"`, non-numeric, invalid role), the child still saves with no link (`signed_for_* = NULL`).
4. **Localization without editing `i18n.json`**: `sign_for_who_missing` is absent from `go/internal/web/guest/i18n.json`. Keep a 6-language map in `child_signer.go` (same pattern as `passport_required.go` and `form_issues.go`), copied verbatim from `App/app/i18n.py` + `App/app/guest_uk_i18n.py`, so `i18n.json` stays untouched.
5. **422 re-render & `form_pages_fill.go` fixes**:
   - In `formPagesFillU15`, `view.AdultSigner` currently reads `len(signers) > 0` (bug: hides `#sign-for-children` when a child was saved first before any adult!). Fix to match Python (`guest.py:2066`, `form.html:304`): `true` when `guest == nil || guest.birthDate == ""`, else `validation.CertainlyAtLeastAge(guest.birthDate, arrival, 18)`.
   - In `renderGuestForm422`, recompute `view.Under15` and `view.AdultSigner` from posted `values.BirthDate` and `stayFrom`, echo whitelisted `SelectedSigner` (ASCII digits only), `SelectedChildRole` / `SelectedSignForRole` (`"parent"` or `"responsible_adult"` only), `SignatureValue` (only if `validation.IsValidSignature(sig)`), and `view.Values["legal_ack"]`.
   - In `form_content.tmpl:313-318`, add `id="signed_by"` to the first `signed_by` radio so `<a href="#signed_by">` in the 422 error summary lands on it.
6. **Child edit vs age-out**:
   - `child == true` and `resolveChildSignerFields` returns 4 keys → write all 4 (`signed_for_guest_id`, `signed_for_role`, `signed_for_at`, `signed_for_wording = "u15-2026-11-10"`).
   - `child == true` and `resolveChildSignerFields` returns `nil` → omit the 4 keys from `payload` (INSERT writes `NULL` via `guestSaveInsertCols`; UPDATE leaves existing link untouched).
   - `child == false` → set all 4 keys to `nil` in `payload` (clears prior link on UPDATE; `GuestFormSignatureIssue(sig, false)` requires adult's own drawn signature first, so a 422 leaves the prior link intact).
7. **Adult linking selected children**: runs after guest row + passport photo persist, before `auditGuestFormSaved`, `guestFormSubmitStayIfComplete`, and `runCompletion`, only when `!child && validation.CertainlyAtLeastAge(values.BirthDate, parseDatePtr(stayFrom), 18)`. Touches ONLY the 4 `signed_for_*` columns (`WHERE id = $5 AND reservation_id = $6 AND archived_at IS NULL AND signed_for_guest_id IS NULL`), so first adult wins and a filed (`sent`) child keeps its filing columns (`submit_state`, `submit_attempts`, `last_errors`) untouched.
8. **Preserve prior briefs**: keep all 2065, 2069, 2070, 2071, 2072, and 2084 behavior in `form_save.go` intact (`guestSaveValidateIssues`, encrypted `*_enc` columns, passport photo validation/storage, `localizeIssues`, headcount/notice/completion hooks).

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/validation/validation.go` | edit | Add `certainlyAtLeastAge` matching Python `_birth_bounds(..., latest=True)`. |
| `go/internal/validation/guest_form.go` | edit | Export `CertainlyAtLeastAge` and `IsValidSignature`. |
| `go/internal/web/guest/child_signer.go` | create | Signer constants, 6-language `sign_for_who_missing` map, `rowArrivalDate`, `resolveChildSignerFields`, `linkSignedChildren`, echo parsers. |
| `go/internal/web/guest/form_pages_fill.go` | edit | Match Python `_under15_lists` (18+, valid drawn sig, per-row `stay_from`, `ORDER BY id`) and `AdultSigner` visibility. |
| `go/internal/web/guest/form_save.go` | edit | Add `signed_by` multi-adult check, pass `signFor` into `buildSavePayload`, add 4 `signed_for_*` cols to `guestSaveInsertCols`, link selected children before completion hooks, fix 422 re-render echo/visibility. |
| `go/internal/web/guest/templates/form_content.tmpl` | edit | Put `id="signed_by"` on the first `signed_by` radio for the 422 error-summary anchor. |
| `go/internal/web/guest/form_save_test.go` | edit | Add `TestGuestSaveChildSigner` and unit tests for age/sig/i18n parity. |

The executor report and brief status follow section 9.

## 4. Steps

### Step 1: Add `CertainlyAtLeastAge` and `IsValidSignature` in `go/internal/validation`

In `go/internal/validation/validation.go` directly after `certainlyUnderAge` (line 257), add:

```go
func certainlyAtLeastAge(raw string, when time.Time, years int) bool {
	if len(raw) != 8 || !isASCIIDigits(raw) {
		return false
	}
	day, _ := strconv.Atoi(raw[0:2])
	month, _ := strconv.Atoi(raw[2:4])
	year, _ := strconv.Atoi(raw[4:8])
	if year == 0 {
		return false
	}
	if month == 0 {
		month = 12
	}
	if month < 1 || month > 12 {
		return false
	}
	if day == 0 {
		day = time.Date(year, time.Month(month)+1, 0, 0, 0, 0, 0, time.UTC).Day()
	}
	birth, ok := roundTrip(year, month, day)
	if !ok {
		return false
	}
	age := when.Year() - birth.Year()
	if when.Month() < birth.Month() || (when.Month() == birth.Month() && when.Day() < birth.Day()) {
		age--
	}
	return age >= years
}
```

In `go/internal/validation/guest_form.go` after `CertainlyUnderAge` (line 336) and `GuestFormSignatureIssue` (line 378), add:

```go
// CertainlyAtLeastAge is validation.certainly_at_least_age (00 month -> 12,
// 00 day -> month's last day).
func CertainlyAtLeastAge(birth string, when *time.Time, years int) bool {
	if when == nil {
		return false
	}
	return certainlyAtLeastAge(birth, *when, years)
}
```

and:

```go
// IsValidSignature is validation.is_valid_signature: true only for a valid
// drawn signature image data URL (rejects empty and the host "imported" marker).
func IsValidSignature(value string) bool {
	return GuestFormSignatureIssue(value, false) == nil
}
```

### Step 2: Create `go/internal/web/guest/child_signer.go`

Create `go/internal/web/guest/child_signer.go`:

```go
package guest

import (
	"context"
	"errors"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	// adultSignerAge is reporting.ADULT_SIGNER_AGE: minimum age on arrival to sign for a child.
	adultSignerAge = 18
	// signForWordingVersion is reporting.SIGN_FOR_WORDING_VERSION.
	signForWordingVersion = "u15-2026-11-10"
)

// signForWhoMissingMessages is i18n.STRINGS[lang]["sign_for_who_missing"]
// (and guest_uk_i18n.STRINGS for uk). Kept here so i18n.json stays unchanged.
var signForWhoMissingMessages = map[string]string{
	"en": "Choose the adult who is signing.",
	"cs": "Vyberte dospělého, který podepisuje.",
	"de": "Wählen Sie die unterschreibende erwachsene Person.",
	"es": "Elija al adulto que firma.",
	"fr": "Choisissez l'adulte signataire.",
	"uk": "Виберіть дорослого, що підписує.",
}

func signForWhoMissingText(lang string) string {
	if msg, ok := signForWhoMissingMessages[lang]; ok && msg != "" {
		return msg
	}
	return signForWhoMissingMessages["en"]
}

func isSignForRole(role string) bool {
	return role == "parent" || role == "responsible_adult"
}

// rowArrivalDate is reporting._stay_dates(guest, reservation)[0].
func rowArrivalDate(rowStayFrom, resDateFrom string) *time.Time {
	if t := parseDatePtr(rowStayFrom); t != nil {
		return t
	}
	return parseDatePtr(resDateFrom)
}

func parseInt64Trimmed(raw string) (int64, bool) {
	s := strings.TrimSpace(raw)
	if s == "" {
		return 0, false
	}
	id, err := strconv.ParseInt(s, 10, 64)
	if err != nil || id <= 0 {
		return 0, false
	}
	return id, true
}

// parsePositiveASCIIDigits matches guest.py:2551 (signed_by_echo.isascii() and isdigit()).
func parsePositiveASCIIDigits(raw string) (int64, bool) {
	if raw == "" {
		return 0, false
	}
	for i := 0; i < len(raw); i++ {
		if raw[i] < '0' || raw[i] > '9' {
			return 0, false
		}
	}
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || id <= 0 {
		return 0, false
	}
	return id, true
}

// resolveChildSignerFields is guest._sign_for_fields (guest.py:411): returns
// the four signed_for_* columns for a child's save, or nil when ineligible.
func resolveChildSignerFields(ctx context.Context, d saveDeps, r *http.Request, resID int64, resDateFrom string, existingID int64, signerRaw, roleRaw, nowS string) (map[string]any, error) {
	signerID, ok := parseInt64Trimmed(signerRaw)
	role := strings.TrimSpace(roleRaw)
	if !ok || !isSignForRole(role) {
		return nil, nil
	}
	if existingID > 0 && signerID == existingID {
		return nil, nil
	}
	if !formPagesOwnedIDs(r, d.getenv)[signerID] {
		return nil, nil
	}
	var birthEnc, birthPlain, sigEnc, sigPlain, rowStayFrom string
	err := d.pool.QueryRow(ctx, `SELECT COALESCE(birth_date_enc,''), COALESCE(birth_date,''),
		COALESCE(signature_png_enc,''), COALESCE(signature_png,''), COALESCE(stay_from,'')
		FROM guest WHERE id = $1 AND reservation_id = $2 AND archived_at IS NULL`,
		signerID, resID).Scan(&birthEnc, &birthPlain, &sigEnc, &sigPlain, &rowStayFrom)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	sig, err := decryptGuestField(d.getenv, d.now, sigEnc, sigPlain)
	if err != nil {
		return nil, err
	}
	if !validation.IsValidSignature(sig) {
		return nil, nil
	}
	birth, err := decryptGuestField(d.getenv, d.now, birthEnc, birthPlain)
	if err != nil {
		return nil, err
	}
	if !validation.CertainlyAtLeastAge(birth, rowArrivalDate(rowStayFrom, resDateFrom), adultSignerAge) {
		return nil, nil
	}
	return map[string]any{
		"signed_for_guest_id": signerID,
		"signed_for_role":     role,
		"signed_for_at":       nowS,
		"signed_for_wording":  signForWordingVersion,
	}, nil
}

// linkSignedChildren is guest._link_signed_children (guest.py:443): links only
// eligible owned, active, under-15, not-yet-linked children on this reservation.
// Writes only the four signed_for_* columns so filed children are not refiled.
func linkSignedChildren(ctx context.Context, d saveDeps, r *http.Request, resID int64, resDateFrom string, adultID int64, idsRaw []string, roleRaw, nowS string) error {
	role := strings.TrimSpace(roleRaw)
	if !isSignForRole(role) || len(idsRaw) == 0 {
		return nil
	}
	owned := formPagesOwnedIDs(r, d.getenv)
	if len(owned) == 0 {
		return nil
	}
	seen := make(map[int64]bool, len(idsRaw))
	for _, raw := range idsRaw {
		childID, ok := parseInt64Trimmed(raw)
		if !ok || seen[childID] || childID == adultID || !owned[childID] {
			continue
		}
		seen[childID] = true
		var birthEnc, birthPlain, rowStayFrom string
		err := d.pool.QueryRow(ctx, `SELECT COALESCE(birth_date_enc,''), COALESCE(birth_date,''),
			COALESCE(stay_from,'')
			FROM guest WHERE id = $1 AND reservation_id = $2 AND archived_at IS NULL`,
			childID, resID).Scan(&birthEnc, &birthPlain, &rowStayFrom)
		if errors.Is(err, pgx.ErrNoRows) {
			continue
		}
		if err != nil {
			return err
		}
		birth, err := decryptGuestField(d.getenv, d.now, birthEnc, birthPlain)
		if err != nil {
			return err
		}
		if !validation.CertainlyUnderAge(birth, rowArrivalDate(rowStayFrom, resDateFrom), guestcontract.UnderSignAge) {
			continue
		}
		if _, err := d.pool.Exec(ctx, `UPDATE guest
			SET signed_for_guest_id = $1, signed_for_role = $2,
			    signed_for_at = $3, signed_for_wording = $4
			WHERE id = $5 AND reservation_id = $6 AND archived_at IS NULL AND signed_for_guest_id IS NULL`,
			adultID, role, nowS, signForWordingVersion, childID, resID); err != nil {
			return err
		}
	}
	return nil
}
```

### Step 3: Fix `go/internal/web/guest/form_pages_fill.go` and `templates/form_content.tmpl`

In `go/internal/web/guest/form_pages_fill.go`, update `formPagesFillU15` (:41–63) and `formU15Lists` (:65–109):

```go
func formPagesFillU15(ctx context.Context, d formPageDeps, view *formView, res formResRow, guest *formGuestRow, r *http.Request) {
	var guestID int64
	if guest != nil {
		guestID = guest.id
	}
	signers, pending := formU15Lists(ctx, d.pool, res.id, guestID, formPagesOwnedIDs(r, d.getenv), d.getenv, d.now, res.dateFrom)
	view.PendingChildren = pending
	if len(pending) > 0 {
		names := make([]string, len(pending))
		for i, c := range pending {
			names[i] = c.Name
		}
		view.PendingChildrenNames = strings.Join(names, ", ")
	}
	view.ChildSigners = signers
	if guest != nil && guest.birthDate != "" {
		arrival := rowArrivalDate(guest.stayFrom, res.dateFrom)
		view.Under15 = validation.CertainlyUnderAge(guest.birthDate, arrival, guestcontract.UnderSignAge)
		view.AdultSigner = validation.CertainlyAtLeastAge(guest.birthDate, arrival, adultSignerAge)
	} else {
		view.AdultSigner = true
	}
}

func formU15Lists(ctx context.Context, pool *pgxpool.Pool, resID, guestID int64, owned map[int64]bool, getenv func(string) string, now func() time.Time, stayFrom string) (adults, pending []formChildEntry) {
	if len(owned) == 0 || pool == nil {
		return nil, nil
	}
	rows, err := pool.Query(ctx, `SELECT id, COALESCE(first_name,''), COALESCE(surname,''), COALESCE(birth_date_enc,''), COALESCE(birth_date,''),
		COALESCE(signature_png,''), COALESCE(signature_png_enc,''), COALESCE(signed_for_guest_id,0), COALESCE(stay_from,'')
		FROM guest WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY id`, resID)
	if err != nil {
		return nil, nil
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var first, surname, birthEnc, birthPlain, sigPlain, sigEnc, rowStayFrom string
		var signedFor int64
		if err := rows.Scan(&id, &first, &surname, &birthEnc, &birthPlain, &sigPlain, &sigEnc, &signedFor, &rowStayFrom); err != nil {
			return nil, nil
		}
		if !owned[id] || id == guestID {
			continue
		}
		name := strings.TrimSpace(first + " " + surname)
		birth := birthPlain
		if birthEnc != "" {
			if plain, err := decryptGuestField(getenv, now, birthEnc, birthPlain); err == nil {
				birth = plain
			}
		}
		sig := sigPlain
		if sigEnc != "" {
			if plain, err := decryptGuestField(getenv, now, sigEnc, sigPlain); err == nil {
				sig = plain
			}
		}
		arrival := rowArrivalDate(rowStayFrom, stayFrom)
		entry := formChildEntry{ID: id, Name: name}
		if validation.IsValidSignature(sig) && validation.CertainlyAtLeastAge(birth, arrival, adultSignerAge) {
			adults = append(adults, entry)
			continue
		}
		if signedFor == 0 && validation.CertainlyUnderAge(birth, arrival, guestcontract.UnderSignAge) {
			pending = append(pending, entry)
		}
	}
	return adults, pending
}
```

In `go/internal/web/guest/templates/form_content.tmpl` (:313–318), add `id="signed_by"` to the first radio:

```html
          {{range $i, $s := $.ChildSigners}}
          <label class="checkline">
            <input type="radio" name="signed_by" value="{{$s.ID}}"{{if eq $i 0}} id="signed_by"{{end}}{{if eq $.SelectedSigner $s.ID}} checked{{end}}>
            <span>{{$s.Name}}</span>
          </label>
          {{end}}
```

### Step 4: Wire child/adult signer validation, persistence, reverse linking, and 422 echo in `go/internal/web/guest/form_save.go`

1. In `handleGuestFormSave` right after `issues := guestSaveValidateIssues(...)` (line 171) and before the passport photo block (line 174):

```go
	var existingID int64
	if existing != nil {
		existingID = existing.id
	}
	// guest.py:2473 — if a child ticked a role with multiple eligible adults and
	// chose none, ask instead of silently dropping the link.
	if child && isSignForRole(strings.TrimSpace(form["child_sign_role"])) && strings.TrimSpace(form["signed_by"]) == "" {
		signers, _ := formU15Lists(ctx, d.pool, resID, existingID, formPagesOwnedIDs(r, d.getenv), d.getenv, d.now, res.dateFrom)
		if len(signers) > 1 {
			issues = append(issues, validation.Issue{Field: "signed_by", Message: signForWhoMissingText(lang), Severity: "error"})
		}
	}
```

2. On 422 refusal (line 204–207), pass `form` and `sig` to `renderGuestForm422`:

```go
	if len(validation.ErrorsOnly(issues)) > 0 {
		renderGuestForm422(w, r, d, apt, token, lang, resID, existing, form, raw, values, stayFrom, stayTo, sig, issues)
		return nil
	}
```

3. Before `buildSavePayload` (line 208–209), compute `signFor` when `child`:

```go
	nowS := utcStamp(d.now)
	var signFor map[string]any
	if child {
		signFor, err = resolveChildSignerFields(ctx, d, r, resID, res.dateFrom, existingID, form["signed_by"], form["child_sign_role"], nowS)
		if err != nil {
			return err
		}
	}
	payload := buildSavePayload(values, stayFrom, stayTo, sig, child, lang, cfg.noticeVersion, nowS, existing, signFor)
```

4. In `buildSavePayload` (line 397), accept `signFor map[string]any` and update the payload right before `return p`:

```go
	if child {
		// guest.py:2587 — empty signFor adds nothing, so edits keep an earlier link.
		for k, val := range signFor {
			p[k] = val
		}
	} else {
		// guest.py:2596 — a guest 15+ (or corrected to 15+) loses any child signer link.
		p["signed_for_guest_id"] = nil
		p["signed_for_role"] = nil
		p["signed_for_at"] = nil
		p["signed_for_wording"] = nil
	}
```

5. In `guestSaveInsertCols` (line 661), append the four columns:

```go
	"signed_at", "last_errors",
	"signed_for_guest_id", "signed_for_role", "signed_for_at", "signed_for_wording",
```

6. In `handleGuestFormSave` after the `photoBody` block (line 254) and BEFORE `auditGuestFormSaved` (line 255):

```go
	if !child && validation.CertainlyAtLeastAge(values.BirthDate, parseDatePtr(stayFrom), adultSignerAge) {
		if err := linkSignedChildren(ctx, d, r, resID, res.dateFrom, savedID, r.PostForm["sign_for_ids"], form["sign_for_role"], nowS); err != nil {
			return err
		}
	}
```

7. In `renderGuestForm422` (line 706), accept `form map[string]string` and `sig string`, and after `view.Values = guestTypedValues(...)` set:

```go
	if form["legal_ack"] != "" {
		view.Values["legal_ack"] = form["legal_ack"]
	}
	if values.BirthDate != "" {
		arrival := parseDatePtr(stayFrom)
		view.Under15 = validation.CertainlyUnderAge(values.BirthDate, arrival, guestcontract.UnderSignAge)
		view.AdultSigner = validation.CertainlyAtLeastAge(values.BirthDate, arrival, adultSignerAge)
	}
	if validation.IsValidSignature(sig) {
		view.SignatureValue = sig
	} else {
		view.SignatureValue = ""
	}
	if id, ok := parsePositiveASCIIDigits(form["signed_by"]); ok {
		view.SelectedSigner = id
	}
	if isSignForRole(form["child_sign_role"]) {
		view.SelectedChildRole = form["child_sign_role"]
	}
	if isSignForRole(form["sign_for_role"]) {
		view.SelectedSignForRole = form["sign_for_role"]
	}
```

### Step 5: Add `TestGuestSaveChildSigner` and capture the 390 px screenshot

In `go/internal/web/guest/form_save_test.go`, add `TestGuestSaveChildSigner` (guarded with `testPoolOptional(t)` and setting `UBYHOST_SECRET_KEY`, `UBYHOST_DATA_KEY`, `UBYHOST_GUEST_PIN=0`, `UBYHOST_MAIL_BACKEND=disabled`) covering all subtests, asserting the four stored DB columns (`signed_for_guest_id`, `signed_for_role`, `signed_for_at`, `signed_for_wording`) directly:

1. **Zero eligible signers**: child under 15 saves without signature (`submit_state='pending'`, all 4 `signed_for_*` columns NULL, `signed_at` NULL); even with `child_sign_role=parent` and no `signed_by`, saves with NULL link.
2. **One eligible adult signer**:
   - Child posts `signed_by=<adult>`, `child_sign_role=parent` → stores `signed_for_guest_id=adult`, `signed_for_role='parent'`, non-empty `signed_for_at`, `signed_for_wording='u15-2026-11-10'`, empty signature, `submit_state='pending'`.
   - Child edit without `signed_by` / `child_sign_role` preserves the existing four `signed_for_*` columns.
   - Child with 1 eligible signer posting `child_sign_role=parent` and empty `signed_by` → saves with NULL link (no 422).
3. **Multiple eligible adult signers**:
   - Child posts `child_sign_role=parent` with empty `signed_by` → **422**; body contains `#signed_by-error`, `Choose the adult who is signing.`, `id="signed_by"`, `aria-invalid="true"`, `name="child_sign_role" value="parent" checked`, `#u15-block` NOT hidden, `#sig-block` hidden; child row NOT inserted.
   - Same request with `lang=cs` returns `Vyberte dospělého, který podepisuje.`.
   - Child posts `child_sign_role=""` with empty `signed_by` → 303, saved with NULL link.
   - Child posts valid `signed_by=<adult2>` + `child_sign_role=responsible_adult` → 303, linked to `adult2` with role `responsible_adult`.
   - Bogus echo values (`signed_by="1 OR 1"`, `child_sign_role="boss"`, `sign_for_role="boss"`) on 422 are NOT echoed.
4. **Ineligible signers silently dropped (child saves with NULL link)**:
   - Adult on another reservation; adult on this reservation NOT in `ubyhost_guest_ids` cookie; 17-year-old with own signature; archived adult; adult with `"imported"` signature; invalid role `"boss"`; non-numeric `"abc"`.
5. **Child ages out on birth-date correction**:
   - Linked child edited with birth date making them 16 on arrival and empty signature → **422**, prior `signed_for_*` link remains intact in DB.
   - Same edit with valid drawn signature → **303**, signature + `signed_at` saved, all four `signed_for_*` columns cleared to `NULL`.
6. **Adult signs for selected children (`sign_for_ids` + `sign_for_role`)**:
   - Seed owned unsigned child, owned filed (`submit_state='sent'`, `submit_attempts=2`, `last_errors='kept'`) unsigned child, owned 16-year-old, unowned child, archived owned child, and already-linked owned child (`first_adult`, `'parent'`, `'then'`, `'old'`).
   - 17-year-old posting `sign_for_ids` + `sign_for_role=parent` links nobody.
   - Adult posting `sign_for_ids` with empty `sign_for_role` links nobody.
   - Adult posting all IDs (plus duplicate + `"x"`) with `sign_for_role=responsible_adult` links ONLY the unsigned owned active child and the filed owned child (`signed_for_guest_id=adult`, `signed_for_role='responsible_adult'`, non-empty `signed_for_at`, `signed_for_wording='u15-2026-11-10'`); filed child keeps `submit_state='sent'`, `submit_attempts=2`, `last_errors='kept'`; 16-year-old, unowned, archived stay NULL; already-linked child keeps `(first_adult, 'parent', 'then', 'old')`; `runCompletion` hook fires once after linking.
   - Also verify `GET /new` with a pending child and 0 adults renders `#sign-for-children` WITHOUT `hidden`!
7. **Unit checks**: `CertainlyAtLeastAge` (including partial `00002008`, `00062008`, leap-day `00022008`/`29022008`), `IsValidSignature` (rejects `""`, `"imported"`, invalid base64; accepts valid PNG data URL), and `signForWhoMissingText` for all 6 languages (`en`, `cs`, `de`, `es`, `fr`, `uk`).

Capture the 390 px screenshot `docs/tasks/screenshots-2073/child-signer-390.png` from the real Go 422 response of the child form with 2 eligible adults and missing `signed_by` (serving `/static/` from `App/app/static`, Playwright at 390×844, `full_page=True`), open and inspect it, and report what you saw.

## 5. Do not touch

Keep `go/internal/web/guest/i18n.json` and the six Python language catalogs untouched. Preserve outbound filing rules, passport photo handling, schema, `form_pages.go` removal cleanup, and route shape.

## 6. Commands

Run from the indicated directory with pipeline failure reporting on. Expect all listed cases to run and pass with 0 skipped.

```sh
cd go && gofmt -l . 2>&1 | tail -30
cd go && go vet ./... 2>&1 | tail -30
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./internal/validation/... ./internal/web/guest/... -run 'GuestSaveChildSigner|FormSave|FormGuest|FormPages|CertainlyAtLeastAge' -count=1 -v 2>&1 | tail -30
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./... -count=1 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```

Capture `docs/tasks/screenshots-2073/child-signer-390.png` (390 px width, synthetic data, Go 422 child-signer form) and inspect it visually before writing the report.

## 7. Acceptance

- [ ] Under-15 signer validation (`signed_by` / `child_sign_role`) and persistence (`signed_for_guest_id`, `signed_for_role`, `signed_for_at`, `signed_for_wording = "u15-2026-11-10"`) match Python across 0, 1, and 2+ eligible signers, ineligible signers, and edits without a new signer.
- [ ] Adult save links only eligible owned, active, under-15, unlinked children of the same stay (`r.PostForm["sign_for_ids"]` + `sign_for_role`) without touching filing columns, before completion hooks run; 17-year-old cannot link children.
- [ ] Correcting a linked child to age 15+ requires the guest's own drawn signature and clears all four `signed_for_*` columns on save.
- [ ] `formU15Lists`, `formPagesFillU15`, and `renderGuestForm422` match Python for encrypted rows, 18+ valid-signature filtering, `#sign-for-children` visibility, and whitelisted 422 echo; `docs/tasks/screenshots-2073/child-signer-390.png` verified at 390 px.
- [ ] `gofmt`, `go vet`, targeted `TestGuestSaveChildSigner`, full `go test ./...`, and `python3 scripts/context_lint.py` all pass with 0 skips and 0 failures.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2073-report.md` with the changed paths, command results, counts, screenshot inspection, acceptance evidence, and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/web/guest/form_save.go`, `go/internal/web/guest/child_signer.go`, `go/internal/web/guest/form_pages_fill.go`, `go/internal/validation/validation.go`

## Owner steps

1. Open after 2072.
2. Review the child/adult signer test results and `docs/tasks/screenshots-2073/child-signer-390.png`.
