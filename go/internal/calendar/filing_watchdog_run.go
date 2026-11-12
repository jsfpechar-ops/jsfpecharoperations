// filing_watchdog_run.go is the acting half of App/app/filing_watchdog.py
// (WP23): notify_hosts (push.deadline_at_risk and the deadline_at_risk host
// mail), send_operator_digest and run. The selection half is filing_watchdog.go
// (brief 1159). Nothing calls this yet: brief 1132 §10 E adds the job kind and
// the Python/Go switch. testdata/filing_watchdog_run_golden.json, written by
// App/scripts/filing_watchdog_run_golden.py, is the parity check.
package calendar

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const (
	// watchdogDigestInterval is DIGEST_INTERVAL.
	watchdogDigestInterval = 72 * time.Hour
	// watchdogDigestSetting is DIGEST_SETTING.
	watchdogDigestSetting = "filing_watchdog_digest_sent_at"
	// watchdogOperatorDefault is config.OPERATOR_EMAIL when the variable is empty.
	watchdogOperatorDefault = "support@ubyhost.com"
	// watchdogPushParamMax is push._PARAM_MAX.
	watchdogPushParamMax = 120
)

// errWatchdogNaiveStamp is Python's TypeError on an offset-less digest stamp.
var errWatchdogNaiveStamp = errors.New("filing watchdog: digest stamp has no UTC offset")

// WatchdogResult is the dict run() returns.
type WatchdogResult struct {
	AtRisk        int
	UnknownRisk   int
	AwaitingRetry int
	HostMails     int
	Digest        int
}

// watchdogMailEnabled is mail.mail_enabled: UBYHOST_MAIL_BACKEND console or ses.
func watchdogMailEnabled(getenv func(string) string) bool {
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	return backend == "console" || backend == "ses"
}

// watchdogBases is (config.PUBLIC_BASE_URL, config.app_base_url()), without a
// trailing slash, as cancelled_notify.go reads them.
func watchdogBases(getenv func(string) string) (string, string) {
	public := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_PUBLIC_BASE_URL")), "/")
	app := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/")
	if app == "" {
		app = public
	}
	return public, app
}

// watchdogStamp is _utc(now).replace(microsecond=0).isoformat().
func watchdogStamp(at time.Time) string {
	return at.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

// watchdogDeadlineText is mail_notify._deadline_text: "DD.MM.YYYY HH:MM".
func watchdogDeadlineText(deadline time.Time) string {
	return deadline.Format("02.01.2006 15:04")
}

// watchdogAddrSpec is a plain addr-spec: a dot-atom local part and a dotted
// domain of letters, digits and hyphens.
const watchdogAddrSpec = `[A-Za-z0-9!#$%&'*+/=?^_{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_{|}~-]+)*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+`

var (
	watchdogAddrPlain = regexp.MustCompile(`^(` + watchdogAddrSpec + `)$`)
	watchdogAddrAngle = regexp.MustCompile(`^[^"()<>\[\]:;@\\,.\t\r\n]*<(` + watchdogAddrSpec + `)>$`)
)

// watchdogAddress is mail.normalise_email for the forms it can read: a plain
// address, or "<address>" after a display name with no special characters.
// For those it gives exactly what Python gives (lower case, at most 254
// characters). Python's parseaddr is a full RFC 2822 parser whose results for
// other forms (comments, quotes, groups, "mailto:") differ between Python
// releases, so it is not ported; any other value that is not blank returns ""
// with unreadable true: the caller logs it at error level and the stay stays
// unmailed (no stamp), so it is never skipped silently and is retried each run.
func watchdogAddress(raw string) (addr string, unreadable bool) {
	s := strings.TrimSpace(raw)
	if s == "" {
		return "", false
	}
	m := watchdogAddrPlain.FindStringSubmatch(s)
	if m == nil {
		m = watchdogAddrAngle.FindStringSubmatch(s)
	}
	if m == nil || len(m[1]) > 254 {
		return "", true
	}
	return strings.ToLower(m[1]), false
}

// watchdogContactEmail is mail_notify._entity_contact_email: the legal
// entity's contact address, normalised, or "" (see watchdogAddress).
func watchdogContactEmail(ctx context.Context, pool *pgxpool.Pool, entity *int64) (string, bool, error) {
	if entity == nil || *entity == 0 {
		return "", false, nil
	}
	var contact *string
	err := pool.QueryRow(ctx, `SELECT contact_email FROM legal_entity WHERE id = $1`, *entity).Scan(&contact)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", false, nil
	}
	if err != nil {
		return "", false, err
	}
	if contact == nil {
		return "", false, nil
	}
	addr, unreadable := watchdogAddress(*contact)
	return addr, unreadable, nil
}

