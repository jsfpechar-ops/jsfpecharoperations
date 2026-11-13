package calendar

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// AlertStay is the reservation behind a host alert card (alerts.present_many
// in App/app/alerts.py): the columns reservation_progress reads. Brief 1381.
type AlertStay struct {
	ID               int64
	DateFrom, DateTo string
	Declared         *int64 // declared_guests
	Override         *int64 // expected_guests_override
	Reduced          *int64 // lead_reduced_guests
}

// AlertProgress is the part of reporting.reservation_progress and
// reservation_deadline_anchor an alert card prints. Unreadable is true when a
// guest field of the stay will not decrypt (Python raises DecryptionError).
type AlertProgress struct {
	Filled     int
	Expected   *int
	Incomplete int
	Status     string
	Anchor     time.Time // reservation_deadline_anchor; zero with HasAnchor false
	HasAnchor  bool
	Unreadable bool
}

func (s AlertStay) row() stayRow {
	return stayRow{id: s.ID, dateFrom: s.DateFrom, dateTo: s.DateTo,
		declared: s.Declared, override: s.Override, reduced: s.Reduced}
}

func alertProgress(s AlertStay, guests []guestRow, today time.Time) AlertProgress {
	stay := s.row()
	p := progress(stay, guests, today)
	anchor, ok := anchorDate(stay, guests)
	return AlertProgress{Filled: p.filled, Expected: p.expected, Incomplete: p.guests - p.filled,
		Status: p.status, Anchor: anchor, HasAnchor: ok}
}

// AlertProgressNoGuests is AlertProgress for a stay with no live guests. The
// layout golden test uses it; it reads nothing.
func AlertProgressNoGuests(s AlertStay) AlertProgress {
	return alertProgress(s, nil, time.Time{})
}

// AlertProgresses is reporting.preload_guests plus reservation_progress for the
// stays of the shell's alert cards: one guest read for all of them. When one
// guest will not decrypt, each stay is read on its own (as preload_guests
// falls back), so only that stay is Unreadable. at is the request instant;
// validation reads its UTC date, as Python's date.today() does on the server.
func AlertProgresses(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, stays []AlertStay, at time.Time) (map[int64]AlertProgress, error) {
	out := make(map[int64]AlertProgress, len(stays))
	if len(stays) == 0 {
		return out, nil
	}
	u := at.UTC()
	today := time.Date(u.Year(), u.Month(), u.Day(), 0, 0, 0, 0, time.UTC)
	ids := make([]int64, len(stays))
	for i, s := range stays {
		ids[i] = s.ID
	}
	fields := &fieldReader{getenv: getenv}
	byStay, err := loadGuests(ctx, pool, ids, fields)
	if err == nil {
		for _, s := range stays {
			out[s.ID] = alertProgress(s, byStay[s.ID], today)
		}
		return out, nil
	}
	if !errors.Is(err, secure.ErrInvalidToken) {
		return nil, err
	}
	for _, s := range stays {
		one, err := loadGuests(ctx, pool, []int64{s.ID}, fields)
		if errors.Is(err, secure.ErrInvalidToken) {
			out[s.ID] = AlertProgress{Unreadable: true}
			continue
		}
		if err != nil {
			return nil, err
		}
		out[s.ID] = alertProgress(s, one[s.ID], today)
	}
	return out, nil
}
