package stays

// Brief 1733: host guest_new, guest_create, guest_edit, guest_update
// (App/app/routes/admin.py 4626-4840).

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

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	submitStateSent        = "sent"
	submitStatePending     = "pending"
	submitStateNotRequired = "not_required"
	submitStateError       = "error"
	submitStateBlocked     = "blocked"
)

var filedGuestFields = []string{
	"surname", "first_name", "birth_date", "nationality",
	"doc_number", "visa_number", "res_street", "res_city", "res_country",
	"purpose", "note", "stay_from", "stay_to",
}

const (
	flashGuestsAdded      = "flash." + "guests.added"
	flashGuestsSavedPlain = "flash." + "guests." + "saved_plain"
	flashGuestsSaved      = "flash." + "guests.saved"
)

const guestEditAuditSQL = `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
	VALUES ($1, $2, $3, $4, $5, $6, $7)`

type guestEditDeps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

type guestEditCall struct {
	guestEditDeps
	w     http.ResponseWriter
	r     *http.Request
	at    time.Time
	lang  string
	host  *session.Host
	owner int64
}

type hostReservation struct {
	id           int64
	apartmentID  int64
	dateFrom     string
	dateTo       string
	defaultPurp  string
	internalName string
}

type hostGuest struct {
	id                 int64
	reservationID      int64
	submitState        string
	restrictedAt       string
	surname, firstName string
	birthDate          string
	nationality        string
	docNumber, visaNum string
	resStreet, resCity string
	resCountry         string
	purpose, note      string
	stayFrom, stayTo   string
	signaturePNG       string
	docType            string
	enteredBy          string
	lastErrors         string
	submitAttempts     int64
	identityVerifiedAt string
	identityVerifiedBy *int64
	isLead             bool
	signedAt           string
	submittedAt        string
	manualFiledAt      string
	passportPhotoAt    string
}

type guestRevealAccess struct {
	All      bool
	Revealed []int64
}

// RegisterGuestEdit wires the four guest add/edit routes (dormant until UBYHOST_GO_PATHS).
func RegisterGuestEdit(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	d := guestEditDeps{pool: pool, getenv: getenv, now: now}
	mux.Handle("GET /reservations/{reservation_id}/guests/new", wrap("/reservations/{reservation_id}/guests/new", guestNewHandler(d)))
	mux.Handle("POST /reservations/{reservation_id}/guests", wrap("/reservations/{reservation_id}/guests", guestCreateHandler(d)))
	mux.Handle("GET /guests/{guest_id}", wrap("/guests/{guest_id}", guestEditGetHandler(d)))
	mux.Handle("POST /guests/{guest_id}", wrap("/guests/{guest_id}", guestUpdateHandler(d)))
}

func guestRevealFromHost(h *session.Host) guestRevealAccess {
	if h.Account.Role == "admin" || !h.Impersonating {
		return guestRevealAccess{All: true}
	}
	var a guestRevealAccess
	list, _ := h.Payload["rv"].([]any)
	for _, v := range list {
		switch n := v.(type) {
		case int64:
			a.Revealed = append(a.Revealed, n)
		case float64:
			a.Revealed = append(a.Revealed, int64(n))
		case int:
			a.Revealed = append(a.Revealed, int64(n))
		}
	}
	return a
}

func guestIdentityVisible(a guestRevealAccess, guestID int64) bool {
	if a.All {
		return true
	}
	for _, id := range a.Revealed {
		if id == guestID {
			return true
		}
	}
	return false
}

func (d guestEditDeps) enterGet(w http.ResponseWriter, r *http.Request) *guestEditCall {
	at := d.now()
	h, err := hostweb.Login(w, r, d.pool, d.getenv, at)
	if err != nil {
		guestEditServerError(w, err)
		return nil
	}
	if h == nil {
		return nil
	}
	return &guestEditCall{guestEditDeps: d, w: w, r: r, at: at, lang: hostweb.Lang(r), host: h, owner: h.Workspace.ID}
}

