package payments

// The Stripe side of the Connect routes: a port of App/app/stripe_connect.py
// (_api 38-100, _identity_params to create_or_get_account 105-219,
// onboarding_link and handle_return 299-326).
//
// Known differences from Python, deliberately not ported: no network retries.
// stripe-python's StripeClient retries twice with idempotency keys; here a
// failed click is simply retried by the host. Request bodies are built from Go
// maps, so JSON keys come out sorted (same content, different order).

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	stripeDefaultBase  = "https://api.stripe.com"
	stripeVersion      = "2026-09-30.endive" // the version stripe-python 16.0.1 sends
	stripeDefaultLimit = 50000               // UBYHOST_STRIPE_MONTHLY_API_CALLS default (config)
	stripeTimeout      = 30 * time.Second
	stripeMaxResponse  = 1 << 20
)

const (
	stripeUsageSQL = `SELECT calls FROM lock_api_usage WHERE month = $1 AND provider = 'stripe'`
	stripeCountSQL = `INSERT INTO lock_api_usage (month, provider, calls) VALUES ($1, 'stripe', 1)
		ON CONFLICT(month, provider) DO UPDATE SET calls = lock_api_usage.calls + 1`
	stripeAccountSQL = `SELECT stripe_account_id FROM stripe_account WHERE owner_user_id = $1 AND mode = $2`
	stripeEntitySQL  = `SELECT name, COALESCE(contact_email, ''), COALESCE(business_type, '')
		FROM legal_entity WHERE owner_user_id = $1`
	stripeInsertSQL = `INSERT INTO stripe_account (owner_user_id, stripe_account_id, mode, onboarding_state,
		charges_enabled, payouts_enabled, created_at, updated_at)
		VALUES ($1, $2, $3, 'pending', 0, 0, $4, $4)`
)

// StripeOnboarder implements Onboarder over the Stripe HTTP API. Environment
// variables are read at call time. APIBase is a field so tests can point it at
// httptest; an empty value means https://api.stripe.com.
type StripeOnboarder struct {
	Pool    *pgxpool.Pool
	Getenv  func(string) string
	Now     func() time.Time
	Client  *http.Client
	APIBase string
}

// NewStripeOnboarder returns the production onboarder: a 30 s client and the
// live Stripe API base.
func NewStripeOnboarder(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) *StripeOnboarder {
	return &StripeOnboarder{
		Pool:    pool,
		Getenv:  getenv,
		Now:     now,
		Client:  &http.Client{Timeout: stripeTimeout},
		APIBase: stripeDefaultBase,
	}
}

// mode is UBYHOST_STRIPE_MODE trimmed and lower-cased (config.STRIPE_MODE).
func (s *StripeOnboarder) mode() string {
	return strings.ToLower(strings.TrimSpace(s.Getenv("UBYHOST_STRIPE_MODE")))
}

func (s *StripeOnboarder) base() string {
	if s.APIBase != "" {
		return s.APIBase
	}
	return stripeDefaultBase
}

func (s *StripeOnboarder) client() *http.Client {
	if s.Client != nil {
		return s.Client
	}
	return &http.Client{Timeout: stripeTimeout}
}

// guard is stripe_connect._api (lines 84-100): the mode and key check, the
// monthly budget, then the count, all before any HTTP call. It returns the
// secret key and the stamp of this call.
func (s *StripeOnboarder) guard(ctx context.Context) (string, string, error) {
	mode := s.mode()
	key := strings.TrimSpace(s.Getenv("UBYHOST_STRIPE_SECRET_KEY"))
	if (mode != "test" && mode != "live") || key == "" {
		return "", "", ErrStripeOff
	}
	stamp := stampAt(s.Now())
	month := stamp[:7]
	// An unparsable limit falls back to the default, as the Python config does.
	limit := int64(stripeDefaultLimit)
	if n, err := strconv.ParseInt(strings.TrimSpace(s.Getenv("UBYHOST_STRIPE_MONTHLY_API_CALLS")), 10, 64); err == nil {
		limit = n
	}
	if limit > 0 {
		var calls int64
		err := s.Pool.QueryRow(ctx, stripeUsageSQL, month).Scan(&calls)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return "", "", err
		}
		if calls >= limit {
			return "", "", ErrStripeOff
		}
	}
	if _, err := s.Pool.Exec(ctx, stripeCountSQL, month); err != nil {
		return "", "", err
	}
	return key, stamp, nil
}

// call sends one Stripe request. A non-2xx reply becomes an error naming the
// status and Stripe's error message and code only, never the body or the key.
func (s *StripeOnboarder) call(ctx context.Context, key, method, path, contentType string, body []byte, out any) error {
	req, err := http.NewRequestWithContext(ctx, method, s.base()+path, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+key)
	req.Header.Set("Stripe-Version", stripeVersion)
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	resp, err := s.client().Do(req)
	if err != nil {
		return fmt.Errorf("stripe: %s %s: %w", method, path, err)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, stripeMaxResponse))
	if err != nil {
		return err
	}
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		var se struct {
			Error struct {
				Message string `json:"message"`
				Code    string `json:"code"`
			} `json:"error"`
		}
		_ = json.Unmarshal(raw, &se)
		return fmt.Errorf("stripe: %s %s: HTTP %d: %s (%s)", method, path, resp.StatusCode,
			se.Error.Message, se.Error.Code)
	}
	if out == nil {
		return nil
	}
	return json.Unmarshal(raw, out)
}

