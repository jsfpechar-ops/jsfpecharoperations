package booking

// The guest's private booking page: booking_manage_page (property_page.py
// 475-533) with booking_manage.view and booking_manage.mask_email,
// day_label and deadline_label (booking_manage.py 9-76). A direct request that
// is still waiting (or expired) shows the payment details page instead
// (property_page_requested.html). The cancel button posts to
// /p/{slug}/b/{id}/{token}/cancel, which Go does not serve yet (brief 1553).

import (
	"context"
	"errors"
	"html/template"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// VisibleStatuses is booking_manage.VISIBLE.
var VisibleStatuses = []string{"paid", "cancelled", "refunded", "clash_refunded"}

func init() {
	// A data: URI built by GuestRails (our own PNG), never a request value.
	guestFuncs["dataURI"] = func(s string) template.URL { return template.URL(s) }
}

// SiteBooking is the site_booking columns the guest pages read.
type SiteBooking struct {
	ID, ApartmentID                       int64
	Status, PayMethod, DateFrom, DateTo   string
	Guests, Nights, TotalCZK, RefundedCZK int
	CleaningFeeCZK                        int
	Policy, GuestEmail, Lang              string
	PaidAt                                bool
	InvoiceID                             *int64
}

// LoadSiteBooking is booking_site.get. ok is false when there is no row.
func LoadSiteBooking(ctx context.Context, db DB, id int64) (SiteBooking, bool, error) {
	b := SiteBooking{ID: id}
	var email, paid *string
	err := db.QueryRow(ctx, `SELECT apartment_id, status, pay_method, date_from, date_to, guests, nights, total_czk,
		refunded_czk, cleaning_fee_czk, cancellation_policy, guest_email, lang, paid_at, invoice_id
		FROM site_booking WHERE id = $1`, id).Scan(&b.ApartmentID, &b.Status, &b.PayMethod, &b.DateFrom, &b.DateTo,
		&b.Guests, &b.Nights, &b.TotalCZK, &b.RefundedCZK, &b.CleaningFeeCZK, &b.Policy, &email, &b.Lang, &paid, &b.InvoiceID)
	if errors.Is(err, pgx.ErrNoRows) {
		return b, false, nil
	}
	if email != nil {
		b.GuestEmail = *email
	}
	b.PaidAt = paid != nil && *paid != ""
	return b, err == nil, err
}

// ManageView is booking_manage.view: everything booking_manage.html prints.
type ManageView struct {
	ID                        int64
	State, Sub, Tone, Name    string
	Arrive, Depart            string
	Guests, Total, Refunded   int
	Email                     string
	CityTax                   int
	Policy                    string
	Direct                    bool
	Deadline                  string
	CanCancel                 bool
	RefundNow                 int
	HasInvoice, HasCorrection bool
}

// MaskEmail is booking_manage.mask_email: "a***@domain".
func MaskEmail(email string) string {
	local, domain, found := strings.Cut(email, "@")
	if !found || local == "" || domain == "" {
		return ""
	}
	return runeSlice(local, 0, 1) + "***@" + domain
}

// DayLabel is booking_manage.day_label.
func DayLabel(iso, lang string) string {
	if lang == "cs" {
		return czDate(iso)
	}
	return iso
}

// DeadlineLabel is booking_manage.deadline_label: until when the full refund
// holds, "" for a non-refundable booking. The subtraction is on the Prague wall
// clock, as Python does with one tzinfo.
func DeadlineLabel(b SiteBooking, checkinHour int, lang string) (string, error) {
	moment, ok := CheckInMoment(b.DateFrom, checkinHour)
	if !ok {
		return "", errors.New("booking: bad date_from")
	}
	w := wall(moment)
	switch b.Policy {
	case "flexible":
		w = w.Add(-24 * time.Hour)
	case "moderate":
		w = w.Add(-5 * 24 * time.Hour)
	default:
		return "", nil
	}
	if lang == "cs" {
		return strconv.Itoa(w.Day()) + ". " + strconv.Itoa(int(w.Month())) + ". " + strconv.Itoa(w.Year()) + " " + w.Format("15:04"), nil
	}
	return w.Format("2006-01-02 15:04"), nil
}

// Started is booking_cancel.started: check-in has begun (instants, not wall).
func Started(b SiteBooking, checkinHour int, now time.Time) (bool, error) {
	moment, ok := CheckInMoment(b.DateFrom, checkinHour)
	if !ok {
		return false, errors.New("booking: bad date_from")
	}
	return !moment.After(now), nil
}

// BuildManageView is booking_manage.view.
func BuildManageView(ctx context.Context, db DB, b SiteBooking, lang string, now time.Time) (ManageView, error) {
	s, err := LoadSettings(ctx, db, b.ApartmentID)
	if err != nil {
		return ManageView{}, err
	}
	var name string
	err = db.QueryRow(ctx, `SELECT internal_name FROM apartment WHERE id = $1`, b.ApartmentID).Scan(&name)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return ManageView{}, err
	}
	state, sub := b.Status, b.Status
	direct := b.PayMethod == "direct"
	if direct && b.Status == "cancelled" {
		state, sub = "declined", "declined"
		if b.PaidAt {
			state, sub = "cancelled", "cancelled_direct"
		}
	}
	started, err := Started(b, s.CheckinHour, now)
	if err != nil {
		return ManageView{}, err
	}
	canCancel := b.Status == "paid" && !direct && !started
	v := ManageView{ID: b.ID, State: state, Sub: sub, Tone: "neutral", Name: name,
		Arrive: DayLabel(b.DateFrom, lang), Depart: DayLabel(b.DateTo, lang), Guests: b.Guests, Total: b.TotalCZK,
		Refunded: b.RefundedCZK, Email: MaskEmail(b.GuestEmail), CityTax: s.CityTaxCZK * b.Guests * b.Nights,
		Policy: b.Policy, Direct: direct, CanCancel: canCancel, HasInvoice: b.InvoiceID != nil && *b.InvoiceID != 0}
	if b.Status == "paid" {
		v.Tone = "done"
	}
	if v.Deadline, err = DeadlineLabel(b, s.CheckinHour, lang); err != nil {
		return ManageView{}, err
	}
	if canCancel {
		if v.RefundNow, err = RefundCZK(RefundBooking{TotalCZK: b.TotalCZK, RefundedCZK: b.RefundedCZK, CleaningFeeCZK: b.CleaningFeeCZK,
			DateFrom: b.DateFrom, CancellationPolicy: b.Policy}, s.CheckinHour, now, false); err != nil {
			return ManageView{}, err
		}
	}
	if v.HasInvoice {
		var one int64
		err := db.QueryRow(ctx, `SELECT id FROM invoice WHERE corrects_invoice_id = $1 LIMIT 1`, *b.InvoiceID).Scan(&one)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return ManageView{}, err
		}
		v.HasCorrection = err == nil
	}
	return v, nil
}

