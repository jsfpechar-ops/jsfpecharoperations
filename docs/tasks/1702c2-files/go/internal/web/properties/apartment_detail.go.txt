package properties

// GET /apartments/{id} (brief 1701): routes/admin.py apartment_detail and
// _render_apartment_detail, the property page. The body is the Go twin of
// apartment_form.html (edit branch) with partials/settings_back_header.html,
// _copy_settings_dialog.html, _property_editor.html, _setup_ready_card.html,
// _property_identity_fields.html, _property_operator.html,
// _property_address_fields.html, _police_fields.html, _police_letter_figure.html
// and _property_calendars.html, drawn in the host layout (hostweb/layout). The
// page strings are their own catalog (apartmentdetail/i18n.json, written by
// App/scripts/go_host_i18n.py).
//
// The Stay fee section (brief 1701b, apartment_detail_fee.go) is the last part of
// the Reporting settings. The forms post to the Python routes as they do
// today (POST /apartments/{id}, .../feeds, .../archive, .../regenerate-pin).
//
// What this port answers 501 for, with the Caddy fallback header (notPorted),
// so Python serves it: a path id that is not a number, a property that is not
// the workspace's (both are Python's branded 404 page), and a copy_from value
// this port does not judge. Nothing routes here until the owner adds the path
// to UBYHOST_GO_PATHS (brief 1705).

