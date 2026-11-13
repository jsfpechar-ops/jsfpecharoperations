package main

// Brief 1353: the host payments pages. Off until the owner adds the paths to
// UBYHOST_GO_PATHS. The QR preview page /payments/qr/{id} and the guest page
// /pay/{id}/{token} stay on Python: their patterns are the PNG routes in
// register_web.go, and they need the base.html frame the Go layout lacks.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments/pages"
)

func init() { registerRoutes(registerPaymentsPages) }

func registerPaymentsPages(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	links := payments.NewStripeOnboarder(pool, os.Getenv, time.Now)
	mux.Handle("GET /payments", m.wrap("/payments", pages.OverviewHandler(pool, os.Getenv, time.Now)))
	mux.Handle("GET /payments/new", m.wrap("/payments/new", pages.NewHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /payments/services", m.wrap("/payments/services", pages.ServiceAddHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /payments/services/{id}/delete", m.wrap("/payments/services/{id}/delete", pages.ServiceDeleteHandler(pool, os.Getenv, time.Now)))
	mux.Handle("GET /payments/requests/{id}/share", m.wrap("/payments/requests/{id}/share", pages.ShareHandler(pool, os.Getenv, time.Now, links)))
	mux.Handle("GET /payments/consent", m.wrap("/payments/consent", pages.ConsentHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /payments/consent", m.wrap("/payments/consent", pages.ConsentAcceptHandler(pool, os.Getenv, time.Now)))
}
