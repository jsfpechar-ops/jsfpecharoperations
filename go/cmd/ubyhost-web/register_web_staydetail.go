package main

// Brief 1861: the stay page (GET /reservations/{id}). It stays off until the
// owner adds a selector to UBYHOST_GO_PATHS; POST /reservations/{id} must be
// served by Go first (see docs/tasks/1861-go-stay-detail-page.md).

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/staydetail"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		staydetail.Register(mux, pool, os.Getenv, time.Now, m.wrap, stayDoorCodes(pool))
	})
}

// stayDoorCodes is the door-code service the stay page reads (door_codes.view),
// built like the door-code job's (door_codes_wire.go). It does not use the pool here.
func stayDoorCodes(pool *pgxpool.Pool) staydetail.DoorCodeViewer {
	keys, err := secure.LoadDataKeys(os.Getenv)
	if err != nil {
		return nil
	}
	return &doorcodes.Service{Pool: pool, Keys: keys, Settings: doorCodesSettings(os.Getenv), Clock: systemClock{}}
}
