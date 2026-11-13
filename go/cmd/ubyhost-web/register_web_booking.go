package main

// Brief 1351: the booking-site routes that render no HTML page. They stay
// off until the owner adds their paths to UBYHOST_GO_PATHS. The pages under
// /p/{slug} come in a later brief; GET /p/{slug} is not registered here.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		// "{token}.ics" is not a valid wildcard: the handler cuts the suffix and
		// answers 404 for any other file name.
		mux.Handle("GET /p/{slug}/{file}", m.wrap("/p/{slug}/{file}", booking.ICalFeedHandler(pool, os.Getenv, time.Now)))
		mux.Handle("GET /p/{slug}/b/{booking_id}/{token}/calendar.ics", m.wrap("/p/{slug}/b/{booking_id}/{token}/calendar.ics", booking.StayCalendarHandler(pool, os.Getenv, time.Now)))
		mux.Handle("GET /photos/property/{name}", m.wrap("/photos/property/{name}", booking.PhotoHandler(os.Getenv)))
	})
}
