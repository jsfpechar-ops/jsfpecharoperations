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

// Billing implements doorcodes.Billing from the database (reporting.reservation_progress
// and claim._completion_fee). Alias for LiveBilling.
type Billing = LiveBilling

// Confirmations implements doorcodes.Confirmations from the database
// (claim.maybe_notify_completion). Alias for LiveConfirmations.
type Confirmations = LiveConfirmations
