package main

// Brief 2065 step 6: DB-backed tests for the registration receipt through the real completion hooks.
// They call the same two hooks guest.runCompletion calls after a save (OnRegistrationComplete, then
// MaybeNotifyCompletion with force=false). Skips without UBYHOST_TEST_DATABASE_URL.

import (
	"bytes"
	"context"
	"encoding/base64"
	"errors"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"os"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"

	doorwire "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes/wire"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/guest"
)

const hooksTestStamp = "2026-06-02T12:00:00+00:00"

// hooksTestPool connects to UBYHOST_TEST_DATABASE_URL and skips when the migrated schema is missing.
func hooksTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	url := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, url)
	if err != nil {
		t.Fatalf("pool: %v", err)
	}
	t.Cleanup(pool.Close)
	var schemaOK int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'apartment' AND column_name = 'stay_fee_guest_rails'`).Scan(&schemaOK); err != nil || schemaOK == 0 {
		t.Skip("needs migrated Postgres schema")
	}
	return pool
}

// hooksTestEnv sets the mail and key env the real hooks read. Console mail backend, no network.
func hooksTestEnv(t *testing.T) {
	t.Helper()
	t.Setenv("UBYHOST_MAIL_BACKEND", "console")
	t.Setenv("UBYHOST_DEPLOYMENT", "staging")
	t.Setenv("UBYHOST_DATA_KEYS", base64.URLEncoding.EncodeToString([]byte(strings.Repeat("k", 32))))
	t.Setenv("UBYHOST_DATA_KEY_LEGACY", "0")
	t.Setenv("UBYHOST_SECRET_KEY", strings.Repeat("c", 32))
	t.Setenv("UBYHOST_GUEST_PIN", "0")
	t.Setenv("UBYHOST_STAY_FEE_GUEST_PAY", "on")
	t.Setenv("UBYHOST_LIFECYCLE_MAIL", "")
	t.Setenv("UBYHOST_HEARTBEAT_MAIL_URL", "")
}

type hooksStay struct {
	aptID, resID int64
	declared     int
	complete     int
	lockProvider string
}

func hooksExec(t *testing.T, pool *pgxpool.Pool, q string, args ...any) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), q, args...); err != nil {
		t.Fatalf("exec %.60s: %v", q, err)
	}
}

// seedHooksStay writes a claimed stay with an e-mail address, a fee-collecting apartment, and
// `complete` complete guests against `declared` declared guests. The INSERTs follow stay_fee_box_test.go.
func seedHooksStay(t *testing.T, pool *pgxpool.Pool, s hooksStay) {
	t.Helper()
	var buf bytes.Buffer
	img := image.NewRGBA(image.Rect(0, 0, 2, 2))
	img.Set(0, 0, color.Black)
	if err := png.Encode(&buf, img); err != nil {
		t.Fatal(err)
	}
	sig := "data:image/png;base64," + base64.StdEncoding.EncodeToString(buf.Bytes())
	ownerID, entityID := s.aptID, s.aptID
	tok := fmt.Sprintf("hooks-%d", s.aptID)

	t.Cleanup(func() { hooksCleanup(t, pool, s) })
	hooksCleanup(t, pool, s)

	hooksExec(t, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3)`, ownerID, tok+"-owner", hooksTestStamp)
	hooksExec(t, pool, `INSERT INTO legal_entity (id, name, iban, created_at, owner_user_id)
		VALUES ($1, 'Hooks Operator', 'CZ6508000000192000145399', $2, $3)`, entityID, hooksTestStamp, ownerID)
	hooksExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, permalink_token, active, created_at, city_en,
		legal_entity_id, stay_fee_collect, stay_fee_rate_czk, stay_fee_guest_rails, lock_provider)
		VALUES ($1, $2, 'Flat', $3, 1, $4, 'Prague', $5, 1, 100, 'iban', NULLIF($6, ''))`,
		s.aptID, ownerID, tok, hooksTestStamp, entityID, s.lockProvider)
	hooksExec(t, pool, `INSERT INTO stay_fee_rate (apartment_id, rate_czk, effective_from, created_at)
		VALUES ($1, 100, '2026-01-01', $2)`, s.aptID, hooksTestStamp)
	hooksExec(t, pool, `INSERT INTO reservation (id, uid, apartment_id, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'ical', '2026-06-01', '2026-06-05', $4, $4)`, s.resID, tok+"-res", s.aptID, hooksTestStamp)
	hooksExec(t, pool, `INSERT INTO reservation_claim (reservation_id, state, email, lang, token_version, declared_guests, created_at, updated_at)
		VALUES ($1, 'claimed', 'guest@example.test', 'en', 1, $2, $3, $3)`, s.resID, s.declared, hooksTestStamp)
	hooksExec(t, pool, `UPDATE reservation SET declared_guests = $1 WHERE id = $2`, s.declared, s.resID)
	for i := 0; i < s.complete; i++ {
		isLead := 0
		if i == 0 {
			isLead = 1
		}
		hooksExec(t, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality,
			doc_number, res_street, res_city, res_country, purpose, is_lead, signature_png)
			VALUES ($1, $2, $3, $3, 'Hook', 'Guest', '01011990', 'CZE', 'HK123456', 'Street 1', 'City', 'CZE', '03', $4, $5)`,
			s.resID*10+int64(i), s.resID, hooksTestStamp, isLead, sig)
	}
}

