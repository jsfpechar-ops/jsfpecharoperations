# 2074: Restart filing attempts when a guest corrects a record

Status: todo
Depends on: 2073 | Base commit: 81c9fae7f27637649226f39ef9975328ed3cae45 | Branch: task/2074-go-guest-filing-correction
Executor: Gemini 4 Neon (medium) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Restore Python's exact guest self-correction filing transition and retry-budget reset in Go (`POST /l/{token}/{reservation_id}/save`). Preserve a UbyPort duplicate block (`submit_state = 'blocked'`, `last_errors`, `submit_attempts`) when the guest changes none of the 13 fields UbyPort receives, restart `submit_attempts = 0` only for eligible corrections (`error`, `blocked`, `not_required`), and fix the `submission_claim` TTL cutoff unit bug while preserving all `sent`, `restricted_at`, compare-and-set, and active-claim protections.

## 2. Context

Go first. UbyPort filing correctness and privacy take priority. Use synthetic data and an isolated local PostgreSQL schema for tests (`UBYHOST_TEST_DATABASE_URL`). Every anchor below is verified against `81c9fae7f27637649226f39ef9975328ed3cae45`; stop if any anchor diverges.

### Python reference anchors

- `App/app/reporting.py:48` — `PENDING = "pending"`, `SENT = "sent"`, `ERROR = "error"`, `BLOCKED = "blocked"`, `NOT_REQUIRED = "not_required"`; `SUBMISSION_CLAIM_TTL_SECONDS = 5 * 60` (`:98`). Note: there is no `submitting` state; an in-flight send is represented by an active row in `submission_claim`.
- `App/app/reporting.py:186` — `def guest_payload(guest, reservation) -> Dict[str, Any]:` maps the 13 `Ubytovany` fields (`cFrom`, `cUntil`, `cSurN`, `cFirstN`, `cDate`, `cPlac`, `cNati`, `cDocN`, `cVisN`, `cResi`, `cPurp`, `cSpz`, `cNote`).
- `App/app/reporting.py:215` — `FILED_FIELDS` (`surname`, `first_name`, `birth_date`, `nationality`, `doc_number`, `visa_number`, `res_street`, `res_city`, `res_country`, `purpose`, `note`, `stay_from`, `stay_to`).
- `App/app/reporting.py:245` — `def filed_record_changed(stored, proposed, reservation) -> bool:` returns `guest_payload(stored, reservation) != guest_payload(proposed, reservation)`.
- `App/app/reporting.py:1311` — `def blocked_as_duplicate(guest) -> bool:` returns `any(uby_errors.is_duplicate(part) for part in (guest["last_errors"] or "").split(" | "))`.
- `App/app/reporting.py:1320` — `def edit_keeps_duplicate_block(stored, proposed, reservation) -> bool:` returns `_field(stored, "submit_state") == BLOCKED and blocked_as_duplicate(stored) and not filed_record_changed(stored, proposed, reservation)`.
- `App/app/reporting.py:1357` — `def guest_correction_resets_attempts(existing) -> bool:` returns `bool(existing) and existing["submit_state"] in (ERROR, BLOCKED, NOT_REQUIRED)` (never resets `pending` or new inserts).
- `App/app/routes/guest.py:2396` — early refusal when `existing["submit_state"] == reporting.SENT` (403 `already_filed`) and early 303 redirect when `existing["restricted_at"]` is set.
- `App/app/routes/guest.py:2579` — sets default `submit_state` (`not_required` when not reportable, else `pending`) and `last_errors: None`; `:2605` `if existing and reporting.edit_keeps_duplicate_block(existing, {**dict(existing), **payload}, reservation): del payload["submit_state"]; del payload["last_errors"]`; `:2613` `elif reporting.guest_correction_resets_attempts(existing): payload["submit_attempts"] = 0`; `:2624` compare-and-set `db.update_if` on `submit_state` + `NOT EXISTS (SELECT 1 FROM submission_claim WHERE guest_id = ? AND claimed_at >= ?)` returning 403 `already_filed` on 0 rows.

