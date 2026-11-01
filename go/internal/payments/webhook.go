// Package payments: webhook.go is the Go port of the Stripe webhook route
// (App/app/routes/stripe_connect.py stripe_webhook, lines 101-129) and of the
// helpers it calls: stripe_connect.py verify_event 326, _record_event 348,
// process_event 381, mirror_by_account_id 275, _mirror 243, _onboarding_state
// 218, _requirements_json 235; payment_links.py on_paid 64; payment_request.py
// set_status 105 and mark_paid 129; rate_limit.py _count, record, blocked and
// client_key. It writes the same rows and audit lines as Python.
package payments

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf16"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	webhookScope    = "stripe_webhook" // rate_limit scope, as in Python
	webhookLimit    = 600              // _WEBHOOK_LIMIT
	webhookWindow   = 3600             // _WEBHOOK_WINDOW, seconds
	webhookMaxBody  = 1 << 20          // body limit; Python has none
	stripeTolerance = 300              // Stripe SDK construct_event default, seconds
)

var (
	errBadSig = errors.New("bad signature")

	// _REQUIREMENT_KEYS and _REJECT_CODES, in Python order.
	requirementKeys = []string{"currently_due", "past_due", "eventually_due", "disabled_reason"}
	rejectCodes     = []string{"rejected", "listed", "fraudulent"}
)

const (
	pruneRateSQL  = `DELETE FROM rate_limit_event WHERE scope = $1 AND key = $2 AND at < $3`
	countRateSQL  = `SELECT COUNT(*) FROM rate_limit_event WHERE scope = $1 AND key = $2`
	insertRateSQL = `INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3)`

	insertEventSQL = `INSERT INTO stripe_webhook_event (event_id, event_type, mode, created_at)
		VALUES ($1, $2, $3, $4)`

	ownerByAccountSQL = `SELECT owner_user_id FROM stripe_account WHERE stripe_account_id = $1 AND mode = $2`
	mirrorSQL         = `UPDATE stripe_account SET onboarding_state = $1, charges_enabled = $2,
		payouts_enabled = $3, requirements_json = $4, updated_at = $5
		WHERE owner_user_id = $6 AND mode = $7 AND onboarding_state != $8`

	requestByLinkSQL = `SELECT id, status, owner_user_id, amount_czk FROM payment_request
		WHERE stripe_payment_link_id = $1`
	transitionSQL = `UPDATE payment_request SET status = $1, paid_at = COALESCE($2, paid_at),
		updated_at = $3 WHERE id = $4 AND status = $5`
)

// dbtx is the part of pgxpool.Pool and pgx.Tx the handler uses.
type dbtx interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

type stripeEvent struct {
	ID   string `json:"id"`
	Type string `json:"type"`
	Data struct {
		Object map[string]any `json:"object"`
	} `json:"data"`
}

// WebhookHandler answers POST /webhooks/stripe. The mode and the secret are read
// once, at construction, from getenv (trimmed; mode lowercased).
func WebhookHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	mode := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_STRIPE_MODE")))
	secret := strings.TrimSpace(getenv("UBYHOST_STRIPE_WEBHOOK_SECRET"))
	live := mode == "test" || mode == "live"

	return func(w http.ResponseWriter, r *http.Request) {
		ctx := r.Context()
		at := now()

		// Rate limit first, then record the row, as Python does.
		key := clientKey(r)
		blocked, err := rateBlocked(ctx, pool, key, at)
		if err != nil {
			log.Printf("stripe webhook rate limit failed: %v", err)
			text(w, http.StatusInternalServerError, "Internal Server Error")
			return
		}
		if blocked {
			text(w, http.StatusTooManyRequests, "slow down")
			return
		}
		if _, err := pool.Exec(ctx, insertRateSQL, webhookScope, key, unixFloat(at)); err != nil {
			log.Printf("stripe webhook rate limit record failed: %v", err)
			text(w, http.StatusInternalServerError, "Internal Server Error")
			return
		}

		raw, err := io.ReadAll(http.MaxBytesReader(w, r.Body, webhookMaxBody))
		if err != nil {
			text(w, http.StatusRequestEntityTooLarge, "payload too large")
			return
		}
		sig := r.Header.Get("Stripe-Signature")
		if !live || secret == "" {
			if live {
				log.Printf("webhook secret unset while UBYHOST_STRIPE_MODE=%s", mode)
				text(w, http.StatusInternalServerError, "webhook secret not configured")
				return
			}
			log.Printf("stripe webhook ignored (mode off): sig=%t bytes=%d", sig != "", len(raw))
			text(w, http.StatusOK, "ignored")
			return
		}

		event, err := verifyEvent(raw, sig, secret, at)
		if err != nil {
			log.Printf("stripe webhook signature rejected")
			text(w, http.StatusBadRequest, "bad signature")
			return
		}
		if err := processEvent(ctx, pool, event, mode, stampAt(at)); err != nil {
			log.Printf("stripe webhook processing failed: %v", err)
			text(w, http.StatusInternalServerError, "Internal Server Error")
			return
		}
		text(w, http.StatusOK, "ok")
	}
}