import (
	"context"
	"embed"
	"html"
	"html/template"
	"net/http"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validationi18n"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/ai"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/exports"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

//go:embed apartmentdetail/apartment_detail.tmpl
var apartmentDetailFiles embed.FS

//go:embed apartmentdetail/i18n.json
var apartmentDetailJSON []byte

// apartmentDetailStrings is the page catalog, written from host_i18n.py by
// App/scripts/go_host_i18n.py from apartmentdetail/i18n_keys.txt.
var apartmentDetailStrings = hostweb.Load(apartmentDetailJSON)

// apartmentDetailTemplates is parsed once; the layout clones it per request.
var apartmentDetailTemplates = layout.MustParseFuncs(apartmentDetailStrings, template.FuncMap{"date_cz": exports.DateCZ, "join": strings.Join},
	apartmentDetailFiles, "apartmentdetail/apartment_detail.tmpl")

// Section ids, the PROPERTY_VIEWS and PROPERTY_SETTINGS_SECTIONS of admin.py.
var (
	detailViews    = map[string]bool{"overview": true, "bookings": true, "settings": true}
	detailSections = map[string]bool{"property": true, "guests": true, "reporting": true, "lock": true, "automation": true}
	// detailExplicit is explicit_map of the sec_open macro.
	detailExplicit = map[string][]string{"property": {"sec-basics"}, "guests": {"sec-messages"},
		"reporting": {"sec-police", "sec-fee"}, "automation": {"sec-police"}, "lock": {"sec-lock"}}
)

// detailStrip is one pill of the strip: its state, whether it is a problem
// (bad or warn) and the health row it came from.
type detailStrip struct {
	State   string
	Problem bool
	TextKey string
}

// detailView is the context of apartment_form.html for an existing property.
// Brief 1702 (POST /apartments/{id}) and 1703 (the small POSTs) draw a refused
// save or form with this same view: they add the POST-only fields of the Python
// context (save_errors, operator_error, shared_time_error, lock_times_error,
// letter_*, feed_draft, feed_errors) next to Status below, and call detailBuild
// and layout.Render the way apartmentDetail does.
type detailView struct {
	Status     int // 0 is 200; a refused save sends 400
	A          *detailApt
	Base       string
	Address    string // address_text
	AddressSub bool   // prop_addr.strip()

	// The copy dialog (_property_copy_form_context).
	CopyPeers   []detailPeer
	CopyFromID  int64
	CopiedName  string
	CopyOpen    bool
	CopySection string

	// The page state (_property_view_state and the 1099 short editor).
	PropertyView, SettingsSection string
	AddCalendar, JustCreated      bool
	FirstSetup, ReadyCard         bool
	SetupOpen                     string
	SectionExplicit               bool
	SectionDone                   map[string]bool
	SectionMinutes                map[string]int
	PoliceReported                bool
	ReadyQR                       template.URL
	Open                          map[string]bool // sec_open per section id
	Progress                      *detailProgress
	SetupHidden                   bool
	WizardActive                  bool

	// The flash the host shell reads from the query (templating.render).
	FlashError, FlashMsg string
	InlineFlashSection   string
	EditorSaved          bool

	// The data.
	Entities       []detailEntity
	Operator       *detailEntity
	Feeds          []detailFeed
	FeedsCount     int
	CalendarErrors int
	Readiness      detailReadiness
	MissBasics     []detailItem
	MissPolice     []detailItem
	MissCalendars  []detailItem
	ReportMissing  int
	PoliceOK       bool
	Cal, Guest     detailStrip
	Police, Biz    detailStrip
	Health         map[string]detailHealthRow
	Door           *detailDoor
	DoorPill       string // ok | off | bad
	Permalink      string
	LinkKey        string
	Pin            string
	LinkNext       detailLinkNext
	LeonCard       string
	Purposes       []detailPurpose
	HasPassword    bool
	HavelOn        bool
	FeeReturnTo    string
	Fee            detailFee
	Hours          []int
	Platforms      []detailPlatform
	PoliceFindings []detailFinding

	Lang             string
	OperatorSelected int64
	AddrRow1         []apartmentNewAddr
	AddrRow2         []apartmentNewAddr
	AutomationModes  []string
	AutomationShown  string
	LetterFirst      bool
	BasicsState      string
	PoliceState      string
	CalendarsState   string
	LockState        string

	// A refused save (_refuse_apartment_save and refuse_fee_save, brief 1702b).
	// The POST handler fills them; GET leaves them empty.
	SaveErrors              []detailSaveError
	SaveFailed              string            // tp('property_page.save_failed', save_errors|length)
	AddressErrors           map[string]string // field -> message in the host's language
	OperatorError           string            // operator_error: an i18n key or ""
	OpError                 string            // _property_operator.html op_error
	ControllerError         bool              // operator_error == 'flash.error.no_such_controller'
	SharedTimeError         string            // shared_time_error: an i18n key or ""
	LockTimesError          bool
	FeeAccountError         bool
	FeeLinkError            bool
	FeeRateError            bool
	FeeOperatorAccountError bool
}

// detailSaveError is _save_error: the settings section and the field id the
// summary above the Save bar links to.
type detailSaveError struct{ Section, Target string }

// detailPlatform is one option of CALENDAR_PLATFORMS ("" name: the "other" text).
type detailPlatform struct{ Key, Name string }

// detailPlatforms is admin.CALENDAR_PLATFORMS.
var detailPlatforms = []detailPlatform{{"booking", "Booking.com"}, {"airbnb", "Airbnb"}, {"vrbo", "Vrbo"},
	{"agoda", "Agoda"}, {"echalupy", "e-chalupy"}, {"other", ""}}

// RegisterApartmentDetail adds GET /apartments/{id}. It only builds the
// handler; the pool is first used inside a request.
func RegisterApartmentDetail(mux *http.ServeMux, wrap Wrap, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) {
	s := &Pages{pool: pool, getenv: getenv, now: now}
	mux.Handle("GET /apartments/{id}", wrap("/apartments/{id}", s.apartmentDetail))
}

// detailT is the page catalog's t() for the request language.
func detailT(lang, key string, in ...any) string {
	params := map[string]any{}
	for i := 0; i+1 < len(in); i += 2 {
		if k, ok := in[i].(string); ok {
			params[k] = in[i+1]
		}
	}
	return apartmentDetailStrings.T(lang, key, params)
}

// detailTP is the page catalog's tp(): count and n are the number.
func detailTP(lang, base string, n int) string {
	return detailT(lang, detailPluralKey(base, n), "count", n, "n", n)
}

// detailPluralKey is host_i18n.plural_key for en, cs and vi.
func detailPluralKey(base string, n int) string {
	switch {
	case n == 1:
		return base + ".one"
	case n >= 2 && n <= 4:
		return base + ".few"
	}
	return base
}

func (s *Pages) detailHavelEnv() ai.HavelEnv {
	return func(k string) (string, bool) { v := s.getenv(k); return v, v != "" }
}

// apartmentDetail is routes/admin.py apartment_detail.
func (s *Pages) apartmentDetail(w http.ResponseWriter, r *http.Request) {
	now := s.now()
	id, valid := parseID(r.PathValue("id"))
	if !valid {
		notPorted(w, "a path id that is not a number")
		return
	}
	host, err := hostweb.Login(w, r, s.pool, s.getenv, now)
	if err != nil {
		fail(w, err)
		return
	}
	if host == nil {
		return
	}
	copyID, ok := apartmentNewQueryInt(r, "copy_from")
	if !ok {
		notPorted(w, "a non-ASCII or oversized number in the query")
		return
	}
	ctx := r.Context()
	owner := host.Workspace.ID
	a, err := s.detailLoad(ctx, owner, id)
	if err == nil && a != nil {
		a, err = s.detailEnsurePIN(ctx, owner, a)
	}
	if err != nil {
		fail(w, err)
		return
	}
	if a == nil {
		notPorted(w, "a property that is not in the workspace")
		return
	}
	view := &detailView{Base: "/apartments/" + strconv.FormatInt(a.ID, 10), CopyFromID: copyID, CopyOpen: queryLast(r, "copy") == "choose"}
	settings := onboarding.PoolSettings(s.pool)
	// _property_copy_form_context: copying is a first-time step.
	stored, err := onboarding.Load(ctx, settings, a.ID)
	if err != nil {
		fail(w, err)
		return
	}
	if stored != nil && !stored.Finished {
		if view.CopyPeers, err = s.detailPeers(ctx, owner, a.ID); err != nil {
			fail(w, err)
			return
		}
	}
	if copyID != 0 && copyID != a.ID {
		src, err := s.detailLoad(ctx, owner, copyID)
		if err != nil {
			fail(w, err)
			return
		}
		if src == nil {
			w.WriteHeader(http.StatusNotFound) // Response("Not found.", status_code=404)
			_, _ = w.Write([]byte("Not found."))
			return
		}
		view.CopiedName = src.InternalName
		detailApplyCopy(a, src)
	}
	s.detailRender(w, r, host, a, view, settings, now)
}

// detailRender builds and draws the page for a: GET /apartments/{id}, and the
// refused save of brief 1702b, whose view carries the error lines and Status.
func (s *Pages) detailRender(w http.ResponseWriter, r *http.Request, host *session.Host, a *detailApt, view *detailView, settings onboarding.Settings, now time.Time) {
	if err := s.detailBuild(r.Context(), r, host, a, view, settings, now); err != nil {
		fail(w, err)
		return
	}
	title := a.InternalName
	page := layout.Page{Title: title, Nav: "apartments", BodyKind: "detail", V2: true, HowKey: "property", Status: view.Status}
	if err := layout.Render(w, r, layout.Env{Pool: s.pool, Getenv: s.getenv, Now: now}, host, page, apartmentDetailTemplates, "apartmentdetail", view); err != nil {
		fail(w, err)
	}
}

// detailBuild is _render_apartment_detail: every value the template reads.
func (s *Pages) detailBuild(ctx context.Context, r *http.Request, host *session.Host, a *detailApt, v *detailView, settings onboarding.Settings, now time.Time) error {
	lang := hostweb.Lang(r)
	owner := host.Workspace.ID
	v.A = a
	v.Hours = make([]int, 24)
	for h := range v.Hours {
		v.Hours[h] = h
	}
	v.Platforms = detailPlatforms
	v.JustCreated = queryLast(r, "created") == "1"
	// _property_view_state.
	view, section := queryLast(r, "view"), queryLast(r, "section")
	// A refused save (brief 1702c2) sets both, as extra does; the query fills the rest.
	if v.PropertyView != "" {
		view = v.PropertyView
	}
	if v.SettingsSection != "" {
		section = v.SettingsSection
	}
	if !detailSections[section] {
		section = ""
	}
	if !detailViews[view] {
		view = "overview"
		if section != "" {
			view = "settings"
		}
	}
	v.PropertyView, v.SettingsSection = view, section
	if v.SettingsSection == "" {
		v.SettingsSection = "property"
	}
	v.AddCalendar = queryLast(r, "add_calendar") == "1"
	v.CopySection = v.SettingsSection
	// templating.render: the flash and the inline section.
	v.FlashError, v.FlashMsg = queryLast(r, "err"), queryLast(r, "msg")
	if sec := queryLast(r, "sec"); sec != "" && isAlphaWord(sec) {
		v.InlineFlashSection = sec
	}
	v.EditorSaved = queryLast(r, "saved") == "1"

	var err error
	if v.Entities, err = s.detailEntities(ctx, owner); err != nil {
		return err
	}
	for i := range v.Entities {
		if v.Entities[i].ID == a.LegalEntityID {
			v.Operator = &v.Entities[i]
		}
	}
	if v.Feeds, err = s.detailFeeds(ctx, a.ID, detailT(lang, "calendar.fallback_name"), detailT(lang, "calendar.platform.other")); err != nil {
		return err
	}
	v.FeedsCount = len(v.Feeds)
	hasStays := false
	for _, f := range v.Feeds {
		if f.LastStatus == "error" {
			v.CalendarErrors++
		}
		if f.Active {
			hasStays = true
		}
	}
	if !hasStays {
		if err = s.pool.QueryRow(ctx, `SELECT EXISTS (SELECT 1 FROM reservation WHERE apartment_id = $1 AND COALESCE(source, '') != 'demo')`, a.ID).Scan(&hasStays); err != nil {
			return err
		}
	}
	issues, err := s.detailIssues(a, now)
	if err != nil {
		return err
	}
	controllerOK, err := s.detailControllerComplete(ctx, owner, a)
	if err != nil {
		return err
	}
	if v.Door, err = s.detailDoorContext(ctx, a); err != nil {
		return err
	}
	lockAvailable := v.Door != nil
	v.Readiness = detailReadinessOf(a, v.Operator, issues, hasStays, controllerOK, true)
	for i := range v.Readiness.Report {
		if m := v.Readiness.Report[i].Message; m != "" {
			v.Readiness.Report[i].Message = validationi18n.Localize(m, lang)
		}
	}
	bundle, err := s.detailGuideBundle(ctx, settings, a, v.FeedsCount, v.Readiness.reportComplete(), lockAvailable)
	if err != nil {
		return err
	}
	// 1099: the short editor. The setup completes only after a passing connection test.
	facts := bundle.Facts
	if v.Door != nil {
		facts.DoorCode = v.Door.State
	}
	state := bundle.State
	if onboarding.IsFirstSetup(state) && onboarding.SetupComplete(a.setup(), facts, state) {
		if err = onboarding.Finish(ctx, settings, a.ID); err != nil {
			return err
		}
		if v.ReadyCard, err = onboarding.CelebrateOnce(ctx, settings, a.ID); err != nil {
			return err
		}
		if bundle, err = s.detailGuideBundle(ctx, settings, a, v.FeedsCount, v.Readiness.reportComplete(), lockAvailable); err != nil {
			return err
		}
		state = bundle.State
	}
	v.FirstSetup = onboarding.IsFirstSetup(state) && !v.ReadyCard
	if v.FirstSetup {
		if key := onboarding.OpenSection(a.setup(), facts, state); key != "" {
			v.SetupOpen = "sec-" + key
		}
	}
	_, hasSection := r.URL.Query()["section"]
	v.SectionExplicit = hasSection && !v.ReadyCard && !(v.FirstSetup && queryLast(r, "saved") == "1")
	v.SectionMinutes = onboarding.SectionMinutes
	v.SectionDone = map[string]bool{}
	for key := range onboarding.SectionMinutes {
		v.SectionDone[key] = onboarding.SectionDone(key, a.setup(), facts, state)
	}
	v.PoliceReported = facts.ReportComplete
	if v.Progress, err = detailSetupProgress(ctx, settings, a, bundle, lockAvailable); err != nil {
		return err
	}
	v.SetupHidden = v.Progress != nil && v.Progress.Hidden
	v.WizardActive = v.Progress != nil && !v.Progress.Hidden

	if v.Health, err = s.detailHealth(ctx, a, v.Feeds, v.Readiness, v.Door, now); err != nil {
		return err
	}
	if v.LinkKey, err = s.detailLinkKey(ctx, a); err != nil {
		return err
	}
	v.Permalink = hostweb.PublicBase(s.getenv) + "/l/" + v.LinkKey
	v.Pin = a.PermalinkPIN
	if v.ReadyCard {
		qr, err := payments.QRDataURI(v.Permalink)
		if err != nil {
			return err
		}
		v.ReadyQR = template.URL(qr) // a data: image; the payload is the guest link made above
	}
	if v.LinkNext, err = s.detailNextStay(ctx, a, now); err != nil {
		return err
	}
	if v.Purposes, err = s.detailPurposes(ctx); err != nil {
		return err
	}
	if v.LeonCard, err = s.detailLeonCard(ctx, a); err != nil {
		return err
	}
	v.HasPassword = a.UbyWSPasswordEnc != ""
	var email string
	if err = s.pool.QueryRow(ctx, `SELECT COALESCE(email, '') FROM user_account WHERE id = $1`, host.Account.ID).Scan(&email); err != nil {
		return err
	}
	v.HavelOn = ai.HavelAIOn(s.detailHavelEnv(), "havel", email)
	if back := safeLocalPath(queryLast(r, "return_to"), ""); back != "" {
		if path, _, _ := strings.Cut(back, "?"); path == "/stay-fees" || path == "/stay-fees/"+strconv.FormatInt(a.ID, 10) {
			v.FeeReturnTo = back
		}
	}
	if v.PoliceFindings, err = s.detailPoliceFindings(ctx, lang, a); err != nil {
		return err
	}
	if v.Fee, err = s.detailFeeBuild(ctx, owner, a, now); err != nil {
		return err
	}
	v.Lang = lang
	v.derive(lang)
	return nil
}

// isAlphaWord is str.isalpha for a query value: letters only, and not empty.
func isAlphaWord(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if !unicode.IsLetter(c) {
			return false
		}
	}
	return true
}

