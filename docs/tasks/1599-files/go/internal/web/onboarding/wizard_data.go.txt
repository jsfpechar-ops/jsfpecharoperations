package onboarding

// wizard_data.go: _wizard_context of App/app/routes/onboarding_wizard.py
// (lines 61-185) and the admin.py helpers it calls (_ensure_apartment_pin,
// _apartment_issues and _readiness for the report list, _setup_facts,
// _setup_state, _setup_guide_bundle, the "lock offered" half of
// _door_code_context), plus workflow.next_stay_window, workflow.steps and
// demo.demo_stay_for. Brief 1599. The writes are the ones Python does while
// it builds the page: a missing PIN is backfilled, a legacy guide of a
// property that is set up is finished, and the finish page spends the
// celebration once.

import (
	"context"
	"crypto/rand"
	"errors"
	"math/big"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata" // Europe/Prague must load on a slim image

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// wizardApt is the apartment row the wizard reads (access.apartment: the
// workspace's row, archived or not). A NULL text column is "".
type wizardApt struct {
	ID                                                         int64
	OwnerUserID                                                *int64
	LegalEntityID, DataControllerEntityID                      *int64
	InternalName, CityEN, DefaultPurpose                       string
	AddrOkres, AddrObec, AddrObecCast, AddrStreet, AddrHouseNo string
	AddrOrientNo, AddrZip                                      string
	UbyIDUB, UbyMark, UbyName, UbyContact, UbyWSUser           string
	UbyWSPasswordEnc                                           string
	AutomationMode                                             string
	SubmitAfterHours, PermalinkWindowDays, StayFeeRateCZK      int64
	Active                                                     int64
	ArchivedAt, PermalinkToken, PermalinkPIN, LockProvider     string
	CheckinHour, CheckoutHour                                  *int64
}

const wizardAptSQL = `SELECT id, owner_user_id, legal_entity_id, data_controller_entity_id,
       internal_name, COALESCE(city_en, ''), default_purpose,
       COALESCE(addr_okres, ''), COALESCE(addr_obec, ''), COALESCE(addr_obec_cast, ''),
       COALESCE(addr_street, ''), COALESCE(addr_house_no, ''), COALESCE(addr_orient_no, ''),
       COALESCE(addr_zip, ''), COALESCE(uby_idub, ''), COALESCE(uby_mark, ''), COALESCE(uby_name, ''),
       COALESCE(uby_contact, ''), COALESCE(uby_ws_user, ''), COALESCE(uby_ws_password_enc, ''),
       automation_mode, submit_after_hours, permalink_window_days, stay_fee_rate_czk, active,
       COALESCE(archived_at, ''), COALESCE(permalink_token, ''), COALESCE(permalink_pin, ''),
       COALESCE(lock_provider, ''), checkin_hour, checkout_hour
  FROM apartment WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`

// wizardLoadApt is access.apartment(request, id): nil when it is not the workspace's.
func (s *wizardServer) wizardLoadApt(ctx context.Context, owner, id int64) (*wizardApt, error) {
	var a wizardApt
	err := s.pool.QueryRow(ctx, wizardAptSQL, id, owner).Scan(&a.ID, &a.OwnerUserID, &a.LegalEntityID,
		&a.DataControllerEntityID, &a.InternalName, &a.CityEN, &a.DefaultPurpose,
		&a.AddrOkres, &a.AddrObec, &a.AddrObecCast, &a.AddrStreet, &a.AddrHouseNo, &a.AddrOrientNo,
		&a.AddrZip, &a.UbyIDUB, &a.UbyMark, &a.UbyName, &a.UbyContact, &a.UbyWSUser, &a.UbyWSPasswordEnc,
		&a.AutomationMode, &a.SubmitAfterHours, &a.PermalinkWindowDays, &a.StayFeeRateCZK, &a.Active,
		&a.ArchivedAt, &a.PermalinkToken, &a.PermalinkPIN, &a.LockProvider, &a.CheckinHour, &a.CheckoutHour)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// setup is the property_setup view of the row.
func (a *wizardApt) setup() Apartment {
	out := Apartment{ID: a.ID, InternalName: a.InternalName, AddrObec: a.AddrObec, AddrHouseNo: a.AddrHouseNo,
		AddrZip: a.AddrZip, StayFeeRateCZK: a.StayFeeRateCZK, LockProvider: a.LockProvider}
	if a.LegalEntityID != nil {
		out.LegalEntityID = *a.LegalEntityID
	}
	return out
}

// wizardEntity is one row of access.entities(request): the workspace's
// operators that are not archived, by name.
type wizardEntity struct {
	ID                  int64
	Name, SignatureName string
}

const wizardEntitiesSQL = `SELECT id, name, COALESCE(signature_name, '') FROM legal_entity
 WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL ORDER BY name`

// wizardCtx is what _wizard_context computes.
type wizardCtx struct {
	Apt           *wizardApt
	Entities      []wizardEntity
	Facts         Facts // facts_payload (feeds, stays, guests_registered, report_complete)
	State         *State
	Guide         *Guide
	LockAvailable bool
	LinkKey       string
	HasPassword   bool
	Celebrate     bool
}

// wizardContext is _wizard_context for one step. It returns nil (and writes
// nothing to w) when the property is not the workspace's; the caller sends
// the host back to /apartments.
func (s *wizardServer) wizardContext(ctx context.Context, owner, id int64, step string, at time.Time) (*wizardCtx, error) {
	apt, err := s.wizardLoadApt(ctx, owner, id)
	if err != nil || apt == nil {
		return nil, err
	}
	if apt.PermalinkPIN == "" { // _ensure_apartment_pin
		pin, err := wizardNewPIN()
		if err != nil {
			return nil, err
		}
		if _, err := s.pool.Exec(ctx, `UPDATE apartment SET permalink_pin = $1 WHERE id = $2`, pin, apt.ID); err != nil {
			return nil, err
		}
		if apt, err = s.wizardLoadApt(ctx, owner, id); err != nil || apt == nil {
			return nil, err
		}
	}
	c := &wizardCtx{Apt: apt}
	var feeds int
	if err := s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM ical_feed WHERE apartment_id = $1`, apt.ID).Scan(&feeds); err != nil {
		return nil, err
	}
	password, err := s.wizardSecret(apt.UbyWSPasswordEnc, at)
	if err != nil {
		return nil, err
	}
	c.HasPassword = apt.UbyWSPasswordEnc != ""
	reportComplete := wizardReportComplete(apt, password)
	if c.LockAvailable, err = s.wizardLockAllowed(ctx, apt.OwnerUserID); err != nil {
		return nil, err
	}
	var stays int
	if err := s.pool.QueryRow(ctx, `SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = $1
 AND r.archived_at IS NULL AND COALESCE(r.source, '') != 'demo'`, apt.ID).Scan(&stays); err != nil {
		return nil, err
	}
	var registered bool
	if err := s.pool.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM guest g JOIN reservation r ON r.id = g.reservation_id
 WHERE r.apartment_id = $1 AND g.entered_by = 'guest' AND COALESCE(r.source, '') != 'demo')`, apt.ID).Scan(&registered); err != nil {
		return nil, err
	}
	c.Facts = Facts{Feeds: feeds, Stays: stays, GuestsRegistered: registered, ReportComplete: reportComplete}
	settings := PoolSettings(s.pool)
	if c.State, err = s.wizardSetupState(ctx, settings, apt, c.Facts); err != nil {
		return nil, err
	}
	if c.State != nil && !c.State.Finished {
		c.Guide = Current(apt.setup(), c.State, c.Facts, c.LockAvailable)
	}
	if c.LinkKey, err = s.wizardLinkKey(ctx, apt, at); err != nil {
		return nil, err
	}
	if c.Entities, err = s.wizardEntities(ctx, owner); err != nil {
		return nil, err
	}
	if step == "done" {
		if c.Celebrate, err = CelebrateOnce(ctx, settings, apt.ID); err != nil {
			return nil, err
		}
	}
	return c, nil
}

// wizardSecret is db.decrypt_secret: "" for an empty or unreadable token.
func (s *wizardServer) wizardSecret(token string, at time.Time) (string, error) {
	if token == "" {
		return "", nil
	}
	keys, err := secure.LoadDataKeys(s.getenv)
	if err != nil {
		return "", err // Python's DataKeyError is a 500 too
	}
	plain, err := keys.Decrypt(token, 0, at)
	if err != nil {
		return "", nil
	}
	return string(plain), nil
}

// wizardReportFields is admin._READINESS_REPORT_FIELDS (the field half).
var wizardReportFields = []string{"uby_idub", "uby_mark", "uby_name", "addr_house_no", "addr_zip", "addr_obec", "uby_ws_user", "uby_ws_password"}

// wizardReportComplete is all(item["done"] for item in _readiness(...)["report"]):
// no validation error on any reporting field.
func wizardReportComplete(a *wizardApt, password string) bool {
	values := map[string]string{
		"internal_name": a.InternalName, "city_en": a.CityEN, "addr_okres": a.AddrOkres, "addr_obec": a.AddrObec,
		"addr_obec_cast": a.AddrObecCast, "addr_street": a.AddrStreet, "addr_house_no": a.AddrHouseNo,
		"addr_orient_no": a.AddrOrientNo, "addr_zip": a.AddrZip, "uby_idub": a.UbyIDUB, "uby_mark": a.UbyMark,
		"uby_name": a.UbyName, "uby_contact": a.UbyContact, "uby_ws_user": a.UbyWSUser, "uby_ws_password": password,
	}
	if a.LegalEntityID != nil {
		values["legal_entity_id"] = strconv.FormatInt(*a.LegalEntityID, 10)
	}
	if a.DataControllerEntityID != nil {
		values["data_controller_entity_id"] = strconv.FormatInt(*a.DataControllerEntityID, 10)
	}
	bad := map[string]bool{}
	for _, issue := range validation.ErrorsOnly(validation.ValidateApartment(values)) {
		bad[issue.Field] = true
	}
	for _, field := range wizardReportFields {
		if bad[field] {
			return false
		}
	}
	return true
}

// wizardDoorCodesEnabled is ttlock.enabled(): UBYHOST_DOOR_CODES is 1, true
// or yes and both TTLock app credentials are set.
func wizardDoorCodesEnabled(getenv func(string) string) bool {
	switch getenv("UBYHOST_DOOR_CODES") {
	case "1", "true", "yes":
	default:
		return false
	}
	return pyStrip(getenv("UBYHOST_TTLOCK_CLIENT_ID")) != "" && pyStrip(getenv("UBYHOST_TTLOCK_CLIENT_SECRET")) != ""
}

// wizardLockAllowed is ttlock.allowed_for(apartment["owner_user_id"]): door
// codes are on and billing.entitlements(owner).ttlock. It decides whether
// _door_code_context is None; the wizard pages read only that and the buffer.
func (s *wizardServer) wizardLockAllowed(ctx context.Context, owner *int64) (bool, error) {
	if !wizardDoorCodesEnabled(s.getenv) || owner == nil {
		return false, nil
	}
	switch strings.ToLower(s.getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
	default:
		return true, nil // UNBILLED
	}
	var status, plan string
	var addon int64
	err := s.pool.QueryRow(ctx, `SELECT status, COALESCE(plan, ''), COALESCE(addon_ttlock, 0) FROM billing_account WHERE owner_user_id = $1`, *owner).Scan(&status, &plan, &addon)
	if errors.Is(err, pgx.ErrNoRows) {
		return true, nil // UNBILLED
	}
	if err != nil {
		return false, err
	}
	switch status {
	case "paused":
		return false, nil
	case "trial_pending", "trialing":
		return true, nil
	}
	if plan == "" {
		plan = "standard"
	}
	return plan == "max" || addon != 0, nil
}

// wizardDemoNames are demo.DEMO_APARTMENT, DEMO_LOFT, DEMO_ENTITY and DEMO_CONTROLLER.
var wizardDemoNames = map[string]bool{"Vinohrady Studio (demo)": true, "Karlín Loft (demo)": true}
var wizardDemoEntities = map[string]bool{"Josef Novák (demo)": true, "Demo Controller s.r.o.": true}

// wizardIsDemoApartment is demo.is_demo_apartment.
func (s *wizardServer) wizardIsDemoApartment(ctx context.Context, a *wizardApt) (bool, error) {
	if wizardDemoNames[a.InternalName] {
		return true, nil
	}
	env := strings.ToLower(s.getenv("UBYHOST_UBYPORT_ENV"))
	if env == "" {
		env = "mock"
	}
	if env != "mock" || a.LegalEntityID == nil {
		return false, nil
	}
	var name string
	err := s.pool.QueryRow(ctx, `SELECT name FROM legal_entity WHERE id = $1`, *a.LegalEntityID).Scan(&name)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return wizardDemoEntities[name], nil
}

// wizardSetupState is admin._setup_state: the stored guide, or the guide of a
// property made before it (a legacy one that is now set up is finished).
func (s *wizardServer) wizardSetupState(ctx context.Context, settings Settings, a *wizardApt, f Facts) (*State, error) {
	state, err := Load(ctx, settings, a.ID)
	if err != nil {
		return nil, err
	}
	setUp := f.ReportComplete && (f.Feeds > 0 || f.Stays > 0)
	if state != nil {
		if state.Legacy && setUp && !state.Finished {
			if err := Finish(ctx, settings, a.ID); err != nil {
				return nil, err
			}
			return Load(ctx, settings, a.ID)
		}
		return state, nil
	}
	if a.ArchivedAt != "" || a.Active == 0 {
		return nil, nil
	}
	demo, err := s.wizardIsDemoApartment(ctx, a)
	if err != nil || demo {
		return nil, err
	}
	if setUp {
		return nil, nil
	}
	return LegacyState(), nil
}

func (s *wizardServer) wizardEntities(ctx context.Context, owner int64) ([]wizardEntity, error) {
	rows, err := s.pool.Query(ctx, wizardEntitiesSQL, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []wizardEntity
	for rows.Next() {
		var e wizardEntity
		if err := rows.Scan(&e.ID, &e.Name, &e.SignatureName); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// wizardRandBelow is secrets.randbelow(n).
func wizardRandBelow(n int64) (int64, error) {
	v, err := rand.Int(rand.Reader, big.NewInt(n))
	if err != nil {
		return 0, err
	}
	return v.Int64(), nil
}

// wizardNewPIN is auth.new_permalink_pin: six digits.
func wizardNewPIN() (string, error) {
	n, err := wizardRandBelow(1000000)
	if err != nil {
		return "", err
	}
	s := strconv.FormatInt(n, 10)
	return strings.Repeat("0", 6-len(s)) + s, nil
}

// wizardPySplit is Python's str.split() with no argument.
func wizardPySplit(s string) []string {
	return strings.FieldsFunc(s, func(r rune) bool { return pyStrip(string(r)) == "" })
}

// wizardCompanyWords are the words that mark an operator name as a company.
var wizardCompanyWords = map[string]bool{"sro": true, "as": true, "ltd": true, "limited": true, "llc": true, "gmbh": true, "inc": true}

// wizardOperatorFirstName is message_operator_first_name of _wizard_context.
func wizardOperatorFirstName(lang string, a *wizardApt, entities []wizardEntity) string {
	var entity *wizardEntity
	for i := range entities {
		if a.LegalEntityID != nil && entities[i].ID == *a.LegalEntityID {
			entity = &entities[i]
			break
		}
	}
	signatory := ""
	if entity != nil {
		signatory = entity.SignatureName
		if signatory == "" {
			name := pyStrip(entity.Name)
			company := false
			for _, word := range wizardPySplit(strings.NewReplacer(".", "", ",", "").Replace(strings.ToLower(name))) {
				if wizardCompanyWords[word] {
					company = true
				}
			}
			if !company {
				signatory = name
			}
		}
	}
	if words := wizardPySplit(signatory); len(words) > 0 {
		return words[0]
	}
	return wizardText.T(lang, "wizard.guest_link.operator_placeholder", nil)
}

// wizardEnvInt is int(os.environ.get(key, def)); a bad value keeps def
// (Python would fail at start-up instead).
func wizardEnvInt(getenv func(string) string, key string, def int) int {
	if n, err := strconv.Atoi(strings.TrimSpace(getenv(key))); err == nil {
		return n
	}
	return def
}

// wizardPragueToday is claim.prague_today().
func wizardPragueToday(at time.Time) time.Time {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		loc = time.UTC
	}
	p := at.In(loc)
	return time.Date(p.Year(), p.Month(), p.Day(), 0, 0, 0, 0, time.UTC)
}

// wizardISO is date.isoformat().
func wizardISO(d time.Time) string { return d.Format("2006-01-02") }

// wizardParseISO is validation.parse_iso_date for the dates the wizard reads.
func wizardParseISO(s string) (time.Time, bool) {
	return validation.ParseISODate(s)
}

// wizardDateShort is validation.fmt_date_short: "d. m." and the year when it
// is not the server's current year (date.today(), UTC on the server).
func wizardDateShort(value string, at time.Time) string {
	d, ok := wizardParseISO(value)
	if !ok {
		return value
	}
	short := strconv.Itoa(d.Day()) + ". " + strconv.Itoa(int(d.Month())) + "."
	if d.Year() == at.UTC().Year() {
		return short
	}
	return short + " " + strconv.Itoa(d.Year())
}

// wizardDateCZ is the date_cz filter (validation.fmt_date): DD.MM.YYYY.
func wizardDateCZ(value string) string {
	d, ok := wizardParseISO(value)
	if !ok {
		return value
	}
	return d.Format("02.01.2006")
}

// wizardLinkNext is workflow.next_stay_window(apartment) as the templates print it.
type wizardLinkNext struct {
	HasStay  bool
	DateFrom string // the stay's date_from
	Window   string // "", "now" or "from"
	Opens    string // ISO date the stay appears on the guest link
	Days     int
}

// wizardNextStayWindow is workflow.next_stay_window.
func (s *wizardServer) wizardNextStayWindow(ctx context.Context, a *wizardApt, at time.Time) (wizardLinkNext, error) {
	today := wizardPragueToday(at)
	days := int(a.PermalinkWindowDays)
	if days == 0 {
		days = 1
	}
	out := wizardLinkNext{Days: days}
	var from, status, source string
	var archived *string
	err := s.pool.QueryRow(ctx, `SELECT date_from, status, COALESCE(source, ''), archived_at FROM reservation
 WHERE apartment_id = $1 AND status = 'active' AND archived_at IS NULL AND COALESCE(source, '') != 'demo'
   AND date_from >= $2 ORDER BY date_from LIMIT 1`, a.ID, wizardISO(today)).Scan(&from, &status, &source, &archived)
	if errors.Is(err, pgx.ErrNoRows) {
		return out, nil
	}
	if err != nil {
		return out, err
	}
	out.HasStay, out.DateFrom = true, from
	// workflow.link_window: the stay is active, not archived and not demo (the query says so).
	start, ok := wizardParseISO(from)
	if !ok || start.Before(today) {
		return out, nil
	}
	opens := start.AddDate(0, 0, -days)
	if !opens.After(today) {
		out.Window, out.Opens = "now", wizardISO(today)
	} else {
		out.Window, out.Opens = "from", wizardISO(opens)
	}
	return out, nil
}

// wizardStep is one row of workflow.steps(apartment).
type wizardStep struct {
	N        int
	Key, Who string
}

// wizardWorkflowSteps is workflow.steps; nil apartment is the generic story.
func (s *wizardServer) wizardWorkflowSteps(a *wizardApt) []wizardStep {
	police, finish := "police", "finish"
	if a != nil {
		switch a.AutomationMode {
		case "manual":
			police = "police_manual"
		case "scheduled":
			police = "police_scheduled"
		case "immediate":
			police = "police_immediate"
		}
		if a.LockProvider == "ttlock" && wizardDoorCodesEnabled(s.getenv) {
			finish = "finish_lock"
		}
	}
	who := "auto"
	if police == "police_manual" {
		who = "you"
	}
	return []wizardStep{{1, "paste", "you_once"}, {2, "form", "auto"}, {3, "email", "auto"}, {4, police, who}, {5, finish, "auto"}}
}

// wizardDemo is setup_demo of the try_it step.
type wizardDemo struct {
	State            string // none, open or registered
	ReservationID    int64
	Progress         layout.Progress
	Status           string // reservation_progress status
	GuestURL         string
	DateFrom, DateTo string
}

// wizardDemoFor is the setup_demo block of _wizard_context (demo.demo_stay_for
// and reporting.reservation_progress).
func (s *wizardServer) wizardDemoFor(ctx context.Context, a *wizardApt, linkKey, lang string, at time.Time) (*wizardDemo, error) {
	var st calendar.AlertStay
	err := s.pool.QueryRow(ctx, `SELECT id, date_from, date_to, declared_guests, expected_guests_override, lead_reduced_guests
  FROM reservation WHERE apartment_id = $1 AND source = 'demo' AND archived_at IS NULL ORDER BY id DESC LIMIT 1`, a.ID).Scan(
		&st.ID, &st.DateFrom, &st.DateTo, &st.Declared, &st.Override, &st.Reduced)
	today := wizardPragueToday(at)
	if errors.Is(err, pgx.ErrNoRows) {
		return &wizardDemo{State: "none", DateFrom: wizardISO(today), DateTo: wizardISO(today.AddDate(0, 0, 1))}, nil
	}
	if err != nil {
		return nil, err
	}
	progress, err := calendar.AlertProgresses(ctx, s.pool, s.getenv, []calendar.AlertStay{st}, at)
	if err != nil {
		return nil, err
	}
	p := progress[st.ID]
	if p.Unreadable {
		return nil, errors.New("demo stay guest will not decrypt") // Python raises DecryptionError
	}
	d := &wizardDemo{State: "open", ReservationID: st.ID, Status: p.Status, DateFrom: st.DateFrom, DateTo: st.DateTo,
		Progress: layout.Progress{Expected: p.Expected, Filled: p.Filled, Guests: p.Filled + p.Incomplete},
		GuestURL: "/l/" + linkKey + "/demo/" + strconv.FormatInt(st.ID, 10) + "?lang=" + lang}
	if p.Filled >= 1 {
		d.State = "registered"
	}
	return d, nil
}

// wizardQR is payments.qr_data_uri.
func wizardQR(payload string) (string, error) { return payments.QRDataURI(payload) }

// wizardPublicBase is config.PUBLIC_BASE_URL.
func wizardPublicBase(getenv func(string) string) string { return hostweb.PublicBase(getenv) }
