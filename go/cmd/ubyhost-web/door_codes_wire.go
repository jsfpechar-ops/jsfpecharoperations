package main

// The door-codes wiring: builds the doorcodes.Reconciler and the cleaner-side queue from the
// environment, as _job_door_codes in App/app/scheduler.py needs them. Everything here touches the
// pool, so it runs on the first switched-on job run (see register_job_door_codes.go).

import (
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	doorcleaning "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes/cleaning"
	doorwire "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes/wire"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// doorCodesParts is the config, data keys, the TTLock client, the lock_account store and the
// monthly budget guard.
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

// systemClock is the real time for the door-code flow and the cleaner queue.
type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// doorCodesJob is the built job: the door-code reconciler and the cleaner-side collaborators.
type doorCodesJob struct {
	pool   *pgxpool.Pool
	rec    *doorcodes.Reconciler
	cleanQ doorcleaning.QueueDeps
	clock  systemClock
}

// newDoorCodesJob is the 'newDoorCodesService' step. It builds doorcodes.Service with the real
// Plans, Mailer, Billing, Confirmations, Push and Alerts, then the phase-2 Lifecycle, the delayed
// notifier and the Reconciler, and the cleaner queue deps. The settings come from
// UBYHOST_DOOR_CODES (on), UBYHOST_DOOR_CODES_LIVE (live) and DOOR_CODE_BUFFER_HOURS = 1 (config.py).
func newDoorCodesJob(pool *pgxpool.Pool) (*doorCodesJob, error) {
	parts, err := newDoorCodesParts(pool)
	if err != nil {
		return nil, err
	}
	mailCfg, err := mail.ConfigFromEnv(os.Getenv)
	if err != nil {
		return nil, fmt.Errorf("door_codes: mail config: %w", err)
	}
	clock := systemClock{}
	mailer := &doorwire.Mailer{
		Pool:       pool,
		Env:        doorCodeMailEnv(os.Getenv),
		Keys:       parts.Keys,
		Getenv:     os.Getenv,
		MailConfig: mailCfg,
	}
	billing := doorwire.LiveBilling{
		Pool:     pool,
		Getenv:   os.Getenv,
		Keys:     parts.Keys,
		GuestPay: strings.ToLower(strings.TrimSpace(os.Getenv("UBYHOST_STAY_FEE_GUEST_PAY"))) == "on",
	}
	push := doorwire.Push{Pool: pool, Getenv: os.Getenv}
	svc := &doorcodes.Service{
		Pool:     pool,
		Keys:     parts.Keys,
		Settings: doorCodesSettings(os.Getenv),
		TTLock:   parts.Client,
		Accounts: parts.Accounts,
		Plans:    doorwire.Plans{Pool: pool, Getenv: os.Getenv},
		Alerts:   doorcodes.NewAlerts(pool),
		Mailer:   mailer,
		Billing:  billing,
		Push:     push,
		Clock:    clock,
	}
	// Set after construction: the confirmation calls back into the door-code service.
	svc.Confirm = doorwire.LiveConfirmations{Pool: pool, Mailer: mailer, Billing: billing, Doors: svc}

	rec := &doorcodes.Reconciler{
		Svc: svc,
		Lifecycle: &doorcodes.Lifecycle{
			Service: svc,
			Notices: doorwire.HostNotices{Mailer: mailer},
			Locks:   parts.Client,
		},
		Budget:      parts.Budget,
		BudgetLimit: parts.Config.MonthlyCalls,
		Locks:       parts.Client,
		Delayed:     doorwire.Delayed{Pool: pool, Mailer: mailer, Push: push},
	}
	return &doorCodesJob{
		pool:  pool,
		rec:   rec,
		clock: clock,
		cleanQ: doorcleaning.QueueDeps{
			TTLock:         parts.Client,
			Cipher:         parts.Keys,
			Clock:          clock,
			StagingNoLogin: stagingNoLogin(os.Getenv),
		},
	}, nil
}

// doorCodesSettings reads the three switches the way config.py does.
func doorCodesSettings(getenv func(string) string) doorcodes.Settings {
	return doorcodes.Settings{
		Enabled:     doorCodesOn(getenv("UBYHOST_DOOR_CODES")),
		Live:        doorCodesOn(getenv("UBYHOST_DOOR_CODES_LIVE")),
		BufferHours: 1,
	}
}

// doorCodeMailEnv is mail_notify's config: app_base_url() (UBYHOST_APP_BASE_URL, else the public
// base), PUBLIC_BASE_URL and SUPPORT_EMAIL.
func doorCodeMailEnv(getenv func(string) string) mailnotify.DoorCodeMailEnv {
	public := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_PUBLIC_BASE_URL")), "/")
	if public == "" {
		public = "http://127.0.0.1:8080"
	}
	app := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/")
	if app == "" {
		app = public
	}
	return mailnotify.DoorCodeMailEnv{AppBaseURL: app, PublicBaseURL: public, SupportEmail: "support@ubyhost.com"}
}

// doorCodesStagingNoLogin is auth.staging_no_login: no queue work in that mode (the cleaner queue
// reads it through QueueDeps.StagingNoLogin).
func stagingNoLogin(getenv func(string) string) bool {
	if strings.ToLower(getenv("UBYHOST_DEPLOYMENT")) != "staging" {
		return false
	}
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STAGING_NO_LOGIN"))) {
	case "1", "true", "yes", "on":
		return true
	}
	return false
}
