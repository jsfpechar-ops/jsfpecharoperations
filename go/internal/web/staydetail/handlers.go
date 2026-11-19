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

func detailHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		host, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if host == nil {
			return
		}

		idStr := r.PathValue("reservation_id")
		id, err := strconv.ParseInt(idStr, 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return
		}

		deps := Deps{
			Pool:   pool,
			Getenv: getenv,
		}
		if len(doorCodes) > 0 {
			deps.DoorCodes = doorCodes[0]
		}

		ctx := r.Context()
		returnTo := r.URL.Query().Get("return_to")
		v, ok, err := Build(ctx, deps, host.Workspace.ID, id, returnTo, at)
		if err != nil {
			serverError(w, err)
			return
		}
		if !ok {
			http.NotFound(w, r)
			return
		}

		page := layout.Page{
			Title:      v.Reservation.InternalName,
			Nav:        "reservations",
			BodyKind:   "detail",
			V2:         true,
			HowKey:     "stay",
			BodyAlerts: true,
		}

		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, host, page, pages, "stay_detail", v); err != nil {
			serverError(w, err)
		}
	}
}

func Register(mux *http.ServeMux, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, wrap func(string, http.HandlerFunc) http.Handler, doorCodeViewers ...DoorCodeViewer) {
	doorCodes = doorCodeViewers
	mux.Handle("GET /reservations/{reservation_id}", wrap("/reservations/{reservation_id}", detailHandler(pool, getenv, now)))
}

var doorCodes []DoorCodeViewer

func serverError(w http.ResponseWriter, err error) {
	code := http.StatusInternalServerError
	if errors.Is(err, pgx.ErrNoRows) {
		code = http.StatusNotFound
	}
	log.Printf("stay detail: %v", err)
	http.Error(w, http.StatusText(code), code)
}
