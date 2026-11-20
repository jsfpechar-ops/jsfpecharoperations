package mailjob

// Port of App/app/fee_update.py (brief 1078): one update mail when the stay-fee
// total changes after the completion mail.
//
// The completion mail states the fee once; RecordBaseline stores that total.
// SweepFeeUpdates compares it with the live total and, once the live total has
// differed for QuietMinutes without a further change, mails the lead guest the
// old and the new amount. Nothing here touches the police filing.
//
// Timestamps keep the Python formats exactly: the pending and sent stamps
// (fee_pending_since, fee_mailed_at by the sweep) use datetime.isoformat(),
// which keeps microseconds when they are not zero; the baseline written by
// RecordBaseline uses db.utcnow(), which drops them.

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// QuietMinutes is fee_update.QUIET_MINUTES: the live total must stay put this long.
const QuietMinutes = 10

// claimedState is claim.CLAIMED.
const claimedState = "claimed"

// feeEligibleSQL is the eligibility read of sweep_fee_updates. It mirrors the
// Python WHERE clause one for one; the dates come back as text.
const feeEligibleSQL = `SELECT r.id, r.apartment_id, r.date_from::text, r.date_to::text,
		c.fee_mailed_total, c.fee_pending_total, a.owner_user_id, COALESCE(a.uby_name, '')
	FROM reservation r
	JOIN apartment a ON a.id = r.apartment_id
	JOIN reservation_claim c ON c.reservation_id = r.id
	WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1
		AND a.archived_at IS NULL
		AND r.source != 'demo' AND r.date_to >= $1 AND c.state = 'claimed'
		AND c.completion_notified_at IS NOT NULL AND c.fee_mailed_total IS NOT NULL
		AND c.email IS NOT NULL`

// feeRow is one eligible reservation as the sweep reads it.
type feeRow struct {
	id           int64
	apartmentID  int64
	dateFrom     string
	dateTo       string
	mailedTotal  int64
	pendingTotal *int64
	ownerUserID  *int64
	ubyName      string
}

// pyISO is datetime.isoformat() for an aware UTC time: microseconds are written
// only when they are not zero.
func pyISO(t time.Time) string {
	t = t.UTC()
	s := t.Format("2006-01-02T15:04:05")
	if us := t.Nanosecond() / 1000; us != 0 {
		s += fmt.Sprintf(".%06d", us)
	}
	return s + "+00:00"
}

