// Package posthog is the Go port of App/app/posthog_sync.py: it sends host
// funnel stage events to PostHog Cloud EU /capture/ and records the last sent
// stage in user_account.posthog_stage. Host accounts only; no guest table is
// read. Failures log the account id and HTTP status only, never the payload.
package posthog

import (
	"bytes"
	"context"
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"time"
	_ "time/tzdata"

	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	// DefaultHost and DefaultAssetsHost are config.POSTHOG_HOST and POSTHOG_ASSETS_HOST defaults.
	DefaultHost       = "https://eu.i.posthog.com"
	DefaultAssetsHost = "https://eu-assets.i.posthog.com"

	captureTimeout = 3 * time.Second // posthog_sync._TIMEOUT
	maxRows        = 5000            // admin_funnel.MAX_ROWS
	funnelZone     = "Europe/Prague" // config.TIMEZONE
	eventNamespace = "6f1c5c6e-0b8e-4d55-9d43-4b1f0b7a3e37"
)

// stageKeys is admin_funnel.stages() in order: the furthest stage with a date is the host's stage.
var stageKeys = []string{
	"signed_up", "email_verified", "created", "first_login", "legal_accepted",
	"first_entity", "first_property", "first_calendar", "first_guest",
	"first_filing", "retained",
}

var filedStates = []string{"ok", "ok_duplicate", "partial"}

// Config is the PostHog part of the environment.
type Config struct {
	APIKey     string
	Host       string
	AssetsHost string
}

// ConfigFromEnv reads POSTHOG_PROJECT_API_KEY, POSTHOG_HOST and POSTHOG_ASSETS_HOST
// like App/app/config.py: trimmed, trailing slashes removed, defaults only when unset.
func ConfigFromEnv(lookup func(string) (string, bool)) Config {
	get := func(name, def string) string {
		v, ok := lookup(name)
		if !ok {
			v = def
		}
		return strings.TrimRight(strings.TrimSpace(v), "/")
	}
	key, _ := lookup("POSTHOG_PROJECT_API_KEY")
	return Config{
		APIKey:     strings.TrimSpace(key),
		Host:       get("POSTHOG_HOST", DefaultHost),
		AssetsHost: get("POSTHOG_ASSETS_HOST", DefaultAssetsHost),
	}
}

// httpsOrigin is analytics._https_origin: https://host[:port] of an absolute https URL, else "".
func httpsOrigin(raw string) string {
	u, err := url.Parse(raw)
	if err != nil || u.Scheme != "https" || u.Hostname() == "" {
		return ""
	}
	host := strings.ToLower(u.Hostname())
	if u.Port() != "" {
		host += ":" + u.Port()
	}
	return "https://" + host
}

// hostAllowed is analytics._host_allowed: https only, US PostHog hosts refused.
func hostAllowed(raw string) bool {
	origin := httpsOrigin(raw)
	if origin == "" {
		return false
	}
	return !strings.Contains(origin, "us.i.posthog.com") && !strings.Contains(origin, "us-assets.i.posthog.com")
}

// apiHost is analytics.enabled() plus tag()["api_host"]: the capture origin, or "" when off.
func apiHost(cfg Config) string {
	if cfg.APIKey == "" || !hostAllowed(cfg.Host) || !hostAllowed(cfg.AssetsHost) {
		return ""
	}
	return httpsOrigin(cfg.Host)
}

// Counts is the result of one Sync.
type Counts struct{ Sent, Skipped, Failed int }

type funnelRow struct {
	stage string
	dates map[string]string // stage key -> stored timestamp text; absent when empty
}

type account struct {
	id            int64
	email         string
	username      string
	displayName   string
	signupSource  string
	utmSource     string
	utmMedium     string
	utmCampaign   string
	posthogStage  string
	hasPosthogStg bool
}

type statusError struct{ status int }

func (e *statusError) Error() string { return fmt.Sprintf("posthog capture status %d", e.status) }