// watchdogPush is push.deadline_at_risk: one push per device of the owner,
// key deadline_at_risk:<reservation>:<device>. Python never raises here; the
// error is returned for the caller to log.
func watchdogPush(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, stay WatchdogStay) error {
	if stay.OwnerUserID == nil || *stay.OwnerUserID == 0 {
		return nil
	}
	id := fmt.Sprintf("%d", stay.ReservationID)
	params := ubyport.AlertParams{
		"property": watchdogCut(stay.Property),
		"date":     watchdogCut(stay.Arrival.Format("02.01.2006")),
		"deadline": watchdogCut(watchdogDeadlineText(stay.Deadline)),
	}
	_, err := ubyport.QueuePush(ctx, pool, getenv, *stay.OwnerUserID, "deadline_at_risk", id,
		"/reservations/"+id, params)
	return err
}

// watchdogCut is push._clean_params: a value cut to 120 characters.
func watchdogCut(s string) string {
	r := []rune(s)
	if len(r) > watchdogPushParamMax {
		return string(r[:watchdogPushParamMax])
	}
	return s
}

// watchdogMailStay queues the host mail for one stay and stamps
// at_risk_mailed_at. It reports whether a mail was queued.
func watchdogMailStay(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, stay *WatchdogStay, at time.Time) (bool, error) {
	to, unreadable, err := watchdogContactEmail(ctx, pool, stay.LegalEntityID)
	if err != nil {
		return false, err
	}
	if unreadable {
		slog.Error("deadline_at_risk host not mailed: contact address unreadable", "reservation_id", stay.ReservationID)
	}
	if to == "" {
		return false, nil
	}
	public, app := watchdogBases(getenv)
	stayURL := fmt.Sprintf("%s/reservations/%d", app, stay.ReservationID)
	content, err := mail.BuildDeadlineAtRisk(public, "en", stay.Property, stay.Arrival.Format("02.01.2006"),
		watchdogDeadlineText(stay.Deadline), stay.Unfiled, stayURL, stay.NoGuests)
	if err != nil {
		return false, err
	}
	if !watchdogMailEnabled(getenv) {
		// Mail is switched off: try again on the next run rather than marking
		// a warning nobody got.
		return false, nil
	}
	reservation, apartment := stay.ReservationID, stay.ApartmentID
	outboxID, err := ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:          "deadline_at_risk",
		Key:           fmt.Sprintf("deadline_at_risk:%d", stay.ReservationID),
		ReservationID: &reservation,
		ApartmentID:   &apartment,
		OwnerUserID:   stay.OwnerUserID,
		To:            to,
		Subject:       content.Subject,
		Text:          content.Text,
		HTML:          content.HTML,
	})
	if err != nil {
		return false, err
	}
	if outboxID == 0 {
		return false, nil
	}
	stamp := watchdogStamp(at)
	if _, err := pool.Exec(ctx,
		`UPDATE reservation SET at_risk_mailed_at = $1 WHERE id = $2 AND at_risk_mailed_at IS NULL`,
		stamp, stay.ReservationID); err != nil {
		return false, err
	}
	stay.MailedAt = &stamp
	return true, nil
}

// NotifyHosts is notify_hosts: the push and the host mail for each stay not
// warned yet, once per stay whichever variant comes first. It returns how many
// mails were queued. A failure on one stay is logged and the next stay goes
// on, as in Python. The push is queued even when there is no address to mail.
func NotifyHosts(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, stays []WatchdogStay, at time.Time) int {
	queued := 0
	for i := range stays {
		stay := &stays[i]
		if stay.MailedAt != nil && *stay.MailedAt != "" {
			continue
		}
		if err := watchdogPush(ctx, pool, getenv, *stay); err != nil {
			slog.Error("push_deadline_failed", "reservation_id", stay.ReservationID)
		}
		ok, err := watchdogMailStay(ctx, pool, getenv, stay, at)
		if err != nil {
			slog.Error("deadline_at_risk mail failed", "reservation_id", stay.ReservationID)
			continue
		}
		if ok {
			queued++
		}
	}
	return queued
}

// watchdogDigestRows is the digest's view of the stays: no guest names.
func watchdogDigestRows(stays []WatchdogStay) []mail.DigestRow {
	rows := make([]mail.DigestRow, 0, len(stays))
	for _, s := range stays {
		rows = append(rows, mail.DigestRow{
			Workspace: s.Workspace,
			Property:  s.Property,
			Arrival:   s.Arrival.Format("02.01.2006"),
			Deadline:  watchdogDeadlineText(s.Deadline),
			Unfiled:   s.Unfiled,
		})
	}
	return rows
}

