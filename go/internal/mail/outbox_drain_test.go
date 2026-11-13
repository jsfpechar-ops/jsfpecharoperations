package mail

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// Database tests for Drain, SendNow and Purge (brief 1231).

func obQueue(t *testing.T, pool *pgxpool.Pool, key, kind, to string, payload map[string]any, attempts int, next string) int64 {
	t.Helper()
	raw, _ := json.Marshal(payload)
	var id int64
	err := pool.QueryRow(context.Background(),
		`INSERT INTO email_outbox (idempotency_key, kind, to_email, subject, payload, state, attempts, next_attempt_at, created_at, updated_at)
		 VALUES ($1, $2, $3, 'Subject', $4, 'queued', $5, $6, '2026-11-13T09:00:00+00:00', '2026-11-13T09:00:00+00:00')
		 RETURNING id`, key, kind, to, string(raw), attempts, next).Scan(&id)
	if err != nil {
		t.Fatal(err)
	}
	return id
}

func obRowState(t *testing.T, pool *pgxpool.Pool, id int64) (state string, attempts int, lastErr, provider, next *string) {
	t.Helper()
	err := pool.QueryRow(context.Background(),
		`SELECT state, attempts, last_error, provider_id, next_attempt_at FROM email_outbox WHERE id = $1`, id).
		Scan(&state, &attempts, &lastErr, &provider, &next)
	if err != nil {
		t.Fatal(err)
	}
	return
}

func TestDrainConsole(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	cfg.Backend = BackendConsole
	cfg.Deployment = "staging"
	obSeedFiles(t, pool, g)
	ctx := context.Background()
	due := "2026-11-13T09:59:59Z" // before 10:00:00+00:00 as text
	ok := obQueue(t, pool, "k1", "completion", "guest@example.test", map[string]any{"text": "hello", "html": "<p>hello</p>", "stay_fee_filing_id": 7}, 0, due)
	bad := obQueue(t, pool, "k2", "claim", "guest@example.test", map[string]any{"text": "{{claim_secret}}"}, 0, due)
	later := obQueue(t, pool, "k3", "completion", "guest@example.test", map[string]any{"text": "later"}, 0, "2026-11-13T11:00:00Z")
	sum, err := Drain(ctx, pool, cfg, 8)
	if err != nil {
		t.Fatal(err)
	}
	if sum != (Summary{Sent: 1, Skipped: 1}) {
		t.Fatalf("summary %+v", sum)
	}
	state, attempts, lastErr, provider, _ := obRowState(t, pool, ok)
	if state != "sent" || attempts != 1 || lastErr != nil || provider == nil || *provider != fmt.Sprintf("console:%d", ok) {
		t.Fatalf("sent row: %s %d %v %v", state, attempts, lastErr, provider)
	}
	var text string
	var htmlCol *string
	if err := pool.QueryRow(ctx, `SELECT body_text, body_html FROM console_mail_log WHERE outbox_id = $1`, ok).Scan(&text, &htmlCol); err != nil {
		t.Fatal(err)
	}
	if text != "hello\n\n[Attachments: poplatek-z-pobytu-2026-10.pdf]" || htmlCol == nil || *htmlCol != "<p>hello</p>" {
		t.Fatalf("console log %q %v", text, htmlCol)
	}
	state, attempts, lastErr, _, next := obRowState(t, pool, bad)
	if state != "queued" || attempts != 1 || lastErr == nil || strings.Contains(*lastErr, "@") || next == nil || *next != "2026-11-13T10:02:00Z" {
		t.Fatalf("failed row: %s %d %v %v", state, attempts, lastErr, next)
	}
	if state, _, _, _, _ := obRowState(t, pool, later); state != "queued" {
		t.Fatalf("not yet due row was touched: %s", state)
	}
	var logs int
	_ = pool.QueryRow(ctx, `SELECT count(*) FROM console_mail_log`).Scan(&logs)
	if logs != 1 {
		t.Fatalf("console log rows %d", logs)
	}
}

