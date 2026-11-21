package guest

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// EntityContact is legal_entity row fields used on the privacy page.
type EntityContact struct {
	Name, Seat, ICO, Email, Phone string
}

// SoftwareOperator is operator.py details() for guest privacy copy.
type SoftwareOperator struct {
	Name, ICO, Address, Email string
}

func softwareOperator(getenv func(string) string) SoftwareOperator {
	return SoftwareOperator{
		Name:    strings.TrimSpace(getenv("UBYHOST_OPERATOR_NAME")),
		ICO:     strings.TrimSpace(getenv("UBYHOST_OPERATOR_ICO")),
		Address: strings.TrimSpace(getenv("UBYHOST_OPERATOR_ADDRESS")),
		Email:   billingjob.OperatorEmail(),
	}
}

func noticeVersion(getenv func(string) string) string {
	v := strings.TrimSpace(getenv("UBYHOST_GUEST_NOTICE_VERSION"))
	if v == "" {
		return "1.0"
	}
	return v
}

func entityDetails(ctx context.Context, pool *pgxpool.Pool, id *int64) EntityContact {
	if id == nil || *id <= 0 {
		return EntityContact{}
	}
	var e EntityContact
	err := pool.QueryRow(ctx,
		`SELECT COALESCE(name,''), COALESCE(seat,''), COALESCE(ico,''),
			COALESCE(contact_email,''), COALESCE(contact_phone,'')
		 FROM legal_entity WHERE id = $1`, *id).
		Scan(&e.Name, &e.Seat, &e.ICO, &e.Email, &e.Phone)
	if err == pgx.ErrNoRows || err != nil {
		return EntityContact{}
	}
	return e
}

func controller(ctx context.Context, pool *pgxpool.Pool, apt *Apartment) EntityContact {
	if apt == nil {
		return EntityContact{}
	}
	if apt.DataControllerEntityID != nil && *apt.DataControllerEntityID > 0 {
		return entityDetails(ctx, pool, apt.DataControllerEntityID)
	}
	return entityDetails(ctx, pool, &apt.LegalEntityID)
}

func hostContact(ctx context.Context, pool *pgxpool.Pool, apt *Apartment) EntityContact {
	if apt == nil || apt.LegalEntityID <= 0 {
		return EntityContact{}
	}
	return entityDetails(ctx, pool, &apt.LegalEntityID)
}

func hostMessageURL(apt *Apartment, host EntityContact) string {
	if host.Email != "" {
		subject := DisplayName(apt)
		u := "mailto:" + host.Email
		if subject != "" {
			u += "?subject=" + url.QueryEscape(subject)
		}
		return u
	}
	if host.Phone != "" {
		return "tel:" + strings.ReplaceAll(host.Phone, " ", "")
	}
	return ""
}

func sharedPage(r *http.Request, token, lang string, apt *Apartment, getenv func(string) string, pool *pgxpool.Pool) Page {
	lang = GuestLanguage(lang)
	p := Page{
		Lang:            lang,
		Token:           token,
		LangURLs:        LangURLs(r, ""),
		PrivacyURL:      GuestLink(token, 0, "/privacy") + LangQuery(lang, ""),
		GuestEndonyms:   GuestEndonyms,
		LoadSignatureJS: true,
	}
	if apt != nil {
		p.Facility = Facility(apt)
		p.FacilityTone = int(apt.ID % 10)
		host := hostContact(r.Context(), pool, apt)
		p.Host = HostContact{Name: host.Name, Email: host.Email, Phone: host.Phone}
	}
	return p
}

// requirePin is guest.py _require_pin. When it returns non-nil, the route must stop.
func requirePin(w http.ResponseWriter, r *http.Request, d shellDeps, token, lang string, apt *Apartment) bool {
	if !guestPinRequired(d.getenv) {
		return false
	}
	if apt == nil {
		return false
	}
	expected := strings.TrimSpace(apt.PermalinkPIN)
	lockToken := apt.PermalinkToken
	if lockToken == "" {
		lockToken = token
	}
	if PinSessionValid(r, d.getenv, lockToken, expected, d.now()) {
		return false
	}
	now := d.now()
	pv, csrfCookie, err := sharedPinPage(r, d.pool, d.getenv, token, lang, apt, now)
	if err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return true
	}
	pv.ReturnTo = r.URL.Path
	if r.URL.RawQuery != "" {
		pv.ReturnTo += "?" + r.URL.RawQuery
	}
	WithLang(w, d.getenv, GuestLanguage(lang))
	writePinPage(w, r, http.StatusOK, pv, nil, csrfCookie, GuestLanguage(lang))
	return true
}

func loadApartmentDetail(ctx context.Context, pool *pgxpool.Pool, column, value string) (*Apartment, bool) {
	q := fmt.Sprintf(`SELECT id, COALESCE(internal_name,''), COALESCE(uby_name,''), COALESCE(city_en,''),
		COALESCE(permalink_token,''), COALESCE(permalink_pin,''),
		COALESCE(passport_photo_policy,''), COALESCE(lock_provider,''), owner_user_id,
		legal_entity_id, data_controller_entity_id
		FROM apartment WHERE %s = $1 AND active = 1 AND archived_at IS NULL`, column)
	var a Apartment
	var legal, ctrl *int64
	err := pool.QueryRow(ctx, q, value).Scan(
		&a.ID, &a.InternalName, &a.UbyName, &a.CityEn, &a.PermalinkToken, &a.PermalinkPIN,
		&a.PassportPhotoPolicy, &a.LockProvider, &a.OwnerUserID, &legal, &ctrl)
	if legal != nil {
		a.LegalEntityID = *legal
	}
	if err == pgx.ErrNoRows {
		return nil, false
	}
	if err != nil {
		return nil, false
	}
	a.DataControllerEntityID = ctrl
	return &a, true
}

func mailEnabled(getenv func(string) string) bool {
	b := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	return b == "console" || b == "ses"
}

// mintGuestPageCSRF sets CSRF cookie when rendering HTML guest pages.
func mintGuestPageCSRF(w http.ResponseWriter, r *http.Request, getenv func(string) string, now time.Time) (string, error) {
	secret, err := secure.LoadSecret(getenv)
	if err != nil {
		return "", err
	}
	token, cookie, err := guestCSRF(r, secret, getenv, now)
	if cookie != nil {
		http.SetCookie(w, cookie)
	}
	return token, err
}