func text(w http.ResponseWriter, code int, body string) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(code)
	_, _ = io.WriteString(w, body)
}

// clientKey: CF-Connecting-IP (Caddy overwrites it), else the peer host, else "unknown".
func clientKey(r *http.Request) string {
	if v := strings.TrimSpace(r.Header.Get("CF-Connecting-IP")); v != "" {
		return v
	}
	if host, _, err := net.SplitHostPort(r.RemoteAddr); err == nil && host != "" {
		return host
	}
	if r.RemoteAddr != "" {
		return r.RemoteAddr
	}
	return "unknown"
}

func unixFloat(t time.Time) float64 {
	return float64(t.UnixNano()) / 1e9
}

// rateBlocked prunes the window (as _count does), then counts the rows.
func rateBlocked(ctx context.Context, pool *pgxpool.Pool, key string, now time.Time) (bool, error) {
	if _, err := pool.Exec(ctx, pruneRateSQL, webhookScope, key, unixFloat(now)-webhookWindow); err != nil {
		return false, err
	}
	var n int64
	if err := pool.QueryRow(ctx, countRateSQL, webhookScope, key).Scan(&n); err != nil {
		return false, err
	}
	return n >= webhookLimit, nil
}

// stampAt formats a time like Python db.utcnow(), the same as jobs.Now(0).
func stampAt(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// verifyEvent checks the Stripe-Signature header against the raw body and
// returns the parsed event. Any failure is errBadSig.
func verifyEvent(raw []byte, header, secret string, now time.Time) (stripeEvent, error) {
	var ev stripeEvent
	if err := verifySignature(raw, header, secret, now); err != nil {
		return ev, err
	}
	if err := json.Unmarshal(raw, &ev); err != nil {
		return ev, errBadSig
	}
	return ev, nil
}

// verifySignature follows the Stripe SDK: header "t=<unix>,v1=<hex>[,v1=...]",
// expected = hex HMAC-SHA256(secret, "<t>." + body), any v1 may match, and
// |now - t| must be within 300 s.
func verifySignature(raw []byte, header, secret string, now time.Time) error {
	var tsRaw string
	var ts int64
	haveTS := false
	var sigs []string
	for _, part := range strings.Split(header, ",") {
		k, v, ok := strings.Cut(part, "=")
		if !ok {
			continue
		}
		switch k {
		case "t":
			n, err := strconv.ParseInt(v, 10, 64)
			if err != nil {
				return errBadSig
			}
			tsRaw, ts, haveTS = v, n, true
		case "v1":
			sigs = append(sigs, v)
		}
	}
	if !haveTS || len(sigs) == 0 {
		return errBadSig
	}
	age := now.Unix() - ts
	if age < 0 {
		age = -age
	}
	if age > stripeTolerance {
		return errBadSig
	}
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(tsRaw + "."))
	mac.Write(raw)
	want := []byte(hex.EncodeToString(mac.Sum(nil)))
	for _, s := range sigs {
		if hmac.Equal([]byte(strings.ToLower(s)), want) {
			return nil
		}
	}
	return errBadSig
}

// processEvent records the event and applies its effect in one transaction. A
// replay (unique violation on event_id) changes nothing and answers ok.
func processEvent(ctx context.Context, pool *pgxpool.Pool, ev stripeEvent, mode, stamp string) error {
	if ev.ID == "" {
		return errors.New("event without id")
	}
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)

	if _, err := tx.Exec(ctx, insertEventSQL, ev.ID, ev.Type, mode, stamp); err != nil {
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			return nil
		}
		return err
	}
	switch ev.Type {
	case "account.updated":
		err = mirrorAccount(ctx, tx, ev.Data.Object, mode, stamp)
	case "payment_link.paid", "checkout.session.completed":
		err = onPaid(ctx, tx, ev.Data.Object, stamp)
	}
	if err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// mirrorAccount is _mirror_by_account_id plus _mirror: update only when the row
// exists and the state changes, audit only when a row changed.
func mirrorAccount(ctx context.Context, q dbtx, acct map[string]any, mode, stamp string) error {
	id, _ := acct["id"].(string)
	var owner int64
	err := q.QueryRow(ctx, ownerByAccountSQL, id, mode).Scan(&owner)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	state := onboardingState(acct)
	req, _ := acct["requirements"].(map[string]any)
	charges := boolInt(truthy(acct["charges_enabled"]))
	payouts := boolInt(truthy(acct["payouts_enabled"]))
	tag, err := q.Exec(ctx, mirrorSQL, state, charges, payouts, requirementsJSON(req), stamp, owner, mode, state)
	if err != nil {
		return err
	}
	if tag.RowsAffected() == 0 {
		return nil
	}
	detail := fmt.Sprintf("acct=%s state=%s charges=%d payouts=%d", id, state, charges, payouts)
	return audit(ctx, q, stamp, "stripe_account_state", detail, owner)
}

