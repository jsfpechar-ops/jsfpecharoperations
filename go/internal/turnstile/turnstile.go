// Package turnstile is the server-side Cloudflare Turnstile check of
// App/app/turnstile.py (brief 1501): the same skip conditions, the same
// siteverify request, timeout and fail-open budget, the same alert. It is a
// library only: no route is registered here.
//
// Three outcomes, as in Python: a failed challenge (missing, oversized,
// rejected or mis-scoped token) is a rejection; an unreachable verifier
// (transport error, timeout, a 4xx or 5xx status, a body that is not JSON)
// lets the visitor through at most five times per address and action in 15
// minutes and raises the turnstile_unavailable alert; anything else is a
// pass only when success is true and the action and hostname match.
package turnstile

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// VerifyURL is turnstile.VERIFY_URL.
const VerifyURL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

// DefaultSiteKey is config.TURNSTILE_SITE_KEY's default (the public key).
const DefaultSiteKey = "0x4AAAAAAE0LDM2eoIjssN00"

const (
	// Timeout is requests.post(..., timeout=10).
	Timeout = 10 * time.Second
	// maxToken is the 2048-character cap on the posted token.
	maxToken = 2048
	// unreachableScope, unreachableMax and unreachableWindow are
	// _UNREACHABLE_MAX_ATTEMPTS and _UNREACHABLE_WINDOW_SECONDS.
	unreachableScope  = "turnstile_unreachable"
	unreachableMax    = 5
	unreachableWindow = 15 * 60
	// maxBody bounds the siteverify answer read into memory.
	maxBody = 64 << 10
)

// Alert copy of _fail_open (English log copy; the card is rendered from the
// kind's notification.turnstile_unavailable.* keys).
const (
	alertMessage = "The security check could not be reached, so it was skipped."
	alertDetail  = "Cloudflare Turnstile did not answer. Guests were let through without the " +
		"check for a short while; the alert clears itself once verification works " +
		"again."
)

// Config is the Turnstile part of App/app/config.py.
type Config struct {
	Deployment string          // config.DEPLOYMENT: UBYHOST_DEPLOYMENT lower-cased, default "local"
	SiteKey    string          // TURNSTILE_SITE_KEY stripped, default DefaultSiteKey
	Secret     string          // TURNSTILE_SECRET stripped
	Hostnames  map[string]bool // TURNSTILE_HOSTNAMES: comma-separated, stripped, lower-cased
}

// FromEnv reads Config as config.py does at import.
func FromEnv(getenv func(string) string) Config {
	deployment := getenv("UBYHOST_DEPLOYMENT")
	if deployment == "" {
		deployment = "local"
	}
	siteKey := getenv("TURNSTILE_SITE_KEY")
	if siteKey == "" {
		siteKey = DefaultSiteKey
	}
	hosts := map[string]bool{}
	for _, v := range strings.Split(getenv("TURNSTILE_HOSTNAMES"), ",") {
		if h := strings.ToLower(pyStrip(v)); h != "" {
			hosts[h] = true
		}
	}
	return Config{
		Deployment: strings.ToLower(deployment),
		SiteKey:    pyStrip(siteKey),
		Secret:     pyStrip(getenv("TURNSTILE_SECRET")),
		Hostnames:  hosts,
	}
}

// Enabled is config.TURNSTILE_ENABLED: site key, secret and at least one
// hostname are set.
func (c Config) Enabled() bool {
	return c.SiteKey != "" && c.Secret != "" && len(c.Hostnames) > 0
}

// Required is turnstile.required(): production and Enabled. When it is
// false, Verify passes every request without a network call.
func (c Config) Required() bool {
	return c.Deployment == "production" && c.Enabled()
}

// Required is turnstile.required() for the process environment.
func Required(getenv func(string) string) bool { return FromEnv(getenv).Required() }

// PageSiteKey is the turnstile_site_key template global: the site key when
// Turnstile is Enabled (in any deployment), else "".
func PageSiteKey(getenv func(string) string) string {
	c := FromEnv(getenv)
	if c.Enabled() {
		return c.SiteKey
	}
	return ""
}

// Verifier redeems tokens. Pool and Getenv are required; the rest is for tests.
type Verifier struct {
	Pool   *pgxpool.Pool
	Getenv func(string) string
	// Client is the HTTP client; nil means one with Timeout.
	Client *http.Client
	// URL replaces VerifyURL (tests only).
	URL string
	// Now is the clock of the fail-open budget; nil means time.Now.
	Now func() time.Time
}

// errUnreachable marks the outcomes Python catches as RequestException or
// ValueError.
var errUnreachable = errors.New("turnstile: verifier unreachable")

