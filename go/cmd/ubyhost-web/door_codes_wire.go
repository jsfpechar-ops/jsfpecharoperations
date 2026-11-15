package main

// The door-codes wiring: builds the doorcodes.Reconciler from the environment.
//
// TODO-blocked: Mailer (mail_notify build_door_code, guest_payload, door_code_notice, mail
// enqueue and drain), Push (push.notify, door_code_missing), Plans (billing entitlements),
// Billing (reporting progress, claim completion fee), Confirmations (claim.maybe_notify_completion)
// and the phase-2 Lifecycle (lifecycle_revoke.go, lifecycle_cancel.go) are not ported yet. No
// fake stands in for them. newDoorCodesReconciler therefore always returns errDoorCodesBlocked
// after it has built the parts that do exist, so the job cannot run.

import (
	"errors"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// errDoorCodesBlocked is the wiring error until the TODO-blocked parts exist.
var errDoorCodesBlocked = errors.New("door_codes: wiring is blocked, the Mailer, Push, Plans, Billing, Confirmations and Lifecycle implementations are not ported yet")

// doorCodesParts is what exists today: config, data keys, the TTLock client, the lock_account store
// and the monthly budget guard.
type doorCodesParts struct {
	Config   ttlock.Config
	Keys     *secure.MultiFernet
	Client   *ttlock.Client
	Accounts ttlock.AccountStore
	Budget   *ttlock.PGBudget
}

// newDoorCodesParts reads the environment and builds the parts above. It uses the pool, so it is
// only called from a job run, never while the handler factory builds.
func newDoorCodesParts(pool *pgxpool.Pool) (doorCodesParts, error) {
	if pool == nil {
		return doorCodesParts{}, errors.New("door_codes: no database pool")
	}
	cfg, err := ttlock.ConfigFromEnv(os.Getenv)
	if err != nil {
		return doorCodesParts{}, err
	}
	keys, err := secure.LoadDataKeys(os.Getenv)
	if err != nil {
		return doorCodesParts{}, err
	}
	accounts := doorcodes.NewAccountStore(pool, keys)
	budget := ttlock.NewPGBudget(pool, cfg.MonthlyCalls, nil)
	client := ttlock.New(cfg, ttlock.Options{Accounts: accounts, Budget: budget})
	return doorCodesParts{Config: cfg, Keys: keys, Client: client, Accounts: accounts, Budget: budget}, nil
}

// newDoorCodesReconciler is the 'newDoorCodesService' step. It builds the existing parts, then
// returns errDoorCodesBlocked. When the TODO-blocked implementations land, this function builds
// doorcodes.Service{Pool, Keys, Settings{Enabled: UBYHOST_DOOR_CODES, Live: UBYHOST_DOOR_CODES_LIVE,
// BufferHours: 1}, TTLock: parts.Client, Accounts, Plans, Alerts: doorcodes.NewAlerts(pool), Mailer,
// Billing, Confirm, Push, Clock} and a doorcodes.Reconciler with Lifecycle, Budget: parts.Budget,
// BudgetLimit: parts.Config.MonthlyCalls, Locks: parts.Client and Delayed.
func newDoorCodesReconciler(pool *pgxpool.Pool) (*doorcodes.Reconciler, error) {
	if _, err := newDoorCodesParts(pool); err != nil {
		return nil, err
	}
	return nil, errDoorCodesBlocked
}
