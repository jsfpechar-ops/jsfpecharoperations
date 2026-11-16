# 1794a: Clash refund that failed is recorded durably (Go booking webhook)

Status: todo
Depends on: 1796, 1797 (both already committed on the working branch; anchors below were checked against 223ab1c) | Base commit: 223ab1c or the later tip of the working branch | Branch: task/1794a-go-clash-refund-due
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier: A (money path and a migration; exact diffs only; a fresh reviewer reads the full diff of every file in section 3)
Second half: [1794b](1794b-go-clash-refund-sweep-alert.md) (stripe_sweep retry and the operator alert). Plan: `docs/plans/ai-payments-hardening.md`, "P1 Fix before Stripe goes live", item 3.

## 1. Objective

When two guests pay for the same nights, the Go booking webhook refunds the second one; if that refund fails today, nothing durable remembers it, and once Stripe stops retrying the guest has paid with no booking and no refund. This brief writes a `site_booking_refund_due` row in the same transaction that decides the clash, counts each failed try on it (never a try blocked by the Stripe call cap), and deletes it when the refund goes through; 1794b adds the daily retry and the operator alert.

## 2. Context

**Rules that apply (pasted).**
- AGENTS.md 2: privacy first; a new personal-data field needs a line in `App/app/retention.py`. This brief stores none (ids, a count, stamps, a Stripe error code), so no retention line. Never log or store the guest's name or e-mail.
- AGENTS.md 5 / rules.md "Database": schema changes are goose files only, `App/migrations_pg/NNNNN_name.sql`, next number = highest + 1 (today `00018_submission_cause.sql`, so **00019**); additive only, the previous image must keep working; after adding one, rerun `App/scripts/pg_schema_golden.py`.
- rules.md "State machines": every stored state/status column has one TRANSITIONS table. This brief adds **no** status value: `site_booking.status` keeps its values (`go/internal/statemachine/tables.go` "site_booking.status", `bookingTransitions` in `booking_webhook.go`, Python `booking_site._TRANSITIONS`). "Refund due" is the existence of a row in a new table with no `*state`/`*status` column, so `App/tests/test_sm_registry.py` (regex `(^|_)(state|status)$`) needs no entry.
- Owner decisions 2026-11-16 (recorded in 1797): **Go only**, no Python change now or as a follow-up; the Go booking webhook goes live (`UBYHOST_GO_BOOKING_WEBHOOK=1`) only after 1792, 1793 and 1794 are merged and green; no backfill (Stripe is in test mode).

**Why a new table and not a status value or new columns (verified).**
- A goose-only `ADD COLUMN` on `site_booking` breaks Python's start-up check: `App/app/db.py` `postgres_schema_status` counts a column-count difference on any table of the frozen SQLite schema as `column_mismatches`, and `validate_postgres_schema_connection` then raises "PostgreSQL schema is absent, outdated, or incompatible." An extra table only raises `extra_tables`, which keeps `current` true (`App/tests/test_goose_migrations.py::test_a_table_outside_the_baseline_keeps_the_schema_current`; goose-only table precedent: `00003_job.sql`).
- A new `site_booking.status` value would need the Python `_TRANSITIONS` twin in the same PR (rules: a column written in both languages changes in both) and the previous image, on rollback, would fail `refund_due -> clash_refunded` as an illegal move.

**Live path today.** `go/internal/payments/booking_webhook.go` runs only when `UBYHOST_GO_BOOKING_WEBHOOK=1`; otherwise Go forwards booking events to Python (`App/app/booking_webhook.py`), which keeps the bug (owner: not patched). `deploy/lightsail/docker-compose.yml` does not pass `UBYHOST_GO_BOOKING_WEBHOOK` to `ubyhost-go` and `docs/ENVIRONMENT.md` has no row for it (brief 1554 owns both). So this fix protects production only after the 1554 switch; Stripe is in test mode, so no real guest is exposed now.

**Idempotency (already there, kept).** Every refund try sends `Idempotency-Key: site_booking_clash_refund_<booking id>`; Python sends the same key (`App/app/booking_webhook.py:115`), and the golden test pins it. Stripe returns the first result for a repeated key, so a webhook retry, the 1794b sweeper or a Python try can never refund twice. Note (Stripe docs, not verifiable offline): Stripe also replays a cached *error* for about 24 hours, so a retry with the same key inside 24 h usually repeats the first error; the daily 1794b retry is a real new try.

