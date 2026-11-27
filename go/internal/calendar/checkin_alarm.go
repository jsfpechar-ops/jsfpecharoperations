package calendar

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const (
	checkInIncompleteAlertKind = "guest_incomplete_checkin"
	checkInReminderMailKind    = "reminder_host"
)

type checkInAlarmRow struct {
	ID            int64
	ApartmentID   int64
	DateFrom      string
	DateTo        string
	Source        string
	Declared      *int64
	Override      *int64
	Reduced       *int64
	CheckinHour   *int64
	InternalName  string
	UbyName       string
	OwnerUserID   *int64
	LegalEntityID *int64
	ClaimState    string
	EmailMasked   string
}

const checkInAlarmRowsSQL = `
SELECT r.id, r.apartment_id, r.date_from, r.date_to, COALESCE(r.source, ''),
       r.declared_guests, r.expected_guests_override, r.lead_reduced_guests,
       a.checkin_hour, COALESCE(a.internal_name, ''), COALESCE(a.uby_name, ''),
       a.owner_user_id, a.legal_entity_id,
       COALESCE(c.state, ''), COALESCE(c.email_masked, '')
FROM reservation r
JOIN apartment a ON a.id = r.apartment_id
LEFT JOIN reservation_claim c ON c.reservation_id = r.id
WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
  AND a.archived_at IS NULL AND COALESCE(r.source, '') != 'demo'
  AND r.date_from >= $1 AND r.date_from <= $2
ORDER BY r.id`

// RunCheckInIncompleteAlarm checks active non-demo stays arriving today once
// the property's check-in hour (fallback 15:00 Europe/Prague) has started.
// When guest registration is still incomplete it raises the warning alert
// guest_incomplete_checkin:<id> and queues a distinct host email with
// idempotency key reminder_host:checkin:<id>:<YYYY-MM-DD>. When forms complete
// or check-in day has passed it resolves the alert automatically.
func RunCheckInIncompleteAlarm(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (int, error) {
	if getenv == nil {
		getenv = func(string) string { return "" }
	}
	local := deadlines.LocalNow(at)
	today := time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, time.UTC)
	windowStart := today.AddDate(0, 0, -7).Format("2006-01-02")
	todayStr := today.Format("2006-01-02")

	rows, err := pool.Query(ctx, checkInAlarmRowsSQL, windowStart, todayStr)
	if err != nil {
		return 0, err
	}
	var list []checkInAlarmRow
	for rows.Next() {
		var r checkInAlarmRow
		if err := rows.Scan(&r.ID, &r.ApartmentID, &r.DateFrom, &r.DateTo, &r.Source,
			&r.Declared, &r.Override, &r.Reduced,
			&r.CheckinHour, &r.InternalName, &r.UbyName,
			&r.OwnerUserID, &r.LegalEntityID,
			&r.ClaimState, &r.EmailMasked); err != nil {
			rows.Close()
			return 0, err
		}
		list = append(list, r)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}
	if len(list) == 0 {
		return 0, nil
	}

	stays := make([]AlertStay, 0, len(list))
	for _, r := range list {
		stays = append(stays, AlertStay{
			ID: r.ID, DateFrom: r.DateFrom, DateTo: r.DateTo,
			Declared: r.Declared, Override: r.Override, Reduced: r.Reduced,
		})
	}
	progress, err := AlertProgresses(ctx, pool, getenv, stays, at)
	if err != nil {
		return 0, err
	}

	raised := 0
	for _, r := range list {
		p := progress[r.ID]
		complete := p.Status == "reported" || p.Status == "not_required" ||
			(p.Expected != nil && p.Filled >= *p.Expected && p.Incomplete == 0)
		dedupeKey := fmt.Sprintf("%s:%d", checkInIncompleteAlertKind, r.ID)

		if r.DateFrom != todayStr || complete {
			if err := ubyport.ResolveAlert(ctx, pool, dedupeKey); err != nil {
				return raised, err
			}
			continue
		}

		var chPtr *int
		if r.CheckinHour != nil {
			v := int(*r.CheckinHour)
			chPtr = &v
		}
		checkInHour := ubyport.EffectiveCheckinHour(chPtr)
		if local.Hour() < checkInHour {
			continue
		}

		propName := strings.TrimSpace(r.InternalName)
		if propName == "" {
			propName = strings.TrimSpace(r.UbyName)
		}
		aptID := r.ApartmentID
		resID := r.ID
		if err := ubyport.RaiseAlert(ctx, pool, "warning", checkInIncompleteAlertKind,
			propName+" · check-in started", "Forms incomplete", dedupeKey,
			&aptID, &resID, nil, nil); err != nil {
			return raised, err
		}
		raised++

		if err := enqueueCheckInHostMail(ctx, pool, getenv, r, propName, p, checkInHour, today, at); err != nil {
			return raised, err
		}
	}
	return raised, nil
}

func enqueueCheckInHostMail(
	ctx context.Context,
	pool *pgxpool.Pool,
	getenv func(string) string,
	r checkInAlarmRow,
	propName string,
	p AlertProgress,
	checkInHour int,
	today time.Time,
	at time.Time,
) error {
	if !mailBackendEnabled(getenv) {
		return nil
	}
	if r.LegalEntityID == nil || *r.LegalEntityID == 0 {
		return nil
	}
	var rawEmail string
	err := pool.QueryRow(ctx, `SELECT COALESCE(contact_email, '') FROM legal_entity WHERE id = $1`, *r.LegalEntityID).Scan(&rawEmail)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	hostEmail := strings.TrimSpace(rawEmail)
	if hostEmail == "" || !strings.Contains(hostEmail, "@") {
		return nil
	}
	publicBase := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_PUBLIC_URL")), "/")
	if publicBase == "" {
		publicBase = strings.TrimRight(hostweb.AppBase(getenv), "/")
	}
	content := mailnotify.BuildReminderHost(publicBase, mailnotify.ReminderHostInput{
		Lang:           "en",
		PropertyName:   propName,
		Date:           today.Format("02.01.2006"),
		Assigned:       r.EmailMasked,
		StayURL:        strings.TrimRight(hostweb.AppBase(getenv), "/") + fmt.Sprintf("/reservations/%d#now", r.ID),
		Claimed:        r.ClaimState == "claimed",
		Filled:         p.Filled,
		Expected:       p.Expected,
		CheckInStarted: true,
		CheckInHour:    checkInHour,
	})
	payloadBytes, err := json.Marshal(map[string]string{
		"text": content.Text,
		"lang": "en",
		"html": content.HTML,
	})
	if err != nil {
		return err
	}
	aptID := r.ApartmentID
	resID := r.ID
	_, err = ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:          checkInReminderMailKind,
		Key:           fmt.Sprintf("reminder_host:checkin:%d:%s", r.ID, r.DateFrom),
		To:            hostEmail,
		Subject:       content.Subject,
		Payload:       string(payloadBytes),
		OwnerUserID:   r.OwnerUserID,
		ApartmentID:   &aptID,
		ReservationID: &resID,
	})
	return err
}

func mailBackendEnabled(getenv func(string) string) bool {
	b := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	return b != "" && b != "disabled" && b != "off" && b != "none"
}
