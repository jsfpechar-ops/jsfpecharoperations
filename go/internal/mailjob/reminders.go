package mailjob

// The day-before guest reminder, the check-in-day host nudge and the
// guest_incomplete_checkin alert: claim.sweep_reminders in App/app/claim.py,
// with mail.enqueue's gates (mailEnabled, demo stay, address) and alerts.raise_alert
// / alerts.resolve. The copy comes from mailnotify (BuildReminderGuest and
// BuildReminderHost), which mirror mail_notify.build_reminder_guest/host. The
// trailing outbox drain (mail.drain(limit=8)) is not here: the caller drains.

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

const (
	reminderGuestKind     = "reminder_guest"
	reminderHostKind      = "reminder_host"
	incompleteCheckinKind = "guest_incomplete_checkin"
	claimStateClaimed     = "claimed" // claim.CLAIMED
	// claim.REMINDER_GUEST_MIN_HOURS_AFTER_CLAIM
	reminderGuestMinHoursAfterClaim = 6
	// mail.GUEST_KINDS contains reminder_guest, so the demo-stay gate applies to it.
	hostLanguage = "en" // mail_notify.HOST_MAIL_LANGUAGE
)

// guestLanguagesOnce applies UBYHOST_GUEST_LANGS to mailnotify once per process.
var guestLanguagesOnce sync.Once

// configureGuestLanguages is the startup step for mailnotify.SetGuestLanguages.
// The default list is en,cs, as in the Python config.
func configureGuestLanguages(getenv func(string) string) {
	guestLanguagesOnce.Do(func() {
		raw := strings.TrimSpace(getenv("UBYHOST_GUEST_LANGS"))
		if raw == "" {
			raw = "en,cs"
		}
		mailnotify.SetGuestLanguages(raw)
	})
}

// publicBase is config.PUBLIC_BASE_URL: UBYHOST_PUBLIC_BASE_URL, with the
// local default, and no trailing slash.
func publicBase(getenv func(string) string) string {
	base := strings.TrimSpace(getenv("UBYHOST_PUBLIC_BASE_URL"))
	if base == "" {
		base = "http://127.0.0.1:8080"
	}
	return strings.TrimRight(base, "/")
}

// reminderRow is one row of the sweep's SELECT: the reservation, its apartment
// and its claim (nil columns of the LEFT JOIN read as empty strings).
type reminderRow struct {
	ID             int64
	ApartmentID    int64
	DateFrom       string
	DateTo         string
	Source         string
	Declared       *int64
	Override       *int64
	Reduced        *int64
	PermalinkToken string
	InternalName   string
	UbyName        string
	CheckinHour    *int64
	OwnerUserID    *int64
	LegalEntityID  *int64
	ClaimState     string
	ClaimEmail     string
	ClaimLang      string
	EmailMasked    string
	ClaimedAt      string
}

// reminderRowsSQL is the SELECT in sweep_reminders. It has no ORDER BY in
// Python; ORDER BY r.id here makes the outbox row order deterministic.
const reminderRowsSQL = `
SELECT r.id, r.apartment_id, r.date_from, r.date_to, COALESCE(r.source, ''),
       r.declared_guests, r.expected_guests_override, r.lead_reduced_guests,
       COALESCE(a.permalink_token, ''), COALESCE(a.internal_name, ''), COALESCE(a.uby_name, ''),
       a.checkin_hour, a.owner_user_id, a.legal_entity_id,
       COALESCE(c.state, ''), COALESCE(c.email, ''), COALESCE(c.lang, ''),
       COALESCE(c.email_masked, ''), COALESCE(c.claimed_at, '')
FROM reservation r
JOIN apartment a ON a.id = r.apartment_id
LEFT JOIN reservation_claim c ON c.reservation_id = r.id
WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
  AND a.archived_at IS NULL
ORDER BY r.id`

