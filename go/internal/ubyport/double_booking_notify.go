package ubyport

// Queues the host e-mail Python would raise for a double booking (brief 1166).
// Go-only feature: there is no Python builder, so there is no golden parity
// test. Errors carry no address, text or key.

import (
	"context"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

var errNotifyDoubleBooking = errors.New("notify: double-booking mail not queued")

// DoubleBooking carries one overlapping pair plus the alert dedupe key.
type DoubleBooking struct {
	ApartmentID                        int64
	Property, Key                      string
	FirstID, SecondID                  int64
	FirstFrom, FirstTo, FirstSource    string
	SecondFrom, SecondTo, SecondSource string
}

// QueueDoubleBookingMail returns the email_outbox id, or 0 when nothing is
// queued (mail off, no apartment, no contact address). The idempotency key is
// the alert dedupe key, so one mail per pair ever; a resolved and re-raised
// pair reopens the alert but sends no second mail.
func QueueDoubleBookingMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, b DoubleBooking) (int64, error) {
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	if backend != "console" && backend != "ses" {
		return 0, nil
	}
	var entity, owner *int64
	var internalName *string
	err := pool.QueryRow(ctx,
		`SELECT legal_entity_id, owner_user_id, internal_name FROM apartment WHERE id = $1`, b.ApartmentID,
	).Scan(&entity, &owner, &internalName)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, errNotifyDoubleBooking
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
		return 0, errNotifyDoubleBooking
	}
	to := normaliseEmail("")
	if contact != nil {
		to = normaliseEmail(*contact)
	}
	if to == "" {
		return 0, nil
	}
	property := b.Property
	if property == "" {
		if internalName != nil && *internalName != "" {
			property = *internalName
		} else {
			property = "UbyHost"
		}
	}
	publicBase := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_PUBLIC_BASE_URL")), "/")
	appBase := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/")
	if appBase == "" {
		appBase = publicBase
	}
	content := mail.BuildDoubleBooking(appBase, publicBase, property,
		mail.StaySpan{From: b.FirstFrom, To: b.FirstTo, Source: b.FirstSource},
		mail.StaySpan{From: b.SecondFrom, To: b.SecondTo, Source: b.SecondSource},
		b.SecondID)
	secondID := b.SecondID
	apartmentID := b.ApartmentID
	return EnqueueMail(ctx, pool, OutboxMail{
		Kind:          "double_booking",
		Key:           b.Key,
		ReservationID: &secondID,
		ApartmentID:   &apartmentID,
		OwnerUserID:   owner,
		To:            to,
		Subject:       content.Subject,
		Text:          content.Text,
		HTML:          content.HTML,
	})
}
