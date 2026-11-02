// Package pushsend is the Go port of App/app/push.py delivery: the outbox drain,
// the test alert and the server's VAPID key. The routes and the scheduler job
// are wired elsewhere.
package pushsend

import (
	"context"
	"crypto/ecdsa"
	"crypto/rand"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/webpush"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the keys in i18n_keys.txt, generated from host_i18n.py by
// App/scripts/go_host_i18n.py.
var catalog = hostweb.Load(catalogJSON)

const (
	testKind     = "test"
	testURL      = "/settings#settings-group-phone"
	vapidSetting = "web_push_vapid_private"
	supportEmail = "support@ubyhost.com" // config.SUPPORT_EMAIL
	dailyCap     = 12
	ttlSeconds   = 24 * 3600
	claimMinutes = 10
	maxFailures  = 5
	sendTimeout  = 10 * time.Second
)

// retryMinutes are the waits after the 1st, 2nd, ... failed try (push.py RETRY_MINUTES).
var retryMinutes = []int{1, 5, 15, 60}

// pushHosts are the push services browsers subscribe with (push.py PUSH_HOST_SUFFIXES).
var pushHosts = []string{
	"fcm.googleapis.com",
	"push.services.mozilla.com",
	"push.apple.com",
	"notify.windows.com",
}

// errBadKey means the stored VAPID setting decrypts but is not a usable key.
var errBadKey = errors.New("pushsend: stored VAPID key is unusable")

var defaultClient = &http.Client{
	Timeout: sendTimeout,
	CheckRedirect: func(*http.Request, []*http.Request) error {
		return http.ErrUseLastResponse
	},
}

// Sender delivers queued web push alerts. Getenv, Now, Client and AllowEndpoint
// may be nil: os.Getenv, time.Now, a client that does not follow redirects, and
// the push-service suffix check.
type Sender struct {
	Pool          *pgxpool.Pool
	Getenv        func(string) string
	Now           func() time.Time
	Client        *http.Client
	AllowEndpoint func(string) bool
}

// outboxRow is one push_outbox row joined to its push_subscription.
type outboxRow struct {
	id, subscriptionID, attempts, failures                      int64
	kind, params, url, key, endpointEnc, p256Enc, authEnc, lang string
}

func (s *Sender) env(name string) string {
	if s.Getenv != nil {
		return s.Getenv(name)
	}
	return os.Getenv(name)
}

func (s *Sender) now() time.Time {
	if s.Now != nil {
		return s.Now()
	}
	return time.Now()
}

func (s *Sender) client() *http.Client {
	if s.Client != nil {
		return s.Client
	}
	return defaultClient
}

// enabled is push.py enabled(): config.WEB_PUSH, read from UBYHOST_WEB_PUSH.
func (s *Sender) enabled() bool {
	switch strings.ToLower(strings.TrimSpace(s.env("UBYHOST_WEB_PUSH"))) {
	case "0", "false", "no":
		return false
	}
	return true
}

// allowed is the endpoint check: a push service the browsers use.
func (s *Sender) allowed(endpoint string) bool {
	if s.AllowEndpoint != nil {
		return s.AllowEndpoint(endpoint)
	}
	parts, err := url.Parse(endpoint)
	if err != nil {
		return false
	}
	host := strings.ToLower(parts.Hostname())
	for _, suffix := range pushHosts {
		if host == suffix || strings.HasSuffix(host, "."+suffix) {
			return true
		}
	}
	return false
}

// stamp is push.py _stamp: UTC, whole seconds, ISO 8601 with +00:00.
func stamp(moment time.Time) string {
	return moment.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
}

// endpointHash is push.py _hash.
func endpointHash(endpoint string) string {
	sum := sha256.Sum256([]byte(endpoint))
	return hex.EncodeToString(sum[:])
}

// decryptSecret is db.decrypt_secret: "" for an empty or unreadable token.
func decryptSecret(keys *secure.MultiFernet, token string) string {
	if token == "" {
		return ""
	}
	plain, err := keys.Decrypt(token, 0, time.Now())
	if err != nil {
		return ""
	}
	return string(plain)
}

// lastStatus is a nullable HTTP status for last_status.
func lastStatus(status *int) any {
	if status == nil {
		return nil
	}
	return int64(*status)
}

// pyJSONString quotes s the way Python's json.dumps(ensure_ascii=False) does.
func pyJSONString(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, c := range s {
		switch c {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			if c < 0x20 {
				fmt.Fprintf(&b, `\u%04x`, c)
			} else {
				b.WriteRune(c)
			}
		}
	}
	b.WriteByte('"')
	return b.String()
}

func (s *Sender) exec(ctx context.Context, sql string, args ...any) error {
	_, err := s.Pool.Exec(ctx, sql, args...)
	return err
}

func (s *Sender) setting(ctx context.Context) (string, error) {
	var value *string
	err := s.Pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, vapidSetting).Scan(&value)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	if value == nil {
		return "", nil
	}
	return *value, nil
}