// Sync sends the pending funnel stage events. It returns a nil error when PostHog
// is off, and when single accounts fail (those are counted); an error means the
// funnel or account query failed or ctx ended. client may be nil; now is the clock.
func Sync(ctx context.Context, pool *pgxpool.Pool, cfg Config, client *http.Client, now time.Time) (Counts, error) {
	var counts Counts
	host := apiHost(cfg)
	if host == "" {
		return counts, nil
	}
	if client == nil {
		client = &http.Client{}
	}
	funnel, err := loadFunnel(ctx, pool, now)
	if err != nil {
		return counts, err
	}
	accounts, err := loadAccounts(ctx, pool)
	if err != nil {
		return counts, err
	}
	for _, a := range accounts {
		if err := ctx.Err(); err != nil {
			return counts, err
		}
		row, ok := funnel[a.id]
		if !ok {
			counts.Skipped++
			continue
		}
		var previous *string
		if a.hasPosthogStg {
			previous = &a.posthogStage
		}
		pending := stagesToSend(previous, row)
		if len(pending) == 0 {
			counts.Skipped++
			continue
		}
		failed := false
		for _, key := range pending {
			payload := map[string]any{
				"api_key":     cfg.APIKey,
				"event":       key,
				"distinct_id": fmt.Sprint(a.id),
				"properties": map[string]any{
					"$ip":            nil,
					"$geoip_disable": true,
					"$set":           personSet(a, key),
				},
				"uuid": eventUUID(a.id, key),
			}
			if ts := row.dates[key]; ts != "" {
				payload["timestamp"] = ts
			}
			if err := capture(ctx, client, host, payload); err != nil {
				status := 0
				if se, ok := err.(*statusError); ok {
					status = se.status
				}
				slog.Warn("posthog capture failed", "account", a.id, "status", status)
				failed = true
				break
			}
			counts.Sent++
			if _, err := pool.Exec(ctx, "UPDATE user_account SET posthog_stage = $1 WHERE id = $2", key, a.id); err != nil {
				slog.Warn("posthog stage update failed", "account", a.id)
				failed = true
				break
			}
		}
		if failed {
			counts.Failed++
		}
	}
	return counts, nil
}

// capture POSTs one event; a status of 400 or more is an error.
func capture(ctx context.Context, client *http.Client, host string, payload map[string]any) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	reqCtx, cancel := context.WithTimeout(ctx, captureTimeout)
	defer cancel()
	req, err := http.NewRequestWithContext(reqCtx, http.MethodPost, strings.TrimRight(host, "/")+"/capture/", bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 1<<16))
	if resp.StatusCode >= 400 {
		return &statusError{status: resp.StatusCode}
	}
	return nil
}

// stagesToSend is posthog_sync._stages_to_send: the stages after previous, up to
// and including the current one, that have a date.
func stagesToSend(previous *string, row funnelRow) []string {
	if row.stage == "" || !isStage(row.stage) {
		return nil
	}
	pastPrevious := previous == nil || !isStage(*previous)
	var result []string
	for _, key := range stageKeys {
		if !pastPrevious {
			if key == *previous {
				pastPrevious = true
			}
			continue
		}
		if row.dates[key] != "" {
			result = append(result, key)
		}
		if key == row.stage {
			break
		}
	}
	return result
}

func isStage(key string) bool {
	for _, k := range stageKeys {
		if k == key {
			return true
		}
	}
	return false
}

// personSet is posthog_sync._person_set (as called by sync: the account columns).
func personSet(a account, funnelStage string) map[string]any {
	props := map[string]any{"funnel_stage": funnelStage}
	email := a.email
	if email == "" && strings.Contains(a.username, "@") {
		email = a.username
	}
	if email != "" {
		props["email"] = email
	}
	if a.displayName != "" {
		props["workspace_name"] = a.displayName
	}
	switch a.signupSource {
	case "google", "meta", "none":
		props["signup_source"] = a.signupSource
	}
	for _, u := range []struct{ key, value string }{
		{"utm_source", a.utmSource}, {"utm_medium", a.utmMedium}, {"utm_campaign", a.utmCampaign},
	} {
		lower := strings.ToLower(u.value)
		if u.value != "" && !strings.Contains(lower, "gclid") && !strings.Contains(lower, "fbclid") {
			props[u.key] = u.value
		}
	}
	return props
}

// eventUUID is uuid.uuid5(namespace, "<account id>:<stage key>"): RFC 4122 version 5.
func eventUUID(accountID int64, stageKey string) string {
	ns, err := hex.DecodeString(strings.ReplaceAll(eventNamespace, "-", ""))
	if err != nil {
		panic("posthog: bad event namespace")
	}
	h := sha1.New()
	h.Write(ns)
	h.Write([]byte(fmt.Sprintf("%d:%s", accountID, stageKey)))
	sum := h.Sum(nil)[:16]
	sum[6] = sum[6]&0x0f | 0x50
	sum[8] = sum[8]&0x3f | 0x80
	x := hex.EncodeToString(sum)
	return x[0:8] + "-" + x[8:12] + "-" + x[12:16] + "-" + x[16:20] + "-" + x[20:32]
}

// monthStarts is admin_funnel._month_starts: UTC ISO bounds of the previous and
// current calendar month in Europe/Prague, in the stored form 2026-10-31T23:00:00+00:00.
func monthStarts(now time.Time) (previous, current string, err error) {
	loc, err := time.LoadLocation(funnelZone)
	if err != nil {
		return "", "", err
	}
	local := now.In(loc)
	cur := time.Date(local.Year(), local.Month(), 1, 0, 0, 0, 0, loc)
	prev := time.Date(local.Year(), local.Month()-1, 1, 0, 0, 0, 0, loc)
	utc := func(t time.Time) string { return t.UTC().Format("2006-01-02T15:04:05") + "+00:00" }
	return utc(prev), utc(cur), nil
}