Important parity note on `note`: in Python (`App/app/reporting.py:206`, `:226`) and Go (`go/internal/ubyport/request.go:219`), `note` IS mapped to `<d:cNote>` and sent to UbyPort. Therefore `loadGuestSaveRow` must load `note`, and changing `note` DOES make `FiledRecordChanged` true. Non-reported edits on a guest save are re-saving identical normalized UbyPort fields (e.g., different input case/whitespace, a freshly drawn `signature`, changed `lang`/`notice_lang`, or empty stored `stay_from`/`stay_to` falling back to reservation `date_from`/`date_to`).

### Go anchors (HEAD `81c9fae7f`)

- `go/internal/ubyport/request.go:40` — `type Guest struct` (all 13 UbyPort fields) and `:176` `func GuestFields(g Guest, r Reservation) map[string]any` (canonical projection already used by `go/internal/web/stays/guest_edit.go:297`).
- `go/internal/ubyport/codes.go:154` — `func IsDuplicate(text string) bool` (`strings.Contains(lowered, "duplic") || strings.HasPrefix(lowered, "150:")`).
- `go/internal/ubyport/claim.go:16` — `const SubmissionClaimTTL = 5 * time.Minute` (`time.Duration`; seconds value is `ubyport.SubmissionClaimTTL.Seconds()`, as used in `claim.go:50` and `recover.go:60`).
- `go/internal/ubyport/collect.go:25` — `collectGuestSent`, `collectGuestBlocked`, `collectGuestNotRequired`, `collectMaxAutoAttempts`.
- `go/internal/ubyport/collect.go:214` — `if c.submitState == collectGuestBlocked && blockedAsDuplicate(c.lastErrors) {`
- `go/internal/ubyport/collect.go:284` — `func blockedAsDuplicate(lastErrors string) bool {`
- `go/internal/web/stays/guest_edit.go:297` — `func ubyGuestPayload(g hostGuest, res hostReservation) map[string]any {` (existing host-side reference using `ubyport.GuestFields`).
- `go/internal/web/guest/form_save.go:50` — `type guestSaveRow struct {`
- `go/internal/web/guest/form_save.go:149` — `if existing != nil && existing.submitState == guestSubmitSent {` (and `:153` `restrictedAt` guard).
- `go/internal/web/guest/form_save.go:228` — `payload := buildSavePayload(values, stayFrom, stayTo, sig, child, lang, cfg.noticeVersion, nowS, existing, signFor)`
- `go/internal/web/guest/form_save.go:421` — `func buildSavePayload(...)` with broken `:442` `if existing != nil && existing.submitState == "blocked" && strings.Contains(existing.lastErrors, "duplicate") {`.
- `go/internal/web/guest/form_save.go:461` — `func loadGuestSaveRow(...)` (currently selects only `id`, `submit_state`, `restricted_at`, `signature_png[_enc]`, `last_errors`, `stay_from`, `stay_to`, `nationality`, `entered_by`, `identity_verified_at`, `passport_photo_at`).
- `go/internal/web/guest/form_save.go:499` — `func updateGuestSaveRow(...)` with `:500` `cutoff := float64(d.now().Unix()) - float64(ubyport.SubmissionClaimTTL)` (subtracts nanoseconds instead of seconds) and `:516` swallowing non-`pgx.ErrNoRows` errors.
- `go/internal/web/guest/form_save.go:697` — `var guestSaveInsertCols = []string{` (keep unchanged; inserts rely on `submit_attempts` default `0`).
- `go/internal/web/guest/form_save_test.go:1424` — `func TestGuestSaveChildSigner(t *testing.T)` (reference harness using `testPoolOptional`, `stayEnv`, `seedGuest`, `postForm`, `rememberOwnedGuestIDs`).

## 3. Files

| Path | Action | Purpose |
|---|---|---|
| `go/internal/ubyport/collect.go` | edit | Export `BlockedAsDuplicate`, `FiledRecordChanged`, `EditKeepsDuplicateBlock`, and `GuestCorrectionResetsAttempts` using `GuestFields` and `IsDuplicate`. |
| `go/internal/web/guest/form_save.go` | edit | Load decrypted reportable fields into `guestSaveRow`, apply exact duplicate-block and attempt-reset rules in `buildSavePayload`, fix `SubmissionClaimTTL.Seconds()` cutoff and `pgx.ErrNoRows` handling in `updateGuestSaveRow`. |
| `go/internal/web/guest/form_save_test.go` | edit | Add `TestGuestSaveFilingCorrection` covering duplicate retention, field correction, attempt-cap reset, `pending` preservation, nationality transitions, and `sent`/restricted/claimed/CAS protections. |

