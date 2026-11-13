package lifecyclemail

import (
	"bytes"
	"compress/zlib"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const goldenDir = "testdata/lifecycle_mail"

// outboxRow keeps the columns the golden compares (no timestamps, no ids).
type outboxRow struct {
	Key           string  `json:"idempotency_key"`
	Kind          string  `json:"kind"`
	To            string  `json:"to_email"`
	CC            *string `json:"cc_email"`
	Subject       string  `json:"subject"`
	Payload       string  `json:"payload"`
	State         string  `json:"state"`
	Attempts      int64   `json:"attempts"`
	OwnerUserID   *int64  `json:"owner_user_id"`
	ReservationID *int64  `json:"reservation_id"`
	ApartmentID   *int64  `json:"apartment_id"`
}

type expected struct {
	Env  map[string]string `json:"env"`
	Runs []struct {
		Now         string              `json:"now"`
		Summary     map[string]int      `json:"summary"`
		OutboxTotal int                 `json:"outbox_total"`
		Outbox      []outboxRow         `json:"outbox"`
		Sent        []map[string]any    `json:"sent"`
		Settings    []map[string]string `json:"settings"`
	} `json:"runs"`
	Builds []struct {
		Kind, Subject, Text, HTML string
		URL                       string `json:"unsubscribe_url"`
	} `json:"builds"`
	Tokens []struct {
		UserID                    int64 `json:"user_id"`
		Address, Hash, Token, URL string
	} `json:"tokens"`
}

func loadExpected(t *testing.T) (expected, func(string) string) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(goldenDir, "expected.json"))
	if err != nil {
		t.Fatal(err)
	}
	var e expected
	if err := json.Unmarshal(raw, &e); err != nil {
		t.Fatal(err)
	}
	return e, func(k string) string { return e.Env[k] }
}

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_lifecycle_%d", time.Now().UnixNano())
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
		if c, err := pgx.Connect(context.Background(), base); err == nil {
			_, _ = c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)")
			c.Close(context.Background())
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
		if i := strings.Index(up, "-- +goose Up"); i >= 0 {
			up = up[i+len("-- +goose Up"):]
		}
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("%s: %v", filepath.Base(f), err)
		}
	}
	return pool
}

// loadFixture inserts fixture.json (tables in order) into pool.
func loadFixture(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(goldenDir, "fixture.json"))
	if err != nil {
		t.Fatal(err)
	}
	var tables []struct {
		Table string                       `json:"table"`
		Rows  []map[string]json.RawMessage `json:"rows"`
	}
	if err := json.Unmarshal(raw, &tables); err != nil {
		t.Fatal(err)
	}
	for _, tb := range tables {
		for _, row := range tb.Rows {
			cols := make([]string, 0, len(row))
			for c := range row {
				cols = append(cols, c)
			}
			sort.Strings(cols)
			marks, args := make([]string, len(cols)), make([]any, len(cols))
			for i, c := range cols {
				marks[i] = fmt.Sprintf("$%d", i+1)
				dec := json.NewDecoder(bytes.NewReader(row[c]))
				dec.UseNumber()
				if err := dec.Decode(&args[i]); err != nil {
					t.Fatal(err)
				}
				if n, ok := args[i].(json.Number); ok {
					if args[i], err = n.Int64(); err != nil {
						t.Fatal(err)
					}
				}
			}
			sql := "INSERT INTO " + tb.Table + " (" + strings.Join(cols, ", ") + ") VALUES (" + strings.Join(marks, ", ") + ")"
			if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
				t.Fatalf("fixture %s: %v", tb.Table, err)
			}
		}
	}
}

// rowsJSON runs a query that returns one json array and decodes it into out.
func rowsJSON(t *testing.T, pool *pgxpool.Pool, query string, out any) {
	t.Helper()
	var raw []byte
	if err := pool.QueryRow(context.Background(), query).Scan(&raw); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(raw, out); err != nil {
		t.Fatal(err)
	}
}