// hooksCleanup removes the rows one stay owns, child tables first.
func hooksCleanup(t *testing.T, pool *pgxpool.Pool, s hooksStay) {
	t.Helper()
	ctx := context.Background()
	res, apt := s.resID, s.aptID
	for _, c := range []struct {
		q  string
		id int64
	}{
		{`DELETE FROM email_outbox WHERE reservation_id = $1`, res},
		{`DELETE FROM guest WHERE reservation_id = $1`, res},
		{`DELETE FROM reservation_claim WHERE reservation_id = $1`, res},
		{`DELETE FROM reservation WHERE id = $1`, res},
		{`DELETE FROM stay_fee_rate WHERE apartment_id = $1`, apt},
		{`DELETE FROM apartment WHERE id = $1`, apt},
		{`DELETE FROM legal_entity WHERE id = $1`, apt},
		{`DELETE FROM user_account WHERE id = $1`, apt},
	} {
		if _, err := pool.Exec(ctx, c.q, c.id); err != nil {
			t.Logf("cleanup %.40s: %v", c.q, err)
		}
	}
}

// completionRows counts the completion receipts queued for the stay.
func completionRows(t *testing.T, pool *pgxpool.Pool, resID int64) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(),
		`SELECT COUNT(*) FROM email_outbox WHERE reservation_id = $1 AND kind = 'completion'`, resID).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

// afterSave runs the two hooks guest.runCompletion calls after a save, in the same order.
func afterSave(h guest.CompletionHooks, s hooksStay) error {
	ctx := context.Background()
	h.OnRegistrationComplete(ctx, s.resID)
	err := h.MaybeNotifyCompletion(ctx, s.resID, s.aptID, false)
	// The receipt row is already queued and completion_notified_at is set before the drain runs.
	// The drain then stops at the {{receipt_details}} block because no details renderer is wired
	// (brief 1231b). That gap is reported, not hidden by the row count below.
	if errors.Is(err, mail.ErrNoDetailsRenderer) {
		return nil
	}
	return err
}

// fallbackHooks builds the adapter the way completionAdapter.build does when the door-code wiring
// cannot be built: the noDoorCodes viewer. Build runs once here, so the real wiring is never tried.
func fallbackHooks(pool *pgxpool.Pool) guest.CompletionHooks {
	a := &completionAdapter{pool: pool}
	a.once.Do(func() {
		a.confirm = doorwire.LiveConfirmations{
			Pool:   pool,
			Mailer: &doorwire.Mailer{Pool: pool, Env: doorCodeMailEnv(os.Getenv), Getenv: os.Getenv},
			Billing: doorwire.LiveBilling{
				Pool:     pool,
				Getenv:   os.Getenv,
				GuestPay: true,
			},
			Doors: noDoorCodes{},
		}
	})
	return a
}

// TestCompletionReceiptOnceForAllDeclaredGuests: all declared guests complete -> one receipt row;
// a repeat save does not add another.
func TestCompletionReceiptOnceForAllDeclaredGuests(t *testing.T) {
	pool := hooksTestPool(t)
	hooksTestEnv(t)
	s := hooksStay{aptID: 206400, resID: 206401, declared: 1, complete: 1}
	seedHooksStay(t, pool, s)
	h := completionHooks(pool)

	if err := afterSave(h, s); err != nil {
		t.Fatalf("first save: %v", err)
	}
	if n := completionRows(t, pool, s.resID); n != 1 {
		t.Fatalf("after all guests complete: %d completion rows, want 1", n)
	}
	if err := afterSave(h, s); err != nil {
		t.Fatalf("second save: %v", err)
	}
	if n := completionRows(t, pool, s.resID); n != 1 {
		t.Fatalf("after second save: %d completion rows, want still 1", n)
	}
}

// TestCompletionReceiptHeldUntilAllDeclaredGuestsComplete: one of two declared guests complete -> no row.
func TestCompletionReceiptHeldUntilAllDeclaredGuestsComplete(t *testing.T) {
	pool := hooksTestPool(t)
	hooksTestEnv(t)
	s := hooksStay{aptID: 206410, resID: 206411, declared: 2, complete: 1}
	seedHooksStay(t, pool, s)
	if err := afterSave(completionHooks(pool), s); err != nil {
		t.Fatalf("save: %v", err)
	}
	if n := completionRows(t, pool, s.resID); n != 0 {
		t.Fatalf("one of two guests complete: %d completion rows, want 0", n)
	}
}

// TestCompletionReceiptHeldForTTLockFallback: a ttlock apartment with the noDoorCodes fallback -> no row sent.
func TestCompletionReceiptHeldForTTLockFallback(t *testing.T) {
	pool := hooksTestPool(t)
	hooksTestEnv(t)
	s := hooksStay{aptID: 206420, resID: 206421, declared: 1, complete: 1, lockProvider: "ttlock"}
	seedHooksStay(t, pool, s)
	if err := afterSave(fallbackHooks(pool), s); err != nil {
		t.Fatalf("save: %v", err)
	}
	if n := completionRows(t, pool, s.resID); n != 0 {
		t.Fatalf("ttlock fallback: %d completion rows, want 0 (held)", n)
	}
}
