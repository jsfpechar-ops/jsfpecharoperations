# 1144: Go port of the `posthog` job (funnel stages to PostHog Cloud EU)

Status: review
Depends on: 1133 (merged) | Base commit: main (current) | Branch: the orchestrator's branch (work on the current branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `go/internal/posthog`, a Go port of `App/app/posthog_sync.py`, and register it as job kind `posthog` in the Go service so it can run in the Go job queue when the owner adds `posthog` to `UBYHOST_GO_JOB_KINDS`. The default is unchanged: Python keeps running the job until the owner flips the env; no Python file changes and nothing is deleted.

## 2. Context

Rules: AGENTS.md rule 2 (privacy, new outbound request needs its reason in the PR), rule 4 (no new dependency: stdlib plus the `pgx` already in `go.mod`; `go.mod` and `go.sum` must not change), rule 5 (no schema change: `user_account.posthog_stage` exists, migration 0008).

**Outbound request reason (rule 2):** this is the same request Python makes today: one `POST https://eu.i.posthog.com/capture/` (PostHog Cloud EU, from `POSTHOG_HOST`) per host funnel stage event, 3 s timeout, no cookies, `$ip` null and `$geoip_disable` true. The body carries host account data only (account id as distinct id, funnel stage, e-mail or e-mail-like username, workspace name, signup source google/meta/none, UTM labels without click ids). No guest data, no new destination, no new field. Off unless `POSTHOG_PROJECT_API_KEY` is set and both PostHog hosts are https and not the US hosts.

**Python source of truth (read-only here):** `App/app/posthog_sync.py` (`sync`, `_stages_to_send`, `_person_set`, `_capture`), `App/app/admin_funnel.py` (`stages()`, `_SQL`, `rows()`, `_month_starts`), `App/app/analytics.py` (`enabled`, `tag`, `_https_origin`, `_host_allowed`), `App/app/config.py` (`POSTHOG_*`, `TIMEZONE = "Europe/Prague"`), `App/app/scheduler.py` (`_job_posthog`, interval 15 min).

**Behaviour that must match Python (the code in step 1 implements each; the tests pin them):**

1. Off, with no request and no DB read: key empty, or `POSTHOG_HOST` or `POSTHOG_ASSETS_HOST` not https, or containing `us.i.posthog.com` or `us-assets.i.posthog.com`. Capture origin = https origin of `POSTHOG_HOST`. Env values are trimmed and lose trailing `/`; the defaults apply only when the variable is unset (an empty `POSTHOG_HOST` means off, as in Python).
2. Funnel query: host accounts only, `ORDER BY created_at, id LIMIT 5000`, filed states `ok`, `ok_duplicate`, `partial`, demo reservations excluded, previous/current Prague-month bounds as UTC ISO text, retained = `last_filing_at` when the host filed in both months. The Go query drops only select columns Python never reads in this job (`username`, `display_name`, `active`, `last_login_at`, `signup_source`, `signup_source_present`, `first_police_at`, the `ad_click` subquery); every stage column and the stage rule are identical.
3. Per account (accounts query as Python, plus `ORDER BY id` for a stable order): the stages after `posthog_stage` up to the current stage that have a date; one POST each; after each success `UPDATE user_account SET posthog_stage = $1 WHERE id = $2`. A failure (status 400 or more, timeout, transport error, or the UPDATE failing) stops that account, counts `failed`, and the loop goes on to the next account. One account failing is not the job's error. Only a failing funnel or account query, or a cancelled context, returns an error. Logs carry the account id and HTTP status only, never e-mail or payload.
4. Person properties: `funnel_stage`; `email` (column, else the username when it contains `@`); `workspace_name` from `display_name`; `signup_source` only `google`/`meta`/`none`; `utm_source`/`utm_medium`/`utm_campaign` only when the value has no `gclid` or `fbclid`, any case. Python builds a `person_base` dict and passes it to `_person_set`; its keys are the column names, so the effective output equals reading the account columns, which is what Go does.
5. Event uuid = `uuid.uuid5(6f1c5c6e-0b8e-4d55-9d43-4b1f0b7a3e37, "<account id>:<stage key>")`, byte-identical to Python (pinned: `42:created` is `a51b963f-709b-582f-b689-11c358242436`, `7:first_filing` is `2d037069-eb48-533d-9117-897709d7e848`, both computed with Python while writing this brief). A switch between Python and Go therefore never double-counts: PostHog dedups on uuid.
6. Timestamp: **every date column is `TEXT` in Postgres** (baseline migration: `created_at text`, `signup_at text`, `audit.at text`, `submission.finished_at text`, and so on; Python stores `datetime.now(utc).replace(microsecond=0).isoformat()`, e.g. `2026-01-03T00:00:00+00:00`). Python passes the stored string through unchanged as `timestamp`; Go scans the same `TEXT` into `*string` and passes it through unchanged. No parsing, no reformatting, so the string is byte-identical to what Python sends. (Mixed legacy formats in old rows are sent verbatim by both.) Confidence: high; verified against `00001_baseline.sql`.

