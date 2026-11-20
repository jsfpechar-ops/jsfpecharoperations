package doorwire

import (
	"context"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// Plans implements doorcodes.Plans as billing.entitlements(owner).ttlock.
type Plans struct {
	Pool   *pgxpool.Pool
	Getenv func(string) string // UBYHOST_BILLING_ENABLED
}

var _ doorcodes.Plans = Plans{}

// TTLockAllowed is billing.entitlements(owner).ttlock: false when billing is off or there
// is no billing row; paused and trial accounts keep no TTLock; otherwise Max or the
// TTLock add-on. The caller checks the door-code and TTLock switches itself.
func (p Plans) TTLockAllowed(ctx context.Context, ownerUserID int64) (bool, error) {
	if !billingEnabled(p.Getenv) {
		return false, nil
	}
	var status string
	var plan *string
	var addon int64
	err := p.Pool.QueryRow(ctx,
		"SELECT status, plan, addon_ttlock FROM billing_account WHERE owner_user_id = $1", ownerUserID).
		Scan(&status, &plan, &addon)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if status == "paused" || status == "trial_pending" || status == "trialing" {
		return false, nil
	}
	planName := "standard"
	if plan != nil && *plan != "" {
		planName = *plan
	}
	return planName == "max" || addon != 0, nil
}

// billingEnabled reads UBYHOST_BILLING_ENABLED the way config.py reads its switches.
// Approximation: the truthy words are 1, true, yes and on (case and space ignored).
func billingEnabled(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_BILLING_ENABLED"))) {
	case "1", "true", "yes", "on":
		return true
	}
	return false
}

// Push covers the push.notify side. The doorcodes.Push interface passes a title and a
// body, but push.notify takes a kind, key, url and params, so Notify cannot be faithful
// and returns an error. QueueDoorCode is push.notify(owner, "door_code", key=..., url=...,
// params=...) as QueuePush writes it.
type Push struct {
	Pool   *pgxpool.Pool
	Getenv func(string) string // UBYHOST_WEB_PUSH
}

var _ doorcodes.Push = Push{}

// QueueDoorCode is push.notify for kind door_code: one push_outbox row per device of the
// owner, key door_code:<key>:<subscription id>. It returns how many rows were queued.
func (p Push) QueueDoorCode(ctx context.Context, ownerUserID int64, key, url string, params ubyport.AlertParams) (int, error) {
	return ubyport.QueuePush(ctx, p.Pool, p.Getenv, ownerUserID, "door_code", key, url, params)
}

// Billing covers the fee block of the code mail. Not ported: reporting.reservation_progress
// and claim._completion_fee. The flow drops the fee block on error (contentWithFee), so the
// code mail still goes out without it.
type Billing struct{}

var _ doorcodes.Billing = Billing{}

// ReservationProgress is reporting.reservation_progress. Not ported.
func (Billing) ReservationProgress(ctx context.Context, reservationID int64) (int, *int, error) {
	return 0, nil, ErrNotPorted
}

// CompletionFee is claim._completion_fee. Not ported.
func (Billing) CompletionFee(ctx context.Context, apartmentID, reservationID int64) (map[string]any, error) {
	return nil, ErrNotPorted
}

// Confirmations covers claim.maybe_notify_completion. Not ported: the registration
// confirmation is large (claim.py) and is out of this phase. While it is not ported, a code
// mail for a stay whose confirmation has not gone is not sent (sendCodeMail returns the
// error and the flow logs it), and the held-confirmation safety net fails loudly.
type Confirmations struct{}

var _ doorcodes.Confirmations = Confirmations{}

// MaybeNotifyCompletion is claim.maybe_notify_completion. Not ported.
func (Confirmations) MaybeNotifyCompletion(ctx context.Context, reservationID, apartmentID int64, force bool) error {
	return ErrNotPorted
}
