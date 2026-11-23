package guest

// Brief 1722: POST party size, lead headcount change, add another guest slot.

import (
	"context"
	"errors"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
)

const maxGuests = 60
const maxLeadChanges = 6

const (
	codeSaved        = "saved"
	codeUnchanged    = "unchanged"
	codeHostSet      = "host_set"
	codeStayGone     = "stay_gone"
	codeOutOfRange   = "out_of_range"
	codeAboveCeiling = "above_ceiling"
	codeBelowFloor   = "below_floor"
	codeAfterCutoff  = "after_cutoff"
	codeLowered      = "lowered"
	codeRestored     = "restored"
	codeStale        = "stale"
	codeTooMany      = "too_many"
	codeFeatureOff   = "feature_off"
)

var acceptedDeclared = map[string]bool{codeSaved: true, codeUnchanged: true, codeHostSet: true}

type partyDeps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

// RegisterParty wires the three guest POST routes (dormant until UBYHOST_GO_PATHS).
func RegisterParty(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler) {
	d := partyDeps{pool: pool, getenv: getenv, now: now}
	mux.Handle("POST /l/{token}/{reservation_id}/party", wrap("POST /l/{token}/{reservation_id}/party", WithPOSTCSRF(getenv, now, partySizeHandler(d))))
	mux.Handle("POST /l/{token}/{reservation_id}/count", wrap("POST /l/{token}/{reservation_id}/count", WithPOSTCSRF(getenv, now, leadCountHandler(d))))
	mux.Handle("POST /l/{token}/{reservation_id}/another", wrap("POST /l/{token}/{reservation_id}/another", WithPOSTCSRF(getenv, now, addAnotherHandler(d))))
}

func parsePartyPath(w http.ResponseWriter, r *http.Request) (token string, resID int64, ok bool) {
	token = strings.TrimSpace(r.PathValue("token"))
	resID, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
	if token == "" || err != nil {
		http.NotFound(w, r)
		return "", 0, false
	}
	return token, resID, true
}

func headcountLeadLive(getenv func(string) string) bool {
	v := strings.TrimSpace(strings.ToLower(getenv("UBYHOST_HEADCOUNT_LEAD_LIVE")))
	return v == "1" || v == "true" || v == "yes" || v == "on"
}

func partyMailEnabled(getenv func(string) string) bool {
	v := strings.TrimSpace(strings.ToLower(getenv("UBYHOST_MAIL_ENABLED")))
	if v == "0" || v == "false" || v == "no" || v == "off" {
		return false
	}
	return getenv("UBYHOST_SMTP_HOST") != "" || getenv("AWS_SES_REGION") != ""
}

// redirectGuest is guest.py _with_lang(RedirectResponse(...)): the language
// rides in the URL and is remembered in the cookie.
func redirectGuest(w http.ResponseWriter, r *http.Request, loc, lang string) {
	if lang != "" {
		WithLang(w, getenvOr(nil), lang)
	}
	http.Redirect(w, r, loc, http.StatusSeeOther)
}

type partyStay struct {
	id, apartmentID, ownerID int64
	status                   string
	archivedAt               string
	override                 *int64
	declared                 *int64
	reduced                  *int64
	dateFrom                 string
	checkinHour              string
	leadChanges              int64
	leadReducedFrom          *int64
}

func (d partyDeps) loadPartyStay(ctx context.Context, token string, resID int64) (*partyStay, bool, error) {
	var s partyStay
	err := d.pool.QueryRow(ctx, `SELECT r.id, r.apartment_id, COALESCE(a.owner_user_id,0),
		COALESCE(r.status,''), COALESCE(r.archived_at::text,''),
		r.expected_guests_override, r.declared_guests, r.lead_reduced_guests,
		COALESCE(r.date_from::text,''), COALESCE(a.checkin_hour::text,''),
		COALESCE(r.lead_reduced_changes,0), r.lead_reduced_from
		FROM reservation r
		JOIN apartment a ON a.id = r.apartment_id
		WHERE r.id = $1 AND a.permalink_token = $2`,
		resID, token).Scan(&s.id, &s.apartmentID, &s.ownerID, &s.status, &s.archivedAt,
		&s.override, &s.declared, &s.reduced, &s.dateFrom, &s.checkinHour, &s.leadChanges, &s.leadReducedFrom)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, false, nil
	}
	return &s, err == nil, err
}

