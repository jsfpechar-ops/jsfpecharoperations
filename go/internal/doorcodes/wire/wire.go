// Package doorwire implements the door-code flow's outside dependencies (the interfaces in
// go/internal/doorcodes/deps.go) against the real database, mail outbox and push outbox.
//
// Each type says which Python function it replaces. Where a function is not ported yet,
// the method returns ErrNotPorted and the doorcodes flow takes its documented fallback.
package doorwire

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strings"
	"time"
	"unicode/utf16"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// ErrNotPorted marks a Python function this package does not implement yet.
var ErrNotPorted = errors.New("doorwire: not ported yet")

// Mailer implements doorcodes.Mailer: mail_notify builders, mail.enqueue and mail.drain.
type Mailer struct {
	Pool   *pgxpool.Pool
	Env    mailnotify.DoorCodeMailEnv // config.app_base_url(), config.PUBLIC_BASE_URL, config.SUPPORT_EMAIL
	Keys   *secure.MultiFernet        // decrypts door_code.pin_enc (db.decrypt_field)
	Getenv func(string) string        // UBYHOST_MAIL_BACKEND and UBYHOST_WEB_PUSH are read here
	Now    func() time.Time           // nil means time.Now
	// MailConfig is the outbox sender configuration for Drain (mail.drain).
	MailConfig mail.Config
}

var _ doorcodes.Mailer = (*Mailer)(nil)

func (m *Mailer) now() time.Time {
	if m.Now != nil {
		return m.Now()
	}
	return time.Now()
}

// BuildDoorCode is mail_notify.build_door_code. The fee block arrives as a map (the
// Python dict); it is read through its JSON form into mailnotify.DoorCodeFee.
func (m *Mailer) BuildDoorCode(ctx context.Context, in doorcodes.DoorCodeMail) (doorcodes.DoorCodeContent, error) {
	var fee *mailnotify.DoorCodeFee
	if len(in.Fee) > 0 {
		raw, err := json.Marshal(in.Fee)
		if err != nil {
			return doorcodes.DoorCodeContent{}, err
		}
		var f mailnotify.DoorCodeFee
		if err := json.Unmarshal(raw, &f); err != nil {
			return doorcodes.DoorCodeContent{}, err
		}
		fee = &f
	}
	out := mailnotify.BuildDoorCode(m.Env.PublicBaseURL, mailnotify.DoorCodeInput{
		Lang:         in.Lang,
		PropertyName: in.PropertyName,
		Checkin:      in.Checkin,
		Checkout:     in.Checkout,
		FirstUseBy:   in.FirstUseBy,
		Fee:          fee,
	})
	return doorcodes.DoorCodeContent{
		Subject: out.Subject,
		QRSpayd: out.QRSpayd,
		Fields:  map[string]any{"text": out.Text, "html": out.HTML},
	}, nil
}

// GuestPayload is mail_notify.guest_payload: text, lang, html when present, and reply_to
// from the apartment's legal entity (never UbyHost support).
func (m *Mailer) GuestPayload(ctx context.Context, apartmentID int64, content doorcodes.DoorCodeContent, lang string) (map[string]any, error) {
	payload := map[string]any{"text": content.Fields["text"], "lang": lang}
	if html, _ := content.Fields["html"].(string); html != "" {
		payload["html"] = html
	}
	apt, err := m.loadApartment(ctx, apartmentID)
	if err != nil {
		return nil, err
	}
	if apt != nil {
		replyTo, err := m.entityContactEmail(ctx, apt.legalEntityID)
		if err != nil {
			return nil, err
		}
		if replyTo != "" {
			payload["reply_to"] = replyTo
		}
	}
	return payload, nil
}

// DoorCodeNotice is mail_notify.door_code_notice(door_code_id, variant). The Python key
// suffix is not part of the interface, so the key has no suffix.
func (m *Mailer) DoorCodeNotice(ctx context.Context, doorCodeID int64, stage string) error {
	return m.DoorCodeNoticeKeyed(ctx, doorCodeID, stage, "")
}

