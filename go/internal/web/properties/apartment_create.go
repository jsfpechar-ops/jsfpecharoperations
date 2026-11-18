package properties

// POST /apartments (brief 1700b2): routes/admin.py apartment_create, with
// _apartment_payload, _property_operator_error, _create_address_errors,
// _refuse_apartment_create and _apply_police_defaults. A refusal draws the
// 1700a form again through RenderApartmentNew; a create writes the apartment
// row Python writes (App/scripts/go_apartment_create_golden.py records it) and
// redirects to the calendar step of the guided setup.
//
// The guest-pay block (stay_fee_guest_form) and unsupported numbers in an ID,
// the rate, the postcode or the variable symbol receive a 501.
//
// Python writes the row, the rate, the guest link, the audit row and the
// setup state one after another; here the row and its rate share one
// transaction, the rest follows in Python's order. Nothing routes here until
// the owner adds the path to UBYHOST_GO_PATHS.

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/text/cases"
	"golang.org/x/text/language"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validationi18n"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

//go:embed apartmentcreate/i18n.json
var apartmentCreateJSON []byte

// apartmentCreateStrings is this route's catalog (apartmentcreate/i18n_keys.txt,
// written by App/scripts/go_host_i18n.py).
var apartmentCreateStrings = hostweb.Load(apartmentCreateJSON)

// apartmentTextFields is admin.APARTMENT_TEXT_FIELDS.
var apartmentTextFields = []string{"internal_name", "city_en", "addr_okres", "addr_obec", "addr_obec_cast", "addr_street",
	"addr_house_no", "addr_orient_no", "addr_zip", "uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user",
	"guest_message", "notes"}

// apartmentCopyKeys is admin._COPY_PROPERTY_KEYS without the two entity ids.
var apartmentCopyKeys = []string{"automation_mode", "submit_after_hours", "default_purpose", "permalink_window_days",
	"permalink_reachback_days", "stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_authority_name",
	"stay_fee_authority_address", "stay_fee_authority_contact", "stay_fee_payee", "stay_fee_instruction",
	"stay_fee_council_account"}

// apartmentAddressFields is admin._ADDRESS_ONLY_FIELDS.
var apartmentAddressFields = []string{"addr_okres", "addr_obec", "addr_obec_cast", "addr_street", "addr_house_no",
	"addr_orient_no", "addr_zip"}

// apartmentFeeTexts are the optional fee texts of stay_fees.fee_form_values and their cut.
var apartmentFeeTexts = []struct {
	key   string
	limit int
}{{"stay_fee_authority_name", 200}, {"stay_fee_authority_address", 200}, {"stay_fee_authority_contact", 200},
	{"stay_fee_payee", 60}, {"stay_fee_instruction", 500}}