func parseVapid(raw string) (*ecdsa.PrivateKey, error) {
	b, err := webpush.UnB64URL(raw)
	if err != nil {
		return nil, errBadKey
	}
	key, err := webpush.PrivateFromRaw(b)
	if err != nil {
		return nil, errBadKey
	}
	return key, nil
}

// vapidKey is push.py vapid_key: the server's signing key, made on first use
// and kept encrypted in settings.
func (s *Sender) vapidKey(ctx context.Context, keys *secure.MultiFernet) (*ecdsa.PrivateKey, error) {
	stored, err := s.setting(ctx)
	if err != nil {
		return nil, err
	}
	if stored != "" {
		if raw := decryptSecret(keys, stored); raw != "" {
			return parseVapid(raw)
		}
		// The app's secret key changed, so this key is lost. Every subscription
		// was made for it; each browser subscribes again from Settings.
		log.Print("pushsend: web push key unreadable; making a new one and dropping all devices")
		if err := s.exec(ctx, `DELETE FROM push_outbox`); err != nil {
			return nil, err
		}
		if err := s.exec(ctx, `DELETE FROM push_subscription`); err != nil {
			return nil, err
		}
		if err := s.exec(ctx, `DELETE FROM settings WHERE key = $1`, vapidSetting); err != nil {
			return nil, err
		}
	}
	fresh, err := webpush.NewPrivateKey()
	if err != nil {
		return nil, err
	}
	sealed, err := keys.EncryptString(webpush.B64URL(webpush.PrivateRaw(fresh)))
	if err != nil {
		return nil, err
	}
	// Two processes may get here at once: the first row wins and both use it.
	if err := s.exec(ctx,
		`INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO NOTHING`,
		vapidSetting, sealed); err != nil {
		return nil, err
	}
	kept, err := s.setting(ctx)
	if err != nil {
		return nil, err
	}
	return parseVapid(decryptSecret(keys, kept))
}

// PublicKey is push.py public_key: the applicationServerKey a browser subscribes with.
func (s *Sender) PublicKey(ctx context.Context) (string, error) {
	keys, err := secure.LoadDataKeys(s.env)
	if err != nil {
		return "", err
	}
	key, err := s.vapidKey(ctx, keys)
	if err != nil {
		return "", err
	}
	return webpush.B64URL(webpush.PublicRaw(key)), nil
}

// Drain is push.py drain: send the alerts that are due. Returns the count per
// outcome (sent, gone, capped, retry, failed); empty when web push is off.
func (s *Sender) Drain(ctx context.Context, limit int) (map[string]int, error) {
	counts := map[string]int{}
	if !s.enabled() {
		return counts, nil
	}
	keys, err := secure.LoadDataKeys(s.env)
	if err != nil {
		return nil, err
	}
	moment := s.now()
	type due struct {
		id   int64
		when string
	}
	rows, err := s.Pool.Query(ctx,
		`SELECT id, next_attempt_at FROM push_outbox WHERE state = 'queued' AND next_attempt_at <= $1 ORDER BY id LIMIT $2`,
		stamp(moment), limit)
	if err != nil {
		return nil, err
	}
	var batch []due
	for rows.Next() {
		var d due
		if err := rows.Scan(&d.id, &d.when); err != nil {
			rows.Close()
			return nil, err
		}
		batch = append(batch, d)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return nil, err
	}
	rows.Close()
	for _, d := range batch {
		claimed, err := s.claim(ctx, d.id, d.when, moment)
		if err != nil {
			return counts, err
		}
		if !claimed {
			continue
		}
		outcome, err := s.deliver(ctx, keys, d.id, moment)
		if err != nil {
			return counts, err
		}
		counts[outcome]++
	}
	return counts, nil
}

