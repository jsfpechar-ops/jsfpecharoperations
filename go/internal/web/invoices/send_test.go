package invoices

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

func TestSendRouteIsRegistered(t *testing.T) {
	seen := false
	for _, r := range Routes(nil, testEnv(), testNow) {
		if r.Pattern == "POST /invoices/{id}/send" {
			seen = true
		}
	}
	if !seen {
		t.Fatal("POST /invoices/{id}/send missing")
	}
}

func TestSendRouteListedInRegisterWebInvoices(t *testing.T) {
	// Covered by cmd/ubyhost-web/register_web_invoices_test.go (step 2).
	_ = strings.Contains
}

func TestSendInvoiceQueuesMail(t *testing.T) {
	app, seed := newTestApp(t)
	id, _ := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	token := app.token(id, testNow)
	path := "/invoices/" + itoa(id) + "/send"
	rec := app.do(http.MethodPost, path, url.Values{}, &host1)
	loc := rec.Header().Get("Location")
	if rec.Code != 303 || !strings.HasPrefix(loc, "/invoices/"+itoa(id)+"?msg=") {
		t.Fatalf("send: %d %q", rec.Code, loc)
	}
	var kind, key, to, subject, payload string
	if err := app.pool.QueryRow(context.Background(),
		`SELECT kind, idempotency_key, to_email, subject, payload FROM email_outbox WHERE idempotency_key = $1`,
		"invoice_issued:"+itoa(id)+":0").Scan(&kind, &key, &to, &subject, &payload); err != nil {
		t.Fatal(err)
	}
	if kind != "invoice_issued" || to != "jana@example.test" || strings.Contains(subject, token) {
		t.Fatalf("outbox: %s %s %q", kind, to, subject)
	}
	if !strings.Contains(payload, mail.ClaimSecretMarker) || !strings.Contains(payload, `"`+mail.ClaimSecretPayloadKey+`"`) || strings.Contains(payload, token) {
		t.Fatalf("payload: %s", payload)
	}
	var emailed string
	if err := app.pool.QueryRow(context.Background(), `SELECT COALESCE(emailed_at,'') FROM invoice WHERE id = $1`, id).Scan(&emailed); err != nil || emailed != "2026-11-13T10:00:00+00:00" {
		t.Fatalf("emailed_at %q %v", emailed, err)
	}
	if app.count(`SELECT COUNT(*) FROM audit WHERE action = 'invoice_sent' AND detail = $1 AND actor = 'host1'`, "id="+itoa(id)) != 1 {
		t.Error("audit invoice_sent")
	}
	again := app.do(http.MethodPost, path, url.Values{}, &host1)
	if again.Code != 303 || !strings.HasPrefix(again.Header().Get("Location"), "/invoices/"+itoa(id)+"?msg=") {
		t.Fatalf("second send: %d", again.Code)
	}
	if app.count(`SELECT COUNT(*) FROM email_outbox WHERE kind = 'invoice_issued' AND idempotency_key LIKE $1`, "invoice_issued:"+itoa(id)+":%") != 2 {
		t.Error("two outbox rows after two sends")
	}
	var key1 string
	if err := app.pool.QueryRow(context.Background(),
		`SELECT idempotency_key FROM email_outbox WHERE idempotency_key = $1`,
		"invoice_issued:"+itoa(id)+":1").Scan(&key1); err != nil {
		t.Fatal(err)
	}
	// HTML and text are in the payload json; the marker must be in text, not the raw token.
	var pl map[string]string
	if err := json.Unmarshal([]byte(payload), &pl); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(pl["text"], mail.ClaimSecretMarker) {
		t.Errorf("text lacks marker: %q", pl["text"])
	}
}