var apartmentDataboxRE = regexp.MustCompile(`^[a-z0-9]{7}package properties

// POST /apartments (brief 1700b2): routes/admin.py apartment_create, with
// _apartment_payload, _property_operator_error, _create_address_errors,
// _refuse_apartment_create and _apply_police_defaults. A refusal draws the
// 1700a form again through RenderApartmentNew; a create writes the apartment
// row Python writes (App/scripts/go_apartment_create_golden.py records it) and
// redirects to the calendar step of the guided setup.
//
// The guest-pay block (stay_fee_guest_form) and unsupported numbers in an ID,
// the rate, the postcode or the variable symbol receive a 501.
//
// Python writes the row, the rate, the guest link, the audit row and the
// setup state one after another; here the row and its rate share one
// transaction, the rest follows in Python's order. Nothing routes here until
// the owner adds the path to UBYHOST_GO_PATHS.

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/text/cases"
	"golang.org/x/text/language"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validationi18n"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

//go:embed apartmentcreate/i18n.json
var apartmentCreateJSON []byte

// apartmentCreateStrings is this route's catalog (apartmentcreate/i18n_keys.txt,
// written by App/scripts/go_host_i18n.py).
var apartmentCreateStrings = hostweb.Load(apartmentCreateJSON)

// apartmentTextFields is admin.APARTMENT_TEXT_FIELDS.
var apartmentTextFields = []string{"internal_name", "city_en", "addr_okres", "addr_obec", "addr_obec_cast", "addr_street",
	"addr_house_no", "addr_orient_no", "addr_zip", "uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user",
	"guest_message", "notes"}

// apartmentCopyKeys is admin._COPY_PROPERTY_KEYS without the two entity ids.
var apartmentCopyKeys = []string{"automation_mode", "submit_after_hours", "default_purpose", "permalink_window_days",
	"permalink_reachback_days", "stay_fee_rate_czk", "stay_fee_cadence", "stay_fee_authority_name",
	"stay_fee_authority_address", "stay_fee_authority_contact", "stay_fee_payee", "stay_fee_instruction",
	"stay_fee_council_account"}

// apartmentAddressFields is admin._ADDRESS_ONLY_FIELDS.
var apartmentAddressFields = []string{"addr_okres", "addr_obec", "addr_obec_cast", "addr_street", "addr_house_no",
	"addr_orient_no", "addr_zip"}

// apartmentFeeTexts are the optional fee texts of stay_fees.fee_form_values and their cut.
var apartmentFeeTexts = []struct {
	key   string
	limit int
}{{"stay_fee_authority_name", 200}, {"stay_fee_authority_address", 200}, {"stay_fee_authority_contact", 200},
	{"stay_fee_payee", 60}, {"stay_fee_instruction", 500}}

)

// apartmentNotPortedFields are form keys whose branch this port does not take.
var apartmentNotPortedFields = []string{"stay_fee_guest_form"}

// stayFeeRateEpoch is stay_fee_rate.EPOCH: a first rate applies from the beginning.
const stayFeeRateEpoch = "2000-01-01"

const (
	apartmentCreateEntitySQL = `SELECT COALESCE(archived_at, ''), COALESCE(contact_email, '') FROM legal_entity
  WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`
	apartmentCreateLiveEntitiesSQL = `SELECT count(*) FROM legal_entity WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL`
	apartmentCreateSourceSQL       = `SELECT COALESCE(internal_name, '') FROM apartment WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`
	apartmentCreateRateSQL         = `INSERT INTO stay_fee_rate (apartment_id, rate_czk, effective_from, created_at) VALUES ($1, $2, $3, $4)`
)

// RegisterApartmentCreate adds POST /apartments. It only builds the handler;
// the pool is first used inside a request.
func RegisterApartmentCreate(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &server{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /apartments", wrap("/apartments", s.apartmentCreate))
}

// apartmentFormInt is admin._form_int: nil for an empty or non-integer value.
// ok is false for a value this port does not judge (a non-ASCII character, or
// an integer past 64 bits).
func apartmentFormInt(r *http.Request, key string) (n *int64, ok bool) {
	raw := formStr(r, key)
	if raw == "" {
		return nil, true
	}
	for _, c := range raw {
		if c > unicode.MaxASCII {
			return nil, false
		}
	}
	if !apartmentNewIntRE.MatchString(raw) {
		return nil, true
	}
	v, err := strconv.ParseInt(strings.ReplaceAll(raw, "_", ""), 10, 64)
	if err != nil {
		return nil, false
	}
	return &v, true
}

// pyDigitUnsure reports a character Python's str.isdigit() may read as a digit
// where Go's unicode.IsDigit and the ASCII parsers do not agree.
func pyDigitUnsure(s string) bool {
	for _, c := range s {
		if c > unicode.MaxASCII && (unicode.IsDigit(c) || unicode.Is(unicode.No, c)) {
			return true
		}
	}
	return false
}

// firstRunes is s[:n] on a Python str.
func firstRunes(s string, n int) string {
	if r := []rune(s); len(r) > n {
		return string(r[:n])
	}
	return s
}

// guestCity is property_setup.guest_city: the English town name guests see.
func guestCity(obec string) string {
	town := strings.Join(strings.FieldsFunc(obec, func(r rune) bool { return pyStrip(string(r)) == "" }), " ")
	lower := strings.ToLower(town)
	if strings.HasPrefix(lower, "praha") {
		return "Prague"
	}
	if lower == "plzeň" {
		return "Pilsen"
	}
	return town
}

func orNull(v *int64) any {
	if v == nil {
		return nil
	}
	return *v
}

func int64Of(v *int64) int64 {
	if v == nil {
		return 0
	}
	return *v
}

// apartmentPayload is admin._apartment_payload: the columns to insert and the
// stripped text fields. ok is false for a value this port does not judge.
type apartmentPayload struct {
	cols              []column
	text              map[string]string
	legal, controller *int64
	feePosted         bool
	rate              int
	password          string // uby_ws_password, stripped; never echoed back
}

func newApartmentPayload(r *http.Request) (p apartmentPayload, ok bool) {
	for _, key := range []string{"addr_zip", "stay_fee_vs", "stay_fee_rate_czk"} {
		if pyDigitUnsure(formStr(r, key)) {
			return p, false
		}
	}
	ints := map[string]*int64{}
	for _, key := range []string{"legal_entity_id", "data_controller_entity_id", "submit_after_hours", "permalink_window_days",
		"permalink_reachback_days", "copy_from"} {
		if ints[key], ok = apartmentFormInt(r, key); !ok {
			return p, false
		}
	}
	p.text = map[string]string{}
	for _, key := range apartmentTextFields {
		p.text[key] = formStr(r, key)
	}
	p.text["guest_message"] = firstRunes(p.text["guest_message"], 1000)
	p.text["uby_mark"] = validation.Upper(p.text["uby_mark"])
	p.text["addr_zip"] = validation.NormaliseZip(p.text["addr_zip"])
	p.text["city_en"] = guestCity(p.text["addr_obec"])
	p.legal, p.controller = ints["legal_entity_id"], ints["data_controller_entity_id"]
	p.password = formStr(r, "uby_ws_password")
	// _automation_timing_values: a new property starts on Manual. form_str
	// reads a missing or empty value as its default (default_purpose too).
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
	window := int64(1)
	if d := int64Of(ints["permalink_window_days"]); d != 0 {
		window = d
	}
	policy := formStr(r, "passport_photo_policy")
	if policy != "required_foreign" {
		policy = "off"
	}
	ocr := 0
	if formStr(r, "ocr_scan") == "1" {
		ocr = 1
	}
	for _, key := range apartmentTextFields {
		p.cols = append(p.cols, column{key, p.text[key]})
	}
	p.cols = append(p.cols, column{"legal_entity_id", orNull(p.legal)}, column{"data_controller_entity_id", orNull(p.controller)},
		column{"automation_mode", mode}, column{"submit_after_hours", hours}, column{"permalink_window_days", window},
		column{"permalink_reachback_days", validation.NormaliseReachbackDays(ints["permalink_reachback_days"])},
		column{"passport_photo_policy", policy}, column{"ocr_scan", ocr})
	if p.feePosted = has(r, "stay_fee_rate_czk"); p.feePosted {
		p.rate = stayfee.ClampRate(formStr(r, "stay_fee_rate_czk"))
		vs := firstRunes(stayfee.VSOf(&stayfee.Apartment{StayFeeVS: formStr(r, "stay_fee_vs")}), 10)
		p.cols = append(p.cols, column{"stay_fee_rate_czk", p.rate}, column{"stay_fee_vs", orNil(vs)})
		if has(r, "stay_fee_cadence") {
			cadence := formStr(r, "stay_fee_cadence")
			if !slices.Contains(stayfee.Cadences, cadence) {
				cadence = "monthly"
			}
			p.cols = append(p.cols, column{"stay_fee_cadence", cadence})
		}
		for _, f := range apartmentFeeTexts {
			if has(r, f.key) {
				p.cols = append(p.cols, column{f.key, orNil(pyStrip(firstRunes(formStr(r, f.key), f.limit)))})
			}
		}
		if has(r, "stay_fee_authority_databox") {
			databox := cases.Lower(language.Und).String(formStr(r, "stay_fee_authority_databox"))
			if !apartmentDataboxRE.MatchString(databox) {
				databox = ""
			}
			p.cols = append(p.cols, column{"stay_fee_authority_databox", orNil(databox)})
		}
		// The council account (stay_fee_council_account or the account_* fields)
		// is read raw and dropped on create, as apartment_create pops it.
	}
	purpose := formStr(r, "default_purpose")
	if !truthy(r, "default_purpose") {
		purpose = "99" // validation.DEFAULT_PURPOSE
	}
	if !validation.IsPurposeCode(purpose) {
		purpose = "10"
	}
	p.cols = append(p.cols, column{"default_purpose", purpose}, column{"active", 1})
	return p, true
}

// liveEntity is _valid_property_operator: the id is one of the workspace's
// operators and not archived. email is its stripped contact_email.
func (s *server) liveEntity(ctx context.Context, id *int64, workspace int64) (live bool, email string, err error) {
	if id == nil || *id == 0 {
		return false, "", nil
	}
	var archived string
	err = s.pool.QueryRow(ctx, apartmentCreateEntitySQL, *id, workspace).Scan(&archived, &email)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, "", nil
	}
	if err != nil {
		return false, "", err
	}
	return archived == "", pyStrip(email), nil
}

// apartmentOperatorError is _property_operator_error: an i18n key or "", and
// the operator's contact e-mail for _apply_police_defaults.
func (s *server) apartmentOperatorError(ctx context.Context, r *http.Request, workspace int64, p apartmentPayload) (key, email string, err error) {
	live, email, err := s.liveEntity(ctx, p.legal, workspace)
	if err != nil {
		return "", "", err
	}
	if !live {
		n, err := s.count(ctx, apartmentCreateLiveEntitiesSQL, workspace)
		if err != nil {
			return "", "", err
		}
		if n == 0 {
			return "apartment.form.operator.add_first", "", nil
		}
		return "apartment.form.operator.required", "", nil
	}
	if formStr(r, "data_controller_entity_id") != "" {
		ok, _, err := s.liveEntity(ctx, p.controller, workspace)
		if err != nil {
			return "", "", err
		}
		if !ok {
			return "flash.error.no_such_controller", "", nil
		}
	}
	return "", email, nil
}

// apartmentAddressErrors is _create_address_errors, each message already in
// the host's language (the template's validation_message filter).
func apartmentAddressErrors(text map[string]string, lang string) map[string]string {
	errs, _ := apartmentAddressErrorList(text, lang)
	return errs
}

// apartmentAddressErrorList is apartmentAddressErrors plus the key order of
// Python's dict (the order the fields were refused in), which the save
// summary of a refused property save follows (brief 1702c2).
func apartmentAddressErrorList(text map[string]string, lang string) (map[string]string, []string) {
	errs := map[string]string{}
	var order []string
	for _, issue := range validation.ErrorsOnly(validation.ValidateApartment(text)) {
		if _, seen := errs[issue.Field]; !seen && slices.Contains(apartmentAddressFields, issue.Field) {
			errs[issue.Field] = issue.Message
			order = append(order, issue.Field)
		}
	}
	if _, seen := errs["addr_street"]; !seen && pyStrip(text["addr_street"]) == "" {
		errs["addr_street"] = "Street is required."
		order = append(order, "addr_street")
	}
	for field, msg := range errs {
		errs[field] = validationi18n.Localize(msg, lang)
	}
	return errs, order
}

// refuseApartmentCreate is _refuse_apartment_create: the form again with what
// the host typed, 400 when something was refused, 200 for operator_refresh.
func (s *server) refuseApartmentCreate(w http.ResponseWriter, r *http.Request, q *request, p apartmentPayload,
	operatorError string, nameError bool, addressErrors map[string]string) {
	ctx, ws := r.Context(), q.host.Workspace.ID
	form := ApartmentNewForm{Draft: map[string]string{}, Prefill: map[string]string{}, OperatorError: operatorError,
		NameError: nameError, AddressErrors: addressErrors}
	for _, key := range apartmentTextFields {
		form.Draft[key] = formStr(r, key)
	}
	form.DraftEntityID, form.SelectedEntityID = int64Of(p.legal), int64Of(p.legal)
	form.DraftControllerID, form.PrefillControllerID = int64Of(p.controller), int64Of(p.controller)
	for _, key := range apartmentCopyKeys {
		if has(r, key) {
			form.Prefill[key] = formStr(r, key)
		}
	}
	if copyID, _ := apartmentFormInt(r, "copy_from"); int64Of(copyID) != 0 {
		var name string
		err := s.pool.QueryRow(ctx, apartmentCreateSourceSQL, *copyID, ws).Scan(&name)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			fail(w, err)
			return
		}
		if err == nil {
			form.CopyFromID, form.CopiedFromName = *copyID, name
		}
	}
	var err error
	if form.Entities, form.Peers, err = loadApartmentNewChoices(ctx, s.pool, ws); err != nil {
		fail(w, err)
		return
	}
	if operatorError != "" || nameError || len(addressErrors) > 0 {
		form.Status = http.StatusBadRequest
	}
	if err := RenderApartmentNew(w, r, layout.Env{Pool: s.pool, Getenv: s.getenv, Now: q.at}, q.host, form); err != nil {
		fail(w, err)
	}
}

// apartmentCreate is POST /apartments (admin.py apartment_create).
func (s *server) apartmentCreate(w http.ResponseWriter, r *http.Request) {
	q, ok := s.enterNew(w, r)
	if !ok {
		return
	}
	for _, key := range apartmentNotPortedFields {
		if has(r, key) {
			notPorted(w, "the form field "+key)
			return
		}
	}
	p, ok := newApartmentPayload(r)
	if !ok {
		notPorted(w, "a non-ASCII digit or an integer past 64 bits in the form")
		return
	}
	if has(r, "operator_refresh") {
		// "Check again" after adding business details in another tab: nothing is written.
		s.refuseApartmentCreate(w, r, q, p, "", false, nil)
		return
	}
	ctx, ws := r.Context(), q.host.Workspace.ID
	nameError := pyStrip(p.text["internal_name"]) == ""
	operatorError, email, err := s.apartmentOperatorError(ctx, r, ws, p)
	if err != nil {
		fail(w, err)
		return
	}
	addressErrors := apartmentAddressErrors(p.text, q.lang)
	if nameError || operatorError != "" || len(addressErrors) > 0 {
		s.refuseApartmentCreate(w, r, q, p, operatorError, nameError, addressErrors)
		return
	}
	id, err := s.insertApartment(ctx, q, p, email)
	if err != nil {
		fail(w, err)
		return
	}
	if err := rotateSlug(ctx, s.pool, id, q.at); err != nil { // guest_slug.ensure: a new property has no slug yet
		fail(w, err)
		return
	}
	if err := s.audit(ctx, q, "apartment_created", fmt.Sprintf("id=%d", id)); err != nil {
		fail(w, err)
		return
	}
	if err := onboarding.Start(ctx, onboarding.PoolSettings(s.pool), id); err != nil {
		fail(w, err)
		return
	}
	msg := hostweb.Flash{Text: apartmentCreateStrings.T(q.lang, "flash.apartments.created", nil), Key: "flash.apartments.created"}
	q.back(w, r, fmt.Sprintf("/apartments/%d/setup/calendar", id), msg, hostweb.Flash{})
}

// applyPoliceDefaults is _apply_police_defaults: the abbreviation from the
// login, the contact from the operator's e-mail. The create and the settings
// save (brief 1702c) share it.
func applyPoliceDefaults(p apartmentPayload, operatorEmail string) []column {
	cols := p.cols
	if pyStrip(p.text["uby_mark"]) == "" {
		if mark := validation.MarkFromWSUser(p.text["uby_ws_user"]); mark != "" {
			cols = setColumn(cols, "uby_mark", mark)
		}
	}
	if pyStrip(p.text["uby_contact"]) == "" && operatorEmail != "" {
		cols = setColumn(cols, "uby_contact", firstRunes(operatorEmail, 50))
	}
	return cols
}

// insertApartment applies the police defaults and the create-only rules, then
// writes the row and, when the fee was posted, its first dated rate.
func (s *server) insertApartment(ctx context.Context, q *request, p apartmentPayload, operatorEmail string) (int64, error) {
	cols := applyPoliceDefaults(p, operatorEmail)
	if pyStrip(p.text["guest_message"]) == "" {
		cols = setColumn(cols, "guest_message", apartmentCreateStrings.T(q.lang, "apartment.form.guest_message.default", nil))
	}
	token, err := newPermalinkToken()
	if err != nil {
		return 0, err
	}
	pin, err := newPermalinkPIN()
	if err != nil {
		return 0, err
	}
	cols = append(cols, column{"permalink_token", token}, column{"permalink_pin", pin}, column{"created_at", stamp(q.at)},
		column{"owner_user_id", q.host.Workspace.ID})
	if int64Of(p.controller) == int64Of(p.legal) {
		cols = setColumn(cols, "data_controller_entity_id", nil)
	}
	var enc any
	if p.password != "" {
		keys, err := secure.LoadDataKeys(s.getenv)
		if err != nil {
			return 0, err
		}
		if enc, err = keys.EncryptString(p.password); err != nil {
			return 0, err
		}
	}
	cols = append(cols, column{"uby_ws_password_enc", enc})
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	sql, args := insertSQL("apartment", cols)
	var id int64
	if err := tx.QueryRow(ctx, sql, args...).Scan(&id); err != nil {
		return 0, err
	}
	// stay_fee_routes.record_rate_change(previous=0): a new property has no
	// history, so a rate above 0 gets one row from EPOCH and nothing else.
	if p.feePosted && p.rate > 0 {
		if _, err := tx.Exec(ctx, apartmentCreateRateSQL, id, p.rate, stayFeeRateEpoch, stamp(q.at)); err != nil {
			return 0, err
		}
	}
	return id, tx.Commit(ctx)
}