**Go queue:** `go/cmd/ubyhost-web/main.go` `goHandlers` maps a kind to `func(ctx) (int, error)`; the int is the rows written (here: events sent). `jobs` does claim, lease, retry, run log. `goIntervals` caps the retry backoff (Python interval is 15 min). A kind in `UBYHOST_GO_JOB_KINDS` must also be in `UBYHOST_JOB_QUEUE_KINDS` (scheduler.py refuses to start otherwise).

Known small differences (accepted): Go logs the summary only when something was sent or failed (Python also logs when only skipped); the JSON body is semantically identical but byte-different (Go escapes `<>&` as `<` etc., Python escapes non-ASCII; both are valid JSON that PostHog parses the same); redirects are followed by Go's default client (PostHog /capture/ does not redirect).

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/posthog/sync.go` | create | the port (step 1) |
| `go/internal/posthog/sync_test.go` | create | unit tests and one DB test (step 2) |
| `go/cmd/ubyhost-web/main.go` | edit | import, `goIntervals`, `posthog` handler (step 3) |
| `docs/ENVIRONMENT.md` | edit | the `UBYHOST_GO_JOB_KINDS` row only (step 4) |
| `docs/tasks/1144-go-posthog-job.md` | edit | `Status:` line only (step 5) |
| `docs/tasks/1144-report.md` | create | the report (§9) |

No other file may change. In particular `go.mod`, `go.sum`, `go/cmd/ubyhost-web/main_test.go` and everything under `App/`.

## 4. Steps

Work on the branch you are on. Do not create a branch, do not push, do not open a PR. After each step run its command, then `git add <that step's files> && git commit -m "1144 step k"`, nothing else staged. Go indentation is **tabs**; paste byte for byte. The code in steps 1 and 2 was compiled with `go vet` and is gofmt-clean at the time of writing; if `gofmt -l` still lists a file, run `gofmt -w` on that file only and mention it in the report.

0. Anchor check, from the repo root:
   `grep -cF '"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"' go/cmd/ubyhost-web/main.go; grep -cF '"submit": func(ctx context.Context) (int, error) {' go/cmd/ubyhost-web/main.go; grep -cF 'var goIntervals = map[string]int{"billing_snapshot": 24 * 60, "stripe_sweep": 24 * 60, "submit": 10, "ical": 60, "push": 1}' go/cmd/ubyhost-web/main.go; grep -cF 'Today `billing_snapshot`, `stripe_sweep`, `ical`, `push` and `submit`.' docs/ENVIRONMENT.md; ls go/internal/posthog docs/tasks/1144-report.md 2>&1 | tail -30`
   Expected: `1`, `1`, `1`, `1`, then two "No such file or directory". Anything else: STOP.

