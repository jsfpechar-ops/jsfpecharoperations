package mail

// Brief 1704b: mail.recent_console_messages for Settings > Technical, the
// console backend's log that a host reads on staging. Read only.

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// ConsoleMessage is one console_mail_log row with its claim secret put back.
type ConsoleMessage struct {
	ToEmail, Subject, BodyText, BodyHTML string
}

// RecentConsole is mail.recent_console_messages(owner, limit) for one owner:
// the newest rows whose outbox row belongs to that owner. The stored body
// keeps the claim secret out; it is put back here, best effort as in Python
// (a key or payload that cannot be read leaves the marker standing).
func RecentConsole(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, owner int64, limit int) ([]ConsoleMessage, error) {
	rows, err := pool.Query(ctx, `SELECT COALESCE(l.to_email, ''), COALESCE(l.subject, ''),
		COALESCE(l.body_text, ''), COALESCE(l.body_html, ''), COALESCE(o.payload, '')
		FROM console_mail_log l JOIN email_outbox o ON o.id = l.outbox_id
		WHERE o.owner_user_id IS NOT DISTINCT FROM $1 ORDER BY l.id DESC LIMIT $2`, owner, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var cfg Config
	if keys, kerr := secure.LoadDataKeys(getenv); kerr == nil {
		cfg.Keys = keys
	}
	var out []ConsoleMessage
	for rows.Next() {
		var m ConsoleMessage
		var payload string
		if err := rows.Scan(&m.ToEmail, &m.Subject, &m.BodyText, &m.BodyHTML, &payload); err != nil {
			return nil, err
		}
		m.BodyText = revealClaimSecret(cfg, m.BodyText, payload)
		m.BodyHTML = revealClaimSecret(cfg, m.BodyHTML, payload)
		out = append(out, m)
	}
	return out, rows.Err()
}

// revealClaimSecret is mail._reveal_claim_secret.
func revealClaimSecret(c Config, body, payloadJSON string) string {
	if !strings.Contains(body, ClaimSecretMarker) {
		return body
	}
	if payloadJSON == "" {
		payloadJSON = "{}"
	}
	var payload map[string]any
	if err := json.Unmarshal([]byte(payloadJSON), &payload); err != nil {
		return body
	}
	token, _ := payload[claimSecretKey].(string)
	if token == "" {
		return body
	}
	secret, err := c.decrypt(token)
	if err != nil {
		return body
	}
	return strings.ReplaceAll(body, ClaimSecretMarker, secret)
}
