package doorwire

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

// errStayNotFound is returned where Python would read a missing reservation row.
var errStayNotFound = errors.New("doorwire: reservation not found")

// errUnreadableGuest is returned where reservation_progress would raise DecryptionError.
var errUnreadableGuest = errors.New("doorwire: a guest field of the stay will not decrypt")

// LiveBilling implements doorcodes.Billing from the database. It is the live counterpart of
// the placeholder Billing in services.go, which stays as it is:
//   - ReservationProgress is reporting.reservation_progress, through calendar.AlertProgresses.
//   - CompletionFee is claim._completion_fee, through stayfee.LoadCompletionFee.
type LiveBilling struct {
	Pool     *pgxpool.Pool
	Getenv   func(string) string // the switches calendar.AlertProgresses reads; nil means os.Getenv
	Keys     *secure.MultiFernet // decrypts guest fields (db.decrypt_field); nil means none can be read
	GuestPay bool                // config.STAY_FEE_GUEST_PAY
	Now      func() time.Time    // nil means time.Now
}

var _ doorcodes.Billing = LiveBilling{}

func (b LiveBilling) now() time.Time {
	if b.Now != nil {
		return b.Now()
	}
	return time.Now()
}

func (b LiveBilling) getenv() func(string) string {
	if b.Getenv != nil {
		return b.Getenv
	}
	return os.Getenv
}

// decrypter opens a stored token the way stayfee expects. With no keys it fails every token.
func (b LiveBilling) decrypter() stayfee.Decrypter {
	if b.Keys == nil {
		return func(string) (string, error) { return "", secure.ErrInvalidToken }
	}
	return stayfee.FernetDecrypter(b.Keys)
}

// loadAlertStay reads the reservation columns reservation_progress reads.
func (b LiveBilling) loadAlertStay(ctx context.Context, reservationID int64) (calendar.AlertStay, bool, error) {
	var s calendar.AlertStay
	err := b.Pool.QueryRow(ctx,
		"SELECT id, date_from, date_to, declared_guests, expected_guests_override, lead_reduced_guests "+
			"FROM reservation WHERE id = $1", reservationID).
		Scan(&s.ID, &s.DateFrom, &s.DateTo, &s.Declared, &s.Override, &s.Reduced)
	if errors.Is(err, pgx.ErrNoRows) {
		return calendar.AlertStay{}, false, nil
	}
	if err != nil {
		return calendar.AlertStay{}, false, err
	}
	return s, true, nil
}

// ReservationProgress is reporting.reservation_progress: filled and expected (nil when the
// expected count is unknown) for the stay.
func (b LiveBilling) ReservationProgress(ctx context.Context, reservationID int64) (int, *int, error) {
	stay, found, err := b.loadAlertStay(ctx, reservationID)
	if err != nil {
		return 0, nil, err
	}
	if !found {
		return 0, nil, errStayNotFound
	}
	got, err := calendar.AlertProgresses(ctx, b.Pool, b.getenv(), []calendar.AlertStay{stay}, b.now())
	if err != nil {
		return 0, nil, err
	}
	p, ok := got[reservationID]
	if !ok {
		return 0, nil, errStayNotFound
	}
	if p.Unreadable {
		return 0, nil, errUnreadableGuest
	}
	return p.Filled, p.Expected, nil
}

// completionFee is claim._completion_fee as the typed stayfee value; nil when the guest pays
// no fee here. Any error is returned, and the caller drops the fee block.
func (b LiveBilling) completionFee(ctx context.Context, apartmentID, reservationID int64) (*stayfee.CompletionFee, error) {
	ap, err := stayfee.LoadApartment(ctx, b.Pool, apartmentID)
	if err != nil || ap == nil {
		return nil, err
	}
	y, m, d := b.now().UTC().Date()
	today := time.Date(y, m, d, 0, 0, 0, 0, time.UTC)
	return stayfee.LoadCompletionFee(ctx, b.Pool, b.decrypter(), ap, reservationID, b.GuestPay, today)
}

// CompletionFee is claim._completion_fee as the dict the Billing interface carries: the JSON
// keys of stayfee.CompletionFee (total, lines, rate, rails, ways, vs). nil when there is no fee.
func (b LiveBilling) CompletionFee(ctx context.Context, apartmentID, reservationID int64) (map[string]any, error) {
	fee, err := b.completionFee(ctx, apartmentID, reservationID)
	if err != nil || fee == nil {
		return nil, err
	}
	raw, err := json.Marshal(fee)
	if err != nil {
		return nil, err
	}
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	return out, nil
}