// existingAccount is the mirror row for the owner in this mode ("" when none).
// Python account_for_owner, first half of create_or_get_account (no call).
func (s *StripeOnboarder) existingAccount(ctx context.Context, owner int64) (string, error) {
	var id string
	err := s.Pool.QueryRow(ctx, stripeAccountSQL, owner, s.mode()).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	return id, err
}

// accountOrCreate is create_or_get_account (lines 170-219).
func (s *StripeOnboarder) accountOrCreate(ctx context.Context, owner int64) (string, error) {
	id, err := s.existingAccount(ctx, owner)
	if err != nil || id != "" {
		return id, err
	}
	return s.createAccount(ctx, owner)
}

// createAccount posts the Accounts v2 account once, then mirrors it.
func (s *StripeOnboarder) createAccount(ctx context.Context, owner int64) (string, error) {
	var name, email, businessType string
	err := s.Pool.QueryRow(ctx, stripeEntitySQL, owner).Scan(&name, &email, &businessType)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", ErrNoEntity
	}
	if err != nil {
		return "", err
	}
	key, stamp, err := s.guard(ctx)
	if err != nil {
		return "", err
	}
	// _identity_params (105-127): company hosts get company KYC, all others individual.
	entityType := "individual"
	if businessType == "company" {
		entityType = "company"
	}
	var contact any // null when the contact email is empty
	if email != "" {
		contact = email
	}
	body, err := json.Marshal(map[string]any{
		"contact_email": contact,
		"display_name":  name,
		"dashboard":     "full",
		"identity": map[string]any{
			"country":          "CZ",
			"entity_type":      entityType,
			"business_details": map[string]any{"registered_name": name},
		},
		// _merchant_config (130-143) and _responsibilities (146-164).
		"configuration": map[string]any{
			"merchant": map[string]any{
				"capabilities": map[string]any{"card_payments": map[string]any{"requested": true}},
			},
		},
		"defaults": map[string]any{
			"currency": "czk",
			"responsibilities": map[string]any{
				"fees_collector":   "stripe",
				"losses_collector": "stripe",
			},
		},
	})
	if err != nil {
		return "", err
	}
	var acct map[string]any
	if err := s.call(ctx, key, http.MethodPost, "/v2/core/accounts", "application/json", body, &acct); err != nil {
		return "", err
	}
	id, _ := acct["id"].(string)
	if id == "" {
		return "", errors.New("stripe: account response has no id")
	}
	mode := s.mode()
	if _, err := s.Pool.Exec(ctx, stripeInsertSQL, owner, id, mode, stamp); err != nil {
		return "", err
	}
	if err := audit(ctx, s.Pool, stamp, "stripe_account_created", "acct="+id, owner); err != nil {
		return "", err
	}
	if err := mirrorAccount(ctx, s.Pool, acct, mode, stamp); err != nil {
		return "", err
	}
	return id, nil
}

// OnboardingLink is onboarding_link (299-312): the account, then a single-use
// v1 account link. The refresh URL regenerates; the return URL checks state.
func (s *StripeOnboarder) OnboardingLink(ctx context.Context, owner int64, baseURL string) (string, error) {
	id, err := s.accountOrCreate(ctx, owner)
	if err != nil {
		return "", err
	}
	key, _, err := s.guard(ctx)
	if err != nil {
		return "", err
	}
	form := url.Values{}
	form.Set("account", id)
	form.Set("refresh_url", baseURL+"/payments/connect/start")
	form.Set("return_url", baseURL+"/payments/connect/return")
	form.Set("type", "account_onboarding")
	var link map[string]any
	if err := s.call(ctx, key, http.MethodPost, "/v1/account_links",
		"application/x-www-form-urlencoded", []byte(form.Encode()), &link); err != nil {
		return "", err
	}
	u, _ := link["url"].(string)
	if u == "" {
		return "", errors.New("stripe: account link response has no url")
	}
	return u, nil
}

// HandleReturn is handle_return (315-326): re-retrieve the account and mirror it.
func (s *StripeOnboarder) HandleReturn(ctx context.Context, owner int64) error {
	id, err := s.existingAccount(ctx, owner)
	if err != nil {
		return err
	}
	if id == "" {
		return ErrNoAccount
	}
	key, stamp, err := s.guard(ctx)
	if err != nil {
		return err
	}
	var acct map[string]any
	if err := s.call(ctx, key, http.MethodGet, "/v1/accounts/"+url.PathEscape(id), "", nil, &acct); err != nil {
		return err
	}
	return mirrorAccount(ctx, s.Pool, acct, s.mode(), stamp)
}

var _ Onboarder = (*StripeOnboarder)(nil)
