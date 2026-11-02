package payments

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const requestCSRFCookie = "requests-test-csrf-cookie"

// fakeLinks is the card rail: it answers SendPaymentLink with a fixed result.
type fakeLinks struct {
	url   string
	err   error
	calls int
}

func (f *fakeLinks) SendPaymentLink(_ context.Context, _ int64) (string, error) {
	f.calls++
	return f.url, f.err
}

// requestCall posts form as host uid (0 means signed out) with a valid CSRF
// token and the Czech language cookie.
func requestCall(t *testing.T, h http.Handler, path string, uid int64, form url.Values) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("x-csrf-token", connectCSRF(t, requestCSRFCookie))
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: requestCSRFCookie})
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "cs"})
	if uid != 0 {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: connectSession(uid, nil)})
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// requestSeed: onboardSeed (hosts 1 and 3, entity 1 of host 1 with no contact
// yet), apartments 1 (host 1) and 2 (host 3), reservations 1 and 2 (ical),
// reservation 3 (demo, host 1), and payment requests 10 to 17.
func requestSeed(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	onboardSeed(t, pool)
	const ts = "2026-11-01T00:00:00+00:00"
	stmts := []string{
		`INSERT INTO apartment (id, legal_entity_id, owner_user_id, internal_name, created_at) VALUES
			(1, 1, 1, 'Byt A', '2026-01-01T00:00:00+00:00'), (2, NULL, 3, 'Byt B', '2026-01-01T00:00:00+00:00')`,
		fmt.Sprintf(`INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, summary, status, created_at, updated_at) VALUES
			(1, 1, 'ical', 'r1', '2026-12-01', '2026-12-03', 'Stay A', 'active', '%[1]s', '%[1]s'),
			(2, 2, 'ical', 'r2', '2026-12-01', '2026-12-03', 'Stay B', 'active', '%[1]s', '%[1]s'),
			(3, 1, 'demo', 'r3', '2026-12-05', '2026-12-06', 'Demo', 'active', '%[1]s', '%[1]s')`, ts),
		`UPDATE legal_entity SET contact_email = 'ops@example.test' WHERE id = 1`,
		// Login sends hosts without accepted terms to /account/accept; env versions are t1, p1, d1.
		`INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method) VALUES
			(101, 1, 'terms', 't1', NOW(), 'clickwrap'), (102, 1, 'privacy', 'p1', NOW(), 'clickwrap'), (103, 1, 'dpa', 'd1', NOW(), 'clickwrap'),
			(104, 3, 'terms', 't1', NOW(), 'clickwrap'), (105, 3, 'privacy', 'p1', NOW(), 'clickwrap'), (106, 3, 'dpa', 'd1', NOW(), 'clickwrap')`,
		fmt.Sprintf(`INSERT INTO payment_request (id, owner_user_id, reservation_id, reason, amount_czk, rail, status, guest_email, expires_at, created_at, updated_at) VALUES
			(10, 1, NULL, 'repair', 250, 'qr', 'draft', 'guest@example.test', '%[1]s', '%[1]s', '%[1]s'),
			(11, 1, NULL, 'cleaning', 90, 'card', 'draft', 'guest@example.test', '%[1]s', '%[1]s', '%[1]s'),
			(12, 1, NULL, 'damage', 300, 'card', 'paid', 'guest@example.test', '%[1]s', '%[1]s', '%[1]s'),
			(13, 1, NULL, 'extra_guest', 60, 'qr', 'sent', 'guest@example.test', '%[1]s', '%[1]s', '%[1]s'),
			(14, 1, NULL, 'late_checkout', 70, 'qr', 'draft', NULL, '%[1]s', '%[1]s', '%[1]s'),
			(15, 1, 3, 'custom', 80, 'qr', 'draft', 'guest@example.test', '%[1]s', '%[1]s', '%[1]s'),
			(16, 3, NULL, 'repair', 55, 'qr', 'draft', 'guest@example.test', '%[1]s', '%[1]s', '%[1]s'),
			(17, 1, NULL, 'cleaning', 95, 'qr', 'draft', 'guest@example.test', '%[1]s', '%[1]s', '%[1]s')`, ts),
		// Ids 10 to 17 were written by hand, so move the sequence past them.
		`SELECT setval(pg_get_serial_sequence('payment_request', 'id'), 100)`,
	}
	for _, q := range stmts {
		if _, err := pool.Exec(context.Background(), q); err != nil {
			t.Fatal(err)
		}
	}
}

