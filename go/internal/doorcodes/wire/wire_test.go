package doorwire

import (
	"bytes"
	"context"
	"encoding/base64"
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

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailnotify"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// testPool creates a fresh database on the server UBYHOST_TEST_DATABASE_URL points at,
// applies App/migrations_pg and drops it at the end. Like the other DB tests it skips when
// the variable is unset.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_doorwire_%d", time.Now().UnixNano())
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
	// Seed rows without the foreign keys of tables this test does not build (user_account).
	cfg.AfterConnect = func(ctx context.Context, c *pgx.Conn) error {
		_, err := c.Exec(ctx, "SET session_replication_role = replica")
		return err
	}
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

func keys(t *testing.T) *secure.MultiFernet {
	t.Helper()
	// A Fernet key is the URL-safe base64 of 32 bytes (invented here).
	key := base64.URLEncoding.EncodeToString(bytes.Repeat([]byte("d"), 32))
	k, err := secure.NewMultiFernet([]byte(key))
	if err != nil {
		t.Fatal(err)
	}
	return k
}

func exec(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatal(err)
	}
}

func consoleEnv(key string) string {
	if key == "UBYHOST_MAIL_BACKEND" {
		return "console"
	}
	return ""
}

var testEnv = mailnotify.DoorCodeMailEnv{
	AppBaseURL:    "https://app.example.test",
	PublicBaseURL: "https://app.example.test",
	SupportEmail:  "support@ubyhost.com",
}

// seedStay inserts one legal entity, one apartment and one stay (invented data).
func seedStay(t *testing.T, pool *pgxpool.Pool, legalContact string) {
	t.Helper()
	ts := "2026-11-15T10:00:00"
	exec(t, pool, `INSERT INTO legal_entity (id, name, vat_status, invoice_due_days, created_at, business_type, contact_email)
		VALUES (3, 'Pension Test s.r.o.', 'none', 14, $1, 'company', $2)`, ts, legalContact)
	exec(t, pool, `INSERT INTO apartment (id, legal_entity_id, owner_user_id, internal_name, automation_mode,
		submit_after_hours, permalink_window_days, permalink_reachback_days, default_purpose, passport_photo_policy,
		stay_fee_rate_czk, stay_fee_cadence, active, created_at, leon_enabled, ocr_scan, stay_fee_collect,
		stay_fee_guest_rails, stay_fee_guest_default_rail)
		VALUES (21, 3, 7, 'Studio Lípa', 'manual', 0, 0, 0, 'tourism', 'off', 0, 'none', 1, $1, 0, 0, 0, '', '')`, ts)
	exec(t, pool, `INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, status, created_at,
		updated_at, lead_reduced_changes) VALUES (501, 21, 'host', 'uid-501', '2026-11-16', '2026-11-18', 'active', $1, $1, 0)`, ts)
}

// --- payload encoding -------------------------------------------------------------

// The expected strings are json.dumps output from the Python venv for the same values
// (python3 json.dumps with default arguments, ensure_ascii=True).
func TestEncodePayloadIsPythonJSONDumps(t *testing.T) {
	got, err := encodePayload("door_code", map[string]any{
		"door_code_enc": "tok\"1",
		"html":          "<p>Hi & é \U0001F511</p>",
		"lang":          "cs",
		"text":          "Hi \u00e9 <b>&</b>\n\u007f",
		"reply_to":      "desk@example.test",
		"qr_spayd":      "SPD*1.0*ACC:CZ65*AM:3400.00",
	})
	if err != nil {
		t.Fatal(err)
	}
	want := `{"text": "Hi \u00e9 <b>&</b>\n\u007f", "lang": "cs", "html": "<p>Hi & \u00e9 \ud83d\udd11</p>", ` +
		`"reply_to": "desk@example.test", "qr_spayd": "SPD*1.0*ACC:CZ65*AM:3400.00", "door_code_enc": "tok\"1"}`
	if got != want {
		t.Fatalf("payload\n got: %s\nwant: %s", got, want)
	}
	notice, err := encodePayload("door_code_notice", map[string]any{"lang": "en", "html": "h", "text": "t"})
	if err != nil {
		t.Fatal(err)
	}
	if want := `{"text": "t", "html": "h", "lang": "en"}`; notice != want {
		t.Fatalf("notice payload got %s want %s", notice, want)
	}
	if _, err := encodePayload("door_code", map[string]any{"text": 3}); err == nil {
		t.Fatal("a non-string payload value must be an error")
	}
}

