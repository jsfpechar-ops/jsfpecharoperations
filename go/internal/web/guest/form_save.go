package guest

// Brief 1724: guest_form_save (App/app/routes/guest.py 2362–2784).

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/passportphotos"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	guestSubmitSent        = "sent"
	guestSubmitPending     = "pending"
	guestSubmitNotRequired = "not_required"
)

// RegisterFormSave wires POST /l/{token}/{reservation_id}/save (dormant until UBYHOST_GO_PATHS).
func RegisterFormSave(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler, hooks CompletionHooks) {
	d := saveDeps{pool: pool, getenv: getenv, now: now, hooks: hooks}
	mux.Handle("POST /l/{token}/{reservation_id}/save", wrap("POST /l/{token}/{reservation_id}/save", WithPOSTCSRF(getenv, now, guestFormSaveHandler(d))))
}

type saveDeps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
	hooks  CompletionHooks
}

func (d saveDeps) shell() shellDeps {
	return shellDeps{pool: d.pool, getenv: d.getenv, now: d.now}
}

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

// guestResMeta is loaded by brief 1721 stay helpers.
type guestResMeta struct {
	apartmentID    int64
	dateFrom       string
	dateTo         string
	declaredGuests *int64
	overrideGuests *int64
	reducedGuests  *int64
}

type guestFormCfg struct {
	defaultPurpose string
	noticeVersion  string
	ownerUserID    int64
}

func guestFormSaveHandler(d saveDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if err := handleGuestFormSave(r.Context(), d, w, r); err != nil {
			http.Error(w, "server error", http.StatusInternalServerError)
		}
	}
}

// guestMaxMultipart mirrors hostweb csrfMaxMultipart (a 10 MiB photo plus the
// form fields). Keep the two values equal.
const guestMaxMultipart = 11 << 20

