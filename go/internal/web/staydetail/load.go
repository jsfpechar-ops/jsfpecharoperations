package staydetail

import (
	"context"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

// Stay is access.reservation(request, id, "r.*, a.internal_name, a.permalink_token,
// a.automation_mode, a.submit_after_hours"): the columns the stay page reads.
type Stay struct {
	stays.Reservation
	CheckinHour *int64
	ArchivedAt  string
	GuestEmail  string
	HostNote    string
}

const loadStaySQL = `SELECT r.id, r.apartment_id, r.date_from, r.date_to, COALESCE(r.status,''), COALESCE(r.source,''),
       COALESCE(r.summary,''), COALESCE(a.internal_name,''), COALESCE(a.permalink_token,''),
       COALESCE(a.automation_mode,''), a.submit_after_hours, a.checkin_hour,
       r.declared_guests, r.expected_guests_override, r.lead_reduced_guests,
       COALESCE(r.archived_at,''), COALESCE(r.guest_email,''), COALESCE(r.host_note,'')
  FROM reservation r JOIN apartment a ON a.id = r.apartment_id
 WHERE r.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2`

// LoadStay returns the owner's stay; ok is false for an unknown id or another owner's stay.
func LoadStay(ctx context.Context, pool *pgxpool.Pool, ownerID, id int64) (Stay, bool, error) {
	var s Stay
	err := pool.QueryRow(ctx, loadStaySQL, id, ownerID).Scan(
		&s.ID, &s.ApartmentID, &s.DateFrom, &s.DateTo, &s.Status, &s.Source,
		&s.Summary, &s.InternalName, &s.PermalinkToken,
		&s.AutomationMode, &s.SubmitAfterHours, &s.CheckinHour,
		&s.Declared, &s.Override, &s.Reduced,
		&s.ArchivedAt, &s.GuestEmail, &s.HostNote)
	if errors.Is(err, pgx.ErrNoRows) {
		return Stay{}, false, nil
	}
	if err != nil {
		return Stay{}, false, err
	}
	return s, true, nil
}
