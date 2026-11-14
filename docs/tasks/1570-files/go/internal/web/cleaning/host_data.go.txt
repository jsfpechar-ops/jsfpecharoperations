package cleaning

import (
	"context"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// eventFull is one cleaning_event row as cleaning.event_for returns it.
type eventFull struct {
	ID, ApartmentID, Overridden, Revision int64
	Source                                *int64
	Date, State                           string
	Start, End, NotesEnc                  *string
}

// eventFor is cleaning.event_for: the event when the owner's active apartment
// holds it, nil otherwise.
func eventFor(ctx context.Context, pool *pgxpool.Pool, owner *int64, id int64) (*eventFull, error) {
	var e eventFull
	err := pool.QueryRow(ctx,
		`SELECT e.id, e.apartment_id, e.source_reservation_id, e.scheduled_date, e.start_time, e.end_time,
		        e.notes_enc, e.overridden, e.state, e.revision
		   FROM cleaning_event e JOIN apartment a ON a.id = e.apartment_id
		  WHERE e.id = $1 AND a.owner_user_id IS NOT DISTINCT FROM $2
		    AND a.active = 1 AND a.archived_at IS NULL`, id, owner).
		Scan(&e.ID, &e.ApartmentID, &e.Source, &e.Date, &e.Start, &e.End, &e.NotesEnc, &e.Overridden, &e.State, &e.Revision)
	if err == pgx.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &e, nil
}

// homeFor is routes/cleaning._home: access.apartment (owner scope), then
// active and not archived. nil means the route answers 404.
func homeFor(ctx context.Context, pool *pgxpool.Pool, owner *int64, id int64) (*home, error) {
	list, err := properties(ctx, pool, owner, []int64{id})
	if err != nil || len(list) == 0 {
		return nil, err
	}
	return &list[0], nil
}
