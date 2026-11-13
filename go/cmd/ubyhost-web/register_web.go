package main

// Lane W (web) owns this file: add a web route here, and only here.
// /healthz, /metrics and the "/" catch-all stay in main.go.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/palette"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pushsend"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pushweb"
)

// registerWeb registers the web routes on mux.
func registerWeb(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	mux.Handle("POST /webhooks/stripe", m.wrap("/webhooks/stripe", payments.WebhookHandler(pool, os.Getenv, time.Now)))
	onboarder := payments.NewStripeOnboarder(pool, os.Getenv, time.Now)
	mux.Handle("GET /payments/connect/start", m.wrap("/payments/connect/start", payments.ConnectStartHandler(pool, os.Getenv, time.Now, onboarder)))
	mux.Handle("POST /payments/connect/start", m.wrap("/payments/connect/start", payments.ConnectStartHandler(pool, os.Getenv, time.Now, onboarder)))
	mux.Handle("GET /payments/connect/return", m.wrap("/payments/connect/return", payments.ConnectReturnHandler(pool, os.Getenv, time.Now, onboarder)))
	mux.Handle("POST /account/push/subscribe", m.wrap("/account/push/subscribe", pushweb.SubscribeHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /account/push/refresh", m.wrap("/account/push/refresh", pushweb.RefreshHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /account/push/unsubscribe", m.wrap("/account/push/unsubscribe", pushweb.UnsubscribeHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /account/push/devices/{id}/delete", m.wrap("/account/push/devices/{id}/delete", pushweb.DeviceDeleteHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /account/push/test", m.wrap("/account/push/test", pushweb.TestHandler(&pushsend.Sender{Pool: pool, Getenv: os.Getenv, Now: time.Now}, os.Getenv, time.Now)))
	mux.Handle("GET /api/command-palette", m.wrap("/api/command-palette", palette.Handler(pool, os.Getenv, time.Now)))
	mux.Handle("GET /dashboard/calendar", m.wrap("/dashboard/calendar", calendar.Handler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /payments/requests/new", m.wrap("/payments/requests/new", payments.RequestNewHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /payments/requests/{id}/send", m.wrap("/payments/requests/{id}/send", payments.RequestSendHandler(pool, os.Getenv, time.Now, onboarder)))
	mux.Handle("GET /payments/qr/{file}", m.wrap("/payments/qr/{file}", payments.QRPNGHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /payments/requests/{id}/link", m.wrap("/payments/requests/{id}/link", payments.RequestLinkHandler(pool, os.Getenv, time.Now, onboarder)))
	mux.Handle("GET /pay/{id}/{file}", m.wrap("/pay/{id}/{file}", payments.GuestQRPNGHandler(pool, os.Getenv)))
}