func handleGuestFormSave(ctx context.Context, d saveDeps, w http.ResponseWriter, r *http.Request) error {
	if d.pool == nil {
		return errors.New("guest form save: nil pool")
	}
	if strings.HasPrefix(r.Header.Get("Content-Type"), "multipart/form-data") {
		if r.MultipartForm == nil {
			r.Body = http.MaxBytesReader(w, r.Body, guestMaxMultipart)
			if err := r.ParseMultipartForm(maxPDFBytes + 1024); err != nil {
				return err
			}
		}
		defer func() {
			if r.MultipartForm != nil {
				_ = r.MultipartForm.RemoveAll()
			}
		}()
	} else if err := r.ParseForm(); err != nil {
		return err
	}
	token := r.PathValue("token")
	resID, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return nil
	}
	lang := formRequestLanguage(r)
	apt, token, early := OpenLink(r, d.pool, token, lang)
	if early != nil {
		early.ServeHTTP(w, r)
		return nil
	}
	if requirePin(w, r, d.shell(), token, lang, apt) {
		return nil
	}
	cfg, res, status, ok, accessErr := guestSaveReservation(ctx, d, r, apt, resID, token)
	if accessErr != nil {
		return accessErr
	}
	if !ok {
		guestUnavailable(w, r, lang, "stay_gone", http.StatusNotFound, token, resID)
		return nil
	}
	if throttleGuestPost(w, r, d, token, "guest_save", lang) {
		return nil
	}
	if (formPageDeps{pool: d.pool, getenv: d.getenv, now: d.now}).formPagesRequireClaim(w, r, apt, formResRow{id: resID, apartmentID: res.apartmentID, ownerUserID: cfg.ownerUserID, status: status, dateFrom: res.dateFrom, dateTo: res.dateTo, declaredGuests: res.declaredGuests, overrideGuests: res.overrideGuests, reducedGuests: res.reducedGuests}, token, lang) {
		return nil
	}
	form := postForm(r)
	guestID := ownedGuestID(r, d.getenv, form)
	var existing *guestSaveRow
	if guestID > 0 {
		existing, err = loadGuestSaveRow(ctx, d.pool, d.getenv, d.now, guestID, resID)
		if err != nil {
			return err
		}
		if existing != nil && existing.submitState == guestSubmitSent {
			guestUnavailable(w, r, lang, "already_filed", http.StatusForbidden, token, resID)
			return nil
		}
		if existing != nil && existing.restrictedAt != "" {
			WithLang(w, d.getenv, lang)
			http.Redirect(w, r, GuestLink(token, resID, LangQuery(lang, "")), http.StatusSeeOther)
			return nil
		}
		if existing != nil && guestFormLocked(existing) {
			guestUnavailable(w, r, lang, "form_locked", http.StatusForbidden, token, resID)
			return nil
		}
	}
	raw := validation.GuestFormRaw(form, cfg.defaultPurpose)
	values := validation.NormaliseGuest(raw, legalToday(d.now))
	stayFrom, stayTo := lockedStayDates(res, existing)
	sig := keptGuestSignature(form["signature"], existingSig(existing))
	child := validation.CertainlyUnderAge(values.BirthDate, parseDatePtr(stayFrom), guestcontract.UnderSignAge)
	if child {
		sig = ""
	}
	issues := guestSaveValidateIssues(form, res, values, raw, stayFrom, stayTo, sig, child, existing, legalToday(d.now), lang)
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
	// guest.py:2483 — a required-photo property needs a passport photo from a foreign guest.
	// The file is read and validated before anything is written; a valid upload is stored after the row.
	var photoBody []byte
	var photoExt string
	storedNat, storedBy, storedVerified := values.Nationality, "guest", ""
	if existing != nil {
		storedNat, storedBy, storedVerified = existing.nationality, existing.enteredBy, existing.identityVerifiedAt
	}
	if passportRequired(apt.PassportPhotoPolicy, storedNat, storedBy, storedVerified) {
		hasExisting := existing != nil && existing.passportPhotoAt != "" && passportphotos.Has(guestDataDir(d.getenv), existing.id)
		file, hdr, ferr := r.FormFile("passport_photo")
		present := ferr == nil && hdr != nil && !(hdr.Size == 0 && hdr.Filename == "")
		if present {
			raw, rerr := readUploadLimited(file)
			_ = file.Close()
			if rerr != nil {
				return rerr
			}
			body, ext, perr := passportphotos.Prepare(raw, hdr.Header.Get("Content-Type"))
			if perr != nil {
				issues = append(issues, validation.Issue{Field: "passport_photo", Message: passportUploadText(lang, perr.Error()), Severity: "error"})
			} else {
				photoBody, photoExt = body, ext
			}
		} else if !hasExisting {
			issues = append(issues, validation.Issue{Field: "passport_photo", Message: stringsCatalog.T(lang, "passport_photo_missing", nil), Severity: "error"})
		}
	}
	// guest.py:2518 — name the field that holds another alphabet, then word every
	// sentence for the guest. Both passes run before the refusal is tested, so a
	// translated sentence is what the page shows and what the log counts.
	issues = localizeIssues(nameLatinIssues(issues, lang), lang)
	if len(validation.ErrorsOnly(issues)) == 0 {
		if dup, derr := hasSamePersonGuestOnStay(ctx, d, resID, existingID, values); derr != nil {
			return derr
		} else if dup {
			issues = append(issues, validation.Issue{Field: "surname", Message: stringsCatalog.T(lang, "error_duplicate_guest", nil), Severity: "error"})
		}
	}
	if len(validation.ErrorsOnly(issues)) > 0 {
		renderGuestForm422(w, r, d, apt, token, lang, resID, existing, form, raw, values, stayFrom, stayTo, sig, issues)
		return nil
	}
	nowS := utcStamp(d.now)
	var signFor map[string]any
	if child {
		signFor, err = resolveChildSignerFields(ctx, d, r, resID, res.dateFrom, existingID, form["signed_by"], form["child_sign_role"], nowS)
		if err != nil {
			return err
		}
	}
	payload := buildSavePayload(values, res, stayFrom, stayTo, sig, child, lang, cfg.noticeVersion, nowS, existing, signFor)
	var savedID int64
	if existing != nil {
		ok, err := updateGuestSaveRow(ctx, d, existing, payload)
		if err != nil {
			return err
		}
		if !ok {
			guestUnavailable(w, r, lang, "already_filed", http.StatusForbidden, token, resID)
			return nil
		}
		savedID = existing.id
	} else {
		partySize, _ := strconv.Atoi(validation.Strip(form["party_size"]))
		ins, insErr := insertGuestSaveRow(ctx, d, payload, resID, res, partySize)
		if insErr != nil {
			return insErr
		}
		if ins.countCode != "" {
			if err := auditHeadcountCount(ctx, d.pool, d.now, resID, ins.countCode, ins.countOld, partySize, cfg.ownerUserID); err != nil {
				return err
			}
		}
		savedID = ins.id
		if savedID == 0 {
			WithLang(w, d.getenv, lang)
			http.Redirect(w, r, GuestLink(token, resID, LangQuery(lang, "")), http.StatusSeeOther)
			return nil
		}
	}
	// guest.py:2709 — store the prepared photo and stamp it only after the file is durable.
	if photoBody != nil {
		keys, kerr := secure.LoadDataKeys(d.getenv)
		if kerr != nil {
			return kerr
		}
		if err := passportphotos.SavePrepared(guestDataDir(d.getenv), keys, savedID, photoBody, photoExt); err != nil {
			return err
		}
		if _, err := d.pool.Exec(ctx, `UPDATE guest SET passport_photo_at = $1, updated_at = $1 WHERE id = $2 AND reservation_id = $3`, nowS, savedID, resID); err != nil {
			return err
		}
	}
	if !child && validation.CertainlyAtLeastAge(values.BirthDate, parseDatePtr(stayFrom), adultSignerAge) {
		if err := linkSignedChildren(ctx, d, r, resID, res.dateFrom, savedID, r.PostForm["sign_for_ids"], form["sign_for_role"], nowS); err != nil {
			return err
		}
	}
	if err := auditGuestFormSaved(ctx, d.pool, savedID, resID, cfg.ownerUserID, lang, d.now); err != nil {
		return err
	}
	rememberOwnedGuestIDs(w, d.getenv, append(ownedGuestIDs(r, d.getenv), savedID))
	// 2096: continue to the next guest while some are missing, else land on the
	// stay Review & Confirm summary screen (confirm endpoint fires completion
	// hooks and jumps to #fee-pay once confirmed).
	var missing *int
	if fresh, okFresh := formPagesReservation(ctx, d.pool, apt, resID, r); okFresh {
		missing = formPagesProgress(ctx, d.pool, fresh).remaining
	}
	tail := ""
	if existing == nil && missing != nil && *missing > 0 {
		tail = "/new"
	}
	loc := GuestLink(token, resID, tail+LangQuery(lang, "&saved=1"))
	WithLang(w, d.getenv, lang)
	http.Redirect(w, r, loc, http.StatusSeeOther)
	return nil
}