The executor report and brief status follow section 9.

## 4. Steps

### Step 1: Export duplicate-block and filing-correction helpers in `go/internal/ubyport/collect.go`

1. Add `"reflect"` to the import block in `go/internal/ubyport/collect.go`.
2. Add `collectGuestError = "error"` to the `const` block at `collect.go:25`:

```go
const (
	collectGuestSent        = "sent"
	collectGuestError       = "error"
	collectGuestBlocked     = "blocked"
	collectGuestNotRequired = "not_required"
	collectMaxAutoAttempts  = 1 // SUBMISSION_MAX_AUTO_ATTEMPTS
)
```

3. Update `collect.go:214` to call `BlockedAsDuplicate(c.lastErrors)`.
4. Replace `blockedAsDuplicate` at `collect.go:283-291` with the four exported helpers mirroring `App/app/reporting.py`:

```go
// BlockedAsDuplicate is reporting.blocked_as_duplicate.
func BlockedAsDuplicate(lastErrors string) bool {
	for _, part := range strings.Split(lastErrors, " | ") {
		if IsDuplicate(part) {
			return true
		}
	}
	return false
}

// FiledRecordChanged is reporting.filed_record_changed: compares the canonical
// UbyPort payload (GuestFields) so empty stay dates falling back to the booking
// window or display-only differences do not count as a correction.
func FiledRecordChanged(stored, proposed Guest, res Reservation) bool {
	return !reflect.DeepEqual(GuestFields(stored, res), GuestFields(proposed, res))
}

// EditKeepsDuplicateBlock is reporting.edit_keeps_duplicate_block (brief 1121):
// true when the stored row is blocked as a duplicate and saving proposed changes
// none of the fields UbyPort receives.
func EditKeepsDuplicateBlock(submitState, lastErrors string, stored, proposed Guest, res Reservation) bool {
	return submitState == collectGuestBlocked &&
		BlockedAsDuplicate(lastErrors) &&
		!FiledRecordChanged(stored, proposed, res)
}

// GuestCorrectionResetsAttempts is reporting.guest_correction_resets_attempts:
// a guest edit restarts submit_attempts only for rows in error, blocked, or
// not_required (never for pending or newly inserted rows).
func GuestCorrectionResetsAttempts(submitState string) bool {
	return submitState == collectGuestError ||
		submitState == collectGuestBlocked ||
		submitState == collectGuestNotRequired
}
```

Do not modify `GuestFields`, `IsDuplicate`, `collect.go` scheduling/cap logic, or any golden XML builder.

### Step 2: Load stored reportable fields and apply exact filing-correction rules in `go/internal/web/guest/form_save.go`

1. Extend `guestSaveRow` (`form_save.go:50-63`) with the stored reportable fields and add `(g *guestSaveRow) ubyGuest() ubyport.Guest`:

```go
type guestSaveRow struct {
	id           int64
	submitState  string
	restrictedAt string
	signaturePNG string
	lastErrors   string
	surname      string
	firstName    string
	birthDate    string
	nationality  string
	docNumber    string
	visaNumber   string
	resStreet    string
	resCity      string
	resCountry   string
	purpose      string
	note         string
	stayFrom     string
	stayTo       string
	enteredBy    string
	// identityVerifiedAt and passportPhotoAt are stored timestamps ("" when unset).
	identityVerifiedAt string
	passportPhotoAt    string
}

func (g *guestSaveRow) ubyGuest() ubyport.Guest {
	return ubyport.Guest{
		StayFrom:    g.stayFrom,
		StayTo:      g.stayTo,
		Surname:     g.surname,
		FirstName:   g.firstName,
		BirthDate:   g.birthDate,
		Nationality: g.nationality,
		DocNumber:   g.docNumber,
		VisaNumber:  g.visaNumber,
		ResStreet:   g.resStreet,
		ResCity:     g.resCity,
		ResCountry:  g.resCountry,
		Purpose:     g.purpose,
		Note:        g.note,
	}
}
```

