package mail

// mail.drain, _deliver, _send_console, _log_staging_link and purge_old.

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
)

// Summary counts what one Drain did.
type Summary struct{ Sent, Failed, Skipped int }

const (
	obMaxAttempts = 8
	obStaleAfter  = 10 * time.Minute
)

// ObBackoff is the delay after a failed attempt: min(6 h, 60 s * 2^min(n, 8)).
func ObBackoff(attempts int) time.Duration {
	n := attempts
	if n > 8 {
		n = 8
	}
	d := 60 * (1 << n)
	if d > 6*60*60 {
		d = 6 * 60 * 60
	}
	return time.Duration(d) * time.Second
}

// Drain sends up to limit queued rows: stale "sending" rows go back to queued,
// each due row is claimed with a compare-and-set and delivered.
func Drain(ctx context.Context, pool *pgxpool.Pool, cfg Config, limit int) (Summary, error) {
	var sum Summary
	if !cfg.Enabled() {
		return sum, nil
	}
	now := cfg.now()
	stale := obStamp(now.Add(-obStaleAfter))
	if _, err := pool.Exec(ctx,
		`UPDATE email_outbox SET state = 'queued' WHERE state = 'sending' AND updated_at < $1`, stale); err != nil {
		return sum, errors.New("mail drain: stale rows not reset")
	}
	rows, err := pool.Query(ctx,
		`SELECT `+obRowColumns+` FROM email_outbox WHERE state = 'queued' AND next_attempt_at <= $1 ORDER BY id LIMIT $2`,
		obStamp(now), limit)
	if err != nil {
		return sum, errors.New("mail drain: queue not read")
	}
	var due []obRow
	for rows.Next() {
		var r obRow
		if err := rows.Scan(r.dest()...); err != nil {
			rows.Close()
			return sum, errors.New("mail drain: queue row not read")
		}
		due = append(due, r)
	}
	rows.Close()
	if rows.Err() != nil {
		return sum, errors.New("mail drain: queue not read")
	}
	for _, r := range due {
		claimed, err := cfg.claim(ctx, pool, r.ID)
		if err != nil {
			return sum, err
		}
		if !claimed {
			continue // another drain took it
		}
		outcome, err := cfg.deliver(ctx, pool, r)
		if err != nil {
			return sum, err
		}
		switch outcome {
		case "sent":
			sum.Sent++
		case "failed":
			sum.Failed++
		default:
			sum.Skipped++
		}
	}
	return sum, nil
}

// claim is db.update_if(email_outbox, id, {state: sending}, {state: queued}).
func (c Config) claim(ctx context.Context, pool *pgxpool.Pool, id int64) (bool, error) {
	tag, err := pool.Exec(ctx,
		`UPDATE email_outbox SET state = 'sending', updated_at = $1 WHERE id = $2 AND state = 'queued'`,
		obStamp(c.now()), id)
	if err != nil {
		return false, errors.New("mail: outbox row not claimed")
	}
	return tag.RowsAffected() == 1, nil
}

// SendNow is mail.send_now: send one queued row straight away (a login link
// the reader waits for). An id <= 0, mail switched off, a missing row or a row
// that is not queued is not an error. A failed delivery is not an error either:
// the row stays queued with the usual back-off and Drain retries it. The error
// is only for an invalid mail environment or database trouble.
func SendNow(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, outboxID int64) error {
	if outboxID <= 0 {
		return nil
	}
	cfg, err := ConfigFromEnv(getenv)
	if err != nil {
		return err
	}
	return cfg.sendNow(ctx, pool, outboxID)
}

func (c Config) sendNow(ctx context.Context, pool *pgxpool.Pool, outboxID int64) error {
	if outboxID <= 0 || !c.Enabled() {
		return nil
	}
	var r obRow
	var state string
	err := pool.QueryRow(ctx, `SELECT `+obRowColumns+`, COALESCE(state, '') FROM email_outbox WHERE id = $1`, outboxID).
		Scan(append(r.dest(), &state)...)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		return errors.New("mail send_now: row not read")
	}
	if state != "queued" {
		return nil
	}
	claimed, err := c.claim(ctx, pool, r.ID)
	if err != nil || !claimed {
		return err
	}
	_, err = c.deliver(ctx, pool, r)
	return err
}