// guestSaveReservation follows the picker fast path before its reachback fallback.
func guestSaveReservation(ctx context.Context, d saveDeps, r *http.Request, apt *Apartment, resID int64, token string) (guestFormCfg, guestResMeta, string, bool, error) {
	if d.pool == nil || apt == nil || resID <= 0 {
		return guestFormCfg{}, guestResMeta{}, "", false, nil
	}
	pa, found := loadPickApartment(ctx, d.pool, apt.ID)
	if !found || pa.PermalinkToken != apt.PermalinkToken {
		return guestFormCfg{}, guestResMeta{}, "", false, nil
	}
	today := pragueTodayPick(d.now())
	visible, err := visibleReservations(ctx, d.pool, pa, today)
	if err != nil {
		return guestFormCfg{}, guestResMeta{}, "", false, err
	}
	eligible := false
	for _, row := range visible {
		if row.ID == resID {
			eligible = true
			break
		}
	}
	var cfg guestFormCfg
	var res guestResMeta
	var status, source string
	var locked *string
	err = d.pool.QueryRow(ctx, `SELECT r.apartment_id, a.owner_user_id, r.date_from::text, r.date_to::text,
		r.declared_guests, r.expected_guests_override, r.lead_reduced_guests, r.status, COALESCE(r.source,''), c.guest_access_locked_at, COALESCE(a.default_purpose,'')
		FROM reservation r JOIN apartment a ON a.id = r.apartment_id LEFT JOIN reservation_claim c ON c.reservation_id = r.id
		WHERE r.id = $1 AND r.apartment_id = $2 AND r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 AND a.archived_at IS NULL AND a.permalink_token = $3`,
		resID, apt.ID, apt.PermalinkToken).Scan(&res.apartmentID, &cfg.ownerUserID, &res.dateFrom, &res.dateTo,
		&res.declaredGuests, &res.overrideGuests, &res.reducedGuests, &status, &source, &locked, &cfg.defaultPurpose)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return guestFormCfg{}, guestResMeta{}, "", false, nil
		}
		return guestFormCfg{}, guestResMeta{}, "", false, err
	}
	owner := (formPageDeps{pool: d.pool, getenv: d.getenv, now: d.now}).access().hostOwns(ctx, r, cfg.ownerUserID)
	if source == "demo" {
		if !owner || !GuestAccessOpen(status, locked != nil && *locked != "") {
			return guestFormCfg{}, guestResMeta{}, "", false, nil
		}
	} else if !eligible {
		rd := pa.ReachbackDays
		reach := validation.NormaliseReachbackDays(&rd)
		cutoff := today.AddDate(0, 0, -int(reach)).Format("2006-01-02")
		if (locked != nil && *locked != "") || res.dateTo < cutoff {
			return guestFormCfg{}, guestResMeta{}, "", false, nil
		}
		if registrationComplete(ctx, d.pool, d.getenv, d.now, pickReservation{ID: resID, DateFrom: res.dateFrom, DateTo: res.dateTo}, today) {
			ownedIDs := ownedGuestIDs(r, d.getenv)
			var ownedStay bool
			if len(ownedIDs) > 0 {
				if err := d.pool.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM guest WHERE reservation_id = $1 AND id = ANY($2))`, resID, ownedIDs).Scan(&ownedStay); err != nil {
					return guestFormCfg{}, guestResMeta{}, "", false, err
				}
			}
			if !owner && !ownedStay && !DeviceHoldsClaim(r, d.getenv, resID, guestSaveClaimVersion(ctx, d.pool, resID)) {
				return guestFormCfg{}, guestResMeta{}, "", false, nil
			}
		}
	}
	if d.getenv != nil {
		cfg.noticeVersion = noticeVersion(d.getenv)
	}
	return cfg, res, status, true, nil
}

func guestSaveClaimVersion(ctx context.Context, pool *pgxpool.Pool, resID int64) int64 {
	claim, err := EnsureClaimRow(ctx, pool, resID, time.Now().UTC().Format(time.RFC3339))
	if err != nil {
		return -1
	}
	return claim.tokenVersion
}

// guestSaveValidateIssues is the save route's database-free checks, in the
// order of guest.py: the form, the signature, then the legal acknowledgement.
// The two sentences owned by this function are worded in the guest's language.
func guestSaveValidateIssues(form map[string]string, res guestResMeta, values validation.GuestRow, raw map[string]string, stayFrom, stayTo, sig string, child bool, existing *guestSaveRow, today time.Time, lang string) []validation.Issue {
	from, to := parseDate(stayFrom), parseDate(stayTo)
	issues := validation.ValidateGuestForm(values, &from, &to, today, raw)
	// guest.py:2462 — a new guest with no expected total gives a party size of 1–60.
	if existing == nil && headcount.Expected(res.overrideGuests, res.declaredGuests, res.reducedGuests) == nil {
		if n, err := strconv.Atoi(validation.Strip(form["party_size"])); err != nil || n < 1 || n > 60 {
			issues = append(issues, validation.Issue{Field: "party_size", Message: stringsCatalog.T(lang, "error_party_size", nil), Severity: "error"})
		}
	}
	if si := validation.GuestFormSignatureIssue(sig, child); si != nil {
		issues = append(issues, *si)
	}
	// guest.py:2480 — the guest must confirm the legal notice.
	if form["legal_ack"] == "" {
		issues = append(issues, validation.Issue{Field: "legal_ack", Message: stringsCatalog.T(lang, "legal_ack_missing", nil), Severity: "error"})
	}
	return issues
}

func postForm(r *http.Request) map[string]string {
	out := map[string]string{}
	for k, v := range r.PostForm {
		if len(v) > 0 {
			out[k] = v[0]
		}
	}
	return out
}

func existingSig(g *guestSaveRow) string {
	if g == nil {
		return ""
	}
	return g.signaturePNG
}

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

func decryptGuestField(getenv func(string) string, now func() time.Time, token, plain string) (string, error) {
	if token == "" {
		return plain, nil
	}
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		return "", err
	}
	when := time.Now()
	if now != nil {
		when = now()
	}
	return keys.DecryptField(token, when)
}

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

// guestInsert is what insertGuestSaveRow reports once its transaction has ended.
type guestInsert struct {
	id         int64  // the new guest, or 0 when none was written
	countCode  string // the first form's count result, "" when no count was attempted
	countOld   *int64 // the declared count before that attempt
	countSaved bool   // the count was saved in the committed transaction
}

// auditHeadcountCount is headcount.record for a first-form count. Call after commit.
func auditHeadcountCount(ctx context.Context, pool *pgxpool.Pool, now func() time.Time, resID int64, code string, old *int64, count int, owner int64) error {
	var action string
	switch code {
	case codeSaved:
		action = "reservation_declared_guests_set"
	case codeBelowFloor:
		action = "reservation_declared_guests_refused"
	default:
		return nil
	}
	from := "None"
	if old != nil {
		from = strconv.FormatInt(*old, 10)
	}
	_, err := pool.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1, $2, $3, $4, $5)`,
		now().UTC(), "guest", action, fmt.Sprintf("id=%d from=%s to=%d source=first_form", resID, from, count), owner)
	return err
}