**Stripe call cap.** `guard` in `go/internal/payments/onboarder.go` returns `ErrStripeOff` when the mode is off, the key does not match the mode (1796), or this month's `lock_api_usage` count reached `UBYHOST_STRIPE_MONTHLY_API_CALLS` (default 50000); it counts the call before the HTTP request. A `guard` error is **not** a failed try here: nothing is counted, the row stays due.

**Excerpts (anchors; if one is not found verbatim, STOP, section 8).** All in `go/internal/payments/booking_webhook.go`.

A. In `confirm`, inside the transaction (the `tx.Exec` line is unique; `expire` uses `b.Pool`):
```go
	if bk.holdID != nil && *bk.holdID != 0 {
		if _, err := tx.Exec(ctx, bookingHoldDeleteSQL, *bk.holdID); err != nil {
```
B. The `refundClash` comment:
```go
// refundClash is _refund_clash: a full refund on the host's connected account.
// Any failure is returned, so the webhook answers 500 and Stripe retries.
```
C. In `refundClash`:
```go
		return fmt.Errorf("site booking %d: cannot refund (no account or intent)", bk.id)
```
D. In `refundClash`:
```go
	if err := b.refund(ctx, key, account, fmt.Sprintf("site_booking_clash_refund_%d", bk.id), form); err != nil {
		return err
	}
	if _, err := b.setStatus(ctx, bk.id, "clash_refunded", []bookingField{
		{"refunded_czk", bk.totalCZK}, {"stripe_payment_intent_id", intent},
	}); err != nil {
		return err
	}
```
E. In `refund`:
```go
		return fmt.Errorf("stripe: POST /v1/refunds: HTTP %d: %s (%s)", resp.StatusCode,
			se.Error.Message, se.Error.Code)
```

Test helpers that already exist in package `payments` (do not redefine): `testPool`, `applyMigrations` (sweep_test.go), `count`, `testNow` (webhook_test.go, `testNow` = 2026-09-21T14:13:20Z), `loadBookingGolden`, `seedBookingGolden`, `bookingEnv`, `bookingGolden` (booking_webhook_test.go). Golden seed: booking 4 is on apartment 11, whose dates clash with active stay 50; host user 1 has `acct_golden1` (mode test); hold 204; total 4000.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/migrations_pg/00019_site_booking_refund_due.sql` | create | new table `site_booking_refund_due` (step 1) |
| `go/internal/schema/expected_schema.json` | regenerate | only via `pg_schema_golden.py` (step 2), if it changes |
| `go/internal/schema/testdata/goose_statements_golden.json` | regenerate | only via `pg_schema_golden.py` (step 2) |
| `go/internal/schema/testdata/fingerprint_golden.json` | regenerate | only via `pg_schema_golden.py` (step 2), if it changes |
| `go/internal/payments/booking_refund_due.go` | create | helpers (step 3) |
| `go/internal/payments/booking_webhook.go` | edit | anchors A to E (steps 4 to 8) |
| `go/internal/payments/booking_refund_due_test.go` | create | tests (step 9) |
| `docs/tasks/1794a-report.md` | create | report (section 9) |

No other file may change. Nothing under `App/app/` changes (go-first: Go only).

## 4. Steps

Run each step's command and the commit in one Bash call: `<command> 2>&1 | tail -30; git add -A && git commit -qm "1794a step k"`.

1. Create `App/migrations_pg/00019_site_booking_refund_due.sql` with exactly:
```sql
-- +goose Up
-- Brief 1794a: a booking-site clash whose refund has not gone through yet.
-- Goose-only (App/app/migrations is frozen) and no schema_migrations row, like 00017 and 00018.
-- A new table, so the schema check counts it as an extra table and stays current,
-- and the previous image ignores it. No personal data: ids, a count, stamps and a
-- Stripe error code. The row is deleted once the refund went through or the booking
-- was paid after all, and with the booking (foreign-key cascade).
CREATE TABLE IF NOT EXISTS site_booking_refund_due (
    site_booking_id   BIGINT PRIMARY KEY REFERENCES site_booking(id) ON DELETE CASCADE,
    payment_intent_id TEXT COLLATE "C",
    attempts          BIGINT NOT NULL DEFAULT 0,
    next_attempt_at   TEXT COLLATE "C" NOT NULL,
    last_error        TEXT COLLATE "C",
    alerted_at        TEXT COLLATE "C",
    created_at        TEXT COLLATE "C" NOT NULL,
    updated_at        TEXT COLLATE "C" NOT NULL
);

