package stays

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

func enrichRows(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, rows []Row, at time.Time) ([]Row, int, error) {
	if len(rows) == 0 {
		return rows, 0, nil
	}
	ids := make([]int64, len(rows))
	for i, r := range rows {
		ids[i] = r.Reservation.ID
	}
	u := at.UTC()
	today := time.Date(u.Year(), u.Month(), u.Day(), 0, 0, 0, 0, time.UTC)
	byStay, err := loadProgGuests(ctx, pool, ids, getenv)
	if errors.Is(err, secure.ErrInvalidToken) {
		return unreadableRows(rows), 0, nil
	}
	if err != nil {
		return nil, 0, err
	}
	signals, err := LoadJourneySignals(ctx, pool, ids, pragueToday(at))
	if err != nil {
		return nil, 0, err
	}
	ready := 0
	for i, r := range rows {
		st := listStay{
			id: r.Reservation.ID, dateFrom: r.Reservation.DateFrom, dateTo: r.Reservation.DateTo,
			declared: r.Reservation.Declared, override: r.Reservation.Override, reduced: r.Reservation.Reduced,
		}
		guests := byStay[r.Reservation.ID]
		sig := signals[r.Reservation.ID]
		rows[i].Progress = buildProgress(st, guests, at)
		rows[i].Progress.ScheduledSendLabel = scheduledSendCompact(r.Reservation, rows[i].Progress, sig, guests, at)
		rows[i].Journey = BuildJourney(r.Reservation, rows[i].Progress, sig, pragueToday(at))
		lp := listProgress(st, guests, today)
		rows[i].Controls = sendControls(r.Reservation, r.Reservation.AutomationMode, lp, guests)
		if rows[i].Controls.SendEnabled && rows[i].ApartmentActive {
			ready++
		}
	}
	return rows, ready, nil
}

func unreadableRows(rows []Row) []Row {
	for i := range rows {
		rows[i].Progress = Progress{Unreadable: true}
	}
	return rows
}
