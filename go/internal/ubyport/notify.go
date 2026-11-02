package ubyport

// Queues the two best-effort notifications that Python raises when UbyPort
// does not take a batch: the submission_problem e-mail and the filing_problem
// push. Same rows, same idempotency keys, as Python writes them.
//
// Python source of truth:
//   - App/app/mail_notify.py: submission_problem / _submission_problem
//     (827-918), _entity_contact_email (135), stays_for_submission (177).
//   - App/app/mail.py: enqueue (231-300), normalise_email (157), mail_enabled (185).
//   - App/app/push.py: notify (267-308), _clean_params (254), filing_problem (468-483),
//     enabled (57).
//   - App/app/deadlines.py: local_now (46), zone Europe/Prague.
//
// Both functions are best-effort in Python: they never fail a filing. Here they
// return an error and the caller logs it and carries on. Errors never carry an
// e-mail address, a reason text or an idempotency key.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"
	_ "time/tzdata" // the Prague zone must exist even on a bare container

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

// ApartmentRef is the apartment columns the notifications read.
type ApartmentRef struct {
	ID            int64
	LegalEntityID *int64
	OwnerUserID   *int64
	InternalName  string
}

const (
	pushParamMax   = 120 // push.py _PARAM_MAX
	mailSubjectMax = 200 // mail.py enqueue subject[:200]
	mailAddrMax    = 254 // mail.py normalise_email
	pragueZone     = "Europe/Prague"
)

// mailAddrRE is mail.py _EMAIL_RE.
var mailAddrRE = regexp.MustCompile(`^[^@\s]+@[^@\s]+\.[^@\s]+$`)

var (
	errNotifyStays = errors.New("notify: stays query failed")
	errNotifyZone  = errors.New("notify: local zone unavailable")
	errNotifyMail  = errors.New("notify: submission problem mail not queued")
	errNotifyPush  = errors.New("notify: filing problem push not queued")
	errNotifyBuild = errors.New("notify: submission problem mail not composed")
)

// normaliseEmail is mail.py normalise_email. Python uses email.utils.parseaddr,
// which is lenient; this supports only the two forms the app stores: a plain
// address, or "Name <addr>". Anything else (commas, several "<" or ">", quotes,
// text after ">") returns "", which means no mail. The address is then lower
// cased and checked with the same regex and length limit as Python.
func normaliseEmail(raw string) string {
	s := strings.TrimSpace(raw)
	if strings.ContainsAny(s, ",\"") || strings.Count(s, "<") > 1 || strings.Count(s, ">") > 1 {
		return ""
	}
	addr := s
	if i := strings.Index(s, "<"); i >= 0 {
		j := strings.Index(s, ">")
		if j < i || strings.TrimSpace(s[j+1:]) != "" {
			return ""
		}
		addr = s[i+1 : j]
	}
	addr = strings.ToLower(strings.TrimSpace(addr))
	if addr == "" || len(addr) > mailAddrMax || !mailAddrRE.MatchString(addr) {
		return ""
	}
	return addr
}

// cutRunes keeps the first n characters (Python str slicing counts code points).
func cutRunes(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		return string(r[:n])
	}
	return s
}

// pragueDate is the local civil date of now in Europe/Prague.
func pragueDate(now time.Time) (string, error) {
	loc, err := time.LoadLocation(pragueZone)
	if err != nil {
		return "", errNotifyZone
	}
	return now.In(loc).Format("2006-01-02"), nil
}

// pushEnabled is push.py enabled(): UBYHOST_WEB_PUSH is on unless it is 0, false
// or no after trim and lower case. Unset (Python default "1") is on.
func pushEnabled(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_WEB_PUSH"))) {
	case "0", "false", "no":
		return false
	}
	return true
}

// mailPayload is json.dumps({"text", "html", "lang"}) with ensure_ascii=True,
// in that key order, with the default separators.
func mailPayload(text, html string) string {
	var b strings.Builder
	b.WriteString(`{"text": `)
	writePyString(&b, text)
	b.WriteString(`, "html": `)
	writePyString(&b, html)
	b.WriteString(`, "lang": "en"}`)
	return b.String()
}

