package pushsend

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/ecdh"
	"crypto/hkdf"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/webpush"
)

var testNow = time.Unix(1790000000, 0)

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL and applies
// the Postgres migrations to it, as pushweb_test.go does.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_pushsend_%d", time.Now().UnixNano())
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
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("migration %s: %v", f, err)
		}
	}
	return pool
}

type fixture struct {
	t    *testing.T
	pool *pgxpool.Pool
	s    *Sender
	keys *secure.MultiFernet
	ua   *ecdh.PrivateKey
	auth []byte
	got  []byte // body of the last request the fake push service received
}

func newFixture(t *testing.T) *fixture {
	t.Helper()
	pool := testPool(t)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version) VALUES (1, 'host_one', 'x', '2026-01-01T00:00:00+00:00', 'host', 1, 1)`); err != nil {
		t.Fatal(err)
	}
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		t.Fatal(err)
	}
	env := map[string]string{
		"UBYHOST_DATA_KEYS":       base64.URLEncoding.EncodeToString(raw),
		"UBYHOST_DATA_KEY_LEGACY": "0",
	}
	getenv := func(name string) string { return env[name] }
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		t.Fatal(err)
	}
	ua, err := ecdh.P256().GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	auth := make([]byte, 16)
	if _, err := rand.Read(auth); err != nil {
		t.Fatal(err)
	}
	f := &fixture{t: t, pool: pool, keys: keys, ua: ua, auth: auth}
	f.s = &Sender{
		Pool:          pool,
		Getenv:        getenv,
		Now:           func() time.Time { return testNow },
		AllowEndpoint: func(string) bool { return true },
	}
	return f
}

// serve starts a fake push service that answers status and keeps the body.
func (f *fixture) serve(status int) string {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		f.got = body
		w.WriteHeader(status)
	}))
	f.t.Cleanup(srv.Close)
	return srv.URL + "/push/device"
}

func (f *fixture) exec(sql string, args ...any) {
	f.t.Helper()
	if _, err := f.pool.Exec(context.Background(), sql, args...); err != nil {
		f.t.Fatal(err)
	}
}

func (f *fixture) scan(sql string, args []any, dest ...any) {
	f.t.Helper()
	if err := f.pool.QueryRow(context.Background(), sql, args...).Scan(dest...); err != nil {
		f.t.Fatal(err)
	}
}

func (f *fixture) count(sql string, args ...any) int64 {
	var n int64
	f.scan(sql, args, &n)
	return n
}

func (f *fixture) seal(v string) string {
	out, err := f.keys.EncryptString(v)
	if err != nil {
		f.t.Fatal(err)
	}
	return out
}

// addDevice stores a subscription for endpoint with this fixture's browser keys.
func (f *fixture) addDevice(endpoint string, failures int64) int64 {
	f.t.Helper()
	var id int64
	f.scan(`INSERT INTO push_subscription (user_account_id, endpoint_hash, endpoint_enc, p256dh_enc, auth_enc, lang, device, failures, created_at, last_seen_at) VALUES (1, $1, $2, $3, $4, 'en', '', $5, '2026-11-01T00:00:00+00:00', '2026-11-01T00:00:00+00:00') RETURNING id`,
		[]any{endpointHash(endpoint), f.seal(endpoint), f.seal(webpush.B64URL(f.ua.PublicKey().Bytes())), f.seal(webpush.B64URL(f.auth)), failures}, &id)
	return id
}

// queue adds one outbox row that is due at nextAt.
func (f *fixture) queue(sub int64, kind, params, key string, attempts int64, nextAt time.Time) int64 {
	f.t.Helper()
	var id int64
	f.scan(`INSERT INTO push_outbox (idempotency_key, subscription_id, user_account_id, kind, params, url, state, attempts, next_attempt_at, created_at) VALUES ($1, $2, 1, $3, $4, '/', 'queued', $5, $6, $7) RETURNING id`,
		[]any{key, sub, kind, params, attempts, stamp(nextAt), stamp(testNow)}, &id)
	return id
}

func (f *fixture) drain() map[string]int {
	f.t.Helper()
	counts, err := f.s.Drain(context.Background(), 50)
	if err != nil {
		f.t.Fatal(err)
	}
	return counts
}

// outbox reads one row's state, due time, last status and sent time.
func (f *fixture) outbox(id int64) (string, string, *int64, *string) {
	var state, next string
	var last *int64
	var sentAt *string
	f.scan(`SELECT state, next_attempt_at, last_status, sent_at FROM push_outbox WHERE id = $1`,
		[]any{id}, &state, &next, &last, &sentAt)
	return state, next, last, sentAt
}

func (f *fixture) expect(name string, got, want any) {
	f.t.Helper()
	if got != want {
		f.t.Errorf("%s: got %v, want %v", name, got, want)
	}
}

// decryptBody reads an aes128gcm body the way a browser does (RFC 8188).
func decryptBody(t *testing.T, body, uaPrivate, authSecret []byte) []byte {
	t.Helper()
	salt := body[:16]
	idLen := int(body[20])
	asPublic := body[21 : 21+idLen]
	ciphertext := body[21+idLen:]
	ua, err := ecdh.P256().NewPrivateKey(uaPrivate)
	if err != nil {
		t.Fatal(err)
	}
	asPub, err := ecdh.P256().NewPublicKey(asPublic)
	if err != nil {
		t.Fatal(err)
	}
	secret, err := ua.ECDH(asPub)
	if err != nil {
		t.Fatal(err)
	}
	info := append(append([]byte("WebPush: info\x00"), ua.PublicKey().Bytes()...), asPublic...)
	ikm, _ := hkdf.Key(sha256.New, secret, authSecret, string(info), 32)
	cek, _ := hkdf.Key(sha256.New, ikm, salt, "Content-Encoding: aes128gcm\x00", 16)
	nonce, _ := hkdf.Key(sha256.New, ikm, salt, "Content-Encoding: nonce\x00", 12)
	block, _ := aes.NewCipher(cek)
	gcm, _ := cipher.NewGCM(block)
	plain, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		t.Fatal(err)
	}
	if binary.BigEndian.Uint32(body[16:20]) != webpush.RecordSize {
		t.Fatal("record size")
	}
	if plain[len(plain)-1] != 0x02 {
		t.Fatal("missing last-record delimiter")
	}
	return plain[:len(plain)-1]
}

func TestSentStampsDevice(t *testing.T) {
	f := newFixture(t)
	sub := f.addDevice(f.serve(http.StatusCreated), 3)
	id := f.queue(sub, "test", "{}", "test:0123456789abcdef:1", 0, testNow)
	f.expect("counts", f.drain()["sent"], 1)
	state, _, _, sentAt := f.outbox(id)
	f.expect("state", state, "sent")
	f.expect("sent_at", *sentAt, stamp(testNow))
	var failures int64
	var lastSent *string
	f.scan(`SELECT failures, last_sent_at FROM push_subscription WHERE id = $1`, []any{sub}, &failures, &lastSent)
	f.expect("failures", failures, int64(0))
	f.expect("last_sent_at", *lastSent, stamp(testNow))
}

func TestGoneStatusesDropDevice(t *testing.T) {
	for _, status := range []int{http.StatusNotFound, http.StatusGone} {
		t.Run(fmt.Sprint(status), func(t *testing.T) {
			f := newFixture(t)
			sub := f.addDevice(f.serve(status), 0)
			f.queue(sub, "test", "{}", "test:a:1", 0, testNow)
			f.expect("counts", f.drain()["gone"], 1)
			f.expect("devices", f.count(`SELECT COUNT(*) FROM push_subscription WHERE id = $1`, sub), int64(0))
			f.expect("outbox", f.count(`SELECT COUNT(*) FROM push_outbox WHERE subscription_id = $1`, sub), int64(0))
		})
	}
}

func TestRetryScheduleThenFailed(t *testing.T) {
	for _, status := range []int{http.StatusTooManyRequests, http.StatusInternalServerError} {
		t.Run(fmt.Sprint(status), func(t *testing.T) {
			f := newFixture(t)
			sub := f.addDevice(f.serve(status), 0)
			first := f.queue(sub, "test", "{}", "test:a:1", 0, testNow)
			later := f.queue(sub, "test", "{}", "test:b:2", 2, testNow)
			f.expect("retry count", f.drain()["retry"], 2)
			_, next, last, _ := f.outbox(first)
			f.expect("first wait", next, stamp(testNow.Add(time.Minute)))
			f.expect("first last_status", *last, int64(status))
			_, next, _, _ = f.outbox(later)
			f.expect("third wait", next, stamp(testNow.Add(15*time.Minute)))
			// The fifth try is past the last wait: the row fails.
			f.exec(`UPDATE push_outbox SET attempts = 4, next_attempt_at = $1 WHERE id = $2`, stamp(testNow), first)
			f.expect("failed count", f.drain()["failed"], 1)
			state, _, _, _ := f.outbox(first)
			f.expect("state", state, "failed")
		})
	}
}

func TestRefusedCountsFailuresThenDrops(t *testing.T) {
	f := newFixture(t)
	sub := f.addDevice(f.serve(http.StatusBadRequest), 3)
	id := f.queue(sub, "test", "{}", "test:a:1", 0, testNow)
	f.expect("counts", f.drain()["failed"], 1)
	state, _, last, _ := f.outbox(id)
	f.expect("state", state, "failed")
	f.expect("last_status", *last, int64(400))
	var failures int64
	f.scan(`SELECT failures FROM push_subscription WHERE id = $1`, []any{sub}, &failures)
	f.expect("failures", failures, int64(4))

	g := newFixture(t)
	gone := g.addDevice(g.serve(http.StatusBadRequest), maxFailures-1)
	g.queue(gone, "test", "{}", "test:b:1", 0, testNow)
	g.drain()
	f.expect("fifth refusal drops", g.count(`SELECT COUNT(*) FROM push_subscription WHERE id = $1`, gone), int64(0))
}

func TestDailyCapStopsSending(t *testing.T) {
	f := newFixture(t)
	sub := f.addDevice(f.serve(http.StatusCreated), 0)
	for i := 0; i < dailyCap; i++ {
		f.exec(`INSERT INTO push_outbox (idempotency_key, subscription_id, user_account_id, kind, params, url, state, attempts, next_attempt_at, created_at, sent_at) VALUES ($1, $2, 1, 'test', '{}', '/', 'sent', 1, $3, $3, $4)`,
			fmt.Sprintf("test:old:%d", i), sub, stamp(testNow), stamp(testNow.Add(-time.Hour)))
	}
	id := f.queue(sub, "test", "{}", "test:new:1", 0, testNow)
	f.expect("counts", f.drain()["capped"], 1)
	state, _, _, _ := f.outbox(id)
	f.expect("state", state, "failed")
	f.expect("no request", len(f.got), 0)
}

func TestClaimTakesRowOnce(t *testing.T) {
	f := newFixture(t)
	sub := f.addDevice(f.serve(http.StatusCreated), 0)
	id := f.queue(sub, "test", "{}", "test:a:1", 0, testNow)
	first, err := f.s.claim(context.Background(), id, stamp(testNow), testNow)
	if err != nil {
		t.Fatal(err)
	}
	second, err := f.s.claim(context.Background(), id, stamp(testNow), testNow)
	if err != nil {
		t.Fatal(err)
	}
	f.expect("first claim", first, true)
	f.expect("second claim", second, false)
}

func TestTransportErrorRetries(t *testing.T) {
	f := newFixture(t)
	srv := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	endpoint := srv.URL + "/push/device"
	srv.Close()
	sub := f.addDevice(endpoint, 0)
	id := f.queue(sub, "test", "{}", "test:a:1", 0, testNow)
	f.expect("counts", f.drain()["retry"], 1)
	state, next, last, _ := f.outbox(id)
	f.expect("state", state, "queued")
	f.expect("next", next, stamp(testNow.Add(time.Minute)))
	f.expect("last_status", last == nil, true)
}

func TestUndecryptableKeysAreGone(t *testing.T) {
	f := newFixture(t)
	sub := f.addDevice(f.serve(http.StatusCreated), 0)
	f.exec(`UPDATE push_subscription SET p256dh_enc = 'not-a-token' WHERE id = $1`, sub)
	f.queue(sub, "test", "{}", "test:a:1", 0, testNow)
	f.expect("counts", f.drain()["gone"], 1)
	f.expect("devices", f.count(`SELECT COUNT(*) FROM push_subscription WHERE id = $1`, sub), int64(0))
}

func TestVapidKeyMadeOnceAndReused(t *testing.T) {
	f := newFixture(t)
	first, err := f.s.PublicKey(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	second, err := f.s.PublicKey(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	f.expect("same key", first, second)
	f.expect("settings rows", f.count(`SELECT COUNT(*) FROM settings WHERE key = $1`, vapidSetting), int64(1))
}

func TestUnreadableVapidResetsEverything(t *testing.T) {
	f := newFixture(t)
	sub := f.addDevice(f.serve(http.StatusCreated), 0)
	f.queue(sub, "test", "{}", "test:a:1", 0, testNow)
	f.exec(`INSERT INTO settings (key, value) VALUES ($1, 'garbage')`, vapidSetting)
	key, err := f.s.PublicKey(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	f.expect("new key made", key != "", true)
	f.expect("outbox cleared", f.count(`SELECT COUNT(*) FROM push_outbox`), int64(0))
	f.expect("devices cleared", f.count(`SELECT COUNT(*) FROM push_subscription`), int64(0))
	var stored string
	f.scan(`SELECT value FROM settings WHERE key = $1`, []any{vapidSetting}, &stored)
	f.expect("setting replaced", stored != "garbage", true)
}

func TestSendTestUnknownEndpointIsGone(t *testing.T) {
	f := newFixture(t)
	outcome, err := f.s.SendTest(context.Background(), 1, "https://fcm.googleapis.com/unknown")
	if err != nil {
		t.Fatal(err)
	}
	f.expect("outcome", outcome, "gone")
}

func TestSendTestDeliversToDevice(t *testing.T) {
	f := newFixture(t)
	endpoint := f.serve(http.StatusCreated)
	f.addDevice(endpoint, 0)
	outcome, err := f.s.SendTest(context.Background(), 1, endpoint)
	if err != nil {
		t.Fatal(err)
	}
	f.expect("outcome", outcome, "sent")
	plain := string(decryptBody(t, f.got, f.ua.Bytes(), f.auth))
	prefix := `{"title": "Alerts are on", "body": "This device will get urgent UbyHost alerts.", "url": "/settings#settings-group-phone", "tag": "test:`
	f.expect("payload prefix", strings.HasPrefix(plain, prefix), true)
	f.expect("payload suffix", strings.HasSuffix(plain, `", "lang": "en"}`), true)
}

func TestPayloadMatchesPython(t *testing.T) {
	f := newFixture(t)
	endpoint := f.serve(http.StatusCreated)
	sub := f.addDevice(endpoint, 0)

	f.queue(sub, "test", "{}", "test:0123456789abcdef:7", 0, testNow)
	f.expect("test sent", f.drain()["sent"], 1)
	plain := string(decryptBody(t, f.got, f.ua.Bytes(), f.auth))
	want := `{"title": "Alerts are on", "body": "This device will get urgent UbyHost alerts.", "url": "/", "tag": "test:0123456789abcdef", "lang": "en"}`
	f.expect("en payload", plain, want)

	f.exec(`UPDATE push_subscription SET lang = 'cs' WHERE id = $1`, sub)
	f.queue(sub, "filing_problem", `{"property": "Vinohrady"}`, "filing_problem:x:8", 0, testNow)
	f.expect("filing sent", f.drain()["sent"], 1)
	plain = string(decryptBody(t, f.got, f.ua.Bytes(), f.auth))
	want = `{"title": "Hlášení policii nepřijato", "body": "Vinohrady: UbyPort hlášení nepřijal.", "url": "/", "tag": "filing_problem:x", "lang": "cs"}`
	f.expect("cs payload", plain, want)
}
