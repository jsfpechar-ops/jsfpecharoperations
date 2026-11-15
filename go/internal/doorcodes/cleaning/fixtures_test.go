package doorcleaning

import (
	"context"
	"errors"
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
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL, applies the goose Up
// sections of App/migrations_pg and drops the database at the end. It skips when the variable
// is unset (the repo norm); when it is set, nothing here skips.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_doorcleaning_%d", time.Now().UnixNano())
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
	files, err := filepath.Glob("../../../../App/migrations_pg/*.sql")
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

// Fakes. None of them reaches the real TTLock API.

var testStart = time.Date(2026, 11, 15, 10, 0, 0, 0, time.UTC)

type fakeClock struct{ t time.Time }

func (c *fakeClock) Now() time.Time { return c.t }

type fakeLock struct {
	enabled bool
	add     func(pin, name string) (string, error)
	named   func(name string) ([]map[string]any, bool, error)
	listed  func(codeID string) (ttlock.TriState, error)
	remove  func(codeID, priority string) error
	adds    []string
	deletes []string
}

// newFakeLock answers every call with an error unless a test sets the function, so an
// unexpected provider call fails the test. CodesNamed defaults to a complete empty list.
func newFakeLock() *fakeLock {
	return &fakeLock{
		enabled: true,
		add:     func(string, string) (string, error) { return "", errors.New("unexpected AddPermanentCode") },
		named:   func(string) ([]map[string]any, bool, error) { return nil, true, nil },
		listed: func(string) (ttlock.TriState, error) {
			return ttlock.TriUnknown, errors.New("unexpected CodeIsListed")
		},
		remove: func(string, string) error { return errors.New("unexpected DeleteCode") },
	}
}

func (f *fakeLock) Enabled() bool { return f.enabled }

func (f *fakeLock) AddPermanentCode(_ context.Context, _ int64, _, pin, name string) (string, error) {
	f.adds = append(f.adds, pin+"/"+name)
	return f.add(pin, name)
}

func (f *fakeLock) CodesNamed(_ context.Context, _ int64, _, name string) ([]map[string]any, bool, error) {
	return f.named(name)
}

func (f *fakeLock) CodeIsListed(_ context.Context, _ int64, _, _, codeID string) (ttlock.TriState, error) {
	return f.listed(codeID)
}

func (f *fakeLock) DeleteCode(_ context.Context, _ int64, _, codeID, priority string) error {
	f.deletes = append(f.deletes, codeID+"/"+priority)
	return f.remove(codeID, priority)
}

// world is a database with one owner, one TTLock account and one ttlock apartment bound to lock 101.
type world struct {
	t     *testing.T
	pool  *pgxpool.Pool
	keys  *secure.MultiFernet
	clock *fakeClock
	lock  *fakeLock
	apt   int64
	acct  int64
}

func newWorld(t *testing.T) *world {
	t.Helper()
	pool := testPool(t)
	keys, err := secure.NewMultiFernet(secure.LegacyKey("doorcleaning-test-secret"))
	if err != nil {
		t.Fatal(err)
	}
	w := &world{t: t, pool: pool, keys: keys, clock: &fakeClock{t: testStart}, lock: newFakeLock()}
	now := iso(testStart)
	ctx := context.Background()
	if _, err := pool.Exec(ctx,
		"INSERT INTO user_account (id, username, password_hash, created_at) VALUES (1, 'owner1', 'x', $1)", now); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx,
		"INSERT INTO lock_account (owner_user_id, provider, username, status, locks_json, created_at, updated_at) "+
			"VALUES (1, 'ttlock', 'owner-login', 'ok', '[]', $1, $1) RETURNING id", now).Scan(&w.acct); err != nil {
		t.Fatal(err)
	}
	w.apt = w.apartment("Invented Flat A", "101", 1)
	if _, err := pool.Exec(ctx,
		"INSERT INTO cleaning_property (apartment_id, updated_at) VALUES ($1, $2)", w.apt, now); err != nil {
		t.Fatal(err)
	}
	return w
}

// apartment inserts an apartment (active 1 or 0) owned by owner with the given lock id.
func (w *world) apartment(name, lockID string, active int) int64 {
	w.t.Helper()
	var id int64
	err := w.pool.QueryRow(context.Background(),
		"INSERT INTO apartment (internal_name, owner_user_id, lock_provider, lock_id, active, created_at) "+
			"VALUES ($1, 1, 'ttlock', $2, $3, $4) RETURNING id",
		name, lockID, active, iso(testStart)).Scan(&id)
	if err != nil {
		w.t.Fatal(err)
	}
	return id
}