// --- build (no database) ---------------------------------------------------------

func TestBuildDoorCodeReadsFeeMap(t *testing.T) {
	m := &Mailer{Env: testEnv}
	fee := map[string]any{
		"total": 3400, "rate": 850, "vs": "2026111601",
		"lines": []any{[]any{2, 1700}, []any{1, 1700}},
		"ways": []any{map[string]any{
			"key": "iban", "payee": "Pension Test s.r.o.", "account": "CZ6508000000192000145399",
			"spayd": "SPD*1.0*ACC:CZ6508000000192000145399*AM:3400.00*CC:CZ*X-VS:2026111601",
		}},
	}
	got, err := m.BuildDoorCode(context.Background(), doorcodes.DoorCodeMail{
		Lang: "uk", PropertyName: "Квартира на Подолі", Checkin: "16.11.2026", Checkout: "18.11.2026",
		FirstUseBy: "16.11.2026 10:00", Fee: fee,
	})
	if err != nil {
		t.Fatal(err)
	}
	if want := "SPD*1.0*ACC:CZ6508000000192000145399*AM:3400.00*CC:CZ*X-VS:2026111601"; got.QRSpayd != want {
		t.Fatalf("qr spayd %q", got.QRSpayd)
	}
	direct := mailnotify.BuildDoorCode(testEnv.PublicBaseURL, mailnotify.DoorCodeInput{
		Lang: "uk", PropertyName: "Квартира на Подолі", Checkin: "16.11.2026", Checkout: "18.11.2026",
		FirstUseBy: "16.11.2026 10:00",
		Fee: &mailnotify.DoorCodeFee{Total: 3400, Rate: 850, VS: "2026111601",
			Lines: []mailnotify.FeeLine{{Days: 2, Amount: 1700}, {Days: 1, Amount: 1700}},
			Ways: []mailnotify.FeeWay{{Key: "iban", Payee: "Pension Test s.r.o.",
				Account: "CZ6508000000192000145399",
				Spayd:   "SPD*1.0*ACC:CZ6508000000192000145399*AM:3400.00*CC:CZ*X-VS:2026111601"}}},
	})
	if got.Fields["html"] != direct.HTML || got.Fields["text"] != direct.Text || got.Subject != direct.Subject {
		t.Fatal("the map path differs from the typed builder")
	}
}

// --- database ---------------------------------------------------------------------

func TestEnqueueIdempotentAndGated(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	seedStay(t, pool, "desk@example.test")
	m := &Mailer{Pool: pool, Env: testEnv, Keys: keys(t), Getenv: consoleEnv}
	in := doorcodes.OutboxMail{
		Kind: "door_code", IdempotencyKey: "door_code:501:2026-11-16:2026-11-18:none",
		ToEmail: " Guest@Example.TEST ", Subject: "Subj", ReservationID: 501, ApartmentID: 21, OwnerUserID: 7,
		Payload: map[string]any{"text": "T", "lang": "en", "html": "H", "reply_to": "desk@example.test"},
	}
	id1, ok, err := m.Enqueue(ctx, in)
	if err != nil || !ok || id1 == 0 {
		t.Fatalf("first enqueue id=%d ok=%v err=%v", id1, ok, err)
	}
	id2, ok, err := m.Enqueue(ctx, in)
	if err != nil || !ok || id2 != id1 {
		t.Fatalf("second enqueue must return the existing id: id=%d ok=%v err=%v", id2, ok, err)
	}
	var to, payload string
	if err := pool.QueryRow(ctx, "SELECT to_email, payload FROM email_outbox WHERE id = $1", id1).Scan(&to, &payload); err != nil {
		t.Fatal(err)
	}
	if to != "guest@example.test" {
		t.Fatalf("to_email %q is not normalised", to)
	}
	if want := `{"text": "T", "lang": "en", "html": "H", "reply_to": "desk@example.test"}`; payload != want {
		t.Fatalf("payload %s", payload)
	}

	// A demo stay's guest mail is skipped (mail.enqueue, GUEST_KINDS).
	exec(t, pool, `INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, status, created_at,
		updated_at, lead_reduced_changes) VALUES (777, 21, 'demo', 'uid-777', '2026-11-16', '2026-11-18', 'active',
		'2026-11-15T10:00:00', '2026-11-15T10:00:00', 0)`)
	demo := in
	demo.IdempotencyKey = "door_code:777:x"
	demo.ReservationID = 777
	if _, ok, err := m.Enqueue(ctx, demo); err != nil || ok {
		t.Fatalf("demo stay must not queue: ok=%v err=%v", ok, err)
	}
	// Mail disabled: Python returns None.
	off := &Mailer{Pool: pool, Env: testEnv, Keys: keys(t), Getenv: func(string) string { return "disabled" }}
	if _, ok, err := off.Enqueue(ctx, in); err != nil || ok {
		t.Fatalf("disabled mail must not queue: ok=%v err=%v", ok, err)
	}
	var n int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM email_outbox").Scan(&n); err != nil || n != 1 {
		t.Fatalf("outbox rows %d err=%v, want 1", n, err)
	}
}

