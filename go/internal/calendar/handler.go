package calendar

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// demoSource is demo.DEMO_STAY_SOURCE: demo stays are previews.
const demoSource = "demo"

// eventOut is one calendar event. The key order is Python's dict order.
type eventOut struct {
	ID             int64   `json:"id"`
	PropertyID     int64   `json:"propertyId"`
	Property       string  `json:"property"`
	Label          string  `json:"label"`
	Start          string  `json:"start"`
	End            string  `json:"end"`
	DisplayStart   string  `json:"displayStart"`
	DisplayEnd     string  `json:"displayEnd"`
	TimingFallback bool    `json:"timingFallback"`
	Guests         int     `json:"guests"`
	Complete       int     `json:"complete"`
	Expected       *int    `json:"expected"`
	Status         string  `json:"status"`
	Tone           string  `json:"tone"`
	Preview        bool    `json:"preview"`
	Source         *string `json:"source"`
	URL            string  `json:"url"`
}

// propertyItem is one active apartment of the owner.
type propertyItem struct {
	ID   int64  `json:"id"`
	Name string `json:"name"`
}

// discard swallows what hostweb.Login writes, as palette does.
type discard struct{ h http.Header }

func (d *discard) Header() http.Header         { return d.h }
func (d *discard) Write(p []byte) (int, error) { return len(p), nil }
func (d *discard) WriteHeader(int)             {}

// fieldReader decrypts guest fields the way ubyport.decryptOrPlain does. The
// data keys load on first use, so a calendar with no encrypted field needs none.
type fieldReader struct {
	getenv func(string) string
	keys   *secure.MultiFernet
}

func (f *fieldReader) value(plain, token string) (string, error) {
	if token == "" {
		return plain, nil
	}
	if f.keys == nil {
		keys, err := secure.LoadDataKeys(f.getenv)
		if err != nil {
			return "", err
		}
		f.keys = keys
	}
	b, err := f.keys.Decrypt(token, 0, time.Now())
	return string(b), err
}

// ownerID is access.owner_id: the workspace owner, nil when there is none.
func ownerID(h *session.Host) *int64 {
	if h == nil || h.Workspace.ID == 0 {
		return nil
	}
	id := h.Workspace.ID
	return &id
}

// hourAny turns a scanned hour column into the value hourOf reads.
func hourAny(p *string) any {
	if p == nil {
		return nil
	}
	return *p
}

