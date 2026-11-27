package doorwire

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// Payload keys of the completion mail (App/app/mail.py DOOR_CODE_KEY, QR_SPAYD_KEY,
// RECEIPT_DETAILS_KEY).
const (
	doorCodeEncKey       = "door_code_enc"
	qrSpaydKey           = "qr_spayd"
	receiptDetailsIDKey  = "receipt_details_reservation_id"
	completionDrainLimit = 4 // mail.drain(limit=4)
)

// CompletionDoors is the part of the door-code service the registration confirmation calls:
// completion_door_code. *doorcodes.Service satisfies it.
type CompletionDoors interface {
	CompletionDoorCode(ctx context.Context, res doorcodes.Reservation, apt doorcodes.Apartment) (doorcodes.CompletionResult, error)
}

// ConfirmationBilling is what the confirmation reads from the billing side: the stay's
// progress and its completion fee. LiveBilling satisfies it.
type ConfirmationBilling interface {
	ReservationProgress(ctx context.Context, reservationID int64) (int, *int, error)
	completionFee(ctx context.Context, apartmentID, reservationID int64) (*stayfee.CompletionFee, error)
}

var _ ConfirmationBilling = LiveBilling{}

// LiveConfirmations implements doorcodes.Confirmations: claim.maybe_notify_completion, the
// registration receipt (also aliased as Confirmations).
type LiveConfirmations struct {
	Pool    *pgxpool.Pool
	Mailer  *Mailer
	Billing ConfirmationBilling
	Doors   CompletionDoors
	Now     func() time.Time // nil means time.Now
	Log     *slog.Logger     // nil means slog.Default()
}

var _ doorcodes.Confirmations = LiveConfirmations{}

func (c LiveConfirmations) now() time.Time {
	if c.Now != nil {
		return c.Now()
	}
	return time.Now()
}

func (c LiveConfirmations) log() *slog.Logger {
	if c.Log != nil {
		return c.Log
	}
	return slog.Default()
}

// MaybeNotifyCompletion is claim.maybe_notify_completion. It sends the receipt once: the
// claim must be CLAIMED, not yet notified, the stay complete and the claim e-mail known.
// A held door code (hold) waits unless force is set. The mail is keyed completion:<res>:<filled>.
func (c LiveConfirmations) MaybeNotifyCompletion(ctx context.Context, reservationID, apartmentID int64, force bool) error {
	if c.Pool == nil {
		return errNilPool
	}
	if c.Billing == nil {
		c.Billing = LiveBilling{Pool: c.Pool, Now: c.Now}
	}
	var state string
	var email, lang, notified *string
	err := c.Pool.QueryRow(ctx,
		"SELECT state, email, lang, completion_notified_at FROM reservation_claim WHERE reservation_id = $1",
		reservationID).Scan(&state, &email, &lang, &notified)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	if state != "claimed" || deref(notified) != "" {
		return nil
	}
	filled, expected, err := c.Billing.ReservationProgress(ctx, reservationID)
	if err != nil {
		return err
	}
	if expected == nil || filled < *expected {
		return nil
	}
	if deref(email) == "" {
		// BE-3: the address was minimised away after the retention window.
		return nil
	}
	langCode := deref(lang)
	if langCode == "" {
		langCode = "en"
	}

	res, apt, err := c.loadStay(ctx, reservationID, apartmentID)
	if err != nil {
		return err
	}
	if res == nil || apt == nil {
		return nil
	}
	code, err := c.Doors.CompletionDoorCode(ctx, *res, apt.Apartment)
	if err != nil {
		return err
	}
	if code.Action == doorcodes.CompletionHold && !force {
		return nil
	}

	content, err := c.buildContent(ctx, res, apt, langCode, filled, *expected, code)
	if err != nil {
		return err
	}
	payload, err := c.Mailer.GuestPayload(ctx, apartmentID, doorcodes.DoorCodeContent{
		Subject: content.Subject,
		QRSpayd: content.QRSpayd,
		Fields:  map[string]any{"text": content.Text, "html": content.HTML},
	}, langCode)
	if err != nil {
		return err
	}
	if content.QRSpayd != "" {
		payload[qrSpaydKey] = content.QRSpayd
	}
	if code.Action == doorcodes.CompletionWith {
		var pin *string
		err := c.Pool.QueryRow(ctx, "SELECT pin_enc FROM door_code WHERE id = $1", code.DoorCodeID).Scan(&pin)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
		if pin != nil {
			payload[doorCodeEncKey] = *pin
		} else {
			payload[doorCodeEncKey] = nil
		}
	}
	if strings.Contains(content.Text, mailnotify.ReceiptDetailsMarker) {
		payload[receiptDetailsIDKey] = reservationID
	}
	cc, _ := payload["reply_to"].(string)
	outboxID, ok, err := c.enqueue(ctx, doorcodes.OutboxMail{
		Kind:           "completion",
		IdempotencyKey: fmt.Sprintf("completion:%d:%d", reservationID, filled),
		ToEmail:        deref(email),
		CcEmail:        cc,
		Subject:        content.Subject,
		Payload:        payload,
		ReservationID:  reservationID,
		ApartmentID:    apt.ID,
		OwnerUserID:    apt.OwnerUserID,
	})
	if err != nil {
		return err
	}

	now := c.now()
	stamp := completionISO(now)
	if _, err := c.Pool.Exec(ctx,
		"UPDATE reservation_claim SET completion_notified_at = $1, updated_at = $1 "+
			"WHERE reservation_id = $2 AND completion_notified_at IS NULL",
		stamp, reservationID); err != nil {
		return err
	}
	if code.Action == doorcodes.CompletionWith {
		if _, err := c.Pool.Exec(ctx,
			"UPDATE door_code SET notified_at = $1, updated_at = $1 WHERE id = $2",
			stamp, code.DoorCodeID); err != nil {
			return err
		}
	}
	if ok && outboxID != 0 && content.Fee != nil {
		// fee_update.record_baseline: a failure is logged, never raised (Python try/except).
		if err := mailjob.RecordBaseline(ctx, c.Pool, reservationID, content.Fee.Total, now); err != nil {
			c.log().Error(fmt.Sprintf("fee baseline not recorded reservation_id=%d err=%v", reservationID, err))
		}
	}
	return c.Mailer.Drain(ctx, completionDrainLimit)
}