// pyUTCNow is db.utcnow(): the same instant without microseconds.
func pyUTCNow(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// quietLongEnough is _quiet_long_enough: the pending stamp is QuietMinutes old.
func quietLongEnough(since *string, now time.Time) bool {
	if since == nil || *since == "" {
		return false
	}
	started, err := time.Parse(time.RFC3339Nano, *since)
	if err != nil {
		started, err = time.ParseInLocation("2006-01-02T15:04:05.999999999", *since, time.UTC)
		if err != nil {
			return false
		}
	}
	return now.Sub(started) >= QuietMinutes*time.Minute
}

// RecordBaseline is fee_update.record_baseline: the completion mail has just
// stated total, so remember it. updated_at is left alone (it is the clock of the
// claim-link resend cooldown). now is the instant written, as db.utcnow() would.
func RecordBaseline(ctx context.Context, pool *pgxpool.Pool, reservationID int64, total int, now time.Time) error {
	_, err := pool.Exec(ctx, `UPDATE reservation_claim SET fee_mailed_total = $1, fee_mailed_at = $2,
		fee_pending_total = NULL, fee_pending_since = NULL WHERE reservation_id = $3`,
		int64(total), pyUTCNow(now), reservationID)
	return err
}

// recordSent is _record_sent: move the baseline, but only if no other worker moved it first.
func recordSent(ctx context.Context, pool *pgxpool.Pool, reservationID, live int64, mailedAt, nowISO string) error {
	_, err := pool.Exec(ctx, `UPDATE reservation_claim SET fee_mailed_total = $1, fee_mailed_at = $2,
		fee_pending_total = NULL, fee_pending_since = NULL
		WHERE reservation_id = $3 AND fee_mailed_at = $4`,
		live, nowISO, reservationID, mailedAt)
	return err
}

// dueFee is what _decide hands back when the mail is due.
type dueFee struct {
	old      int64
	mailedAt string
	email    string
	lang     string
}

// decideFee is _decide: under the row lock, update the pending columns or
// return what is due. outcome is "none", "pending" or "due".
func decideFee(ctx context.Context, pool *pgxpool.Pool, reservationID int64, live *int64,
	now time.Time, nowISO string) (string, *dueFee, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return "", nil, err
	}
	defer tx.Rollback(ctx) //nolint:errcheck
	finish := func(outcome string, due *dueFee) (string, *dueFee, error) {
		if err := tx.Commit(ctx); err != nil {
			return "", nil, err
		}
		return outcome, due, nil
	}
	// db.lock_key(cur, "fee_update", reservation_id): the same advisory key as Python.
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "fee_update", reservationID); err != nil {
		return "", nil, err
	}
	var (
		state, email, lang, mailedAt, pendingSince *string
		mailedTotal, pendingTotal                  *int64
	)
	err = tx.QueryRow(ctx, `SELECT state, email, lang, fee_mailed_total, fee_mailed_at,
		fee_pending_total, fee_pending_since FROM reservation_claim WHERE reservation_id = $1`,
		reservationID).Scan(&state, &email, &lang, &mailedTotal, &mailedAt, &pendingTotal, &pendingSince)
	if errors.Is(err, pgx.ErrNoRows) {
		return finish("none", nil)
	}
	if err != nil {
		return "", nil, err
	}
	if state == nil || *state != claimedState || email == nil || *email == "" || mailedTotal == nil {
		return finish("none", nil)
	}
	mailed := *mailedTotal
	if live == nil || *live == mailed {
		if pendingTotal == nil && pendingSince == nil {
			return finish("none", nil)
		}
		// A mail queued under this baseline means its record was lost (the process
		// died after the enqueue). The guest was told that mail's total, so it
		// becomes the baseline; the next sweep then mails the correction.
		prefix := fmt.Sprintf("completion_update:%d:%s:", reservationID, pyStr(mailedAt))
		rows, err := tx.Query(ctx, `SELECT idempotency_key FROM email_outbox
			WHERE reservation_id = $1 AND kind = 'completion_update' ORDER BY id DESC`, reservationID)
		if err != nil {
			return "", nil, err
		}
		lost, found := "", false
		for rows.Next() {
			var key string
			if err := rows.Scan(&key); err != nil {
				rows.Close()
				return "", nil, err
			}
			if strings.HasPrefix(key, prefix) {
				lost, found = key[len(prefix):], true
				break
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return "", nil, err
		}
		if found && isDigits(lost) {
			if n, err := strconv.ParseInt(lost, 10, 64); err == nil && n != mailed {
				if _, err := tx.Exec(ctx, `UPDATE reservation_claim SET fee_mailed_total = $1,
					fee_mailed_at = $2, fee_pending_total = NULL, fee_pending_since = NULL
					WHERE reservation_id = $3`, n, nowISO, reservationID); err != nil {
					return "", nil, err
				}
				return finish("none", nil)
			}
		}
		if _, err := tx.Exec(ctx, `UPDATE reservation_claim SET fee_pending_total = NULL,
			fee_pending_since = NULL WHERE reservation_id = $1`, reservationID); err != nil {
			return "", nil, err
		}
		return finish("none", nil)
	}
	if pendingTotal == nil || *pendingTotal != *live {
		// The wait restarts on every further change.
		if _, err := tx.Exec(ctx, `UPDATE reservation_claim SET fee_pending_total = $1,
			fee_pending_since = $2 WHERE reservation_id = $3`, *live, nowISO, reservationID); err != nil {
			return "", nil, err
		}
		return finish("pending", nil)
	}
	if !quietLongEnough(pendingSince, now) {
		return finish("pending", nil)
	}
	due := &dueFee{old: mailed, mailedAt: pyStr(mailedAt), email: *email, lang: "en"}
	if lang != nil && *lang != "" {
		due.lang = *lang
	}
	return finish("due", due)
}