2. Update `loadGuestSaveRow` (`form_save.go:461-482`) to select all 13 reportable fields plus their `_enc` counterparts and decrypt all 6 protected fields (`birth_date`, `doc_number`, `visa_number`, `res_street`, `res_city`, `signature_png`) through `decryptGuestField` (failing on any decryption error, never silently returning empty):

```go
func loadGuestSaveRow(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, id, resID int64) (*guestSaveRow, error) {
	var g guestSaveRow
	var birthEnc, docEnc, visaEnc, streetEnc, cityEnc, sigEnc string
	err := pool.QueryRow(ctx, `SELECT id, submit_state, COALESCE(restricted_at::text,''),
		COALESCE(surname,''), COALESCE(first_name,''),
		COALESCE(birth_date,''), COALESCE(birth_date_enc,''),
		COALESCE(nationality,''),
		COALESCE(doc_number,''), COALESCE(doc_number_enc,''),
		COALESCE(visa_number,''), COALESCE(visa_number_enc,''),
		COALESCE(res_street,''), COALESCE(res_street_enc,''),
		COALESCE(res_city,''), COALESCE(res_city_enc,''),
		COALESCE(res_country,''), COALESCE(purpose,''), COALESCE(note,''),
		COALESCE(stay_from,''), COALESCE(stay_to,''),
		COALESCE(signature_png,''), COALESCE(signature_png_enc,''),
		COALESCE(last_errors,''), COALESCE(entered_by,''),
		COALESCE(identity_verified_at::text,''), COALESCE(passport_photo_at::text,'')
		FROM guest WHERE id = $1 AND reservation_id = $2`, id, resID).
		Scan(&g.id, &g.submitState, &g.restrictedAt,
			&g.surname, &g.firstName,
			&g.birthDate, &birthEnc,
			&g.nationality,
			&g.docNumber, &docEnc,
			&g.visaNumber, &visaEnc,
			&g.resStreet, &streetEnc,
			&g.resCity, &cityEnc,
			&g.resCountry, &g.purpose, &g.note,
			&g.stayFrom, &g.stayTo,
			&g.signaturePNG, &sigEnc,
			&g.lastErrors, &g.enteredBy,
			&g.identityVerifiedAt, &g.passportPhotoAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	for _, f := range []struct {
		dst *string
		enc string
	}{
		{&g.birthDate, birthEnc},
		{&g.docNumber, docEnc},
		{&g.visaNumber, visaEnc},
		{&g.resStreet, streetEnc},
		{&g.resCity, cityEnc},
		{&g.signaturePNG, sigEnc},
	} {
		plain, derr := decryptGuestField(getenv, now, f.enc, *f.dst)
		if derr != nil {
			return nil, derr
		}
		*f.dst = plain
	}
	return &g, nil
}
```

3. Update the call at `form_save.go:228` to pass `res`:

```go
payload := buildSavePayload(values, res, stayFrom, stayTo, sig, child, lang, cfg.noticeVersion, nowS, existing, signFor)
```

4. Update `buildSavePayload` (`form_save.go:421-459`) to accept `res guestResMeta` and replace lines 442-445 with the exact Python `guest.py:2605-2619` rules while keeping all child-signer (`signFor`), notice, signature, and `entered_by` fields intact:

```go
func buildSavePayload(v validation.GuestRow, res guestResMeta, stayFrom, stayTo, sig string, child bool, lang, noticeVer, now string, existing *guestSaveRow, signFor map[string]any) map[string]any {
	p := map[string]any{
		"surname": v.Surname, "first_name": v.FirstName, "birth_date": v.BirthDate,
		"nationality": v.Nationality, "doc_number": v.DocNumber, "visa_number": v.VisaNumber,
		"res_street": v.ResStreet, "res_city": v.ResCity, "res_country": v.ResCountry,
		"purpose": v.Purpose, "note": v.Note,
		"stay_from": stayFrom, "stay_to": stayTo, "signature_png": sig,
		"notice_version": noticeVer, "notice_lang": lang, "notice_ack_at": now,
		"filled_at": now, "entered_by": "guest", "updated_at": now,
	}
	if child {
		p["signed_at"] = nil
	} else {
		p["signed_at"] = now
	}
	st := guestSubmitNotRequired
	if validation.GuestIsReportable(v.Nationality) {
		st = guestSubmitPending
	}
	p["submit_state"] = st
	p["last_errors"] = nil
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
	if existing != nil {
		proposed := ubyport.Guest{
			StayFrom:    stayFrom,
			StayTo:      stayTo,
			Surname:     v.Surname,
			FirstName:   v.FirstName,
			BirthDate:   v.BirthDate,
			Nationality: v.Nationality,
			DocNumber:   v.DocNumber,
			VisaNumber:  v.VisaNumber,
			ResStreet:   v.ResStreet,
			ResCity:     v.ResCity,
			ResCountry:  v.ResCountry,
			Purpose:     v.Purpose,
			Note:        v.Note,
		}
		ubyRes := ubyport.Reservation{DateFrom: res.dateFrom, DateTo: res.dateTo}
		if ubyport.EditKeepsDuplicateBlock(existing.submitState, existing.lastErrors, existing.ubyGuest(), proposed, ubyRes) {
			delete(p, "submit_state")
			delete(p, "last_errors")
		} else if ubyport.GuestCorrectionResetsAttempts(existing.submitState) {
			p["submit_attempts"] = 0
		}
	}
	return p
}
```

5. Fix `updateGuestSaveRow` (`form_save.go:499-520`) so `cutoff` subtracts seconds (`ubyport.SubmissionClaimTTL.Seconds()`, not nanoseconds) and only `pgx.ErrNoRows` maps to `(false, nil)` while real DB errors propagate:

```go
func updateGuestSaveRow(ctx context.Context, d saveDeps, existing *guestSaveRow, payload map[string]any) (bool, error) {
	cutoff := float64(d.now().Unix()) - ubyport.SubmissionClaimTTL.Seconds()
	enc, err := encryptSaveFields(d.getenv, payload)
	if err != nil {
		return false, err
	}
	args := []any{existing.id, existing.submitState, cutoff}
	sets := make([]string, 0, len(enc))
	i := 4
	for k, v := range enc {
		sets = append(sets, k+" = $"+strconv.Itoa(i))
		args = append(args, v)
		i++
	}
	q := `UPDATE guest SET ` + strings.Join(sets, ", ") + ` WHERE id = $1 AND submit_state = $2
		AND NOT EXISTS (SELECT 1 FROM submission_claim WHERE guest_id = $1 AND claimed_at >= $3) RETURNING id`
	var id int64
	if err := d.pool.QueryRow(ctx, q, args...).Scan(&id); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return false, nil
		}
		return false, err
	}
	return id == existing.id, nil
}
```

Keep `guestSaveInsertCols` (`form_save.go:697`) and the early `guestSubmitSent` / `restrictedAt` guards (`form_save.go:149-157`) unchanged.

### Step 3: Add `TestGuestSaveFilingCorrection` in `go/internal/web/guest/form_save_test.go`

Add `"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"` to imports in `form_save_test.go` (if needed for direct helper assertions) and implement `TestGuestSaveFilingCorrection(t *testing.T)` following the `TestGuestSaveChildSigner` (`form_save_test.go:1424`) HTTP + PostgreSQL harness (`testPoolOptional`, `secure.LoadDataKeys(testDataEnv)`, `RegisterStayClaim` + `RegisterFormPages` + `RegisterFormSave`, signed owned-guest cookie via `rememberOwnedGuestIDs`, isolated per-subtest stay with `t.Cleanup` deleting `submission_claim`, `guest`, `reservation_claim`, `reservation`, `apartment`, `user_account`).

Cover all of the following subtests and assert HTTP status plus final DB `submit_state`, `last_errors`, `submit_attempts`, and decrypted fields (verifying 0 skips when `UBYHOST_TEST_DATABASE_URL` is set):