// ManageData is the Data of the two templates.
type ManageData struct {
	Slug, Token string
	V           ManageView
	Error       string
	// The requested page:
	PageName string
	Rails    []GuestRail
	Dates    string
	Total    int
	Expired  bool
}

// BookingForToken is _booking_or_none: nil unless the token is the booking's
// signed token and the booking may be shown (direct requests too when
// openRequests).
func BookingForToken(ctx context.Context, db DB, secret string, id int64, token string, openRequests bool) (*SiteBooking, error) {
	if !ManageTokenOK(secret, id, token) {
		return nil, nil
	}
	b, ok, err := LoadSiteBooking(ctx, db, id)
	if err != nil || !ok {
		return nil, err
	}
	if openRequests && b.PayMethod == "direct" && (b.Status == "requested" || b.Status == "expired") {
		return &b, nil
	}
	if !contains(VisibleStatuses, b.Status) {
		return nil, nil
	}
	return &b, nil
}

func manageLang(r *http.Request, b SiteBooking) string {
	if v := r.URL.Query()["lang"]; len(v) > 0 && (v[len(v)-1] == "cs" || v[len(v)-1] == "en") {
		return v[len(v)-1]
	}
	if b.Lang == "cs" || b.Lang == "en" {
		return b.Lang
	}
	return "cs"
}

// ManageHandler serves GET /p/{slug}/b/{booking_id}/{token}.
func ManageHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, qr func(string) (string, error)) http.HandlerFunc {
	manage := newSet("manage.tmpl")
	requested := newSet("requested.tmpl")
	noStore := map[string]string{"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		if limited(w, r, pool, scopeManage, at) {
			return
		}
		ctx := r.Context()
		id, err := strconv.ParseInt(r.PathValue("booking_id"), 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		secret, err := secure.LoadSecret(getenv)
		if err != nil {
			serverError(w, "manage secret", err)
			return
		}
		b, err := BookingForToken(ctx, pool, secret, id, r.PathValue("token"), true)
		if err != nil {
			serverError(w, "manage booking", err)
			return
		}
		if b == nil {
			http.NotFound(w, r)
			return
		}
		lang := manageLang(r, *b)
		slug, token := r.PathValue("slug"), r.PathValue("token")
		if b.PayMethod == "direct" && (b.Status == "requested" || b.Status == "expired") {
			pg, err := LoadPage(ctx, pool, getenv, b.ApartmentID)
			if err != nil {
				serverError(w, "manage page", err)
				return
			}
			rails, err := GuestRails(ctx, pool, b.ApartmentID, b.ID, b.TotalCZK, qr)
			if err != nil {
				serverError(w, "manage rails", err)
				return
			}
			name := ""
			if pg != nil {
				name = pg.Name
			}
			g := Guest{Lang: lang, Data: ManageData{Slug: slug, Token: token, PageName: name, Rails: rails,
				Dates: DayLabel(b.DateFrom, lang) + " – " + DayLabel(b.DateTo, lang), Total: b.TotalCZK, Expired: b.Status == "expired"}}
			g.Title = g.T("pp.book.req_title")
			writeGuest(w, r, requested, http.StatusOK, g, noStore)
			return
		}
		v, err := BuildManageView(ctx, pool, *b, lang, at)
		if err != nil {
			serverError(w, "manage view", err)
			return
		}
		e := r.URL.Query().Get("e")
		if e != "started" && e != "busy" && e != "refund_failed" {
			e = ""
		}
		g := Guest{Lang: lang, Data: ManageData{Slug: slug, Token: token, V: v, Error: e}}
		g.Title = g.T("bk.h1."+v.State) + " · " + v.Name
		writeGuest(w, r, manage, http.StatusOK, g, noStore)
	}
}
