package mail

// The queue side of the account mails (brief 1501): mail_notify.link_mail,
// email_changed, passkey_added and workspace_deletion, each through
// mail.enqueue into email_outbox. Nothing here sends: the caller hands a
// returned id to SendNow (login links) or leaves the row to Drain. Errors
// and log lines never carry an address, a token or an idempotency key.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"log"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// hostMailLanguage is mail_notify.HOST_MAIL_LANGUAGE.
const hostMailLanguage = "en"

// accountRow is one email_outbox row of an account mail. payload holds the
// payload keys in Python's order; a nil value is JSON null.
type accountRow struct {
	kind, key, to, subject string
	payload                []payloadField
	owner                  int64
}

type payloadField struct {
	key   string
	value *string
}

func strPtr(s string) *string { return &s }

// accountPublicBase is config.PUBLIC_BASE_URL (the logo in the shell).
func accountPublicBase(getenv func(string) string) string {
	base := getenv("UBYHOST_PUBLIC_BASE_URL")
	if base == "" {
		base = "http://127.0.0.1:8080"
	}
	return strings.TrimRight(base, "/")
}

// accountAppBase is config.app_base_url(): UBYHOST_APP_BASE_URL, else the
// public base URL.
func accountAppBase(getenv func(string) string) string {
	if v := strings.TrimRight(strings.TrimSpace(getenv("UBYHOST_APP_BASE_URL")), "/"); v != "" {
		return v
	}
	return accountPublicBase(getenv)
}

// accountOperatorEmail is config.OPERATOR_EMAIL.
func accountOperatorEmail(getenv func(string) string) string {
	if v := strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL")); v != "" {
		return v
	}
	return "support@ubyhost.com"
}

// accountMailEnabled is mail.mail_enabled: UBYHOST_MAIL_BACKEND (default
// disabled), stripped and lower-cased, is console or ses.
func accountMailEnabled(getenv func(string) string) bool {
	b := getenv("UBYHOST_MAIL_BACKEND")
	if b == "" {
		b = BackendDisabled
	}
	b = strings.ToLower(strings.TrimSpace(b))
	return b == BackendConsole || b == BackendSES
}

// accountPayloadJSON is json.dumps(payload): ", " and ": " separators,
// ensure_ascii, keys in the order given.
func accountPayloadJSON(fields []payloadField) string {
	var b strings.Builder
	b.WriteByte('{')
	for i, f := range fields {
		if i > 0 {
			b.WriteString(", ")
		}
		asciiJSON(&b, f.key)
		b.WriteString(": ")
		if f.value == nil {
			b.WriteString("null")
		} else {
			asciiJSON(&b, *f.value)
		}
	}
	b.WriteByte('}')
	return b.String()
}

// asciiJSON writes s as json.dumps(ensure_ascii=True) does: \" \\ \n \r \t
// \b \f short escapes, every other byte outside space..tilde as \uXXXX
// (UTF-16, surrogate pairs above U+FFFF).
func asciiJSON(b *strings.Builder, s string) {
	const hexDigits = "0123456789abcdef"
	u := func(r rune) {
		b.WriteString(`\u`)
		for shift := 12; shift >= 0; shift -= 4 {
			b.WriteByte(hexDigits[(r>>uint(shift))&0xf])
		}
	}
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
			switch {
			case r >= 0x20 && r <= 0x7e:
				b.WriteRune(r)
			case r > 0xffff:
				r -= 0x10000
				u(0xd800 + (r>>10)&0x3ff)
				u(0xdc00 + r&0x3ff)
			default:
				u(r)
			}
		}
	}
	b.WriteByte('"')
}

// accountEnqueue is mail.enqueue for one account mail: 0 while mail is off or
// the address is not valid; an existing idempotency key returns its row's
// id; an insert that fails is logged (kind only) and answered with the row
// another writer stored, or 0, as Python does.
func accountEnqueue(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, m accountRow, now time.Time) (int64, error) {
	if !accountMailEnabled(getenv) {
		return 0, nil
	}
	to := obNormaliseEmail(m.to)
	if to == "" {
		return 0, nil
	}
	var id int64
	err := pool.QueryRow(ctx, `SELECT id FROM email_outbox WHERE idempotency_key = $1`, m.key).Scan(&id)
	if err == nil {
		return id, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return 0, errors.New("mail enqueue: outbox not read")
	}
	subject := m.subject
	if utf8.RuneCountInString(subject) > 200 {
		subject = string([]rune(subject)[:200])
	}
	at := obStamp(now)
	err = pool.QueryRow(ctx, `INSERT INTO email_outbox (idempotency_key, kind, reservation_id, apartment_id,
		owner_user_id, to_email, cc_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at)
		VALUES ($1, $2, NULL, NULL, $3, $4, NULL, $5, $6, 'queued', 0, $7, $7, $7) RETURNING id`,
		m.key, m.kind, m.owner, to, subject, accountPayloadJSON(m.payload), at).Scan(&id)
	if err == nil {
		return id, nil
	}
	log.Printf("mail enqueue failed kind=%s", m.kind)
	err = pool.QueryRow(ctx, `SELECT id FROM email_outbox WHERE idempotency_key = $1`, m.key).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, errors.New("mail enqueue: outbox not read")
	}
	return id, nil
}