// deliver sends one row already marked sending. It returns sent, failed or
// skipped; the error is only for database trouble or a cancelled context.
func (c Config) deliver(ctx context.Context, pool *pgxpool.Pool, r obRow) (string, error) {
	providerID, sendErr := c.send(ctx, pool, r)
	if sendErr == nil {
		stamp := obStamp(c.now())
		_, err := pool.Exec(ctx,
			`UPDATE email_outbox SET state = 'sent', provider_id = $1, sent_at = $2, updated_at = $2,
			        last_error = NULL, attempts = $3 WHERE id = $4`,
			providerID, stamp, r.Attempts+1, r.ID)
		if err != nil {
			return "", errors.New("mail drain: sent row not saved")
		}
		return "sent", nil
	}
	if ctx.Err() != nil {
		return "", ctx.Err() // the row stays sending and goes back to queued after 10 minutes
	}
	if errors.Is(sendErr, ErrNoDetailsRenderer) {
		// A setup problem, not a failed send: put the row back as it was.
		if _, err := pool.Exec(ctx,
			`UPDATE email_outbox SET state = 'queued', updated_at = $1 WHERE id = $2 AND state = 'sending'`,
			obStamp(c.now()), r.ID); err != nil {
			return "", errors.New("mail drain: row not put back")
		}
		return "", sendErr
	}
	attempts := r.Attempts + 1
	terminal := attempts >= obMaxAttempts
	state := "queued"
	if terminal {
		state = "failed"
	}
	now := c.now()
	next := now.Add(ObBackoff(int(attempts))).Format("2006-01-02T15:04:05") + "Z"
	safe := obSafeError(sendErr)
	if _, err := pool.Exec(ctx,
		`UPDATE email_outbox SET state = $1, attempts = $2, last_error = $3, next_attempt_at = $4, updated_at = $5
		 WHERE id = $6`, state, attempts, safe, next, obStamp(now), r.ID); err != nil {
		return "", errors.New("mail drain: failed row not saved")
	}
	if !terminal {
		return "skipped", nil
	}
	masked := MaskEmail(r.To)
	err := obRaiseAlert(ctx, pool, now, "warning", "mail_failed",
		fmt.Sprintf("E-mail could not be sent (%s).", r.Kind),
		fmt.Sprintf("To %s: %s", masked, safe),
		fmt.Sprintf("mail_failed:%d", r.ID), r.ApartmentID, r.ReservationID,
		[][2]string{{"error", safe}, {"kind", r.Kind}, {"to", masked}})
	if err != nil {
		return "", errors.New("mail drain: mail_failed alert not saved")
	}
	return "failed", nil
}

// send builds and delivers one row and returns the provider id.
func (c Config) send(ctx context.Context, pool *pgxpool.Pool, r obRow) (string, error) {
	p, err := obParsePayload(r.Payload)
	if err != nil {
		return "", err
	}
	if c.Backend == BackendConsole {
		return c.sendConsole(ctx, pool, r, p)
	}
	body, err := c.deliveryBody(ctx, pool, p)
	if err != nil {
		return "", err
	}
	html, err := c.deliveryHTML(ctx, pool, p)
	if err != nil {
		return "", err
	}
	parts, err := c.obAttachments(ctx, pool, p)
	if err != nil {
		return "", err
	}
	id, err := c.obSendSES(ctx, r, p, body, html, parts)
	if err != nil {
		return "", err
	}
	slog.Info("ses mail", "id", r.ID, "kind", r.Kind, "to", MaskEmail(r.To), "message_id", id)
	return id, nil
}