func readOutbox(t *testing.T, pool *pgxpool.Pool) (rows []outboxRow) {
	rowsJSON(t, pool, `SELECT COALESCE(json_agg(json_build_object('idempotency_key', idempotency_key,
		'kind', kind, 'to_email', to_email, 'cc_email', cc_email, 'subject', subject, 'payload', payload,
		'state', state, 'attempts', attempts, 'owner_user_id', owner_user_id, 'reservation_id', reservation_id,
		'apartment_id', apartment_id) ORDER BY id), '[]'::json) FROM email_outbox`, &rows)
	return rows
}

func TestRunDailyGolden(t *testing.T) {
	e, getenv := loadExpected(t)
	pool := testPool(t)
	loadFixture(t, pool)
	cfg := ConfigFromEnv(getenv)
	seen := 1 // the fixture's own outbox row
	for _, run := range e.Runs {
		now, err := time.Parse(time.RFC3339, run.Now)
		if err != nil {
			t.Fatal(err)
		}
		summary, err := RunDaily(context.Background(), pool, cfg, now)
		if err != nil {
			t.Fatalf("%s: %v", run.Now, err)
		}
		if !reflect.DeepEqual(summary, run.Summary) {
			t.Errorf("%s: summary %v, want %v", run.Now, summary, run.Summary)
		}
		all := readOutbox(t, pool)
		if len(all) != run.OutboxTotal || len(all)-seen != len(run.Outbox) {
			t.Fatalf("%s: %d outbox rows, want %d", run.Now, len(all), run.OutboxTotal)
		}
		for i, got := range all[seen:] {
			want := run.Outbox[i]
			// A token may differ in its compressed bytes only (see TestTokensGolden).
			if stripTokens(got.Payload) != stripTokens(want.Payload) {
				t.Errorf("%s row %d: payload differs", run.Now, i)
			}
			gotTokens, wantTokens := tokensIn(got.Payload), tokensIn(want.Payload)
			if len(gotTokens) != 3 || len(gotTokens) != len(wantTokens) {
				t.Errorf("%s row %d: %d tokens, want %d", run.Now, i, len(gotTokens), len(wantTokens))
			}
			for j := range min(len(gotTokens), len(wantTokens)) {
				a, okA := decodeToken(cfg.SecretKey, gotTokens[j])
				b, okB := decodeToken(cfg.SecretKey, wantTokens[j])
				if !okA || !okB || a != b {
					t.Errorf("%s row %d token %d: %q vs %q", run.Now, i, j, a, b)
				}
			}
			got.Payload, want.Payload = "", ""
			if !reflect.DeepEqual(got, want) {
				t.Errorf("%s row %d:\n got  %+v\n want %+v", run.Now, i, got, want)
			}
		}
		seen = len(all)
		var sent []map[string]any
		rowsJSON(t, pool, `SELECT COALESCE(json_agg(json_build_object('user_account_id', user_account_id,
			'kind', kind) ORDER BY user_account_id, kind), '[]'::json) FROM lifecycle_mail_sent`, &sent)
		if !reflect.DeepEqual(fmt.Sprint(sent), fmt.Sprint(run.Sent)) {
			t.Errorf("%s: sent %v, want %v", run.Now, sent, run.Sent)
		}
		var settings []map[string]string
		rowsJSON(t, pool, `SELECT COALESCE(json_agg(json_build_object('key', key, 'value', value) ORDER BY key),
			'[]'::json) FROM settings WHERE key IN ('lifecycle_mail_last_day', 'other_setting')`, &settings)
		if !reflect.DeepEqual(settings, run.Settings) {
			t.Errorf("%s: settings %v, want %v", run.Now, settings, run.Settings)
		}
	}
}

// stripTokens cuts every unsubscribe token out of s.
func stripTokens(s string) string {
	const marker = "/mail/unsubscribe/"
	var out strings.Builder
	for {
		i := strings.Index(s, marker)
		if i < 0 {
			return out.String() + s
		}
		out.WriteString(s[:i+len(marker)])
		rest := s[i+len(marker):]
		j := strings.IndexAny(rest, "?\\\"")
		if j < 0 {
			return out.String()
		}
		s = rest[j:]
	}
}