1. Create `go/internal/posthog/sync.go` with exactly this content. Then from `go/`: `gofmt -l internal/posthog; go vet ./internal/posthog/ 2>&1 | tail -30` (expected: no output; `go vet` also compiles the test file once step 2 exists, so run it again after step 2).

```go
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
```

2. Create `go/internal/posthog/sync_test.go` with exactly this content. Then from `go/`: `gofmt -l internal/posthog; go vet ./internal/posthog/ 2>&1 | tail -30` (expected: no output).

```go
package posthog

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Pinned from Python: uuid.uuid5(UUID('6f1c5c6e-0b8e-4d55-9d43-4b1f0b7a3e37'), '<id>:<stage>').
func TestEventUUIDMatchesPython(t *testing.T) {
	if got := eventUUID(42, "created"); got != "a51b963f-709b-582f-b689-11c358242436" {
		t.Errorf("eventUUID(42, created) = %s", got)
	}
	if got := eventUUID(7, "first_filing"); got != "2d037069-eb48-533d-9117-897709d7e848" {
		t.Errorf("eventUUID(7, first_filing) = %s", got)
	}
}

func TestApiHostOffAndOn(t *testing.T) {
	cases := []struct {
		name string
		cfg  Config
		want string
	}{
		{"on defaults", Config{"k", DefaultHost, DefaultAssetsHost}, "https://eu.i.posthog.com"},
		{"on with port", Config{"k", "https://ph.example.com:8443", DefaultAssetsHost}, "https://ph.example.com:8443"},
		{"no key", Config{"", DefaultHost, DefaultAssetsHost}, ""},
		{"http host", Config{"k", "http://eu.i.posthog.com", DefaultAssetsHost}, ""},
		{"http assets", Config{"k", DefaultHost, "http://eu-assets.i.posthog.com"}, ""},
		{"us host", Config{"k", "https://us.i.posthog.com", DefaultAssetsHost}, ""},
		{"us assets", Config{"k", DefaultHost, "https://us-assets.i.posthog.com"}, ""},
		{"empty host", Config{"k", "", DefaultAssetsHost}, ""},
	}
	for _, c := range cases {
		if got := apiHost(c.cfg); got != c.want {
			t.Errorf("%s: apiHost = %q, want %q", c.name, got, c.want)
		}
	}
}

func TestConfigFromEnvDefaultsOnlyWhenUnset(t *testing.T) {
	env := map[string]string{"POSTHOG_PROJECT_API_KEY": " k ", "POSTHOG_HOST": " https://h.example.com// "}
	lookup := func(n string) (string, bool) { v, ok := env[n]; return v, ok }
	want := Config{APIKey: "k", Host: "https://h.example.com", AssetsHost: DefaultAssetsHost}
	if got := ConfigFromEnv(lookup); got != want {
		t.Errorf("ConfigFromEnv = %+v, want %+v", got, want)
	}
	env["POSTHOG_HOST"] = ""
	if got := ConfigFromEnv(lookup); got.Host != "" {
		t.Errorf("empty POSTHOG_HOST must stay empty (off), got %q", got.Host)
	}
}

func TestStagesToSend(t *testing.T) {
	row := funnelRow{stage: "first_property", dates: map[string]string{
		"created": "2026-01-01T00:00:00+00:00", "first_login": "2026-01-02T00:00:00+00:00",
		"first_entity": "2026-01-03T00:00:00+00:00", "first_property": "2026-01-04T00:00:00+00:00",
	}}
	str := func(s string) *string { return &s }
	cases := []struct {
		name     string
		previous *string
		want     []string
	}{
		{"never sent", nil, []string{"created", "first_login", "first_entity", "first_property"}},
		{"unknown previous", str("nonsense"), []string{"created", "first_login", "first_entity", "first_property"}},
		{"after created", str("created"), []string{"first_login", "first_entity", "first_property"}},
		{"stage without date as previous", str("legal_accepted"), []string{"first_entity", "first_property"}},
		{"already current", str("first_property"), nil},
	}
	for _, c := range cases {
		if got := stagesToSend(c.previous, row); !reflect.DeepEqual(got, c.want) {
			t.Errorf("%s: got %v, want %v", c.name, got, c.want)
		}
	}
	if got := stagesToSend(nil, funnelRow{}); got != nil {
		t.Errorf("empty stage: got %v, want none", got)
	}
}

func TestPersonSet(t *testing.T) {
	a := account{id: 1, username: "host@example.com", displayName: "Villa Test", signupSource: "google",
		utmSource: "newsletter", utmMedium: "CPC-GCLID-1", utmCampaign: ""}
	want := map[string]any{
		"funnel_stage": "created", "email": "host@example.com", "workspace_name": "Villa Test",
		"signup_source": "google", "utm_source": "newsletter",
	}
	if got := personSet(a, "created"); !reflect.DeepEqual(got, want) {
		t.Errorf("personSet = %v, want %v", got, want)
	}
	b := account{id: 2, email: "real@example.com", username: "other@example.com", signupSource: "organic", utmCampaign: "xFBCLIDx"}
	if got := personSet(b, "first_login"); !reflect.DeepEqual(got, map[string]any{"funnel_stage": "first_login", "email": "real@example.com"}) {
		t.Errorf("personSet(b) = %v", got)
	}
	c := account{id: 3, username: "plainname"}
	if got := personSet(c, "created"); !reflect.DeepEqual(got, map[string]any{"funnel_stage": "created"}) {
		t.Errorf("personSet(c) = %v", got)
	}
}

func TestMonthStarts(t *testing.T) {
	prev, cur, err := monthStarts(time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC))
	if err != nil || prev != "2026-09-30T22:00:00+00:00" || cur != "2026-10-31T23:00:00+00:00" {
		t.Errorf("november: %s %s %v", prev, cur, err)
	}
	prev, cur, err = monthStarts(time.Date(2027, 1, 15, 10, 0, 0, 0, time.UTC))
	if err != nil || prev != "2026-11-30T23:00:00+00:00" || cur != "2026-12-31T23:00:00+00:00" {
		t.Errorf("january: %s %s %v", prev, cur, err)
	}
}

func TestCapturePayloadAndStatus(t *testing.T) {
	var mu sync.Mutex
	var gotPath, gotType string
	var gotBody map[string]any
	status := http.StatusOK
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		mu.Lock()
		defer mu.Unlock()
		gotPath, gotType = r.URL.Path, r.Header.Get("Content-Type")
		_ = json.Unmarshal(raw, &gotBody)
		w.WriteHeader(status)
	}))
	defer srv.Close()
	payload := map[string]any{
		"api_key": "k", "event": "created", "distinct_id": "42", "uuid": eventUUID(42, "created"),
		"timestamp":  "2026-01-01T00:00:00+00:00",
		"properties": map[string]any{"$ip": nil, "$geoip_disable": true, "$set": personSet(account{id: 42}, "created")},
	}
	if err := capture(context.Background(), srv.Client(), srv.URL, payload); err != nil {
		t.Fatal(err)
	}
	if gotPath != "/capture/" || gotType != "application/json" {
		t.Errorf("path %q type %q", gotPath, gotType)
	}
	props, _ := gotBody["properties"].(map[string]any)
	if gotBody["api_key"] != "k" || gotBody["event"] != "created" || gotBody["distinct_id"] != "42" ||
		gotBody["uuid"] != "a51b963f-709b-582f-b689-11c358242436" ||
		gotBody["timestamp"] != "2026-01-01T00:00:00+00:00" || props["$geoip_disable"] != true {
		t.Errorf("payload = %v", gotBody)
	}
	if v, has := props["$ip"]; !has || v != nil {
		t.Error("$ip must be present as null")
	}
	status = http.StatusInternalServerError
	err := capture(context.Background(), srv.Client(), srv.URL, payload)
	if se, ok := err.(*statusError); !ok || se.status != 500 {
		t.Errorf("500 gave %v, want statusError 500", err)
	}
}

func TestSyncOffMakesNoRequestAndNeedsNoDatabase(t *testing.T) {
	hit := false
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { hit = true }))
	defer srv.Close()
	for _, cfg := range []Config{
		{"", srv.URL, srv.URL}, {"k", "http://x.example", srv.URL}, {"k", "https://us.i.posthog.com", srv.URL},
	} {
		counts, err := Sync(context.Background(), nil, cfg, srv.Client(), time.Now())
		if err != nil || counts != (Counts{}) {
			t.Errorf("off: %+v %v", counts, err)
		}
	}
	if hit {
		t.Error("a request was made while PostHog is off")
	}
}

func TestSyncEndToEnd(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO user_account
		(id, username, password_hash, created_at, email, display_name, signup_source, signup_utm_source, signup_at, email_verified_at, posthog_stage) VALUES
		(1, 'one@example.com', 'x', '2026-01-03T00:00:00+00:00', NULL, 'Villa One', 'google', 'newsletter', '2026-01-01T00:00:00+00:00', '2026-01-02T00:00:00+00:00', NULL),
		(2, 'two', 'x', '2026-02-01T00:00:00+00:00', 'two@example.com', NULL, NULL, NULL, NULL, NULL, 'created'),
		(3, 'three', 'x', '2026-03-01T00:00:00+00:00', NULL, NULL, NULL, NULL, NULL, NULL, NULL)`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at, role) VALUES (4, 'boss', 'x', '2026-01-01T00:00:00+00:00', 'admin')`); err != nil {
		t.Fatal(err)
	}
	var mu sync.Mutex
	var events []string
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]any
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &body)
		mu.Lock()
		events = append(events, fmt.Sprintf("%v:%v:%v", body["distinct_id"], body["event"], body["timestamp"]))
		mu.Unlock()
		if body["distinct_id"] == "3" {
			w.WriteHeader(http.StatusBadGateway)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()
	cfg := Config{APIKey: "k", Host: srv.URL, AssetsHost: DefaultAssetsHost}
	now := time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC)
	counts, err := Sync(ctx, pool, cfg, srv.Client(), now)
	if err != nil {
		t.Fatal(err)
	}
	if counts != (Counts{Sent: 3, Skipped: 1, Failed: 1}) {
		t.Errorf("counts = %+v", counts)
	}
	sort.Strings(events)
	want := []string{
		"1:created:2026-01-03T00:00:00+00:00",
		"1:email_verified:2026-01-02T00:00:00+00:00",
		"1:signed_up:2026-01-01T00:00:00+00:00",
		"3:created:2026-03-01T00:00:00+00:00",
	}
	if !reflect.DeepEqual(events, want) {
		t.Errorf("events = %v, want %v", events, want)
	}
	stages := map[int64]*string{}
	rows, err := pool.Query(ctx, "SELECT id, posthog_stage FROM user_account ORDER BY id")
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var id int64
		var s *string
		if err := rows.Scan(&id, &s); err != nil {
			t.Fatal(err)
		}
		stages[id] = s
	}
	rows.Close()
	if stages[1] == nil || *stages[1] != "created" || stages[2] == nil || *stages[2] != "created" || stages[3] != nil || stages[4] != nil {
		t.Errorf("posthog_stage = %v %v %v %v", stages[1], stages[2], stages[3], stages[4])
	}
	events = nil
	counts, err = Sync(ctx, pool, cfg, srv.Client(), now)
	if err != nil || counts.Sent != 0 || counts.Failed != 1 || len(events) != 1 {
		t.Errorf("second run: %+v %v events=%v (only account 3 retries)", counts, err, events)
	}
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies
// the goose Up sections of App/migrations_pg and drops the database at the end.
// It skips when the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_posthog_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	applyMigrations(t, pool)
	return pool
}

func applyMigrations(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(context.Background(), up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
}
```