func (s partyStay) gone() bool {
	return s.status != "active" || s.archivedAt != ""
}

type rowQuerier interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}

func liveGuestRows(ctx context.Context, q rowQuerier, resID int64) (int, error) {
	var n int
	err := q.QueryRow(ctx, `SELECT COUNT(*)::int FROM guest WHERE reservation_id = $1 AND archived_at IS NULL`, resID).Scan(&n)
	return n, err
}

func expectedCount(s partyStay) *int64 {
	return headcount.Expected(s.override, s.declared, s.reduced)
}

func (d partyDeps) applyDeclared(ctx context.Context, resID int64, count int) (string, error) {
	tx, err := d.pool.Begin(ctx)
	if err != nil {
		return "", err
	}
	defer tx.Rollback(ctx)
	var s partyStay
	err = tx.QueryRow(ctx, `SELECT r.id, r.apartment_id, COALESCE(a.owner_user_id,0),
		COALESCE(r.status,''), COALESCE(r.archived_at::text,''),
		r.expected_guests_override, r.declared_guests, r.lead_reduced_guests,
		COALESCE(r.date_from::text,''), COALESCE(a.checkin_hour::text,''),
		COALESCE(r.lead_reduced_changes,0), r.lead_reduced_from
		FROM reservation r
		JOIN apartment a ON a.id = r.apartment_id
		WHERE r.id = $1 FOR UPDATE OF r`, resID).Scan(&s.id, &s.apartmentID, &s.ownerID, &s.status, &s.archivedAt,
		&s.override, &s.declared, &s.reduced, &s.dateFrom, &s.checkinHour, &s.leadChanges, &s.leadReducedFrom)
	if errors.Is(err, pgx.ErrNoRows) {
		return codeStayGone, nil
	}
	if err != nil {
		return "", err
	}
	if s.gone() {
		return codeStayGone, nil
	}
	if s.override != nil && *s.override != 0 {
		return codeHostSet, nil
	}
	if count < 1 {
		return codeOutOfRange, nil
	}
	if count > maxGuests {
		return codeAboveCeiling, nil
	}
	old := s.declared
	if old != nil && int(*old) == count {
		return codeUnchanged, nil
	}
	if s.reduced != nil && int(*s.reduced) == count {
		return codeUnchanged, nil
	}
	live, err := liveGuestRows(ctx, tx, resID)
	if err != nil {
		return "", err
	}
	if count < live {
		if live < 1 {
			live = 1
		}
		if count < live {
			return codeBelowFloor, nil
		}
	}
	if headcountLeadLive(d.getenv) && old != nil && count < int(ptrInt(expectedCount(s))) &&
		cutoffPassed(s.dateFrom, s.checkinHour, d.now()) {
		return codeAfterCutoff, nil
	}
	stamp := d.now().UTC().Format(time.RFC3339)
	if s.reduced != nil {
		_, err = tx.Exec(ctx, `UPDATE reservation SET declared_guests = $1, lead_reduced_guests = NULL,
			lead_reduced_from = NULL, lead_reduced_at = NULL, updated_at = $2 WHERE id = $3`,
			count, stamp, resID)
	} else {
		_, err = tx.Exec(ctx, `UPDATE reservation SET declared_guests = $1, updated_at = $2 WHERE id = $3`,
			count, stamp, resID)
	}
	if err != nil {
		return "", err
	}
	if err = tx.Commit(ctx); err != nil {
		return "", err
	}
	return codeSaved, nil
}

func ptrInt(p *int64) int {
	if p == nil {
		return 0
	}
	return int(*p)
}

func cutoffPassed(dateFrom, checkinHour string, now time.Time) bool {
	cutoff := leadCutoff(dateFrom, checkinHour)
	if cutoff.IsZero() {
		return true
	}
	return !now.Before(cutoff)
}