func TestPlansTTLockAllowed(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	rows := []struct {
		owner  int64
		status string
		plan   string
		addon  int
		want   bool
	}{
		{1, "active", "max", 0, true},
		{2, "active", "standard", 1, true},
		{3, "active", "standard", 0, false},
		{4, "paused", "max", 1, false},
		{5, "trialing", "max", 1, false},
		{6, "trial_pending", "max", 0, false},
	}
	for _, r := range rows {
		exec(t, pool, `INSERT INTO billing_account (owner_user_id, status, plan, payment_method, founder, addon_ttlock,
			addon_whitelabel, apartments_billed, cancel_at_period_end, carry_czk, updated_at, discount_percent)
			VALUES ($1, $2, $3, 'card', 0, $4, 0, 0, 0, 0, '2026-11-15T10:00:00', 0)`, r.owner, r.status, r.plan, r.addon)
	}
	p := Plans{Pool: pool, Getenv: func(k string) string {
		if k == "UBYHOST_BILLING_ENABLED" {
			return "1"
		}
		return ""
	}}
	for _, r := range rows {
		got, err := p.TTLockAllowed(ctx, r.owner)
		if err != nil || got != r.want {
			t.Errorf("owner %d (%s, %s, addon %d): got %v err=%v want %v", r.owner, r.status, r.plan, r.addon, got, err, r.want)
		}
	}
	if got, err := p.TTLockAllowed(ctx, 99); err != nil || got {
		t.Errorf("owner without a billing row: got %v err=%v", got, err)
	}
	off := Plans{Pool: pool, Getenv: func(string) string { return "" }}
	if got, err := off.TTLockAllowed(ctx, 1); err != nil || got {
		t.Errorf("billing off must answer false (UNBILLED has no ttlock): got %v err=%v", got, err)
	}
}

