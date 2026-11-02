package payments

// Go port of the two host POST routes that create and send a direct payment
// request: App/app/routes/payments.py payment_request_new (86-118) and
// payment_request_send (123-196), line by line. The Python helpers ported here
// are payment_request.create, _assign_variable_symbol and set_status
// (App/app/payment_request.py), and mail.enqueue with the guards this call
// needs (App/app/mail.py 231-290). Production keeps these paths on Python: the
// Go container is off and Caddy sends no path to Go.

import (
	"context"
	_ "embed"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

//go:embed i18n.json
var requestsJSON []byte

// requestStrings is the payments catalog (flash texts and reason labels),
// generated from App/app/host_i18n.py by App/scripts/go_host_i18n.py.
var requestStrings = hostweb.Load(requestsJSON)

// requestReasons is payment_request.REASONS.
var requestReasons = map[string]bool{
	"repair": true, "extra_guest": true, "late_checkout": true,
	"cleaning": true, "damage": true, "custom": true,
}

// requestRails is payment_request.RAILS.
var requestRails = map[string]bool{"card": true, "qr": true}

const (
	// requestMailLang is the language the send route always uses (payments.py "lang = cs").
	requestMailLang = "cs"
	// requestExpiryDays is the 30 days added to today for expires_at.
	requestExpiryDays = 30
	// requestMailSubjectCS is i18n.py mail_payment_request_subject (cs).
	requestMailSubjectCS = "Žádost o platbu od vašeho hostitele (%d Kč)"
	// requestMailTextCS is i18n.py mail_payment_request_text (cs).
	requestMailTextCS = "Dobrý den,\n\nVáš hostitel vás žádá o platbu %d Kč za: %s.\nZaplaťte zde: %s\n\nPokud jste tuto zprávu nečekali, ignorujte ji.\n"
)

const (
	requestRowSQL = `SELECT owner_user_id, status, rail, reason, amount_czk, reservation_id, guest_email
		FROM payment_request WHERE id = $1`
	requestStayOwnerSQL = `SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id
		WHERE r.id = $1 AND a.owner_user_id = $2`
	requestInsertSQL = `INSERT INTO payment_request (owner_user_id, apartment_id, reservation_id, reason, amount_czk,
		currency, guest_email, guest_note, rail, status, expires_at, created_at, updated_at)
		VALUES ($1, NULL, $2, $3, $4, 'CZK', $5, $6, $7, 'draft', $8, $9, $9) RETURNING id`
	requestVSSQL       = `UPDATE payment_request SET variable_symbol = $1, updated_at = $2 WHERE id = $3`
	requestSentSQL     = `UPDATE payment_request SET status = 'sent', updated_at = $1 WHERE id = $2 AND status = 'draft'`
	reservationDemoSQL = `SELECT 1 FROM reservation WHERE id = $1 AND source = 'demo'`
	hostReplyToSQL     = `SELECT le.contact_email FROM legal_entity le
		JOIN apartment a ON a.legal_entity_id = le.id WHERE a.owner_user_id = $1 LIMIT 1`
	hostEntitySQL = `SELECT contact_email FROM legal_entity WHERE owner_user_id = $1 LIMIT 1`
)

// LinkSender is the card-rail half of the send route: payment_links.send. The
// returned URL is "" when the account cannot take payments yet.
type LinkSender interface {
	SendPaymentLink(ctx context.Context, requestID int64) (string, error)
}

// RequestNewHandler serves POST /payments/requests/new (payments.py 86-118).
// CSRF runs first, then the login gate, as the Python dependencies do.
func RequestNewHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			requestFail(w, err)
			return
		}
		if h == nil {
			return
		}
		ctx := r.Context()
		owner := h.Workspace.ID
		lang := hostweb.Lang(r)
		invalid := func() {
			hostweb.Back(w, r, "/payments", hostweb.Flash{}, requestFlash(lang, "payments.err.invalid"))
		}

		reason := strings.TrimSpace(r.PostFormValue("reason"))
		if !requestReasons[reason] {
			invalid()
			return
		}
		amount, ok := paymentAmount(strings.TrimSpace(r.PostFormValue("amount_czk")))
		if !ok {
			hostweb.Back(w, r, "/payments", hostweb.Flash{}, requestFlash(lang, "payments.err.amount"))
			return
		}
		var reservationID *int64
		if stayRaw := strings.TrimSpace(r.PostFormValue("reservation_id")); isASCIIDigits(stayRaw) {
			id, err := strconv.ParseInt(stayRaw, 10, 64)
			if err != nil {
				invalid()
				return
			}
			var found int64
			err = pool.QueryRow(ctx, requestStayOwnerSQL, id, owner).Scan(&found)
			if errors.Is(err, pgx.ErrNoRows) {
				invalid()
				return
			}
			if err != nil {
				requestFail(w, err)
				return
			}
			reservationID = &found
		}
		// expires = date.today() + 30 days; the container runs in UTC.
		expires := at.UTC().AddDate(0, 0, requestExpiryDays).Format("2006-01-02")
		rawRail := r.PostFormValue("rail")
		if rawRail == "" {
			rawRail = "card"
		}
		rail := strings.TrimSpace(rawRail)
		if !requestRails[rail] {
			invalid()
			return
		}
		stamp := stampAt(at)

		tx, err := pool.Begin(ctx)
		if err != nil {
			requestFail(w, err)
			return
		}
		defer func() { _ = tx.Rollback(ctx) }()
		var id int64
		err = tx.QueryRow(ctx, requestInsertSQL, owner, reservationID, reason, amount,
			optionalText(r.PostFormValue("guest_email")), optionalText(r.PostFormValue("guest_note")),
			rail, expires, stamp).Scan(&id)
		if err != nil {
			requestFail(w, err)
			return
		}
		if rail == "qr" {
			// VS = the row's own id, zero-padded to 10 digits (payment_request._assign_variable_symbol).
			if _, err := tx.Exec(ctx, requestVSSQL, fmt.Sprintf("%010d", id), stamp, id); err != nil {
				requestFail(w, err)
				return
			}
		}
		if err := tx.Commit(ctx); err != nil {
			requestFail(w, err)
			return
		}
		hostweb.Back(w, r, "/payments", requestFlash(lang, "payments.draft_saved"), hostweb.Flash{})
	}
}