func TestDrainTerminalFailureRaisesAlert(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	cfg.Backend = BackendConsole
	ctx := context.Background()
	id := obQueue(t, pool, "k1", "claim", "jan.novak@example.test", map[string]any{"text": "{{claim_secret}}"}, 7, "2026-11-13T09:00:00Z")
	sum, err := Drain(ctx, pool, cfg, 8)
	if err != nil || sum.Failed != 1 {
		t.Fatalf("%+v %v", sum, err)
	}
	state, attempts, lastErr, _, next := obRowState(t, pool, id)
	if state != "failed" || attempts != 8 || lastErr == nil || next == nil || *next != "2026-11-13T14:16:00Z" {
		t.Fatalf("terminal row: %s %d %v %v", state, attempts, lastErr, next)
	}
	var level, kind, key, message, detail, params string
	err = pool.QueryRow(ctx, `SELECT level, kind, dedupe_key, message, detail, params FROM alert WHERE dedupe_key = $1`,
		fmt.Sprintf("mail_failed:%d", id)).Scan(&level, &kind, &key, &message, &detail, &params)
	if err != nil {
		t.Fatal(err)
	}
	if level != "warning" || kind != "mail_failed" || message != "E-mail could not be sent (claim)." {
		t.Fatalf("alert %s %s %s", level, kind, message)
	}
	if !strings.HasPrefix(detail, "To j********@e******.test: ") || strings.Contains(detail+params, "jan.novak") {
		t.Fatalf("alert leaks the address or has the wrong shape: %q %q", detail, params)
	}
	wantParams := `{"error": "` + *lastErr + `", "kind": "claim", "to": "j********@e******.test"}`
	if params != wantParams {
		t.Fatalf("params %q want %q", params, wantParams)
	}
}

func TestDrainResetsStaleSending(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	cfg.Backend = BackendConsole
	ctx := context.Background()
	id := obQueue(t, pool, "k1", "completion", "guest@example.test", map[string]any{"text": "hi"}, 0, "2026-11-13T09:00:00Z")
	fresh := obQueue(t, pool, "k2", "completion", "guest@example.test", map[string]any{"text": "hi"}, 0, "2026-11-13T09:00:00Z")
	for _, r := range []struct {
		id      int64
		updated string
	}{{id, "2026-11-13T09:49:00+00:00"}, {fresh, "2026-11-13T09:51:00+00:00"}} {
		if _, err := pool.Exec(ctx, `UPDATE email_outbox SET state = 'sending', updated_at = $1 WHERE id = $2`, r.updated, r.id); err != nil {
			t.Fatal(err)
		}
	}
	sum, err := Drain(ctx, pool, cfg, 8)
	if err != nil || sum.Sent != 1 {
		t.Fatalf("%+v %v", sum, err)
	}
	if state, _, _, _, _ := obRowState(t, pool, id); state != "sent" {
		t.Fatalf("stale row %s", state)
	}
	if state, _, _, _, _ := obRowState(t, pool, fresh); state != "sending" {
		t.Fatalf("fresh sending row must be left alone, got %s", state)
	}
}

func TestDrainSESRequest(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	var gotPath, gotAuth, gotDate, gotType string
	var gotBody map[string]any
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath, gotAuth, gotDate, gotType = r.URL.Path, r.Header.Get("Authorization"), r.Header.Get("X-Amz-Date"), r.Header.Get("Content-Type")
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &gotBody)
		// the signature must verify against the request as received
		date, auth := obSignV4(r.Host, r.URL.Path, "eu-central-1", "ses", "AKIDEXAMPLE", "secret", cfg.now(), raw)
		if date != gotDate || auth != gotAuth {
			http.Error(w, "bad signature", 403)
			return
		}
		_, _ = w.Write([]byte(`{"MessageId":"0100abc"}`))
	}))
	defer srv.Close()
	cfg.SESEndpoint = srv.URL
	cfg.HTTPClient = srv.Client()
	ctx := context.Background()
	id := obQueue(t, pool, "k1", "lifecycle_no_guest", "host@example.test",
		map[string]any{"text": "tip", "html": "<p>tip</p>", "reply_to": "r@example.test", "list_unsubscribe": "https://app.example.test/u/1"},
		0, "2026-11-13T09:00:00Z")
	sum, err := Drain(ctx, pool, cfg, 8)
	if err != nil || sum.Sent != 1 {
		t.Fatalf("%+v %v", sum, err)
	}
	state, _, _, provider, _ := obRowState(t, pool, id)
	if state != "sent" || provider == nil || *provider != "0100abc" {
		t.Fatalf("row %s %v", state, provider)
	}
	if gotPath != "/v2/email/outbound-emails" || gotType != "application/json" || !strings.HasPrefix(gotAuth, "AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20261113/eu-central-1/ses/aws4_request") {
		t.Fatalf("request %s %s %s", gotPath, gotType, gotAuth)
	}
	simple := gotBody["Content"].(map[string]any)["Simple"].(map[string]any)
	body := simple["Body"].(map[string]any)
	if gotBody["FromEmailAddress"] != "UbyHost <noreply@mail.example.test>" ||
		simple["Subject"].(map[string]any)["Data"] != "Subject" ||
		body["Text"].(map[string]any)["Data"] != "tip" || body["Html"].(map[string]any)["Data"] != "<p>tip</p>" ||
		gotBody["ReplyToAddresses"].([]any)[0] != "r@example.test" ||
		gotBody["Destination"].(map[string]any)["ToAddresses"].([]any)[0] != "host@example.test" {
		t.Fatalf("body %v", gotBody)
	}
	headers := simple["Headers"].([]any)
	if len(headers) != 2 || headers[0].(map[string]any)["Name"] != "List-Unsubscribe" {
		t.Fatalf("headers %v", headers)
	}
}