// reservation inserts a booking for apt; source and status are as in the reservation table.
func (w *world) reservation(apt int64, uid, from, to, source, status string) int64 {
	w.t.Helper()
	var id int64
	err := w.pool.QueryRow(context.Background(),
		"INSERT INTO reservation (apartment_id, uid, date_from, date_to, source, status, created_at, updated_at) "+
			"VALUES ($1, $2, $3, $4, $5, $6, $7, $7) RETURNING id",
		apt, uid, from, to, source, status, iso(testStart)).Scan(&id)
	if err != nil {
		w.t.Fatal(err)
	}
	return id
}

func (w *world) exec(sql string, args ...any) {
	w.t.Helper()
	if _, err := w.pool.Exec(context.Background(), sql, args...); err != nil {
		w.t.Fatal(err)
	}
}

func (w *world) deps() QueueDeps {
	return QueueDeps{TTLock: w.lock, Cipher: w.keys, Clock: w.clock}
}

func (w *world) encrypt(pin string) string {
	w.t.Helper()
	token, err := w.keys.EncryptString(pin)
	if err != nil {
		w.t.Fatal(err)
	}
	return token
}

// codeSeed describes one cleaning_code row to insert. Empty strings and zero values are NULL.
type codeSeed struct {
	source, state, pin, provider, ref, next, claimed string
	acct                                             int64
	lockID                                           string
	attempts                                         int64
	apt                                              int64 // 0 means the world's apartment
}

func nz(s string) any {
	if s == "" {
		return nil
	}
	return s
}

func (w *world) code(s codeSeed) int64 {
	w.t.Helper()
	apt := s.apt
	if apt == 0 {
		apt = w.apt
	}
	var pin any
	if s.pin != "" {
		pin = w.encrypt(s.pin)
	}
	var acct any
	if s.acct != 0 {
		acct = s.acct
	}
	var id int64
	err := w.pool.QueryRow(context.Background(),
		"INSERT INTO cleaning_code (apartment_id, source, pin_enc, lock_account_id, lock_id, provider_code_id, "+
			"operation_ref, state, attempts, next_attempt_at, claimed_at, created_at, updated_at) "+
			"VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $12) RETURNING id",
		apt, s.source, pin, acct, nz(s.lockID), nz(s.provider), s.ref, s.state, s.attempts,
		nz(s.next), nz(s.claimed), iso(testStart)).Scan(&id)
	if err != nil {
		w.t.Fatal(err)
	}
	return id
}

// pending inserts a ttlock row for the world's apartment and lock, pointed to as pending.
func (w *world) pending(state, pin, ref string, attempts int64) int64 {
	id := w.code(codeSeed{source: "ttlock", state: state, pin: pin, ref: ref, attempts: attempts,
		acct: w.acct, lockID: "101"})
	w.exec("UPDATE cleaning_property SET pending_code_id = $1 WHERE apartment_id = $2", id, w.apt)
	return id
}

func (w *world) setProperty(code, pending *int64) {
	w.t.Helper()
	var c, p any
	if code != nil {
		c = *code
	}
	if pending != nil {
		p = *pending
	}
	w.exec("UPDATE cleaning_property SET code_id = $1, pending_code_id = $2 WHERE apartment_id = $3", c, p, w.apt)
}

// property returns the code and pending code ids of the world's apartment (nil for NULL).
func (w *world) property() (*int64, *int64) {
	w.t.Helper()
	var code, pending *int64
	err := w.pool.QueryRow(context.Background(),
		"SELECT code_id, pending_code_id FROM cleaning_property WHERE apartment_id = $1", w.apt).Scan(&code, &pending)
	if err != nil {
		w.t.Fatal(err)
	}
	return code, pending
}

func (w *world) read(id int64) codeRow {
	w.t.Helper()
	c, err := scanCode(w.pool.QueryRow(context.Background(),
		"SELECT "+codeColumns+" FROM cleaning_code WHERE id = $1", id))
	if err != nil {
		w.t.Fatal(err)
	}
	return c
}

func (w *world) runQueue() int {
	w.t.Helper()
	n, err := ProcessQueue(context.Background(), w.pool, w.deps())
	if err != nil {
		w.t.Fatalf("ProcessQueue: %v", err)
	}
	return n
}

// ttlockErr is a TTLockError of the given kind, as the client reports it.
func ttlockErr(kind string) error {
	return &ttlock.TTLockError{Kind: kind, Message: "invented " + kind}
}
