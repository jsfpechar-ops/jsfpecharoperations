# 1158: Go port of the `meta_capi` job (CompleteRegistration events to the Meta Conversions API)

Status: review
Depends on: 1152 (merged) | Base commit: main (current) | Branch: the orchestrator's branch (work on the current branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `go/internal/metacapi`, a Go port of `App/app/meta_capi.py` `send_pending`, and register it as job kind `meta_capi` in the Go service so it can run in the Go job queue when the owner adds `meta_capi` to `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS`. The default is unchanged: Python keeps running the job until the owner flips the env; no `App/` file changes and nothing is deleted.

## 2. Context

Rules: AGENTS.md rule 2 (privacy, new outbound request needs its reason in the PR), rule 4 (no new dependency: stdlib plus the `pgx` already in `go.mod`; `go.mod` and `go.sum` must not change), rule 5 (no schema change: every `ad_click` column used exists, migrations 0003 and 0004, `00001_baseline.sql`).

**Outbound request reason (rule 2):** this is the same request Python makes today: one form-encoded `POST https://graph.facebook.com/<UBYHOST_META_GRAPH_VERSION, default v26.0>/<UBYHOST_META_DATASET_ID>/events` per queued sign-up event (Meta Conversions API), 10 s timeout, no cookies, access token in the form body and never in the URL. The body carries one `CompleteRegistration` event: `event_name`, `event_time` (the unix time the account verified its e-mail), `event_id` (the random id Python stored at enqueue), `action_source` `website`, `event_source_url` (`<UBYHOST_PUBLIC_BASE_URL>/signup`, no query string), `opt_out` true, and `user_data` with `fbc` (the Meta click id stored with the visitor's opt-in consent) and `client_user_agent` when stored. Nothing is hashed because no e-mail, phone, name or IP address is sent. No guest data, no new destination, no new field. Off (no request, no database access) unless both `UBYHOST_META_DATASET_ID` and `UBYHOST_META_ACCESS_TOKEN` are set; `UBYHOST_META_TEST_EVENT_CODE`, when set, is added to the form as in Python.

**Python source of truth (read-only here):** `App/app/meta_capi.py`, `App/app/config.py`, `App/app/scheduler.py` (`_job_meta_capi`, interval 10 min), `App/app/signup.py`.

**What stays in Python (no change, safe next to the Go job):** `enqueue` (writes `send_state = pending`, `event_id`, `next_attempt_at` when the e-mail is confirmed, called from `signup.activate`), `signup.withdraw_consent`, and `signup.purge`, which runs inside the scheduler's `retention` job (not in `meta_capi`) and calls `expire_unsendable` and blanks `fbc` 7 days after upload. Go does not run `retention`, so those keep working unchanged. `expire_unsendable` is also part of `send_pending`, so Go runs it too, with the same SQL; both are idempotent.

**Behaviour that must match Python (the code in step 1 implements each; the tests pin them):**

1. Off: `UBYHOST_META_DATASET_ID` or `UBYHOST_META_ACCESS_TOKEN` empty (values trimmed) gives a zero summary, no request, no database call. `UBYHOST_META_GRAPH_VERSION` defaults to `v26.0` only when the variable is unset (set but empty stays empty, as `os.environ.get`). The Graph host is a code constant, never read from the environment, so no env value can redirect the token.
2. Shared state, so a switch in either direction never double-sends: Go uses the same `ad_click` columns and the same compare-and-set as Python (`send_state` pending, sending, sent, failed, expired; `attempts`, `next_attempt_at`, `last_error`, `uploaded_at`). Python generates `event_id` (`secrets.token_hex(16)`) at enqueue; Go only reads it and sends it unchanged, so every retry, and any resend after a crash between the HTTP call and the write, carries the same `event_id` and Meta deduplicates. Go never generates an id.
3. Order per run: hand back rows stuck in `sending` for 10 minutes (`next_attempt_at < now - 10 min`), run `expire_unsendable` (pending events whose account verified more than 7 days minus 1 hour ago become `expired` with `last_error` "older than Meta's 7-day event window"), then take at most 20 due rows (`platform = 'meta' AND send_state = 'pending' AND next_attempt_at <= now ORDER BY id`). Each row is claimed with `UPDATE ... WHERE id = ? AND send_state = 'pending' AND withdrawn_at IS NULL AND fbc IS NOT NULL` (one row affected, else skipped), then read back with `user_account.email_verified_at`, then posted with no transaction open, then written.
4. Answer: success is HTTP 200 and `events_received >= 1`: `send_state = sent`, `attempts + 1`, `last_error` NULL, `uploaded_at` = now. A retry (network error, HTTP 5xx, 429, `error.is_transient`, or `error.code` in 1, 2, 4, 17, 32, 341, 613, 80004; or a configuration code 10, 190, 200, 803, which also raises the alert `meta_capi_config`) sets `pending` and `next_attempt_at = now + min(6 h, 60 s * 2^min(attempts, 8))`, or `failed` when `attempts` reaches 8. Anything else is `failed` at once with no new `next_attempt_at`. `last_error` is `HTTP <status>[, code <code>][: <message first 200 characters>]`, cut to 400 characters, or `network: Timeout` / `network: ConnectionError`. The alert is `ubyport.RaiseAlert(warning, "meta_capi_config", dedupe key "meta_capi_config", params {"error": detail})`.
5. Payload bytes: `data` is `json.dumps([event], separators=(",", ":"))` with `ensure_ascii`; Go reproduces the key order (`event_name`, `event_time`, `event_id`, `action_source`, `event_source_url`, `opt_out`, `user_data{fbc, client_user_agent}`), compact separators, no HTML escaping and every non-ASCII character as lower-case `\uXXXX` (surrogate pairs above U+FFFF), so the bytes are identical. The form also carries `access_token` and optionally `test_event_code`; Pinned with Python-computed strings in `TestEventJSONMatchesPython`.
6. Timestamps: every date column is `TEXT` (baseline: `email_verified_at text`, `next_attempt_at text`, `uploaded_at text`). Python writes `datetime.now(utc).replace(microsecond=0).isoformat()` (`2026-11-12T10:00:00+00:00`); Go writes the same form (`iso`, and `ubyport.UTCNow` for `uploaded_at`). Rows are compared as text, as Python does. `event_time` is the unix int of `email_verified_at` parsed like `datetime.fromisoformat(s.replace("Z", "+00:00"))` with a missing zone read as UTC; pinned for six spellings (`1767225600`, from Python). An unreadable or NULL `email_verified_at` makes Python raise (the job fails and the claimed row waits in `sending` for the 10 minute hand-back); Go returns an error the same way.
7. Logs: row id, attempt and HTTP status only. Go does not log Meta's error text. No e-mail, token, `fbc`, user agent or payload in any log, error or alert; transport errors are never printed (a Go `url.Error` carries the URL). The token is also replaced by `[redacted]` in `last_error` and in the alert detail, in case Meta echoes it.
8. Failure isolation: one event failing is counted, not returned. Only a database error, an unreadable `email_verified_at`, or a cancelled context returns an error (queue backoff). A failing alert write is logged and the retry still recorded (Python would raise).

**Go queue:** `go/cmd/ubyhost-web/main.go` `goHandlers` maps a kind to `func(ctx) (int, error)`; the int is the rows written (here: events sent). `jobs` does claim, lease, retry, run log. `goIntervals` caps the retry backoff (Python interval is 10 min). A kind in `UBYHOST_GO_JOB_KINDS` must also be in `UBYHOST_JOB_QUEUE_KINDS` (scheduler.py refuses to start otherwise).

Accepted differences: a non-object answer body counts as no `events_received` (Python raises); the `network:` detail is Go's class, not Python's exception name.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/metacapi/send.go` | create | the port (step 1) |
| `go/internal/metacapi/send_test.go` | create | unit tests and one DB test (step 2) |
| `go/cmd/ubyhost-web/main.go` | edit | import, `goIntervals`, `meta_capi` handler (step 3) |
| `docs/ENVIRONMENT.md` | edit | the `UBYHOST_GO_JOB_KINDS` row only (step 4) |
| `docs/tasks/1158-go-meta-capi-job.md` | edit | `Status:` line only (step 5) |
| `docs/tasks/1158-report.md` | create | the report (§9) |

No other file may change. In particular `go.mod`, `go.sum`, `go/cmd/ubyhost-web/main_test.go` and everything under `App/`.

## 4. Steps

Work on the branch you are on. Do not create a branch, do not push, do not open a PR. After each step run its command, then `git add <that step's files> && git commit -m "1158 step k"`, nothing else staged. Go indentation is **tabs**; paste byte for byte. The code in steps 1 and 2 was compiled with `go vet`, is gofmt-clean, and its tests passed (the DB test against a local Postgres 16) at the time of writing; if `gofmt -l` still lists a file, run `gofmt -w` on that file only and mention it in the report.

0. Anchor check, from the repo root:
   `grep -cF '"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"' go/cmd/ubyhost-web/main.go; grep -cF '"submit": func(ctx context.Context) (int, error) {' go/cmd/ubyhost-web/main.go; grep -cF 'var goIntervals = map[string]int{"billing_snapshot": 24 * 60, "stripe_sweep": 24 * 60, "submit": 10, "ical": 60, "push": 1, "posthog": 15}' go/cmd/ubyhost-web/main.go; grep -cF 'Today `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit` and `posthog` (the Go service reads the same `POSTHOG_*` variables from `.env`).' docs/ENVIRONMENT.md; ls go/internal/metacapi docs/tasks/1158-report.md 2>&1 | tail -30`
   Expected: `1`, `1`, `1`, `1`, then two "No such file or directory". Anything else: STOP.

1. Create `go/internal/metacapi/send.go` with exactly this content. Then from `go/`: `gofmt -l internal/metacapi; go vet ./internal/metacapi/ 2>&1 | tail -30` (expected: no output; `go vet` also compiles the test file once step 2 exists, so run it again after step 2).

```go
// Package metacapi is the Go port of App/app/meta_capi.py send_pending: it posts
// the queued sign-up event (CompleteRegistration) of each ad_click row to the
// Meta Conversions API and records the answer in the same ad_click columns
// Python uses (send_state, attempts, next_attempt_at, last_error, uploaded_at).
// The row is claimed with a compare-and-set, the HTTP call runs with no
// transaction open, and the answer is written afterwards. event_id is written
// by Python at enqueue time and only read here, so Meta deduplicates across a
// switch. Logs carry the row id, attempt and HTTP status only, never the access
// token, fbc, user agent or payload.
package metacapi

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const (
	// DefaultGraphHost is meta_capi.GRAPH_HOST.
	DefaultGraphHost = "https://graph.facebook.com"
	// DefaultGraphVersion is config.META_GRAPH_VERSION's default.
	DefaultGraphVersion = "v26.0"

	eventName      = "CompleteRegistration" // meta_capi.EVENT_NAME
	actionSource   = "website"              // meta_capi.ACTION_SOURCE
	requestTimeout = 10 * time.Second       // meta_capi.TIMEOUT_SECONDS
	maxAttempts    = 8                      // meta_capi.MAX_ATTEMPTS
	// sendWindow is meta_capi.SEND_WINDOW: 7 days minus 1 hour.
	sendWindow = 7*24*time.Hour - time.Hour
	// staleSending is meta_capi.STALE_SENDING.
	staleSending = 10 * time.Minute
	batchLimit   = 20 // send_pending(limit=20)

	statePending = "pending"
	stateSending = "sending"
	stateSent    = "sent"
	stateFailed  = "failed"
	stateExpired = "expired"
)

// Meta Graph API error codes, as in meta_capi.
var (
	transientCodes = map[int]bool{1: true, 2: true, 4: true, 17: true, 32: true, 341: true, 613: true, 80004: true}
	configCodes    = map[int]bool{10: true, 190: true, 200: true, 803: true}
)

// Config is the Meta part of the environment (config.META_* and PUBLIC_BASE_URL).
type Config struct {
	DatasetID     string
	AccessToken   string
	TestEventCode string
	GraphVersion  string
	PublicBase    string
	// GraphHost is never read from the environment; tests point it at a local server.
	GraphHost string
}

// ConfigFromEnv reads UBYHOST_META_DATASET_ID, UBYHOST_META_ACCESS_TOKEN,
// UBYHOST_META_TEST_EVENT_CODE, UBYHOST_META_GRAPH_VERSION (default only when
// unset, like os.environ.get) and UBYHOST_PUBLIC_BASE_URL. Values are trimmed.
func ConfigFromEnv(lookup func(string) (string, bool)) Config {
	get := func(name string) string {
		v, _ := lookup(name)
		return strings.TrimSpace(v)
	}
	version := DefaultGraphVersion
	if v, ok := lookup("UBYHOST_META_GRAPH_VERSION"); ok {
		version = strings.TrimSpace(v)
	}
	return Config{
		DatasetID:     get("UBYHOST_META_DATASET_ID"),
		AccessToken:   get("UBYHOST_META_ACCESS_TOKEN"),
		TestEventCode: get("UBYHOST_META_TEST_EVENT_CODE"),
		GraphVersion:  version,
		PublicBase: hostweb.PublicBase(func(name string) string {
			v, _ := lookup(name)
			return v
		}),
		GraphHost: DefaultGraphHost,
	}
}

// Enabled is config.meta_capi_enabled(): both the dataset and the token are set.
func (c Config) Enabled() bool { return c.DatasetID != "" && c.AccessToken != "" }

func (c Config) endpoint() string {
	host := c.GraphHost
	if host == "" {
		host = DefaultGraphHost
	}
	return host + "/" + c.GraphVersion + "/" + c.DatasetID + "/events"
}

// Summary is the result of one Send (meta_capi.send_pending's dict).
type Summary struct{ Sent, Retry, Failed, Expired int }

// iso is meta_capi._iso: UTC, whole seconds, +00:00.
func iso(t time.Time) string {
	return t.UTC().Format("2006-01-02T15:04:05") + "+00:00"
}

var parseLayouts = []string{
	"2006-01-02T15:04:05Z07:00",
	"2006-01-02 15:04:05Z07:00",
	"2006-01-02T15:04:05",
	"2006-01-02 15:04:05",
	"2006-01-02",
}

// parseStored is meta_capi._parse: datetime.fromisoformat with "Z" read as
// +00:00 and a missing zone read as UTC.
func parseStored(stored string) (time.Time, error) {
	s := strings.ReplaceAll(stored, "Z", "+00:00")
	for _, layout := range parseLayouts {
		if t, err := time.Parse(layout, s); err == nil {
			return t, nil
		}
	}
	return time.Time{}, errors.New("unreadable email_verified_at")
}

// retryDelay is meta_capi._delay.
func retryDelay(attempts int) time.Duration {
	if attempts > 8 {
		attempts = 8
	}
	seconds := 60 * (1 << attempts)
	if seconds > 6*60*60 {
		seconds = 6 * 60 * 60
	}
	return time.Duration(seconds) * time.Second
}

// truncate keeps the first n characters (Python slices characters, not bytes).
func truncate(s string, n int) string {
	if utf8.RuneCountInString(s) <= n {
		return s
	}
	return string([]rune(s)[:n])
}

type userData struct {
	FBC             string `json:"fbc"`
	ClientUserAgent string `json:"client_user_agent,omitempty"`
}

// event has meta_capi.build_payload's key order, so the JSON bytes match Python's.
type event struct {
	EventName      string   `json:"event_name"`
	EventTime      int64    `json:"event_time"`
	EventID        *string  `json:"event_id"`
	ActionSource   string   `json:"action_source"`
	EventSourceURL string   `json:"event_source_url"`
	OptOut         bool     `json:"opt_out"`
	UserData       userData `json:"user_data"`
}

type row struct {
	id              int64
	fbc             string
	eventID         *string
	attempts        int
	clientUserAgent string
	emailVerifiedAt string
}

// eventJSON is json.dumps([event], separators=(",", ":")) with ensure_ascii:
// compact, no HTML escaping, every non-ASCII character as \uXXXX (lower case).
func eventJSON(ev event) (string, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode([]event{ev}); err != nil {
		return "", err
	}
	raw := strings.TrimRight(buf.String(), "\n")
	var out strings.Builder
	for _, r := range raw {
		switch {
		case r < 0x80:
			out.WriteRune(r)
		case r < 0x10000:
			fmt.Fprintf(&out, `\u%04x`, r)
		default:
			r -= 0x10000
			fmt.Fprintf(&out, `\u%04x\u%04x`, 0xd800+(r>>10), 0xdc00+(r&0x3ff))
		}
	}
	return out.String(), nil
}

func buildEvent(cfg Config, r row) (event, error) {
	verified, err := parseStored(r.emailVerifiedAt)
	if err != nil {
		return event{}, err
	}
	return event{
		EventName:      eventName,
		EventTime:      verified.Unix(),
		EventID:        r.eventID,
		ActionSource:   actionSource,
		EventSourceURL: cfg.PublicBase + "/signup",
		OptOut:         true,
		UserData:       userData{FBC: r.fbc, ClientUserAgent: r.clientUserAgent},
	}, nil
}

// outcome of one HTTP call. retry and fatal carry the detail stored in last_error.
type outcome struct {
	ok     bool
	retry  bool
	config bool // a configuration error: raise the alert, then retry
	status int
	detail string
}

// intCode reads a whole JSON number as an int (Python's `code in {1, 2, ...}`).
func intCode(v any) (int, bool) {
	if c, ok := v.(float64); ok && c == float64(int(c)) {
		return int(c), true
	}
	return 0, false
}

func eventsReceived(v any) int {
	switch n := v.(type) {
	case float64:
		return int(n)
	case string:
		i, _ := strconv.Atoi(strings.TrimSpace(n))
		return i
	}
	return 0
}

// post is meta_capi._post: one form-encoded POST, the token in the body (never
// the URL). It never returns the token in its detail.
func post(ctx context.Context, client *http.Client, cfg Config, data string) outcome {
	form := url.Values{}
	form.Set("data", data)
	form.Set("access_token", cfg.AccessToken)
	if cfg.TestEventCode != "" {
		form.Set("test_event_code", cfg.TestEventCode)
	}
	reqCtx, cancel := context.WithTimeout(ctx, requestTimeout)
	defer cancel()
	req, err := http.NewRequestWithContext(reqCtx, http.MethodPost, cfg.endpoint(), strings.NewReader(form.Encode()))
	if err != nil {
		return outcome{retry: true, detail: "network: RequestException"}
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := client.Do(req)
	if err != nil {
		// Never print err: it can carry the request URL.
		var netErr net.Error
		if errors.As(err, &netErr) && netErr.Timeout() || errors.Is(err, context.DeadlineExceeded) {
			return outcome{retry: true, detail: "network: Timeout"}
		}
		return outcome{retry: true, detail: "network: ConnectionError"}
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	var answer map[string]any
	if json.Unmarshal(raw, &answer) != nil {
		answer = nil
	}
	if resp.StatusCode == http.StatusOK && eventsReceived(answer["events_received"]) >= 1 {
		return outcome{ok: true, status: resp.StatusCode}
	}
	errObj, _ := answer["error"].(map[string]any)
	code, hasCode := intCode(errObj["code"])
	summary := fmt.Sprintf("HTTP %d", resp.StatusCode)
	if rawCode, present := errObj["code"]; present && rawCode != nil {
		if hasCode {
			summary += ", code " + strconv.Itoa(code)
		} else {
			summary += ", code " + fmt.Sprint(rawCode)
		}
	}
	message := ""
	if m, ok := errObj["message"].(string); ok {
		message = truncate(m, 200)
	}
	detail := summary
	if message != "" {
		detail = summary + ": " + message
	}
	// Meta's message must never echo the token into last_error or an alert.
	detail = strings.ReplaceAll(detail, cfg.AccessToken, "[redacted]")
	transient, _ := errObj["is_transient"].(bool)
	switch {
	case resp.StatusCode >= 500 || resp.StatusCode == 429 || transient || (hasCode && transientCodes[code]):
		return outcome{retry: true, status: resp.StatusCode, detail: detail}
	case hasCode && configCodes[code]:
		return outcome{retry: true, config: true, status: resp.StatusCode, detail: detail}
	}
	return outcome{status: resp.StatusCode, detail: detail}
}

// expireUnsendable is meta_capi.expire_unsendable: pending events whose account
// verified its e-mail before the cutoff become expired. Returns the row count.
func expireUnsendable(ctx context.Context, pool *pgxpool.Pool, now time.Time) (int, error) {
	tag, err := pool.Exec(ctx,
		`UPDATE ad_click SET send_state = $1, last_error = $2
		 WHERE platform = 'meta' AND send_state = $3 AND user_account_id IN (
		   SELECT id FROM user_account WHERE email_verified_at < $4)`,
		stateExpired, "older than Meta's 7-day event window", statePending, iso(now.Add(-sendWindow)))
	if err != nil {
		return 0, err
	}
	return int(tag.RowsAffected()), nil
}

// Send is meta_capi.send_pending. It returns a zero Summary and no error when
// Meta is off (no request, no database access). A single event failing is
// counted, not returned; an error means a database call failed, an unreadable
// email_verified_at (as in Python the claimed row then waits for the 10 minute
// stale hand-back), or ctx ended. client may be nil.
func Send(ctx context.Context, pool *pgxpool.Pool, cfg Config, client *http.Client, now time.Time) (Summary, error) {
	var sum Summary
	if !cfg.Enabled() {
		return sum, nil
	}
	if client == nil {
		client = &http.Client{}
	}
	if _, err := pool.Exec(ctx,
		`UPDATE ad_click SET send_state = $1 WHERE send_state = $2 AND next_attempt_at < $3`,
		statePending, stateSending, iso(now.Add(-staleSending))); err != nil {
		return sum, err
	}
	expired, err := expireUnsendable(ctx, pool, now)
	if err != nil {
		return sum, err
	}
	sum.Expired = expired
	ids, err := dueIDs(ctx, pool, now)
	if err != nil {
		return sum, err
	}
	for _, id := range ids {
		if err := ctx.Err(); err != nil {
			return sum, err
		}
		// Claim, then read what was claimed: a withdrawal in between leaves nothing to send.
		tag, err := pool.Exec(ctx,
			`UPDATE ad_click SET send_state = $1, next_attempt_at = $2
			 WHERE id = $3 AND send_state = $4 AND withdrawn_at IS NULL AND fbc IS NOT NULL`,
			stateSending, iso(now), id, statePending)
		if err != nil {
			return sum, err
		}
		if tag.RowsAffected() != 1 {
			continue
		}
		r, err := loadRow(ctx, pool, id)
		if err != nil {
			return sum, err
		}
		attempts := r.attempts + 1
		ev, err := buildEvent(cfg, r)
		if err != nil {
			return sum, err
		}
		data, err := eventJSON(ev)
		if err != nil {
			return sum, err
		}
		out := post(ctx, client, cfg, data)
		switch {
		case out.ok:
			if _, err := pool.Exec(ctx,
				`UPDATE ad_click SET send_state = $1, attempts = $2, last_error = NULL, uploaded_at = $3
				 WHERE id = $4 AND send_state = $5`,
				stateSent, attempts, ubyport.UTCNow(), id, stateSending); err != nil {
				return sum, err
			}
			sum.Sent++
		case out.retry:
			if out.config {
				if err := ubyport.RaiseAlert(ctx, pool, "warning", "meta_capi_config",
					"Meta Conversions API refused the access token or dataset.", out.detail, "meta_capi_config",
					nil, nil, nil, ubyport.AlertParams{"error": out.detail}); err != nil {
					slog.Warn("meta capi alert not written", "id", id)
				}
			}
			terminal := attempts >= maxAttempts
			state := statePending
			if terminal {
				state = stateFailed
			}
			if _, err := pool.Exec(ctx,
				`UPDATE ad_click SET send_state = $1, attempts = $2, last_error = $3, next_attempt_at = $4
				 WHERE id = $5 AND send_state = $6`,
				state, attempts, truncate(out.detail, 400), iso(now.Add(retryDelay(attempts))), id, stateSending); err != nil {
				return sum, err
			}
			if terminal {
				sum.Failed++
			} else {
				sum.Retry++
			}
			slog.Warn("meta event not sent", "id", id, "attempt", attempts, "status", out.status)
		default:
			if _, err := pool.Exec(ctx,
				`UPDATE ad_click SET send_state = $1, attempts = $2, last_error = $3
				 WHERE id = $4 AND send_state = $5`,
				stateFailed, attempts, truncate(out.detail, 400), id, stateSending); err != nil {
				return sum, err
			}
			sum.Failed++
			slog.Warn("meta event refused", "id", id, "attempt", attempts, "status", out.status)
		}
	}
	return sum, nil
}

func dueIDs(ctx context.Context, pool *pgxpool.Pool, now time.Time) ([]int64, error) {
	rows, err := pool.Query(ctx,
		`SELECT c.id FROM ad_click c WHERE c.platform = 'meta' AND c.send_state = $1
		 AND c.next_attempt_at <= $2 ORDER BY c.id LIMIT $3`,
		statePending, iso(now), batchLimit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

func loadRow(ctx context.Context, pool *pgxpool.Pool, id int64) (row, error) {
	var r row
	var fbc, agent, verified *string
	err := pool.QueryRow(ctx,
		`SELECT c.id, c.fbc, c.event_id, c.attempts, c.client_user_agent, u.email_verified_at
		 FROM ad_click c JOIN user_account u ON u.id = c.user_account_id WHERE c.id = $1`, id).
		Scan(&r.id, &fbc, &r.eventID, &r.attempts, &agent, &verified)
	if err != nil {
		return r, err
	}
	if fbc != nil {
		r.fbc = *fbc
	}
	if agent != nil {
		r.clientUserAgent = *agent
	}
	if verified != nil {
		r.emailVerifiedAt = *verified
	}
	return r, nil
}
```

2. Create `go/internal/metacapi/send_test.go` with exactly this content. Then from `go/`: `gofmt -l internal/metacapi; go vet ./internal/metacapi/ 2>&1 | tail -30; go test ./internal/metacapi/ -count=1 2>&1 | tail -30` (expected: `ok`; `TestSendEndToEnd` skips without `UBYHOST_TEST_DATABASE_URL`).

```go
package metacapi

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func str(s string) *string { return &s }

// Pinned from Python: json.dumps([event], separators=(",", ":")) of the same values.
func TestEventJSONMatchesPython(t *testing.T) {
	cfg := Config{PublicBase: "https://app.example.com"}
	cases := []struct {
		name string
		r    row
		want string
	}{
		{
			"null event id, awkward user agent",
			row{fbc: "fb.1.1.x", eventID: nil, emailVerifiedAt: "2026-01-01T00:00:00+00:00",
				clientUserAgent: "A\"B\\C\n\t\U0001F600 <i>&"},
			`[{"event_name":"CompleteRegistration","event_time":1767225600,"event_id":null,"action_source":"website","event_source_url":"https://app.example.com/signup","opt_out":true,"user_data":{"fbc":"fb.1.1.x","client_user_agent":"A\"B\\C\n\t\ud83d\ude00 <i>&"}}]`,
		},
		{
			"no user agent",
			row{fbc: "fb.1.1.x", eventID: str("abc"), emailVerifiedAt: "2026-01-01T02:00:00+02:00"},
			`[{"event_name":"CompleteRegistration","event_time":1767225600,"event_id":"abc","action_source":"website","event_source_url":"https://app.example.com/signup","opt_out":true,"user_data":{"fbc":"fb.1.1.x"}}]`,
		},
	}
	for _, c := range cases {
		ev, err := buildEvent(cfg, c.r)
		if err != nil {
			t.Fatal(c.name, err)
		}
		got, err := eventJSON(ev)
		if err != nil {
			t.Fatal(c.name, err)
		}
		if got != c.want {
			t.Errorf("%s:\n got %s\nwant %s", c.name, got, c.want)
		}
	}
}

// Pinned from Python: int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()), naive read as UTC.
func TestParseStoredMatchesPython(t *testing.T) {
	for _, s := range []string{
		"2026-01-01T00:00:00+00:00", "2026-01-01T02:00:00+02:00", "2026-01-01T00:00:00Z",
		"2026-01-01T00:00:00", "2026-01-01 00:00:00", "2026-01-01T00:00:00.000000+00:00",
	} {
		got, err := parseStored(s)
		if err != nil || got.Unix() != 1767225600 {
			t.Errorf("parseStored(%q) = %v, %v; want 1767225600", s, got.Unix(), err)
		}
	}
	if _, err := parseStored(""); err == nil {
		t.Error("an empty email_verified_at must be an error, as in Python")
	}
}

func TestRetryDelayAndIso(t *testing.T) {
	// Python: min(6 * 60 * 60, 60 * 2 ** min(attempts, 8)).
	for attempts, want := range map[int]time.Duration{1: 120 * time.Second, 2: 240 * time.Second, 8: 15360 * time.Second, 9: 15360 * time.Second} {
		if got := retryDelay(attempts); got != want {
			t.Errorf("retryDelay(%d) = %v, want %v", attempts, got, want)
		}
	}
	if got := iso(time.Date(2026, 11, 12, 10, 0, 5, 999, time.FixedZone("x", 3600))); got != "2026-11-12T09:00:05+00:00" {
		t.Errorf("iso = %s", got)
	}
	if got := truncate("ééé", 2); got != "éé" {
		t.Errorf("truncate counts characters, got %q", got)
	}
}

func TestConfigFromEnvAndEnabled(t *testing.T) {
	env := map[string]string{
		"UBYHOST_META_DATASET_ID": " 123 ", "UBYHOST_META_ACCESS_TOKEN": " tok ",
		"UBYHOST_PUBLIC_BASE_URL": "https://app.example.com/",
	}
	lookup := func(n string) (string, bool) { v, ok := env[n]; return v, ok }
	got := ConfigFromEnv(lookup)
	want := Config{DatasetID: "123", AccessToken: "tok", GraphVersion: "v26.0", PublicBase: "https://app.example.com", GraphHost: DefaultGraphHost}
	if got != want || !got.Enabled() {
		t.Errorf("ConfigFromEnv = %+v", got)
	}
	if got.endpoint() != "https://graph.facebook.com/v26.0/123/events" {
		t.Errorf("endpoint = %s", got.endpoint())
	}
	env["UBYHOST_META_GRAPH_VERSION"] = ""
	if ConfigFromEnv(lookup).GraphVersion != "" {
		t.Error("an empty UBYHOST_META_GRAPH_VERSION stays empty, as in Python")
	}
	for _, drop := range []string{"UBYHOST_META_DATASET_ID", "UBYHOST_META_ACCESS_TOKEN"} {
		saved := env[drop]
		delete(env, drop)
		if ConfigFromEnv(lookup).Enabled() {
			t.Errorf("must be off without %s", drop)
		}
		env[drop] = saved
	}
}

func TestSendOffMakesNoRequestAndNeedsNoDatabase(t *testing.T) {
	called := false
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { called = true }))
	defer srv.Close()
	// A nil pool would panic on any database call.
	sum, err := Send(context.Background(), nil, Config{DatasetID: "123", GraphHost: srv.URL, GraphVersion: "v26.0"}, nil, time.Now())
	if err != nil || sum != (Summary{}) || called {
		t.Errorf("sum=%+v err=%v called=%v", sum, err, called)
	}
}

func TestPostOutcomes(t *testing.T) {
	const token = "SECRET-TOKEN"
	cases := []struct {
		name       string
		status     int
		body       string
		wantOK     bool
		wantRetry  bool
		wantConfig bool
		wantDetail string
	}{
		{"sent", 200, `{"events_received":1}`, true, false, false, ""},
		{"zero received", 200, `{"events_received":0}`, false, false, false, "HTTP 200"},
		{"server error", 500, `oops`, false, true, false, "HTTP 500"},
		{"rate limited", 429, `{}`, false, true, false, "HTTP 429"},
		{"transient flag", 400, `{"error":{"code":100,"is_transient":true,"message":"later"}}`, false, true, false, "HTTP 400, code 100: later"},
		{"transient code", 400, `{"error":{"code":4,"message":"slow down"}}`, false, true, false, "HTTP 400, code 4: slow down"},
		{"config code, token echoed", 400, `{"error":{"code":190,"message":"bad ` + token + ` here"}}`, false, true, true, "HTTP 400, code 190: bad [redacted] here"},
		{"fatal", 400, `{"error":{"code":100,"message":"Invalid parameter"}}`, false, false, false, "HTTP 400, code 100: Invalid parameter"},
		{"fatal without body", 404, ``, false, false, false, "HTTP 404"},
	}
	for _, c := range cases {
		var gotPath, gotQuery, gotType string
		var form map[string][]string
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			gotPath, gotQuery, gotType = r.URL.Path, r.URL.RawQuery, r.Header.Get("Content-Type")
			_ = r.ParseForm()
			form = r.PostForm
			w.WriteHeader(c.status)
			_, _ = w.Write([]byte(c.body))
		}))
		cfg := Config{DatasetID: "123", AccessToken: token, TestEventCode: "TEST1", GraphVersion: "v26.0", GraphHost: srv.URL}
		out := post(context.Background(), srv.Client(), cfg, `[{"x":1}]`)
		srv.Close()
		if out.ok != c.wantOK || out.retry != c.wantRetry || out.config != c.wantConfig || out.detail != c.wantDetail {
			t.Errorf("%s: %+v", c.name, out)
		}
		if gotPath != "/v26.0/123/events" || gotQuery != "" || gotType != "application/x-www-form-urlencoded" {
			t.Errorf("%s: path=%q query=%q type=%q (the token must not be in the URL)", c.name, gotPath, gotQuery, gotType)
		}
		if form["data"][0] != `[{"x":1}]` || form["access_token"][0] != token || form["test_event_code"][0] != "TEST1" {
			t.Errorf("%s: form = %v", c.name, form)
		}
	}
	// A transport error is a retry and its detail names no URL and no token.
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	cfg := Config{DatasetID: "123", AccessToken: token, GraphVersion: "v26.0", GraphHost: srv.URL}
	srv.Close()
	out := post(context.Background(), http.DefaultClient, cfg, `[]`)
	if !out.retry || out.detail != "network: ConnectionError" || strings.Contains(out.detail, token) {
		t.Errorf("transport error: %+v", out)
	}
}

func TestSendEndToEnd(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC)
	fresh := "2026-11-11T00:00:00+00:00" // verified yesterday: inside the 7-day window
	old := "2026-11-01T00:00:00+00:00"   // verified 11 days ago: outside it
	if _, err := pool.Exec(ctx, `INSERT INTO consent_texts (id, version, purpose, lang, text, text_sha256, created_at) VALUES (1, 'v1', 'meta', 'en', 't', 'h', '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at, email_verified_at) VALUES
		(1, 'a', 'x', $1, $1), (2, 'b', 'x', $1, $1), (3, 'c', 'x', $1, $1), (4, 'd', 'x', $2, $2),
		(5, 'e', 'x', $1, $1), (6, 'f', 'x', $1, $1)`, fresh, old); err != nil {
		t.Fatal(err)
	}
	// 1 sends, 2 is refused by Meta (retry), 3 is refused for good, 4 is too old,
	// 5 withdrew, 6 is not due yet.
	if _, err := pool.Exec(ctx, `INSERT INTO ad_click
		(id, user_account_id, platform, clicked_at, consent_text_id, consented_at, created_at, fbc, event_id, send_state, attempts, next_attempt_at, withdrawn_at, client_user_agent) VALUES
		(1, 1, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.one', 'evt-one', 'pending', 2, '2026-11-12T09:00:00+00:00', NULL, 'UA one'),
		(2, 2, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.two', 'evt-two', 'pending', 0, '2026-11-12T09:00:00+00:00', NULL, NULL),
		(3, 3, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.three', 'evt-three', 'pending', 0, '2026-11-12T09:00:00+00:00', NULL, NULL),
		(4, 4, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.four', 'evt-four', 'pending', 0, '2026-11-12T09:00:00+00:00', NULL, NULL),
		(5, 5, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.five', 'evt-five', 'pending', 0, '2026-11-12T09:00:00+00:00', '2026-11-12T08:00:00+00:00', NULL),
		(6, 6, 'meta', 'c', 1, 'c', 'c', 'fb.1.1.six', 'evt-six', 'pending', 0, '2026-11-12T11:00:00+00:00', NULL, NULL)`); err != nil {
		t.Fatal(err)
	}
	var mu sync.Mutex
	var sent []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = r.ParseForm()
		data := r.PostForm.Get("data")
		mu.Lock()
		sent = append(sent, data)
		mu.Unlock()
		switch {
		case strings.Contains(data, "evt-two"):
			w.WriteHeader(http.StatusServiceUnavailable)
		case strings.Contains(data, "evt-three"):
			w.WriteHeader(http.StatusBadRequest)
			_, _ = w.Write([]byte(`{"error":{"code":100,"message":"Invalid parameter"}}`))
		default:
			_, _ = w.Write([]byte(`{"events_received":1}`))
		}
	}))
	defer srv.Close()
	cfg := Config{DatasetID: "123", AccessToken: "tok", GraphVersion: "v26.0", PublicBase: "https://app.example.com", GraphHost: srv.URL}
	sum, err := Send(ctx, pool, cfg, srv.Client(), now)
	if err != nil {
		t.Fatal(err)
	}
	if sum != (Summary{Sent: 1, Retry: 1, Failed: 1, Expired: 1}) {
		t.Errorf("summary = %+v", sum)
	}
	sort.Strings(sent)
	wantOne := `[{"event_name":"CompleteRegistration","event_time":1794355200,"event_id":"evt-one","action_source":"website","event_source_url":"https://app.example.com/signup","opt_out":true,"user_data":{"fbc":"fb.1.1.one","client_user_agent":"UA one"}}]`
	if len(sent) != 3 || !contains(sent, wantOne) {
		t.Errorf("sent = %v", sent)
	}
	type state struct {
		State    string
		Attempts int
		Err      *string
		Next     *string
		Uploaded *string
	}
	got := map[int]state{}
	rows, err := pool.Query(ctx, "SELECT id, send_state, attempts, last_error, next_attempt_at, uploaded_at FROM ad_click ORDER BY id")
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var id int
		var s state
		if err := rows.Scan(&id, &s.State, &s.Attempts, &s.Err, &s.Next, &s.Uploaded); err != nil {
			t.Fatal(err)
		}
		got[id] = s
	}
	rows.Close()
	if s := got[1]; s.State != "sent" || s.Attempts != 3 || s.Err != nil || s.Uploaded == nil {
		t.Errorf("row 1 = %+v", s)
	}
	// Retry: attempts 1, delay 120 s from now.
	if s := got[2]; s.State != "pending" || s.Attempts != 1 || s.Err == nil || *s.Err != "HTTP 503" || s.Next == nil || *s.Next != "2026-11-12T10:02:00+00:00" {
		t.Errorf("row 2 = %+v", s)
	}
	if s := got[3]; s.State != "failed" || s.Attempts != 1 || s.Err == nil || *s.Err != "HTTP 400, code 100: Invalid parameter" {
		t.Errorf("row 3 = %+v", s)
	}
	if s := got[4]; s.State != "expired" || s.Err == nil || *s.Err != "older than Meta's 7-day event window" || s.Attempts != 0 {
		t.Errorf("row 4 = %+v", s)
	}
	if got[5].State != "pending" || got[5].Attempts != 0 || got[6].State != "pending" || got[6].Attempts != 0 {
		t.Errorf("rows 5 and 6 must be untouched: %+v %+v", got[5], got[6])
	}
	// A second run later: row 2 is due again and is retried, nothing is sent twice.
	sent = nil
	later := now.Add(3 * time.Minute)
	if _, err := Send(ctx, pool, cfg, srv.Client(), later); err != nil {
		t.Fatal(err)
	}
	if len(sent) != 1 || !strings.Contains(sent[0], "evt-two") {
		t.Errorf("second run sent %v (only row 2 is due)", sent)
	}
	// A claim whose worker died is handed back after 10 minutes and sent once.
	if _, err := pool.Exec(ctx, `UPDATE ad_click SET send_state = 'sending', next_attempt_at = '2026-11-12T09:00:00+00:00' WHERE id = 6`); err != nil {
		t.Fatal(err)
	}
	sent = nil
	if _, err := Send(ctx, pool, cfg, srv.Client(), now.Add(2*time.Hour)); err != nil {
		t.Fatal(err)
	}
	resent := 0
	for _, data := range sent {
		if strings.Contains(data, "evt-six") {
			resent++
		}
	}
	if resent != 1 {
		t.Errorf("the stale claim must be handed back and sent once, got %d in %v", resent, sent)
	}
}

func contains(list []string, want string) bool {
	for _, s := range list {
		if s == want {
			return true
		}
	}
	return false
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
	name := fmt.Sprintf("ubyhost_go_metacapi_%d", time.Now().UnixNano())
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
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
```

   with

```go
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/metacapi"
```

   b. Replace (once)

```go
var goIntervals = map[string]int{"billing_snapshot": 24 * 60, "stripe_sweep": 24 * 60, "submit": 10, "ical": 60, "push": 1, "posthog": 15}
```

   with

```go
var goIntervals = map[string]int{"billing_snapshot": 24 * 60, "stripe_sweep": 24 * 60, "submit": 10, "ical": 60, "push": 1, "posthog": 15, "meta_capi": 10}
```

   c. Replace (once)

```go
		"submit": func(ctx context.Context) (int, error) {
```

   with

```go
		"meta_capi": func(ctx context.Context) (int, error) {
			sum, err := metacapi.Send(ctx, pool, metacapi.ConfigFromEnv(os.LookupEnv), nil, time.Now())
			if sum != (metacapi.Summary{}) {
				slog.Info("meta conversions", "sent", sum.Sent, "retry", sum.Retry, "failed", sum.Failed, "expired", sum.Expired)
			}
			return sum.Sent, err
		},
		"submit": func(ctx context.Context) (int, error) {
```

   Then from `go/`: `gofmt -l cmd/ubyhost-web; go build ./cmd/ubyhost-web 2>&1 | tail -30 && rm -f ubyhost-web` (expected: no output).

4. Docs.

   a. `docs/ENVIRONMENT.md`: in the `UBYHOST_GO_JOB_KINDS` row replace the text
   ``Today `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit` and `posthog` (the Go service reads the same `POSTHOG_*` variables from `.env`).``
   with
   ``Today `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit`, `posthog` and `meta_capi` (the Go service reads the same `POSTHOG_*` and `UBYHOST_META_*` variables from `.env`).``

   Then from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -5` (expected: passes).

5. Set the `Status:` line of this brief to `review` and write the report (§9). Commit `1158 step 5`.

## 5. Do not touch

`App/` (the Python job stays and keeps running by default; `enqueue`, `withdraw_consent` and `purge` stay Python), `go.mod`, `go.sum`, `go/cmd/ubyhost-web/main_test.go`, every other file in `go/internal/`, `.env` files, secrets, deploy files. AGENTS.md rules 1 to 5 above. Do not add `meta_capi` to any default env value or compose default: the switch stays the owner's.

## 6. Commands

From `go/`:

```bash
test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/metacapi/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
```

Expected: two `ok` lines. `TestSendEndToEnd` skips locally (no `UBYHOST_TEST_DATABASE_URL`) and runs in CI against Postgres; the other metacapi tests run locally.

```bash
go test ./internal/metacapi/ -run 'TestEventJSONMatchesPython|TestParseStoredMatchesPython|TestRetryDelayAndIso|TestConfigFromEnvAndEnabled|TestSendOffMakesNoRequestAndNeedsNoDatabase|TestPostOutcomes' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
```

Expected: six `--- PASS` lines and `ok`.

From the repo root:

```bash
python3 scripts/context_lint.py 2>&1 | tail -5
```

Expected: passes. Test-map has no Go row yet; the first command above is the check, and no Python test runs because no `App/` file changes. Do not edit `docs/context/test-map.md` (another brief owns it).

## 7. Acceptance

- [ ] The first §6 command prints two `ok` lines.
- [ ] `git diff --stat main..HEAD -- go/go.mod go/go.sum App | tail -5` prints nothing (no dependency, no Python change).
- [ ] `grep -c '"meta_capi"' go/cmd/ubyhost-web/main.go` prints `2` (interval and handler).
- [ ] `grep -n 'slog\.' go/internal/metacapi/send.go | grep -i 'token\|fbc\|email\|agent\|detail\|err)' | tail -5` prints nothing (no secret, identifier or error text in a log line).
- [ ] `grep -n 'RawQuery\|?access_token' go/internal/metacapi/send.go | tail -3` prints nothing (token only in the form body).
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] `git diff --stat "$(git log -1 --format=%H --grep=^Brief.1158)"..HEAD | tail -30` lists only the §3 paths.
- [ ] Five commits "1158 step 1" to "1158 step 5"; nothing pushed.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in step 0 gives another count, or a "replace" block is not found exactly once;
- a test fails twice, or `go vet` fails on the pasted code (do not rewrite it: report the error);
- `TestSendEndToEnd` fails against a database: report the SQL error;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed, or `go.mod`/`go.sum` changes;
- a file outside §3 needs a change;
- a step is unclear;
- you need push, merge, a PR, secrets, SSH or deploy (the orchestrator or owner does that).

## 9. Report

Write `docs/tasks/1158-report.md` (600 tokens at most) with: 1. `git diff --stat "$(git log -1 --format=%H --grep=^Brief.1158)"..HEAD` (last 10 lines); 2. each §6 command with the last 5 lines of its output; 3. §7 ticked; 4. deviations; 5. questions; 6. follow-up: a test-map row for the Go module is owed by another brief (do not edit test-map or status here); 7. owner steps left (expected: the owner steps below, after merge and deploy).

## Risk list (for the reviewer)

Read the full diff of `go/internal/metacapi/send.go` and `go/cmd/ubyhost-web/main.go`. Focus:

- **No double send on a switch or rollback:** claim is the same compare-and-set on `send_state`; `event_id` is only read (Python wrote it at enqueue), never generated; the stale hand-back (10 min) and the 8-attempt limit match Python; Meta deduplicates a crash-resend on the same `event_id`.
- **Privacy / outbound:** only `<graph host>/<version>/<dataset>/events` is called, the host is a code constant; the payload is `fbc`, optional user agent, times, ids, page URL, `opt_out` true; no hashing is needed or done because no e-mail, phone or IP is sent; the token is in the form body, not the URL, and is redacted from `last_error` and the alert; log lines carry row id, attempt and status only; `last_error` holds only Meta's code and first 200 characters of its message.
- **Payload bytes:** `eventJSON` reproduces Python's `json.dumps` (ensure_ascii, compact, key order); two Python-computed strings pin it (quote, backslash, control characters, `<>&`, astral character).
- **SQL run by the brief writer** against a local Postgres 16 (`TestSendEndToEnd` passed); CI is the second run.
- `metacapi` imports `ubyport` for `RaiseAlert` and `UTCNow` (already used by other jobs); no import cycle. `go.mod` and `go.sum` unchanged; Python job, `enqueue`, `withdraw_consent`, `purge` and defaults untouched.

## Owner steps

1. Review the draft PR when the orchestrator says it is green; merge it with `scripts/merge-pr-on-green.sh`. Merging deploys the Go binary but changes nothing yet: Python still runs `meta_capi`.
2. To switch (only after the deploy is healthy, and only if Meta is on: `UBYHOST_META_DATASET_ID` and `UBYHOST_META_ACCESS_TOKEN` are set), on the server edit `/opt/ubyhost/deploy/lightsail/.env` and add `meta_capi` to both lists, keeping what is already there:

```bash
UBYHOST_JOB_QUEUE_KINDS=<existing kinds>,meta_capi
UBYHOST_GO_JOB_KINDS=<existing kinds>,meta_capi
```

   The `UBYHOST_META_*` variables stay in the same `.env`; the Go service reads them from there (if it does not, the job is "off" and sends nothing).
3. Restart the stack from `/opt/ubyhost/deploy/lightsail`:

```bash
docker compose up -d
```

4. Check one run (the job runs every 10 minutes; with nothing pending there is nothing to see, so look for errors, not events). A visitor who signs up with a Meta click and the Meta box ticked, then confirms the e-mail, should show a `CompleteRegistration` in Meta Events Manager once, not twice:

```bash
docker compose logs --since 30m ubyhost-go 2>&1 | grep -i 'meta' | tail -20
```

   Expected: no `meta event not sent` or `meta event refused` lines. (If the service is not called `ubyhost-go`, run `docker compose ps` and use the Go service's name.)
5. Rollback: remove `meta_capi` from both lists in `.env` and run `docker compose up -d` again. Python resumes the job from the same `ad_click` rows; `event_id` is the same, so nothing is sent twice.