// completionContent is what buildContent gives MaybeNotifyCompletion: the composed mail and
// the fee the receipt states (nil when none).
type completionContent struct {
	mailnotify.CompletionOutput
	Fee *mailnotify.DoorCodeFee
}

// buildContent is _guest_mail_content("completion", ...) on its happy path: the property label,
// dates, stay panel, host footer, door-code block and fee block, then build_completion.
func (c LiveConfirmations) buildContent(ctx context.Context, res *doorcodes.Reservation, apt *completionApt,
	lang string, filled, expected int, code doorcodes.CompletionResult) (completionContent, error) {
	propertyName := completionPropertyLabel(apt.InternalName, apt.UbyName, lang)
	host, err := completionHostDetails(ctx, c.Pool, apt.LegalEntityID)
	if err != nil {
		return completionContent{}, err
	}
	checkin, checkout := mailnotify.CompletionFacts(lang, res.DateFrom, res.DateTo, apt.CheckinHour, apt.CheckoutHour)

	var fee *mailnotify.DoorCodeFee
	typed, feeErr := c.Billing.completionFee(ctx, apt.ID, res.ID)
	if feeErr != nil {
		// _completion_fee drops the fee block on any failure, never the receipt.
		c.log().Warn(fmt.Sprintf("completion fee block dropped reservation_id=%d err=%v", res.ID, feeErr))
	} else if typed != nil {
		fee = feeToDoorFee(typed)
	}

	var doorCode *mailnotify.CompletionDoorCode
	if code.Action == doorcodes.CompletionWith && code.Fields != nil {
		doorCode = &mailnotify.CompletionDoorCode{
			Checkin:    code.Fields.Checkin,
			Checkout:   code.Fields.Checkout,
			FirstUseBy: code.Fields.FirstUseBy,
		}
	}
	exp := expected
	out := mailnotify.BuildCompletion(c.Mailer.Env.PublicBaseURL, mailnotify.CompletionInput{
		Lang:         lang,
		PropertyName: propertyName,
		Dates:        mailnotify.CompletionDateRange(res.DateFrom, res.DateTo),
		Host:         host,
		DoorCode:     doorCode,
		Filled:       filled,
		Expected:     &exp,
		Checkin:      checkin,
		Checkout:     checkout,
		HostURL:      fmt.Sprintf("%s/reservations/%d", c.Mailer.Env.AppBaseURL, res.ID),
		Fee:          fee,
		SentDetails:  true,
	})
	return completionContent{CompletionOutput: out, Fee: fee}, nil
}

// loadStay reads the reservation and apartment rows the confirmation needs. Either is nil
// when the row is gone.
func (c LiveConfirmations) loadStay(ctx context.Context, reservationID, apartmentID int64) (*doorcodes.Reservation, *completionApt, error) {
	var r doorcodes.Reservation
	var source *string
	err := c.Pool.QueryRow(ctx,
		"SELECT id, apartment_id, source, status, date_from, date_to, registration_completed_at, archived_at "+
			"FROM reservation WHERE id = $1", reservationID).
		Scan(&r.ID, &r.ApartmentID, &source, &r.Status, &r.DateFrom, &r.DateTo, &r.RegistrationCompletedAt, &r.ArchivedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil, nil
	}
	if err != nil {
		return nil, nil, err
	}
	r.Source = deref(source)

	var a completionApt
	var owner, entity *int64
	var lockProvider, internalName, ubyName *string
	err = c.Pool.QueryRow(ctx,
		"SELECT id, owner_user_id, lock_provider, lock_id, checkin_hour, checkout_hour, internal_name, uby_name, legal_entity_id "+
			"FROM apartment WHERE id = $1", apartmentID).
		Scan(&a.ID, &owner, &lockProvider, &a.LockID, &a.CheckinHour, &a.CheckoutHour, &internalName, &ubyName, &entity)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil, nil
	}
	if err != nil {
		return nil, nil, err
	}
	if owner != nil {
		a.OwnerUserID = *owner
	}
	if entity != nil {
		a.LegalEntityID = *entity
	}
	a.LockProvider = deref(lockProvider)
	a.InternalName = deref(internalName)
	a.UbyName = deref(ubyName)
	return &r, &a, nil
}

