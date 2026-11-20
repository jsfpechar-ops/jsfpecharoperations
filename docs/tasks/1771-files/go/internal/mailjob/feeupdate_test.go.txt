package mailjob

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

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// feeNow is 2026-11-15 10:00 in Prague (09:00 UTC); the stay is 2026-11-20 to 22.
var feeNow = time.Date(2026, 11, 15, 9, 0, 0, 0, time.UTC)

const feeCompletionStamp = "2026-11-14T10:00:00+00:00"

func feeTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_fee_%d", time.Now().UnixNano())
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
	feeApplyMigrations(t, pool)
	return pool
}

func feeApplyMigrations(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
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
		if _, err := pool.Exec(context.Background(), up); err != nil {
			t.Fatalf("migration %s: %v", filepath.Base(f), err)
		}
	}
}

// feeFixture: one host entity with an IBAN, one active apartment charging 120 CZK a
// night, one claimed stay of two nights (2026-11-20 to 22) with one Czech guest.
// The live total is 240 CZK. The baseline the completion mail stated is 200 CZK.
func feeFixture(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	stmts := []string{
		`INSERT INTO legal_entity (id, name, contact_email, iban, created_at)
		   VALUES (1, 'Example Host s.r.o.', 'host@example.test', 'CZ6508000000192000145399', '2026-01-01T00:00:00+00:00')`,
		`INSERT INTO apartment (id, legal_entity_id, owner_user_id, internal_name, permalink_token, active,
		   created_at, stay_fee_rate_czk, stay_fee_collect, stay_fee_guest_rails, stay_fee_guest_default_rail,
		   stay_fee_guest_revolut_link, stay_fee_guest_cash_note)
		   VALUES (1, 1, NULL, 'Harbour Flat', 'tok-fee', 1, '2026-01-01T00:00:00+00:00', 120, 1,
		   'qr,revolut,cash', 'iban', 'https://revolut.example.test/pay/harbour', 'Cash at the desk')`,
		`INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, declared_guests, status, created_at, updated_at)
		   VALUES (10, 1, 'ota', 'uid-10', '2026-11-20', '2026-11-22', 1, 'active', '2026-11-14T09:00:00+00:00', '2026-11-14T09:00:00+00:00')`,
		`INSERT INTO guest (id, reservation_id, surname, first_name, birth_date, nationality, created_at, updated_at)
		   VALUES (101, 10, 'Test', 'Guest', '1990-07-07', 'CZE', '2026-11-14T09:00:00+00:00', '2026-11-14T09:00:00+00:00')`,
		`INSERT INTO reservation_claim (reservation_id, state, email, lang, claimed_at, completion_notified_at,
		   fee_mailed_total, fee_mailed_at, created_at, updated_at)
		   VALUES (10, 'claimed', 'guest@example.test', 'en', $1, $1, 200, $1, $1, $1)`,
	}
	for _, s := range stmts {
		if _, err := pool.Exec(ctx, s, feeArgs(s)...); err != nil {
			t.Fatal(err)
		}
	}
}

// feeArgs binds the completion stamp to the statements that carry $1.
func feeArgs(sql string) []any {
	if strings.Contains(sql, "$1") {
		return []any{feeCompletionStamp}
	}
	return nil
}

func feeState(t *testing.T, pool *pgxpool.Pool) (mailedTotal int64, mailedAt string, pendingTotal *int64, pendingSince *string) {
	t.Helper()
	err := pool.QueryRow(context.Background(), `SELECT fee_mailed_total, fee_mailed_at, fee_pending_total, fee_pending_since
		FROM reservation_claim WHERE reservation_id = 10`).Scan(&mailedTotal, &mailedAt, &pendingTotal, &pendingSince)
	if err != nil {
		t.Fatal(err)
	}
	return
}