// DoorCodeNoticeKeyed is mail_notify.door_code_notice(door_code_id, variant, key_suffix). An
// empty keySuffix is Python's None; a non-empty one makes the mail key unique for that suffix.
func (m *Mailer) DoorCodeNoticeKeyed(ctx context.Context, doorCodeID int64, stage, keySuffix string) error {
	var reservationID, apartmentID int64
	var lastError, pinEnc *string
	err := m.Pool.QueryRow(ctx,
		"SELECT reservation_id, apartment_id, last_error, pin_enc FROM door_code WHERE id = $1",
		doorCodeID).Scan(&reservationID, &apartmentID, &lastError, &pinEnc)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	res, err := m.loadReservation(ctx, reservationID)
	if err != nil || res == nil {
		return err
	}
	apt, err := m.loadApartment(ctx, apartmentID)
	if err != nil || apt == nil {
		return err
	}
	to, err := m.entityContactEmail(ctx, apt.legalEntityID)
	if err != nil || to == "" {
		return err
	}
	in := mailnotify.DoorCodeNoticeIn{
		DoorCodeID:    doorCodeID,
		ReservationID: res.id,
		Variant:       stage,
		PropertyName:  apt.internalName,
		DateFrom:      res.dateFrom,
		LastError:     deref(lastError),
	}
	in.KeySuffix = keySuffix
	if deref(pinEnc) != "" {
		in.HasPin = true
		in.Pin = m.decryptOrEmpty(deref(pinEnc))
	}
	out := mailnotify.BuildDoorCodeNotice(m.Env, in)
	_, _, err = m.Enqueue(ctx, noticeOutbox(out, to, res.id, apt))
	return err
}

// DelayedNotice is mail_notify.door_code_delayed_notice(reservation_id, reason). It is not
// in the doorcodes.Mailer interface; it is here so the flow can call it when the
// interface gains the method.
func (m *Mailer) DelayedNotice(ctx context.Context, reservationID int64, reason string) error {
	res, err := m.loadReservation(ctx, reservationID)
	if err != nil || res == nil {
		return err
	}
	apt, err := m.loadApartment(ctx, res.apartmentID)
	if err != nil || apt == nil {
		return err
	}
	to, err := m.entityContactEmail(ctx, apt.legalEntityID)
	if err != nil || to == "" {
		return err
	}
	out := mailnotify.BuildDoorCodeDelayedNotice(m.Env, mailnotify.DoorCodeDelayedIn{
		ReservationID: res.id,
		PropertyName:  apt.internalName,
		DateFrom:      res.dateFrom,
		Reason:        reason,
	})
	_, _, err = m.Enqueue(ctx, noticeOutbox(out, to, res.id, apt))
	return err
}

// Enqueue is mail.enqueue. ok is false where Python returns None: mail disabled, a demo
// stay's guest mail, or an address that does not normalise. An existing idempotency key
// returns the existing row's id with ok true, as Python does.
func (m *Mailer) Enqueue(ctx context.Context, in doorcodes.OutboxMail) (int64, bool, error) {
	if !mailEnabled(m.Getenv) {
		return 0, false, nil
	}
	if in.Kind == "door_code" && in.ReservationID != 0 {
		var one int
		err := m.Pool.QueryRow(ctx,
			"SELECT 1 FROM reservation WHERE id = $1 AND source = 'demo'", in.ReservationID).Scan(&one)
		if err == nil {
			return 0, false, nil
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return 0, false, err
		}
	}
	to := ubyport.NormaliseEmail(in.ToEmail)
	if to == "" {
		return 0, false, nil
	}
	payload, err := encodePayload(in.Kind, in.Payload)
	if err != nil {
		return 0, false, err
	}
	id, err := ubyport.EnqueueMail(ctx, m.Pool, ubyport.OutboxMail{
		Kind:          in.Kind,
		Key:           in.IdempotencyKey,
		ReservationID: optID(in.ReservationID),
		ApartmentID:   optID(in.ApartmentID),
		OwnerUserID:   optID(in.OwnerUserID),
		To:            to,
		CC:            ubyport.NormaliseEmail(in.CcEmail),
		Subject:       in.Subject,
		Payload:       payload,
	})
	if err != nil {
		return 0, false, err
	}
	return id, true, nil
}

// Drain is mail.drain(limit=...): a no-op unless the mail backend is console or ses.
func (m *Mailer) Drain(ctx context.Context, limit int) error {
	if !m.MailConfig.Enabled() {
		return nil
	}
	_, err := mail.Drain(ctx, m.Pool, m.MailConfig, limit)
	return err
}

// mailEnabled is mail.py mail_enabled(): UBYHOST_MAIL_BACKEND is console or ses.
func mailEnabled(getenv func(string) string) bool {
	backend := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	return backend == "console" || backend == "ses"
}

