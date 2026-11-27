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
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	// GuestReminderMailKind is email_outbox.kind for automated guest reminders.
	GuestReminderMailKind = "reminder_guest"

	// Cooldowns after claimed_at so a guest actively filling the form is not emailed mid-flow.
	guestReminderPostClaimMinHours  = 6
	guestReminderDayBeforeMinHours  = 3
	guestReminderCheckInDayMinHours = 2

	// Polite daytime window in Europe/Prague (09:00-20:59) so guests are never emailed overnight.
	guestReminderWindowStartHour = 9
	guestReminderWindowEndHour   = 21

	// Lead time before apartment.checkin_hour for the final check-in-day guest reminder.
	guestReminderCheckInLeadHours = 3
)

// GuestReminderPlan is the selected automatic reminder stage and its stable
// email_outbox.idempotency_key. Shared by calendar.RunGuestReminders (live
// deadlines job) and mailjob.SweepReminders so both paths stay deduped.
type GuestReminderPlan struct {
	Stage       string
	Key         string
	CheckInHour int
}

// DecideGuestReminder picks which automatic guest reminder stage (if any) is
// due for an incomplete, claimed, non-demo stay at now (Europe/Prague local
// day/hour). At most one reminder fires per stage (post-claim, day-before,
// check-in day), and never outside 09:00-20:59 Europe/Prague.
func DecideGuestReminder(
	reservationID int64,
	start time.Time,
	today time.Time,
	localHour int,
	checkInHour int,
	claimedAt string,
	now time.Time,
) (GuestReminderPlan, bool) {
	if localHour < guestReminderWindowStartHour || localHour >= guestReminderWindowEndHour {
		return GuestReminderPlan{}, false
	}
	claimed, ok := parseClaimedAt(claimedAt)
	if !ok {
		return GuestReminderPlan{}, false
	}
	elapsed := now.Sub(claimed)
	if elapsed < 0 {
		return GuestReminderPlan{}, false
	}
	dateStr := start.Format("2006-01-02")
	tomorrow := today.AddDate(0, 0, 1)

	switch {
	case start.Equal(today):
		sendHour := checkInHour - guestReminderCheckInLeadHours
		if sendHour < guestReminderWindowStartHour {
			sendHour = guestReminderWindowStartHour
		}
		if localHour >= sendHour && elapsed >= guestReminderCheckInDayMinHours*time.Hour {
			return GuestReminderPlan{
				Stage:       mailnotify.GuestReminderCheckInDay,
				Key:         fmt.Sprintf("reminder_guest:checkin:%d:%s", reservationID, dateStr),
				CheckInHour: checkInHour,
			}, true
		}
	case start.Equal(tomorrow):
		if elapsed >= guestReminderDayBeforeMinHours*time.Hour {
			return GuestReminderPlan{
				Stage:       mailnotify.GuestReminderDayBefore,
				Key:         fmt.Sprintf("reminder_guest:%d:%s", reservationID, dateStr),
				CheckInHour: checkInHour,
			}, true
		}
	case start.After(tomorrow):
		if elapsed >= guestReminderPostClaimMinHours*time.Hour {
			return GuestReminderPlan{
				Stage:       mailnotify.GuestReminderPostClaim,
				Key:         fmt.Sprintf("reminder_guest:post_claim:%d:%s", reservationID, dateStr),
				CheckInHour: checkInHour,
			}, true
		}
	}
	return GuestReminderPlan{}, false
}

func parseClaimedAt(raw string) (time.Time, bool) {
	if raw == "" {
		return time.Time{}, false
	}
	parsed, err := time.Parse(time.RFC3339Nano, strings.Replace(raw, "Z", "+00:00", 1))
	if err == nil {
		return parsed, true
	}
	parsed, err = time.ParseInLocation("2006-01-02T15:04:05", raw, time.UTC)
	if err != nil {
		return time.Time{}, false
	}
	return parsed, true
}

type guestReminderRow struct {
	ID             int64
	ApartmentID    int64
	DateFrom       string
	DateTo         string
	Source         string
	Declared       *int64
	Override       *int64
	Reduced        *int64
	CheckinHour    *int64
	InternalName   string
	UbyName        string
	PermalinkToken string
	OwnerUserID    *int64
	LegalEntityID  *int64
	ClaimEmail     string
	ClaimLang      string
	ClaimedAt      string
}

const guestReminderRowsSQL = `
SELECT r.id, r.apartment_id, r.date_from, r.date_to, COALESCE(r.source, ''),
       r.declared_guests, r.expected_guests_override, r.lead_reduced_guests,
       a.checkin_hour, COALESCE(a.internal_name, ''), COALESCE(a.uby_name, ''),
       COALESCE(a.permalink_token, ''), a.owner_user_id, a.legal_entity_id,
       COALESCE(rc.email, ''), COALESCE(rc.lang, ''), COALESCE(rc.claimed_at, '')
  FROM reservation r
  JOIN apartment a ON a.id = r.apartment_id
  JOIN reservation_claim rc ON rc.reservation_id = r.id
 WHERE r.status = 'active'
   AND r.archived_at IS NULL
   AND a.active = 1
   AND a.archived_at IS NULL
   AND COALESCE(r.source, '') <> 'demo'
   AND rc.state = 'claimed'
   AND COALESCE(rc.email, '') <> ''
   AND COALESCE(rc.claimed_at, '') <> ''
   AND r.date_from >= $1
 ORDER BY r.id`