func requestStatus(t *testing.T, pool *pgxpool.Pool, id int) string {
	t.Helper()
	var s string
	if err := pool.QueryRow(context.Background(), `SELECT status FROM payment_request WHERE id = $1`, id).Scan(&s); err != nil {
		t.Fatal(err)
	}
	return s
}

func TestRequestNewDatabase(t *testing.T) {
	pool := testPool(t)
	requestSeed(t, pool)
	env := connectEnv("test", map[string]string{"UBYHOST_MAIL_BACKEND": "console"})
	mux := http.NewServeMux()
	mux.Handle("POST /payments/requests/new", RequestNewHandler(pool, env, connectNow))
	const path = "/payments/requests/new"
	total := func() int { return count(t, pool, `SELECT COUNT(*) FROM payment_request`) }
	before := total()

	t.Run("signed out goes to login and saves nothing", func(t *testing.T) {
		rec := requestCall(t, mux, path, 0, url.Values{"reason": {"repair"}, "amount_czk": {"100"}})
		if rec.Code != http.StatusSeeOther || strings.HasPrefix(rec.Header().Get("Location"), "/payments") {
			t.Errorf("signed out: code %d, Location %q", rec.Code, rec.Header().Get("Location"))
		}
		if total() != before {
			t.Error("signed out saved a row")
		}
	})

	t.Run("bad csrf is refused and saves nothing", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodPost, path, strings.NewReader("reason=repair&amount_czk=100"))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("x-csrf-token", "not-a-token")
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: requestCSRFCookie})
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: connectSession(1, nil)})
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		if strings.HasPrefix(rec.Header().Get("Location"), "/payments") || total() != before {
			t.Errorf("bad csrf: code %d, rows changed", rec.Code)
		}
	})

	for _, tc := range []struct {
		name string
		form url.Values
		err  bool
	}{
		{"bad reason", url.Values{"reason": {"nope"}, "amount_czk": {"100"}}, true},
		{"amount zero", url.Values{"reason": {"repair"}, "amount_czk": {"0"}}, true},
		{"amount minus one", url.Values{"reason": {"repair"}, "amount_czk": {"-1"}}, true},
		{"amount decimal", url.Values{"reason": {"repair"}, "amount_czk": {"1.5"}}, true},
		{"amount empty", url.Values{"reason": {"repair"}, "amount_czk": {""}}, true},
		{"other owner's stay", url.Values{"reason": {"repair"}, "amount_czk": {"100"}, "reservation_id": {"2"}}, true},
		{"bad rail", url.Values{"reason": {"repair"}, "amount_czk": {"100"}, "rail": {"cash"}}, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			rec := requestCall(t, mux, path, 1, tc.form)
			loc := rec.Header().Get("Location")
			if rec.Code != http.StatusSeeOther || !strings.HasPrefix(loc, "/payments?err=") {
				t.Errorf("got %d %q, want an err flash", rec.Code, loc)
			}
			if total() != before {
				t.Error("a row was saved")
			}
		})
	}

	t.Run("card draft is saved with every column", func(t *testing.T) {
		rec := requestCall(t, mux, path, 1, url.Values{
			"reason": {"cleaning"}, "amount_czk": {"90"}, "reservation_id": {"1"},
			"rail": {"card"}, "guest_email": {" Guest@Example.test "}, "guest_note": {"  note "},
		})
		if loc := rec.Header().Get("Location"); loc != "/payments?msg=Koncept%20ulo%C5%BEen." {
			t.Fatalf("Location = %q", loc)
		}
		var (
			id                                       int
			currency, status, rail, email, note, exp string
			reservation                              *int64
			vs                                       *string
			amount                                   int64
		)
		err := pool.QueryRow(context.Background(),
			`SELECT id, amount_czk, currency, status, rail, reservation_id, guest_email, guest_note, variable_symbol, expires_at
			 FROM payment_request WHERE owner_user_id = 1 AND amount_czk = 90 AND id > 17 ORDER BY id DESC LIMIT 1`,
		).Scan(&id, &amount, &currency, &status, &rail, &reservation, &email, &note, &vs, &exp)
		if err != nil {
			t.Fatal(err)
		}
		if amount != 90 || currency != "CZK" || status != "draft" || rail != "card" {
			t.Errorf("row: amount %d currency %s status %s rail %s", amount, currency, status, rail)
		}
		if reservation == nil || *reservation != 1 || email != "Guest@Example.test" || note != "note" {
			t.Errorf("row: reservation %v email %q note %q", reservation, email, note)
		}
		if vs != nil {
			t.Errorf("card row has variable symbol %q", *vs)
		}
		if want := testNow.UTC().AddDate(0, 0, 30).Format("2006-01-02"); exp != want {
			t.Errorf("expires_at = %q, want %q", exp, want)
		}
	})

	t.Run("qr draft gets the variable symbol", func(t *testing.T) {
		rec := requestCall(t, mux, path, 1, url.Values{"reason": {"repair"}, "amount_czk": {"120"}, "rail": {"qr"}})
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("code %d", rec.Code)
		}
		var id int
		var vs string
		if err := pool.QueryRow(context.Background(),
			`SELECT id, variable_symbol FROM payment_request WHERE amount_czk = 120`).Scan(&id, &vs); err != nil {
			t.Fatal(err)
		}
		if want := fmt.Sprintf("%010d", id); vs != want {
			t.Errorf("variable_symbol = %q, want %q", vs, want)
		}
	})
}

