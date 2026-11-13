# 1235 part 2: test and golden script for the lifecycle tips port

Status: todo
Report: docs/tasks/1235-report.md
Part of [1235](1235-go-lifecycle-mail.md); read that brief first and follow its rules, §5 to §9. This file only holds Steps 5 and 6, split off for the size cap. Create each file with exactly the content shown, check `sha256sum <path>` against the line under it, then go back to Step 7 of the main brief.

## 1. Objective

The Go test and the Python golden script of brief 1235.

## 2. Context

As in [1235 §2](1235-go-lifecycle-mail.md#2-context).

## 3. Files

`go/internal/lifecyclemail/lifecyclemail_test.go` and `App/scripts/lifecycle_mail_golden.py` (both create; listed in [1235 §3](1235-go-lifecycle-mail.md#3-files)).

## 4. Steps

### Step 5: `go/internal/lifecyclemail/lifecyclemail_test.go`

```go
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
```

sha256: `1557be1286222bc7cae1734f615f707d726f17f4c362d3dc7b47fd2e4adfaa82`

### Step 6: `App/scripts/lifecycle_mail_golden.py`

```python
#!/usr/bin/env python3
"""Write the Python oracle for the Go lifecyclemail package (1235).

Dev tool, never run in production. Invented data only: no .env, no network, a
throwaway SQLite database. Run from App/:

    .venv/bin/python scripts/lifecycle_mail_golden.py [--out DIR]

It writes two files to go/internal/lifecyclemail/testdata/lifecycle_mail/:

* fixture.json: the tables the Go test loads into Postgres;
* expected.json: the environment, the state after each run_daily call
  (summary, outbox rows, lifecycle_mail_sent, settings), build_lifecycle
  output for every kind and some unsubscribe tokens and hashes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = APP_DIR.parent / "go" / "internal" / "lifecyclemail" / "testdata" / "lifecycle_mail"

TMP = Path(tempfile.mkdtemp(prefix="lifecycle-golden-"))
ENV = {
    "UBYHOST_LIFECYCLE_MAIL": "1",
    "UBYHOST_MAIL_BACKEND": "console",
    "UBYHOST_SECRET_KEY": "golden-secret-key-0123456789-abcdefghij-invented",
    "UBYHOST_PUBLIC_BASE_URL": "https://www.example.test",
    "UBYHOST_APP_BASE_URL": "https://app.example.test",
    "UBYHOST_OPERATOR_NAME": "Demo & Sons <s.r.o.>",
    "UBYHOST_OPERATOR_ICO": "12345678",
    "UBYHOST_OPERATOR_ADDRESS": "Demo Street 1, 100 00 Praha č",
    "UBYHOST_OPERATOR_EMAIL": "help@example.test",
}
os.environ.update(ENV)
os.environ["UBYHOST_DB"] = str(TMP / "golden.db")
os.environ["UBYHOST_DATA_DIR"] = str(TMP)
os.environ["UBYHOST_ENABLE_SCHEDULER"] = "0"
os.environ.pop("UBYHOST_DATABASE_URL", None)
sys.path.insert(0, str(APP_DIR))

from app import db, lifecycle_mail, mail, mail_notify  # noqa: E402

REF = datetime(2026, 3, 10, 8, 30, tzinfo=timezone.utc)
# Instants: before 09:00 Prague, after, same day again, next day, and the
# morning DST starts (29 March: 06:30Z is 08:30 local, 07:30Z is 09:30 local).
RUNS = [
    datetime(2026, 3, 10, 7, 30, tzinfo=timezone.utc),
    datetime(2026, 3, 10, 8, 30, tzinfo=timezone.utc),
    datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc),
    datetime(2026, 3, 11, 8, 30, tzinfo=timezone.utc),
    datetime(2026, 3, 30, 6, 30, tzinfo=timezone.utc),
    datetime(2026, 3, 30, 7, 30, tzinfo=timezone.utc),
]


def ago(days: int = 0, hours: int = 0) -> str:
    return (REF - timedelta(days=days, hours=hours)).replace(microsecond=0).isoformat()


# One line per account: (id, login days ago, contact addresses, user columns).
# Apartments, feeds and reservations follow in APARTMENTS, FEEDS, RESERVATIONS.
HOSTS = [
    (1, 4, ["Alpha@Example.Test", " alpha@example.test ", "Second <second@example.test>"], {}),
    (2, 2, ["two@example.test"], {}),  # not due yet
    (3, 5, ["three@example.test"], {"onboarding_emails_opt_out": 1}),
    (4, 5, ["four@example.test"], {}),  # suppressed
    (5, 5, ["five-a@example.test", "five-b@example.test"], {}),  # one suppressed
    (6, 5, [], {}),  # no contact
    (7, 40, ["seven@example.test"], {}),  # too late
    (8, 20, ["eight@example.test"], {}),  # also a 2FA login 5 days ago
    (9, None, ["nine@example.test"], {"last_login_at": ago(4)}),
    (10, 5, ["ten@example.test"], {"active": 0}),
    (11, 5, ["eleven@example.test"], {"deletion_due_at": ago(-5)}),
    (12, 5, ["twelve@example.test"], {"role": "admin"}),
    (13, 10, ["thirteen@example.test"], {}),
    (14, 10, ["fourteen@example.test"], {}),
    (15, 40, ["fifteen@example.test"], {}),
    (16, 40, ["sixteen@example.test"], {}),
    (17, 40, ["seventeen@example.test"], {}),
    (18, 40, ["eighteen@example.test"], {}),
    (19, 10, ["nineteen@example.test"], {}),
    (20, 4, ["twenty@example.test"], {}),  # marker already there
    (21, 3, ["twentyone@example.test"], {}),  # due on the second morning
    (22, 5, ["not-an-email", "", None], {}),
    (23, 4, ["\u017dlu\u0165ou\u010dk\u00fd@example.test"], {}),
    (24, 4, ["dup@example.test"], {}),  # outbox row with the key exists
]
APARTMENTS = [(1, 13, 4), (2, 14, 4), (3, 15, 40), (4, 16, 40), (5, 17, 40), (6, 18, 40), (7, 19, 4), (8, 19, 1)]
FEEDS = [(1, 2, 4, 0, "error"), (2, 3, 15, 1, "ok"), (3, 4, 15, 1, "ok"), (4, 5, 15, 1, "ok"), (5, 6, 10, 1, "ok")]
RESERVATIONS = [(1, 4, "ical"), (2, 5, "demo")]  # both completed


def build_fixture() -> list:
    users, entities, audits = [], [], []
    for uid, days, emails, extra in HOSTS:
        users.append(
            {"id": uid, "username": f"user{uid}", "password_hash": "x", "role": "host", "active": 1,
             "created_at": ago(100), "onboarding_emails_opt_out": 0, **extra}
        )
        if days is not None:
            hours = -6 if uid == 21 else 0
            audits.append({"id": len(audits) + 1, "at": ago(days, hours), "action": "login", "owner_user_id": uid})
        for email in emails:
            entities.append({"id": len(entities) + 1, "name": f"Entity {len(entities) + 1}",
                             "contact_email": email, "owner_user_id": uid, "created_at": ago(100)})
    audits.append({"id": len(audits) + 1, "at": ago(5), "action": "two_factor_login", "owner_user_id": 8})
    apartments = [{"id": a, "owner_user_id": u, "internal_name": f"Flat {a}", "created_at": ago(d)}
                  for a, u, d in APARTMENTS]
    feeds = [{"id": f, "apartment_id": a, "url": f"https://cal.example.test/{f}.ics", "active": act,
              "last_status": status, "created_at": ago(d)} for f, a, d, act, status in FEEDS]
    reservations = [{"id": r, "apartment_id": a, "source": src, "uid": f"uid-{r}", "date_from": "2026-03-01",
                     "date_to": "2026-03-03", "registration_completed_at": ago(5), "created_at": ago(9),
                     "updated_at": ago(9)} for r, a, src in RESERVATIONS]
    suppression = [{"email_hash": lifecycle_mail.email_hash(a), "scope": "onboarding", "created_at": ago(2)}
                   for a in ("four@example.test", "five-a@example.test")]
    sent = [{"user_account_id": 20, "kind": "lifecycle_no_property", "sent_at": ago(1)}]
    outbox = [{"idempotency_key": "lifecycle:lifecycle_no_property:24:dup@example.test",
               "kind": "lifecycle_no_property", "owner_user_id": 24, "to_email": "dup@example.test",
               "subject": "old", "payload": "{}", "state": "queued", "attempts": 0,
               "created_at": ago(1), "updated_at": ago(1)}]
    return [
        ("user_account", users), ("legal_entity", entities), ("audit", audits), ("apartment", apartments),
        ("ical_feed", feeds), ("reservation", reservations), ("lifecycle_mail_sent", sent),
        ("mail_suppression", suppression), ("email_outbox", outbox),
        ("settings", [{"key": "other_setting", "value": "keep"}]),
    ]


def snapshot(skip: int) -> dict:
    """The state now; ``outbox`` holds only the rows after the first ``skip``."""
    outbox = db.query(
        "SELECT idempotency_key, kind, to_email, cc_email, subject, payload, state, attempts, "
        "owner_user_id, reservation_id, apartment_id FROM email_outbox ORDER BY id"
    )
    sent = db.query("SELECT user_account_id, kind FROM lifecycle_mail_sent ORDER BY user_account_id, kind")
    # init_db seeds its own markers; only the keys this job and the fixture use count.
    settings = db.query(
        "SELECT key, value FROM settings WHERE key IN ('lifecycle_mail_last_day', 'other_setting') ORDER BY key"
    )
    return {
        "outbox_total": len(outbox),
        "outbox": [dict(row) for row in outbox][skip:],
        "sent": [dict(row) for row in sent],
        "settings": [dict(row) for row in settings],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        db.init_db()
        tables = build_fixture()
        for table, rows in tables:
            for row in rows:
                cols = ", ".join(row)
                marks = ", ".join("?" for _ in row)
                db.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))
        runs = []
        seen = 1  # the pre-existing outbox row
        for moment in RUNS:
            summary = lifecycle_mail.run_daily(moment)
            state = snapshot(seen)
            seen = state["outbox_total"]
            runs.append({"now": moment.isoformat(), "summary": summary, **state})
        builds = []
        for kind in lifecycle_mail.mail_notify.LIFECYCLE_ACTIONS:
            for url in (
                "https://www.example.test/mail/unsubscribe/abc?lang=en",
                'https://x.example.test/u?a=1&b="2"&c=<3>',
            ):
                content = mail_notify.build_lifecycle(kind, unsubscribe_url=url, lang="en")
                builds.append({"kind": kind, "unsubscribe_url": url, **content})
        tokens = []
        for user_id, address in (
            (1, "Alpha@Example.Test"),
            (0, ""),
            (123456789, "Second <second@example.test>"),
            (7, "Žluťoučký@example.test"),
            (9, "nope"),
        ):
            tokens.append(
                {
                    "user_id": user_id,
                    "address": address,
                    "hash": lifecycle_mail.email_hash(address),
                    "token": lifecycle_mail.unsubscribe_token(user_id, address),
                    "url": lifecycle_mail.unsubscribe_url(user_id, address, "en"),
                }
            )
        expected = {"env": ENV, "runs": runs, "builds": builds, "tokens": tokens}
        args.out.mkdir(parents=True, exist_ok=True)
        fixture = [{"table": table, "rows": rows} for table, rows in tables]
        (args.out / "fixture.json").write_text(
            json.dumps(fixture, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        (args.out / "expected.json").write_text(
            json.dumps(expected, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

sha256: `8dd3d68c45aec3bb29483d80b7807f89754038d89926265c66bc2e836a1f12c5`

## 5. Do not touch

As in [1235 §5](1235-go-lifecycle-mail.md#5-do-not-touch).

## 6. Commands

As in [1235 §6](1235-go-lifecycle-mail.md#6-commands).

## 7. Acceptance

As in [1235 §7](1235-go-lifecycle-mail.md#7-acceptance).

## 8. Stop and ask

As in [1235 §8](1235-go-lifecycle-mail.md#8-stop-and-ask).

## 9. Report

One report for both parts: [1235 §9](1235-go-lifecycle-mail.md#9-report). Set `Status: review` here too.