-- +goose Down
DROP TABLE IF EXISTS site_booking_refund_due;
```
   Command: `ls App/migrations_pg/ | tail -2` shows `00018_submission_cause.sql` then `00019_site_booking_refund_due.sql`.

2. Regenerate the schema fixtures. If `App/.venv/bin/python` does not exist, first run `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r ../requirements.txt 2>&1 | tail -5` (existing requirements only). Command: `cd App && .venv/bin/python scripts/pg_schema_golden.py 2>&1 | tail -5 && .venv/bin/python scripts/pg_schema_golden.py --check 2>&1 | tail -5; echo check_exit=$?; cd .. && git status --short | head -20`. Expect `check_exit=0`; changed files only among the three `go/internal/schema/` files of section 3.

3. Create `go/internal/payments/booking_refund_due.go` with exactly (tabs for indentation), then `gofmt -w` it:
```go
package payments

// Clash refunds that have not gone through yet (brief 1794a, plan
// ai-payments-hardening P1 item 3). confirm writes a site_booking_refund_due
// row in the transaction that finds the clash; refundClash counts each failed
// try on it and deletes it once the refund went through. Every try sends the
// same Idempotency-Key, so Stripe refunds a booking at most once. The row
// holds no personal data: ids, a count, stamps and a Stripe error code.

