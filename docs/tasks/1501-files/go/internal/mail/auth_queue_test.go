package mail

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// These tests need UBYHOST_TEST_DATABASE_URL (accountTestPool skips without it).

func accountTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_mail_account_%d", time.Now().UnixNano())
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

var accountNow = time.Date(2026, 11, 14, 9, 0, 0, 0, time.UTC)

func accountEnv(g accountGolden, backend string) func(string) string {
	return func(k string) string {
		if k == "UBYHOST_MAIL_BACKEND" {
			return backend
		}
		return g.Env[k]
	}
}

type outboxRow struct {
	kind, to, subject, payload, state string
	owner                             *int64
}

func outbox(t *testing.T, pool *pgxpool.Pool, key string) (outboxRow, bool) {
	t.Helper()
	var r outboxRow
	err := pool.QueryRow(context.Background(), `SELECT kind, to_email, subject, payload, state, owner_user_id
		FROM email_outbox WHERE idempotency_key = $1`, key).Scan(&r.kind, &r.to, &r.subject, &r.payload, &r.state, &r.owner)
	if err == pgx.ErrNoRows {
		return r, false
	}
	if err != nil {
		t.Fatal(err)
	}
	return r, true
}

func outboxCount(t *testing.T, pool *pgxpool.Pool) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(), `SELECT COUNT(*) FROM email_outbox`).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func addHost(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), `INSERT INTO user_account (id, username, password_hash, created_at)
		VALUES (7, 'host7', 'x', '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
}

func goldenMail(t *testing.T, g accountGolden, builder, kind, lang string, minutes int) (string, string, string) {
	t.Helper()
	for _, m := range g.Mails {
		if m.Builder == builder && m.Kind == kind && m.Lang == lang && m.Minutes == minutes {
			return m.Subject, m.Text, m.HTML
		}
	}
	t.Fatalf("no golden %s %s %s %d", builder, kind, lang, minutes)
	return "", "", ""
}

// TestQueueLinkMail is link_mail end to end: the row Python writes, the
// token only encrypted beside the marker, one row per token, nothing while
// mail is off or the address is invalid.
func TestQueueLinkMail(t *testing.T) {
	pool := accountTestPool(t)
	ctx := context.Background()
	g := loadAccountGolden(t)
	env := accountEnv(g, "console")
	addHost(t, pool)
	token := g.Payloads.LinkKeyToken
	id, err := QueueLinkMail(ctx, pool, env, KindLoginLink, 7, " Host@Example.CZ ", token, 15, "CS-cz", accountNow)
	if err != nil || id == 0 {
		t.Fatalf("QueueLinkMail = %d, %v", id, err)
	}
	row, ok := outbox(t, pool, g.Payloads.LinkKey)
	if !ok {
		t.Fatal("no row under the Python key")
	}
	subject, text, html := goldenMail(t, g, "link", KindLoginLink, "CS-cz", 15)
	if row.kind != KindLoginLink || row.to != "host@example.cz" || row.subject != subject || row.state != "queued" ||
		row.owner == nil || *row.owner != 7 {
		t.Fatalf("row %+v", row)
	}
	var p map[string]*string
	if err := json.Unmarshal([]byte(row.payload), &p); err != nil {
		t.Fatal(err)
	}
	if p["text"] == nil || *p["text"] != text || *p["html"] != html || *p["lang"] != "cs" || p[claimSecretKey] == nil {
		t.Fatal("payload differs from Python")
	}
	if strings.Contains(row.payload, token) || !strings.Contains(*p["text"], ClaimSecretMarker) {
		t.Fatal("the token is in the stored body")
	}
	keys, err := secure.LoadDataKeys(env)
	if err != nil {
		t.Fatal(err)
	}
	plain, err := keys.Decrypt(*p[claimSecretKey], 0, accountNow)
	if err != nil || string(plain) != token {
		t.Fatal("claim_secret_enc does not decrypt to the token")
	}
	want := accountPayloadJSON([]payloadField{{"text", strPtr(text)}, {"html", strPtr(html)}, {"lang", strPtr("cs")},
		{claimSecretKey, p[claimSecretKey]}})
	if row.payload != want {
		t.Fatal("payload is not json.dumps of the Python dict")
	}
	again, err := QueueLinkMail(ctx, pool, env, KindLoginLink, 7, "host@example.cz", token, 15, "cs", accountNow)
	if err != nil || again != id || outboxCount(t, pool) != 1 {
		t.Fatalf("same token: %d %v, want the same row", again, err)
	}
	if n, err := QueueLinkMail(ctx, pool, accountEnv(g, ""), KindLoginLink, 7, "host@example.cz", "other", 15, "", accountNow); n != 0 || err != nil {
		t.Fatalf("mail off: %d %v", n, err)
	}
	if n, err := QueueLinkMail(ctx, pool, env, KindAccountInvite, 7, "not an address", "other", 4320, "", accountNow); n != 0 || err != nil {
		t.Fatalf("bad address: %d %v", n, err)
	}
	if _, err := QueueLinkMail(ctx, pool, env, "reset", 7, "host@example.cz", "x", 15, "", accountNow); err != ErrUnknownMail {
		t.Fatalf("unknown kind: %v", err)
	}
	if outboxCount(t, pool) != 1 {
		t.Fatal("extra rows")
	}
}

// TestQueueNotices: email_changed (both sides, notify_new off), passkey_added
// and workspace_deletion (one row per distinct contact address).
func TestQueueNotices(t *testing.T) {
	pool := accountTestPool(t)
	ctx := context.Background()
	g := loadAccountGolden(t)
	env := accountEnv(g, "ses")
	addHost(t, pool)
	n, err := QueueEmailChanged(ctx, pool, env, 7, "old@example.cz", "new.address@example.cz", "2026-11-14T09:00:00+00:00", "self", true, accountNow)
	if err != nil || n != 2 {
		t.Fatalf("email_changed = %d %v", n, err)
	}
	old, ok1 := outbox(t, pool, "email_changed:7:2026-11-14T09:00:00+00:00:old")
	_, ok2 := outbox(t, pool, "email_changed:7:2026-11-14T09:00:00+00:00:new")
	if !ok1 || !ok2 || old.to != "old@example.cz" {
		t.Fatal("email_changed rows")
	}
	c, _ := BuildEmailChanged(accountPublicBase(env), accountOperatorEmail(env), "old", g.MaskedNew, "", "self")
	if old.payload != accountPayloadJSON(noticePayload(c, env)) || old.subject != c.Subject {
		t.Fatal("email_changed payload")
	}
	if n, err := QueueEmailChanged(ctx, pool, env, 7, "old@example.cz", "x@example.cz", "s2", "support", false, accountNow); n != 1 || err != nil {
		t.Fatalf("notify_new off: %d %v", n, err)
	}
	if id, err := QueuePasskeyAdded(ctx, pool, env, 7, "host@example.cz", 3, "MacBook", accountNow); id == 0 || err != nil {
		t.Fatalf("passkey: %d %v", id, err)
	}
	if _, ok := outbox(t, pool, "passkey_added:7:3"); !ok {
		t.Fatal("passkey row")
	}
	if id, err := QueuePasskeyAdded(ctx, pool, env, 7, "", 4, "x", accountNow); id != 0 || err != nil {
		t.Fatalf("no address: %d %v", id, err)
	}
	for i, addr := range []any{"Billing@Example.cz", nil, "billing@example.cz", "x", "second@example.cz"} {
		if _, err := pool.Exec(ctx, `INSERT INTO legal_entity (id, name, contact_email, owner_user_id, created_at)
			VALUES ($1, 'E', $2, 7, '2026-01-01T00:00:00+00:00')`, i+1, addr); err != nil {
			t.Fatal(err)
		}
	}
	n, err = QueueWorkspaceDeletion(ctx, pool, env, 7, "2027-01-05T10:00:00+00:00", DeletionWeekBefore, accountNow)
	if err != nil || n != 2 {
		t.Fatalf("workspace_deletion = %d %v", n, err)
	}
	del, ok := outbox(t, pool, "workspace_deletion:7:2027-01-05T10:00:00+00:00:week_before:billing@example.cz")
	if !ok || !strings.Contains(del.subject, "05.01.2027") {
		t.Fatalf("deletion row %+v", del)
	}
	if _, err := QueueWorkspaceDeletion(ctx, pool, env, 7, "2027-01-05", "tomorrow", accountNow); err != ErrUnknownMail {
		t.Fatalf("unknown stage: %v", err)
	}
}