3. `go/cmd/ubyhost-web/main.go`.

   a. Replace (once)

```go
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
```

   with

```go
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/posthog"
```

   b. Replace (once)

```go
var goIntervals = map[string]int{"billing_snapshot": 24 * 60, "stripe_sweep": 24 * 60, "submit": 10, "ical": 60, "push": 1}
```

   with

```go
var goIntervals = map[string]int{"billing_snapshot": 24 * 60, "stripe_sweep": 24 * 60, "submit": 10, "ical": 60, "push": 1, "posthog": 15}
```

   c. Replace (once)

```go
		"submit": func(ctx context.Context) (int, error) {
```

   with

```go
		"posthog": func(ctx context.Context) (int, error) {
			counts, err := posthog.Sync(ctx, pool, posthog.ConfigFromEnv(os.LookupEnv), nil, time.Now())
			if counts.Sent > 0 || counts.Failed > 0 {
				slog.Info("posthog sync", "sent", counts.Sent, "skipped", counts.Skipped, "failed", counts.Failed)
			}
			return counts.Sent, err
		},
		"submit": func(ctx context.Context) (int, error) {
```

   Then from `go/`: `gofmt -l cmd/ubyhost-web; go build ./cmd/ubyhost-web 2>&1 | tail -30 && rm -f ubyhost-web` (expected: no output).

