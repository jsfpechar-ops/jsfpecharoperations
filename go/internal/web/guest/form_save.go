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
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/scheduler"
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
func RegisterFormSave(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	d := saveDeps{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /l/{token}/{reservation_id}/save", wrap("POST /l/{token}/{reservation_id}/save", WithPOSTCSRF(getenv, now, guestFormSaveHandler(d))))
}

type saveDeps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
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
	stayFrom     string
	stayTo       string
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

func handleGuestFormSave(ctx context.Context, d saveDeps, w http.ResponseWriter, r *http.Request) error {
	if d.pool == nil {
		return errors.New("guest form save: nil pool")
	}
	if err := r.ParseForm(); err != nil {
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
	cfg, res, ok := reservationForGuest(ctx, d.pool, apt, resID, d.getenv)
	if !ok {
		guestUnavailable(w, r, lang, "stay_gone", http.StatusNotFound, token, resID)
		return nil
	}
	if throttleGuestPost(w, r, d, token, "guest_save", lang) {
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
	issues := guestSaveValidateIssues(form, cfg, res, values, raw, stayFrom, stayTo, sig, child, existing, legalToday(d.now))
	// guest.py:2518 — name the field that holds another alphabet, then word every
	// sentence for the guest. Both passes run before the refusal is tested, so a
	// translated sentence is what the page shows and what the log counts.
	issues = localizeIssues(nameLatinIssues(issues, lang), lang)
	if len(validation.ErrorsOnly(issues)) > 0 {
		renderGuestForm422(w, r, d, apt, token, lang, resID, existing, raw, values, stayFrom, stayTo, issues)
		return nil
	}
	nowS := utcStamp(d.now)
	payload := buildSavePayload(values, stayFrom, stayTo, sig, child, lang, cfg.noticeVersion, nowS, existing)
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
		partySize, _ := strconv.Atoi(strings.TrimSpace(form["party_size"]))
		savedID, err = insertGuestSaveRow(ctx, d, payload, resID, res, partySize)
		if err != nil {
			return err
		}
		if savedID == 0 {
			_ = guestFormSubmitStayIfComplete(ctx, d.pool, d.getenv, d.now, res.apartmentID, resID)
			WithLang(w, d.getenv, lang)
			http.Redirect(w, r, GuestLink(token, resID, LangQuery(lang, "")), http.StatusSeeOther)
			return nil
		}
	}
	if err := auditGuestFormSaved(ctx, d.pool, savedID, resID, cfg.ownerUserID, lang, d.now); err != nil {
		return err
	}
	_ = guestFormSubmitStayIfComplete(ctx, d.pool, d.getenv, d.now, res.apartmentID, resID)
	rememberOwnedGuestIDs(w, d.getenv, append(ownedGuestIDs(r, d.getenv), savedID))
	loc := GuestLink(token, resID, LangQuery(lang, ""))
	if existing == nil {
		loc = GuestLink(token, resID, "/new"+LangQuery(lang, ""))
	}
	WithLang(w, d.getenv, lang)
	http.Redirect(w, r, loc, http.StatusSeeOther)
	return nil
}

func guestSaveFormContract(form map[string]string) guestcontract.GuestForm {
	return guestcontract.GuestForm{
		Surname: form["surname"], FirstName: form["first_name"], BirthDate: form["birth_date"],
		Nationality: form["nationality"], DocNumber: form["doc_number"], VisaNumber: form["visa_number"],
		ResStreet: form["res_street"], ResCity: form["res_city"], ResCountry: form["res_country"],
		Purpose: form["purpose"], Note: form["note"], ParentDocNumber: form["parent_doc_number"],
		Signature: form["signature"], PartySize: form["party_size"], LegalAck: form["legal_ack"] != "",
		ChildSignRole: form["child_sign_role"], SignedBy: form["signed_by"],
	}
}

func guestSaveExpectedGuests(res guestResMeta) *int {
	exp := headcount.Expected(res.overrideGuests, res.declaredGuests, res.reducedGuests)
	if exp == nil {
		return nil
	}
	n := int(*exp)
	return &n
}

func guestSaveValidateIssues(form map[string]string, cfg guestFormCfg, res guestResMeta, values validation.GuestRow, raw map[string]string, stayFrom, stayTo, sig string, child bool, existing *guestSaveRow, today time.Time) []validation.Issue {
	if existing == nil {
		return guestcontract.CheckNewGuest(guestSaveFormContract(form), guestcontract.FormConfig{DefaultPurpose: cfg.defaultPurpose},
			guestcontract.Stay{DateFrom: res.dateFrom, DateTo: res.dateTo, ExpectedGuests: guestSaveExpectedGuests(res)}, today)
	}
	from, to := parseDate(stayFrom), parseDate(stayTo)
	issues := validation.ValidateGuestForm(values, &from, &to, today, raw)
	if si := validation.GuestFormSignatureIssue(sig, child); si != nil {
		issues = append(issues, *si)
	}
	if form["legal_ack"] == "" {
		issues = append(issues, validation.Issue{Field: "legal_ack", Message: "Please confirm that you have read the legal information.", Severity: "error"})
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

func buildSavePayload(v validation.GuestRow, stayFrom, stayTo, sig string, child bool, lang, noticeVer, now string, existing *guestSaveRow) map[string]any {
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
	if existing != nil && existing.submitState == "blocked" && strings.Contains(existing.lastErrors, "duplicate") {
		delete(p, "submit_state")
		delete(p, "last_errors")
	} else if guestCorrectionResetsAttempts(existing) {
		p["submit_attempts"] = int64(0)
	}
	return p
}

// guestCorrectionResetsAttempts mirrors reporting.guest_correction_resets_attempts.
func guestCorrectionResetsAttempts(existing *guestSaveRow) bool {
	if existing == nil {
		return false
	}
	switch existing.submitState {
	case "error", "blocked", "not_required":
		return true
	default:
		return false
	}
}

func loadGuestSaveRow(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, id, resID int64) (*guestSaveRow, error) {
	var g guestSaveRow
	var sigEnc string
	err := pool.QueryRow(ctx, `SELECT id, submit_state, COALESCE(restricted_at::text,''), COALESCE(signature_png,''),
		COALESCE(signature_png_enc,''), COALESCE(last_errors,''), COALESCE(stay_from,''), COALESCE(stay_to,'')
		FROM guest WHERE id = $1 AND reservation_id = $2`, id, resID).
		Scan(&g.id, &g.submitState, &g.restrictedAt, &g.signaturePNG, &sigEnc, &g.lastErrors, &g.stayFrom, &g.stayTo)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	plain, err := decryptGuestField(getenv, now, sigEnc, g.signaturePNG)
	if err != nil {
		return nil, err
	}
	g.signaturePNG = plain
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
	cutoff := float64(d.now().Unix()) - float64(ubyport.SubmissionClaimTTL)
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
		return false, nil
	}
	return id == existing.id, nil
}

func insertGuestSaveRow(ctx context.Context, d saveDeps, payload map[string]any, resID int64, res guestResMeta, partySize int) (int64, error) {
	tx, err := d.pool.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx) //nolint:errcheck
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext('reservation'), $1::int)`, resID); err != nil {
		return 0, err
	}
	var declared *int64
	if err := tx.QueryRow(ctx, `SELECT declared_guests, expected_guests_override, lead_reduced_guests FROM reservation WHERE id = $1`,
		resID).Scan(&declared, &res.overrideGuests, &res.reducedGuests); err != nil {
		return 0, err
	}
	res.declaredGuests = declared
	exp := headcount.Expected(res.overrideGuests, res.declaredGuests, res.reducedGuests)
	if exp == nil && partySize > 0 {
		code, _, err := headcount.ApplyDeclaredInTx(ctx, tx, resID, partySize, d.now())
		if err != nil {
			return 0, err
		}
		if code != "saved" {
			return 0, tx.Commit(ctx)
		}
		res.declaredGuests = ptrInt64(int64(partySize))
		exp = headcount.Expected(res.overrideGuests, res.declaredGuests, res.reducedGuests)
	}
	var live int
	if err := tx.QueryRow(ctx, `SELECT COUNT(*) FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`, resID).Scan(&live); err != nil {
		return 0, err
	}
	if exp != nil && live >= int(*exp) {
		return 0, tx.Commit(ctx)
	}
	var isFirst bool
	if err := tx.QueryRow(ctx, `SELECT NOT EXISTS (SELECT 1 FROM guest WHERE reservation_id = $1)`, resID).Scan(&isFirst); err != nil {
		return 0, err
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
		return 0, err
	}
	var id int64
	err = tx.QueryRow(ctx, `INSERT INTO guest (`+strings.Join(guestSaveInsertCols, ", ")+`)
		VALUES (`+guestSaveInsertPlaceholders()+`) RETURNING id`,
		guestSaveInsertArgs(enc)...).Scan(&id)
	if err != nil {
		return 0, err
	}
	return id, tx.Commit(ctx)
}

func encryptSaveFields(getenv func(string) string, payload map[string]any) (map[string]any, error) {
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		return nil, err
	}
	out := map[string]any{}
	for k, v := range payload {
		switch k {
		case "birth_date", "doc_number", "visa_number", "res_street", "res_city", "signature_png":
			if s, ok := v.(string); ok && s != "" {
				tok, err := keys.EncryptString(s)
				if err != nil {
					return nil, err
				}
				out[k+"_enc"] = tok
				continue
			}
			out[k+"_enc"] = nil
			continue
		}
		out[k] = v
	}
	return out, nil
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

func reservationForGuest(ctx context.Context, pool *pgxpool.Pool, apt *Apartment, resID int64, getenv func(string) string) (guestFormCfg, guestResMeta, bool) {
	if pool == nil || apt == nil || resID <= 0 {
		return guestFormCfg{}, guestResMeta{}, false
	}
	var cfg guestFormCfg
	var res guestResMeta
	var purpose string
	err := pool.QueryRow(ctx, `SELECT r.apartment_id, a.owner_user_id, r.date_from::text, r.date_to::text,
		r.declared_guests, r.expected_guests_override, r.lead_reduced_guests, COALESCE(a.default_purpose,'')
		FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE r.id = $1 AND r.apartment_id = $2 AND r.status = 'active' AND r.archived_at IS NULL
		  AND COALESCE(r.source,'') <> 'demo' AND a.permalink_token = $3`,
		resID, apt.ID, apt.PermalinkToken).Scan(
		&res.apartmentID, &cfg.ownerUserID, &res.dateFrom, &res.dateTo,
		&res.declaredGuests, &res.overrideGuests, &res.reducedGuests, &purpose)
	if err != nil {
		return guestFormCfg{}, guestResMeta{}, false
	}
	cfg.defaultPurpose = purpose
	if getenv != nil {
		cfg.noticeVersion = noticeVersion(getenv)
	}
	return cfg, res, true
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

// renderGuestForm422 redraws the form the guest just submitted, with what they
// typed and the sentences saying what to fix — Python's 422 (guest.py:2530
// renders the form context again with values and issues), not a bare status.
func renderGuestForm422(w http.ResponseWriter, r *http.Request, d saveDeps, apt *Apartment, token, lang string, resID int64, existing *guestSaveRow, raw map[string]string, values validation.GuestRow, stayFrom, stayTo string, issues []validation.Issue) {
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
	var mode string
	if err := pool.QueryRow(ctx, `SELECT COALESCE(automation_mode,'') FROM apartment WHERE id = $1`, apartmentID).Scan(&mode); err != nil {
		return err
	}
	dec := func(token string) (string, error) {
		if token == "" {
			return "", nil
		}
		k, err := secure.LoadDataKeys(getenv)
		if err != nil {
			return "", err
		}
		b, err := k.Decrypt(token, 0, now())
		return string(b), err
	}
	completed, err := ubyport.RefreshRegistrationCompletedAt(ctx, pool, reservationID, dec, now)
	if err != nil || completed == nil || mode != "immediate" {
		return err
	}
	_, err = scheduler.Enqueue(ctx, pool, "submit")
	return err
}
func ptrInt64(n int64) *int64 {
	return &n
}
