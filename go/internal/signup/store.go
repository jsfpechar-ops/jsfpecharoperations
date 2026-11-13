package signup

import (
	"context"
	"errors"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// execer is what a pool and a transaction share.
type execer interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

func isUnique(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}

// insertRow is db.insert: one row, the new id back.
func insertRow(ctx context.Context, q execer, table string, cols []string, vals []any) (int64, error) {
	marks := make([]string, len(cols))
	for i := range cols {
		marks[i] = "$" + strconv.Itoa(i+1)
	}
	var id int64
	err := q.QueryRow(ctx, "INSERT INTO "+table+" ("+strings.Join(cols, ", ")+") VALUES ("+
		strings.Join(marks, ", ")+") RETURNING id", vals...).Scan(&id)
	return id, err
}

// updateRow is db.update: SET the columns WHERE id.
func updateRow(ctx context.Context, q execer, table string, id int64, cols []string, vals []any) error {
	sets := make([]string, len(cols))
	for i, c := range cols {
		sets[i] = c + " = $" + strconv.Itoa(i+1)
	}
	_, err := q.Exec(ctx, "UPDATE "+table+" SET "+strings.Join(sets, ", ")+" WHERE id = $"+
		strconv.Itoa(len(cols)+1), append(vals, id)...)
	return err
}

type actorKey struct{}

type auditActor struct {
	userID       int64
	username     string
	impersonator *int64
}

// WithAuditActor is db.set_current_actor for the audit rows this package
// writes under ctx: the signed-in account, and with impersonating its own id
// as impersonator. An admin route calls it before ResendOperator, as
// Python's require_login does.
func WithAuditActor(ctx context.Context, userID int64, username string, impersonating bool) context.Context {
	a := auditActor{userID: userID, username: username}
	if impersonating {
		id := userID
		a.impersonator = &id
	}
	return context.WithValue(ctx, actorKey{}, a)
}

// audit is db.audit: an actor of "host" becomes the signed-in username.
func audit(ctx context.Context, q execer, at, action, detail, actor string, owner *int64) error {
	var actorID, impersonator *int64
	if a, ok := ctx.Value(actorKey{}).(auditActor); ok {
		id := a.userID
		actorID, impersonator = &id, a.impersonator
		if actor == "host" {
			actor = a.username
		}
	}
	_, err := q.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id`, at, actor, action, detail, owner, actorID, impersonator)
	return err
}

var emailRE = regexp.MustCompile(`^[^@\s]+@[^@\s]+\.[^@\s]+$`)

// normaliseEmail is mail.normalise_email for a bare address (the only form
// stored on an account): trimmed, lower-cased, checked, at most 254 chars.
func normaliseEmail(raw string) string {
	addr := strings.ToLower(pyStrip(raw))
	if addr == "" || !emailRE.MatchString(addr) || utf8.RuneCountInString(addr) > 254 {
		return ""
	}
	return addr
}

// mailEnabled is mail.mail_enabled: UBYHOST_MAIL_BACKEND is console or ses.
func mailEnabled(getenv func(string) string) bool {
	b := strings.ToLower(strings.TrimSpace(envOr(getenv, "UBYHOST_MAIL_BACKEND", "disabled")))
	return b == "console" || b == "ses"
}

// pyDumps is json.dumps of a dict of strings, in the given key order, with
// Python's defaults: ", " and ": " separators and ensure_ascii.
func pyDumps(pairs [][2]string) string {
	parts := make([]string, len(pairs))
	for i, p := range pairs {
		parts[i] = asciiString(p[0]) + ": " + asciiString(p[1])
	}
	return "{" + strings.Join(parts, ", ") + "}"
}

// asciiString is a JSON string with ensure_ascii=True.
func asciiString(s string) string {
	const hex = "0123456789abcdef"
	u := func(b *strings.Builder, r rune) {
		b.WriteString(`\u`)
		for shift := 12; shift >= 0; shift -= 4 {
			b.WriteByte(hex[(r>>uint(shift))&0xf])
		}
	}
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch {
		case r == '"':
			b.WriteString(`\"`)
		case r == '\\':
			b.WriteString(`\\`)
		case r == '\n':
			b.WriteString(`\n`)
		case r == '\r':
			b.WriteString(`\r`)
		case r == '\t':
			b.WriteString(`\t`)
		case r == '\b':
			b.WriteString(`\b`)
		case r == '\f':
			b.WriteString(`\f`)
		case r < 0x20 || (r >= 0x7f && r < 0x10000):
			u(&b, r)
		case r >= 0x10000:
			r -= 0x10000
			u(&b, 0xd800+(r>>10))
			u(&b, 0xdc00+(r&0x3ff))
		default:
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
	return b.String()
}

// outboxMail is one mail.enqueue call.
type outboxMail struct {
	kind, key, to, subject string
	text, html, lang       string
	claimSecret            string // "" means no claim_secret_enc
	owner                  *int64
}

// enqueue is mail.enqueue for the sign-up kinds: nothing while mail is off or
// the address is not valid; an existing idempotency key is left alone; an
// insert error is swallowed, as Python logs it and returns the existing id.
func enqueue(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, m outboxMail, at string) error {
	pairs := [][2]string{{"text", m.text}, {"html", m.html}, {"lang", m.lang}}
	if m.claimSecret != "" {
		// Python encrypts in mail_notify, before enqueue looks at anything.
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			return err
		}
		enc, err := keys.EncryptString(m.claimSecret)
		if err != nil {
			return err
		}
		pairs = append(pairs, [2]string{"claim_secret_enc", enc})
	}
	if !mailEnabled(getenv) {
		return nil
	}
	to := normaliseEmail(m.to)
	if to == "" {
		return nil
	}
	var existing int64
	err := pool.QueryRow(ctx, `SELECT id FROM email_outbox WHERE idempotency_key = $1`, m.key).Scan(&existing)
	if err == nil {
		return nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	subject := m.subject
	if utf8.RuneCountInString(subject) > 200 {
		subject = string([]rune(subject)[:200])
	}
	_, _ = pool.Exec(ctx, `INSERT INTO email_outbox (idempotency_key, kind, reservation_id, apartment_id, owner_user_id,
		to_email, cc_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at)
		VALUES ($1, $2, NULL, NULL, $3, $4, NULL, $5, $6, 'queued', 0, $7, $7, $7)`,
		m.key, m.kind, m.owner, to, subject, pyDumps(pairs), at)
	return nil
}