4. Docs.

   a. `docs/ENVIRONMENT.md`: in the `UBYHOST_GO_JOB_KINDS` row replace the text
   ``Today `billing_snapshot`, `stripe_sweep`, `ical`, `push` and `submit`.``
   with
   ``Today `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit` and `posthog` (the Go service reads the same `POSTHOG_*` variables from `.env`).``

   Then from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5` (expected: passes).

5. Set the `Status:` line of this brief to `review` and write the report (§9). Commit `1144 step 5`.

## 5. Do not touch

`App/` (the Python job stays and keeps running by default), `go.mod`, `go.sum`, `go/cmd/ubyhost-web/main_test.go`, every other file in `go/internal/`, `.env` files, secrets, deploy files. AGENTS.md rules 1 to 5 above. Do not add `posthog` to any default env value or compose default: the switch stays the owner's.

## 6. Commands

From `go/`:

```bash
test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/posthog/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
```

Expected: two `ok` lines. `TestSyncEndToEnd` skips locally (no `UBYHOST_TEST_DATABASE_URL`) and runs in CI against Postgres; the other posthog tests run locally.

```bash
go test ./internal/posthog/ -run 'TestEventUUIDMatchesPython|TestApiHostOffAndOn|TestStagesToSend|TestPersonSet|TestMonthStarts|TestCapturePayloadAndStatus|TestSyncOff|TestConfigFromEnv' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
```

Expected: eight `--- PASS` lines and `ok`.

From the repo root:

```bash
python3 scripts/context_lint.py 2>&1 | tail -5
```

Expected: passes. Test-map has no Go row yet; the first command above is the check, and no Python test runs because no `App/` file changes. Do not edit `docs/context/test-map.md` (another brief owns it).

## 7. Acceptance

- [ ] The first §6 command prints two `ok` lines.
- [ ] `git diff --stat main..HEAD -- go/go.mod go/go.sum App | tail -5` prints nothing (no dependency, no Python change).
- [ ] `grep -c '"posthog"' go/cmd/ubyhost-web/main.go` prints `2` (interval and handler).
- [ ] `grep -rn 'email\|Email' go/internal/posthog/sync.go | grep -i 'slog' | tail -5` prints nothing (no e-mail in a log line).
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat "$(git log -1 --format=%H --grep=^Brief.1144)"..HEAD | tail -30` lists only the §3 paths.
- [ ] Five commits "1144 step 1" to "1144 step 5"; nothing pushed.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in step 0 gives another count, or a "replace" block is not found exactly once;
- a test fails twice, or `go vet` fails on the pasted code (do not rewrite it: report the error);
- `TestSyncEndToEnd` is run locally against a database and fails: report the SQL error text (the funnel SQL could not be executed by the brief writer, only compiled; CI is the first real run);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed, or `go.mod`/`go.sum` changes;
- a file outside §3 needs a change;
- you doubt the timestamp rule (§2 item 6: the stored `TEXT` is sent unchanged);
- a step is unclear;
- you need push, merge, a PR, secrets, SSH or deploy (the orchestrator or owner does that).