// insertGuestSaveRow is guest.py's first-form block (brief 1092): the lock, the
// fresh reservation, the first count and the guest INSERT share one transaction.
func insertGuestSaveRow(ctx context.Context, d saveDeps, payload map[string]any, resID int64, res guestResMeta, partySize int) (guestInsert, error) {
	var out guestInsert
	tx, err := d.pool.Begin(ctx)
	if err != nil {
		return out, err
	}
	defer tx.Rollback(ctx) //nolint:errcheck
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext('reservation'), $1::int)`, resID); err != nil {
		return out, err
	}
	// Read the reservation fresh under the lock, as Python does.
	var aptID int64
	var status, archived string
	var override, declared, reduced *int64
	err = tx.QueryRow(ctx, `SELECT apartment_id, COALESCE(status,''), COALESCE(archived_at::text,''),
		expected_guests_override, declared_guests, lead_reduced_guests
		FROM reservation WHERE id = $1 FOR UPDATE`, resID).Scan(&aptID, &status, &archived, &override, &declared, &reduced)
	if errors.Is(err, pgx.ErrNoRows) {
		return out, nil
	}
	if err != nil {
		return out, err
	}
	if aptID != res.apartmentID || (partyStay{status: status, archivedAt: archived}).gone() {
		return out, nil
	}
	if headcount.Expected(override, declared, reduced) == nil {
		out.countOld = declared
		out.countCode, err = partyDeps{pool: d.pool, getenv: d.getenv, now: d.now}.applyDeclaredTx(ctx, tx, resID, partySize)
		if err != nil {
			return out, err
		}
		out.countSaved = out.countCode == codeSaved
		if !out.countSaved {
			return out, tx.Commit(ctx)
		}
		if err = tx.QueryRow(ctx, `SELECT expected_guests_override, declared_guests, lead_reduced_guests
			FROM reservation WHERE id = $1`, resID).Scan(&override, &declared, &reduced); err != nil {
			return out, err
		}
	}
	exp := headcount.Expected(override, declared, reduced)
	live, err := liveGuestRows(ctx, tx, resID)
	if err != nil {
		return out, err
	}
	if exp != nil && live >= int(*exp) {
		// The count, if saved, still commits; no guest is added to a full group.
		return out, tx.Commit(ctx)
	}
	var isFirst bool
	if err := tx.QueryRow(ctx, `SELECT NOT EXISTS (SELECT 1 FROM guest WHERE reservation_id = $1)`, resID).Scan(&isFirst); err != nil {
		return out, err
	}
	lead := 0
	if isFirst {
		lead = 1
	}
	payload["reservation_id"] = resID
	payload["is_lead"] = lead
	payload["created_at"] = payload["filled_at"]
	enc, err := encryptSaveFields(d.getenv, payload)
	if err != nil {
		return out, err
	}
	var id int64
	err = tx.QueryRow(ctx, `INSERT INTO guest (`+strings.Join(guestSaveInsertCols, ", ")+`)
		VALUES (`+guestSaveInsertPlaceholders()+`) RETURNING id`,
		guestSaveInsertArgs(enc)...).Scan(&id)
	if err != nil {
		return out, err
	}
	out.id = id
	return out, tx.Commit(ctx)
}

func encryptSaveFields(getenv func(string) string, payload map[string]any) (map[string]any, error) {
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		return nil, err
	}
	return secure.GuestWriteValues(keys, payload)
}

func auditGuestFormSaved(ctx context.Context, pool *pgxpool.Pool, guestID, resID, owner int64, lang string, now func() time.Time) error {
	_, err := pool.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id) VALUES ($1, $2, $3, $4, $5)`,
		now().UTC(), "guest", "guest_form_saved", fmt.Sprintf("guest=%d reservation=%d lang=%s", guestID, resID, lang), owner)
	return err
}