// pyStr is the text Python's f-string gives a column: "None" for NULL.
func pyStr(s *string) string {
	if s == nil {
		return "None"
	}
	return *s
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

// SweepFeeUpdates is sweep_fee_updates. It returns the counters queued (mails
// enqueued and the baseline moved) and pending (a change started its wait).
// Mail is queued through ubyport.EnqueueMail; the backend is read from
// UBYHOST_MAIL_BACKEND (console or ses), and UBYHOST_STAY_FEE_GUEST_PAY must be
// "on" for a fee to exist at all. A row that fails is logged and skipped.
func SweepFeeUpdates(ctx context.Context, pool *pgxpool.Pool, now time.Time) (map[string]int, error) {
	getenv := os.Getenv
	now = now.UTC()
	nowISO := pyISO(now)
	summary := map[string]int{"queued": 0, "pending": 0}

	loc, err := time.LoadLocation(configTimeZone)
	if err != nil {
		return nil, err
	}
	local := now.In(loc)
	today := time.Date(local.Year(), local.Month(), local.Day(), 0, 0, 0, 0, time.UTC)

	rows, err := pool.Query(ctx, feeEligibleSQL, today.Format("2006-01-02"))
	if err != nil {
		return nil, err
	}
	var list []feeRow
	for rows.Next() {
		var r feeRow
		if err := rows.Scan(&r.id, &r.apartmentID, &r.dateFrom, &r.dateTo, &r.mailedTotal,
			&r.pendingTotal, &r.ownerUserID, &r.ubyName); err != nil {
			rows.Close()
			return nil, err
		}
		list = append(list, r)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}

	guestPay := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STAY_FEE_GUEST_PAY"))) == "on"
	dec := lazyDecrypter(getenv)
	for _, r := range list {
		outcome, err := processFeeRow(ctx, pool, getenv, dec, guestPay, r, now, nowISO, today)
		if err != nil {
			log.Printf("fee update sweep skipped reservation_id=%d: %v", r.id, err)
			continue
		}
		switch outcome {
		case "pending":
			summary["pending"]++
		case "queued":
			summary["queued"]++
		}
	}
	return summary, nil
}

// processFeeRow handles one eligible reservation and returns "pending", "queued"
// or "" (nothing to count).
func processFeeRow(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	dec stayfee.Decrypter, guestPay bool, r feeRow, now time.Time, nowISO string, today time.Time) (string, error) {
	ap, err := stayfee.LoadApartment(ctx, pool, r.apartmentID)
	if err != nil {
		return "", err
	}
	fee, err := stayfee.LoadCompletionFee(ctx, pool, dec, ap, r.id, guestPay, today)
	if err != nil {
		return "", err
	}
	var live *int64
	if fee != nil {
		v := int64(fee.Total)
		live = &v
	}
	if r.pendingTotal == nil && (live == nil || *live == r.mailedTotal) {
		// Nothing changed and nothing is waiting: no transaction.
		return "", nil
	}
	outcome, due, err := decideFee(ctx, pool, r.id, live, now, nowISO)
	if err != nil {
		return "", err
	}
	if outcome == "pending" {
		return "pending", nil
	}
	if outcome != "due" || live == nil {
		return "", nil
	}
	// mail.enqueue returns nothing with the mail off or for an address that does
	// not parse; then the baseline does not move and the next sweep tries again.
	to := ubyport.NormaliseEmail(due.email)
	if to == "" || !mailEnabled(getenv) {
		return "", nil
	}

	host, err := feeHostDetails(ctx, pool, ap.LegalEntityID)
	if err != nil {
		return "", err
	}
	vs := ""
	for _, rail := range fee.Rails {
		if rail == "iban" {
			vs = fee.VS // mail_notify: the variable symbol rides on the bank way only
		}
	}
	content := mailnotify.BuildFeeUpdate(publicBase(getenv), mailnotify.FeeUpdateInput{
		Lang:         due.lang,
		PropertyName: feePropertyLabel(ap.InternalName, r.ubyName, due.lang),
		Dates:        fmtDateRange(r.dateFrom, r.dateTo),
		Host:         host,
		OldTotal:     int(due.old),
		NewTotal:     int(*live),
		VS:           vs,
	})
	var legalEntity *int64
	if ap.LegalEntityID != 0 {
		id := ap.LegalEntityID
		legalEntity = &id
	}
	replyTo, err := entityContactEmail(ctx, pool, legalEntity)
	if err != nil {
		return "", err
	}
	payload := encodePayload(
		kv{"text", content.Text}, kv{"lang", due.lang}, kv{"html", content.HTML}, kv{"reply_to", replyTo},
	)
	rid, aid := r.id, r.apartmentID
	// No clock and no counter in the key: a rerun, a second worker or a crash
	// before the record below reuses the same row.
	key := fmt.Sprintf("completion_update:%d:%s:%d", r.id, due.mailedAt, *live)
	if _, err := ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:          "completion_update",
		Key:           key,
		ReservationID: &rid,
		ApartmentID:   &aid,
		OwnerUserID:   r.ownerUserID,
		To:            to,
		Subject:       content.Subject,
		Payload:       payload,
	}); err != nil {
		return "", err
	}
	if err := recordSent(ctx, pool, r.id, *live, due.mailedAt, nowISO); err != nil {
		return "", err
	}
	return "queued", nil
}