func TestDrainSESErrorsDoNotLeakAddresses(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Amzn-ErrorType", "MessageRejected:http://internal.amazon.com/coral/")
		w.WriteHeader(400)
		_, _ = w.Write([]byte(`{"message":"Email address is not verified: guest@example.test"}`))
	}))
	defer srv.Close()
	cfg.SESEndpoint = srv.URL
	cfg.HTTPClient = srv.Client()
	id := obQueue(t, pool, "k1", "completion", "guest@example.test", map[string]any{"text": "x"}, 0, "2026-11-13T09:00:00Z")
	if sum, err := Drain(context.Background(), pool, cfg, 8); err != nil || sum.Skipped != 1 {
		t.Fatalf("%+v %v", sum, err)
	}
	_, _, lastErr, _, _ := obRowState(t, pool, id)
	if lastErr == nil || *lastErr != "SES SendEmail failed: HTTP 400 (MessageRejected)" {
		t.Fatalf("last_error %v", lastErr)
	}
	// a response without a MessageId is an error too
	srv2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { _, _ = w.Write([]byte(`{}`)) }))
	defer srv2.Close()
	cfg.SESEndpoint = srv2.URL
	if _, err := cfg.sesSend(context.Background(), sesRequest{}); err == nil || !strings.Contains(err.Error(), "MessageId") {
		t.Fatalf("no message id: %v", err)
	}
}

func TestPurge(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	ctx := context.Background()
	_ = g
	now := time.Date(2026, 11, 13, 10, 0, 0, 123456000, time.UTC) // 11:00 in Prague
	// cutoff = 2026-10-30T11:00:00.123456 (Prague wall clock, microseconds kept)
	ins := func(key, state, updated string) {
		if _, err := pool.Exec(ctx,
			`INSERT INTO email_outbox (idempotency_key, kind, to_email, state, created_at, updated_at) VALUES ($1, 'completion', 'a@b.test', $2, $3, $3)`,
			key, state, updated); err != nil {
			t.Fatal(err)
		}
	}
	ins("old-sent", "sent", "2026-10-30T10:00:00+00:00")
	ins("old-failed", "failed", "2026-10-01T10:00:00+00:00")
	ins("old-queued", "queued", "2026-10-01T10:00:00+00:00")
	ins("new-sent", "sent", "2026-11-12T10:00:00+00:00")
	for i, at := range []string{"2026-10-29T10:00:00+00:00", "2026-11-12T10:00:00+00:00"} {
		if _, err := pool.Exec(ctx, `INSERT INTO console_mail_log (outbox_id, created_at) VALUES ($1, $2)`, i, at); err != nil {
			t.Fatal(err)
		}
	}
	n, err := Purge(ctx, pool, now, 14)
	if err != nil || n != 2 {
		t.Fatalf("purged %d %v", n, err)
	}
	var left, logs int
	_ = pool.QueryRow(ctx, `SELECT count(*) FROM email_outbox`).Scan(&left)
	_ = pool.QueryRow(ctx, `SELECT count(*) FROM console_mail_log`).Scan(&logs)
	if left != 2 || logs != 1 {
		t.Fatalf("left %d logs %d", left, logs)
	}
	if got := obIsoNaive(time.Date(2026, 10, 30, 11, 0, 0, 123456000, time.UTC)); got != "2026-10-30T11:00:00.123456" {
		t.Fatalf("iso %s", got)
	}
	if got := obIsoNaive(time.Date(2026, 10, 30, 11, 0, 0, 0, time.UTC)); got != "2026-10-30T11:00:00" {
		t.Fatalf("iso %s", got)
	}
}

