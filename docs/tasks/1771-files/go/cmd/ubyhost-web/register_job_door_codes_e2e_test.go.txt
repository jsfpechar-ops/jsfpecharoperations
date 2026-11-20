package main

// End to end: the door-codes job handler, with real Postgres, a fake TTLock gateway on httptest
// and the console mail backend. No network leaves the test.

import (
	"context"
	"encoding/base64"
	"net/http"
	"net/http/httptest"
	"os"
	"sync/atomic"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"
)

// fakeTTLockGateway answers every TTLock call with a successful body and counts the calls.
func fakeTTLockGateway(t *testing.T) (*httptest.Server, *atomic.Int64) {
	t.Helper()
	var calls atomic.Int64
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"errcode":0,"access_token":"tok","refresh_token":"ref","expires_in":7200,` +
			`"uid":1,"date":1795000000000,"keyboardPwd":"123456","keyboardPwdId":42,"list":[]}`))
	}))
	t.Cleanup(srv.Close)
	return srv, &calls
}

// setDoorCodeEnv switches the door-code job on and points TTLock at the fake gateway.
func setDoorCodeEnv(t *testing.T, apiBase, doorCodes string) {
	t.Helper()
	t.Setenv("UBYHOST_DOOR_CODES", doorCodes)
	t.Setenv("UBYHOST_DOOR_CODES_LIVE", "1")
	t.Setenv("UBYHOST_TTLOCK_API_BASE", apiBase)
	t.Setenv("UBYHOST_TTLOCK_CLIENT_ID", "test-client")
	t.Setenv("UBYHOST_TTLOCK_CLIENT_SECRET", "test-secret")
	t.Setenv("UBYHOST_DATA_KEYS", base64.URLEncoding.EncodeToString([]byte("0123456789abcdef0123456789abcdef")))
	t.Setenv("UBYHOST_DATA_KEY_LEGACY", "0")
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	t.Setenv("UBYHOST_BILLING_ENABLED", "1")
}

// seedDoorCodeStay is a registered, eligible stay: owner with a max plan, a lock_account, a
// TTLock apartment, the stay (today to three days on) and a confirmed claim with the guest's address.
func seedDoorCodeStay(t *testing.T, pool *pgxpool.Pool, keys *secure.MultiFernet, now time.Time) int64 {
	t.Helper()
	ctx := context.Background()
	stamp := now.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05") + "+00:00"
	exec := func(sql string, args ...any) {
		t.Helper()
		if _, err := pool.Exec(ctx, sql, args...); err != nil {
			t.Fatalf("seed: %v", err)
		}
	}
	exec("INSERT INTO user_account (id, username, password_hash, created_at) VALUES (7, 'owner7', 'x', $1)", stamp)
	exec("INSERT INTO billing_account (owner_user_id, status, plan, updated_at) VALUES (7, 'active', 'max', $1)", stamp)
	accounts := doorcodes.NewAccountStore(pool, keys)
	accountID, err := accounts.Insert(ctx, 7, "uhx", "password", now)
	if err != nil {
		t.Fatalf("seed lock account: %v", err)
	}
	// A stored login, so the client does not need the OAuth round trip.
	rec := ttlock.TokenRecord{AccessToken: "tok", RefreshToken: "ref", ExpiresAt: now.Add(30 * 24 * time.Hour)}
	if err := accounts.SaveLogin(ctx, accountID, rec, now); err != nil {
		t.Fatalf("seed login: %v", err)
	}
	var apt int64
	if err := pool.QueryRow(ctx,
		"INSERT INTO apartment (internal_name, owner_user_id, lock_provider, lock_id, checkin_hour, checkout_hour, created_at) "+
			"VALUES ('Test flat', 7, 'ttlock', '555', 14, 10, $1) RETURNING id", stamp).Scan(&apt); err != nil {
		t.Fatalf("seed apartment: %v", err)
	}
	from := now.Format("2006-01-02")
	to := now.AddDate(0, 0, 3).Format("2006-01-02")
	var res int64
	if err := pool.QueryRow(ctx,
		"INSERT INTO reservation (apartment_id, uid, date_from, date_to, registration_completed_at, status, source, created_at, updated_at) "+
			"VALUES ($1, 'uid-e2e-door-code', $2, $3, $4, 'active', 'manual', $4, $4) RETURNING id",
		apt, from, to, stamp).Scan(&res); err != nil {
		t.Fatalf("seed reservation: %v", err)
	}
	exec("INSERT INTO reservation_claim (reservation_id, state, email, lang, completion_notified_at, created_at, updated_at) "+
		"VALUES ($1, 'claimed', 'guest@example.test', 'en', $2, $2, $2)", res, stamp)
	return res
}

func TestDoorCodesJobIssuesCodeThroughHandler(t *testing.T) {
	pool := mailJobTestPool(t)
	ctx := context.Background()
	gateway, calls := fakeTTLockGateway(t)
	setDoorCodeEnv(t, gateway.URL, "1")

	keys, err := secure.LoadDataKeys(os.Getenv)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Now().UTC()
	res := seedDoorCodeStay(t, pool, keys, now)

	n, err := doorCodesHandler(pool)(ctx)
	if err != nil {
		t.Fatalf("handler: %v", err)
	}
	if calls.Load() == 0 {
		t.Fatal("the gateway was never called")
	}
	var state string
	if err := pool.QueryRow(ctx, "SELECT state FROM door_code WHERE reservation_id = $1", res).Scan(&state); err != nil {
		t.Fatalf("door_code row: %v", err)
	}
	if state != doorcodes.StateIssued {
		t.Fatalf("door_code state %q, want %q (handler returned %d)", state, doorcodes.StateIssued, n)
	}
	var queued int
	if err := pool.QueryRow(ctx,
		"SELECT COUNT(*) FROM email_outbox WHERE kind = 'door_code' AND reservation_id = $1", res).Scan(&queued); err != nil {
		t.Fatal(err)
	}
	if queued == 0 {
		t.Fatal("no door_code mail reached the outbox")
	}
}

func TestDoorCodesJobOffDoesNothingAgainstDatabase(t *testing.T) {
	pool := mailJobTestPool(t)
	ctx := context.Background()
	gateway, calls := fakeTTLockGateway(t)
	setDoorCodeEnv(t, gateway.URL, "")

	keys, err := secure.LoadDataKeys(os.Getenv)
	if err != nil {
		t.Fatal(err)
	}
	res := seedDoorCodeStay(t, pool, keys, time.Now().UTC())

	n, err := doorCodesHandler(pool)(ctx)
	if n != 0 || err != nil {
		t.Fatalf("off: n=%d err=%v", n, err)
	}
	if calls.Load() != 0 {
		t.Fatalf("off: the gateway was called %d times", calls.Load())
	}
	var rows, outbox int
	if err := pool.QueryRow(ctx, "SELECT COUNT(*) FROM door_code WHERE reservation_id = $1", res).Scan(&rows); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, "SELECT COUNT(*) FROM email_outbox WHERE reservation_id = $1", res).Scan(&outbox); err != nil {
		t.Fatal(err)
	}
	if rows != 0 || outbox != 0 {
		t.Fatalf("off: door_code rows %d, outbox rows %d, want 0 and 0", rows, outbox)
	}
}