// derive fills what the editor template computes with {% set %}: the address
// text, the six pills, the missing lists and which sections start open.
func (v *detailView) derive(lang string) {
	a := v.A
	v.Address = strings.Join(nonEmpty(pyStrip(a.AddrStreet+" "+a.AddrHouseNo), a.AddrObec), ", ")
	v.AddressSub = pyStrip(v.Address) != ""
	pill := func(key string) detailStrip {
		row := v.Health[key]
		return detailStrip{State: row.State, Problem: row.State == "bad" || row.State == "warn", TextKey: row.TextKey}
	}
	v.Cal, v.Guest, v.Police, v.Biz = pill("calendar"), pill("guest_link"), pill("police"), pill("business")
	v.PoliceOK = v.Health["police"].State == "ok"
	for _, item := range v.Readiness.Report {
		if !item.Done {
			v.ReportMissing++
		}
	}
	for _, item := range v.Readiness.Invite {
		if !item.Done {
			if item.Anchor == "calendars" {
				v.MissCalendars = append(v.MissCalendars, item)
			} else {
				v.MissBasics = append(v.MissBasics, item)
			}
		}
	}
	for _, item := range v.Readiness.Report {
		if !item.Done {
			if item.Anchor == "address" {
				v.MissBasics = append(v.MissBasics, item)
			} else {
				v.MissPolice = append(v.MissPolice, item)
			}
		}
	}
	// _property_operator.html: the stored (or copied) operator when it is one of
	// the host's, else the only operator, else none.
	for _, e := range v.Entities {
		if e.ID == a.LegalEntityID {
			v.OperatorSelected = e.ID
		}
	}
	if v.OperatorSelected == 0 && len(v.Entities) == 1 {
		v.OperatorSelected = v.Entities[0].ID
	}
	// _property_address_fields.html: the seven boxes with the stored values.
	draft := map[string]string{"addr_street": a.AddrStreet, "addr_house_no": a.AddrHouseNo, "addr_orient_no": a.AddrOrientNo,
		"addr_zip": a.AddrZip, "addr_obec": a.AddrObec, "addr_obec_cast": a.AddrObecCast, "addr_okres": a.AddrOkres}
	boxes := ApartmentNewForm{Draft: draft, AddressErrors: v.AddressErrors}.view("")
	v.AddrRow1, v.AddrRow2 = boxes.AddrRow1, boxes.AddrRow2
	v.AutomationModes = []string{"manual", "scheduled", "immediate"}
	v.AutomationShown = "manual"
	for _, m := range v.AutomationModes {
		if a.AutomationMode == m {
			v.AutomationShown = m
		}
	}
	v.LetterFirst = v.FirstSetup && !v.SectionDone["police"]
	missing := func() string { return detailTP(lang, "property_nav.report_missing", v.ReportMissing) }
	// The one-line state of each section header (sec_state).
	v.BasicsState = firstText(func() string {
		if v.FirstSetup && v.SectionDone["basics"] {
			return detailT(lang, "setup.sec.done")
		}
		return v.Address
	}(), detailT(lang, "property_nav.address_missing"))
	switch {
	case !v.FirstSetup && v.PoliceOK:
		v.PoliceState = detailT(lang, "property_nav.report_ready")
	case !v.FirstSetup, !v.PoliceReported:
		v.PoliceState = missing()
	case v.SectionDone["police"]:
		v.PoliceState = detailT(lang, "setup.sec.done")
	default:
		v.PoliceState = detailT(lang, "setup.sec.police_untested")
	}
	if v.FeedsCount > 0 {
		v.CalendarsState = detailTP(lang, "apartment.form.calendars_count", v.FeedsCount)
	} else {
		v.CalendarsState = detailT(lang, "setup.sec.recommended")
	}
	v.LockState = detailT(lang, "property_nav.switch_off")
	if v.Door != nil && v.Door.State == "on" {
		v.LockState = detailT(lang, "property_nav.switch_enabled")
	}
	v.DoorPill = "off"
	if v.Door != nil {
		switch v.Door.State {
		case "on":
			v.DoorPill = "ok"
		case "off":
			// _property_operator.html: the stored (or copied) operator when it is one of
			// the host's, else the only operator, else none.
			for _, e := range v.Entities {
				if e.ID == a.LegalEntityID {
					v.OperatorSelected = e.ID
				}
			}
			if v.OperatorSelected == 0 && len(v.Entities) == 1 {
				v.OperatorSelected = v.Entities[0].ID
			}
			// _property_address_fields.html: the seven boxes with the stored values.
			draft := map[string]string{"addr_street": a.AddrStreet, "addr_house_no": a.AddrHouseNo, "addr_orient_no": a.AddrOrientNo,
				"addr_zip": a.AddrZip, "addr_obec": a.AddrObec, "addr_obec_cast": a.AddrObecCast, "addr_okres": a.AddrOkres}
			boxes := ApartmentNewForm{Draft: draft, AddressErrors: v.AddressErrors}.view("")
			v.AddrRow1, v.AddrRow2 = boxes.AddrRow1, boxes.AddrRow2
			v.AutomationModes = []string{"manual", "scheduled", "immediate"}
			v.AutomationShown = "manual"
			for _, m := range v.AutomationModes {
				if a.AutomationMode == m {
					v.AutomationShown = m
				}
			}
			v.LetterFirst = v.FirstSetup && !v.SectionDone["police"]
			missing := func() string { return detailTP(lang, "property_nav.report_missing", v.ReportMissing) }
			// The one-line state of each section header (sec_state).
			v.BasicsState = firstText(func() string {
				if v.FirstSetup && v.SectionDone["basics"] {
					return detailT(lang, "setup.sec.done")
				}
				return v.Address
			}(), detailT(lang, "property_nav.address_missing"))
			switch {
			case !v.FirstSetup && v.PoliceOK:
				v.PoliceState = detailT(lang, "property_nav.report_ready")
			case !v.FirstSetup, !v.PoliceReported:
				v.PoliceState = missing()
			case v.SectionDone["police"]:
				v.PoliceState = detailT(lang, "setup.sec.done")
			default:
				v.PoliceState = detailT(lang, "setup.sec.police_untested")
			}
			if v.FeedsCount > 0 {
				v.CalendarsState = detailTP(lang, "apartment.form.calendars_count", v.FeedsCount)
			} else {
				v.CalendarsState = detailT(lang, "setup.sec.recommended")
			}
			v.DoorPill = "off"
		default:
			v.DoorPill = "bad"
		}
	}
	if len(v.SaveErrors) > 0 {
		v.SaveFailed = detailTP(lang, "property_page.save_failed", len(v.SaveErrors))
	}
	if strings.HasPrefix(v.OperatorError, "apartment.form.operator.") {
		v.OpError = v.OperatorError
	}
	v.ControllerError = v.OperatorError == "flash.error.no_such_controller"
	v.Open = map[string]bool{}
	for _, id := range []string{"sec-basics", "sec-messages", "sec-police", "sec-fee", "sec-calendars", "sec-lock"} {
		key := id[4:]
		open := v.InlineFlashSection == key && (v.FlashError != "" || !(v.FirstSetup || v.ReadyCard))
		for _, e := range v.SaveErrors {
			if e.Section == key {
				open = true
			}
		}
		if v.SectionExplicit {
			for _, e := range detailExplicit[v.SettingsSection] {
				if e == id {
					open = true
				}
			}
		}
		if id == "sec-calendars" && v.PropertyView == "bookings" {
			open = true
		}
		if v.FirstSetup && id == v.SetupOpen && !v.SectionExplicit && v.PropertyView != "bookings" {
			open = true
		}
		v.Open[id] = open
	}
}

