package payments

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"strconv"

	"github.com/jackc/pgx/v5"
)

const (
	paylinkRequestSQL = `SELECT id, owner_user_id, rail, reason, amount_czk, COALESCE(stripe_payment_link_id, '')
		FROM payment_request WHERE id = $1`
	paylinkAccountSQL = `SELECT stripe_account_id, onboarding_state FROM stripe_account WHERE owner_user_id = $1 AND mode = $2`
	paylinkStampSQL   = `UPDATE payment_request SET stripe_payment_link_id = $1, updated_at = $2 WHERE id = $3`
)

// reasonCS is the Czech payments.reason.* text (host_i18n.py 3149-3154).
var reasonCS = map[string]string{
	"repair":        "Příspěvek na opravu",
	"extra_guest":   "Další host",
	"late_checkout": "Pozdní odjezd",
	"cleaning":      "Úklid",
	"damage":        "Škoda",
	"custom":        "Vlastní",
}

// paymentLink is the part of a Stripe Payment Link this code reads.
type paymentLink struct {
	ID     string `json:"id"`
	URL    string `json:"url"`
	Active bool   `json:"active"`
}

// paylinkName is payment_links.product_name (lines 26-30): the Czech reason
// and the request number. An unknown reason falls back to its key, as
// host_i18n.translate does.
func paylinkName(reason string, id int64) string {
	text, ok := reasonCS[reason]
	if !ok {
		text = "payments.reason." + reason
	}
	return fmt.Sprintf("%s (žádost č. %d)", text, id)
}

// SendPaymentLink is payment_links.send (lines 26-95) for the card rail. It
// returns the Payment Link URL, or "" with no error when the owner's Stripe
// account cannot take payments yet, or when the request does not exist. A
// resend returns the stored link while it is still active.
func (s *StripeOnboarder) SendPaymentLink(ctx context.Context, requestID int64) (string, error) {
	var (
		id, owner, amount    int64
		rail, reason, linkID string
	)
	err := s.Pool.QueryRow(ctx, paylinkRequestSQL, requestID).Scan(&id, &owner, &rail, &reason, &amount, &linkID)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	if rail != "card" {
		return "", errors.New("card rail only")
	}
	var acct, state string
	err = s.Pool.QueryRow(ctx, paylinkAccountSQL, owner, s.mode()).Scan(&acct, &state)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	if state != "complete" {
		return "", nil
	}
	// One guard for the whole send, as Python's single _api() call (line 83).
	key, stamp, err := s.guard(ctx)
	if err != nil {
		return "", err
	}
	if linkID != "" {
		var old paymentLink
		err := s.call(ctx, key, "GET", "/v1/payment_links/"+url.PathEscape(linkID), "", nil, &old, acct)
		if err != nil {
			return "", err
		}
		if old.Active {
			return old.URL, nil
		}
	}
	form := url.Values{}
	idText := strconv.FormatInt(id, 10)
	form.Set("line_items[0][quantity]", "1")
	form.Set("line_items[0][price_data][currency]", "czk")
	form.Set("line_items[0][price_data][unit_amount]", strconv.FormatInt(amount*100, 10))
	form.Set("line_items[0][price_data][product_data][name]", paylinkName(reason, id))
	form.Set("restrictions[completed_sessions][limit]", "1")
	form.Set("metadata[payment_request_id]", idText)
	form.Set("payment_intent_data[metadata][payment_request_id]", idText)
	var created paymentLink
	err = s.call(ctx, key, "POST", "/v1/payment_links", "application/x-www-form-urlencoded",
		[]byte(form.Encode()), &created, acct)
	if err != nil {
		return "", err
	}
	if created.ID == "" || created.URL == "" {
		return "", errors.New("stripe: payment link response has no id or url")
	}
	if _, err := s.Pool.Exec(ctx, paylinkStampSQL, created.ID, stamp, requestID); err != nil {
		return "", err
	}
	if err := audit(ctx, s.Pool, stamp, "payment_link_created",
		fmt.Sprintf("id=%d link=%s", requestID, created.ID), owner); err != nil {
		return "", err
	}
	return created.URL, nil
}