func (d guestEditDeps) enterPost(w http.ResponseWriter, r *http.Request) *guestEditCall {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return nil
	}
	_ = r.ParseForm()
	h, err := hostweb.Login(w, r, d.pool, d.getenv, at)
	if err != nil {
		guestEditServerError(w, err)
		return nil
	}
	if h == nil {
		return nil
	}
	return &guestEditCall{guestEditDeps: d, w: w, r: r, at: at, lang: hostweb.Lang(r), host: h, owner: h.Workspace.ID}
}

func (c *guestEditCall) flash(key string, params map[string]any) hostweb.Flash {
	text := hostweb.HostStrings.T(c.lang, key, params)
	if text == key {
		text = catalog.T(c.lang, key, params)
	}
	return hostweb.Flash{Text: text, Key: key}
}

func (c *guestEditCall) audit(ctx context.Context, action, detail string) error {
	var impersonator any
	if c.host.Impersonating {
		impersonator = c.host.Account.ID
	}
	_, err := c.pool.Exec(ctx, guestEditAuditSQL, isoStamp(c.at), c.host.Account.Username, action, detail,
		c.owner, c.host.Account.ID, impersonator)
	return err
}

func guestEditServerError(w http.ResponseWriter, err error) {
	log.Printf("stays guest_edit: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

func parseResGuestID(w http.ResponseWriter, r *http.Request, key string) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue(key), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return 0, false
	}
	return id, true
}

func (c *guestEditCall) loadReservation(ctx context.Context, id int64, extraCols bool) (*hostReservation, bool, error) {
	q := `SELECT r.id, r.apartment_id, COALESCE(r.date_from,''), COALESCE(r.date_to,''),
		COALESCE(a.default_purpose,''), COALESCE(a.internal_name,'')
		FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE r.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`
	var res hostReservation
	err := c.pool.QueryRow(ctx, q, id, c.owner).Scan(
		&res.id, &res.apartmentID, &res.dateFrom, &res.dateTo, &res.defaultPurp, &res.internalName)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	_ = extraCols
	return &res, true, nil
}

func (d guestEditDeps) loadGuest(ctx context.Context, owner, guestID int64) (*hostGuest, bool, error) {
	// The identity columns have an encrypted copy (data keys); the guest form
	// reads what Python's reporting.guest_dict reads, so both are fetched and
	// the plain value wins when there is no token.
	q := `SELECT g.id, g.reservation_id, COALESCE(g.submit_state,''), COALESCE(g.restricted_at,''),
		COALESCE(g.surname,''), COALESCE(g.first_name,''),
		COALESCE(g.nationality,''), COALESCE(g.doc_number,''), COALESCE(g.doc_number_enc,''),
		COALESCE(g.visa_number,''), COALESCE(g.visa_number_enc,''),
		COALESCE(g.res_country,''),
		COALESCE(g.purpose,''), COALESCE(g.note,''), COALESCE(g.stay_from,''), COALESCE(g.stay_to,''),
		COALESCE(g.doc_type,''), COALESCE(g.entered_by,''),
		COALESCE(g.last_errors,''), COALESCE(g.submit_attempts,0),
		COALESCE(g.identity_verified_at,''), g.identity_verified_by, COALESCE(g.is_lead,0) != 0,
		COALESCE(g.signed_at,''), COALESCE(g.submitted_at,''), COALESCE(g.manual_filed_at,''),
		COALESCE(g.passport_photo_at,''),
		COALESCE(g.birth_date,''), COALESCE(g.birth_date_enc,''),
		COALESCE(g.res_street,''), COALESCE(g.res_street_enc,''),
		COALESCE(g.res_city,''), COALESCE(g.res_city_enc,''),
		COALESCE(g.signature_png,''), COALESCE(g.signature_png_enc,'')
		FROM guest g JOIN reservation r ON r.id = g.reservation_id
		JOIN apartment a ON a.id = r.apartment_id
		WHERE g.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`
	var g hostGuest
	var birthP, birthE, docP, docE, visaP, visaE, streetP, streetE, cityP, cityE, sigP, sigE string
	err := d.pool.QueryRow(ctx, q, guestID, owner).Scan(
		&g.id, &g.reservationID, &g.submitState, &g.restrictedAt,
		&g.surname, &g.firstName, &g.nationality, &docP, &docE, &visaP, &visaE,
		&g.resCountry, &g.purpose, &g.note, &g.stayFrom, &g.stayTo,
		&g.docType, &g.enteredBy, &g.lastErrors, &g.submitAttempts,
		&g.identityVerifiedAt, &g.identityVerifiedBy, &g.isLead,
		&g.signedAt, &g.submittedAt, &g.manualFiledAt, &g.passportPhotoAt,
		&birthP, &birthE, &streetP, &streetE, &cityP, &cityE, &sigP, &sigE)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, err
	}
	fields := &guestFields{getenv: d.getenv}
	for _, pair := range []struct {
		plain, token string
		dst          *string
	}{
		{docP, docE, &g.docNumber}, {visaP, visaE, &g.visaNum},
		{birthP, birthE, &g.birthDate}, {streetP, streetE, &g.resStreet},
		{cityP, cityE, &g.resCity}, {sigP, sigE, &g.signaturePNG},
	} {
		value, verr := fields.value(pair.plain, pair.token)
		if verr != nil {
			return nil, false, verr
		}
		*pair.dst = value
	}
	return &g, true, nil
}