func TestPushQueueDoorCode(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	ts := "2026-11-15T10:00:00"
	for i, dev := range []string{"phone", "laptop"} {
		exec(t, pool, `INSERT INTO push_subscription (id, user_account_id, endpoint_hash, endpoint_enc, p256dh_enc,
			auth_enc, lang, device, failures, created_at, last_seen_at)
			VALUES ($1, 7, $2, 'e', 'p', 'a', 'en', $3, 0, $4, $4)`, int64(i+1), fmt.Sprintf("h%d", i), dev, ts)
	}
	p := Push{Pool: pool, Getenv: func(string) string { return "" }}
	n, err := p.QueueDoorCode(ctx, 7, "501", "/reservations/501", ubyport.AlertParams{"property": "Studio Lípa"})
	if err != nil || n != 2 {
		t.Fatalf("queued %d err=%v, want 2 (one per device)", n, err)
	}
	rows, err := pool.Query(ctx, "SELECT idempotency_key, kind, url, state FROM push_outbox ORDER BY idempotency_key")
	if err != nil {
		t.Fatal(err)
	}
	var got []string
	for rows.Next() {
		var key, kind, url, state string
		if err := rows.Scan(&key, &kind, &url, &state); err != nil {
			t.Fatal(err)
		}
		got = append(got, key+"|"+kind+"|"+url+"|"+state)
	}
	rows.Close()
	want := []string{"door_code:501:1|door_code|/reservations/501|queued", "door_code:501:2|door_code|/reservations/501|queued"}
	if strings.Join(got, "\n") != strings.Join(want, "\n") {
		t.Fatalf("push rows\n got: %v\nwant: %v", got, want)
	}
	// The same key again reaches no device (the unique key stops it); Python's notify logs
	// and returns 0, the Go QueuePush returns that as an error with 0 rows.
	if n, _ := p.QueueDoorCode(ctx, 7, "501", "/reservations/501", nil); n != 0 {
		t.Fatalf("a second identical push must not reach a device twice: n=%d", n)
	}
	off := Push{Pool: pool, Getenv: func(string) string { return "0" }}
	if n, err := off.QueueDoorCode(ctx, 7, "502", "/x", nil); err != nil || n != 0 {
		t.Fatalf("UBYHOST_WEB_PUSH=0 must queue nothing: n=%d err=%v", n, err)
	}
	if err := (Push{Pool: pool}).Notify(ctx, 7, "t", "b"); err != ErrNotPorted {
		t.Fatalf("Notify must say it is not ported, got %v", err)
	}
}

func TestDoorCodeNoticeEndToEnd(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	seedStay(t, pool, "  Desk@Example.test ")
	k := keys(t)
	m := &Mailer{Pool: pool, Env: testEnv, Keys: k, Getenv: consoleEnv}
	exec(t, pool, `INSERT INTO door_code (id, reservation_id, apartment_id, lock_id, code_kind, state, attempts,
		created_at, updated_at, last_error) VALUES (11, 501, 21, 'L1', 'random', 'failed', 0,
		'2026-11-15T10:00:00', '2026-11-15T10:00:00', 'bad_window')`)

	if err := m.DoorCodeNotice(ctx, 11, "failed"); err != nil {
		t.Fatal(err)
	}
	var kind, key, to string
	var cc *string
	var subject, payload string
	err := pool.QueryRow(ctx, `SELECT kind, idempotency_key, to_email, cc_email, subject, payload FROM email_outbox`).
		Scan(&kind, &key, &to, &cc, &subject, &payload)
	if err != nil {
		t.Fatal(err)
	}
	if kind != "door_code_notice" || key != "door_code_notice:11:failed" || to != "desk@example.test" {
		t.Fatalf("row %s %s %s", kind, key, to)
	}
	if cc == nil || *cc != "support@ubyhost.com" {
		t.Fatalf("failed notices copy support, got %v", cc)
	}
	// The subject is the golden string for this variant (door_code_golden.json, notice_failed_bad_window).
	if want := "Studio Lípa: please create the door code yourself"; subject != want {
		t.Fatalf("subject %q", subject)
	}
	if !strings.HasPrefix(payload, `{"text": "We are sorry: the door code for the stay from 16.11.2026 could not be created.`) ||
		!strings.Contains(payload, "[bad_window]") {
		t.Fatalf("payload %s", payload)
	}
	var decoded map[string]string
	if err := json.Unmarshal([]byte(payload), &decoded); err != nil || decoded["lang"] != "en" {
		t.Fatalf("payload is not valid JSON with lang en: %v", err)
	}

	// The second call is the same key: no second row.
	if err := m.DoorCodeNotice(ctx, 11, "failed"); err != nil {
		t.Fatal(err)
	}
	var n int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM email_outbox").Scan(&n); err != nil || n != 1 {
		t.Fatalf("rows %d err=%v, want 1", n, err)
	}

	// A PIN is masked to its last two digits, and a cancelled notice has no cc.
	enc, err := k.EncryptString("8837261")
	if err != nil {
		t.Fatal(err)
	}
	exec(t, pool, `INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, status, created_at,
		updated_at, lead_reduced_changes) VALUES (502, 21, 'host', 'uid-502', '2026-11-20', '2026-11-21', 'cancelled',
		'2026-11-15T10:00:00', '2026-11-15T10:00:00', 0)`)
	exec(t, pool, `INSERT INTO door_code (id, reservation_id, apartment_id, lock_id, code_kind, state, attempts,
		created_at, updated_at, pin_enc) VALUES (12, 502, 21, 'L1', 'random', 'issued', 0,
		'2026-11-15T10:00:00', '2026-11-15T10:00:00', $1)`, enc)
	if err := m.DoorCodeNotice(ctx, 12, "cancelled_not_deleted"); err != nil {
		t.Fatal(err)
	}
	var cancelledPayload string
	var cancelledCC *string
	if err := pool.QueryRow(ctx, "SELECT payload, cc_email FROM email_outbox WHERE idempotency_key = $1",
		"door_code_notice:12:cancelled_not_deleted").Scan(&cancelledPayload, &cancelledCC); err != nil {
		t.Fatal(err)
	}
	var cancelled map[string]string
	if err := json.Unmarshal([]byte(cancelledPayload), &cancelled); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(cancelled["text"], "\u2022\u2022\u2022\u202261") {
		t.Fatalf("masked code missing: %q", cancelled["text"])
	}
	if cancelledCC != nil {
		t.Fatalf("cancelled_not_deleted does not copy support, got cc %v", *cancelledCC)
	}

	// A door code row that is gone is not an error (Python returns None).
	if err := m.DoorCodeNotice(ctx, 999, "failed"); err != nil {
		t.Fatalf("missing row: %v", err)
	}
}

