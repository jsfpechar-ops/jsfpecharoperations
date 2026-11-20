package booking

// Host booking-site setup (brief 1710c): GET/POST /apartments/{id}/booking-site.
// Python: App/app/routes/payments.py booking_site_setup, booking_site_save.

import (
	"context"
	"embed"
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
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed booking_site_setup_i18n.json
var bookingSiteSetupI18nJSON []byte

//go:embed templates/booking_site_setup.tmpl
var bookingSiteSetupFS embed.FS

var (
	bookingSiteCatalog = hostweb.Load(bookingSiteSetupI18nJSON)
	bookingSiteSetup   = layout.MustParseFuncs(bookingSiteCatalog, nil, bookingSiteSetupFS, "templates/booking_site_setup.tmpl")
)

type siteSetupServer struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

type noticeOption struct {
	Value string
	Label string
}

// SetupPageData is the template context when site_allowed.
type SetupPageData struct {
	Allowed     bool
	ApartmentID int64
	Apartment   string
	Settings    Settings
	Steps       []SetupStep
	StepsDone   int
	StepsTitle  string
	Policies    []string
	CanPublish  bool
	Published   bool
	PageURL     string
	ICalURL     string
	QR          string
	NoticeValue string
	NoticeOpts  []noticeOption
	Pay         PaySetupView
	Bookings    []HostBookingRow
}

func parseApartmentID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue("apartment_id"), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return 0, false
	}
	return id, true
}

// RegisterBookingSiteSetup registers GET/POST booking-site (dormant until UBYHOST_GO_PATHS).
func RegisterBookingSiteSetup(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	s := &siteSetupServer{pool: pool, getenv: getenv, now: now}
	mux.Handle("GET /apartments/{apartment_id}/booking-site", wrap("/apartments/{apartment_id}/booking-site", s.get()))
	mux.Handle("POST /apartments/{apartment_id}/booking-site", wrap("/apartments/{apartment_id}/booking-site", s.post()))
}

func (s *siteSetupServer) flash(lang, key string) hostweb.Flash {
	text := bookingSiteCatalog.T(lang, key, nil)
	if text == key {
		text = hostweb.HostStrings.T(lang, key, nil)
	}
	return hostweb.Flash{Text: text, Key: key}
}

func (s *siteSetupServer) login(w http.ResponseWriter, r *http.Request, at time.Time) (*session.Host, bool) {
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		siteSetupError(w, err)
		return nil, false
	}
	return h, h != nil
}

func siteSetupError(w http.ResponseWriter, err error) {
	log.Printf("booking booking_site_setup: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

func (s *siteSetupServer) ownApartment(ctx context.Context, ownerID, apartmentID int64) (string, bool, error) {
	var name string
	err := s.pool.QueryRow(ctx, `SELECT internal_name FROM apartment WHERE id = $1 AND owner_user_id = $2`,
		apartmentID, ownerID).Scan(&name)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", false, nil
	}
	return name, err == nil, err
}

func siteSetupBack(w http.ResponseWriter, r *http.Request, apartmentID int64, msg, err hostweb.Flash) {
	hostweb.Back(w, r, fmt.Sprintf("/apartments/%d/booking-site", apartmentID), msg, err)
}

func (s *siteSetupServer) buildPage(ctx context.Context, r *http.Request, ownerID, aptID int64, name string, at time.Time) (SetupPageData, error) {
	allowed, err := SiteAllowed(ctx, s.pool, s.getenv, ownerID)
	if err != nil {
		return SetupPageData{}, err
	}
	out := SetupPageData{Allowed: allowed, ApartmentID: aptID, Apartment: name}
	if !allowed {
		return out, nil
	}
	settings, err := LoadSettings(ctx, s.pool, aptID)
	if err != nil {
		return SetupPageData{}, err
	}
	slug, err := EnsureSlug(ctx, s.pool, aptID, at)
	if err != nil {
		return SetupPageData{}, err
	}
	base := strings.TrimRight(hostweb.PublicBase(s.getenv), "/")
	pageURL := base + "/p/" + slug
	steps, err := SetupSteps(ctx, s.pool, s.getenv, aptID, ownerID, at)
	if err != nil {
		return SetupPageData{}, err
	}
	token, err := ICalToken(ctx, s.pool, aptID)
	if err != nil {
		return SetupPageData{}, err
	}
	qr, err := payments.QRDataURI(pageURL)
	if err != nil {
		return SetupPageData{}, err
	}
	pay, err := SetupView(ctx, s.pool, aptID)
	if err != nil {
		return SetupPageData{}, err
	}
	bookings, err := HostRows(ctx, s.pool, aptID, 20)
	if err != nil {
		return SetupPageData{}, err
	}
	lang := hostweb.Lang(r)
	opts := make([]noticeOption, len(NoticeOptions))
	for i, v := range NoticeOptions {
		key := "bsite.notice." + strings.NewReplacer(":", "_", " ", "_").Replace(v)
		opts[i] = noticeOption{Value: v, Label: bookingSiteCatalog.T(lang, key, nil)}
	}
	published := false
	for _, row := range steps {
		if row.Key == "publish" && row.Done {
			published = true
			break
		}
	}
	out.Settings = settings
	out.Steps = steps
	out.StepsDone = stepsDoneCount(steps)
	out.StepsTitle = bookingSiteCatalog.T(lang, "bsite.steps.title", map[string]any{"done": out.StepsDone})
	out.Policies = Policies
	out.CanPublish = CanPublish(steps)
	out.Published = published
	out.PageURL = pageURL
	out.ICalURL = pageURL + "/" + token + ".ics"
	out.QR = qr
	out.NoticeValue = NoticeValue(settings)
	out.NoticeOpts = opts
	out.Pay = pay
	out.Bookings = bookings
	return out, nil
}

func (s *siteSetupServer) get() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := s.now()
		h, ok := s.login(w, r, at)
		if !ok {
			return
		}
		aptID, ok := parseApartmentID(w, r)
		if !ok {
			return
		}
		name, found, err := s.ownApartment(r.Context(), h.Workspace.ID, aptID)
		if err != nil {
			siteSetupError(w, err)
			return
		}
		if !found {
			http.NotFound(w, r)
			return
		}
		data, err := s.buildPage(r.Context(), r, h.Workspace.ID, aptID, name, at)
		if err != nil {
			siteSetupError(w, err)
			return
		}
		lang := hostweb.Lang(r)
		title := bookingSiteCatalog.T(lang, "bsite.title", nil) + " · " + name
		env := layout.Env{Pool: s.pool, Getenv: s.getenv, Now: at}
		p := layout.Page{Title: title, Nav: "booking_sites", BodyKind: "form", V2: true,
			BackURL: fmt.Sprintf("/apartments/%d/page", aptID)}
		w.Header().Set("Cache-Control", "no-store, private")
		if err := layout.Render(w, r, env, h, p, bookingSiteSetup, "booking_site_setup", data); err != nil {
			siteSetupError(w, err)
		}
	}
}