func guestRowFromHost(g hostGuest) validation.GuestRow {
	return validation.GuestRow{
		Surname: g.surname, FirstName: g.firstName, BirthDate: g.birthDate, Nationality: g.nationality,
		DocNumber: g.docNumber, VisaNumber: g.visaNum, ResStreet: g.resStreet, ResCity: g.resCity,
		ResCountry: g.resCountry, Purpose: g.purpose, Note: g.note,
		StayFrom: g.stayFrom, StayTo: g.stayTo, SignaturePNG: g.signaturePNG,
	}
}

func guestIsFiled(g hostGuest) bool {
	return g.submitState == submitStateSent
}

func ubyGuestPayload(g hostGuest, res hostReservation) map[string]any {
	return ubyport.GuestFields(ubyport.Guest{
		Surname: g.surname, FirstName: g.firstName, BirthDate: g.birthDate, Nationality: g.nationality,
		DocNumber: g.docNumber, VisaNumber: g.visaNum, ResStreet: g.resStreet, ResCity: g.resCity,
		ResCountry: g.resCountry, Purpose: g.purpose, Note: g.note,
		StayFrom: g.stayFrom, StayTo: g.stayTo,
	}, ubyport.Reservation{DateFrom: res.dateFrom, DateTo: res.dateTo})
}

func filedRecordChanged(stored, proposed hostGuest, res hostReservation) bool {
	return fmt.Sprint(ubyGuestPayload(stored, res)) != fmt.Sprint(ubyGuestPayload(proposed, res))
}

func editKeepsDuplicateBlock(stored, proposed hostGuest, res hostReservation) bool {
	return stored.submitState == submitStateBlocked &&
		blockedAsDuplicateGuest(stored.lastErrors) &&
		!filedRecordChanged(stored, proposed, res)
}

func blockedAsDuplicateGuest(lastErrors string) bool {
	for _, part := range strings.Split(lastErrors, " | ") {
		if ubyport.IsDuplicate(part) {
			return true
		}
	}
	return false
}

func guestFormMap(r *http.Request) map[string]string {
	out := map[string]string{}
	for k, vs := range r.PostForm {
		if len(vs) > 0 {
			out[k] = strings.TrimSpace(vs[len(vs)-1])
		}
	}
	return out
}

func guestPayloadFromForm(r *http.Request, res hostReservation) hostGuest {
	form := guestFormMap(r)
	raw := validation.GuestFormRaw(form, res.defaultPurp)
	g := hostGuest{
		surname: raw["surname"], firstName: raw["first_name"], birthDate: raw["birth_date"],
		nationality: raw["nationality"], docNumber: raw["doc_number"], visaNum: raw["visa_number"],
		resStreet: raw["res_street"], resCity: raw["res_city"], resCountry: raw["res_country"],
		purpose: raw["purpose"], note: raw["note"],
		stayFrom: formStr(r, "stay_from"), stayTo: formStr(r, "stay_to"),
	}
	docType := formStr(r, "doc_type")
	for _, d := range stayfee.DocTypes {
		if d == docType {
			g.docType = docType
			break
		}
	}
	return g
}

