package signup

import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// These tests need UBYHOST_TEST_DATABASE_URL (testPool skips without it).

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_signup_%d", time.Now().UnixNano())
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

const dbSecret = "signup-db-test-secret-0123456789-abcdefgh"

var dbVars = map[string]string{
	"UBYHOST_SECRET_KEY":        dbSecret,
	"UBYHOST_MAIL_BACKEND":      "console",
	"UBYHOST_META_DATASET_ID":   "1",
	"UBYHOST_META_ACCESS_TOKEN": "t",
	"UBYHOST_BILLING_ENABLED":   "1",
	"UBYHOST_PUBLIC_BASE_URL":   "https://ubyhost.example",
}

func dbEnv(k string) string { return dbVars[k] }

func one(t *testing.T, pool *pgxpool.Pool, sql string, args ...any) string {
	t.Helper()
	var v *string
	if err := pool.QueryRow(context.Background(), "SELECT ("+sql+")::text", args...).Scan(&v); err != nil {
		t.Fatalf("%s: %v", sql, err)
	}
	if v == nil {
		return "NULL"
	}
	return *v
}

// outboxToken decrypts the claim secret of an outbox row.
func outboxToken(t *testing.T, pool *pgxpool.Pool, key string) string {
	t.Helper()
	var payload map[string]string
	if err := json.Unmarshal([]byte(one(t, pool, `SELECT payload FROM email_outbox WHERE idempotency_key = $1`, key)), &payload); err != nil {
		t.Fatal(err)
	}
	keys, err := secure.LoadDataKeys(dbEnv)
	if err != nil {
		t.Fatal(err)
	}
	plain, err := keys.Decrypt(payload["claim_secret_enc"], 0, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(payload["text"], "/signup/verify?t={{claim_secret}}") || payload["lang"] == "" {
		t.Fatalf("payload %v", payload)
	}
	return string(plain)
}

func TestSignupFlowDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Unix(1798761600, 0).UTC()
	click, err := IssueClick(dbSecret, map[string]string{"gclid": "G1", "fbclid": "FB1"}, now.UnixMilli()-1000)
	if err != nil {
		t.Fatal(err)
	}
	in := RegisterInput{
		Email: "anna@example.com", Workspace: "Chata", Lang: "cs",
		Attr:      map[string]string{"utm_source": "google", "utm_medium": "cpc", "click": click},
		Consents:  map[string]bool{Google: true, Meta: true},
		Selection: url.Values{"plan": {"max"}, "apts": {"3"}},
		IP:        "203.0.113.9", UserAgent: "Mozilla/5.0 \x01(X11)",
	}
	if out, err := Register(ctx, pool, dbEnv, in, now); out != "created" || err != nil {
		t.Fatalf("register: %s %v", out, err)
	}
	id := int64(1)
	if got := one(t, pool, `SELECT concat_ws('|', active, email, display_name, signup_source, signup_selection_json,
		signup_utm_source, signup_utm_medium, coalesce(signup_utm_campaign, '-'), signup_at, password_hash = '')
		FROM user_account WHERE id = 1`); got != `0|anna@example.com|Chata|google|{"apartments": "3", "plan": "max"}|google|cpc|-|2027-01-01T00:00:00+00:00|t` {
		t.Errorf("account %s", got)
	}
	if got := one(t, pool, `SELECT string_agg(concat_ws('|', platform, coalesce(gclid, '-'), coalesce(fbc, '-'),
		coalesce(client_user_agent, '-'), clicked_at, t.version), ';' ORDER BY platform) FROM ad_click c JOIN consent_texts t ON t.id = c.consent_text_id`); got !=
		"google|G1|-|-|2026-12-31T23:59:59+00:00|ads-google-v1-cs;meta|-|fb.1.1798761599000.FB1|Mozilla/5.0 (X11)|2026-12-31T23:59:59+00:00|ads-meta-v2-cs" {
		t.Errorf("clicks %s", got)
	}
	if got := one(t, pool, `SELECT string_agg(document || version || ip, ',' ORDER BY id) FROM legal_acceptance`); got != "terms1.7203.0.113.9,privacy1.8203.0.113.9,dpa1.8203.0.113.9" {
		t.Errorf("acceptance %s", got)
	}
	if got := one(t, pool, `SELECT string_agg(action || ':' || actor || ':' || detail, ',' ORDER BY id) FROM audit`); got !=
		"legal_accepted:"+one(t, pool, `SELECT username FROM user_account WHERE id = 1`)+":terms_v1.7 privacy_v1.8 dpa_v1.8 method=clickwrap,signup_created:anonymous:" {
		t.Errorf("audit %s", got)
	}
	nonce := one(t, pool, `SELECT signup_verify_nonce FROM user_account WHERE id = 1`)
	first := outboxToken(t, pool, "signup_verify:1:"+nonce)
	if a, err := PendingAccount(ctx, pool, dbSecret, first, now); err != nil || a == nil || a.ID != id {
		t.Fatalf("pending account: %+v %v", a, err)
	}
	// Signing up again replaces the workspace and retires the first link.
	in.Workspace, in.Consents = "Chata 2", nil
	if out, _ := Register(ctx, pool, dbEnv, in, now); out != "refreshed" {
		t.Fatalf("second register: %s", out)
	}
	if a, _ := PendingAccount(ctx, pool, dbSecret, first, now); a != nil {
		t.Error("older link still works")
	}
	if n := one(t, pool, `SELECT count(*) FROM ad_click`); n != "0" {
		t.Errorf("unticked boxes kept %s click rows", n)
	}
	in.Consents = map[string]bool{Google: true, Meta: true}
	if out, _ := Register(ctx, pool, dbEnv, in, now); out != "refreshed" {
		t.Fatal("third register")
	}
	nonce = one(t, pool, `SELECT signup_verify_nonce FROM user_account WHERE id = 1`)
	a, err := PendingAccount(ctx, pool, dbSecret, outboxToken(t, pool, "signup_verify:1:"+nonce), now)
	if err != nil || a == nil {
		t.Fatalf("pending %v", err)
	}
	if ok, err := Activate(ctx, pool, dbEnv, a, now); !ok || err != nil {
		t.Fatalf("activate %v", err)
	}
	if ok, _ := Activate(ctx, pool, dbEnv, a, now); ok {
		t.Error("second activation won")
	}
	if got := one(t, pool, `SELECT concat_ws('|', status, trial_started_at, trial_ends_at) FROM billing_account WHERE owner_user_id = 1`); got != "trialing|2027-01-01|2027-01-31" {
		t.Errorf("billing %s", got)
	}
	if got := one(t, pool, `SELECT send_state || length(event_id) FROM ad_click WHERE platform = 'meta'`); got != "pending32" {
		t.Errorf("meta event %s", got)
	}
	if got := one(t, pool, `SELECT to_email || subject FROM email_outbox WHERE idempotency_key = 'signup_admin:1'`); got != "support@ubyhost.comNew UbyHost sign-up: Chata 2" {
		t.Errorf("admin mail %s", got)
	}
	// An active account: the exists mail, once per hour.
	for i := 0; i < 2; i++ {
		if out, _ := Register(ctx, pool, dbEnv, in, now.Add(time.Duration(i)*time.Minute)); out != "exists" {
			t.Fatal("register on active account")
		}
	}
	if n := one(t, pool, `SELECT count(*) FROM email_outbox WHERE idempotency_key = 'signup_exists:1:2027-01-01T00'`); n != "1" {
		t.Errorf("exists mails %s", n)
	}
	if ok, _ := ResendOperator(ctx, pool, 1, "operator:admin", dbEnv, now); ok {
		t.Error("resend on an active account")
	}
	// Withdrawal blanks the ids, keeps the record, and stops the Meta event.
	if ok, err := WithdrawConsent(ctx, pool, 1, Meta, "host", now); !ok || err != nil {
		t.Fatalf("withdraw %v", err)
	}
	if ok, _ := WithdrawConsent(ctx, pool, 1, Meta, "host", now); ok {
		t.Error("withdrew twice")
	}
	if got := one(t, pool, `SELECT concat_ws('|', coalesce(fbc, '-'), coalesce(client_user_agent, '-'), send_state, withdrawn_at, ids_deleted_at) FROM ad_click WHERE platform = 'meta'`); got != "-|-|withdrawn|2027-01-01T00:00:00+00:00|2027-01-01T00:00:00+00:00" {
		t.Errorf("withdrawn %s", got)
	}
	if ok, _ := HasClick(ctx, pool, 1, Meta); ok {
		t.Error("withdrawn click still live")
	}
	cs, err := ConsentsFor(ctx, pool, 1)
	if err != nil || len(cs) != 2 || cs[0].Platform != Google || cs[1].WithdrawnAt == nil {
		t.Errorf("consents %+v %v", cs, err)
	}
	// Export: once, then only with again.
	body, n, err := ExportConversions(ctx, pool, dbEnv, now, false)
	if err != nil || n != 1 || !strings.HasSuffix(body, "G1,UbyHost sign-up,2027-01-01 01:00:00+0100,Granted,Denied\r\n") {
		t.Errorf("export %d %q %v", n, body, err)
	}
	if _, n, _ := ExportConversions(ctx, pool, dbEnv, now.Add(time.Hour), false); n != 0 {
		t.Error("exported twice")
	}
	if _, n, _ := ExportConversions(ctx, pool, dbEnv, now.Add(time.Hour), true); n != 1 {
		t.Error("again lost the row")
	}
	if got := one(t, pool, `SELECT uploaded_at FROM ad_click WHERE platform = 'google'`); got != "2027-01-01T00:00:00+00:00" {
		t.Errorf("uploaded_at %s", got)
	}
	if _, n, _ := ExportConversions(ctx, pool, dbEnv, now.Add(86*24*time.Hour), true); n != 0 {
		t.Error("row older than 85 days exported")
	}
}

func TestResendAndLimitsDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	now := time.Unix(1798761600, 0).UTC()
	in := RegisterInput{Email: "bob@example.com", Workspace: "", Lang: "en", Attr: map[string]string{}}
	if out, err := Register(ctx, pool, dbEnv, in, now); out != "created" || err != nil {
		t.Fatalf("register %s %v", out, err)
	}
	old := one(t, pool, `SELECT signup_verify_nonce FROM user_account WHERE id = 1`)
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, created_at, role)
		VALUES (99, 'admin01', '', '2026-01-01T00:00:00+00:00', 'admin')`); err != nil {
		t.Fatal(err)
	}
	actx := WithAuditActor(ctx, 99, "admin01", false)
	if ok, err := ResendOperator(actx, pool, 1, "operator:admin01", dbEnv, now.Add(time.Minute)); !ok || err != nil {
		t.Fatalf("resend %v", err)
	}
	nonce := one(t, pool, `SELECT signup_verify_nonce FROM user_account WHERE id = 1`)
	if nonce == old {
		t.Error("nonce not replaced")
	}
	if got := one(t, pool, `SELECT actor || ':' || actor_user_id || ':' || coalesce(impersonator_user_id::text, '-') FROM audit WHERE action = 'signup_resend_operator'`); got != "operator:admin01:99:-" {
		t.Errorf("resend audit %s", got)
	}
	var payload map[string]string
	_ = json.Unmarshal([]byte(one(t, pool, `SELECT payload FROM email_outbox WHERE idempotency_key = $1`, "signup_verify:1:"+nonce)), &payload)
	user := one(t, pool, `SELECT username FROM user_account WHERE id = 1`)
	if payload["lang"] != "cs" || !strings.Contains(payload["text"], "„"+user+"“") {
		t.Errorf("resend mail lang %q text %q", payload["lang"], payload["text"])
	}
	if ok, err := ResendOperator(ctx, pool, 42, "operator:x", dbEnv, now); ok || err != nil {
		t.Error("resend for a missing account")
	}
	if ok, _ := HasClick(ctx, pool, 1, Google); ok {
		t.Error("click without consent stored")
	}
	if got := one(t, pool, `SELECT signup_source FROM user_account WHERE id = 1`); got != "none" {
		t.Errorf("source %s", got)
	}
	for i := 0; i < SignupEmailMax; i++ {
		if blocked, _ := RateLimited(ctx, pool, "ip1", "bob@example.com", now); blocked {
			t.Fatalf("blocked after %d", i)
		}
		if err := RecordAttempt(ctx, pool, "ip1", "bob@example.com", now); err != nil {
			t.Fatal(err)
		}
	}
	if blocked, _ := RateLimited(ctx, pool, "ip1", "bob@example.com", now); !blocked {
		t.Error("e-mail budget not enforced")
	}
	if blocked, _ := RateLimited(ctx, pool, "ip1", "", now); blocked {
		t.Error("ip budget spent after 3")
	}
	if blocked, _ := RateLimited(ctx, pool, "ip1", "", now.Add(time.Hour+time.Second)); blocked {
		t.Error("budget did not reset after an hour")
	}
	// Wording edited without a version bump is filed under a hashed version.
	first, err := ConsentTextID(ctx, pool, Google, "en", now)
	if err != nil {
		t.Fatal(err)
	}
	if again, _ := ConsentTextID(ctx, pool, Google, "en", now); again != first {
		t.Error("consent text not reused")
	}
	if _, err := pool.Exec(ctx, `UPDATE consent_texts SET text_sha256 = 'x' WHERE id = $1`, first); err != nil {
		t.Fatal(err)
	}
	moved, err := ConsentTextID(ctx, pool, Google, "en", now)
	if err != nil || moved == first {
		t.Fatalf("hashed version %d %v", moved, err)
	}
	if v := one(t, pool, `SELECT version FROM consent_texts WHERE id = $1`, moved); !regexp.MustCompile(`^ads-google-v1-en-[0-9a-f]{8}$`).MatchString(v) {
		t.Errorf("hashed version %s", v)
	}
}
