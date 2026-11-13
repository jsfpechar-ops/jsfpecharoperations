package booking

// HTTP handlers for the booking-site routes that render no HTML page, ported
// from App/app/routes/property_page.py: the private iCal feed (0817), the
// guest's stay calendar (0821) and the property photo file (0432). Each
// factory only captures its arguments; the pool is used per request.

import (
	"context"
	"errors"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Rate limits from property_page.py (_RATE_MAX, _RATE_WINDOW).
const (
	rateMax    = 120
	rateWindow = 3600 // seconds

	scopeICal   = "property_page_ical"
	scopeManage = "booking_manage"
)

var photoName = regexp.MustCompile(`^[0-9a-f]{32}\.jpg$`)

func text(w http.ResponseWriter, code int, body string) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(code)
	_, _ = io.WriteString(w, body)
}

func serverError(w http.ResponseWriter, what string, err error) {
	log.Printf("booking %s: %v", what, err)
	text(w, http.StatusInternalServerError, "Internal Server Error")
}

// peer is rate_limit.client_key's host: CF-Connecting-IP (Caddy overwrites
// it), else the peer host, else "unknown".
func peer(r *http.Request) string {
	if v := strings.TrimSpace(r.Header.Get("CF-Connecting-IP")); v != "" {
		return v
	}
	if host, _, err := net.SplitHostPort(r.RemoteAddr); err == nil && host != "" {
		return host
	}
	if r.RemoteAddr != "" {
		return r.RemoteAddr
	}
	return "unknown"
}

// throttle is rate_limit.blocked + record with client_key(request, scope):
// prune the window, count, refuse at rateMax, else record one event.
func throttle(ctx context.Context, db DB, r *http.Request, scope string, now time.Time) (blocked bool, err error) {
	key := peer(r) + ":" + scope
	at := float64(now.UnixNano()) / 1e9
	if _, err := db.Exec(ctx, `DELETE FROM rate_limit_event WHERE scope = $1 AND key = $2 AND at < $3`,
		scope, key, at-rateWindow); err != nil {
		return false, err
	}
	var n int64
	if err := db.QueryRow(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE scope = $1 AND key = $2`,
		scope, key).Scan(&n); err != nil {
		return false, err
	}
	if n >= rateMax {
		return true, nil
	}
	_, err = db.Exec(ctx, `INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3)`, scope, key, at)
	return false, err
}

// limited runs throttle and writes the 429 or 500 answer; true means stop.
func limited(w http.ResponseWriter, r *http.Request, db DB, scope string, now time.Time) bool {
	blocked, err := throttle(r.Context(), db, r, scope, now)
	if err != nil {
		serverError(w, "rate limit", err)
		return true
	}
	if blocked {
		text(w, http.StatusTooManyRequests, "slow down")
		return true
	}
	return false
}

// ICalFeedHandler serves GET /p/{slug}/{file} where file is "<token>.ics":
// property_page_ical. Any other file name is 404 without touching the
// database, so the pattern shadows nothing Python serves under /p/<slug>/
// as long as only .ics paths are routed to Go.
func ICalFeedHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token, ok := strings.CutSuffix(r.PathValue("file"), ".ics")
		if !ok || token == "" {
			http.NotFound(w, r)
			return
		}
		at := now()
		if limited(w, r, pool, scopeICal, at) {
			return
		}
		ctx := r.Context()
		apartmentID, found, err := ApartmentForSlug(ctx, pool, r.PathValue("slug"))
		if err != nil {
			serverError(w, "ical slug", err)
			return
		}
		if !found {
			http.NotFound(w, r)
			return
		}
		good, err := FeedTokenOK(ctx, pool, apartmentID, token)
		if err != nil {
			serverError(w, "ical token", err)
			return
		}
		if !good {
			http.NotFound(w, r)
			return
		}
		body, err := ExportICS(ctx, pool, apartmentID, at.In(time.Local), at)
		if err != nil {
			serverError(w, "ical export", err)
			return
		}
		h := w.Header()
		h.Set("Content-Type", "text/calendar; charset=utf-8")
		h.Set("Cache-Control", "private, max-age=300")
		h.Set("X-Robots-Tag", "noindex")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, body)
	}
}

// StayBooking is the part of a site_booking row the stay calendar needs.
type StayBooking struct {
	ID          int64
	ApartmentID int64
	Status      string
	DateFrom    string
	DateTo      string
}

// LoadStayBooking reads one site_booking row; ok is false when none.
func LoadStayBooking(ctx context.Context, db DB, bookingID int64) (StayBooking, bool, error) {
	b := StayBooking{ID: bookingID}
	err := db.QueryRow(ctx, `SELECT apartment_id, status, date_from, date_to FROM site_booking WHERE id = $1`,
		bookingID).Scan(&b.ApartmentID, &b.Status, &b.DateFrom, &b.DateTo)
	if errors.Is(err, pgx.ErrNoRows) {
		return b, false, nil
	}
	return b, err == nil, err
}

// StayCalendarHandler serves GET /p/{slug}/b/{booking_id}/{token}/calendar.ics:
// booking_manage_calendar. Only a paid booking with a good token answers.
func StayCalendarHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		bookingID, err := strconv.ParseInt(r.PathValue("booking_id"), 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		at := now()
		if limited(w, r, pool, scopeManage, at) {
			return
		}
		secret, err := secure.LoadSecret(getenv)
		if err != nil {
			serverError(w, "secret", err)
			return
		}
		if !ManageTokenOK(secret, bookingID, r.PathValue("token")) {
			http.NotFound(w, r)
			return
		}
		ctx := r.Context()
		b, found, err := LoadStayBooking(ctx, pool, bookingID)
		if err != nil {
			serverError(w, "stay booking", err)
			return
		}
		if !found || b.Status != "paid" {
			http.NotFound(w, r)
			return
		}
		var name *string
		err = pool.QueryRow(ctx, `SELECT internal_name FROM apartment WHERE id = $1`, b.ApartmentID).Scan(&name)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			serverError(w, "stay name", err)
			return
		}
		label := ""
		if name != nil {
			label = *name
		}
		body, err := StayICS(b.ID, b.DateFrom, b.DateTo, label, at)
		if err != nil {
			serverError(w, "stay ics", err)
			return
		}
		h := w.Header()
		h.Set("Content-Type", "text/calendar; charset=utf-8")
		h.Set("Cache-Control", "no-store")
		h.Set("X-Robots-Tag", "noindex")
		h.Set("Content-Disposition", `attachment; filename="stay.ics"`)
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, body)
	}
}

// PhotosDir is property_page.photos_dir without the mkdir:
// $UBYHOST_DATA_DIR/property_photos (default dir "data").
func PhotosDir(getenv func(string) string) string {
	dir := getenv("UBYHOST_DATA_DIR")
	if dir == "" {
		dir = "data"
	}
	return filepath.Join(dir, "property_photos")
}

// PhotoHandler serves GET /photos/property/{name}: property_photo_file. The
// name must be 32 hex characters + ".jpg"; anything else is 404.
func PhotoHandler(getenv func(string) string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		name := r.PathValue("name")
		if !photoName.MatchString(name) {
			http.NotFound(w, r)
			return
		}
		f, err := os.Open(filepath.Join(PhotosDir(getenv), name))
		if err != nil {
			http.NotFound(w, r)
			return
		}
		defer f.Close()
		info, err := f.Stat()
		if err != nil || !info.Mode().IsRegular() {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "image/jpeg")
		w.Header().Set("Cache-Control", "public, max-age=86400")
		http.ServeContent(w, r, name, info.ModTime(), f)
	}
}
