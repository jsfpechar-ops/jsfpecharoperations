package payments

// Go port of three more Python payment routes from App/app/routes/payments.py:
// payment_request_link (POST /payments/requests/{id}/link, 218-238) and
// guest_qr_png (GET /pay/{id}/{token}.png, 614-622) with the guest token from
// payment_request.guest_token. The HTML pages GET /payments/requests/{id}/share
// and GET /pay/{id}/{token} stay on Python; Caddy decides which paths reach Go.

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const guestQRSQL = `SELECT owner_user_id, rail, status, amount_czk, variable_symbol FROM payment_request WHERE id = $1`

// guestToken is payment_request.guest_token: 32 hex characters of an
// HMAC-SHA256 over "payreq:<id>:<variable symbol>" keyed by the app secret.
func guestToken(secret string, id int64, vs string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	fmt.Fprintf(mac, "payreq:%d:%s", id, vs)
	return hex.EncodeToString(mac.Sum(nil))[:32]
}

// GuestQRPNGHandler serves GET /pay/{id}/{file} for <token>.png: no login, the
// token is the proof. Anything else is a 404, as in Python.
func GuestQRPNGHandler(pool *pgxpool.Pool, getenv func(string) string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		token, ok := strings.CutSuffix(r.PathValue("file"), ".png")
		id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
		if !ok || err != nil || id < 0 || !asciiDigits(r.PathValue("id")) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		var (
			owner        int64
			rail, status string
			amount       int64
			vs           *string
		)
		err = pool.QueryRow(r.Context(), guestQRSQL, id).Scan(&owner, &rail, &status, &amount, &vs)
		if errors.Is(err, pgx.ErrNoRows) || (err == nil && (rail != "qr" || status == "cancelled")) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		if err != nil {
			requestFail(w, err)
			return
		}
		secret, err := secure.LoadSecret(getenv)
		if err != nil {
			requestFail(w, err)
			return
		}
		vsText := ""
		if vs != nil {
			vsText = *vs
		}
		if !hmac.Equal([]byte(guestToken(secret, id, vsText)), []byte(token)) {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		payload, err := qrPayload(r.Context(), pool, owner, amount, vs)
		if errors.Is(err, errQRAccount) {
			qrNoAccount(w)
			return
		}
		if err != nil {
			requestFail(w, err)
			return
		}
		png, err := qrPNGBytes(payload)
		if err != nil {
			requestFail(w, err)
			return
		}
		w.Header().Set("Content-Type", "image/png")
		w.Header().Set("Cache-Control", "private, max-age=300")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(png)
	}
}

func asciiDigits(s string) bool {
	return s != "" && isASCIIDigits(s)
}

// RequestLinkHandler serves POST /payments/requests/{id}/link: make or reuse
// the card link without an e-mail, then redirect to the share page (Python).
func RequestLinkHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, links LinkSender) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
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
		// _own_card_request: the owner's open card request.
		open := status == "draft" || status == "sent" || status == "awaiting_payment"
		if rowOwner != owner || rail != "card" || !open {
			flashErr("payments.err.invalid")
			return
		}
		link, err := links.SendPaymentLink(ctx, id)
		if errors.Is(err, ErrStripeOff) {
			flashErr("payments.err.stripe_off")
			return
		}
		if err != nil {
			requestFail(w, err)
			return
		}
		if link == "" {
			f := requestFlash(lang, "payments.err.not_ready")
			f.Fix = "stripe"
			hostweb.Back(w, r, "/payments", hostweb.Flash{}, f)
			return
		}
		if status == "draft" {
			stamp := stampAt(at)
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
		http.Redirect(w, r, fmt.Sprintf("/payments/requests/%d/share", id), http.StatusSeeOther)
	}
}