import (
	"context"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

const (
	// refundDueMaxBackoff caps the wait between two tries.
	refundDueMaxBackoff = 24 * time.Hour

	refundDueInsertSQL = `INSERT INTO site_booking_refund_due (site_booking_id, payment_intent_id,
		attempts, next_attempt_at, created_at, updated_at) VALUES ($1, $2, 0, $3, $3, $3)
		ON CONFLICT (site_booking_id) DO UPDATE SET payment_intent_id =
		COALESCE(site_booking_refund_due.payment_intent_id, excluded.payment_intent_id)`
	refundDueDeleteSQL = `DELETE FROM site_booking_refund_due WHERE site_booking_id = $1`
	refundDueFailSQL   = `UPDATE site_booking_refund_due SET attempts = attempts + 1, last_error = $2,
		updated_at = $3 WHERE site_booking_id = $1 RETURNING attempts`
	refundDueNextSQL = `UPDATE site_booking_refund_due SET next_attempt_at = $2 WHERE site_booking_id = $1`
)

// refundIdempotencyKey is the Idempotency-Key of every clash refund try for a
// booking. Python's _refund_clash sends the same key, so a Python try, a Go
// webhook retry and stripe_sweep can never refund twice.
func refundIdempotencyKey(bookingID int64) string {
	return fmt.Sprintf("site_booking_clash_refund_%d", bookingID)
}

// refundError is a non-2xx answer of POST /v1/refunds. Error() is the text the
// webhook returned before 1794; only the status and the code are stored.
type refundError struct {
	status        int
	message, code string
}

func (e *refundError) Error() string {
	return fmt.Sprintf("stripe: POST /v1/refunds: HTTP %d: %s (%s)", e.status, e.message, e.code)
}

// refundErrorCode is the last_error stored for a failed try:
// "http_<status>:<code>" for a Stripe answer (the code lower-cased, reduced to
// a-z, 0-9 and _, at most 64 characters, "none" when empty) and "request"
// for anything else (timeout, network). Stripe's message is never stored.
func refundErrorCode(err error) string {
	var re *refundError
	if !errors.As(err, &re) {
		return "request"
	}
	code := strings.Map(func(r rune) rune {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '_' {
			return r
		}
		return -1
	}, strings.ToLower(re.code))
	if len(code) > 64 {
		code = code[:64]
	}
	if code == "" {
		code = "none"
	}
	return fmt.Sprintf("http_%d:%s", re.status, code)
}

// refundBackoff is the wait after the n-th failed try: 1 h, 2 h, 4 h, 8 h,
// 16 h, then refundDueMaxBackoff.
func refundBackoff(n int64) time.Duration {
	d := time.Hour
	for i := int64(1); i < n && d < refundDueMaxBackoff; i++ {
		d *= 2
	}
	return min(d, refundDueMaxBackoff)
}

// markRefundDue runs in confirm's transaction. A clash records the refund as
// due (a retry keeps the row and only fills a missing intent); a booking that
// is paid after all no longer owes one.
func markRefundDue(ctx context.Context, q dbtx, bookingID int64, intent string, clash bool, stamp string) error {
	if !clash {
		_, err := q.Exec(ctx, refundDueDeleteSQL, bookingID)
		return err
	}
	var pi *string
	if intent != "" {
		pi = &intent
	}
	_, err := q.Exec(ctx, refundDueInsertSQL, bookingID, pi, stamp)
	return err
}

// refundFailed counts one failed try and sets the next one. It only logs its
// own errors: the caller returns the refund error, so Stripe retries anyway.
func (b *BookingWebhook) refundFailed(ctx context.Context, bookingID int64, code string) {
	now := b.Now()
	var n int64
	err := b.Pool.QueryRow(ctx, refundDueFailSQL, bookingID, code, stampAt(now)).Scan(&n)
	if errors.Is(err, pgx.ErrNoRows) {
		return
	}
	if err != nil {
		log.Printf("clash refund: count failed try for site booking %d: %v", bookingID, err)
		return
	}
	if _, err := b.Pool.Exec(ctx, refundDueNextSQL, bookingID, stampAt(now.Add(refundBackoff(n)))); err != nil {
		log.Printf("clash refund: set next try for site booking %d: %v", bookingID, err)
	}
}

// refundDone removes the row once the booking is clash_refunded (or paid).
func (b *BookingWebhook) refundDone(ctx context.Context, bookingID int64) error {
	_, err := b.Pool.Exec(ctx, refundDueDeleteSQL, bookingID)
	return err
}
```
   Command: `gofmt -w go/internal/payments/booking_refund_due.go && cd go && go build ./internal/payments/` : no output.

4. `booking_webhook.go`, anchor A. Replace
```go
	if bk.holdID != nil && *bk.holdID != 0 {
		if _, err := tx.Exec(ctx, bookingHoldDeleteSQL, *bk.holdID); err != nil {
```
   with
```go
	// 1794a: the clash and its refund-due row commit together, so a refund that
	// then fails is never forgotten.
	if err := markRefundDue(ctx, tx, bk.id, intent, clash, stamp); err != nil {
		return err
	}
	if bk.holdID != nil && *bk.holdID != 0 {
		if _, err := tx.Exec(ctx, bookingHoldDeleteSQL, *bk.holdID); err != nil {
```
   Command: `cd go && go build ./internal/payments/` : no output.

5. Anchor B. Replace the two comment lines with
```go
// refundClash is _refund_clash: a full refund on the host's connected account.
// Any failure is returned, so the webhook answers 500 and Stripe retries. A
// failed try is counted on the site_booking_refund_due row confirm wrote; a
// closed Stripe (off, key and mode apart, or the monthly call cap reached) is
// not a try and is not counted. Only the run that moves the booking to
// clash_refunded writes the audit line and the mails.
```
   Command: `grep -c 'site_booking_refund_due row confirm wrote' go/internal/payments/booking_webhook.go` prints `1`.

6. Anchor C. Replace the line with
```go
		b.refundFailed(ctx, bk.id, "no_account_or_intent")
		return fmt.Errorf("site booking %d: cannot refund (no account or intent)", bk.id)
```
   Command: `cd go && go build ./internal/payments/` : no output.

7. Anchor D. Replace the whole block with
```go
	if err := b.refund(ctx, key, account, refundIdempotencyKey(bk.id), form); err != nil {
		b.refundFailed(ctx, bk.id, refundErrorCode(err))
		return err
	}
	moved, err := b.setStatus(ctx, bk.id, "clash_refunded", []bookingField{
		{"refunded_czk", bk.totalCZK}, {"stripe_payment_intent_id", intent},
	})
	if err != nil {
		return err
	}
	if err := b.refundDone(ctx, bk.id); err != nil {
		return err
	}
	if !moved {
		return nil // a webhook retry or stripe_sweep finished it first
	}
```
   Leave the `audit(...)` call and the final `return b.mailClash(...)` line after it unchanged. Command: `cd go && go build ./internal/payments/` : no output.

8. Anchor E. Replace the two lines with
```go
		return &refundError{status: resp.StatusCode, message: se.Error.Message, code: se.Error.Code}
```
   Command: `cd go && go build ./... && go vet ./internal/payments/` : no output.

9. Create `go/internal/payments/booking_refund_due_test.go` with exactly (1794b appends to it):
```go
package payments

// Tests for clash refunds that have not gone through (brief 1794a). They use
// the golden seed of booking_webhook_test.go: booking 4 is on apartment 11,
// whose dates clash with the active stay 50; its host (user 1) has the
// connected account acct_golden1; its hold is 204, its payment intent pi_4.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// refundStub is a fake Stripe POST /v1/refunds that keeps Stripe's promise
// for a key that already succeeded: the same refund comes back and no new one
// is made. While fail is above 0, a call answers 402 card_declined.
type refundStub struct {
	mu      sync.Mutex
	fail    int
	calls   []string          // Idempotency-Key of every call, in order
	refunds map[string]string // key -> refund id, one per key that succeeded
}

func newRefundStub(t *testing.T, fail int) (*refundStub, *httptest.Server) {
	t.Helper()
	s := &refundStub{fail: fail, refunds: map[string]string{}}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		s.mu.Lock()
		defer s.mu.Unlock()
		if r.Method != http.MethodPost || r.URL.Path != "/v1/refunds" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		key := r.Header.Get("Idempotency-Key")
		s.calls = append(s.calls, key)
		if id, ok := s.refunds[key]; ok {
			_, _ = io.WriteString(w, `{"id":"`+id+`","status":"succeeded"}`)
			return
		}
		if s.fail > 0 {
			s.fail--
			w.WriteHeader(http.StatusPaymentRequired)
			_, _ = io.WriteString(w, `{"error":{"message":"fake Stripe error","code":"card_declined"}}`)
			return
		}
		id := fmt.Sprintf("re_%d", len(s.refunds)+1)
		s.refunds[key] = id
		_, _ = io.WriteString(w, `{"id":"`+id+`","status":"succeeded"}`)
	}))
	t.Cleanup(srv.Close)
	return s, srv
}

// seen returns the keys of all calls so far and the number of refunds made.
func (s *refundStub) seen() ([]string, int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]string(nil), s.calls...), len(s.refunds)
}