1. `blocked_duplicate_unchanged_fields_stays_blocked`:
   - Seed `submit_state = 'blocked'`, `last_errors = '150: Duplicate record'`, `submit_attempts = 3`, `nationality = 'DEU'`, `surname = 'SMITH'`, `first_name = 'JOHN'`, `birth_date = '10051990'` (encrypted), `doc_number = 'DOC12345'` (encrypted), `stay_from = ''`, `stay_to = ''` (empty so `GuestFields` falls back to booking dates `2026-06-20`..`2026-06-22`).
   - POST with lowercase/spaced inputs (`surname=" smith "`, `first_name=" john "`, `birth_date="10.05.1990"`), a different valid `signature` PNG, and `lang=de`.
   - Assert 303 redirect; `submit_state == "blocked"`, `last_errors == "150: Duplicate record"`, `submit_attempts == 3`, and `notice_lang == "de"` (proving non-filing columns still saved).
2. `blocked_duplicate_czech_wording_stays_blocked`:
   - Seed `submit_state = 'blocked'`, `last_errors = '105: Jiná chyba | Duplicitní záznam'`, `submit_attempts = 2` (contains `"duplic"`, not `"duplicate"`).
   - POST unchanged UbyPort fields.
   - Assert 303; `submit_state == "blocked"`, `last_errors` unchanged, `submit_attempts == 2`.
3. `blocked_duplicate_changed_field_resets`:
   - Subcases changing `doc_number` (`DOC12345` -> `DOC99999`), changing `birth_date` (`10.05.1990` -> `11.05.1990`), changing `surname` (`SMITH` -> `JONES`), and changing `note` (`""` -> `"Late arrival"`, which changes `cNote`).
   - Assert 303; `submit_state == "pending"`, `last_errors` is NULL, `submit_attempts == 0`, and decrypted stored field reflects the edit.
4. `non_duplicate_error_and_blocked_at_attempt_cap_reset`:
   - Seed `submit_state = 'error'`, `last_errors = '104: Invalid birth date'`, `submit_attempts = 3`; POST corrected or unchanged fields -> 303, `submit_state == "pending"`, `last_errors` NULL, `submit_attempts == 0`.
   - Seed `submit_state = 'blocked'`, `last_errors = '104: Invalid birth date'` (non-duplicate), `submit_attempts = 3`; POST unchanged fields -> 303, `submit_state == "pending"`, `last_errors` NULL, `submit_attempts == 0`.
5. `pending_edit_preserves_submit_attempts`:
   - Seed `submit_state = 'pending'`, `last_errors = 'transient'`, `submit_attempts = 2`.
   - POST edit (e.g. changing `surname`).
   - Assert 303; `submit_state == "pending"`, `last_errors` NULL, `submit_attempts == 2` (NOT reset).
6. `nationality_transitions`:
   - Reportable duplicate-blocked (`DEU`, `submit_state = 'blocked'`, `last_errors = '150: Duplicate record'`, `submit_attempts = 3`) -> edit `nationality` to `CZE` -> 303, `submit_state == "not_required"`, `last_errors` NULL, `submit_attempts == 0`.
   - Reportable `error` (`DEU`, `submit_state = 'error'`, `submit_attempts = 3`) -> edit `nationality` to `CZE` -> 303, `submit_state == "not_required"`, `last_errors` NULL, `submit_attempts == 0`.
   - Czech (`CZE`, `submit_state = 'not_required'`, `submit_attempts = 2`) -> edit `nationality` to `DEU` -> 303, `submit_state == "pending"`, `last_errors` NULL, `submit_attempts == 0`.
7. `sent_restricted_claimed_and_cas_protected`:
   - `submit_state = 'sent'`, `submitted_at = stamp`, `submit_attempts = 1`: POST returns 403 (`already_filed`); `surname`, `doc_number_enc`, `submit_state`, `submit_attempts`, `submitted_at` untouched.
   - `restricted_at = stamp`, `submit_state = 'error'`, `submit_attempts = 2`: POST returns 303 to stay page without updating guest row (`surname`, `submit_state`, `submit_attempts` untouched).
   - Active `submission_claim` (`claimed_at = float64(now().Unix()) - 60`, within 5 min TTL) on `submit_state = 'error'`, `submit_attempts = 2`: POST returns 403 (`already_filed`); row untouched (`submit_state == "error"`, `submit_attempts == 2`, `surname` untouched).
   - Expired `submission_claim` (`claimed_at = float64(now().Unix()) - 600`, past 5 min TTL) on `submit_state = 'error'`, `submit_attempts = 2`: POST returns 303; row updated (`submit_state == "pending"`, `last_errors` NULL, `submit_attempts == 0`).
   - Concurrent CAS state flip: call `updateGuestSaveRow` with stale `existing.submitState = "error"` after DB row was updated to `"sent"` -> returns `updated == false, err == nil`, `"sent"` row untouched.