// nonEmpty is Python's [x, y] | select: the truthy items.
func nonEmpty(items ...string) []string {
	var out []string
	for _, s := range items {
		if s != "" {
			out = append(out, s)
		}
	}
	return out
}

// detailLeonCard is guest_guide.leon_card_state: "" (None) where Leon is not
// offered, else off, terms, waiting or on.
func (s *Pages) detailLeonCard(ctx context.Context, a *detailApt) (string, error) {
	var owner int64
	if a.OwnerUserID != nil {
		owner = *a.OwnerUserID
	}
	la := ai.LeonApartment{ID: a.ID, OwnerID: owner, Name: a.InternalName, Enabled: a.LeonEnabled != 0,
		TermsVersion: a.LeonTermsVersion, LegalEntityID: a.LegalEntityID}
	store := ai.LeonStore{HavelStore: ai.HavelStore{Pool: s.pool, Env: s.detailHavelEnv()}}
	offered, err := store.Offered(ctx, la)
	if err != nil || !offered {
		return "", err
	}
	live := false
	if la.Enabled {
		f, err := store.Facts(ctx, a.ID)
		if err != nil {
			return "", err
		}
		live = f.Live
	}
	return ai.LeonHostState(la, live), nil
}

// ReachbackDays is `apartment.permalink_reachback_days or 365`.
func (v *detailView) ReachbackDays() int64 {
	if v.A.PermalinkReachbackDays == 0 {
		return 365
	}
	return v.A.PermalinkReachbackDays
}