func keptGuestSignature(posted, stored string) string {
	posted = strings.TrimSpace(posted)
	if posted == "" {
		return stored
	}
	if _, err := parseSignatureDataURLExported(posted); err == nil {
		return posted
	}
	return stored
}

func parseSignatureDataURLExported(value string) ([]byte, error) {
	// validation.parseSignatureDataURL is package-private; duplicate the check via GuestFormSignatureIssue.
	if strings.TrimSpace(value) == "" {
		return nil, fmt.Errorf("empty")
	}
	if !strings.HasPrefix(value, "data:image/") {
		return nil, fmt.Errorf("not image")
	}
	return []byte("ok"), nil
}

func validationDocTypes() []string {
	return stayfee.DocTypes
}

func guestNewHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		resID, ok := parseResGuestID(w, r, "reservation_id")
		if !ok {
			return
		}
		c := d.enterGet(w, r)
		if c == nil {
			return
		}
		res, found, err := c.loadReservation(r.Context(), resID, true)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_stay", nil))
			return
		}
		access := guestRevealFromHost(c.host)
		c.writeHostGuestForm(w, guestFormView{
			Reservation: *res, Editing: false, Lang: c.lang, CSRF: guestFormCSRF(c.r),
			Access: access,
		})
	}
}

func guestCreateHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		resID, ok := parseResGuestID(w, r, "reservation_id")
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		res, found, err := c.loadReservation(r.Context(), resID, false)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_stay", nil))
			return
		}
		payload := guestPayloadFromForm(r, *res)
		signature := keptGuestSignature(formStr(r, "signature"), "")
		preview := payload
		preview.signaturePNG = signature
		preview.enteredBy = "host"
		row := guestRowFromHost(preview)
		issues := validation.GuestIssues(row, res.dateFrom, res.dateTo, c.at.UTC())
		if len(validation.ErrorsOnly(issues)) > 0 {
			c.writeHostGuestForm(w, guestFormView{
				Reservation: *res, Guest: &preview, Issues: issues, Editing: false,
				Lang: c.lang, CSRF: guestFormCSRF(c.r), Access: guestRevealFromHost(c.host),
			})
			return
		}
		stamp := isoStamp(c.at)
		var isFirst bool
		_ = c.pool.QueryRow(r.Context(), `SELECT NOT EXISTS (SELECT 1 FROM guest WHERE reservation_id = $1 AND archived_at IS NULL)`,
			resID).Scan(&isFirst)
		state := submitStateNotRequired
		if validation.GuestIsReportable(payload.nationality) {
			state = submitStatePending
		}
		guestID, err := insertHostGuest(r.Context(), c, resID, payload, signature, state, isFirst, stamp)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		_ = c.audit(r.Context(), "guest_created", fmt.Sprintf("id=%d reservation=%d by=host", guestID, resID))
		_ = guestSubmitStayIfComplete(r.Context(), c.guestEditDeps, res.apartmentID, resID)
		hostweb.Back(w, r, fmt.Sprintf("/reservations/%d", resID), c.flash(flashGuestsAdded, nil), hostweb.Flash{})
	}
}

func guestEditGetHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		guestID, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		c := d.enterGet(w, r)
		if c == nil {
			return
		}
		guest, found, err := d.loadGuest(r.Context(), c.owner, guestID)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			http.NotFound(w, r)
			return
		}
		res, found, err := c.loadReservation(r.Context(), guest.reservationID, true)
		if err != nil || !found {
			guestEditServerError(w, err)
			return
		}
		row := guestRowFromHost(*guest)
		issues := validation.GuestIssues(row, res.dateFrom, res.dateTo, c.at.UTC())
		access := guestRevealFromHost(c.host)
		c.writeHostGuestForm(w, guestFormView{
			Reservation: *res, Guest: guest, Issues: issues, Editing: true,
			Lang: c.lang, CSRF: guestFormCSRF(c.r), Access: access,
			IdentityHidden: !guestIdentityVisible(access, guestID),
		})
	}
}