func parseDate(s string) time.Time {
	t, ok := validation.ParseISODate(s)
	if !ok {
		return time.Time{}
	}
	return t
}

func legalToday(now func() time.Time) time.Time {
	at := now()
	return time.Date(at.Year(), at.Month(), at.Day(), 0, 0, 0, 0, time.UTC)
}

func utcStamp(now func() time.Time) string {
	return now().UTC().Format(time.RFC3339)
}

// Portal hooks (briefs 1720–1723 replace these stubs in shell.go / form_pages.go).
func throttleGuestPost(w http.ResponseWriter, r *http.Request, d saveDeps, token, kind, lang string) bool {
	if guestPostLimited(r.Context(), d.pool, d.getenv, r, token, kind, d.now()) {
		guestUnavailable(w, r, lang, "rate_limited", http.StatusTooManyRequests, token, 0)
		return true
	}
	return false
}

func guestLink(token string, resID int64, lang string) string {
	_ = lang
	return GuestLink(token, resID, "")
}

func guestUnavailable(w http.ResponseWriter, r *http.Request, lang, code string, status int, token string, resID int64) {
	extra := map[string]string{}
	if resID > 0 {
		extra["reservation_id"] = strconv.FormatInt(resID, 10)
	}
	WriteUnavailable(w, r, lang, code, status, token, extra)
}