// linkKeyPart is sha256(token).hexdigest()[:24]: the key changes with every
// link, so a second request is a second mail.
func linkKeyPart(token string) string {
	sum := sha256.Sum256([]byte(token))
	return hex.EncodeToString(sum[:])[:24]
}

// QueueLinkMail is mail_notify.link_mail: queue a login (KindLoginLink),
// invitation (KindAccountInvite) or address confirmation (KindEmailConfirm)
// link to toEmail. The stored body carries ClaimSecretMarker where the token
// belongs; the token travels encrypted beside it (claim_secret_enc), as a
// guest claim link does. minutes is the link's lifetime
// (session.LinkTTL[purpose] / 60); lang "" is English. It returns the outbox
// id for SendNow, 0 when nothing was queued (mail off, invalid address).
// The token is encrypted before mail is checked, as Python does, so missing
// data keys are an error even with mail off.
func QueueLinkMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, kind string,
	userID int64, toEmail, token string, minutes int, lang string, now time.Time) (int64, error) {
	spec, ok := linkMail[kind]
	if !ok {
		return 0, ErrUnknownMail
	}
	link := accountAppBase(getenv) + spec[1] + "?t=" + ClaimSecretMarker
	lang = authLanguage(lang)
	c, err := BuildLinkMail(accountPublicBase(getenv), accountOperatorEmail(getenv), kind, link, minutes, lang)
	if err != nil {
		return 0, err
	}
	var enc *string
	if token != "" {
		keys, err := secure.LoadDataKeys(getenv)
		if err != nil {
			return 0, err
		}
		sealed, err := keys.EncryptString(token)
		if err != nil {
			return 0, errors.New("mail: link secret not encrypted")
		}
		enc = &sealed
	}
	return accountEnqueue(ctx, pool, getenv, accountRow{
		kind: kind, key: kind + ":" + strconv.FormatInt(userID, 10) + ":" + linkKeyPart(token),
		to: toEmail, subject: c.Subject, owner: userID,
		payload: []payloadField{{"text", strPtr(c.Text)}, {"html", strPtr(c.HTML)}, {"lang", strPtr(lang)},
			{claimSecretKey, enc}},
	}, now)
}

// noticePayload is the payload of the English account notices:
// text, html, lang "en", reply_to the operator.
func noticePayload(c Content, getenv func(string) string) []payloadField {
	return []payloadField{{"text", strPtr(c.Text)}, {"html", strPtr(c.HTML)},
		{"lang", strPtr(hostMailLanguage)}, {"reply_to", strPtr(accountOperatorEmail(getenv))}}
}

// QueueEmailChanged is mail_notify.email_changed: the notice to the old and
// (with notifyNew) the new login address, keys
// email_changed:<user>:<stamp>:<side>. by is "support" or "self". It returns
// how many rows were queued (an existing key counts).
func QueueEmailChanged(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, userID int64,
	oldEmail, newEmail, stamp, by string, notifyNew bool, now time.Time) (int, error) {
	queued := 0
	masked := MaskEmail(newEmail)
	for _, s := range [][2]string{{"old", oldEmail}, {"new", newEmail}} {
		side, address := s[0], s[1]
		if address == "" || (side == "new" && !notifyNew) {
			continue
		}
		c, err := BuildEmailChanged(accountPublicBase(getenv), accountOperatorEmail(getenv), side, masked, "", by)
		if err != nil {
			return queued, err
		}
		id, err := accountEnqueue(ctx, pool, getenv, accountRow{
			kind: "email_changed", key: "email_changed:" + strconv.FormatInt(userID, 10) + ":" + stamp + ":" + side,
			to: address, subject: c.Subject, owner: userID, payload: noticePayload(c, getenv),
		}, now)
		if err != nil {
			return queued, err
		}
		if id != 0 {
			queued++
		}
	}
	return queued, nil
}