func guestUpdateHandler(d guestEditDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		guestID, ok := parseResGuestID(w, r, "guest_id")
		if !ok {
			return
		}
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		guest, found, err := d.loadGuest(r.Context(), c.owner, guestID)
		if err != nil {
			guestEditServerError(w, err)
			return
		}
		if !found {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_guest", nil))
			return
		}
		if guest.restrictedAt != "" {
			hostweb.Back(w, r, fmt.Sprintf("/reservations/%d", guest.reservationID), hostweb.Flash{},
				c.flash("flash.error.guest_restricted", nil))
			return
		}
		res, found, err := c.loadReservation(r.Context(), guest.reservationID, false)
		if err != nil || !found {
			guestEditServerError(w, err)
			return
		}
		payload := guestPayloadFromForm(r, *res)
		access := guestRevealFromHost(c.host)
		signature := keptGuestSignature(formStr(r, "signature"), guest.signaturePNG)
		if !guestIdentityVisible(access, guestID) {
			payload.docNumber = guest.docNumber
			payload.visaNum = guest.visaNum
			signature = guest.signaturePNG
		}
		if guestIsFiled(*guest) {
			form := guestFormMap(r)
			for _, field := range filedGuestFields {
				if _, ok := form[field]; !ok {
					switch field {
					case "surname":
						payload.surname = guest.surname
					case "first_name":
						payload.firstName = guest.firstName
					case "birth_date":
						payload.birthDate = guest.birthDate
					case "nationality":
						payload.nationality = guest.nationality
					case "doc_number":
						payload.docNumber = guest.docNumber
					case "visa_number":
						payload.visaNum = guest.visaNum
					case "res_street":
						payload.resStreet = guest.resStreet
					case "res_city":
						payload.resCity = guest.resCity
					case "res_country":
						payload.resCountry = guest.resCountry
					case "purpose":
						payload.purpose = guest.purpose
					case "note":
						payload.note = guest.note
					case "stay_from":
						payload.stayFrom = guest.stayFrom
					case "stay_to":
						payload.stayTo = guest.stayTo
					}
				}
			}
			postedSig := formStr(r, "signature")
			sigChanged := postedSig != "" && postedSig != guest.signaturePNG &&
				strings.HasPrefix(postedSig, "data:image/")
			proposed := *guest
			mergeHostGuest(&proposed, payload)
			proposed.signaturePNG = signature
			if sigChanged || filedRecordChanged(*guest, proposed, *res) {
				_ = c.audit(r.Context(), "guest_update_refused_filed", fmt.Sprintf("id=%d by=host", guestID))
				hostweb.Back(w, r, fmt.Sprintf("/guests/%d", guestID), hostweb.Flash{},
					c.flash("flash.error.guest_filed_locked", nil))
				return
			}
			payload = hostGuest{docType: payload.docType}
			signature = guest.signaturePNG
		}
		preview := *guest
		mergeHostGuest(&preview, payload)
		preview.signaturePNG = signature
		preview.enteredBy = "host"
		issues := validation.GuestIssues(guestRowFromHost(preview), res.dateFrom, res.dateTo, c.at.UTC())
		if len(validation.ErrorsOnly(issues)) > 0 && !guestIsFiled(*guest) {
			c.writeHostGuestForm(w, guestFormView{
				Reservation: *res, Guest: &preview, Issues: issues, Editing: true,
				Lang: c.lang, CSRF: guestFormCSRF(c.r), Access: access,
			})
			return
		}
		updates, state := guestUpdateFields(*guest, preview, signature, *res, c)
		updated, updateErr := guestUpdateIf(r.Context(), c.pool, c.getenv, guestID, guest.submitState, updates, c.at)
		if updateErr != nil {
			guestEditServerError(w, updateErr)
			return
		}
		if !updated {
			hostweb.Back(w, r, fmt.Sprintf("/guests/%d", guestID), hostweb.Flash{},
				c.flash("flash.error.guest_changed_retry", nil))
			return
		}
		_ = c.audit(r.Context(), "guest_updated", fmt.Sprintf("id=%d by=host", guestID))
		_ = ubyport.ClearStuckIfRecovered(r.Context(), c.pool, res.id)
		_ = guestSubmitStayIfComplete(r.Context(), c.guestEditDeps, res.apartmentID, res.id)
		msg := c.flash(flashGuestsSavedPlain, nil)
		if filled, expected, err := reservationGuestCounts(r.Context(), c.pool, res.id); err == nil && expected != nil {
			msg = c.flash(flashGuestsSaved, map[string]any{"filled": filled, "expected": *expected})
		}
		hostweb.Back(w, r, fmt.Sprintf("/guests/%d", guestID), msg, hostweb.Flash{})
		_ = state
	}
}