// lazyDecrypter opens stored tokens with the data keys, loaded on first use. A
// fee block reads a guest token only when one is stored, so a deployment that
// never encrypts guest fields never needs the keys.
func lazyDecrypter(getenv func(string) string) stayfee.Decrypter {
	var once sync.Once
	var dec stayfee.Decrypter
	var loadErr error
	return func(token string) (string, error) {
		once.Do(func() {
			keys, err := secure.LoadDataKeys(getenv)
			if err != nil {
				loadErr = err
				return
			}
			dec = stayfee.FernetDecrypter(keys)
		})
		if loadErr != nil {
			return "", loadErr
		}
		return dec(token)
	}
}

// feeHostDetails is mail_notify.host_details: the operating entity as a guest sees
// it in a footer. A missing entity gives nil, which the footer reads as no host.
func feeHostDetails(ctx context.Context, pool *pgxpool.Pool, legalEntityID int64) (*mailnotify.Host, error) {
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

// feePropertyLabel is mail_notify.property_label: the host's name first, the
// police-register name as a fallback, then a translated stand-in.
func feePropertyLabel(internalName, ubyName, lang string) string {
	name := strings.TrimSpace(internalName)
	if name == "" {
		name = strings.TrimSpace(ubyName)
	}
	if name != "" {
		return name
	}
	return mailnotify.GuestText(lang, "mail_property_fallback", nil)
}

// fmtDate is validation.fmt_date: DD.MM.YYYY, or the input unchanged when it does not parse.
func fmtDate(value string) string {
	if d, ok := validation.ParseISODate(value); ok {
		return d.Format("02.01.2006")
	}
	return value
}

// fmtDateRange is validation.fmt_date_range: "from – to", or whichever end exists.
func fmtDateRange(from, to string) string {
	start, end := fmtDate(from), fmtDate(to)
	if start != "" && end != "" {
		return start + " \u2013 " + end
	}
	return start + end
}