// clashEvent4 is checkout.session.completed, paid, for golden booking 4.
func clashEvent4(t *testing.T) stripeEvent {
	t.Helper()
	raw := `{"id":"evt_rd_4","type":"checkout.session.completed","data":{"object":{"id":"cs_4","payment_status":"paid","payment_intent":"pi_4","metadata":{"site_booking_id":"4"}}}}`
	var ev stripeEvent
	if err := json.Unmarshal([]byte(raw), &ev); err != nil {
		t.Fatal(err)
	}
	return ev
}

// refundDueHandler is the booking handler with its clock at at and Stripe at base.
func refundDueHandler(pool *pgxpool.Pool, g bookingGolden, base string, at time.Time, extra map[string]string) *BookingWebhook {
	bw := NewBookingWebhook(pool, bookingEnv(g, extra), func() time.Time { return at })
	bw.Stripe.APIBase = base
	return bw
}

// dueRow is one site_booking_refund_due row; NULL text reads as "".
type dueRow struct {
	Attempts                             int64
	Intent, LastError, AlertedAt, NextAt string
}

func readDue(t *testing.T, pool *pgxpool.Pool, id int64) (dueRow, bool) {
	t.Helper()
	var d dueRow
	err := pool.QueryRow(context.Background(), `SELECT attempts, COALESCE(payment_intent_id, ''),
		COALESCE(last_error, ''), COALESCE(alerted_at, ''), next_attempt_at
		FROM site_booking_refund_due WHERE site_booking_id = $1`, id).Scan(
		&d.Attempts, &d.Intent, &d.LastError, &d.AlertedAt, &d.NextAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return d, false
	}
	if err != nil {
		t.Fatal(err)
	}
	return d, true
}