## 9. Report

Write `docs/tasks/1144-report.md` (600 tokens at most) with: 1. `git diff --stat "$(git log -1 --format=%H --grep=^Brief.1144)"..HEAD` (last 10 lines); 2. each §6 command with the last 5 lines of its output; 3. §7 ticked; 4. deviations; 5. questions; 6. follow-up: add a test-map row "Go module (`go/`)" with the first §6 command, in a later brief (not this one); 7. owner steps left (expected: the owner steps below, after merge and deploy).

## Risk list (for the reviewer)

Read the full diff of `go/internal/posthog/sync.go` and `go/cmd/ubyhost-web/main.go` (the test file only skim). Focus:

- **No double counting on a switch:** `eventUUID` is byte-identical to Python's `uuid5` (two pinned values from Python in the test); the stage rule in `stagesToSend` is a literal port; `posthog_stage` is updated after each success.
- **Privacy / outbound:** only `{host}/capture/` is called; the payload has no guest field; `$ip` null and `$geoip_disable` true; log lines carry account id and status only; the off switch covers a missing key, non-https and US hosts.
- **Timestamp:** sent verbatim from `TEXT` columns, like Python (§2 item 6). Residual uncertainty: none known; old rows with odd formats are sent verbatim by both.
- **SQL not executed by the brief writer:** `funnelSQL` was adapted from `admin_funnel._SQL` with `$n` placeholders and compiled, but only `TestSyncEndToEnd` in CI runs it. The first CI run is the check; a SQL error there is a real finding.
- Failure semantics: one account failing stops only that account; a failed funnel or account query fails the job (the queue retries with backoff).
- `go.mod` and `go.sum` unchanged; Python job and defaults untouched.