func ownedGuestID(r *http.Request, getenv func(string) string, form map[string]string) int64 {
	raw := strings.TrimSpace(form["guest_id"])
	id, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || id <= 0 {
		return 0
	}
	for _, owned := range ownedGuestIDs(r, getenv) {
		if owned == id {
			return id
		}
	}
	return 0
}

// guestSaveInsertCols is the guest-row write list. Encrypted PII must use the
// *_enc columns; omitting them silently dropped birth date, document and signature.
var guestSaveInsertCols = []string{
	"reservation_id", "is_lead", "surname", "first_name", "nationality",
	"res_country", "purpose", "note", "stay_from", "stay_to",
	"notice_version", "notice_lang", "notice_ack_at", "filled_at", "entered_by",
	"submit_state", "created_at", "updated_at",
	"birth_date_enc", "doc_number_enc", "visa_number_enc",
	"res_street_enc", "res_city_enc", "signature_png_enc",
	"signed_at", "last_errors",
	"signed_for_guest_id", "signed_for_role", "signed_for_at", "signed_for_wording",
}

func guestSaveInsertPlaceholders() string {
	parts := make([]string, len(guestSaveInsertCols))
	for i := range guestSaveInsertCols {
		parts[i] = "$" + strconv.Itoa(i+1)
	}
	return strings.Join(parts, ",")
}

func guestSaveInsertArgs(enc map[string]any) []any {
	args := make([]any, len(guestSaveInsertCols))
	for i, col := range guestSaveInsertCols {
		args[i] = enc[col]
	}
	return args
}

func lockedStayDates(res guestResMeta, existing *guestSaveRow) (string, string) {
	if existing != nil && existing.stayFrom != "" {
		return existing.stayFrom, existing.stayTo
	}
	return res.dateFrom, res.dateTo
}

func keptGuestSignature(posted, stored string) string {
	if strings.TrimSpace(posted) != "" {
		return posted
	}
	return stored
}

func guestFormLocked(row *guestSaveRow) bool { return false }