// funnelSQL is admin_funnel._SQL reduced to the columns Sync reads (the dropped
// ones are not used by posthog_sync); placeholders: $1 previous month start,
// $2 current month start, $3-$5 filed states, $6 row cap.
const funnelSQL = `SELECT u.id, u.signup_at, u.email_verified_at, u.created_at,
COALESCE((SELECT MIN(au.at) FROM audit au WHERE au.owner_user_id = u.id
  AND au.action IN ('login', 'two_factor_login')), u.last_login_at) AS first_login_at,
(SELECT MIN(la.accepted_at) FROM legal_acceptance la WHERE la.user_account_id = u.id) AS legal_accepted_at,
(SELECT MIN(le.created_at) FROM legal_entity le WHERE le.owner_user_id = u.id) AS first_entity_at,
(SELECT MIN(a.created_at) FROM apartment a WHERE a.owner_user_id = u.id) AS first_property_at,
(SELECT MIN(f.created_at) FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id
  WHERE a.owner_user_id = u.id AND f.last_status = 'ok') AS first_calendar_at,
(SELECT MIN(r.registration_completed_at) FROM reservation r
  JOIN apartment a ON a.id = r.apartment_id
  WHERE a.owner_user_id = u.id AND r.registration_completed_at IS NOT NULL
  AND COALESCE(r.source, '') != 'demo') AS first_guest_at,
fs.first_filing_at, fs.last_filing_at,
COALESCE(fs.filings_previous, 0)::bigint AS filings_previous,
COALESCE(fs.filings_current, 0)::bigint AS filings_current
FROM user_account u
LEFT JOIN (
  SELECT a.owner_user_id,
  MIN(COALESCE(s.finished_at, s.created_at)) AS first_filing_at,
  MAX(COALESCE(s.finished_at, s.created_at)) AS last_filing_at,
  SUM(CASE WHEN s.created_at >= $1 AND s.created_at < $2 THEN 1 ELSE 0 END) AS filings_previous,
  SUM(CASE WHEN s.created_at >= $2 THEN 1 ELSE 0 END) AS filings_current
  FROM submission s JOIN apartment a ON a.id = s.apartment_id
  WHERE s.state IN ($3, $4, $5) GROUP BY a.owner_user_id
) fs ON fs.owner_user_id = u.id
WHERE u.role = 'host' ORDER BY u.created_at, u.id LIMIT $6`

// loadFunnel is admin_funnel.rows(): one funnelRow per host account id.
func loadFunnel(ctx context.Context, pool *pgxpool.Pool, now time.Time) (map[int64]funnelRow, error) {
	previous, current, err := monthStarts(now)
	if err != nil {
		return nil, err
	}
	rows, err := pool.Query(ctx, funnelSQL, previous, current, filedStates[0], filedStates[1], filedStates[2], maxRows)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[int64]funnelRow{}
	for rows.Next() {
		var id, filedPrevious, filedCurrent int64
		var signup, verified, created, login, legal, entity, property, calendar, guest, firstFiling, lastFiling *string
		if err := rows.Scan(&id, &signup, &verified, &created, &login, &legal, &entity, &property,
			&calendar, &guest, &firstFiling, &lastFiling, &filedPrevious, &filedCurrent); err != nil {
			return nil, err
		}
		var retained *string
		if filedPrevious != 0 && filedCurrent != 0 {
			retained = lastFiling
		}
		byStage := []*string{signup, verified, created, login, legal, entity, property, calendar, guest, firstFiling, retained}
		row := funnelRow{dates: map[string]string{}}
		for i, key := range stageKeys {
			if v := byStage[i]; v != nil && *v != "" {
				row.dates[key] = *v
				row.stage = key
			}
		}
		out[id] = row
	}
	return out, rows.Err()
}

func loadAccounts(ctx context.Context, pool *pgxpool.Pool) ([]account, error) {
	rows, err := pool.Query(ctx, `SELECT id, email, username, display_name, signup_utm_source,
signup_utm_medium, signup_utm_campaign, signup_source, posthog_stage
FROM user_account WHERE role = 'host' ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []account
	for rows.Next() {
		var a account
		var email, username, display, source, medium, campaign, signup, stage *string
		if err := rows.Scan(&a.id, &email, &username, &display, &source, &medium, &campaign, &signup, &stage); err != nil {
			return nil, err
		}
		a.email, a.username, a.displayName = deref(email), deref(username), deref(display)
		a.utmSource, a.utmMedium, a.utmCampaign, a.signupSource = deref(source), deref(medium), deref(campaign), deref(signup)
		if stage != nil {
			a.posthogStage, a.hasPosthogStg = *stage, true
		}
		out = append(out, a)
	}
	return out, rows.Err()
}

func deref(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
