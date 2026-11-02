package ubyport

// Queues the two notifications Python raises when a calendar cancels a stay
// whose guests already filled forms: the host e-mail and one push per device.
// Python source of truth: App/app/mail_notify.py cancelled_with_guests
// (1131-1190) and App/app/push.py cancelled_with_guests (528-548). Nothing
// calls these yet. Errors carry no address, text or key.

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

var errNotifyCancelled = errors.New("notify: cancelled-with-guests mail not queued")

// QueueCancelledWithGuestsMail returns the email_outbox id, or 0 when nothing is
// queued (mail off, no apartment, no contact address, no reservation). The
// idempotency key is cancelled_with_guests:<reservation>:<variant>. The mail
// row has no reservation_id, as in Python. variant is cancelled or disappeared.
// Base URLs come from getenv: UBYHOST_APP_BASE_URL, else UBYHOST_PUBLIC_BASE_URL.
func QueueCancelledWithGuestsMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	apartmentID, reservationID int64, variant string) (int64, error) {
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	if backend != "console" && backend != "ses" {
		return 0, nil
	}
	var entity, owner *int64
	var internalName *string
	err := pool.QueryRow(ctx,
		`SELECT legal_entity_id, owner_user_id, internal_name FROM apartment WHERE id = $1`, apartmentID,
	).Scan(&entity, &owner, &internalName)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, errNotifyCancelled
	}
	if entity == nil || *entity == 0 {
		return 0, nil
	}
	var contact *string
	err = pool.QueryRow(ctx, `SELECT contact_email FROM legal_entity WHERE id = $1`, *entity).Scan(&contact)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, errNotifyCancelled
	}
	raw := ""
	if contact != nil {
		raw = *contact
	}
	to := normaliseEmail(raw)
	if to == "" {
		return 0, nil
	}
	var dateFrom string
	err = pool.QueryRow(ctx, `SELECT date_from FROM reservation WHERE id = $1`, reservationID).Scan(&dateFrom)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, errNotifyCancelled
	}
	property := "UbyHost"
	if internalName != nil && *internalName != "" {
		property = *internalName
	}
	publicBase := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_PUBLIC_BASE_URL")), "/")
	appBase := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/")
	if appBase == "" {
		appBase = publicBase
	}
	content, err := mail.BuildCancelledWithGuests(appBase, publicBase, "en", property, dateFrom, variant, reservationID)
	if err != nil {
		return 0, errNotifyCancelled
	}
	return EnqueueMail(ctx, pool, OutboxMail{
		Kind:        "cancelled_with_guests",
		Key:         fmt.Sprintf("cancelled_with_guests:%d:%s", reservationID, variant),
		ApartmentID: &apartmentID,
		OwnerUserID: owner,
		To:          to,
		Subject:     content.Subject,
		Text:        content.Text,
		HTML:        content.HTML,
	})
}

// QueueCancelledWithGuestsPush returns how many push_outbox rows were inserted:
// one per device of the owner, key cancelled_with_guests:<reservation>:<device>.
// Params are property (internal name or "") and date (DD.MM.YYYY), each cut to
// 120 runes. URL is /reservations/<id>. Push off or no owner gives 0.
func QueueCancelledWithGuestsPush(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	apartmentID, reservationID int64) (int, error) {
	var dateFrom string
	var owner *int64
	var internalName *string
	err := pool.QueryRow(ctx,
		`SELECT r.date_from, a.owner_user_id, a.internal_name
		   FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		  WHERE r.id = $1 AND a.id = $2`, reservationID, apartmentID,
	).Scan(&dateFrom, &owner, &internalName)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, errNotifyPush
	}
	if owner == nil || *owner == 0 {
		return 0, nil
	}
	property := ""
	if internalName != nil {
		property = *internalName
	}
	params := AlertParams{
		"property": cutRunes(property, pushParamMax),
		"date":     cutRunes(pyDay(dateFrom), pushParamMax),
	}
	return QueuePush(ctx, pool, getenv, *owner, "cancelled_with_guests", strconv.FormatInt(reservationID, 10),
		fmt.Sprintf("/reservations/%d", reservationID), params)
}

// pyDay is push.py _day: an ISO date as DD.MM.YYYY, else the value unchanged.
func pyDay(value string) string {
	t, err := time.Parse("2006-01-02", value)
	if err != nil {
		return value
	}
	return t.Format("02.01.2006")
}