## 5. Do not touch

Keep the nationalities list, error codebook, lease duration (`SubmissionClaimTTL = 5 * time.Minute`), scheduler retry cap, `GuestFields` XML contract, `guestSaveInsertCols`, and `go/internal/web/stays/guest_edit.go` fixed. No live UbyPort calls. No edits under `App/`.

## 6. Commands

Run from the repo root (or `cd go` as shown) with pipeline failure reporting on. Expect every listed command and test case to run and pass with 0 skipped.

```sh
cd go && gofmt -l . 2>&1 | tail -30
cd go && go vet ./... 2>&1 | tail -30
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./internal/web/guest/ -run 'GuestSaveFilingCorrection|FormSave|GuestWriteEncryption|GuestSaveChildSigner' -count=1 -v 2>&1 | tail -30
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./internal/ubyport/ -run 'Collect|GoldenEnvelopes' -count=1 -v 2>&1 | tail -30
cd go && UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5433/guest_test go test ./... -count=1 2>&1 | tail -30
python3 scripts/context_lint.py 2>&1 | tail -30
```

Use fixture credentials and record only pass/fail, counts, and redacted diagnostics.

## 7. Acceptance

- [ ] `ubyport.BlockedAsDuplicate`, `ubyport.FiledRecordChanged`, `ubyport.EditKeepsDuplicateBlock`, and `ubyport.GuestCorrectionResetsAttempts` share `ubyport.GuestFields` and `ubyport.IsDuplicate` with zero duplicate field lists and passing `Collect` / `GoldenEnvelopes` tests.
- [ ] `loadGuestSaveRow` hydrates and decrypts all 13 reportable fields (`birth_date`, `doc_number`, `visa_number`, `res_street`, `res_city`, `signature_png` via `decryptGuestField`), and `buildSavePayload` matches `App/app/routes/guest.py:2579-2619` exactly.
- [ ] Unchanged duplicate-blocked edits (including case/whitespace normalization, fresh signature, language change, empty stay dates inheriting booking dates, and non-English `duplic` / `150:` errors) stay `blocked` with `last_errors` and `submit_attempts` preserved; any changed `GuestFields` value resets to `pending`/`not_required`, `last_errors = NULL`, `submit_attempts = 0`.
- [ ] Non-duplicate `error`/`blocked` edits reset `submit_attempts = 0`; `pending` edits do not reset `submit_attempts`; nationality transitions between reportable and `CZE` set the right `submit_state` and reset attempts on eligible rows.
- [ ] `sent`, `restricted_at`, active `submission_claim` (within 5 min TTL), and CAS-flipped rows are refused untouched; expired `submission_claim` rows (past 5 min TTL) no longer block guest saves.
- [ ] `gofmt`, `go vet`, targeted guest + ubyport tests, full `go test ./... -count=1`, and `python3 scripts/context_lint.py` all pass with 0 skipped and 0 failures.

## 8. Stop and ask

Stop and report if an anchor diverges after listed prerequisites, a required test fails twice, a dependency or file outside section 3 is needed, or the executor limit is reached. Escalate any need for live credentials, a real provider, a deployed server, or a product decision.

## 9. Report

Write `docs/tasks/2074-report.md` with the changed paths, command results, counts, acceptance evidence and owner steps. Set the brief to `Status: review` after completing the checks. Use `Status: blocked` in the report if stopped.

## Risk list (for the reviewer)

`go/internal/web/guest/form_save.go`, `go/internal/ubyport/collect.go`

## Owner steps

1. Open after 2073.
2. Check that the report distinguishes an unchanged duplicate (preserving `blocked`, `last_errors`, and `submit_attempts`) from a genuine UbyPort field correction, and confirms active vs expired `submission_claim` behavior.
