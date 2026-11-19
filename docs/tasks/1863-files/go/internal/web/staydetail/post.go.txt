package staydetail

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"log"
	"math"
	"math/big"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

//go:embed stayupdate/i18n.json
var stayUpdateJSON []byte

// stayUpdateStrings is this route's catalog (stayupdate/i18n_keys.txt,
// written by App/scripts/go_host_i18n.py).
var stayUpdateStrings = hostweb.Load(stayUpdateJSON)

// saveStatuses are the stay states the settings form may set.
var saveStatuses = map[string]bool{"active": true, "cancelled": true, "ignored": true}

// saveStay is what reservation_update reads from access.reservation.
type saveStay struct {
	apartmentID                     int64
	override, declared, leadReduced *int64
}

// UpdateHandler is POST /reservations/{reservation_id} (admin.py reservation_update).
func UpdateHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Python answers 422 for an id that is not an integer. POST
		// /reservations/submit-ready matches this pattern in Go and must never save.
		id, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		if err := r.ParseForm(); err != nil {
			log.Printf("stay save: form: %v", err)
		}
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			saveServerError(w, err)
			return
		}
		if h == nil {
			return
		}
		lang := hostweb.Lang(r)
		flash := func(key string) hostweb.Flash {
			return hostweb.Flash{Text: stayUpdateStrings.T(lang, key, nil), Key: key}
		}
		ctx := r.Context()
		st, ok, err := saveLoadStay(ctx, pool, h.Workspace.ID, id)
		if err != nil {
			saveServerError(w, err)
			return
		}
		if !ok {
			hostweb.Back(w, r, "/reservations", hostweb.Flash{}, flash("flash.error.no_such_stay"))
			return
		}
		stamp := at.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
		cols := []string{"guest_email", "host_note", "updated_at"}
		vals := []any{saveFormStr(r, "guest_email"), saveFormStr(r, "host_note"), stamp}
		if _, has := r.PostForm["summary"]; has {
			cols = append(cols, "summary")
			vals = append(vals, saveTruncate(saveFormStr(r, "summary"), 160))
		}
		if _, has := r.PostForm["expected_guests_override"]; has {
			expected := saveFormInt(r, "expected_guests_override")
			if expected != nil && (*expected < 1 || *expected > 60) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusUnprocessableEntity)
				_, _ = w.Write([]byte(`{"ok":false}`))
				return
			}
			// _keep_or_clear_lead_reduction (admin.py 4156-4173).
			switch {
			case st.leadReduced == nil || *st.leadReduced == 0:
				cols = append(cols, "expected_guests_override")
				vals = append(vals, expected)
			case saveSameCount(expected, headcount.Expected(st.override, st.declared, st.leadReduced)):
				// The number shown was saved again: the reduction stays, no override is written.
			default:
				cols = append(cols, "expected_guests_override", "lead_reduced_guests", "lead_reduced_from", "lead_reduced_at")
				vals = append(vals, expected, nil, nil, nil)
			}
		}
		status := saveFormStr(r, "status")
		if saveStatuses[status] {
			cols = append(cols, "status")
			vals = append(vals, status)
		} else {
			status = ""
		}
		sets := make([]string, len(cols))
		for i, c := range cols {
			sets[i] = fmt.Sprintf("%s = $%d", c, i+1)
		}
		vals = append(vals, id)
		if _, err := pool.Exec(ctx,
			"UPDATE reservation SET "+strings.Join(sets, ", ")+fmt.Sprintf(" WHERE id = $%d", len(vals)),
			vals...); err != nil {
			saveServerError(w, err)
			return
		}
		switch status {
		case "cancelled", "ignored":
			if err := ical.ExpireOnCancel(ctx, pool, id); err != nil {
				saveServerError(w, err)
				return
			}
		default:
			if status == "active" {
				if err := ubyport.ResolveAlert(ctx, pool, fmt.Sprintf("cancelled_with_guests:%d", id)); err != nil {
					saveServerError(w, err)
					return
				}
			}
			if _, err := submitStayIfComplete(ctx, pool, getenv, now, st.apartmentID, id); err != nil {
				saveServerError(w, err)
				return
			}
		}
		hostweb.Back(w, r, fmt.Sprintf("/reservations/%d", id), flash("flash.reservations.saved"), hostweb.Flash{})
	}
}

// saveLoadStay is access.reservation: the stay, reached through its apartment's owner.
func saveLoadStay(ctx context.Context, pool *pgxpool.Pool, ownerID, id int64) (saveStay, bool, error) {
	var s saveStay
	err := pool.QueryRow(ctx,
		`SELECT r.apartment_id, r.expected_guests_override, r.declared_guests, r.lead_reduced_guests
		   FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		  WHERE r.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`,
		id, ownerID).Scan(&s.apartmentID, &s.override, &s.declared, &s.leadReduced)
	if errors.Is(err, pgx.ErrNoRows) {
		return s, false, nil
	}
	if err != nil {
		return s, false, err
	}
	return s, true, nil
}

// saveFormStr is admin_helpers.form_str: the last value, stripped.
func saveFormStr(r *http.Request, key string) string {
	values := r.PostForm[key]
	if len(values) == 0 {
		return ""
	}
	return strings.TrimSpace(values[len(values)-1])
}

// saveFormInt is admin._form_int: nil when blank or not an integer. An
// integer beyond int64 is still an integer to Python, so it comes back as
// math.MaxInt64 and fails the 1 to 60 check, as in Python.
func saveFormInt(r *http.Request, key string) *int64 {
	raw := saveFormStr(r, key)
	if raw == "" {
		return nil
	}
	n, ok := new(big.Int).SetString(raw, 10)
	if !ok {
		return nil
	}
	v := int64(math.MaxInt64)
	if n.IsInt64() {
		v = n.Int64()
	}
	return &v
}

// saveTruncate is Python's text[:n] (characters, not bytes).
func saveTruncate(s string, n int) string {
	runes := []rune(s)
	if len(runes) <= n {
		return s
	}
	return string(runes[:n])
}

// saveSameCount is Python == on two Optional[int].
func saveSameCount(a, b *int64) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func saveServerError(w http.ResponseWriter, err error) {
	log.Printf("stay save: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}