// QueuePasskeyAdded is mail_notify.passkey_added: the notice to the
// account's login address, key passkey_added:<user>:<passkey>. 0 when
// toEmail is empty or nothing was queued.
func QueuePasskeyAdded(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, userID int64,
	toEmail string, passkeyID int64, name string, now time.Time) (int64, error) {
	if toEmail == "" {
		return 0, nil
	}
	c := BuildPasskeyAdded(accountPublicBase(getenv), accountOperatorEmail(getenv), name, "")
	return accountEnqueue(ctx, pool, getenv, accountRow{
		kind: "passkey_added", key: "passkey_added:" + strconv.FormatInt(userID, 10) + ":" + strconv.FormatInt(passkeyID, 10),
		to: toEmail, subject: c.Subject, owner: userID, payload: noticePayload(c, getenv),
	}, now)
}

// isoDate is validation.parse_iso_date's strptime(value[:10], "%Y-%m-%d"):
// four digits, then a month and a day in strptime's forms (one or two
// digits, the day also " 5"), then a real calendar date.
var isoDate = regexp.MustCompile(`^([0-9]{4})-(1[0-2]|0[1-9]|[1-9])-(3[01]|[12][0-9]|0[1-9]|[1-9]| [1-9])$`)

// FmtDate is validation.fmt_date: an ISO date as DD.MM.YYYY; a value that is
// not one is returned unchanged.
func FmtDate(value string) string {
	head := value
	if r := []rune(value); len(r) > 10 {
		head = string(r[:10])
	}
	m := isoDate.FindStringSubmatch(head)
	if m == nil {
		return value
	}
	y, _ := strconv.Atoi(m[1])
	mo, _ := strconv.Atoi(m[2])
	d, _ := strconv.Atoi(strings.TrimSpace(m[3]))
	t := time.Date(y, time.Month(mo), d, 0, 0, 0, 0, time.UTC)
	if y < 1 || t.Day() != d || int(t.Month()) != mo {
		return value
	}
	return t.Format("02.01.2006")
}

// workspaceContactEmails is mail_notify.workspace_contact_emails: every
// distinct normalised contact address on the workspace's legal entities, in
// id order.
func workspaceContactEmails(ctx context.Context, pool *pgxpool.Pool, ownerUserID int64) ([]string, error) {
	rows, err := pool.Query(ctx, `SELECT contact_email FROM legal_entity WHERE owner_user_id = $1 ORDER BY id`, ownerUserID)
	if err != nil {
		return nil, errors.New("mail: contact addresses not read")
	}
	defer rows.Close()
	var found []string
	seen := map[string]bool{}
	for rows.Next() {
		var raw *string
		if err := rows.Scan(&raw); err != nil {
			return nil, errors.New("mail: contact addresses not read")
		}
		if raw == nil {
			continue
		}
		if a := obNormaliseEmail(*raw); a != "" && !seen[a] {
			seen[a] = true
			found = append(found, a)
		}
	}
	if rows.Err() != nil {
		return nil, errors.New("mail: contact addresses not read")
	}
	return found, nil
}

// QueueWorkspaceDeletion is mail_notify.workspace_deletion: the deletion
// notice (stage DeletionScheduled or DeletionWeekBefore) to every contact
// address of the workspace, keys
// workspace_deletion:<owner>:<dueAt>:<stage>:<address>. It returns how many
// rows were queued (an existing key counts).
func QueueWorkspaceDeletion(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	ownerUserID int64, dueAt, stage string, now time.Time) (int, error) {
	if stage != DeletionScheduled && stage != DeletionWeekBefore {
		return 0, ErrUnknownMail
	}
	head := dueAt
	if r := []rune(dueAt); len(r) > 10 {
		head = string(r[:10])
	}
	c, err := BuildWorkspaceDeletion(accountPublicBase(getenv), accountOperatorEmail(getenv), stage, FmtDate(head), "")
	if err != nil {
		return 0, err
	}
	addresses, err := workspaceContactEmails(ctx, pool, ownerUserID)
	if err != nil {
		return 0, err
	}
	queued := 0
	for _, address := range addresses {
		id, err := accountEnqueue(ctx, pool, getenv, accountRow{
			kind: "workspace_deletion",
			key:  "workspace_deletion:" + strconv.FormatInt(ownerUserID, 10) + ":" + dueAt + ":" + stage + ":" + address,
			to:   address, subject: c.Subject, owner: ownerUserID, payload: noticePayload(c, getenv),
		}, now)
		if err != nil {
			return queued, err
		}
		if id != 0 {
			queued++
		}
	}
	return queued, nil
}