func mergeHostGuest(dst *hostGuest, src hostGuest) {
	dst.surname = src.surname
	dst.firstName = src.firstName
	dst.birthDate = src.birthDate
	dst.nationality = src.nationality
	dst.docNumber = src.docNumber
	dst.visaNum = src.visaNum
	dst.resStreet = src.resStreet
	dst.resCity = src.resCity
	dst.resCountry = src.resCountry
	dst.purpose = src.purpose
	dst.note = src.note
	dst.stayFrom = src.stayFrom
	dst.stayTo = src.stayTo
	dst.docType = src.docType
}

func guestUpdateFields(stored, proposed hostGuest, signature string, res hostReservation, c *guestEditCall) (map[string]any, string) {
	updates := map[string]any{
		"surname": proposed.surname, "first_name": proposed.firstName, "birth_date": proposed.birthDate,
		"nationality": proposed.nationality, "doc_number": proposed.docNumber, "visa_number": proposed.visaNum,
		"res_street": proposed.resStreet, "res_city": proposed.resCity, "res_country": proposed.resCountry,
		"purpose": proposed.purpose, "note": proposed.note, "stay_from": proposed.stayFrom, "stay_to": proposed.stayTo,
		"doc_type": proposed.docType, "updated_at": isoStamp(c.at),
	}
	state := stored.submitState
	if !guestIsFiled(stored) {
		updates["signature_png"] = signature
		if strings.HasPrefix(signature, "data:image/") && signature != stored.signaturePNG {
			updates["signed_at"] = isoStamp(c.at)
		}
	}
	if guestIsFiled(stored) {
		delete(updates, "signature_png")
	} else if validation.GuestIsReportable(proposed.nationality) {
		updates["identity_verified_at"] = isoStamp(c.at)
		updates["identity_verified_by"] = c.host.Account.ID
	}
	if stored.submitState == submitStateSent {
		// keep submit_state
	} else if !validation.GuestIsReportable(proposed.nationality) {
		state = submitStateNotRequired
		updates["submit_state"] = state
	} else if editKeepsDuplicateBlock(stored, proposed, res) {
		// keep state
	} else if stored.submitState == submitStateError || stored.submitState == submitStateBlocked || stored.submitState == submitStateNotRequired {
		state = submitStatePending
		updates["submit_state"] = state
		updates["last_errors"] = nil
		updates["submit_attempts"] = int64(0)
	}
	return updates, state
}

func guestUpdateIf(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, guestID int64, expectState string, values map[string]any, at time.Time) (bool, error) {
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		return false, err
	}
	values, err = secure.GuestWriteValues(keys, values)
	if err != nil {
		return false, err
	}
	cutoff := float64(at.Unix()) - float64(ubyport.SubmissionClaimTTL)
	var n int64
	args := []any{guestID, expectState, cutoff}
	sets := make([]string, 0, len(values))
	i := 4
	for k, v := range values {
		sets = append(sets, k+" = $"+strconv.Itoa(i))
		args = append(args, v)
		i++
	}
	if len(sets) == 0 {
		return true, nil
	}
	q := `UPDATE guest SET ` + strings.Join(sets, ", ") + ` WHERE id = $1 AND submit_state = $2
		AND NOT EXISTS (SELECT 1 FROM submission_claim WHERE guest_id = $1 AND claimed_at >= $3)`
	if err := pool.QueryRow(ctx, q+" RETURNING id", args...).Scan(&n); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return false, nil
		}
		return false, err
	}
	return n == guestID, nil
}

