package staydetail

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// submitCompletedStayOpts lets tests inject a fake submitter/sender without
// bypassing the gate logic inside ubyport.SubmitCompletedStay.
var submitCompletedStayOpts *ubyport.SubmitCompletedStayOptions

// submitStayIfComplete is reporting.submit_stay_if_complete (reporting.py
// 1152-1197). It returns true when immediate stay-scoped filing ran cleanly.
func submitStayIfComplete(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apartmentID, reservationID int64) (bool, error) {
	return ubyport.SubmitCompletedStay(ctx, pool, getenv, now, apartmentID, reservationID, submitCompletedStayOpts)
}