// propertyRows is access.apartments with active: the owner's non-archived
// apartments, NULL-safe on the owner, by internal name.
func propertyRows(ctx context.Context, pool *pgxpool.Pool, owner *int64) ([]propertyItem, error) {
	rows, err := pool.Query(ctx,
		`SELECT id, internal_name FROM apartment
		  WHERE owner_user_id IS NOT DISTINCT FROM $1 AND archived_at IS NULL AND active = true
		  ORDER BY internal_name`, owner)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []propertyItem{}
	for rows.Next() {
		var p propertyItem
		if err := rows.Scan(&p.ID, &p.Name); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

// loadGuests reads the live guests of all the given stays in one query, keyed
// by reservation, and decrypts the document fields.
func loadGuests(ctx context.Context, pool *pgxpool.Pool, ids []int64, fields *fieldReader) (map[int64][]guestRow, error) {
	out := map[int64][]guestRow{}
	if len(ids) == 0 {
		return out, nil
	}
	rows, err := pool.Query(ctx,
		`SELECT g.id, g.reservation_id, COALESCE(g.nationality,''), COALESCE(g.submit_state,''),
		COALESCE(g.manual_filed_at,''), COALESCE(g.submitted_at,''), COALESCE(g.identity_verified_at,''),
		COALESCE(g.stay_from,''), COALESCE(g.stay_to,''),
		COALESCE(g.surname,''), COALESCE(g.first_name,''), COALESCE(g.res_country,''),
		COALESCE(g.purpose,''), COALESCE(g.note,''),
		COALESCE(g.doc_number,''), COALESCE(g.doc_number_enc,''),
		COALESCE(g.visa_number,''), COALESCE(g.visa_number_enc,''),
		COALESCE(g.birth_date,''), COALESCE(g.birth_date_enc,''),
		COALESCE(g.res_street,''), COALESCE(g.res_street_enc,''),
		COALESCE(g.res_city,''), COALESCE(g.res_city_enc,''),
		COALESCE(g.signature_png,''), COALESCE(g.signature_png_enc,'')
		FROM guest g
		WHERE g.reservation_id = ANY($1) AND g.archived_at IS NULL
		ORDER BY g.reservation_id, g.is_lead DESC, g.id`, ids)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var g guestRow
		var resID int64
		var stayFrom, stayTo, surname, first, resCountry, purpose, note string
		var docP, docE, visaP, visaE, birthP, birthE, streetP, streetE, cityP, cityE, sigP, sigE string
		if err := rows.Scan(&g.id, &resID, &g.nationality, &g.submitState, &g.manualFiledAt,
			&g.submittedAt, &g.identityVerifiedAt, &stayFrom, &stayTo,
			&surname, &first, &resCountry, &purpose, &note,
			&docP, &docE, &visaP, &visaE, &birthP, &birthE, &streetP, &streetE, &cityP, &cityE,
			&sigP, &sigE); err != nil {
			return nil, err
		}
		pairs := [][2]string{{docP, docE}, {visaP, visaE}, {birthP, birthE}, {streetP, streetE}, {cityP, cityE}, {sigP, sigE}}
		vals := make([]string, len(pairs))
		for i, p := range pairs {
			v, err := fields.value(p[0], p[1])
			if err != nil {
				return nil, err
			}
			vals[i] = v
		}
		g.row = validation.GuestRow{
			Surname: surname, FirstName: first, BirthDate: vals[2], Nationality: g.nationality,
			DocNumber: vals[0], VisaNumber: vals[1], ResStreet: vals[3], ResCity: vals[4],
			ResCountry: resCountry, Purpose: purpose, Note: note,
			StayFrom: stayFrom, StayTo: stayTo, SignaturePNG: vals[5],
		}
		out[resID] = append(out[resID], g)
	}
	return out, rows.Err()
}

// events mirrors dashboard_calendar.events for one owner and range.
func events(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, owner *int64, from, to time.Time, property *int64, at time.Time) ([]eventOut, error) {
	args := []any{owner, to.Format("2006-01-02"), from.Format("2006-01-02")}
	sql := `SELECT r.id, r.apartment_id, a.internal_name, r.date_from, r.date_to, COALESCE(r.summary,''),
		r.source, r.declared_guests, r.expected_guests_override, a.checkin_hour::text, a.checkout_hour::text
		FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE a.owner_user_id IS NOT DISTINCT FROM $1 AND a.active = true
		AND a.archived_at IS NULL AND r.archived_at IS NULL AND r.status = 'active'
		AND r.date_from < $2 AND r.date_to >= $3`
	if property != nil {
		sql += ` AND a.id = $4`
		args = append(args, *property)
	}
	sql += ` ORDER BY r.date_from, r.date_to, r.id`
	rows, err := pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, err
	}
	var stays []stayRow
	var ids []int64
	for rows.Next() {
		var s stayRow
		if err := rows.Scan(&s.id, &s.propertyID, &s.property, &s.dateFrom, &s.dateTo, &s.label,
			&s.source, &s.declared, &s.override, &s.checkinHour, &s.checkoutHour); err != nil {
			rows.Close()
			return nil, err
		}
		stays = append(stays, s)
		ids = append(ids, s.id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	guests, err := loadGuests(ctx, pool, ids, &fieldReader{getenv: getenv})
	if err != nil {
		return nil, err
	}
	now := localNow(at)
	today := time.Date(at.UTC().Year(), at.UTC().Month(), at.UTC().Day(), 0, 0, 0, 0, time.UTC)
	out := []eventOut{}
	for _, s := range stays {
		g := guests[s.id]
		p := progress(s, g, today)
		cell := stayCell(s, p, g, now)
		preview := s.source != nil && *s.source == demoSource
		checkin, checkout := hourAny(s.checkinHour), hourAny(s.checkoutHour)
		out = append(out, eventOut{
			ID: s.id, PropertyID: s.propertyID, Property: s.property, Label: s.label,
			Start: s.dateFrom, End: s.dateTo,
			DisplayStart:   displayAt(s.dateFrom, visualHour(checkin)),
			DisplayEnd:     displayAt(s.dateTo, visualHour(checkout)),
			TimingFallback: !hourIsValid(checkin) || !hourIsValid(checkout),
			Guests:         p.guests, Complete: p.filled, Expected: p.expected,
			Status: p.status, Tone: tone(cell.Level, p.status, preview),
			Preview: preview, Source: s.source,
			URL: "/reservations/" + strconv.FormatInt(s.id, 10) + "?return_to=/",
		})
	}
	return out, nil
}

// writeJSON writes compact JSON without HTML escaping, as Python's JSONResponse does.
func writeJSON(w http.ResponseWriter, status int, v any) {
	var b bytes.Buffer
	enc := json.NewEncoder(&b)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(bytes.TrimSuffix(b.Bytes(), []byte("\n")))
}

// Handler serves GET /dashboard/calendar for the signed-in owner.
func Handler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		at := now()
		h, err := hostweb.Login(&discard{h: http.Header{}}, r, pool, getenv, at)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		if h == nil {
			writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthorized"})
			return
		}
		query := r.URL.Query()
		from, to, err := parseRange(query.Get("from"), query.Get("to"))
		if err != nil {
			writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"error": "invalid_range"})
			return
		}
		var property *int64
		if raw := query.Get("property"); raw != "" {
			n, err := strconv.ParseInt(strings.TrimSpace(raw), 10, 64)
			if err != nil || n <= 0 {
				writeJSON(w, http.StatusUnprocessableEntity, map[string]string{"error": "invalid_range"})
				return
			}
			property = &n
		}
		ctx := r.Context()
		owner := ownerID(h)
		props, err := propertyRows(ctx, pool, owner)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		if property != nil {
			found := false
			for _, p := range props {
				found = found || p.ID == *property
			}
			if !found {
				writeJSON(w, http.StatusNotFound, map[string]string{"error": "not_found"})
				return
			}
		}
		evs, err := events(ctx, pool, getenv, owner, from, to, property, at)
		if err != nil {
			http.Error(w, "Internal Server Error", http.StatusInternalServerError)
			return
		}
		writeJSON(w, http.StatusOK, struct {
			Properties []propertyItem `json:"properties"`
			Events     []eventOut     `json:"events"`
		}{Properties: props, Events: evs})
	}
}
