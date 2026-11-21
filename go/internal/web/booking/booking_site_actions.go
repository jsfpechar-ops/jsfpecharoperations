package booking

// Host POST routes for booking-site pay, confirm, decline and cancel (brief 1710d).
// Python: payments.py booking_site_pay, _direct_action, booking_site_cancel.

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed booking_site_host_i18n.json
var bookingSiteHostI18nJSON []byte

var bookingSiteHostCatalog = hostweb.Load(bookingSiteHostI18nJSON)

type siteActionsServer struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
	hook   *payments.BookingWebhook
}

// RegisterBookingSiteActions registers the four POST host routes (dormant until UBYHOST_GO_PATHS).
func RegisterBookingSiteActions(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	s := &siteActionsServer{
		pool: pool, getenv: getenv, now: now,
		hook: payments.WebhookForHost(pool, getenv, now),
	}
	id := "POST /apartments/{apartment_id}/booking-site/pay"
	mux.Handle(id, wrap(id, s.payRails()))
	id = "POST /apartments/{apartment_id}/booking-site/confirm"
	mux.Handle(id, wrap(id, s.directAction("confirm")))
	id = "POST /apartments/{apartment_id}/booking-site/decline"
	mux.Handle(id, wrap(id, s.directAction("decline")))
	id = "POST /apartments/{apartment_id}/booking-site/cancel"
	mux.Handle(id, wrap(id, s.cancelBooking()))
}

func (s *siteActionsServer) flash(lang, key string) hostweb.Flash {
	text := bookingSiteHostCatalog.T(lang, key, nil)
	if text == key {
		text = hostweb.HostStrings.T(lang, key, nil)
	}
	return hostweb.Flash{Text: text, Key: key}
}

func parseSiteApartmentID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue("apartment_id"), 10, 64)
	if err != nil {
		http.NotFound(w, r)
		return 0, false
	}
	return id, true
}

func (s *siteActionsServer) enterPost(w http.ResponseWriter, r *http.Request) (*session.Host, int64, bool) {
	at := s.now()
	if !hostweb.CSRF(w, r, s.getenv, at) {
		return nil, 0, false
	}
	_ = r.ParseForm()
	aptID, ok := parseSiteApartmentID(w, r)
	if !ok {
		return nil, 0, false
	}
	h, err := hostweb.Login(w, r, s.pool, s.getenv, at)
	if err != nil {
		siteActionsError(w, err)
		return nil, 0, false
	}
	if h == nil {
		return nil, 0, false
	}
	ctx := r.Context()
	owns, err := s.ownApartment(ctx, h.Workspace.ID, aptID)
	if err != nil {
		siteActionsError(w, err)
		return nil, 0, false
	}
	if !owns {
		http.NotFound(w, r)
		return nil, 0, false
	}
	return h, aptID, true
}

func (s *siteActionsServer) ownApartment(ctx context.Context, ownerID, apartmentID int64) (bool, error) {
	var one int
	err := s.pool.QueryRow(ctx, `SELECT 1 FROM apartment WHERE id = $1 AND owner_user_id = $2`, apartmentID, ownerID).Scan(&one)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	return err == nil, err
}

