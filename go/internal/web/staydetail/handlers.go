package staydetail

import (
	"errors"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

// pageData is the template context: the View plus payments_hidden(), a
// Jinja global the View does not carry.
type pageData struct {
	View
	PaymentsHidden bool
}

// detailHandler serves GET /reservations/{reservation_id}
// (admin.reservation_detail).
func detailHandler(deps Deps, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		host, err := hostweb.Login(w, r, deps.Pool, deps.Getenv, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if host == nil {
			return
		}
		id, err := strconv.ParseInt(r.PathValue("reservation_id"), 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		v, ok, err := Build(r.Context(), deps, host.Workspace.ID, id, r.URL.Query().Get("return_to"), at)
		if err != nil {
			serverError(w, err)
			return
		}
		if !ok {
			http.NotFound(w, r)
			return
		}
		page := layout.Page{
			Title:      v.Reservation.InternalName + " · " + dateCZ(v.Reservation.DateFrom),
			Nav:        "reservations",
			BodyKind:   "detail",
			V2:         true,
			HowKey:     "stay",
			BodyAlerts: true,
		}
		data := pageData{View: v, PaymentsHidden: paymentsHidden(deps.Getenv)}
		if err := layout.Render(w, r, layout.Env{Pool: deps.Pool, Getenv: deps.Getenv, Now: at}, host, page, pages, "stay_detail", data); err != nil {
			serverError(w, err)
		}
	}
}

// Register mounts GET /reservations/{reservation_id} only; doorCodes[0], when
// given, is the door-code service the page reads (nil hides the panel).
func Register(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler, doorCodes ...DoorCodeViewer) {
	deps := Deps{Pool: pool, Getenv: getenv}
	if len(doorCodes) > 0 {
		deps.DoorCodes = doorCodes[0]
	}
	mux.Handle("GET /reservations/{reservation_id}", wrap("/reservations/{reservation_id}", detailHandler(deps, now)))
}

func serverError(w http.ResponseWriter, err error) {
	code := http.StatusInternalServerError
	if errors.Is(err, pgx.ErrNoRows) {
		code = http.StatusNotFound
	}
	log.Printf("stay detail: %v", err)
	http.Error(w, http.StatusText(code), code)
}