// StaysForSubmission is mail_notify.stays_for_submission: the stays whose guests
// were in one batch, read from submission.guest_ids (the batch frozen at send
// time). Grouped and ordered as Python does.
func StaysForSubmission(ctx context.Context, pool *pgxpool.Pool, submissionID int64) ([]mail.Stay, error) {
	if submissionID == 0 {
		return nil, nil
	}
	var raw *string
	err := pool.QueryRow(ctx, `SELECT guest_ids FROM submission WHERE id = $1`, submissionID).Scan(&raw)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, errNotifyStays
	}
	var guestIDs []int64
	if raw == nil || json.Unmarshal([]byte(*raw), &guestIDs) != nil || len(guestIDs) == 0 {
		return nil, nil
	}
	marks := make([]string, len(guestIDs))
	args := make([]any, len(guestIDs))
	for i, id := range guestIDs {
		marks[i] = fmt.Sprintf("$%d", i+1)
		args[i] = id
	}
	query := "SELECT r.id, r.date_from, r.date_to, r.summary, " +
		"       a.id AS apartment_id, a.internal_name AS property_name " +
		"FROM guest g " +
		"JOIN reservation r ON r.id = g.reservation_id " +
		"JOIN apartment a ON a.id = r.apartment_id " +
		"WHERE g.id IN (" + strings.Join(marks, ", ") + ") " +
		"GROUP BY r.id, a.id, a.internal_name " +
		"ORDER BY r.date_from, r.id"
	rows, err := pool.Query(ctx, query, args...)
	if err != nil {
		return nil, errNotifyStays
	}
	defer rows.Close()
	var stays []mail.Stay
	for rows.Next() {
		var s mail.Stay
		var summary, property *string
		var apartmentID int64
		if err := rows.Scan(&s.ID, &s.DateFrom, &s.DateTo, &summary, &apartmentID, &property); err != nil {
			return nil, errNotifyStays
		}
		if summary != nil {
			s.Summary = *summary
		}
		if property != nil {
			s.PropertyName = *property
		}
		stays = append(stays, s)
	}
	if rows.Err() != nil {
		return nil, errNotifyStays
	}
	return stays, nil
}

// QueueSubmissionProblemMail is mail_notify.submission_problem for the e-mail
// part. It returns the email_outbox id, or 0 when nothing is queued (mail off,
// no contact address). Idempotency key: submission_problem:<apartment>:<state>:
// <local Prague date>; an existing row with that key is returned, not duplicated.
// The mail language is always "en" (HOST_MAIL_LANGUAGE in Python).
func QueueSubmissionProblemMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	appBaseURL, publicBaseURL string, apt ApartmentRef, submissionID int64,
	state, reason string, transport bool, now time.Time) (int64, error) {
	// mail.py mail_enabled: UBYHOST_MAIL_BACKEND is console or ses.
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	if backend != "console" && backend != "ses" {
		return 0, nil
	}
	if apt.LegalEntityID == nil || *apt.LegalEntityID == 0 {
		return 0, nil
	}
	var contact *string
	err := pool.QueryRow(ctx, `SELECT contact_email FROM legal_entity WHERE id = $1`, *apt.LegalEntityID).Scan(&contact)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, errNotifyMail
	}
	raw := ""
	if contact != nil {
		raw = *contact
	}
	to := normaliseEmail(raw)
	if to == "" {
		return 0, nil
	}
	stays, err := StaysForSubmission(ctx, pool, submissionID)
	if err != nil {
		return 0, err
	}
	content, err := mail.BuildSubmissionProblem(appBaseURL, publicBaseURL, "en", apt.InternalName,
		state, reason, transport, stays, submissionID)
	if err != nil {
		return 0, errNotifyBuild
	}
	date, err := pragueDate(now)
	if err != nil {
		return 0, err
	}
	key := fmt.Sprintf("submission_problem:%d:%s:%s", apt.ID, state, date)
	var reservationID *int64
	if len(stays) == 1 {
		id := stays[0].ID
		reservationID = &id
	}
	return EnqueueMail(ctx, pool, OutboxMail{
		Kind: "submission_problem", Key: key, ReservationID: reservationID,
		ApartmentID: &apt.ID, OwnerUserID: apt.OwnerUserID, To: to,
		Subject: content.Subject, Text: content.Text, HTML: content.HTML,
	})
}

// QueueFilingProblemPush is push.filing_problem: one alert per device of the
// owner, per property and local day. It returns how many push_outbox rows were
// inserted (0 when push is off, there is no owner, or all already exist).
// Key: filing_problem:<apartment>:<local date>:<subscription id>. The URL is the
// reservation for exactly one stay, else /reservations.
func QueueFilingProblemPush(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	apt ApartmentRef, submissionID int64, now time.Time) (int, error) {
	if !pushEnabled(getenv) || apt.OwnerUserID == nil || *apt.OwnerUserID == 0 {
		return 0, nil
	}
	owner := *apt.OwnerUserID
	stays, err := StaysForSubmission(ctx, pool, submissionID)
	if err != nil {
		return 0, err
	}
	date, err := pragueDate(now)
	if err != nil {
		return 0, err
	}
	key := fmt.Sprintf("%d:%s", apt.ID, date)
	url := "/reservations"
	if len(stays) == 1 {
		url = fmt.Sprintf("/reservations/%d", stays[0].ID)
	}
	return QueuePush(ctx, pool, getenv, owner, "filing_problem", key, url,
		AlertParams{"property": cutRunes(apt.InternalName, pushParamMax)})
}