// tokensIn returns every unsubscribe token in s, in order.
func tokensIn(s string) []string {
	const marker = "/mail/unsubscribe/"
	var found []string
	for {
		i := strings.Index(s, marker)
		if i < 0 {
			return found
		}
		s = s[i+len(marker):]
		j := strings.IndexAny(s, "?\\\"")
		if j < 0 {
			return append(found, s)
		}
		found = append(found, s[:j])
		s = s[j:]
	}
}

func TestBuildLifecycleGolden(t *testing.T) {
	e, getenv := loadExpected(t)
	cfg := ConfigFromEnv(getenv)
	if len(e.Builds) != 6 {
		t.Fatalf("%d builds in the golden", len(e.Builds))
	}
	for _, b := range e.Builds {
		got, err := cfg.BuildLifecycle(b.Kind, b.URL, "en")
		if err != nil {
			t.Fatal(err)
		}
		if got.Subject != b.Subject || got.Text != b.Text || got.HTML != b.HTML {
			t.Errorf("%s: subject, text or html differs from Python", b.Kind)
		}
	}
	if _, err := cfg.BuildLifecycle("lifecycle_nope", "u", "en"); err == nil {
		t.Error("unknown kind must fail")
	}
	if _, err := cfg.BuildLifecycle("lifecycle_no_guest", "u", "cs"); err != ErrLanguage {
		t.Errorf("cs: %v", err)
	}
}

// decodeToken verifies the signature and returns the JSON the token carries.
func decodeToken(secret, token string) (string, bool) {
	cut := strings.LastIndex(token, ".")
	if cut < 0 {
		return "", false
	}
	value := token[:cut]
	if sig, _ := signValue(secret, value); sig != token[cut+1:] {
		return "", false
	}
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimPrefix(value, "."))
	if err != nil {
		return "", false
	}
	if strings.HasPrefix(value, ".") {
		r, err := zlib.NewReader(bytes.NewReader(raw))
		if err != nil {
			return "", false
		}
		if raw, err = io.ReadAll(r); err != nil {
			return "", false
		}
	}
	return string(raw), true
}

func TestTokensGolden(t *testing.T) {
	e, getenv := loadExpected(t)
	cfg := ConfigFromEnv(getenv)
	if cfg.SecretKey == "" {
		t.Fatal("no secret in the golden env")
	}
	for _, tk := range e.Tokens {
		if h := EmailHash(cfg.SecretKey, tk.Address); h != tk.Hash {
			t.Errorf("hash of %q: %q want %q", tk.Address, h, tk.Hash)
		}
		got, err := UnsubscribeToken(cfg.SecretKey, tk.UserID, tk.Address)
		if err != nil {
			t.Fatal(err)
		}
		// Python zlib and Go deflate may write different bytes for one JSON;
		// both must verify and carry the same JSON.
		a, okA := decodeToken(cfg.SecretKey, got)
		b, okB := decodeToken(cfg.SecretKey, tk.Token)
		if !okA || !okB || a != b {
			t.Errorf("token for %d: %q vs %q", tk.UserID, a, b)
		}
	}
	url, _ := cfg.UnsubscribeURL(1, "a@example.test", "en")
	if !strings.HasPrefix(url, "https://www.example.test/mail/unsubscribe/") || !strings.HasSuffix(url, "?lang=en") {
		t.Errorf("url %q", url)
	}
}