func TestDoorCodeNoticeNoContactAddress(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	seedStay(t, pool, "   ")
	m := &Mailer{Pool: pool, Env: testEnv, Keys: keys(t), Getenv: consoleEnv}
	exec(t, pool, `INSERT INTO door_code (id, reservation_id, apartment_id, lock_id, code_kind, state, attempts,
		created_at, updated_at, last_error) VALUES (13, 501, 21, 'L1', 'random', 'failed', 0,
		'2026-11-15T10:00:00', '2026-11-15T10:00:00', 'permission')`)
	if err := m.DoorCodeNotice(ctx, 13, "failed"); err != nil {
		t.Fatal(err)
	}
	var n int
	if err := pool.QueryRow(ctx, "SELECT count(*) FROM email_outbox").Scan(&n); err != nil || n != 0 {
		t.Fatalf("no contact address must queue nothing: rows %d err=%v", n, err)
	}
}

func TestGuestPayloadReplyTo(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	seedStay(t, pool, "Desk@Example.test")
	m := &Mailer{Pool: pool, Env: testEnv, Getenv: consoleEnv}
	got, err := m.GuestPayload(ctx, 21, doorcodes.DoorCodeContent{
		Fields: map[string]any{"text": "T", "html": "H"},
	}, "cs")
	if err != nil {
		t.Fatal(err)
	}
	if got["reply_to"] != "desk@example.test" || got["lang"] != "cs" || got["html"] != "H" || got["text"] != "T" {
		t.Fatalf("guest payload %v", got)
	}
	none, err := m.GuestPayload(ctx, 404, doorcodes.DoorCodeContent{Fields: map[string]any{"text": "T"}}, "en")
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := none["reply_to"]; ok {
		t.Fatal("an unknown apartment has no reply_to")
	}
	if _, ok := none["html"]; ok {
		t.Fatal("an empty html is left out of the payload")
	}
}

func TestDrainWithoutBackendIsNoop(t *testing.T) {
	pool := testPool(t)
	m := &Mailer{Pool: pool, Env: testEnv, Getenv: func(string) string { return "" }}
	if err := m.Drain(context.Background(), 4); err != nil {
		t.Fatal(err)
	}
}

func TestNotPortedStubs(t *testing.T) {
	ctx := context.Background()
	if _, _, err := (Billing{}).ReservationProgress(ctx, 1); err != ErrNotPorted {
		t.Fatalf("ReservationProgress: %v", err)
	}
	if _, err := (Billing{}).CompletionFee(ctx, 1, 1); err != ErrNotPorted {
		t.Fatalf("CompletionFee: %v", err)
	}
	if err := (Confirmations{}).MaybeNotifyCompletion(ctx, 1, 1, false); err != ErrNotPorted {
		t.Fatalf("MaybeNotifyCompletion: %v", err)
	}
}
