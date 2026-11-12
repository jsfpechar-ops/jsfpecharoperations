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