// hasSamePersonGuestOnStay checks whether another live guest row on resID
// already represents the same individual (2095 Layer 1 duplicate prevention).
func hasSamePersonGuestOnStay(ctx context.Context, d saveDeps, resID, excludeID int64, values validation.GuestRow) (bool, error) {
	rows, err := d.pool.Query(ctx, `
		SELECT id, COALESCE(surname, ''), COALESCE(first_name, ''), COALESCE(birth_date, ''),
		       COALESCE(doc_number_enc, ''), COALESCE(nationality, '')
		FROM guest
		WHERE reservation_id = $1 AND archived_at IS NULL AND id != $2`, resID, excludeID)
	if err != nil {
		return false, err
	}
	defer rows.Close()
	keys, _ := secure.LoadDataKeys(d.getenv)
	at := d.now()
	incoming := ubyport.GuestIdentity{
		ID:          excludeID,
		Surname:     values.Surname,
		FirstName:   values.FirstName,
		BirthDate:   values.BirthDate,
		DocNumber:   values.DocNumber,
		Nationality: values.Nationality,
	}
	for rows.Next() {
		var other ubyport.GuestIdentity
		var docEnc string
		if err := rows.Scan(&other.ID, &other.Surname, &other.FirstName, &other.BirthDate, &docEnc, &other.Nationality); err != nil {
			return false, err
		}
		if docEnc != "" && keys != nil {
			if plain, derr := keys.DecryptField(docEnc, at); derr == nil {
				other.DocNumber = plain
			}
		}
		if ubyport.IsSamePerson(other, incoming) {
			return true, nil
		}
	}
	return false, rows.Err()
}

// renderGuestForm422 redraws the form the guest just submitted, with what they
// typed and the sentences saying what to fix — Python's 422 (guest.py:2530
// renders the form context again with values and issues), not a bare status.
func renderGuestForm422(w http.ResponseWriter, r *http.Request, d saveDeps, apt *Apartment, token, lang string, resID int64, existing *guestSaveRow, form, raw map[string]string, values validation.GuestRow, stayFrom, stayTo, sig string, issues []validation.Issue) {
	fd := formPageDeps{pool: d.pool, getenv: d.getenv, now: d.now}
	ctx := r.Context()
	res, ok := formPagesReservation(ctx, fd.pool, apt, resID, r)
	if !ok {
		w.WriteHeader(http.StatusUnprocessableEntity)
		_, _ = w.Write([]byte("validation"))
		return
	}
	var guest *formGuestRow
	if existing != nil {
		guest, _ = loadFormGuest(ctx, d.pool, existing.id, resID, d.getenv, d.now)
	}
	mode := "new"
	if guest != nil {
		mode = "edit"
	}
	view, err := buildFormView(ctx, fd, w, r, apt, token, res, guest, lang, mode)
	if err != nil {
		log.Printf("guest form 422: %v", err)
		http.Error(w, "server error", http.StatusInternalServerError)
		return
	}
	view.Values = guestTypedValues(values, raw, stayFrom, stayTo)
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
	view.Issues = issues
	view.LoadSignatureJS = true
	view.WrapClass = "g-checkin-page"
	writeFormPageStatus(w, r, view, http.StatusUnprocessableEntity)
}

// guestTypedValues is the form's own values after a refused submit: what
// validation.py cleaned, plus guest._keep_unreadable_text — a name or address in
// another alphabet cleans to nothing, and the guest must still see what they
// typed so they can correct it.
func guestTypedValues(values validation.GuestRow, raw map[string]string, stayFrom, stayTo string) map[string]string {
	out := map[string]string{
		"surname":     values.Surname,
		"first_name":  values.FirstName,
		"birth_date":  values.BirthDate,
		"nationality": values.Nationality,
		"doc_number":  values.DocNumber,
		"visa_number": values.VisaNumber,
		"res_street":  values.ResStreet,
		"res_city":    values.ResCity,
		"res_country": values.ResCountry,
		"purpose":     values.Purpose,
		"note":        values.Note,
		"stay_from":   stayFrom,
		"stay_to":     stayTo,
	}
	for _, field := range []string{"surname", "first_name", "res_street", "res_city"} {
		if out[field] != "" {
			continue
		}
		typed := strings.TrimSpace(raw[field])
		if typed == "" {
			continue
		}
		if runes := []rune(typed); len(runes) > 100 {
			typed = string(runes[:100])
		}
		out[field] = typed
	}
	return out
}

func parseDatePtr(s string) *time.Time {
	t, ok := validation.ParseISODate(s)
	if !ok {
		return nil
	}
	return &t
}

func guestFormSubmitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) error {
	_, err := ubyport.SubmitCompletedStay(ctx, pool, getenv, now, apartmentID, reservationID, nil)
	return err
}