// RequestSendHandler serves POST /payments/requests/{id}/send (payments.py
// 123-196). A non-integer id is a 404, as FastAPI's int path.
func RequestSendHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, links LinkSender) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}
		at := now()
		if !hostweb.CSRF(w, r, getenv, at) {
			return
		}
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			requestFail(w, err)
			return
		}
		if h == nil {
			return
		}
		id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		ctx := r.Context()
		owner := h.Workspace.ID
		lang := hostweb.Lang(r)
		flashErr := func(key string) {
			hostweb.Back(w, r, "/payments", hostweb.Flash{}, requestFlash(lang, key))
		}

		var (
			rowOwner             int64
			status, rail, reason string
			amount               int64
			reservationID        *int64
			guestEmail           *string
		)
		err = pool.QueryRow(ctx, requestRowSQL, id).Scan(&rowOwner, &status, &rail, &reason, &amount, &reservationID, &guestEmail)
		if errors.Is(err, pgx.ErrNoRows) {
			flashErr("payments.err.invalid")
			return
		}
		if err != nil {
			requestFail(w, err)
			return
		}
		if rowOwner != owner {
			flashErr("payments.err.invalid")
			return
		}
		if status != "draft" && status != "sent" {
			flashErr("payments.err.cannot_send")
			return
		}
		resend := status == "sent"
		email := ""
		if guestEmail != nil {
			email = strings.TrimSpace(*guestEmail)
		}
		if email == "" {
			flashErr("payments.err.no_email")
			return
		}
		var link string
		if rail == "card" {
			link, err = links.SendPaymentLink(ctx, id)
			if errors.Is(err, ErrStripeOff) {
				flashErr("payments.err.stripe_off")
				return
			}
			if err != nil {
				requestFail(w, err)
				return
			}
			if link == "" {
				flashErr("payments.err.not_ready")
				return
			}
		} else {
			link = fmt.Sprintf("/payments/qr/%d", id)
		}

		stamp := stampAt(at)
		if !resend {
			// payment_request.set_status draft -> sent: conditional, audited once.
			tag, err := pool.Exec(ctx, requestSentSQL, stamp, id)
			if err != nil {
				requestFail(w, err)
				return
			}
			if tag.RowsAffected() == 1 {
				if err := audit(ctx, pool, stamp, "payment_request_status",
					fmt.Sprintf("id=%d draft->sent", id), owner); err != nil {
					requestFail(w, err)
					return
				}
			}
		}
		if err := queueRequestMail(ctx, pool, getenv, owner, id, reservationID, email, link, reason, amount, resend); err != nil {
			requestFail(w, err)
			return
		}
		hostweb.Back(w, r, "/payments", requestFlash(lang, "payments.sent"), hostweb.Flash{})
	}
}