func TestRequestSendDatabase(t *testing.T) {
	pool := testPool(t)
	requestSeed(t, pool)
	env := connectEnv("test", map[string]string{"UBYHOST_MAIL_BACKEND": "console"})
	links := &fakeLinks{url: "https://pay.stripe.example/test_link"}
	mux := http.NewServeMux()
	mux.Handle("POST /payments/requests/{id}/send", RequestSendHandler(pool, env, connectNow, links))
	send := func(id int, uid int64) *httptest.ResponseRecorder {
		return requestCall(t, mux, fmt.Sprintf("/payments/requests/%d/send", id), uid, nil)
	}
	outbox := func(key string) int {
		return count(t, pool, `SELECT COUNT(*) FROM email_outbox WHERE idempotency_key = $1`, key)
	}

	t.Run("non-integer id is 404", func(t *testing.T) {
		if rec := requestCall(t, mux, "/payments/requests/abc/send", 1, nil); rec.Code != http.StatusNotFound {
			t.Errorf("code %d, want 404", rec.Code)
		}
	})

	t.Run("other owner's request is invalid", func(t *testing.T) {
		rec := send(16, 1)
		if !strings.HasPrefix(rec.Header().Get("Location"), "/payments?err=") || requestStatus(t, pool, 16) != "draft" {
			t.Errorf("got %q, status %s", rec.Header().Get("Location"), requestStatus(t, pool, 16))
		}
	})

	t.Run("paid request cannot be sent", func(t *testing.T) {
		rec := send(12, 1)
		if !strings.HasPrefix(rec.Header().Get("Location"), "/payments?err=") || requestStatus(t, pool, 12) != "paid" {
			t.Errorf("got %q", rec.Header().Get("Location"))
		}
	})

	t.Run("no guest e-mail", func(t *testing.T) {
		rec := send(14, 1)
		if !strings.HasPrefix(rec.Header().Get("Location"), "/payments?err=") || requestStatus(t, pool, 14) != "draft" {
			t.Errorf("got %q", rec.Header().Get("Location"))
		}
	})

	t.Run("qr first send moves draft to sent, audits and queues one mail", func(t *testing.T) {
		rec := send(10, 1)
		if loc := rec.Header().Get("Location"); loc != "/payments?msg=Odesl%C3%A1no%20hostovi." {
			t.Fatalf("Location = %q", loc)
		}
		if requestStatus(t, pool, 10) != "sent" {
			t.Error("status did not move to sent")
		}
		if !containsDetail(auditDetails(t, pool, "payment_request_status"), "id=10 draft->sent") {
			t.Error("no draft->sent audit row")
		}
		var subject, to, payload string
		if err := pool.QueryRow(context.Background(),
			`SELECT subject, to_email, payload FROM email_outbox WHERE idempotency_key = 'payment_request:10:sent:v1'`,
		).Scan(&subject, &to, &payload); err != nil {
			t.Fatal(err)
		}
		if subject != "Žádost o platbu od vašeho hostitele (250 Kč)" || to != "guest@example.test" {
			t.Errorf("subject %q to %q", subject, to)
		}
		// json.dumps with ensure_ascii, as Python writes it.
		want := `{"text": "Dobr\u00fd den,\n\nV\u00e1\u0161 hostitel v\u00e1s \u017e\u00e1d\u00e1 o platbu 250 K\u010d za: P\u0159\u00edsp\u011bvek na opravu.\nZapla\u0165te zde: /payments/qr/10\n\nPokud jste tuto zpr\u00e1vu ne\u010dekali, ignorujte ji.\n", "lang": "cs", "reply_to": "ops@example.test", "apartment": null}`
		if payload != want {
			t.Errorf("payload\n got %s\nwant %s", payload, want)
		}
	})

	t.Run("resend keeps the status and uses key v2", func(t *testing.T) {
		rec := send(13, 1)
		if rec.Header().Get("Location") != "/payments?msg=Odesl%C3%A1no%20hostovi." || requestStatus(t, pool, 13) != "sent" {
			t.Errorf("got %q", rec.Header().Get("Location"))
		}
		if outbox("payment_request:13:sent:v2") != 1 {
			t.Error("no v2 mail row")
		}
		if containsDetail(auditDetails(t, pool, "payment_request_status"), "id=13 draft->sent") {
			t.Error("resend wrote a status audit row")
		}
	})

	t.Run("card with stripe off flashes and sends no mail", func(t *testing.T) {
		links.err, links.url = ErrStripeOff, ""
		rec := send(11, 1)
		if !strings.HasPrefix(rec.Header().Get("Location"), "/payments?err=") || requestStatus(t, pool, 11) != "draft" {
			t.Errorf("got %q", rec.Header().Get("Location"))
		}
		if outbox("payment_request:11:sent:v1") != 0 {
			t.Error("mail queued with stripe off")
		}
	})

	t.Run("card not ready flashes", func(t *testing.T) {
		links.err, links.url = nil, ""
		rec := send(11, 1)
		if !strings.HasPrefix(rec.Header().Get("Location"), "/payments?err=") || requestStatus(t, pool, 11) != "draft" {
			t.Errorf("got %q", rec.Header().Get("Location"))
		}
	})

	t.Run("card ready puts the link in the mail", func(t *testing.T) {
		links.err, links.url = nil, "https://pay.stripe.example/test_link"
		rec := send(11, 1)
		if rec.Header().Get("Location") != "/payments?msg=Odesl%C3%A1no%20hostovi." || requestStatus(t, pool, 11) != "sent" {
			t.Errorf("got %q", rec.Header().Get("Location"))
		}
		var payload string
		if err := pool.QueryRow(context.Background(),
			`SELECT payload FROM email_outbox WHERE idempotency_key = 'payment_request:11:sent:v1'`).Scan(&payload); err != nil {
			t.Fatal(err)
		}
		if !strings.Contains(payload, "https://pay.stripe.example/test_link") {
			t.Errorf("payload has no link: %s", payload)
		}
	})

	t.Run("demo stay sends no mail but still moves to sent", func(t *testing.T) {
		send(15, 1)
		if requestStatus(t, pool, 15) != "sent" || outbox("payment_request:15:sent:v1") != 0 {
			t.Error("demo stay: status or mail wrong")
		}
	})

	t.Run("mail disabled sends no mail but still moves to sent", func(t *testing.T) {
		off := RequestSendHandler(pool, connectEnv("test", map[string]string{"UBYHOST_MAIL_BACKEND": "disabled"}), connectNow, links)
		offMux := http.NewServeMux()
		offMux.Handle("POST /payments/requests/{id}/send", off)
		links.err, links.url = nil, "https://pay.stripe.example/test_link"
		requestCall(t, offMux, "/payments/requests/17/send", 1, nil)
		if requestStatus(t, pool, 17) != "sent" || outbox("payment_request:17:sent:v1") != 0 {
			t.Error("mail disabled: status or mail wrong")
		}
	})
}