// OutboxMail is one email_outbox row to queue. A nil ReservationID is NULL.
// To must already be normalised; Text and HTML are the bodies, Subject is cut
// to 200 runes by EnqueueMail.
type OutboxMail struct {
	Kind          string
	Key           string
	ReservationID *int64
	ApartmentID   *int64
	OwnerUserID   *int64
	To            string
	Subject       string
	Text          string
	HTML          string
	// Payload, when set, is the encoded payload column and replaces Text and HTML.
	Payload string
}

// EnqueueMail is mail.enqueue for one row. An existing idempotency key returns
// its id; a unique-violation race returns the winner's id. Errors carry no
// address, text or key.
func EnqueueMail(ctx context.Context, pool *pgxpool.Pool, m OutboxMail) (int64, error) {
	var existing int64
	err := pool.QueryRow(ctx, `SELECT id FROM email_outbox WHERE idempotency_key = $1`, m.Key).Scan(&existing)
	if err == nil {
		return existing, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return 0, errNotifyMail
	}
	ts := UTCNow()
	var id int64
	err = pool.QueryRow(ctx,
		`INSERT INTO email_outbox (idempotency_key, kind, reservation_id, apartment_id, owner_user_id,
		   to_email, cc_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, NULL, $7, $8, 'queued', 0, $9, $9, $9)
		 RETURNING id`,
		m.Key, m.Kind, m.ReservationID, m.ApartmentID, m.OwnerUserID, m.To,
		cutRunes(m.Subject, mailSubjectMax), m.payloadJSON(), ts,
	).Scan(&id)
	if err == nil {
		return id, nil
	}
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23505" {
		// Lost a race with another worker: the row exists, return its id.
		if err := pool.QueryRow(ctx, `SELECT id FROM email_outbox WHERE idempotency_key = $1`, m.Key).Scan(&id); err != nil {
			return 0, errNotifyMail
		}
		return id, nil
	}
	return 0, errNotifyMail
}

// QueuePush is push.notify: one push_outbox row per device of ownerUserID, key
// <kind>:<key>:<subscription id>, so the same event never reaches a device twice.
// The caller cuts the param values. It returns how many rows were inserted (0
// when push is off or there is no owner). Params are written with sorted keys
// (pyJSONParams); see the report for the difference from Python's key order.
func QueuePush(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	ownerUserID int64, kind, key, url string, params AlertParams) (int, error) {
	if !pushEnabled(getenv) || ownerUserID == 0 {
		return 0, nil
	}
	stored, err := pyJSONParams(params)
	if err != nil || stored == nil {
		return 0, errNotifyPush
	}
	rows, err := pool.Query(ctx, `SELECT id FROM push_subscription WHERE user_account_id = $1`, ownerUserID)
	if err != nil {
		return 0, errNotifyPush
	}
	var devices []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return 0, errNotifyPush
		}
		devices = append(devices, id)
	}
	rows.Close()
	if rows.Err() != nil {
		return 0, errNotifyPush
	}
	ts := UTCNow()
	queued := 0
	for _, device := range devices {
		tag, err := pool.Exec(ctx,
			`INSERT INTO push_outbox (idempotency_key, subscription_id, user_account_id, kind, params, url,
			   state, attempts, next_attempt_at, created_at)
			 VALUES ($1, $2, $3, $4, $5, $6, 'queued', 0, $7, $7)
			 ON CONFLICT(idempotency_key) DO NOTHING`,
			fmt.Sprintf("%s:%s:%d", kind, key, device), device, ownerUserID, kind, *stored, url, ts)
		if err != nil {
			return queued, errNotifyPush
		}
		queued += int(tag.RowsAffected())
	}
	return queued, nil
}

// payloadJSON is the payload column: Payload when set, else the text and html form.
func (m OutboxMail) payloadJSON() string {
	if m.Payload != "" {
		return m.Payload
	}
	return mailPayload(m.Text, m.HTML)
}

// PyString is writePyString for callers outside this package: a Python str as
// json.dumps writes it (ensure_ascii, double quotes).
func PyString(s string) string {
	var b strings.Builder
	writePyString(&b, s)
	return b.String()
}

// NormaliseEmail is mail.normalise_email for callers outside this package.
func NormaliseEmail(raw string) string { return normaliseEmail(raw) }