// onboardingState maps Stripe's account onto the five mirror states.
func onboardingState(acct map[string]any) string {
	req, _ := acct["requirements"].(map[string]any)
	if truthy(acct["disabled"]) {
		return "disabled"
	}
	if errs, ok := req["errors"].([]any); ok {
		for _, e := range errs {
			em, ok := e.(map[string]any)
			if !ok {
				continue
			}
			code, _ := em["code"].(string)
			for _, word := range rejectCodes {
				if strings.Contains(code, word) {
					return "rejected"
				}
			}
		}
	}
	due := truthy(req["currently_due"])
	past := truthy(req["past_due"])
	if truthy(acct["charges_enabled"]) && !due && !past {
		return "complete"
	}
	if due || past {
		return "action_required"
	}
	return "pending"
}

// requirementsJSON is Python json.dumps(subset): key order of requirementKeys,
// ", " and ": " separators, ensure_ascii. NULL when nothing is set.
func requirementsJSON(req map[string]any) *string {
	if len(req) == 0 {
		return nil
	}
	var parts []string
	for _, k := range requirementKeys {
		v := req[k]
		if !truthy(v) {
			continue
		}
		parts = append(parts, pyString(k)+": "+pyValue(v))
	}
	if len(parts) == 0 {
		return nil
	}
	s := "{" + strings.Join(parts, ", ") + "}"
	return &s
}

// onPaid is payment_links.on_paid: link id = object.payment_link or object.id.
// Statuses other than draft, sent, awaiting_payment and paid write nothing.
func onPaid(ctx context.Context, q dbtx, obj map[string]any, stamp string) error {
	linkID, _ := obj["payment_link"].(string)
	if linkID == "" {
		linkID, _ = obj["id"].(string)
	}
	if linkID == "" {
		return nil
	}
	var id, owner, amount int64
	var status string
	err := q.QueryRow(ctx, requestByLinkSQL, linkID).Scan(&id, &status, &owner, &amount)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	switch status {
	case "paid":
		return nil
	case "draft", "sent", "awaiting_payment":
	default:
		return nil
	}
	if status == "draft" {
		if err := setStatus(ctx, q, id, owner, "draft", "sent", false, stamp); err != nil {
			return err
		}
		status = "sent"
	}
	if err := setStatus(ctx, q, id, owner, status, "paid", true, stamp); err != nil {
		return err
	}
	return audit(ctx, q, stamp, "payment_request_paid",
		fmt.Sprintf("id=%d via=stripe_webhook amount=%d CZK", id, amount), owner)
}

// setStatus moves one request from one status to another, with its audit line.
func setStatus(ctx context.Context, q dbtx, id, owner int64, from, to string, paid bool, stamp string) error {
	var paidAt any
	if paid {
		paidAt = stamp
	}
	tag, err := q.Exec(ctx, transitionSQL, to, paidAt, stamp, id, from)
	if err != nil {
		return err
	}
	if tag.RowsAffected() != 1 {
		return fmt.Errorf("payment_request %d changed while the webhook ran", id)
	}
	return audit(ctx, q, stamp, "payment_request_status", fmt.Sprintf("id=%d %s->%s", id, from, to), owner)
}

func audit(ctx context.Context, q dbtx, stamp, action, detail string, owner int64) error {
	_, err := q.Exec(ctx, insertAuditSQL, stamp, action, detail, owner)
	return err
}

func boolInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

// truthy is Python truthiness for the JSON values Stripe sends.
func truthy(v any) bool {
	switch x := v.(type) {
	case bool:
		return x
	case string:
		return x != ""
	case float64:
		return x != 0
	case []any:
		return len(x) > 0
	case map[string]any:
		return len(x) > 0
	}
	return false
}

// pyValue renders a JSON value the way Python json.dumps does.
func pyValue(v any) string {
	switch x := v.(type) {
	case bool:
		if x {
			return "true"
		}
		return "false"
	case string:
		return pyString(x)
	case float64:
		return strconv.FormatFloat(x, 'f', -1, 64)
	case []any:
		parts := make([]string, len(x))
		for i, e := range x {
			parts[i] = pyValue(e)
		}
		return "[" + strings.Join(parts, ", ") + "]"
	case map[string]any:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		parts := make([]string, len(keys))
		for i, k := range keys {
			parts[i] = pyString(k) + ": " + pyValue(x[k])
		}
		return "{" + strings.Join(parts, ", ") + "}"
	}
	return "null"
}

// pyString is json.dumps for one string with ensure_ascii=True.
func pyString(s string) string {
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
		case r < 0x20 || r > 0x7e:
			if r > 0xffff {
				hi, lo := utf16.EncodeRune(r)
				fmt.Fprintf(&b, `\u%04x\u%04x`, hi, lo)
			} else {
				fmt.Fprintf(&b, `\u%04x`, r)
			}
		default:
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
	return b.String()
}
