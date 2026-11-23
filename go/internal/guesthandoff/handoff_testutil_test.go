package guesthandoff

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func handoffTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_handoff_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			return
		}
		defer c.Close(context.Background())
		_, _ = c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)")
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal(err)
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("migrations")
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

func handoffTestEnv(k string) string {
	switch k {
	case "UBYHOST_MAIL_BACKEND":
		return "console"
	case "UBYHOST_APP_URL":
		return "https://app.ubyhost.example"
	case "UBYHOST_PUBLIC_URL":
		return "https://stay.example"
	default:
		return ""
	}
}

func handoffSeedApartment(t *testing.T, pool *pgxpool.Pool) (aptID, ownerID, entityID int64) {
	t.Helper()
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00+00:00"
	if err := pool.QueryRow(ctx, `INSERT INTO user_account (username, password_hash, role, active, session_version, created_at, email)
VALUES ('handoff-host', 'x', 'host', 1, 1, $1, 'host@example.test') RETURNING id`, stamp).Scan(&ownerID); err != nil {
		t.Fatal(err)
	}
	contact := "jana@example.test"
	if err := pool.QueryRow(ctx, `INSERT INTO legal_entity (name, owner_user_id, created_at, contact_email)
VALUES ('Jana Host', $1, $2, $3) RETURNING id`, ownerID, stamp, contact).Scan(&entityID); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `INSERT INTO apartment (owner_user_id, legal_entity_id, internal_name, created_at)
VALUES ($1, $2, 'Vinohrady flat', $3) RETURNING id`, ownerID, entityID, stamp).Scan(&aptID); err != nil {
		t.Fatal(err)
	}
	return aptID, ownerID, entityID
}

func handoffInsertQuestion(t *testing.T, pool *pgxpool.Pool, aptID int64, urgent int) int64 {
	t.Helper()
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00+00:00"
	var chatID int64
	if err := pool.QueryRow(ctx, `INSERT INTO guest_chat (apartment_id, door, lang, created_at, last_message_at)
VALUES ($1, 'stay', 'en', $2, $2) RETURNING id`, aptID, stamp).Scan(&chatID); err != nil {
		t.Fatal(err)
	}
	var msgID int64
	if err := pool.QueryRow(ctx, `INSERT INTO guest_chat_message (chat_id, role, text, created_at)
VALUES ($1, 'guest', 'Where is the iron?', $2) RETURNING id`, chatID, stamp).Scan(&msgID); err != nil {
		t.Fatal(err)
	}
	var qID int64
	if err := pool.QueryRow(ctx, `INSERT INTO guest_question (chat_id, apartment_id, message_id, summary, status, urgent, created_at)
VALUES ($1, $2, $3, 'Iron?', 'open', $4, $5) RETURNING id`, chatID, aptID, msgID, urgent, stamp).Scan(&qID); err != nil {
		t.Fatal(err)
	}
	return qID
}

func handoffOutboxCount(t *testing.T, pool *pgxpool.Pool, aptID int64) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(), `SELECT COUNT(*) FROM email_outbox WHERE kind = $1 AND apartment_id = $2`, MailKind, aptID).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

func handoffOpenAlertLevel(t *testing.T, pool *pgxpool.Pool, aptID int64) string {
	t.Helper()
	var level string
	key := dedupeKey(aptID)
	err := pool.QueryRow(context.Background(), `SELECT level FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL`, key).Scan(&level)
	if err != nil {
		t.Fatal(err)
	}
	return level
}