// noticeOutbox is the OutboxMail a notice enqueues (the ids come from the rows read).
func noticeOutbox(out mailnotify.DoorCodeNoticeOut, to string, reservationID int64, apt *apartment) doorcodes.OutboxMail {
	return doorcodes.OutboxMail{
		Kind:           out.Kind,
		IdempotencyKey: out.IdempotencyKey,
		ToEmail:        to,
		CcEmail:        out.CC,
		Subject:        out.Subject,
		Payload:        map[string]any{"text": out.Text, "html": out.HTML, "lang": out.Lang},
		ReservationID:  reservationID,
		ApartmentID:    apt.id,
		OwnerUserID:    apt.ownerUserID,
	}
}

// encodePayload is json.dumps(payload) as Python writes it: ensure_ascii, ", " and ": "
// separators, and the keys in the order the Python builder inserted them. A notice is
// text, html, lang (_door_code_payload); a guest mail is text, lang, html, reply_to, then
// the door-code keys the flow adds (guest_payload and _send_code_mail). Any other key
// follows in sorted order. Only string values are supported.
func encodePayload(kind string, payload map[string]any) (string, error) {
	order := []string{"text", "lang", "html", "reply_to", "qr_spayd", "door_code_enc"}
	if kind == "door_code_notice" {
		order = []string{"text", "html", "lang"}
	}
	seen := map[string]bool{}
	for _, k := range order {
		seen[k] = true
	}
	var extra []string
	for k := range payload {
		if !seen[k] {
			extra = append(extra, k)
		}
	}
	sort.Strings(extra)
	keys := append(order, extra...)

	var b strings.Builder
	b.WriteByte('{')
	first := true
	for _, k := range keys {
		v, ok := payload[k]
		if !ok {
			continue
		}
		s, ok := v.(string)
		if !ok {
			return "", fmt.Errorf("doorwire: payload %q is %T, want string", k, v)
		}
		if !first {
			b.WriteString(", ")
		}
		first = false
		pyJSONString(&b, k)
		b.WriteString(": ")
		pyJSONString(&b, s)
	}
	b.WriteByte('}')
	return b.String(), nil
}

// pyJSONString writes s as json.dumps does with ensure_ascii=True: every character
// outside printable ASCII is \uXXXX (surrogate pairs above the BMP), and < > & are not
// escaped (Go's encoding/json would escape them).
func pyJSONString(b *strings.Builder, s string) {
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
		case r >= 0x20 && r <= 0x7e:
			b.WriteRune(r)
		case r > 0xffff:
			hi, lo := utf16.EncodeRune(r)
			fmt.Fprintf(b, `\u%04x\u%04x`, hi, lo)
		default:
			fmt.Fprintf(b, `\u%04x`, r)
		}
	}
	b.WriteByte('"')
}

func optID(v int64) *int64 {
	if v == 0 {
		return nil
	}
	return &v
}

func deref(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// decryptOrEmpty is db.decrypt_field(...) or "": a token that does not decrypt gives "".
func (m *Mailer) decryptOrEmpty(token string) string {
	if m.Keys == nil {
		return ""
	}
	plain, err := m.Keys.Decrypt(token, 0, m.now())
	if err != nil {
		return ""
	}
	return string(plain)
}

type reservation struct {
	id          int64
	apartmentID int64
	dateFrom    string
}

type apartment struct {
	id            int64
	internalName  string
	ownerUserID   int64
	legalEntityID int64
}

func (m *Mailer) loadReservation(ctx context.Context, id int64) (*reservation, error) {
	var r reservation
	err := m.Pool.QueryRow(ctx,
		"SELECT id, apartment_id, date_from FROM reservation WHERE id = $1", id).
		Scan(&r.id, &r.apartmentID, &r.dateFrom)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &r, nil
}

func (m *Mailer) loadApartment(ctx context.Context, id int64) (*apartment, error) {
	var a apartment
	var name *string
	var owner, entity *int64
	err := m.Pool.QueryRow(ctx,
		"SELECT id, internal_name, owner_user_id, legal_entity_id FROM apartment WHERE id = $1", id).
		Scan(&a.id, &name, &owner, &entity)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	a.internalName = deref(name)
	if owner != nil {
		a.ownerUserID = *owner
	}
	if entity != nil {
		a.legalEntityID = *entity
	}
	return &a, nil
}

// entityContactEmail is _entity_contact_email: legal_entity.contact_email, normalised;
// "" when there is no entity or no address.
func (m *Mailer) entityContactEmail(ctx context.Context, legalEntityID int64) (string, error) {
	if legalEntityID == 0 {
		return "", nil
	}
	var contact *string
	err := m.Pool.QueryRow(ctx, "SELECT contact_email FROM legal_entity WHERE id = $1", legalEntityID).Scan(&contact)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return ubyport.NormaliseEmail(deref(contact)), nil
}