## Owner steps

1. Review the draft PR when the orchestrator says it is green; merge it with `scripts/merge-pr-on-green.sh`. Merging deploys the Go binary but changes nothing yet: Python still runs `posthog`.
2. To switch (only after the deploy is healthy), on the server edit `/opt/ubyhost/deploy/lightsail/.env` and add `posthog` to both lists, keeping what is already there:

```bash
UBYHOST_JOB_QUEUE_KINDS=<existing kinds>,posthog
UBYHOST_GO_JOB_KINDS=<existing kinds>,posthog
```

   `POSTHOG_PROJECT_API_KEY` stays as it is in the same `.env`; the Go service reads it from there.
3. Restart the stack from `/opt/ubyhost/deploy/lightsail`:

```bash
docker compose up -d
```

4. Check one run (the job runs every 15 minutes; a first run after the switch sends nothing new when Python already sent everything, so look for the run, not for events):

```bash
docker compose logs --since 30m ubyhost-go 2>&1 | grep -i posthog | tail -20
```

   Expected: no `posthog capture failed` lines. In PostHog, a new host's `created` event appears once, not twice. (If the service is not called `ubyhost-go`, run `docker compose ps` and use the Go service's name.)
5. Rollback: remove `posthog` from both lists in `.env` and run `docker compose up -d` again. Python resumes the job; event uuids match, so nothing is sent twice.
