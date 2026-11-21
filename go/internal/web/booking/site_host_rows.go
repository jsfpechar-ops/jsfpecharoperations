package booking

// booking_manage.host_rows for the host booking-site setup page.

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// HostBookingRow is one line in the recent bookings list.
type HostBookingRow struct {
	ID         int64
	Name       string
	Status     string
	StatusKey  string
	Dates      string
	Total      int
	Direct     bool
	CanConfirm bool
	CanDecline bool
	CanCancel  bool
	CanRetry   bool
}

// HostRows is booking_manage.host_rows.
func HostRows(ctx context.Context, db DB, apartmentID int64, limit int) ([]HostBookingRow, error) {
	if limit <= 0 {
		limit = 20
	}
	rows, err := db.Query(ctx, `SELECT id, guest_name, status, date_from, date_to, total_czk, pay_method, refunded_czk
		FROM site_booking
		WHERE apartment_id = $1 AND status IN ('requested', 'expired', 'paid', 'cancelled', 'refunded', 'clash_refunded')
		  AND (status != 'expired' OR pay_method = 'direct')
		ORDER BY date_from DESC, id DESC LIMIT $2`, apartmentID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []HostBookingRow
	for rows.Next() {
		var id, total int64
		var guest, status, from, to, pay string
		var refunded *int64
		if err := rows.Scan(&id, &guest, &status, &from, &to, &total, &pay, &refunded); err != nil {
			return nil, err
		}
		direct := pay == "direct"
		ref := int64(0)
		if refunded != nil {
			ref = *refunded
		}
		sk := status
		if direct && status == "cancelled" {
			sk = "cancelled_direct"
		}
		out = append(out, HostBookingRow{
			ID:         id,
			Name:       shortGuestName(guest),
			Status:     status,
			StatusKey:  sk,
			Dates:      hostDateSpan(from, to),
			Total:      int(total),
			Direct:     direct,
			CanConfirm: direct && (status == "requested" || status == "expired"),
			CanDecline: direct && (status == "requested" || status == "expired"),
			CanCancel:  status == "paid",
			CanRetry:   status == "cancelled" && !direct && ref == 0,
		})
	}
	return out, rows.Err()
}

func shortGuestName(full string) string {
	parts := strings.Fields(full)
	if len(parts) == 0 {
		return ""
	}
	if len(parts) == 1 {
		return parts[0]
	}
	r := []rune(parts[len(parts)-1])
	initial := string(r[:1])
	return parts[0] + " " + initial + "."
}

func hostDateSpan(from, to string) string {
	f, err1 := time.Parse("2006-01-02", from)
	t, err2 := time.Parse("2006-01-02", to)
	if err1 != nil || err2 != nil {
		return from + "–" + to
	}
	return fmt.Sprintf("%d.–%d. %d.", f.Day(), t.Day(), t.Month())
}