// Verify is turnstile.verify(request, token, expected_action). token is the
// last cf-turnstile-response form value ("" when the field is missing). The
// error is for the outcomes that raise in Python (a reply that is JSON but
// not an object, or a database error in the fail-open path); the caller
// answers 500 then, as Python does.
func (v Verifier) Verify(ctx context.Context, r *http.Request, token, expectedAction string) (bool, error) {
	cfg := FromEnv(v.Getenv)
	if !cfg.Required() {
		return true, nil
	}
	if token == "" || utf8.RuneCountInString(token) > maxToken {
		return false, nil
	}
	result, err := v.siteverify(ctx, cfg.Secret, token, clientip.Host(r, v.Getenv))
	if errors.Is(err, errUnreachable) {
		log.Printf("turnstile: verification unavailable action=%s", expectedAction)
		return v.failOpen(ctx, r, expectedAction)
	}
	if err != nil {
		return false, err
	}
	return Accepted(result, expectedAction, cfg.Hostnames), nil
}

// siteverify is the requests.post of verify: the form fields secret,
// response and remoteip in that order, raise_for_status, then .json().
func (v Verifier) siteverify(ctx context.Context, secret, token, remoteIP string) (map[string]json.RawMessage, error) {
	body := "secret=" + url.QueryEscape(secret) + "&response=" + url.QueryEscape(token) +
		"&remoteip=" + url.QueryEscape(remoteIP)
	endpoint := v.URL
	if endpoint == "" {
		endpoint = VerifyURL
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(body))
	if err != nil {
		return nil, errUnreachable
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	client := v.Client
	if client == nil {
		client = &http.Client{Timeout: Timeout}
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, errUnreachable
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return nil, errUnreachable
	}
	raw, err := io.ReadAll(io.LimitReader(resp.Body, maxBody))
	if err != nil {
		return nil, errUnreachable
	}
	if !json.Valid(raw) {
		return nil, errUnreachable
	}
	var obj map[string]json.RawMessage
	dec := json.NewDecoder(bytes.NewReader(raw))
	if err := dec.Decode(&obj); err != nil || obj == nil {
		// Valid JSON that is not an object: result.get raises AttributeError.
		return nil, errors.New("turnstile: siteverify answer is not a JSON object")
	}
	return obj, nil
}

// Accepted is the final test of verify: success is exactly true, action
// equals expectedAction, and str(hostname).lower() is a configured hostname.
func Accepted(result map[string]json.RawMessage, expectedAction string, hostnames map[string]bool) bool {
	if string(bytes.TrimSpace(result["success"])) != "true" {
		return false
	}
	var action string
	if err := json.Unmarshal(result["action"], &action); err != nil || action != expectedAction {
		return false
	}
	return hostnames[strings.ToLower(pyStr(result["hostname"]))]
}

// pyStr is str(result.get("hostname", "")) for a JSON value: a string as it
// is, null as "None", true and false as "True" and "False", a missing key as
// "", anything else as its JSON text.
func pyStr(raw json.RawMessage) string {
	text := string(bytes.TrimSpace(raw))
	switch text {
	case "":
		return ""
	case "null":
		return "None"
	case "true":
		return "True"
	case "false":
		return "False"
	}
	var s string
	if err := json.Unmarshal(raw, &s); err == nil {
		return s
	}
	return text
}

// failOpen is _fail_open: raise the alert, then let the visitor through
// unless this address used up its budget for this action.
func (v Verifier) failOpen(ctx context.Context, r *http.Request, expectedAction string) (bool, error) {
	now := time.Now()
	if v.Now != nil {
		now = v.Now()
	}
	key := clientip.Key(r, v.Getenv, expectedAction)
	if err := ubyport.RaiseAlert(ctx, v.Pool, "warning", "turnstile_unavailable", alertMessage, alertDetail,
		"turnstile_unavailable:"+expectedAction, nil, nil, nil, nil); err != nil {
		return false, err
	}
	blocked, err := session.RateBlocked(ctx, v.Pool, unreachableScope, key, unreachableMax, unreachableWindow, now)
	if err != nil {
		return false, err
	}
	if blocked {
		log.Printf("turnstile: unreachable too often; refusing this attempt action=%s", expectedAction)
		return false, nil
	}
	if err := session.RateRecord(ctx, v.Pool, unreachableScope, key, now); err != nil {
		return false, err
	}
	return true, nil
}

// pyStrip is str.strip(): Unicode white space plus U+001C..U+001F.
func pyStrip(s string) string {
	return strings.TrimFunc(s, func(c rune) bool { return unicode.IsSpace(c) || (c >= 0x1c && c <= 0x1f) })
}