// RunGuestReminders queues automatic incomplete-registration reminders for
// claimed non-demo stays arriving today or later. It runs inside Go's live
// deadlines job and shares exact idempotency keys with mailjob.SweepReminders
// so neither job ever queues duplicates.
func RunGuestReminders(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, at time.Time) (int, error) {
	if getenv == nil {
		getenv = func(string) string { return "" }
	}
	if !mailBackendEnabled(getenv) {
		return 0, nil
	}
	if langs := strings.TrimSpace(getenv("UBYHOST_GUEST_LANGS")); langs != "" {
		mailnotify.SetGuestLanguages(langs)
	}
	local := deadlines.LocalNow(at)
	today := time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, time.UTC)
	todayStr := today.Format("2006-01-02")

	rows, err := pool.Query(ctx, guestReminderRowsSQL, todayStr)
	if err != nil {
		return 0, err
	}
	var list []guestReminderRow
	for rows.Next() {
		var r guestReminderRow
		if err := rows.Scan(&r.ID, &r.ApartmentID, &r.DateFrom, &r.DateTo, &r.Source,
			&r.Declared, &r.Override, &r.Reduced,
			&r.CheckinHour, &r.InternalName, &r.UbyName,
			&r.PermalinkToken, &r.OwnerUserID, &r.LegalEntityID,
			&r.ClaimEmail, &r.ClaimLang, &r.ClaimedAt); err != nil {
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

	starts := make(map[int64]time.Time, len(list))
	stays := make([]AlertStay, 0, len(list))
	for _, r := range list {
		start, ok := validation.ParseISODate(r.DateFrom)
		if !ok {
			continue
		}
		starts[r.ID] = time.Date(start.Year(), start.Month(), start.Day(), 0, 0, 0, 0, time.UTC)
		stays = append(stays, AlertStay{
			ID: r.ID, DateFrom: r.DateFrom, DateTo: r.DateTo,
			Declared: r.Declared, Override: r.Override, Reduced: r.Reduced,
		})
	}
	if len(stays) == 0 {
		return 0, nil
	}
	progress, err := AlertProgresses(ctx, pool, getenv, stays, at)
	if err != nil {
		return 0, err
	}

	publicBase := strings.TrimRight(hostweb.PublicBase(getenv), "/")
	queued := 0
	for _, r := range list {
		start, ok := starts[r.ID]
		if !ok {
			continue
		}
		p := progress[r.ID]
		if p.Unreadable {
			continue
		}
		complete := p.Status == "reported" || p.Status == "not_required" ||
			(p.Expected != nil && p.Filled >= *p.Expected && p.Incomplete == 0)
		if complete {
			continue
		}
		var chPtr *int
		if r.CheckinHour != nil {
			v := int(*r.CheckinHour)
			chPtr = &v
		}
		checkInHour := ubyport.EffectiveCheckinHour(chPtr)
		plan, due := DecideGuestReminder(r.ID, start, today, local.Hour(), checkInHour, r.ClaimedAt, at)
		if !due {
			continue
		}
		to := ubyport.NormaliseEmail(r.ClaimEmail)
		if to == "" {
			continue
		}
		var existing int64
		err := pool.QueryRow(ctx, `SELECT id FROM email_outbox WHERE idempotency_key = $1`, plan.Key).Scan(&existing)
		if err == nil {
			continue
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return queued, err
		}

		lang := strings.TrimSpace(r.ClaimLang)
		if lang == "" {
			lang = "en"
		}
		propName := strings.TrimSpace(r.InternalName)
		if propName == "" {
			propName = strings.TrimSpace(r.UbyName)
		}
		if propName == "" {
			propName = mailnotify.GuestText(lang, "mail_property_fallback", nil)
		}
		host, replyTo, err := loadGuestReminderHost(ctx, pool, r.LegalEntityID)
		if err != nil {
			return queued, err
		}
		content := mailnotify.BuildReminderGuest(publicBase, mailnotify.ReminderGuestInput{
			Lang:         lang,
			PropertyName: propName,
			StayURL:      publicBase + fmt.Sprintf("/l/%s/%d", r.PermalinkToken, r.ID),
			Host:         host,
			Filled:       p.Filled,
			Expected:     p.Expected,
			Stage:        plan.Stage,
			CheckInHour:  plan.CheckInHour,
		})
		payloadMap := map[string]string{
			"text": content.Text,
			"lang": lang,
		}
		if content.HTML != "" {
			payloadMap["html"] = content.HTML
		}
		if replyTo != "" {
			payloadMap["reply_to"] = replyTo
		}
		payloadBytes, err := json.Marshal(payloadMap)
		if err != nil {
			return queued, err
		}
		aptID := r.ApartmentID
		resID := r.ID
		if _, err := ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
			Kind:          GuestReminderMailKind,
			Key:           plan.Key,
			To:            to,
			Subject:       content.Subject,
			Payload:       string(payloadBytes),
			OwnerUserID:   r.OwnerUserID,
			ApartmentID:   &aptID,
			ReservationID: &resID,
		}); err != nil {
			return queued, err
		}
		queued++
	}
	return queued, nil
}

func loadGuestReminderHost(ctx context.Context, pool *pgxpool.Pool, legalEntityID *int64) (*mailnotify.Host, string, error) {
	if legalEntityID == nil || *legalEntityID == 0 {
		return nil, "", nil
	}
	var h mailnotify.Host
	var rawEmail string
	err := pool.QueryRow(ctx,
		`SELECT COALESCE(name, ''), COALESCE(seat, ''), COALESCE(contact_email, ''), COALESCE(contact_phone, '')
		   FROM legal_entity WHERE id = $1`, *legalEntityID).
		Scan(&h.Name, &h.Seat, &rawEmail, &h.Phone)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, "", nil
	}
	if err != nil {
		return nil, "", err
	}
	h.Name = strings.TrimSpace(h.Name)
	h.Seat = strings.TrimSpace(h.Seat)
	h.Phone = strings.TrimSpace(h.Phone)
	h.Email = ubyport.NormaliseEmail(rawEmail)
	return &h, h.Email, nil
}