// sendConsole is _send_console: the delivered form is built first (so a missing
// secret fails the row), the log keeps the stored form with an attachment note.
func (c Config) sendConsole(ctx context.Context, pool *pgxpool.Pool, r obRow, p obPayload) (string, error) {
	body, err := c.deliveryBody(ctx, pool, p)
	if err != nil {
		return "", err
	}
	if _, err := c.deliveryHTML(ctx, pool, p); err != nil {
		return "", err
	}
	parts, err := c.obAttachments(ctx, pool, p)
	if err != nil {
		return "", err
	}
	note := ""
	if len(parts) > 0 {
		names := make([]string, len(parts))
		for i, a := range parts {
			names[i] = a.Filename
		}
		note = "\n\n[Attachments: " + strings.Join(names, ", ") + "]"
	}
	var html any
	if h := p.str("html"); h != "" {
		html = h
	}
	var cc any
	if r.CCRaw != nil {
		cc = *r.CCRaw
	}
	if _, err := pool.Exec(ctx,
		`INSERT INTO console_mail_log (outbox_id, to_email, cc_email, subject, body_text, body_html, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		r.ID, r.To, cc, r.Subject, p.str("text")+note, html, obStamp(c.now())); err != nil {
		return "", errors.New("console mail log not written")
	}
	slog.Info("console mail", "id", r.ID, "kind", r.Kind, "to", MaskEmail(r.To), "attachments", len(parts))
	if link := obStagingLink(c.Deployment, r.Kind, body); link != "" {
		slog.Warn("staging login link", "kind", r.Kind, "to", MaskEmail(r.To), "link", link)
	}
	return "console:" + strconv.FormatInt(r.ID, 10), nil
}

var obLinkKinds = map[string]bool{"login_link": true, "account_invite": true, "email_confirm": true, "signup_verify": true}

var obLinkInBody = regexp.MustCompile(`https?://\S+[?&]t=[A-Za-z0-9_.\-]+`)

// obStagingLink is the match _log_staging_link would log; empty when it logs
// nothing. Only staging, only the kinds whose link logs someone in.
func obStagingLink(deployment, kind, body string) string {
	if deployment != "staging" || !obLinkKinds[kind] {
		return ""
	}
	return obLinkInBody.FindString(body)
}

// Purge is mail.purge_old: finished outbox rows and console log entries older
// than days. The cutoff is the Prague wall clock as Python's isoformat writes it.
// It returns the number of outbox rows deleted.
func Purge(ctx context.Context, pool *pgxpool.Pool, now time.Time, days int) (int, error) {
	cutoff := obIsoNaive(deadlines.LocalNow(now).Add(-time.Duration(days) * 24 * time.Hour))
	tag, err := pool.Exec(ctx,
		`DELETE FROM email_outbox WHERE state IN ('sent', 'failed', 'bounced', 'complained') AND updated_at < $1`, cutoff)
	if err != nil {
		return 0, errors.New("mail purge: outbox not purged")
	}
	if _, err := pool.Exec(ctx, `DELETE FROM console_mail_log WHERE created_at < $1`, cutoff); err != nil {
		return int(tag.RowsAffected()), errors.New("mail purge: console log not purged")
	}
	return int(tag.RowsAffected()), nil
}

// obRaiseAlert is alerts.raise_alert for the mail_failed case (ubyport.RaiseAlert
// does the same, but this package cannot import ubyport). params are written as
// json.dumps(sort_keys=True, ensure_ascii=False) does, so they must be sorted.
func obRaiseAlert(ctx context.Context, pool *pgxpool.Pool, now time.Time, level, kind, message, detail, dedupeKey string,
	apartmentID, reservationID *int64, params [][2]string) error {
	var b strings.Builder
	b.WriteByte('{')
	for i, kv := range params {
		if i > 0 {
			b.WriteString(", ")
		}
		obJSONString(&b, kv[0])
		b.WriteString(": ")
		obJSONString(&b, kv[1])
	}
	b.WriteByte('}')
	stored := b.String()

	var owner *int64
	if apartmentID != nil && *apartmentID != 0 {
		err := pool.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, *apartmentID).Scan(&owner)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
	}
	if owner == nil && reservationID != nil && *reservationID != 0 {
		err := pool.QueryRow(ctx,
			`SELECT a.owner_user_id FROM reservation r JOIN apartment a ON a.id = r.apartment_id WHERE r.id = $1`,
			*reservationID).Scan(&owner)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
	}
	stamp := obStamp(now)
	tag, err := pool.Exec(ctx,
		`UPDATE alert SET level = $1, message = $2, detail = $3, params = $4, created_at = $5
		 WHERE dedupe_key = $6 AND resolved_at IS NULL`, level, message, detail, stored, stamp, dedupeKey)
	if err != nil {
		return err
	}
	if tag.RowsAffected() > 0 {
		return nil
	}
	_, err = pool.Exec(ctx,
		`INSERT INTO alert (level, kind, apartment_id, reservation_id, owner_user_id, dedupe_key, message, detail, params, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
		level, kind, apartmentID, reservationID, owner, dedupeKey, message, detail, stored, stamp)
	return err
}

// obJSONString writes s as json.dumps(ensure_ascii=False) does.
func obJSONString(b *strings.Builder, s string) {
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			if r < 0x20 {
				fmt.Fprintf(b, `\u%04x`, r)
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
}