// queueRequestMail is mail.enqueue for kind payment_request as the send route
// calls it. Mail off, a demo stay, or an address that does not normalise queue
// nothing and are not errors. An enqueue failure is logged, not returned, as
// Python's enqueue does.
func queueRequestMail(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	owner, requestID int64, reservationID *int64, guestEmail, link, reason string, amount int64, resend bool) error {
	if !mailOn(getenv) {
		log.Printf("mail disabled; skip payment request mail id=%d", requestID)
		return nil
	}
	if reservationID != nil && *reservationID != 0 {
		var one int
		err := pool.QueryRow(ctx, reservationDemoSQL, *reservationID).Scan(&one)
		if err == nil {
			log.Printf("demo stay; skip guest mail kind=payment_request id=%d", requestID)
			return nil
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
	}
	to := ubyport.NormaliseEmail(guestEmail)
	if to == "" {
		return nil
	}
	replyTo, err := hostReplyTo(ctx, pool, owner)
	if err != nil {
		return err
	}
	if ubyport.NormaliseEmail(replyTo) == "" {
		log.Printf("guest mail has no reply_to kind=payment_request id=%d", requestID)
	}
	reasonLabel := requestStrings.T(requestMailLang, "payments.reason."+reason, nil)
	version := 1
	if resend {
		version = 2
	}
	key := fmt.Sprintf("payment_request:%d:sent:v%d", requestID, version)
	// json.dumps({"text", "lang", "reply_to", "apartment"}), ensure_ascii, default separators.
	payload := `{"text": ` + ubyport.PyString(fmt.Sprintf(requestMailTextCS, amount, reasonLabel, link)) +
		`, "lang": "cs", "reply_to": ` + ubyport.PyString(replyTo) + `, "apartment": null}`
	if _, err := ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:          "payment_request",
		Key:           key,
		ReservationID: reservationID,
		OwnerUserID:   &owner,
		To:            to,
		Subject:       fmt.Sprintf(requestMailSubjectCS, amount),
		Payload:       payload,
	}); err != nil {
		log.Printf("mail enqueue failed kind=payment_request key=%s", key)
	}
	return nil
}

// hostReplyTo is _host_reply_to: the entity contact of the owner's apartment,
// else of any entity they own. A row with no address gives "", as Python.
func hostReplyTo(ctx context.Context, pool *pgxpool.Pool, owner int64) (string, error) {
	var contact *string
	err := pool.QueryRow(ctx, hostReplyToSQL, owner).Scan(&contact)
	if errors.Is(err, pgx.ErrNoRows) {
		err = pool.QueryRow(ctx, hostEntitySQL, owner).Scan(&contact)
		if errors.Is(err, pgx.ErrNoRows) {
			return "", nil
		}
	}
	if err != nil {
		return "", err
	}
	if contact == nil {
		return "", nil
	}
	return *contact, nil
}

// mailOn is mail.mail_enabled: the backend is console or ses.
func mailOn(getenv func(string) string) bool {
	switch strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND"))) {
	case "console", "ses":
		return true
	}
	return false
}

// requestFlash is a payments flash in the request language.
func requestFlash(lang, key string) hostweb.Flash {
	return hostweb.Flash{Text: requestStrings.T(lang, key, nil), Key: key}
}

// paymentAmount is int(raw) for raw.isdigit() and int(raw) >= 1. Only ASCII
// digits count here; Python's isdigit also takes other Unicode digits.
func paymentAmount(raw string) (int64, bool) {
	if !isASCIIDigits(raw) {
		return 0, false
	}
	n, err := strconv.ParseInt(raw, 10, 64)
	if err != nil || n < 1 {
		return 0, false
	}
	return n, true
}

func isASCIIDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

// optionalText is strip() or None: an empty value is NULL.
func optionalText(raw string) *string {
	s := strings.TrimSpace(raw)
	if s == "" {
		return nil
	}
	return &s
}

func requestFail(w http.ResponseWriter, err error) {
	log.Printf("payment request route failed: %v", err)
	text(w, http.StatusInternalServerError, "Internal Server Error")
}