func TestSendNow(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	ctx := context.Background()
	env := map[string]string{"UBYHOST_MAIL_BACKEND": "console", "UBYHOST_DATA_KEYS": g.FernetKey, "UBYHOST_DATA_KEY_LEGACY": "0"}
	getenv := func(k string) string { return env[k] }
	due := "2026-11-13T09:00:00Z"
	ok := obQueue(t, pool, "k1", "login_link", "guest@example.test", map[string]any{"text": "hi"}, 0, due)
	bad := obQueue(t, pool, "k2", "claim", "guest@example.test", map[string]any{"text": "{{claim_secret}}"}, 2, due)
	if err := SendNow(ctx, pool, getenv, 0); err != nil {
		t.Fatalf("id 0: %v", err)
	}
	if err := SendNow(ctx, pool, getenv, 999999); err != nil {
		t.Fatalf("missing row: %v", err)
	}
	env["UBYHOST_MAIL_BACKEND"] = "disabled"
	if err := SendNow(ctx, pool, getenv, ok); err != nil {
		t.Fatalf("disabled: %v", err)
	}
	if state, _, _, _, _ := obRowState(t, pool, ok); state != "queued" {
		t.Fatalf("disabled mail must not touch the row: %s", state)
	}
	env["UBYHOST_MAIL_BACKEND"] = "smtp"
	if err := SendNow(ctx, pool, getenv, ok); err == nil {
		t.Fatal("an invalid backend is a config error")
	}
	env["UBYHOST_MAIL_BACKEND"] = "console"
	if err := SendNow(ctx, pool, getenv, ok); err != nil {
		t.Fatal(err)
	}
	if state, attempts, _, provider, _ := obRowState(t, pool, ok); state != "sent" || attempts != 1 || provider == nil || *provider != fmt.Sprintf("console:%d", ok) {
		t.Fatalf("sent: %s %d %v", state, attempts, provider)
	}
	if err := SendNow(ctx, pool, getenv, ok); err != nil {
		t.Fatalf("a sent row is left alone: %v", err)
	}
	var logs int
	_ = pool.QueryRow(ctx, `SELECT count(*) FROM console_mail_log WHERE outbox_id = $1`, ok).Scan(&logs)
	if logs != 1 {
		t.Fatalf("sent twice: %d log rows", logs)
	}
	// a failed delivery is not an error: the row stays queued with back-off
	if err := SendNow(ctx, pool, getenv, bad); err != nil {
		t.Fatalf("failed delivery must not be an error: %v", err)
	}
	if state, attempts, lastErr, _, next := obRowState(t, pool, bad); state != "queued" || attempts != 3 || lastErr == nil || next == nil || *next == due {
		t.Fatalf("failed row: %s %d %v %v", state, attempts, lastErr, next)
	}
}

func TestNoDetailsRendererPutsRowBack(t *testing.T) {
	g := obLoadGolden(t)
	pool := obTestPool(t)
	cfg := obTestConfig(t, g)
	cfg.Backend = BackendConsole
	ctx := context.Background()
	saved := obDefaultDetails
	obDefaultDetails = nil
	defer func() { obDefaultDetails = saved }()
	id := obQueue(t, pool, "k1", "guest_details_host", "host@example.test",
		map[string]any{"text": "{{guest_details}}", "guest_details_reservation_id": 5}, 0, "2026-11-13T09:00:00Z")
	if _, err := Drain(ctx, pool, cfg, 8); !errors.Is(err, ErrNoDetailsRenderer) {
		t.Fatalf("drain: %v", err)
	}
	if err := cfg.sendNow(ctx, pool, id); !errors.Is(err, ErrNoDetailsRenderer) {
		t.Fatalf("send_now: %v", err)
	}
	if state, attempts, lastErr, _, _ := obRowState(t, pool, id); state != "queued" || attempts != 0 || lastErr != nil {
		t.Fatalf("row must be put back untouched: %s %d %v", state, attempts, lastErr)
	}
	cfg.Details = obFakeDetails{}
	if sum, err := Drain(ctx, pool, cfg, 8); err != nil || sum.Sent != 1 {
		t.Fatalf("with a renderer: %+v %v", sum, err)
	}
}