// claim takes a due row for claimMinutes, so a second process cannot send it too.
func (s *Sender) claim(ctx context.Context, id int64, due string, moment time.Time) (bool, error) {
	tag, err := s.Pool.Exec(ctx,
		`UPDATE push_outbox SET attempts = attempts + 1, next_attempt_at = $1 WHERE id = $2 AND state = 'queued' AND next_attempt_at = $3`,
		stamp(moment.Add(claimMinutes*time.Minute)), id, due)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

// SendTest is push.py send_test: the test alert to one device now. Returns the outcome.
func (s *Sender) SendTest(ctx context.Context, accountID int64, endpoint string) (string, error) {
	var deviceID int64
	err := s.Pool.QueryRow(ctx,
		`SELECT id FROM push_subscription WHERE endpoint_hash = $1 AND user_account_id = $2`,
		endpointHash(endpoint), accountID).Scan(&deviceID)
	if errors.Is(err, pgx.ErrNoRows) {
		return "gone", nil
	}
	if err != nil {
		return "", err
	}
	keys, err := secure.LoadDataKeys(s.env)
	if err != nil {
		return "", err
	}
	moment := s.now()
	nonce := make([]byte, 8)
	if _, err := rand.Read(nonce); err != nil {
		return "", err
	}
	var outboxID int64
	err = s.Pool.QueryRow(ctx,
		`INSERT INTO push_outbox (idempotency_key, subscription_id, user_account_id, kind, params, url, state, attempts, next_attempt_at, created_at) VALUES ($1, $2, $3, $4, '{}', $5, 'queued', 1, $6, $7) RETURNING id`,
		fmt.Sprintf("%s:%s:%d", testKind, hex.EncodeToString(nonce), deviceID),
		deviceID, accountID, testKind, testURL,
		stamp(moment.Add(claimMinutes*time.Minute)), stamp(moment)).Scan(&outboxID)
	if err != nil {
		return "", err
	}
	return s.deliver(ctx, keys, outboxID, moment)
}

// deliver is push.py _deliver: one claimed outbox row, sent or settled.
func (s *Sender) deliver(ctx context.Context, keys *secure.MultiFernet, outboxID int64, moment time.Time) (string, error) {
	var r outboxRow
	err := s.Pool.QueryRow(ctx,
		`SELECT o.id, o.subscription_id, o.attempts, o.kind, o.params, o.url, o.idempotency_key, s.endpoint_enc, s.p256dh_enc, s.auth_enc, s.lang, s.failures FROM push_outbox o JOIN push_subscription s ON s.id = o.subscription_id WHERE o.id = $1`,
		outboxID).Scan(&r.id, &r.subscriptionID, &r.attempts, &r.kind, &r.params, &r.url, &r.key,
		&r.endpointEnc, &r.p256Enc, &r.authEnc, &r.lang, &r.failures)
	if errors.Is(err, pgx.ErrNoRows) {
		return "gone", nil
	}
	if err != nil {
		return "", err
	}
	var sentToday int64
	if err := s.Pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM push_outbox WHERE subscription_id = $1 AND state = 'sent' AND sent_at >= $2`,
		r.subscriptionID, stamp(moment.Add(-24*time.Hour))).Scan(&sentToday); err != nil {
		return "", err
	}
	if sentToday >= dailyCap {
		log.Printf("pushsend: push_capped subscription=%d kind=%s", r.subscriptionID, r.kind)
		if err := s.finish(ctx, r.id, "failed", nil, moment); err != nil {
			return "", err
		}
		return "capped", nil
	}
	params := map[string]any{}
	_ = json.Unmarshal([]byte(r.params), &params)
	title := catalog.T(r.lang, "push.msg."+r.kind+".title", params)
	body := catalog.T(r.lang, "push.msg."+r.kind+".body", params)
	// One notification per event: a repeat replaces it instead of stacking.
	tag := r.key
	if i := strings.LastIndex(tag, ":"); i >= 0 {
		tag = tag[:i]
	}
	payload := "{" + `"title": ` + pyJSONString(title) +
		`, "body": ` + pyJSONString(body) +
		`, "url": ` + pyJSONString(r.url) +
		`, "tag": ` + pyJSONString(tag) +
		`, "lang": ` + pyJSONString(r.lang) + "}"

	endpoint := decryptSecret(keys, r.endpointEnc)
	vapid, err := s.vapidKey(ctx, keys)
	if errors.Is(err, errBadKey) {
		return s.goneDevice(ctx, r.subscriptionID)
	}
	if err != nil {
		return "", err
	}
	ua, uaErr := webpush.UnB64URL(decryptSecret(keys, r.p256Enc))
	auth, authErr := webpush.UnB64URL(decryptSecret(keys, r.authEnc))
	if uaErr != nil || authErr != nil {
		// Stored keys that no longer decrypt (the app key changed): unusable.
		return s.goneDevice(ctx, r.subscriptionID)
	}
	if !s.allowed(endpoint) {
		return s.goneDevice(ctx, r.subscriptionID)
	}
	status, err := webpush.Send(s.client(), endpoint, ua, auth, []byte(payload), vapid,
		"mailto:"+supportEmail, ttlSeconds, "high", s.now())
	if errors.Is(err, webpush.ErrTransport) {
		return s.retry(ctx, r, nil, moment)
	}
	if err != nil {
		return s.goneDevice(ctx, r.subscriptionID)
	}
	return s.settle(ctx, r, status, moment)
}

// settle is push.py _settle: what one HTTP status means for the row and device.
func (s *Sender) settle(ctx context.Context, r outboxRow, status int, moment time.Time) (string, error) {
	switch {
	case status >= 200 && status < 300:
		if err := s.finish(ctx, r.id, "sent", &status, moment); err != nil {
			return "", err
		}
		if err := s.exec(ctx, `UPDATE push_subscription SET failures = 0, last_sent_at = $1 WHERE id = $2`,
			stamp(moment), r.subscriptionID); err != nil {
			return "", err
		}
		return "sent", nil
	case status == 404 || status == 410:
		// The browser unsubscribed or the app was removed: forget the device.
		return s.goneDevice(ctx, r.subscriptionID)
	case status == 429 || status >= 500:
		return s.retry(ctx, r, &status, moment)
	}
	if err := s.finish(ctx, r.id, "failed", &status, moment); err != nil {
		return "", err
	}
	failures := r.failures + 1
	if failures >= maxFailures {
		if err := s.drop(ctx, r.subscriptionID); err != nil {
			return "", err
		}
		return "failed", nil
	}
	if err := s.exec(ctx, `UPDATE push_subscription SET failures = $1 WHERE id = $2`,
		failures, r.subscriptionID); err != nil {
		return "", err
	}
	return "failed", nil
}

// retry is push.py _retry: wait for the next RETRY_MINUTES slot, or fail past the last one.
func (s *Sender) retry(ctx context.Context, r outboxRow, status *int, moment time.Time) (string, error) {
	if r.attempts > int64(len(retryMinutes)) {
		if err := s.finish(ctx, r.id, "failed", status, moment); err != nil {
			return "", err
		}
		return "failed", nil
	}
	idx := int(r.attempts) - 1
	if idx < 0 {
		idx = 0
	}
	next := stamp(moment.Add(time.Duration(retryMinutes[idx]) * time.Minute))
	if err := s.exec(ctx, `UPDATE push_outbox SET next_attempt_at = $1, last_status = $2 WHERE id = $3`,
		next, lastStatus(status), r.id); err != nil {
		return "", err
	}
	return "retry", nil
}

// finish is push.py _finish.
func (s *Sender) finish(ctx context.Context, id int64, state string, status *int, moment time.Time) error {
	var sentAt any
	if state == "sent" {
		sentAt = stamp(moment)
	}
	return s.exec(ctx, `UPDATE push_outbox SET state = $1, last_status = $2, sent_at = $3 WHERE id = $4`,
		state, lastStatus(status), sentAt, id)
}

// drop is push.py _drop: the device and its outbox rows.
func (s *Sender) drop(ctx context.Context, subscriptionID int64) error {
	if err := s.exec(ctx, `DELETE FROM push_outbox WHERE subscription_id = $1`, subscriptionID); err != nil {
		return err
	}
	return s.exec(ctx, `DELETE FROM push_subscription WHERE id = $1`, subscriptionID)
}

func (s *Sender) goneDevice(ctx context.Context, subscriptionID int64) (string, error) {
	if err := s.drop(ctx, subscriptionID); err != nil {
		return "", err
	}
	return "gone", nil
}
