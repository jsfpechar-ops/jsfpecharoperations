package stays

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"math/big"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

type postDeps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
	hooks  CompletionHooks
}

type postCall struct {
	postDeps
	w     http.ResponseWriter
	r     *http.Request
	at    time.Time
	lang  string
	owner int64
}

func (d postDeps) enterPost(w http.ResponseWriter, r *http.Request) *postCall {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return nil
	}
	if err := r.ParseForm(); err != nil {
		log.Printf("stays create: form: %v", err)
	}
	h, err := hostweb.Login(w, r, d.pool, d.getenv, at)
	if err != nil {
		serverError(w, err)
		return nil
	}
	if h == nil {
		return nil
	}
	return &postCall{postDeps: d, w: w, r: r, at: at, lang: hostweb.Lang(r), owner: h.Workspace.ID}
}

func (c *postCall) flash(key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(c.lang, key, params), Key: key}
}

func (c *postCall) back(path string, msg, err hostweb.Flash) {
	hostweb.Back(c.w, c.r, path, msg, err)
}

func formStr(r *http.Request, key string) string {
	values := r.PostForm[key]
	if len(values) == 0 {
		return ""
	}
	return strings.TrimSpace(values[len(values)-1])
}

func formInt(r *http.Request, key string) *int64 {
	raw := formStr(r, key)
	if raw == "" {
		return nil
	}
	n, ok := pyFormInt(raw)
	if !ok || !n.IsInt64() {
		return nil
	}
	v := n.Int64()
	return &v
}

func pyFormInt(text string) (*big.Int, bool) {
	n := new(big.Int)
	if _, ok := n.SetString(text, 10); !ok {
		return nil, false
	}
	return n, true
}

func isoStamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

type createApt struct {
	id        int64
	name      string
	permalink string
	active    bool
	archived  bool
}

func (c *postCall) apartment(ctx context.Context, id int64) (*createApt, error) {
	var a createApt
	var archived *string
	var active int
	err := c.pool.QueryRow(ctx, `SELECT id, COALESCE(name, ''), COALESCE(permalink_token, ''), active, archived_at FROM apartment
		WHERE id = $1 AND owner_user_id IS NOT DISTINCT FROM $2`, id, c.owner).Scan(&a.id, &a.name, &a.permalink, &active, &archived)
	if errorsIsNoRows(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	a.active = active != 0
	a.archived = archived != nil && *archived != ""
	return &a, nil
}

func errorsIsNoRows(err error) bool {
	return errors.Is(err, pgx.ErrNoRows)
}

func (c *postCall) overlappingCount(ctx context.Context, apartmentID int64, start, end string) (int64, error) {
	var n int64
	err := c.pool.QueryRow(ctx, `SELECT COUNT(*) FROM reservation WHERE apartment_id = $1
 AND status = 'active' AND archived_at IS NULL AND date_from < $2 AND date_to > $3`,
		apartmentID, end, start).Scan(&n)
	return n, err
}

func manualUID() (string, error) {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return "manual-" + hex.EncodeToString(b[:]), nil
}

func optionalText(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func calendarJSON(r *http.Request) bool {
	return formStr(r, "calendar") == "1" && strings.Contains(r.Header.Get("Accept"), "application/json")
}

func writeCalendarErrors(w http.ResponseWriter, errors map[string]string) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnprocessableEntity)
	_ = json.NewEncoder(w).Encode(map[string]any{"errors": errors})
}

func writeCalendarOverlap(w http.ResponseWriter, msg string) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusConflict)
	_ = json.NewEncoder(w).Encode(map[string]any{"error": msg, "overlap": true})
}

func writeCalendarCreated(w http.ResponseWriter, id int64) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(map[string]any{
		"id":  id,
		"url": fmt.Sprintf("/reservations/%d?return_to=/", id),
	})
}