// HourSelected is `apartment[name]|string == h|string` for the two hour selects.
func (v *detailView) HourSelected(name string, h int) bool {
	hour := v.A.CheckinHour
	if name == "checkout_hour" {
		hour = v.A.CheckoutHour
	}
	return hour != nil && *hour == int64(h)
}

// FacilityHelp is facility_help of _police_fields.html: the hint and the
// example line (markup, as the Jinja set block is).
func (v *detailView) FacilityHelp() template.HTML {
	return template.HTML(html.EscapeString(detailT(v.Lang, "apartment.form.ubyport.name_hint")) +
		` <span class="facility-example"><span class="facility-example-label">` +
		html.EscapeString(detailT(v.Lang, "apartment.form.ubyport.name_example")) +
		`</span>Ubytovací zařízení: <mark>BYT Č. [2] FIKTVNÍ 1234/56 (PRAHA,</mark> PRAHA 2, FIKTVNÍ, 1234/56)</span>`)
}

// detailWindow is what _door_code_window.html computes from the two hours.
type detailWindow struct {
	Buffer                 int
	Checkin, Checkout      string
	Complete               bool
	StartHour, EndHour     int
	StartPrevious, EndNext bool
}

// Window is _door_code_window.html: the check-in and check-out hours count
// only as 0..23, as Python's hour_values test has it.
func (v *detailView) Window() detailWindow {
	w := detailWindow{Buffer: v.Door.Buffer}
	valid := func(h *int64) bool { return h != nil && *h >= 0 && *h <= 23 }
	in, out := v.A.CheckinHour, v.A.CheckoutHour
	if valid(in) {
		w.Checkin = strconv.FormatInt(*in, 10)
	}
	if valid(out) {
		w.Checkout = strconv.FormatInt(*out, 10)
	}
	if w.Complete = valid(in) && valid(out); w.Complete {
		start, end := int(*in)-w.Buffer, int(*out)+w.Buffer
		w.StartHour, w.StartPrevious = ((start%24)+24)%24, start < 0
		w.EndHour, w.EndNext = end%24, end >= 24
	}
	return w
}