// completionApt is the apartment row the receipt reads: the completion-side fields of
// doorcodes.Apartment plus uby_name (the property label fallback) and legal_entity_id (the
// footer host).
type completionApt struct {
	doorcodes.Apartment
	UbyName       string
	LegalEntityID int64
}

// completionPropertyLabel is mail_notify.property_label: the host's name first, the
// police-register name (uby_name) as a fallback, then a translated stand-in.
func completionPropertyLabel(internalName, ubyName, lang string) string {
	name := strings.TrimSpace(internalName)
	if name == "" {
		name = strings.TrimSpace(ubyName)
	}
	if name != "" {
		return name
	}
	return mailnotify.GuestText(lang, "mail_property_fallback", nil)
}

// completionHostDetails is mail_notify.host_details: the operating entity as a guest sees it
// in a footer. A missing entity gives nil.
func completionHostDetails(ctx context.Context, pool *pgxpool.Pool, legalEntityID int64) (*mailnotify.Host, error) {
	if legalEntityID == 0 {
		return nil, nil
	}
	var name, seat, email, phone string
	err := pool.QueryRow(ctx, `SELECT COALESCE(name, ''), COALESCE(seat, ''), COALESCE(contact_email, ''),
		COALESCE(contact_phone, '') FROM legal_entity WHERE id = $1`, legalEntityID).
		Scan(&name, &seat, &email, &phone)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &mailnotify.Host{
		Name:  strings.TrimSpace(name),
		Seat:  strings.TrimSpace(seat),
		Email: ubyport.NormaliseEmail(email),
		Phone: strings.TrimSpace(phone),
	}, nil
}

// feeToDoorFee turns the stay fee into the fee dict the door-code and completion builders read.
func feeToDoorFee(f *stayfee.CompletionFee) *mailnotify.DoorCodeFee {
	out := &mailnotify.DoorCodeFee{Total: f.Total, Rate: f.Rate, VS: f.VS}
	for _, l := range f.Lines {
		out.Lines = append(out.Lines, mailnotify.FeeLine{Days: l[0], Amount: l[1]})
	}
	for _, w := range f.Ways {
		out.Ways = append(out.Ways, mailnotify.FeeWay{Key: w.Key, Payee: w.Payee, Account: w.Account,
			Spayd: w.SPAYD, Link: w.Link, Note: w.Note})
	}
	return out
}

// completionISO is db.utcnow() as the text columns store it (the doorcodes iso format).
func completionISO(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// enqueue is mail.enqueue for the completion mail. It is Mailer.Enqueue with the payload
// encoder below, because the receipt carries an integer (receipt_details_reservation_id) that
// encodePayload, which takes strings only, cannot write.
func (c LiveConfirmations) enqueue(ctx context.Context, in doorcodes.OutboxMail) (int64, bool, error) {
	if !mailEnabled(c.Mailer.Getenv) {
		return 0, false, nil
	}
	to := ubyport.NormaliseEmail(in.ToEmail)
	if to == "" {
		return 0, false, nil
	}
	payload, err := encodeCompletionPayload(in.Payload)
	if err != nil {
		return 0, false, err
	}
	id, err := ubyport.EnqueueMail(ctx, c.Pool, ubyport.OutboxMail{
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

// encodeCompletionPayload is json.dumps(payload) for the completion mail, keys in Python's
// insertion order: text, lang, html, reply_to, qr_spayd, door_code_enc, then the rest sorted
// (the order encodePayload uses). Strings, integers and None are written as Python writes them.
func encodeCompletionPayload(payload map[string]any) (string, error) {
	order := []string{"text", "lang", "html", "reply_to", "qr_spayd", "door_code_enc"}
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
	var b strings.Builder
	b.WriteByte('{')
	first := true
	for _, k := range append(order, extra...) {
		v, ok := payload[k]
		if !ok {
			continue
		}
		if !first {
			b.WriteString(", ")
		}
		first = false
		pyJSONString(&b, k)
		b.WriteString(": ")
		switch x := v.(type) {
		case string:
			pyJSONString(&b, x)
		case int64:
			b.WriteString(strconv.FormatInt(x, 10))
		case nil:
			b.WriteString("null")
		default:
			return "", fmt.Errorf("doorwire: completion payload %q is %T", k, v)
		}
	}
	b.WriteByte('}')
	return b.String(), nil
}
