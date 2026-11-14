package main

// Brief 1542: POST /p/{slug}/checkout (card payments through Stripe Checkout).
// Off until the owner adds the path to UBYHOST_GO_PATHS (see brief 1550).
// pay_mode=direct is served by booking.Direct (brief 1543).

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
		c.Direct = booking.Direct{Pool: pool, Getenv: os.Getenv, Now: time.Now, QR: payments.QRDataURI}.Start
		mux.Handle("POST /p/{slug}/checkout", m.wrap("/p/{slug}/checkout", c.Handler()))
	})
}