func countRows(t *testing.T, pool *pgxpool.Pool, query string, args ...any) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(), query, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func TestDisabledSwitchesWriteNothing(t *testing.T) {
	_, getenv := loadExpected(t)
	pool := testPool(t)
	loadFixture(t, pool)
	now := time.Date(2026, 3, 10, 8, 30, 0, 0, time.UTC)
	base := ConfigFromEnv(getenv)
	for _, tc := range []struct {
		name   string
		mod    func(c *Config)
		marker int
	}{
		{"switch off", func(c *Config) { c.LifecycleMail = false }, 0},
		{"backend off", func(c *Config) { c.MailBackend = "disabled" }, 0},
		// As in Python: run_daily writes the day marker, then run() refuses.
		{"no operator ico", func(c *Config) { c.OperatorICO = "" }, 1},
	} {
		cfg := base
		tc.mod(&cfg)
		summary, err := RunDaily(context.Background(), pool, cfg, now)
		if err != nil || len(summary) != 0 {
			t.Fatalf("%s: %v %v", tc.name, summary, err)
		}
		if n := countRows(t, pool, `SELECT count(*) FROM email_outbox`); n != 1 {
			t.Fatalf("%s: %d outbox rows", tc.name, n)
		}
		if n := countRows(t, pool, `SELECT count(*) FROM lifecycle_mail_sent`); n != 1 {
			t.Fatalf("%s: %d sent markers", tc.name, n)
		}
		if n := countRows(t, pool, `SELECT count(*) FROM settings WHERE key = $1`, LastRunKey); n != tc.marker {
			t.Fatalf("%s: %d day markers, want %d", tc.name, n, tc.marker)
		}
	}
}

func TestMissingSecretDoesNotUseUpTheDay(t *testing.T) {
	_, getenv := loadExpected(t)
	pool := testPool(t)
	loadFixture(t, pool)
	now := time.Date(2026, 3, 10, 8, 30, 0, 0, time.UTC)
	cfg := ConfigFromEnv(getenv)
	cfg.SecretKey = ""
	summary, err := RunDaily(context.Background(), pool, cfg, now)
	if err == nil || len(summary) != 0 {
		t.Fatalf("want an error, got %v %v", summary, err)
	}
	if strings.Contains(err.Error(), "@") {
		t.Fatal("error carries an address")
	}
	if n := countRows(t, pool, `SELECT count(*) FROM settings WHERE key = $1`, LastRunKey); n != 0 {
		t.Fatalf("%d day markers", n)
	}
	if n := countRows(t, pool, `SELECT count(*) FROM email_outbox`); n != 1 {
		t.Fatalf("%d outbox rows", n)
	}
}

func TestConfigFromEnv(t *testing.T) {
	empty := func(string) string { return "" }
	c := ConfigFromEnv(empty)
	if c.LifecycleMail || c.MailBackend != "disabled" || c.PublicBaseURL != "http://127.0.0.1:8080" ||
		c.OperatorEmail != "support@ubyhost.com" || c.appBaseURL() != "http://127.0.0.1:8080" {
		t.Fatalf("defaults: %+v", c)
	}
	env := map[string]string{
		"UBYHOST_LIFECYCLE_MAIL":   "YES",
		"UBYHOST_MAIL_BACKEND":     " SES ",
		"UBYHOST_PUBLIC_BASE_URL":  "https://www.example.test//",
		"UBYHOST_APP_BASE_URL":     " https://app.example.test/ ",
		"UBYHOST_OPERATOR_NAME":    " Name ",
		"UBYHOST_OPERATOR_EMAIL":   " ops@example.test ",
		"UBYHOST_SECRET_KEY":       "0123456789abcdef0123456789abcdef",
		"UBYHOST_OPERATOR_ICO":     "1",
		"UBYHOST_OPERATOR_ADDRESS": "A",
	}
	c = ConfigFromEnv(func(k string) string { return env[k] })
	if !c.LifecycleMail || c.MailBackend != "ses" || !c.mailEnabled() || c.PublicBaseURL != "https://www.example.test" ||
		c.appBaseURL() != "https://app.example.test" || c.OperatorName != "Name" ||
		c.OperatorEmail != "ops@example.test" || !c.senderIdentified() ||
		c.SecretKey != "0123456789abcdef0123456789abcdef" {
		t.Fatalf("set: %+v", c)
	}
	for _, v := range []string{"0", "on", " 1"} {
		if lifecycleSwitch(v) {
			t.Errorf("switch %q must be off", v)
		}
	}
}