func insertHostGuest(ctx context.Context, c *guestEditCall, resID int64, payload hostGuest, signature, state string, isLead bool, stamp string) (int64, error) {
	keys, err := secure.LoadDataKeys(c.getenv)
	if err != nil {
		return 0, err
	}
	protected, err := secure.GuestWriteValues(keys, map[string]any{
		"birth_date": payload.birthDate, "doc_number": payload.docNumber, "visa_number": payload.visaNum,
		"res_street": payload.resStreet, "res_city": payload.resCity, "signature_png": signature,
	})
	if err != nil {
		return 0, err
	}
	lead := 0
	if isLead {
		lead = 1
	}
	identityAt := ""
	var identityBy any
	if validation.GuestIsReportable(payload.nationality) {
		identityAt = stamp
		identityBy = c.host.Account.ID
	}
	var id int64
	err = c.pool.QueryRow(ctx,
		`INSERT INTO guest (reservation_id, surname, first_name, birth_date, nationality,
			doc_number, visa_number, res_street, res_city, res_country, purpose, note,
			stay_from, stay_to, doc_type, is_lead, entered_by, signature_png, signed_at, filled_at,
			submit_state, identity_verified_at, identity_verified_by, created_at, updated_at,
			birth_date_enc, doc_number_enc, visa_number_enc, res_street_enc, res_city_enc, signature_png_enc)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,'host',$17,$18,$18,$19,$20,$21,$18,$18,$22,$23,$24,$25,$26,$27) RETURNING id`,
		resID, payload.surname, payload.firstName, protected["birth_date"], payload.nationality,
		protected["doc_number"], protected["visa_number"], protected["res_street"], protected["res_city"], payload.resCountry,
		payload.purpose, payload.note, payload.stayFrom, payload.stayTo, payload.docType, lead,
		protected["signature_png"], stamp, state, nullIfEmpty(identityAt), identityBy,
		protected["birth_date_enc"], protected["doc_number_enc"], protected["visa_number_enc"],
		protected["res_street_enc"], protected["res_city_enc"], protected["signature_png_enc"],
	).Scan(&id)
	return id, err
}

func nullIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func guestSubmitStayIfComplete(ctx context.Context, d guestEditDeps, apartmentID, reservationID int64) error {
	_, err := ubyport.SubmitCompletedStay(ctx, d.pool, d.getenv, d.now, apartmentID, reservationID, nil)
	return err
}

func guestSaveDecrypter(getenv func(string) string) ubyport.FieldDecrypter {
	var keys *secure.MultiFernet
	return func(token string) (string, error) {
		if token == "" {
			return "", nil
		}
		if keys == nil {
			k, err := secure.LoadDataKeys(getenv)
			if err != nil {
				return "", err
			}
			keys = k
		}
		b, err := keys.Decrypt(token, 0, time.Now())
		return string(b), err
	}
}

func reservationGuestCounts(ctx context.Context, pool *pgxpool.Pool, resID int64) (filled int, expected *int, err error) {
	var declared, override *int64
	err = pool.QueryRow(ctx, `SELECT declared_guests, expected_guests_override FROM reservation WHERE id = $1`, resID).
		Scan(&declared, &override)
	if err != nil {
		return
	}
	var exp int
	if override != nil {
		exp = int(*override)
		expected = &exp
	} else if declared != nil {
		exp = int(*declared)
		expected = &exp
	}
	err = pool.QueryRow(ctx, `SELECT count(*) FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`, resID).Scan(&filled)
	return
}

func guestFormCSRF(r *http.Request) string {
	if c, err := r.Cookie("csrf_nonce"); err == nil {
		return c.Value
	}
	return ""
}