// SweepReminders is claim.sweep_reminders. It returns the counters of the Python
// summary dict: guest, host, host_early and locked (always 0, as in Python).
// Mail is queued through ubyport.EnqueueMail and alerts through ubyport.RaiseAlert
// and ubyport.ResolveAlert. The backend is read from UBYHOST_MAIL_BACKEND.
func SweepReminders(ctx context.Context, pool *pgxpool.Pool, now time.Time) (map[string]int, error) {
	getenv := os.Getenv
	configureGuestLanguages(getenv)
	summary := map[string]int{"guest": 0, "host": 0, "host_early": 0, "locked": 0}

	local := deadlines.LocalNow(now)
	today := dayOf(local)
	hour := local.Hour()

	rows, err := loadReminderRows(ctx, pool)
	if err != nil {
		return nil, err
	}
	// Only stays with a readable start date reach the progress read, as in Python
	// where the date check comes first.
	starts := make(map[int64]time.Time, len(rows))
	stays := make([]calendar.AlertStay, 0, len(rows))
	for _, r := range rows {
		start, ok := validation.ParseISODate(r.DateFrom)
		if !ok {
			continue
		}
		starts[r.ID] = dayOf(start)
		stays = append(stays, calendar.AlertStay{
			ID: r.ID, DateFrom: r.DateFrom, DateTo: r.DateTo,
			Declared: r.Declared, Override: r.Override, Reduced: r.Reduced,
		})
	}
	progress, err := calendar.AlertProgresses(ctx, pool, getenv, stays, now)
	if err != nil {
		return nil, err
	}

	for _, r := range rows {
		start, ok := starts[r.ID]
		if !ok {
			continue
		}
		p := progress[r.ID]
		if p.Unreadable {
			// db.DecryptionError: Python logs and skips the stay before any alert change.
			slog.Error("reminder sweep skipped reservation", "reservation_id", r.ID)
			continue
		}
		complete := formsComplete(p)
		if complete || start.Before(today) {
			// After the check-in day has passed the deadline chase is the reminder that is still true.
			if err := ubyport.ResolveAlert(ctx, pool, incompleteKey(r.ID)); err != nil {
				return nil, err
			}
		}

		tomorrow := today.AddDate(0, 0, 1)
		if start.Equal(tomorrow) && hour >= 9 && r.ClaimState == claimStateClaimed &&
			r.ClaimEmail != "" && claimMature(r.ClaimedAt, now) && !complete {
			lang := r.ClaimLang
			if lang == "" {
				lang = "en"
			}
			host, err := hostDetails(ctx, pool, r.LegalEntityID)
			if err != nil {
				return nil, err
			}
			content := mailnotify.BuildReminderGuest(publicBase(getenv), mailnotify.ReminderGuestInput{
				Lang:         lang,
				PropertyName: propertyLabel(r, lang),
				StayURL:      publicBase(getenv) + fmt.Sprintf("/l/%s/%d", r.PermalinkToken, r.ID),
				Host:         host,
				Filled:       p.Filled,
				Expected:     p.Expected,
			})
			replyTo, err := entityContactEmail(ctx, pool, r.LegalEntityID)
			if err != nil {
				return nil, err
			}
			payload := encodePayload(
				kv{"text", content.Text}, kv{"lang", lang}, kv{"html", content.HTML},
				kv{"reply_to", replyTo}, // html and reply_to only when set
			)
			queued, err := queueMail(ctx, pool, getenv, r, mailRequest{
				kind:    reminderGuestKind,
				key:     fmt.Sprintf("reminder_guest:%d:%s", r.ID, start.Format("2006-01-02")),
				to:      r.ClaimEmail,
				subject: content.Subject,
				payload: payload,
			})
			if err != nil {
				return nil, err
			}
			if queued {
				summary["guest"]++
			}
		}

		// 2094: day-before 18:00 nudge and check-in-time alarm use distinct idempotency keys
		// so the day-before reminder never suppresses the check-in-time email.
		var chPtr *int
		if r.CheckinHour != nil {
			v := int(*r.CheckinHour)
			chPtr = &v
		}
		checkInHour := ubyport.EffectiveCheckinHour(chPtr)
		early := start.Equal(tomorrow) && hour >= 18 && !complete &&
			p.Status != "reported" && p.Status != "not_required" && r.Source != "demo"
		checkInDue := start.Equal(today) && hour >= checkInHour && !complete &&
			p.Status != "reported" && p.Status != "not_required" && r.Source != "demo"
		if early || checkInDue {
			hostEmail, err := entityContactEmail(ctx, pool, r.LegalEntityID)
			if err != nil {
				return nil, err
			}
			if hostEmail != "" {
				mailKey := fmt.Sprintf("reminder_host:checkin:%d:%s", r.ID, start.Format("2006-01-02"))
				if early {
					mailKey = fmt.Sprintf("reminder_host:day_before:%d:%s", r.ID, start.Format("2006-01-02"))
				}
				content := mailnotify.BuildReminderHost(publicBase(getenv), mailnotify.ReminderHostInput{
					Lang:           hostLanguage,
					PropertyName:   propertyTitle(r),
					Date:           start.Format("02.01.2006"),
					Assigned:       r.EmailMasked,
					StayURL:        strings.TrimRight(hostweb.AppBase(getenv), "/") + fmt.Sprintf("/reservations/%d#now", r.ID),
					Claimed:        r.ClaimState == claimStateClaimed,
					Filled:         p.Filled,
					Expected:       p.Expected,
					Tomorrow:       early,
					CheckInStarted: checkInDue,
					CheckInHour:    checkInHour,
				})
				if _, err := queueMail(ctx, pool, getenv, r, mailRequest{
					kind:    reminderHostKind,
					key:     mailKey,
					to:      hostEmail,
					subject: content.Subject,
					payload: encodePayload(kv{"text", content.Text}, kv{"lang", hostLanguage}, kv{"html", content.HTML}),
				}); err != nil {
					return nil, err
				}
			}
			if early {
				summary["host_early"]++
				continue
			}
			if err := ubyport.RaiseAlert(ctx, pool, "warning", incompleteCheckinKind,
				propertyTitle(r)+" · check-in today", "Forms incomplete", incompleteKey(r.ID),
				ptr(r.ApartmentID), ptr(r.ID), nil, nil); err != nil {
				return nil, err
			}
			summary["host"]++
		}
	}
	return summary, nil
}

