package doorcodes

import (
	"context"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// Clock is the current time. Tests use a fixed clock.
type Clock interface {
	Now() time.Time
}

// TTLock is the part of go/internal/ttlock Client that the door-code flow calls.
// The real *ttlock.Client satisfies it. Tests never call the real API.
type TTLock interface {
	Enabled() bool
	CreatePeriodCode(ctx context.Context, accountID int64, lockID string, startMS, endMS int64, name, priority string) (string, string, error)
	AddCustomCode(ctx context.Context, accountID int64, lockID string, startMS, endMS int64, name, priority string) (string, string, error)
	FindCodeByName(ctx context.Context, accountID int64, lockID, name string, startMS, endMS int64) (string, string, bool, error)
}

// Alert is one host alert (alerts.raise_alert arguments the door-code flow uses).
type Alert struct {
	Level         string
	Kind          string
	Message       string
	DedupeKey     string
	ApartmentID   int64 // 0 when none
	ReservationID int64 // 0 when none
	Params        map[string]any
}

// Alerts raises and resolves host alerts (App/app/alerts.py raise_alert and resolve).
type Alerts interface {
	Raise(ctx context.Context, a Alert) error
	Resolve(ctx context.Context, dedupeKey string) error
}

// Plans says whether the owner's plan allows TTLock (billing.entitlements(...).ttlock).
type Plans interface {
	TTLockAllowed(ctx context.Context, ownerUserID int64) (bool, error)
}

// DoorCodeMail is the input of mail_notify.build_door_code.
type DoorCodeMail struct {
	Lang         string
	PropertyName string
	Checkin      string
	Checkout     string
	FirstUseBy   string
	Fee          map[string]any // nil when the fee block does not ride along
}

// DoorCodeContent is what build_door_code returns, as far as the door-code flow reads it.
type DoorCodeContent struct {
	Subject string
	QRSpayd string // empty when none
	Fields  map[string]any
}

// OutboxMail is the mail.enqueue call for kind door_code.
type OutboxMail struct {
	Kind           string
	IdempotencyKey string
	ToEmail        string
	CcEmail        string
	Subject        string
	Payload        map[string]any
	ReservationID  int64
	ApartmentID    int64
	OwnerUserID    int64
}

// Mailer covers the mail_notify and mail calls. The implementation is a later phase.
type Mailer interface {
	// BuildDoorCode is mail_notify.build_door_code(lang, property_name, checkin, checkout, first_use_by[, fee]).
	BuildDoorCode(ctx context.Context, in DoorCodeMail) (DoorCodeContent, error)
	// GuestPayload is mail_notify.guest_payload(apartment, content, lang) for the apartment with this id.
	GuestPayload(ctx context.Context, apartmentID int64, content DoorCodeContent, lang string) (map[string]any, error)
	// DoorCodeNotice is mail_notify.door_code_notice(door_code_id, stage) (the host notice).
	DoorCodeNotice(ctx context.Context, doorCodeID int64, stage string) error
	// Enqueue is mail.enqueue. ok is false when the idempotency key already exists (Python None).
	Enqueue(ctx context.Context, m OutboxMail) (outboxID int64, ok bool, err error)
	// Drain is mail.drain(limit=...).
	Drain(ctx context.Context, limit int) error
}

// Billing gives the fee block of the code mail: reporting.reservation_progress and claim._completion_fee.
type Billing interface {
	// ReservationProgress returns filled and expected (nil when unknown) for the stay.
	ReservationProgress(ctx context.Context, reservationID int64) (filled int, expected *int, err error)
	// CompletionFee is claim._completion_fee(apartment, reservation); nil when there is no fee.
	CompletionFee(ctx context.Context, apartmentID, reservationID int64) (map[string]any, error)
}

// Confirmations sends a held registration confirmation (claim.maybe_notify_completion).
type Confirmations interface {
	MaybeNotifyCompletion(ctx context.Context, reservationID, apartmentID int64, force bool) error
}

// Push is the push.notify call. Lines 1-801 of door_codes.py never call it; later phases may.
type Push interface {
	Notify(ctx context.Context, ownerUserID int64, title, body string) error
}

// Settings are the config.py values the door-code flow reads.
type Settings struct {
	Enabled     bool // DOOR_CODES_ENABLED
	Live        bool // DOOR_CODES_LIVE
	BufferHours int  // DOOR_CODE_BUFFER_HOURS
}

// Service is the door-code flow. Each method is one function of door_codes.py.
type Service struct {
	Pool     *pgxpool.Pool
	Keys     *secure.MultiFernet
	Settings Settings
	TTLock   TTLock
	Accounts ttlock.AccountStore
	Plans    Plans
	Alerts   Alerts
	Mailer   Mailer
	Billing  Billing
	Confirm  Confirmations
	Push     Push
	Clock    Clock
	Log      *slog.Logger
}

// ubyportAlerts implements Alerts on the shared alert table (ubyport.RaiseAlert, ResolveAlert).
type ubyportAlerts struct {
	pool *pgxpool.Pool
}

// NewAlerts returns the Alerts implementation backed by the alert table.
func NewAlerts(pool *pgxpool.Pool) Alerts {
	return ubyportAlerts{pool: pool}
}

func (a ubyportAlerts) Raise(ctx context.Context, in Alert) error {
	var apartmentID, reservationID *int64
	if in.ApartmentID != 0 {
		v := in.ApartmentID
		apartmentID = &v
	}
	if in.ReservationID != 0 {
		v := in.ReservationID
		reservationID = &v
	}
	return ubyport.RaiseAlert(ctx, a.pool, in.Level, in.Kind, in.Message, "", in.DedupeKey,
		apartmentID, reservationID, nil, ubyport.AlertParams(in.Params))
}

func (a ubyportAlerts) Resolve(ctx context.Context, dedupeKey string) error {
	return ubyport.ResolveAlert(ctx, a.pool, dedupeKey)
}
