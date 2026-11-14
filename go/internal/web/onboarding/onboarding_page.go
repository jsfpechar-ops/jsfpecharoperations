package onboarding

// GET /onboarding (brief 1595): routes/onboarding.py onboarding_view, the
// checklist page. The page data is onboarding.progress (App/app/onboarding.py
// 125-251) as far as onboarding.html reads it; the body is the Go twin of the
// _components.html macros onboarding_welcome and onboarding_finish, drawn in
// the host layout (hostweb/layout). Nothing routes here until the owner adds
// the path to UBYHOST_GO_PATHS.

import (
	"context"
	"embed"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/palette"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

//go:embed onboardingpage/onboarding.tmpl
var onboardingPageFiles embed.FS

//go:embed onboardingpage/i18n.json
var onboardingPageJSON []byte

// onboardingPageStrings is the page catalog, written from host_i18n.py by
// App/scripts/go_host_i18n.py from onboardingpage/i18n_keys.txt.
var onboardingPageStrings = hostweb.Load(onboardingPageJSON)

// onboardingPageTemplates is parsed once; the layout clones it per request.
var onboardingPageTemplates = layout.MustParse(onboardingPageStrings, onboardingPageFiles, "onboardingpage/onboarding.tmpl")

// onboardingPageStep is one entry of progress()["steps"].
type onboardingPageStep struct {
	ID        string
	Done      bool
	URL       string
	ManualURL string
	LearnURL  string
}

// onboardingPageFinish is progress()["finish"]: the share card of a finished
// single-property workspace.
type onboardingPageFinish struct {
	ApartmentID      int64
	Name             string
	Permalink        string
	LinkKey          string
	Pin              string
	PassportPolicy   string
	CommunicationURL string
}

// onboardingPageProgress is the part of onboarding.progress the page reads.
type onboardingPageProgress struct {
	Steps     []onboardingPageStep
	Current   *onboardingPageStep
	Completed int
	Total     int
	Finished  bool
	Finish    *onboardingPageFinish
	Dismissed bool
}

// onboardingPageData is the template data: progress, the demo card switch
// (demo_available) and request.url.path for the resume form.
type onboardingPageData struct {
	P             onboardingPageProgress
	DemoAvailable bool
	Path          string
}

// onboardingPageApartment is one row of progress()'s apartments query.
type onboardingPageApartment struct {
	id             int64
	internalName   string
	fields         map[string]string // the text columns validate_apartment reads
	passwordEnc    string
	feeds          int64
	permalinkSlug  string
	permalinkToken string
	permalinkPin   string
	passportPolicy string
}

const onboardingPageApartmentsSQL = `SELECT a.id, a.internal_name,
  COALESCE(a.uby_idub, ''), COALESCE(a.uby_mark, ''), COALESCE(a.uby_name, ''), COALESCE(a.uby_contact, ''),
  COALESCE(a.addr_okres, ''), COALESCE(a.addr_obec, ''), COALESCE(a.addr_obec_cast, ''), COALESCE(a.addr_street, ''),
  COALESCE(a.addr_house_no, ''), COALESCE(a.addr_orient_no, ''), COALESCE(a.addr_zip, ''), COALESCE(a.uby_ws_user, ''),
  COALESCE(a.uby_ws_password_enc, ''),
  CASE WHEN a.legal_entity_id IS NULL THEN '' ELSE a.legal_entity_id::text END,
  CASE WHEN a.data_controller_entity_id IS NULL THEN '' ELSE a.data_controller_entity_id::text END,
  (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1),
  COALESCE((SELECT s.slug FROM apartment_slug s WHERE s.apartment_id = a.id AND s.is_current = 1 LIMIT 1), ''),
  COALESCE(a.permalink_token, ''), COALESCE(a.permalink_pin, ''), COALESCE(a.passport_photo_policy, '')
FROM apartment a
WHERE a.archived_at IS NULL AND a.owner_user_id IS NOT DISTINCT FROM $1
ORDER BY a.id`

var onboardingPageTextColumns = []string{"uby_idub", "uby_mark", "uby_name", "uby_contact", "addr_okres", "addr_obec",
	"addr_obec_cast", "addr_street", "addr_house_no", "addr_orient_no", "addr_zip", "uby_ws_user"}

// loadOnboardingPageApartments runs progress()'s apartments query.
func loadOnboardingPageApartments(ctx context.Context, pool *pgxpool.Pool, owner int64) ([]onboardingPageApartment, error) {
	rows, err := pool.Query(ctx, onboardingPageApartmentsSQL, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []onboardingPageApartment
	for rows.Next() {
		var a onboardingPageApartment
		text := make([]string, len(onboardingPageTextColumns))
		var entity, controller string
		dest := []any{&a.id, &a.internalName}
		for i := range text {
			dest = append(dest, &text[i])
		}
		dest = append(dest, &a.passwordEnc, &entity, &controller, &a.feeds, &a.permalinkSlug, &a.permalinkToken, &a.permalinkPin, &a.passportPolicy)
		if err := rows.Scan(dest...); err != nil {
			return nil, err
		}
		a.fields = make(map[string]string, len(text)+3)
		for i, k := range onboardingPageTextColumns {
			a.fields[k] = text[i]
		}
		a.fields["legal_entity_id"] = entity
		a.fields["data_controller_entity_id"] = controller
		out = append(out, a)
	}
	return out, rows.Err()
}

// onboardingPageDecrypter is db.decrypt_secret: "" for an empty token, for a
// token no data key opens and for a plain text that is not UTF-8. The data
// keys are loaded on the first token only.
type onboardingPageDecrypter struct {
	getenv func(string) string
	now    time.Time
	keys   *secure.MultiFernet
}

func (d *onboardingPageDecrypter) decrypt(token string) (string, error) {
	if token == "" {
		return "", nil
	}
	if d.keys == nil {
		keys, err := secure.LoadDataKeys(d.getenv)
		if err != nil {
			return "", err
		}
		d.keys = keys
	}
	plain, err := d.keys.Decrypt(token, 0, d.now)
	if err != nil || !utf8.Valid(plain) {
		return "", nil
	}
	return string(plain), nil
}

// loadOnboardingPageProgress is onboarding.progress(owner) for the page.
func loadOnboardingPageProgress(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now time.Time, owner int64) (onboardingPageProgress, error) {
	var p onboardingPageProgress
	var entityCount, readyEntityCount, manualStays int64
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM legal_entity WHERE owner_user_id IS NOT DISTINCT FROM $1`, owner).Scan(&entityCount); err != nil {
		return p, err
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM legal_entity
WHERE owner_user_id IS NOT DISTINCT FROM $1 AND TRIM(COALESCE(name, '')) != ''
AND TRIM(COALESCE(seat, '')) != ''
AND TRIM(COALESCE(ico, '')) != ''
AND TRIM(COALESCE(contact_email, '')) != ''`, owner).Scan(&readyEntityCount); err != nil {
		return p, err
	}
	apartments, err := loadOnboardingPageApartments(ctx, pool, owner)
	if err != nil {
		return p, err
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM reservation r
JOIN apartment a ON a.id = r.apartment_id
WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.archived_at IS NULL
AND r.status = 'active' AND r.source = 'manual'`, owner).Scan(&manualStays); err != nil {
		return p, err
	}
	var feedCount int64
	for _, a := range apartments {
		feedCount += a.feeds
	}
	hasStays := feedCount > 0 || manualStays > 0
	dec := &onboardingPageDecrypter{getenv: getenv, now: now}
	setupIssues := 0
	for _, a := range apartments {
		fields := make(map[string]string, len(a.fields)+1)
		for k, v := range a.fields {
			fields[k] = v
		}
		if fields["uby_ws_password"], err = dec.decrypt(a.passwordEnc); err != nil {
			return p, err
		}
		if len(validation.ErrorsOnly(validation.ValidateApartment(fields))) > 0 {
			setupIssues++
		}
	}
	count := len(apartments)
	var first *onboardingPageApartment
	if count > 0 {
		first = &apartments[0]
	}
	firstURL := func(suffix, fallback string) string {
		if first == nil {
			return fallback
		}
		return fmt.Sprintf("/apartments/%d%s", first.id, suffix)
	}
	propertyURL := "/entities"
	if entityCount > 0 {
		propertyURL = "/apartments/new"
	}
	p.Steps = []onboardingPageStep{
		{ID: "entity", Done: readyEntityCount > 0, URL: "/entities", LearnURL: "/guide#setup"},
		{ID: "property", Done: count > 0, URL: propertyURL, LearnURL: "/guide#setup"},
		{ID: "calendars", Done: hasStays, URL: firstURL("?view=bookings#calendars", "/apartments/new"),
			ManualURL: "/reservations#add-stay-panel", LearnURL: "/guide#stays"},
		{ID: "automation", Done: count > 0 && setupIssues == 0,
			URL: firstURL("?view=settings&section=reporting#ubyport", "/apartments/new"), LearnURL: "/guide#reporting"},
		{ID: "guest_link", Done: count > 0 && hasStays && setupIssues == 0,
			URL: firstURL("?view=settings&section=guests#communication", "/apartments"), LearnURL: "/guide#guests"},
	}
	for i := range p.Steps {
		if p.Steps[i].Done {
			p.Completed++
		} else if p.Current == nil {
			p.Current = &p.Steps[i]
		}
	}
	p.Total = len(p.Steps)
	p.Finished = p.Completed == p.Total
	// 0949: one property only; with several the card would show just the first one's link and PIN.
	if p.Finished && first != nil && count == 1 {
		token := first.permalinkSlug
		if token == "" {
			if token, err = palette.LinkKey(ctx, pool, first.id, first.internalName, first.permalinkToken); err != nil {
				return p, err
			}
		}
		policy := first.passportPolicy
		if policy == "" {
			policy = "off"
		}
		p.Finish = &onboardingPageFinish{
			ApartmentID:      first.id,
			Name:             first.internalName,
			Permalink:        hostweb.PublicBase(getenv) + "/l/" + token,
			LinkKey:          token,
			Pin:              first.permalinkPin,
			PassportPolicy:   policy,
			CommunicationURL: fmt.Sprintf("/apartments/%d?view=settings&section=guests#communication", first.id),
		}
	}
	var dismissed string
	err = pool.QueryRow(ctx, `SELECT COALESCE(value, '') FROM settings WHERE key = $1`, fmt.Sprintf("onboarding_dismissed_%d", owner)).Scan(&dismissed)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return p, err
	}
	p.Dismissed = owner != 0 && dismissed == "1"
	return p, nil
}

// onboardingPageDemoAvailable is config.UBYPORT_ENV == "mock": the value is
// os.environ.get(key, "mock").lower(), so only a missing key is mock.
func onboardingPageDemoAvailable(lookupEnv func(string) (string, bool)) bool {
	env, set := lookupEnv("UBYHOST_UBYPORT_ENV")
	if !set {
		env = "mock"
	}
	return strings.ToLower(env) == "mock"
}

// OnboardingPageHandler serves GET /onboarding (routes/onboarding.py
// onboarding_view): require_login, then onboarding.html in the host layout
// (nav dashboard, body_kind form, v2, no page header).
func OnboardingPageHandler(pool *pgxpool.Pool, getenv func(string) string, lookupEnv func(string) (string, bool), now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if h == nil {
			return
		}
		renderOnboardingPage(w, r, pool, getenv, lookupEnv, at, h)
	}
}

func renderOnboardingPage(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, lookupEnv func(string) (string, bool), at time.Time, h *session.Host) {
	p, err := loadOnboardingPageProgress(r.Context(), pool, getenv, at, h.Workspace.ID)
	if err != nil {
		serverError(w, err)
		return
	}
	data := onboardingPageData{P: p, DemoAvailable: onboardingPageDemoAvailable(lookupEnv), Path: r.URL.Path}
	page := layout.Page{
		Title:    onboardingPageStrings.T(hostweb.Lang(r), "onboarding.welcome_title", nil),
		Nav:      "dashboard",
		BodyKind: "form",
		V2:       true,
	}
	if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, h, page, onboardingPageTemplates, "onboarding", data); err != nil {
		serverError(w, err)
	}
}