// watchdogLastDigest reads the digest stamp: ok false when it is missing or
// unreadable (Python's None: the digest may go out). A stamp without an
// offset is Python's TypeError and returns errWatchdogNaiveStamp.
func watchdogLastDigest(raw string) (time.Time, bool, error) {
	for _, layout := range []string{time.RFC3339Nano, "2006-01-02 15:04:05.999999999Z07:00"} {
		if t, err := time.Parse(layout, raw); err == nil {
			return t, true, nil
		}
	}
	for _, layout := range []string{"2006-01-02T15:04:05.999999999", "2006-01-02 15:04:05.999999999", "2006-01-02"} {
		if _, err := time.Parse(layout, raw); err == nil {
			return time.Time{}, false, errWatchdogNaiveStamp
		}
	}
	return time.Time{}, false, nil
}

// SendOperatorDigest is send_operator_digest: the operator digest, unless one
// went out in the last 72 hours. A stamp in the future (a clock set back)
// does not block it. It reports whether a digest was queued.
func SendOperatorDigest(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, stays, unknown []WatchdogStay, at time.Time) (bool, error) {
	if len(stays) == 0 && len(unknown) == 0 {
		return false, nil
	}
	operator := strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL"))
	if operator == "" {
		operator = watchdogOperatorDefault
	}
	to, unreadable := watchdogAddress(operator)
	if unreadable {
		slog.Error("deadline digest not sent: UBYHOST_OPERATOR_EMAIL unreadable")
	}
	if to == "" {
		return false, nil
	}
	current := at.UTC().Truncate(time.Second)
	var lastRaw *string
	err := pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, watchdogDigestSetting).Scan(&lastRaw)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return false, err
	}
	if lastRaw != nil && *lastRaw != "" {
		last, ok, err := watchdogLastDigest(*lastRaw)
		if err != nil {
			return false, err
		}
		if ok {
			age := current.Sub(last)
			if age >= 0 && age < watchdogDigestInterval {
				return false, nil
			}
		}
	}
	public, _ := watchdogBases(getenv)
	content, err := mail.BuildDeadlineDigest(public, "en", watchdogDigestRows(stays), watchdogDigestRows(unknown))
	if err != nil {
		return false, err
	}
	if !watchdogMailEnabled(getenv) {
		return false, nil
	}
	stamp := watchdogStamp(current)
	outboxID, err := ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:    "deadline_digest",
		Key:     "deadline_digest:" + stamp,
		To:      to,
		Subject: content.Subject,
		Text:    content.Text,
		HTML:    content.HTML,
	})
	if err != nil {
		return false, err
	}
	if outboxID == 0 {
		return false, nil
	}
	if _, err := pool.Exec(ctx,
		`INSERT INTO settings (key, value) VALUES ($1, $2)
		ON CONFLICT(key) DO UPDATE SET value = excluded.value`,
		watchdogDigestSetting, stamp); err != nil {
		return false, err
	}
	return true, nil
}

// RunFilingWatchdog is filing_watchdog.run: one watchdog pass. It fails only
// when the at-risk query fails. AtRisk counts only stays with known reportable
// guests and alone decides the heartbeat (FilingHeartbeatURL); UnknownRisk and
// AwaitingRetry do not. The unknown-risk query and the digest are isolated: a
// failure is logged and the pass goes on, so neither silences the real check.
// lookupEnv is os.LookupEnv in production; an unreadable
// UBYHOST_SUBMIT_SWEEP_MINUTES fails the pass, as Python refuses to start.
func RunFilingWatchdog(ctx context.Context, pool *pgxpool.Pool, lookupEnv func(string) (string, bool), at time.Time) (WatchdogResult, error) {
	getenv := func(name string) string {
		v, _ := lookupEnv(name)
		return v
	}
	every, err := AtRiskStays(ctx, pool, lookupEnv, at, true)
	if err != nil {
		return WatchdogResult{}, err
	}
	var stays []WatchdogStay
	for _, s := range every {
		if !s.AwaitingRetry {
			stays = append(stays, s)
		}
	}
	unknown, err := UnknownRiskStays(ctx, pool, at)
	if err != nil {
		// The weaker check must not silence the real one or its heartbeat.
		slog.Error("unknown-risk query failed")
		unknown = nil
	}
	both := make([]WatchdogStay, 0, len(stays)+len(unknown))
	both = append(both, stays...)
	both = append(both, unknown...)
	hostMails := NotifyHosts(ctx, pool, getenv, both, at)
	digest, err := SendOperatorDigest(ctx, pool, getenv, stays, unknown, at)
	if err != nil {
		slog.Error("deadline digest failed")
		digest = false
	}
	result := WatchdogResult{
		AtRisk:        len(stays),
		UnknownRisk:   len(unknown),
		AwaitingRetry: len(every) - len(stays),
		HostMails:     hostMails,
	}
	if digest {
		result.Digest = 1
	}
	return result, nil
}