// CreateHandler is POST /reservations (admin.py reservation_create).
func CreateHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	d := postDeps{pool: pool, getenv: getenv, now: now}
	return func(w http.ResponseWriter, r *http.Request) {
		c := d.enterPost(w, r)
		if c == nil {
			return
		}
		ctx := r.Context()
		apartmentID := formInt(r, "apartment_id")
		dateFrom := formStr(r, "date_from")
		dateTo := formStr(r, "date_to")
		calJSON := calendarJSON(r)

		if calJSON {
			errs := map[string]string{}
			if _, _, err := calendar.ParseDates(dateFrom, dateTo); err != nil {
				errs["date_to"] = c.flash("flash.error.dates_order", nil).Text
			}
			var apt *createApt
			if apartmentID != nil {
				var err error
				apt, err = c.apartment(ctx, *apartmentID)
				if err != nil {
					serverError(w, err)
					return
				}
			}
			if apartmentID == nil || apt == nil || !apt.active || apt.archived {
				errs["apartment_id"] = c.flash("flash.error.no_such_apartment", nil).Text
			}
			guestRaw := formStr(r, "expected_guests")
			if guestRaw != "" {
				g := formInt(r, "expected_guests")
				if g == nil || *g < 1 || *g > 60 {
					errs["expected_guests"] = catalog.T(c.lang, "calendar.guests_error", nil)
				}
			}
			if len(errs) > 0 {
				writeCalendarErrors(w, errs)
				return
			}
			if formStr(r, "allow_overlap") != "1" && apartmentID != nil {
				n, err := c.overlappingCount(ctx, *apartmentID, dateFrom, dateTo)
				if err != nil {
					serverError(w, err)
					return
				}
				if n > 0 {
					writeCalendarOverlap(w, catalog.T(c.lang, "calendar.overlap", nil))
					return
				}
			}
		}

		if apartmentID == nil || dateFrom == "" || dateTo == "" {
			c.back("/reservations", hostweb.Flash{}, c.flash("flash.error.stay_dates_required", nil))
			return
		}
		apt, err := c.apartment(ctx, *apartmentID)
		if err != nil {
			serverError(w, err)
			return
		}
		if apt == nil {
			c.back("/reservations", hostweb.Flash{}, c.flash("flash.error.no_such_apartment", nil))
			return
		}
		if _, _, err := calendar.ParseDates(dateFrom, dateTo); err != nil {
			c.back("/reservations", hostweb.Flash{}, c.flash("flash.error.dates_order", nil))
			return
		}

		uid, err := manualUID()
		if err != nil {
			serverError(w, err)
			return
		}
		stamp := isoStamp(c.at)
		var id int64
		err = pool.QueryRow(ctx, `INSERT INTO reservation (
			apartment_id, source, uid, date_from, date_to, summary, expected_guests_override,
			guest_email, host_note, status, created_at, updated_at)
			VALUES ($1,'manual',$2,$3,$4,$5,$6,$7,$8,'active',$9,$9) RETURNING id`,
			*apartmentID, uid, dateFrom, dateTo,
			optionalText(formStr(r, "summary")),
			formInt(r, "expected_guests"),
			optionalText(formStr(r, "guest_email")),
			optionalText(formStr(r, "host_note")),
			stamp,
		).Scan(&id)
		if err != nil {
			serverError(w, err)
			return
		}

		// Stay creation must succeed even when mail is unavailable or claim seeding fails.
		guestAddr := ubyport.NormaliseEmail(formStr(r, "guest_email"))
		party := formInt(r, "expected_guests")
		if !calJSON && guestAddr != "" && party != nil && *party >= 1 && billingjob.MailEnabled() {
			ok, _, _, cerr := StartClaim(
				ctx,
				ClaimSeedDeps{Pool: pool, Getenv: d.getenv, Now: d.now},
				SeedReservation{ID: id, ApartmentID: *apartmentID, Status: "active"},
				SeedApartment{ID: apt.id, OwnerUserID: c.owner, Name: apt.name, PermalinkToken: apt.permalink},
				guestAddr,
				int(*party),
				"en",
				false,
			)
			if cerr != nil {
				log.Printf("stays create: claim mail failed, reservation=%d: %v", id, cerr)
			} else if ok {
				_ = c.editAudit(ctx, "guest_link_sent_on_create", fmt.Sprintf("reservation=%d", id))
			}
		}

		if calJSON {
			writeCalendarCreated(w, id)
			return
		}
		c.back(fmt.Sprintf("/reservations/%d", id), c.flash("flash.reservations.created", nil), hostweb.Flash{})
	}
}
