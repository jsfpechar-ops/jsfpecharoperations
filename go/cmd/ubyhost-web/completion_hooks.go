package main

// Brief 2065 step 5: the registration hooks for guest_form_save (door_codes.on_registration_complete,
// then claim.maybe_notify_completion). The door-code wiring is built on the first hook call, once per
// route registration. If it cannot be built (no TTLock or data-key config), the adapter still runs the
// registration receipt through a viewer that reports "no code", so apartments without door codes keep
// getting their receipt. Errors are logged, never raised: the guest save must not fail.

import (
	"context"
	"log/slog"
	"os"
	"strings"
	"sync"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	doorwire "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes/wire"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest"
)

// completionAdapter implements guest.CompletionHooks. svc is nil when the door-code wiring is off
// or could not be built; confirm is nil only when there is no pool.
// When the build fails, the receipt is held for door-code apartments and sent without a code for the rest.
type completionAdapter struct {
	pool    *pgxpool.Pool
	once    sync.Once
	svc     *doorcodes.Service
	confirm doorcodes.Confirmations
}

// completionHooks returns the adapter for the guest save route.
func completionHooks(pool *pgxpool.Pool) guest.CompletionHooks {
	return &completionAdapter{pool: pool}
}

// noDoorCodes is the viewer used when the door-code service cannot be built. An apartment with
// lock_provider 'ttlock' uses door codes, so its receipt is held (the same hold Python and Go use
// while a code is prepared); ReleaseHeldConfirmations sends it later with the code. Only apartments
// without door codes get the receipt "without" a code.
type noDoorCodes struct{}

func (noDoorCodes) CompletionDoorCode(_ context.Context, _ doorcodes.Reservation, apt doorcodes.Apartment) (doorcodes.CompletionResult, error) {
	if apt.LockProvider == "ttlock" {
		return doorcodes.CompletionResult{Action: doorcodes.CompletionHold}, nil
	}
	return doorcodes.CompletionResult{Action: doorcodes.CompletionWithout}, nil
}

// build runs once. It never panics and never returns an error: a failed build is logged once.
func (a *completionAdapter) build() {
	a.once.Do(func() {
		if a.pool == nil {
			return
		}
		job, err := newDoorCodesJob(a.pool)
		if err == nil {
			a.svc = job.rec.Svc
			a.confirm = job.rec.Svc.Confirm
			return
		}
		slog.Warn("completion hooks: door-code wiring not built; receipts go without door codes", "error", err)
		billing := doorwire.LiveBilling{
			Pool:     a.pool,
			Getenv:   os.Getenv,
			GuestPay: strings.ToLower(strings.TrimSpace(os.Getenv("UBYHOST_STAY_FEE_GUEST_PAY"))) == "on",
		}
		a.confirm = doorwire.LiveConfirmations{
			Pool:    a.pool,
			Mailer:  &doorwire.Mailer{Pool: a.pool, Env: doorCodeMailEnv(os.Getenv), Getenv: os.Getenv},
			Billing: billing,
			Doors:   noDoorCodes{},
		}
	})
}

// OnRegistrationComplete issues the door code for a completed registration, when door codes are on.
func (a *completionAdapter) OnRegistrationComplete(ctx context.Context, reservationID int64) {
	a.build()
	if a.svc != nil {
		a.svc.OnRegistrationComplete(ctx, reservationID)
	}
}

// MaybeNotifyCompletion queues the registration receipt when it is due.
func (a *completionAdapter) MaybeNotifyCompletion(ctx context.Context, reservationID, apartmentID int64, force bool) error {
	a.build()
	if a.confirm == nil {
		return nil
	}
	return a.confirm.MaybeNotifyCompletion(ctx, reservationID, apartmentID, force)
}
