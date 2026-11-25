package guest

import (
	"context"
	"log"
	"strings"
	"time"

	_ "time/tzdata" // Europe/Prague on slim deploy images

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/headcount"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

var praguePick = func() *time.Location {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		return time.UTC
	}
	return loc
}()

func pragueTodayPick(at time.Time) time.Time {
	y, m, d := at.In(praguePick).Date()
	return time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
}

// pickApartment is the apartment row pick_stay reads beyond shell.Apartment.
type pickApartment struct {
	ID                    int64
	InternalName, UbyName string
	CityEn                string
	GuestMessage          string
	PermalinkToken        string
	PermalinkPIN          string
	WindowDays            int64
	ReachbackDays         int64
	LegalEntityID         *int64
	DataControllerID      *int64
	OwnerUserID           *int64
}

func loadPickApartment(ctx context.Context, pool *pgxpool.Pool, aptID int64) (pickApartment, bool) {
	var a pickApartment
	var win, reach int64
	err := pool.QueryRow(ctx, `SELECT id, COALESCE(internal_name,''), COALESCE(uby_name,''), COALESCE(city_en,''),
		COALESCE(guest_message,''), COALESCE(permalink_token,''), COALESCE(permalink_pin,''),
		COALESCE(permalink_window_days,1), COALESCE(permalink_reachback_days,365),
		legal_entity_id, data_controller_entity_id, owner_user_id
		FROM apartment WHERE id = $1 AND active = 1 AND archived_at IS NULL`, aptID).
		Scan(&a.ID, &a.InternalName, &a.UbyName, &a.CityEn, &a.GuestMessage, &a.PermalinkToken, &a.PermalinkPIN,
			&win, &reach, &a.LegalEntityID, &a.DataControllerID, &a.OwnerUserID)
	if err == pgx.ErrNoRows {
		return pickApartment{}, false
	}
	if err != nil {
		return pickApartment{}, false
	}
	a.WindowDays = win
	a.ReachbackDays = reach
	return a, true
}

type pickReservation struct {
	ID       int64
	DateFrom string
	DateTo   string
}

func visibleReservations(ctx context.Context, pool *pgxpool.Pool, apt pickApartment, today time.Time) ([]pickReservation, error) {
	window := apt.WindowDays
	if window < 1 {
		window = 1
	}
	start := pragueTodayPick(today).Format("2006-01-02")
	horizon := pragueTodayPick(today).AddDate(0, 0, int(window)).Format("2006-01-02")
	rows, err := pool.Query(ctx, `
		SELECT r.id, COALESCE(r.date_from,''), COALESCE(r.date_to,'')
		FROM reservation r
		LEFT JOIN reservation_claim c ON c.reservation_id = r.id
		WHERE r.apartment_id = $1 AND r.status = 'active' AND r.archived_at IS NULL
		  AND COALESCE(r.source,'') != 'demo'
		  AND r.date_from >= $2 AND r.date_from <= $3
		  AND c.guest_access_locked_at IS NULL
		ORDER BY r.date_from`, apt.ID, start, horizon)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []pickReservation
	for rows.Next() {
		var r pickReservation
		if err := rows.Scan(&r.ID, &r.DateFrom, &r.DateTo); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

func reservationForGuestExtra(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apt pickApartment, resID int64, today time.Time) (*pickReservation, error) {
	for _, r := range mustVisible(ctx, pool, apt, today) {
		if r.ID == resID {
			return &r, nil
		}
	}
	rd := apt.ReachbackDays
	reach := validation.NormaliseReachbackDays(&rd)
	cutoff := pragueTodayPick(today).AddDate(0, 0, -int(reach)).Format("2006-01-02")
	var r pickReservation
	var locked *time.Time
	err := pool.QueryRow(ctx, `
		SELECT r.id, COALESCE(r.date_from,''), COALESCE(r.date_to,''), c.guest_access_locked_at
		FROM reservation r
		LEFT JOIN reservation_claim c ON c.reservation_id = r.id
		WHERE r.id = $1 AND r.apartment_id = $2 AND r.status = 'active' AND r.archived_at IS NULL
		  AND COALESCE(r.source,'') != 'demo'`, resID, apt.ID).
		Scan(&r.ID, &r.DateFrom, &r.DateTo, &locked)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if locked != nil || r.DateTo < cutoff {
		return nil, nil
	}
	if registrationComplete(ctx, pool, getenv, now, r, today) {
		return nil, nil
	}
	return &r, nil
}

func mustVisible(ctx context.Context, pool *pgxpool.Pool, apt pickApartment, today time.Time) []pickReservation {
	out, err := visibleReservations(ctx, pool, apt, today)
	if err != nil {
		return nil
	}
	return out
}

func registrationComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, res pickReservation, today time.Time) bool {
	var override, declared, reduced *int64
	err := pool.QueryRow(ctx,
		`SELECT declared_guests, expected_guests_override, lead_reduced_guests FROM reservation WHERE id = $1`,
		res.ID).Scan(&declared, &override, &reduced)
	if err != nil {
		return false
	}
	expected := headcount.Expected(override, declared, reduced)
	rows, err := pool.Query(ctx, "SELECT "+stayGuestSelect+", COALESCE(manual_filed_at,'') FROM guest WHERE reservation_id = $1 AND archived_at IS NULL", res.ID)
	if err != nil {
		return false
	}
	defer rows.Close()
	incomplete := 0
	filled := 0
	for rows.Next() {
		var c stayGuestCols
		var manual string
		if err := rows.Scan(append(c.scanArgs(), &manual)...); err != nil {
			return false
		}
		g, err := c.validationRow(getenv, now)
		if err != nil {
			log.Printf("registrationComplete: guest %d not decrypted: %v", c.ID, err)
			incomplete++
			continue
		}
		done := (c.Submit == "sent" && manual != "") || validation.GuestIsComplete(g, res.DateFrom, res.DateTo, today)
		if done {
			filled++
		} else {
			incomplete++
		}
	}
	if expected == nil {
		return filled > 0 && incomplete == 0
	}
	return filled >= int(*expected) && incomplete == 0
}

func stayHasOwnedGuest(ctx context.Context, pool *pgxpool.Pool, resID int64, owned map[int64]struct{}) bool {
	if len(owned) == 0 {
		return false
	}
	ids := make([]int64, 0, len(owned))
	for id := range owned {
		ids = append(ids, id)
	}
	var one int
	err := pool.QueryRow(ctx, `SELECT 1 FROM guest WHERE reservation_id = $1 AND id = ANY($2) AND archived_at IS NULL LIMIT 1`,
		resID, ids).Scan(&one)
	return err == nil
}

func guestPinRequired(getenv func(string) string) bool {
	v := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_GUEST_PIN")))
	if v == "" {
		return true
	}
	return v != "0" && v != "false" && v != "no"
}