func feeOutbox(t *testing.T, pool *pgxpool.Pool) []string {
	t.Helper()
	rows, err := pool.Query(context.Background(), `SELECT idempotency_key FROM email_outbox
		WHERE kind = 'completion_update' ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var keys []string
	for rows.Next() {
		var k string
		if err := rows.Scan(&k); err != nil {
			t.Fatal(err)
		}
		keys = append(keys, k)
	}
	return keys
}

func feeSweep(t *testing.T, pool *pgxpool.Pool, at time.Time) map[string]int {
	t.Helper()
	got, err := SweepFeeUpdates(context.Background(), pool, at)
	if err != nil {
		t.Fatal(err)
	}
	return got
}

func TestFeeUpdateTimestampFormats(t *testing.T) {
	withMicro := time.Date(2026, 11, 15, 9, 0, 0, 123456000, time.UTC)
	if got := pyISO(withMicro); got != "2026-11-15T09:00:00.123456+00:00" {
		t.Errorf("pyISO keeps microseconds: got %q", got)
	}
	if got := pyISO(feeNow); got != "2026-11-15T09:00:00+00:00" {
		t.Errorf("pyISO drops a zero fraction like isoformat: got %q", got)
	}
	if got := pyUTCNow(withMicro); got != "2026-11-15T09:00:00+00:00" {
		t.Errorf("pyUTCNow (db.utcnow) drops microseconds: got %q", got)
	}
	since := "2026-11-15T09:00:00.500000+00:00"
	if quietLongEnough(&since, feeNow.Add(9*time.Minute+59*time.Second)) {
		t.Error("9 min 59 s is not the 10 minute quiet window")
	}
	if !quietLongEnough(&since, feeNow.Add(10*time.Minute+time.Second)) {
		t.Error("10 min 1 s after the stamp must count as quiet")
	}
	if quietLongEnough(nil, feeNow) {
		t.Error("no pending stamp is never quiet")
	}
}

func TestFeeUpdatePendingThenQueuedAfterQuietWindow(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	t.Setenv("UBYHOST_STAY_FEE_GUEST_PAY", "on")
	t.Setenv("UBYHOST_PUBLIC_BASE_URL", "https://app.example.test")
	pool := feeTestPool(t)
	feeFixture(t, pool)

	if got := feeSweep(t, pool, feeNow); got["pending"] != 1 || got["queued"] != 0 {
		t.Fatalf("first sweep: %v", got)
	}
	if _, _, pt, ps := feeState(t, pool); pt == nil || *pt != 240 || ps == nil || *ps != "2026-11-15T09:00:00+00:00" {
		t.Fatalf("pending columns after first sweep: %v %v", pt, ps)
	}
	if got := feeSweep(t, pool, feeNow.Add(9*time.Minute)); got["pending"] != 1 || got["queued"] != 0 {
		t.Fatalf("sweep inside the quiet window: %v", got)
	}
	later := feeNow.Add(11 * time.Minute)
	if got := feeSweep(t, pool, later); got["queued"] != 1 {
		t.Fatalf("sweep after the quiet window: %v", got)
	}
	mailed, mailedAt, pt, _ := feeState(t, pool)
	if mailed != 240 || mailedAt != pyISO(later) || pt != nil {
		t.Fatalf("baseline after queue: total=%d at=%q pending=%v", mailed, mailedAt, pt)
	}
	keys := feeOutbox(t, pool)
	want := "completion_update:10:" + feeCompletionStamp + ":240"
	if len(keys) != 1 || keys[0] != want {
		t.Fatalf("outbox keys = %v, want [%s]", keys, want)
	}
	var subject, payload string
	if err := pool.QueryRow(context.Background(), `SELECT subject, payload FROM email_outbox WHERE idempotency_key = $1`,
		want).Scan(&subject, &payload); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(subject, "now 240 CZK") {
		t.Errorf("subject %q does not state the new total", subject)
	}
	if !strings.Contains(payload, `"reply_to": "host@example.test"`) {
		t.Errorf("payload has no reply_to: %s", payload)
	}
	if got := feeSweep(t, pool, later.Add(time.Minute)); got["queued"] != 0 || got["pending"] != 0 {
		t.Errorf("nothing changed, so the next sweep must do nothing: %v", got)
	}
	if n := len(feeOutbox(t, pool)); n != 1 {
		t.Errorf("a second sweep queued again: %d rows", n)
	}
}

func TestFeeUpdateRestartsWaitOnFurtherChange(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	t.Setenv("UBYHOST_STAY_FEE_GUEST_PAY", "on")
	pool := feeTestPool(t)
	feeFixture(t, pool)

	feeSweep(t, pool, feeNow) // pending at 240
	if _, err := pool.Exec(context.Background(), `UPDATE reservation SET date_to = '2026-11-23' WHERE id = 10`); err != nil {
		t.Fatal(err)
	}
	restart := feeNow.Add(8 * time.Minute)
	if got := feeSweep(t, pool, restart); got["pending"] != 1 {
		t.Fatalf("a further change restarts the wait: %v", got)
	}
	if got := feeSweep(t, pool, feeNow.Add(11*time.Minute)); got["queued"] != 0 {
		t.Fatalf("only 3 minutes since the restart: %v", got)
	}
	if got := feeSweep(t, pool, feeNow.Add(19*time.Minute)); got["queued"] != 1 {
		t.Fatalf("11 minutes since the restart: %v", got)
	}
	keys := feeOutbox(t, pool)
	if len(keys) != 1 || !strings.HasSuffix(keys[0], ":360") {
		t.Fatalf("outbox keys = %v, want the 360 CZK total", keys)
	}
}

func TestFeeUpdateMailOffRecordsNothing(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "off")
	t.Setenv("UBYHOST_STAY_FEE_GUEST_PAY", "on")
	pool := feeTestPool(t)
	feeFixture(t, pool)

	feeSweep(t, pool, feeNow)
	if got := feeSweep(t, pool, feeNow.Add(11*time.Minute)); got["queued"] != 0 {
		t.Fatalf("mail is off, nothing may be queued: %v", got)
	}
	mailed, mailedAt, _, _ := feeState(t, pool)
	if mailed != 200 || mailedAt != feeCompletionStamp {
		t.Errorf("baseline moved with mail off: total=%d at=%q", mailed, mailedAt)
	}
	if n := len(feeOutbox(t, pool)); n != 0 {
		t.Errorf("outbox rows with mail off: %d", n)
	}
}

func TestFeeUpdateLostRecordBecomesBaseline(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	t.Setenv("UBYHOST_STAY_FEE_GUEST_PAY", "on")
	pool := feeTestPool(t)
	feeFixture(t, pool)
	ctx := context.Background()
	// The live total is 240 and the guest was told 240 by a mail whose record was lost:
	// the outbox row exists, the baseline still says 200, a pending 300 is stuck.
	if _, err := pool.Exec(ctx, `UPDATE reservation_claim SET fee_mailed_total = 240, fee_pending_total = 300,
		fee_pending_since = '2026-11-15T07:00:00+00:00' WHERE reservation_id = 10`); err != nil {
		t.Fatal(err)
	}
	rid, aid := int64(10), int64(1)
	if _, err := ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind: "completion_update", Key: "completion_update:10:" + feeCompletionStamp + ":300",
		ReservationID: &rid, ApartmentID: &aid, To: "guest@example.test", Subject: "old", Text: "old",
	}); err != nil {
		t.Fatal(err)
	}
	if got := feeSweep(t, pool, feeNow); got["queued"] != 0 || got["pending"] != 0 {
		t.Fatalf("recovery sends nothing new: %v", got)
	}
	mailed, mailedAt, pt, ps := feeState(t, pool)
	if mailed != 300 || mailedAt != pyISO(feeNow) || pt != nil || ps != nil {
		t.Errorf("baseline after recovery: total=%d at=%q pending=%v since=%v", mailed, mailedAt, pt, ps)
	}
}

func TestFeeUpdateNothingWhenLiveMatchesBaseline(t *testing.T) {
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	t.Setenv("UBYHOST_STAY_FEE_GUEST_PAY", "on")
	pool := feeTestPool(t)
	feeFixture(t, pool)
	if _, err := pool.Exec(context.Background(), `UPDATE reservation_claim SET fee_mailed_total = 240 WHERE reservation_id = 10`); err != nil {
		t.Fatal(err)
	}
	if got := feeSweep(t, pool, feeNow); got["queued"] != 0 || got["pending"] != 0 {
		t.Fatalf("no change, no work: %v", got)
	}
	if n := len(feeOutbox(t, pool)); n != 0 {
		t.Errorf("outbox rows: %d", n)
	}
}

func TestRecordBaselineStoresTotalWithoutMicroseconds(t *testing.T) {
	pool := feeTestPool(t)
	feeFixture(t, pool)
	at := time.Date(2026, 11, 15, 9, 0, 0, 987654000, time.UTC)
	if err := RecordBaseline(context.Background(), pool, 10, 320, at); err != nil {
		t.Fatal(err)
	}
	mailed, mailedAt, pt, ps := feeState(t, pool)
	if mailed != 320 || mailedAt != "2026-11-15T09:00:00+00:00" || pt != nil || ps != nil {
		t.Errorf("baseline: total=%d at=%q pending=%v since=%v", mailed, mailedAt, pt, ps)
	}
}