func (s *siteSetupServer) enterPost(w http.ResponseWriter, r *http.Request) (*session.Host, int64, bool) {
	at := s.now()
	if !hostweb.CSRF(w, r, s.getenv, at) {
		return nil, 0, false
	}
	h, ok := s.login(w, r, at)
	if !ok {
		return nil, 0, false
	}
	aptID, ok := parseApartmentID(w, r)
	if !ok {
		return nil, 0, false
	}
	if err := r.ParseForm(); err != nil {
		siteSetupError(w, err)
		return nil, 0, false
	}
	_, found, err := s.ownApartment(r.Context(), h.Workspace.ID, aptID)
	if err != nil {
		siteSetupError(w, err)
		return nil, 0, false
	}
	if !found {
		http.NotFound(w, r)
		return nil, 0, false
	}
	return h, aptID, true
}

func (s *siteSetupServer) post() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h, aptID, ok := s.enterPost(w, r)
		if !ok {
			return
		}
		lang := hostweb.Lang(r)
		ctx := r.Context()
		at := s.now()
		allowed, err := SiteAllowed(ctx, s.pool, s.getenv, h.Workspace.ID)
		if err != nil {
			siteSetupError(w, err)
			return
		}
		if !allowed {
			siteSetupBack(w, r, aptID, hostweb.Flash{}, s.flash(lang, "bsite.err.not_max"))
			return
		}
		form := r.PostForm
		switch {
		case len(form["ical_done"]) > 0:
			if err := MarkICalDone(ctx, s.pool, aptID); err != nil {
				siteSetupError(w, err)
				return
			}
			siteSetupBack(w, r, aptID, s.flash(lang, "bsite.flash.ical_done"), hostweb.Flash{})
			return
		case form.Get("publish") != "" || form.Get("unpublish") != "":
			pub := form.Get("publish") != ""
			if pub {
				steps, err := SetupSteps(ctx, s.pool, s.getenv, aptID, h.Workspace.ID, at)
				if err != nil {
					siteSetupError(w, err)
					return
				}
				if !CanPublish(steps) {
					done := map[string]bool{}
					for _, row := range steps {
						done[row.Key] = row.Done
					}
					key := "bsite.err.publish_need_page"
					if done["page"] {
						key = "bsite.err.publish_not_ready"
					}
					siteSetupBack(w, r, aptID, hostweb.Flash{}, s.flash(lang, key))
					return
				}
			}
			if err := PublishPage(ctx, s.pool, aptID, pub, at); err != nil {
				siteSetupError(w, err)
				return
			}
			key := "bsite.flash.unpublished"
			if pub {
				key = "bsite.flash.published"
			}
			siteSetupBack(w, r, aptID, s.flash(lang, key), hostweb.Flash{})
			return
		}
		values, err := ParseSetupForm(form)
		if err != nil {
			field := SetupFormError(err.Error())
			siteSetupBack(w, r, aptID, hostweb.Flash{}, s.flash(lang, "bsite.err."+field))
			return
		}
		if _, err := SaveSettings(ctx, s.pool, aptID, values, at); err != nil {
			field := SetupFormError(err.Error())
			siteSetupBack(w, r, aptID, hostweb.Flash{}, s.flash(lang, "bsite.err."+field))
			return
		}
		siteSetupBack(w, r, aptID, s.flash(lang, "bsite.flash.saved"), hostweb.Flash{})
	}
}