func loadReminderRows(ctx context.Context, pool *pgxpool.Pool) ([]reminderRow, error) {
	rows, err := pool.Query(ctx, reminderRowsSQL)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []reminderRow
	for rows.Next() {
		var r reminderRow
		if err := rows.Scan(&r.ID, &r.ApartmentID, &r.DateFrom, &r.DateTo, &r.Source,
			&r.Declared, &r.Override, &r.Reduced,
			&r.PermalinkToken, &r.InternalName, &r.UbyName,
			&r.CheckinHour, &r.OwnerUserID, &r.LegalEntityID,
			&r.ClaimState, &r.ClaimEmail, &r.ClaimLang, &r.EmailMasked, &r.ClaimedAt); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// formsComplete is alerts.forms_complete.
func formsComplete(p calendar.AlertProgress) bool {
	if p.Status == "reported" || p.Status == "not_required" {
		return true
	}
	return p.Expected != nil && p.Filled >= *p.Expected && p.Incomplete == 0
}

func incompleteKey(reservationID int64) string {
	return fmt.Sprintf("%s:%d", incompleteCheckinKind, reservationID)
}

// claimMature is claim._reminder_guest_claim_mature with the sweep's clock.
// An unreadable stamp counts as not mature (Python raises ValueError there).
func claimMature(claimedAt string, now time.Time) bool {
	if claimedAt == "" {
		return false
	}
	parsed, err := time.Parse(time.RFC3339Nano, strings.Replace(claimedAt, "Z", "+00:00", 1))
	if err != nil {
		parsed, err = time.ParseInLocation("2006-01-02T15:04:05", claimedAt, time.UTC)
		if err != nil {
			return false
		}
	}
	return now.Sub(parsed) >= reminderGuestMinHoursAfterClaim*time.Hour
}

// propertyLabel is mail_notify.property_label: the host's name first, then the
// police-register name, then the translated stand-in for a missing name.
func propertyLabel(r reminderRow, lang string) string {
	if name := strings.TrimSpace(r.InternalName); name != "" {
		return name
	}
	if name := strings.TrimSpace(r.UbyName); name != "" {
		return name
	}
	return mailnotify.GuestText(lang, "mail_property_fallback", nil)
}

// propertyTitle is the internal name as the alert prints it (no fallback).
func propertyTitle(r reminderRow) string { return r.InternalName }

// hostDetails is mail_notify.host_details: the footer's operating entity. It is
// nil when the stay has no legal entity or the row is gone, as Python's {} is.
func hostDetails(ctx context.Context, pool *pgxpool.Pool, legalEntityID *int64) (*mailnotify.Host, error) {
	if legalEntityID == nil || *legalEntityID == 0 {
		return nil, nil
	}
	var h mailnotify.Host
	var email string
	err := pool.QueryRow(ctx,
		`SELECT COALESCE(name, ''), COALESCE(seat, ''), COALESCE(contact_email, ''), COALESCE(contact_phone, '')
		   FROM legal_entity WHERE id = $1`, *legalEntityID).
		Scan(&h.Name, &h.Seat, &email, &h.Phone)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	h.Name = strings.TrimSpace(h.Name)
	h.Seat = strings.TrimSpace(h.Seat)
	h.Phone = strings.TrimSpace(h.Phone)
	h.Email = ubyport.NormaliseEmail(email)
	return &h, nil
}

// entityContactEmail is mail_notify._entity_contact_email.
func entityContactEmail(ctx context.Context, pool *pgxpool.Pool, legalEntityID *int64) (string, error) {
	if legalEntityID == nil || *legalEntityID == 0 {
		return "", nil
	}
	var raw string
	err := pool.QueryRow(ctx, `SELECT COALESCE(contact_email, '') FROM legal_entity WHERE id = $1`,
		*legalEntityID).Scan(&raw)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return ubyport.NormaliseEmail(raw), nil
}

// mailRequest is one mail.enqueue call from the sweep.
type mailRequest struct {
	kind, key, to, subject, payload string
}

// queueMail is mail.enqueue's gates followed by ubyport.EnqueueMail. It reports
// whether Python's enqueue would have returned a row id (an existing key counts,
// as it does in Python).
func queueMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	r reminderRow, m mailRequest) (bool, error) {
	if !mailEnabled(getenv) {
		return false, nil
	}
	if m.kind == reminderGuestKind && r.Source == "demo" {
		return false, nil
	}
	to := ubyport.NormaliseEmail(m.to)
	if to == "" {
		return false, nil
	}
	rid, aid := r.ID, r.ApartmentID
	if _, err := ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:          m.kind,
		Key:           m.key,
		ReservationID: &rid,
		ApartmentID:   &aid,
		OwnerUserID:   r.OwnerUserID,
		To:            to,
		Subject:       m.subject,
		Payload:       m.payload,
	}); err != nil {
		return false, err
	}
	return true, nil
}

// mailEnabled is mail.mail_enabled: backend console or ses.
func mailEnabled(getenv func(string) string) bool {
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	return backend == "console" || backend == "ses"
}

type kv struct {
	k, v string
}

// encodePayload writes a payload as json.dumps does for a dict of strings
// (insertion order, ", " and ": " separators, ensure_ascii). An empty html or
// reply_to is left out, as the Python code leaves a missing key out.
func encodePayload(pairs ...kv) string {
	var b strings.Builder
	b.WriteByte('{')
	first := true
	for _, p := range pairs {
		if p.v == "" && (p.k == "reply_to" || p.k == "html") {
			continue
		}
		if !first {
			b.WriteString(", ")
		}
		first = false
		b.WriteString(ubyport.PyString(p.k))
		b.WriteString(": ")
		b.WriteString(ubyport.PyString(p.v))
	}
	b.WriteByte('}')
	return b.String()
}

func dayOf(t time.Time) time.Time {
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, time.UTC)
}

func ptr[T any](v T) *T { return &v }
