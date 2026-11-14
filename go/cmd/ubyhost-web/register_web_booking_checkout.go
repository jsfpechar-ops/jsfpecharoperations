package main

// Brief 1542: POST /p/{slug}/checkout (card payments through Stripe Checkout).
// Off until the owner adds the path to UBYHOST_GO_PATHS (see brief 1550).
// pay_mode=direct answers "unavailable" until brief 1543 passes a Direct func.

import (
	"context"
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/booking"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		stripe := payments.NewStripeOnboarder(pool, os.Getenv, time.Now)
		c := booking.Checkout{Pool: pool, Getenv: os.Getenv, Now: time.Now,
			Session: func(ctx context.Context, in booking.SessionInput) (string, string, error) {
				return stripe.CreateCheckoutSession(ctx, payments.CheckoutParams(in))
			}}
		mux.Handle("POST /p/{slug}/checkout", m.wrap("/p/{slug}/checkout", c.Handler()))
	})
}