// refundCapEnv sets a budget of one Stripe call a month; capReached spends it.
var refundCapEnv = map[string]string{"UBYHOST_STRIPE_MONTHLY_API_CALLS": "1"}

func capReached(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	if _, err := pool.Exec(context.Background(),
		`INSERT INTO lock_api_usage (month, provider, calls) VALUES ($1, 'stripe', 1)`,
		stampAt(testNow)[:7]); err != nil {
		t.Fatal(err)
	}
}

func TestRefundDueHelpers(t *testing.T) {
	if got := refundIdempotencyKey(4); got != "site_booking_clash_refund_4" {
		t.Errorf("key = %q", got)
	}
	backoff := map[int64]time.Duration{1: time.Hour, 2: 2 * time.Hour, 5: 16 * time.Hour, 6: 24 * time.Hour, 40: 24 * time.Hour}
	for n, want := range backoff {
		if got := refundBackoff(n); got != want {
			t.Errorf("refundBackoff(%d) = %v, want %v", n, got, want)
		}
	}
	codes := map[string]error{
		"http_402:card_declined":   &refundError{status: 402, message: "guest@example.test", code: "card_declined"},
		"http_400:none":            &refundError{status: 400},
		"http_403:account_invalid": fmt.Errorf("wrapped: %w", &refundError{status: 403, code: "Account_Invalid "}),
		"request":                  errors.New("stripe: POST /v1/refunds: timeout"),
	}
	for want, err := range codes {
		if got := refundErrorCode(err); got != want {
			t.Errorf("refundErrorCode(%v) = %q, want %q", err, got, want)
		}
	}
	e := &refundError{status: 402, message: "fake Stripe error", code: "card_declined"}
	if e.Error() != "stripe: POST /v1/refunds: HTTP 402: fake Stripe error (card_declined)" {
		t.Errorf("Error() = %q", e.Error())
	}
}

// A failed refund leaves a due row with one try counted; the hold is released
// and the booking stays pending as before.
func TestClashRefundFailureRecordsDue(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	stub, srv := newRefundStub(t, 100)
	bw := refundDueHandler(pool, g, srv.URL, testNow, nil)
	if err := bw.Process(context.Background(), clashEvent4(t), "test"); err == nil {
		t.Fatal("refund failed but Process returned nil: Stripe would not retry")
	}
	d, ok := readDue(t, pool, 4)
	want := dueRow{Attempts: 1, Intent: "pi_4", LastError: "http_402:card_declined", NextAt: stampAt(testNow.Add(time.Hour))}
	if !ok || d != want {
		t.Errorf("due row %+v (found %v), want %+v", d, ok, want)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM booking_hold WHERE id = 204`); n != 0 {
		t.Errorf("hold 204 kept")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 4 AND status = 'pending'`); n != 1 {
		t.Errorf("booking 4 is not pending")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM reservation WHERE uid = 'site-4'`); n != 0 {
		t.Errorf("a stay was written for the clashing booking")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_rd_4'`); n != 0 {
		t.Errorf("failed event was recorded")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'site_booking_clash_refunded'`); n != 0 {
		t.Errorf("refund audited although it failed")
	}
	calls, refunds := stub.seen()
	if len(calls) != 1 || refunds != 0 || calls[0] != "site_booking_clash_refund_4" {
		t.Errorf("Stripe calls %v, refunds %d", calls, refunds)
	}
}

// The call cap reached is not a try: nothing is counted and Stripe is not called.
func TestClashRefundCapNotCounted(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	capReached(t, pool)
	stub, srv := newRefundStub(t, 0)
	bw := refundDueHandler(pool, g, srv.URL, testNow, refundCapEnv)
	if err := bw.Process(context.Background(), clashEvent4(t), "test"); !errors.Is(err, ErrStripeOff) {
		t.Fatalf("Process = %v, want ErrStripeOff", err)
	}
	d, ok := readDue(t, pool, 4)
	if !ok || d.Attempts != 0 || d.LastError != "" || d.NextAt != stampAt(testNow) {
		t.Errorf("cap reached: due row %+v (found %v), want 0 tries, no error, due now", d, ok)
	}
	if calls, _ := stub.seen(); len(calls) != 0 {
		t.Errorf("Stripe called %d times with the cap reached", len(calls))
	}
}

// Stripe's retry refunds with the same key, once; the row goes, the audit line
// and the guest mail are written once.
func TestClashRefundRetryClearsDue(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	stub, srv := newRefundStub(t, 1)
	bw := refundDueHandler(pool, g, srv.URL, testNow, nil)
	ctx := context.Background()
	ev := clashEvent4(t)
	if err := bw.Process(ctx, ev, "test"); err == nil {
		t.Fatal("first try should fail")
	}
	if err := bw.Process(ctx, ev, "test"); err != nil {
		t.Fatalf("Stripe retry: %v", err)
	}
	if _, ok := readDue(t, pool, 4); ok {
		t.Error("due row kept after the refund went through")
	}
	calls, refunds := stub.seen()
	if len(calls) != 2 || refunds != 1 || calls[0] != "site_booking_clash_refund_4" || calls[1] != calls[0] {
		t.Errorf("Stripe calls %v, refunds %d", calls, refunds)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 4 AND status = 'clash_refunded' AND refunded_czk = 4000`); n != 1 {
		t.Errorf("booking 4 not clash_refunded")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'site_booking_clash_refunded' AND detail = 'id=4 amount=4000'`); n != 1 {
		t.Errorf("%d refund audit lines, want 1", n)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = 'site_booking:4:clash_refund'`); n != 1 {
		t.Errorf("%d guest refund mails, want 1", n)
	}
	if err := bw.Process(ctx, ev, "test"); err != nil {
		t.Fatalf("replay: %v", err)
	}
	if calls, _ := stub.seen(); len(calls) != 2 {
		t.Errorf("replay called Stripe again: %v", calls)
	}
}