func leadCutoff(dateFrom, checkinHour string) time.Time {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		return time.Time{}
	}
	d, err := time.Parse("2006-01-02", strings.TrimSpace(dateFrom)[:min(10, len(strings.TrimSpace(dateFrom)))])
	if err != nil {
		return time.Time{}
	}
	hour := 0
	if checkinHour != "" {
		if h, err := strconv.Atoi(checkinHour); err == nil {
			hour = h
		}
	}
	return time.Date(d.Year(), d.Month(), d.Day(), hour, 0, 0, 0, loc)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func (d partyDeps) changeByLead(ctx context.Context, resID int64, count, shown int) (string, error) {
	if !headcountLeadLive(d.getenv) {
		return codeFeatureOff, nil
	}
	tx, err := d.pool.Begin(ctx)
	if err != nil {
		return "", err
	}
	defer tx.Rollback(ctx)
	var s partyStay
	err = tx.QueryRow(ctx, `SELECT r.id, r.apartment_id, COALESCE(a.owner_user_id,0),
		COALESCE(r.status,''), COALESCE(r.archived_at::text,''),
		r.expected_guests_override, r.declared_guests, r.lead_reduced_guests,
		COALESCE(r.date_from::text,''), COALESCE(a.checkin_hour::text,''),
		COALESCE(r.lead_reduced_changes,0), r.lead_reduced_from
		FROM reservation r
		JOIN apartment a ON a.id = r.apartment_id
		WHERE r.id = $1 FOR UPDATE OF r`, resID).Scan(&s.id, &s.apartmentID, &s.ownerID, &s.status, &s.archivedAt,
		&s.override, &s.declared, &s.reduced, &s.dateFrom, &s.checkinHour, &s.leadChanges, &s.leadReducedFrom)
	if errors.Is(err, pgx.ErrNoRows) {
		return codeStayGone, nil
	}
	if err != nil {
		return "", err
	}
	cur := expectedCount(s)
	if s.gone() {
		return codeStayGone, nil
	}
	if cur == nil || count < 1 {
		return codeOutOfRange, nil
	}
	current := int(*cur)
	if count == current {
		return codeUnchanged, nil
	}
	if shown != current {
		return codeStale, nil
	}
	base := s.override
	if base == nil || *base == 0 {
		base = s.declared
	}
	baseVal := current
	if base != nil {
		baseVal = int(*base)
	}
	if count > baseVal {
		return codeAboveCeiling, nil
	}
	live, err := liveGuestRows(ctx, tx, resID)
	if err != nil {
		return "", err
	}
	if count < live {
		if live < 1 {
			live = 1
		}
		if count < live {
			return codeBelowFloor, nil
		}
	}
	changes := int(s.leadChanges)
	if count < current {
		if cutoffPassed(s.dateFrom, s.checkinHour, d.now()) {
			return codeAfterCutoff, nil
		}
		if changes >= maxLeadChanges {
			return codeTooMany, nil
		}
	}
	stamp := d.now().UTC().Format(time.RFC3339)
	if count == baseVal {
		_, err = tx.Exec(ctx, `UPDATE reservation SET lead_reduced_guests = NULL, lead_reduced_from = NULL,
			lead_reduced_at = NULL, lead_reduced_changes = $1, updated_at = $2 WHERE id = $3`,
			changes+1, stamp, resID)
	} else {
		_, err = tx.Exec(ctx, `UPDATE reservation SET lead_reduced_guests = $1, lead_reduced_from = $2,
			lead_reduced_at = $3, lead_reduced_changes = $4, updated_at = $3 WHERE id = $5`,
			count, baseVal, stamp, changes+1, resID)
	}
	if err != nil {
		return "", err
	}
	if err = tx.Commit(ctx); err != nil {
		return "", err
	}
	if count < current {
		return codeLowered, nil
	}
	return codeRestored, nil
}

func (d partyDeps) reservationExpected(ctx context.Context, resID int64) (filled int, expected *int, err error) {
	b := calendar.AlertStay{ID: resID}
	err = d.pool.QueryRow(ctx, `SELECT date_from::text, date_to::text, declared_guests,
		expected_guests_override, lead_reduced_guests FROM reservation WHERE id = $1`, resID).
		Scan(&b.DateFrom, &b.DateTo, &b.Declared, &b.Override, &b.Reduced)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil, err
	}
	if err != nil {
		return 0, nil, err
	}
	got, err := calendar.AlertProgresses(ctx, d.pool, d.getenv, []calendar.AlertStay{b}, d.now())
	if err != nil {
		return 0, nil, err
	}
	p, ok := got[resID]
	if !ok {
		return 0, nil, err
	}
	return p.Filled, p.Expected, nil
}