func siteActionsError(w http.ResponseWriter, err error) {
	log.Printf("booking_site_actions: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

func bsiteBack(w http.ResponseWriter, r *http.Request, apartmentID int64, msg hostweb.Flash) {
	hostweb.Back(w, r, fmt.Sprintf("/apartments/%d/booking-site", apartmentID), msg, hostweb.Flash{})
}

func bsiteBackHash(w http.ResponseWriter, r *http.Request, apartmentID int64, hash string, msg hostweb.Flash) {
	hostweb.Back(w, r, fmt.Sprintf("/apartments/%d/booking-site%s", apartmentID, hash), msg, hostweb.Flash{})
}

func (s *siteActionsServer) requireMax(ctx context.Context, w http.ResponseWriter, r *http.Request, ownerID, aptID int64, lang string) bool {
	ok, err := SiteAllowed(ctx, s.pool, s.getenv, ownerID)
	if err != nil {
		siteActionsError(w, err)
		return false
	}
	if !ok {
		hostweb.Back(w, r, fmt.Sprintf("/apartments/%d/booking-site", aptID), hostweb.Flash{}, s.flash(lang, "bsite.err.not_max"))
		return false
	}
	return true
}

func (s *siteActionsServer) payRails() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h, aptID, ok := s.enterPost(w, r)
		if !ok {
			return
		}
		lang := hostweb.Lang(r)
		ctx := r.Context()
		if !s.requireMax(ctx, w, r, h.Workspace.ID, aptID, lang) {
			return
		}
		var curDefault *string
		err := s.pool.QueryRow(ctx, `SELECT stay_fee_guest_default_rail FROM apartment WHERE id = $1`, aptID).Scan(&curDefault)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			siteActionsError(w, err)
			return
		}
		def := ""
		if curDefault != nil {
			def = *curDefault
		}
		vals, err := ParseRailsForm(ctx, s.pool, aptID, r.PostForm["rails"], r.PostFormValue("revolut_link"),
			r.PostFormValue("cash_note"), def)
		if err != nil {
			bsiteBackHash(w, r, aptID, "#pay", s.flash(lang, "bsite.err."+err.Error()))
			return
		}
		q := `UPDATE apartment SET stay_fee_guest_rails = $1, updated_at = $2`
		args := []any{vals.Rails, StampAt(s.now())}
		if vals.RevolutLink != nil {
			args = append(args, *vals.RevolutLink)
			q += fmt.Sprintf(`, stay_fee_guest_revolut_link = $%d`, len(args))
		}
		if vals.CashNote != nil {
			args = append(args, *vals.CashNote)
			q += fmt.Sprintf(`, stay_fee_guest_cash_note = $%d`, len(args))
		} else if len(r.PostForm["rails"]) > 0 {
			q += `, stay_fee_guest_cash_note = NULL`
		}
		if vals.DefaultRail != nil {
			args = append(args, *vals.DefaultRail)
			q += fmt.Sprintf(`, stay_fee_guest_default_rail = $%d`, len(args))
		}
		args = append(args, aptID)
		q += fmt.Sprintf(` WHERE id = $%d`, len(args))
		if _, err := s.pool.Exec(ctx, q, args...); err != nil {
			siteActionsError(w, err)
			return
		}
		bsiteBack(w, r, aptID, s.flash(lang, "payments.page.saved"))
	}
}

func (s *siteActionsServer) directAction(which string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h, aptID, ok := s.enterPost(w, r)
		if !ok {
			return
		}
		lang := hostweb.Lang(r)
		raw := r.PostFormValue("booking_id")
		bid, err := strconv.ParseInt(raw, 10, 64)
		if err != nil || bid <= 0 {
			http.NotFound(w, r)
			return
		}
		ctx := r.Context()
		var rowApt int64
		err = s.pool.QueryRow(ctx, `SELECT apartment_id FROM site_booking WHERE id = $1`, bid).Scan(&rowApt)
		if errors.Is(err, pgx.ErrNoRows) || rowApt != aptID {
			http.NotFound(w, r)
			return
		}
		if err != nil {
			siteActionsError(w, err)
			return
		}
		var code string
		switch which {
		case "confirm":
			code = s.hook.HostConfirmDirect(ctx, bid, h.Workspace.ID)
		default:
			code = s.hook.HostDeclineDirect(ctx, bid, h.Workspace.ID)
		}
		if code == "not_found" {
			http.NotFound(w, r)
			return
		}
		if code == "taken" {
			bsiteBack(w, r, aptID, s.flash(lang, "bsite.err.direct_taken"))
			return
		}
		if code != "" {
			bsiteBack(w, r, aptID, s.flash(lang, "bsite.err.not_cancellable"))
			return
		}
		key := "bsite.flash.direct_decline"
		if which == "confirm" {
			key = "bsite.flash.direct_confirm"
		}
		bsiteBack(w, r, aptID, s.flash(lang, key))
	}
}

func (s *siteActionsServer) cancelBooking() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		h, aptID, ok := s.enterPost(w, r)
		if !ok {
			return
		}
		lang := hostweb.Lang(r)
		raw := r.PostFormValue("booking_id")
		bid, err := strconv.ParseInt(raw, 10, 64)
		if err != nil || bid <= 0 {
			http.NotFound(w, r)
			return
		}
		ctx := r.Context()
		var rowApt, owner int64
		var payMethod string
		err = s.pool.QueryRow(ctx, `SELECT apartment_id, owner_user_id, pay_method FROM site_booking WHERE id = $1`, bid).
			Scan(&rowApt, &owner, &payMethod)
		if errors.Is(err, pgx.ErrNoRows) || rowApt != aptID || owner != h.Workspace.ID {
			http.NotFound(w, r)
			return
		}
		if err != nil {
			siteActionsError(w, err)
			return
		}
		code, _ := s.hook.HostCancelByHost(ctx, bid, h.Workspace.ID)
		if code == "not_found" {
			http.NotFound(w, r)
			return
		}
		if code == "refund_failed" {
			bsiteBack(w, r, aptID, s.flash(lang, "bsite.err.cancel_failed"))
			return
		}
		if code != "" {
			bsiteBack(w, r, aptID, s.flash(lang, "bsite.err.not_cancellable"))
			return
		}
		key := "bsite.flash.cancelled"
		if payMethod == "direct" {
			key = "bsite.flash.cancelled_direct"
		}
		bsiteBack(w, r, aptID, s.flash(lang, key))
	}
}