// When the clashing stay is gone by the retry, the booking is paid and owes no refund.
func TestClashGoneClearsDue(t *testing.T) {
	g := loadBookingGolden(t)
	pool := testPool(t)
	seedBookingGolden(t, pool, g)
	stub, srv := newRefundStub(t, 100)
	bw := refundDueHandler(pool, g, srv.URL, testNow, nil)
	ctx := context.Background()
	ev := clashEvent4(t)
	if err := bw.Process(ctx, ev, "test"); err == nil {
		t.Fatal("first try should fail")
	}
	if _, err := pool.Exec(ctx, `UPDATE reservation SET status = 'cancelled' WHERE id = 50`); err != nil {
		t.Fatal(err)
	}
	if err := bw.Process(ctx, ev, "test"); err != nil {
		t.Fatalf("retry without clash: %v", err)
	}
	if _, ok := readDue(t, pool, 4); ok {
		t.Error("due row kept for a paid booking")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM site_booking WHERE id = 4 AND status = 'paid'`); n != 1 {
		t.Errorf("booking 4 not paid")
	}
	if calls, _ := stub.seen(); len(calls) != 1 {
		t.Errorf("Stripe calls %v, want only the failed first try", calls)
	}
}
```
   Command: `gofmt -l go/internal/payments/ | head -50` prints nothing (if it lists a section 3 file, run `gofmt -w` on that file only), then `cd go && go test ./internal/payments/ -run 'TestRefundDueHelpers|TestClashRefund|TestClashGone' -count=1 -v 2>&1 | tail -30`: every test `PASS`, none `SKIP` (needs `UBYHOST_TEST_DATABASE_URL`; without it only `TestRefundDueHelpers` runs, the others SKIP: say so in the report).

10. Run all of section 6. Commit only if a command changed a file.

## 5. Do not touch

- Every file not in section 3; especially `App/app/` (Python, go-first, owner: Go only), `go/internal/statemachine/tables.go`, `bookingTransitions`, `onboarder.go`, `webhook.go`, `go/internal/payments/testdata/booking_webhook/golden.json` and `booking_webhook_test.go` (the golden test must pass unchanged).
- Keep the key text `site_booking_clash_refund_<id>`: the golden test and Python use it.
- No new dependency (rule 4). No live Stripe call in any test. Never log or store guest name or e-mail. Never push to `main`; merge only with `scripts/merge-pr-on-green.sh` (owner).

## 6. Commands

- `cd go && go build ./... 2>&1 | tail -30` : no output.
- `cd go && go vet ./internal/payments/ 2>&1 | tail -30` : no output.
- `gofmt -l go/internal/payments/ | head -50` : no output.
- `cd go && go test ./internal/payments/ -count=1 2>&1 | tail -30` : `ok` (golden test `TestBookingWebhookMatchesPython` included, unchanged).
- `cd go && go test ./internal/payments/ -count=1 -v 2>&1 | grep -c -- '--- SKIP'` : `0` with `UBYHOST_TEST_DATABASE_URL` set.
- `cd go && go test ./internal/schema/ -count=1 2>&1 | tail -30` : `ok`.
- From `App/`: `.venv/bin/python -m pytest tests/test_go_schema_golden.py tests/test_goose_migrations.py tests/test_sm_registry.py tests/test_migrations.py tests/test_db_*.py -q --tb=short -x 2>&1 | tail -30` : passed (PostgreSQL-only tests may skip without `UBYHOST_TEST_DATABASE_URL`; list them in the report).
- `python3 scripts/context_lint.py 2>&1 | tail -3` : `context lint: OK` (an overlap warning with 1797 or 1794b is expected).

## 7. Acceptance

- [ ] `App/migrations_pg/00019_site_booking_refund_due.sql` exists, byte-equal to step 1; `pg_schema_golden.py --check` exits 0.
- [ ] `grep -c 'markRefundDue(ctx, tx, bk.id, intent, clash, stamp)' go/internal/payments/booking_webhook.go` prints `1`, and the line sits before the hold delete inside `confirm`.
- [ ] `grep -c 'refundFailed(ctx, bk.id' go/internal/payments/booking_webhook.go` prints `2`; `grep -c 'refundIdempotencyKey(bk.id)' ...` prints `1`; `grep -c 'site_booking_clash_refund_%d' go/internal/payments/booking_webhook.go` prints `0`.
- [ ] All section 6 commands as expected; the five new tests PASS (not SKIP) with a test database, in CI at least.
- [ ] `git diff --stat` lists only section 3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt (anchor A to E) is not found verbatim;
- `TestBookingWebhookMatchesPython` fails (the golden must not change);
- a test fails twice;
- `pg_schema_golden.py` changes a file outside section 3, or the next goose number is not 00019 (`python3 scripts/context_lint.py 2>&1 | tail -2` names it);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1794a-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

Open one draft PR. Its body says: new outbound requests: none new in kind (retries of the existing `POST /v1/refunds` on the host's connected account); retention: no personal data stored, no `retention.py` line; Python unchanged (owner: Go only).

## Risk list (for the reviewer)

Full diff of: `booking_webhook.go` (confirm, refundClash, refund), `booking_refund_due.go`, `00019_site_booking_refund_due.sql`, the regenerated schema fixtures.

## Owner steps

1. Wait for the fresh Tier A review of the full diff, then merge with `scripts/merge-pr-on-green.sh` when CI is green (the new tests must show as run, not skipped).
2. The deploy applies goose file 00019 like every goose file; nothing else to do. It has no effect in production until the Go booking webhook is switched on (brief 1554), which you do only after 1796, 1797, 1794a and 1794b are merged.

## Plan differences

- The idempotency key already existed (`site_booking_clash_refund_<id>`, same in Python): kept, only moved into `refundIdempotencyKey`.
- "Refund due" is a row in a new table, not a `site_booking.status` value (reasons in section 2).
- The row is written for every clash, before the refund call, not only after a failure: a crash between commit and the Stripe answer is then covered too.
- `docs/ENVIRONMENT.md` has no `UBYHOST_GO_BOOKING_WEBHOOK` row and the compose file does not pass it (left to 1554).

## Open questions for the owner

1. Stripe answers `charge_already_refunded` when the payment was refunded by hand. Should that count as "refund done" (row removed, booking `clash_refunded`)? Not built: today it stays a failed try.