func partySizeHandler(d partyDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token, resID, ok := parsePartyPath(w, r)
		if !ok {
			return
		}
		lang := langFromRequest(r)
		apartment, link, early := OpenLink(r, d.pool, token, lang)
		if early != nil {
			early.ServeHTTP(w, r)
			return
		}
		token = link
		gate := stayClaimDeps{pool: d.pool, getenv: d.getenv, now: d.now}
		if gate.pinRedirect(w, r, token, lang, resID) {
			return
		}
		stay, found, err := d.loadPartyStay(r.Context(), apartment.PermalinkToken, resID)
		if err != nil {
			http.Error(w, "server error", http.StatusInternalServerError)
			return
		}
		if !found || stay.gone() {
			http.NotFound(w, r)
			return
		}
		if err := r.ParseForm(); err != nil {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}
		count, err := strconv.Atoi(strings.TrimSpace(r.FormValue("party_size")))
		if err != nil {
			count = 0
		}
		if !partyMailEnabled(d.getenv) {
			if count < 1 || count > maxGuests {
				redirectGuest(w, r, guestLink(token, resID, lang)+langQueryAmp(lang, "party_error=1"), lang)
				return
			}
			code, err := d.applyDeclared(r.Context(), resID, count)
			if err != nil {
				http.Error(w, "server error", http.StatusInternalServerError)
				return
			}
			loc := guestLink(token, resID, lang)
			if !acceptedDeclared[code] {
				loc += langQueryAmp(lang, "party_error=1")
			} else {
				loc += langQuery(lang)
			}
			redirectGuest(w, r, loc, lang)
			return
		}
		// Claim path stays on stay_claim.go (brief 1721); without mail we only set declared.
		redirectGuest(w, r, guestLink(token, resID, lang)+langQuery(lang), lang)
	}
}

func leadCountHandler(d partyDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !headcountLeadLive(d.getenv) {
			http.NotFound(w, r)
			return
		}
		token, resID, ok := parsePartyPath(w, r)
		if !ok {
			return
		}
		lang := r.URL.Query().Get("lang")
		if !partyMailEnabled(d.getenv) {
			http.NotFound(w, r)
			return
		}
		stay, found, err := d.loadPartyStay(r.Context(), token, resID)
		if err != nil {
			http.Error(w, "server error", http.StatusInternalServerError)
			return
		}
		if !found || stay.gone() {
			http.NotFound(w, r)
			return
		}
		if err := r.ParseForm(); err != nil {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}
		count, _ := strconv.Atoi(strings.TrimSpace(r.FormValue("count")))
		shown, _ := strconv.Atoi(strings.TrimSpace(r.FormValue("shown")))
		code, err := d.changeByLead(r.Context(), resID, count, shown)
		if err != nil {
			http.Error(w, "server error", http.StatusInternalServerError)
			return
		}
		redirectGuest(w, r, guestLink(token, resID, lang)+langQueryAmp(lang, "count="+url.QueryEscape(code)), lang)
	}
}

func addAnotherHandler(d partyDeps) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token, resID, ok := parsePartyPath(w, r)
		if !ok {
			return
		}
		lang := r.URL.Query().Get("lang")
		stay, found, err := d.loadPartyStay(r.Context(), token, resID)
		if err != nil {
			http.Error(w, "server error", http.StatusInternalServerError)
			return
		}
		if !found || stay.gone() {
			http.NotFound(w, r)
			return
		}
		if stay.override != nil && *stay.override != 0 {
			redirectGuest(w, r, guestLink(token, resID, lang)+langQuery(lang), lang)
			return
		}
		filled, expected, err := d.reservationExpected(r.Context(), resID)
		if err != nil {
			http.Error(w, "server error", http.StatusInternalServerError)
			return
		}
		current := filled
		if expected != nil {
			current = *expected
		}
		if current < 1 {
			current = 1
		}
		next := current + 1
		if next > maxGuests {
			next = maxGuests
		}
		_, _ = d.applyDeclared(r.Context(), resID, next)
		redirectGuest(w, r, guestLink(token, resID, lang)+"/new"+langQuery(lang), lang)
	}
}
