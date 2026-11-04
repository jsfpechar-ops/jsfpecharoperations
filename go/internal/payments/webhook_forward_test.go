package payments

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// fakePy is Python's /webhooks/stripe stand-in: it records each call and
// answers a chosen status and body.
type fakePy struct {
	mu     sync.Mutex
	calls  int
	body   []byte
	sig    string
	ctype  string
	cip    string
	status int
	reply  string
}

func newFakePy(t *testing.T, status int, reply string) (*fakePy, *httptest.Server) {
	t.Helper()
	f := &fakePy{status: status, reply: reply}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		f.mu.Lock()
		f.calls++
		f.body = b
		f.sig = r.Header.Get("Stripe-Signature")
		f.ctype = r.Header.Get("Content-Type")
		f.cip = r.Header.Get("CF-Connecting-IP")
		f.mu.Unlock()
		w.WriteHeader(f.status)
		_, _ = io.WriteString(w, f.reply)
	}))
	t.Cleanup(srv.Close)
	return f, srv
}

func (f *fakePy) callCount() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.calls
}

// fwdEnv is webhookEnv plus UBYHOST_PY_WEBHOOK_URL.
func fwdEnv(mode, url string) func(string) string {
	env := webhookEnv(mode, "whsec_test")
	return func(k string) string {
		if k == "UBYHOST_PY_WEBHOOK_URL" {
			return url
		}
		return env(k)
	}
}

func fwdHandler(pool *pgxpool.Pool, mode, url string) http.HandlerFunc {
	return WebhookHandler(pool, fwdEnv(mode, url), func() time.Time { return testNow })
}

var fwdSeq int

// fwdPost sends a POST with a unique peer address (the rate limit keys on it)
// and returns the status and body Go answered.
func fwdPost(h http.HandlerFunc, body []byte, sig, cip string) (int, string) {
	fwdSeq++
	req := httptest.NewRequest(http.MethodPost, "/webhooks/stripe", bytes.NewReader(body))
	req.RemoteAddr = fmt.Sprintf("10.20.%d.%d:1234", fwdSeq/250, fwdSeq%250+1)
	req.Header.Set("Content-Type", "application/json")
	if sig != "" {
		req.Header.Set("Stripe-Signature", sig)
	}
	if cip != "" {
		req.Header.Set("CF-Connecting-IP", cip)
	}
	rec := httptest.NewRecorder()
	h(rec, req)
	return rec.Code, rec.Body.String()
}

func fwdSigned(body []byte) string {
	return fmt.Sprintf("t=%d,v1=%s", testNow.Unix(), signFor("whsec_test", testNow.Unix(), body))
}

func TestForwardBookingEventTypes(t *testing.T) {
	pool := testPool(t)
	seedHost(t, pool)
	types := []string{
		"checkout.session.completed",
		"checkout.session.async_payment_succeeded",
		"checkout.session.expired",
		"checkout.session.async_payment_failed",
	}
	for _, typ := range types {
		t.Run(typ, func(t *testing.T) {
			py, srv := newFakePy(t, http.StatusOK, "ok")
			h := fwdHandler(pool, "test", srv.URL)
			body := []byte(`{"id":"evt_fwd","type":"` + typ + `","data":{"object":{"payment_status":"paid","metadata":{"site_booking_id":"7"}}}}`)
			code, out := fwdPost(h, body, fwdSigned(body), "203.0.113.9")
			if code != 200 || out != "ok" {
				t.Errorf("got %d %q, want 200 ok", code, out)
			}
			if py.callCount() != 1 {
				t.Fatalf("python calls: %d, want 1", py.callCount())
			}
			if !bytes.Equal(py.body, body) {
				t.Errorf("forwarded body differs")
			}
			if py.sig != fwdSigned(body) {
				t.Errorf("forwarded Stripe-Signature differs")
			}
			if py.ctype != "application/json" {
				t.Errorf("forwarded Content-Type: %q", py.ctype)
			}
			if py.cip != "203.0.113.9" {
				t.Errorf("forwarded CF-Connecting-IP: %q", py.cip)
			}
			if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_fwd'`); n != 0 {
				t.Errorf("forwarded event wrote %d event rows", n)
			}
		})
	}
}

func TestForwardPassesPythonStatus(t *testing.T) {
	pool := testPool(t)
	seedHost(t, pool)
	body := []byte(`{"id":"evt_status","type":"checkout.session.completed","data":{"object":{"metadata":{"site_booking_id":"7"}}}}`)
	cases := []struct {
		status int
		reply  string
	}{
		{http.StatusInternalServerError, "boom"},
		{http.StatusBadRequest, "bad"},
	}
	for _, c := range cases {
		py, srv := newFakePy(t, c.status, c.reply)
		code, out := fwdPost(fwdHandler(pool, "test", srv.URL), body, fwdSigned(body), "")
		if code != c.status || out != c.reply {
			t.Errorf("python %d %q: got %d %q", c.status, c.reply, code, out)
		}
		if py.callCount() != 1 {
			t.Errorf("python %d: calls %d", c.status, py.callCount())
		}
	}
}

func TestForwardPythonDown(t *testing.T) {
	pool := testPool(t)
	seedHost(t, pool)
	body := []byte(`{"id":"evt_down","type":"checkout.session.expired","data":{"object":{"metadata":{"site_booking_id":"7"}}}}`)
	dead := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	deadURL := dead.URL
	dead.Close()
	code, out := fwdPost(fwdHandler(pool, "test", deadURL), body, fwdSigned(body), "")
	if code != http.StatusBadGateway || out != "forward failed" {
		t.Errorf("python down: got %d %q", code, out)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_down'`); n != 0 {
		t.Errorf("python down wrote %d event rows", n)
	}
	// Retry with Python up: forwarded.
	py, srv := newFakePy(t, http.StatusOK, "ok")
	code, out = fwdPost(fwdHandler(pool, "test", srv.URL), body, fwdSigned(body), "")
	if code != 200 || out != "ok" || py.callCount() != 1 {
		t.Errorf("retry: got %d %q, python calls %d", code, out, py.callCount())
	}
}

func TestForwardNotForwarded(t *testing.T) {
	pool := testPool(t)
	seedHost(t, pool)
	seedRequest(t, pool, 90, "sent", "plink_90")
	seedRequest(t, pool, 91, "sent", "plink_91")

	// Booking event that also carries a payment link: forwarded only, request untouched.
	py, srv := newFakePy(t, http.StatusOK, "ok")
	h := fwdHandler(pool, "test", srv.URL)
	body := []byte(`{"id":"evt_both","type":"checkout.session.completed","data":{"object":{"payment_status":"paid","payment_link":"plink_90","metadata":{"site_booking_id":"7"}}}}`)
	if code, out := fwdPost(h, body, fwdSigned(body), ""); code != 200 || out != "ok" {
		t.Errorf("booking with payment link: got %d %q", code, out)
	}
	if py.callCount() != 1 {
		t.Errorf("booking with payment link: python calls %d", py.callCount())
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM payment_request WHERE id = 90 AND status = 'sent'`); n != 1 {
		t.Errorf("forwarded event changed the payment request")
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_both'`); n != 0 {
		t.Errorf("forwarded event wrote event row")
	}

	// Payment-link event without site_booking_id: handled in Go as before.
	py2, srv2 := newFakePy(t, http.StatusOK, "ok")
	h2 := fwdHandler(pool, "test", srv2.URL)
	body2 := []byte(`{"id":"evt_plain","type":"checkout.session.completed","data":{"object":{"payment_status":"paid","payment_link":"plink_91"}}}`)
	if code, out := fwdPost(h2, body2, fwdSigned(body2), ""); code != 200 || out != "ok" {
		t.Errorf("payment link: got %d %q", code, out)
	}
	if py2.callCount() != 0 {
		t.Errorf("payment link forwarded: %d calls", py2.callCount())
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = 'evt_plain'`); n != 1 {
		t.Errorf("payment link: event row count %d", n)
	}
	if n := count(t, pool, `SELECT COUNT(*) FROM payment_request WHERE id = 91 AND status = 'paid'`); n != 1 {
		t.Errorf("payment link: request not marked paid")
	}

	// Not booking events: never forwarded, recorded in Go.
	cases := []struct{ id, body string }{
		{"evt_empty", `{"id":"evt_empty","type":"checkout.session.completed","data":{"object":{"payment_status":"unpaid","metadata":{"site_booking_id":""}}}}`},
		{"evt_nometa", `{"id":"evt_nometa","type":"checkout.session.expired","data":{"object":{"payment_status":"unpaid"}}}`},
		{"evt_pi", `{"id":"evt_pi","type":"payment_intent.succeeded","data":{"object":{"metadata":{"site_booking_id":"7"}}}}`},
		{"evt_acct_fwd", `{"id":"evt_acct_fwd","type":"account.updated","data":{"object":{"id":"acct_1","metadata":{"site_booking_id":"7"}}}}`},
	}
	for _, c := range cases {
		py3, srv3 := newFakePy(t, http.StatusOK, "ok")
		b := []byte(c.body)
		code, out := fwdPost(fwdHandler(pool, "test", srv3.URL), b, fwdSigned(b), "")
		if code != 200 || out != "ok" {
			t.Errorf("%s: got %d %q", c.id, code, out)
		}
		if py3.callCount() != 0 {
			t.Errorf("%s: forwarded to python", c.id)
		}
		if n := count(t, pool, `SELECT COUNT(*) FROM stripe_webhook_event WHERE event_id = $1`, c.id); n != 1 {
			t.Errorf("%s: event row count %d, want 1", c.id, n)
		}
	}
}

func TestForwardRejectedAndOff(t *testing.T) {
	pool := testPool(t)
	seedHost(t, pool)
	body := []byte(`{"id":"evt_rej","type":"checkout.session.completed","data":{"object":{"metadata":{"site_booking_id":"7"}}}}`)

	py, srv := newFakePy(t, http.StatusOK, "ok")
	code, _ := fwdPost(fwdHandler(pool, "test", srv.URL), body, "t=1,v1=00", "")
	if code != http.StatusBadRequest {
		t.Errorf("bad signature: got %d, want 400", code)
	}
	if py.callCount() != 0 {
		t.Errorf("bad signature forwarded")
	}

	py2, srv2 := newFakePy(t, http.StatusOK, "ok")
	code, out := fwdPost(fwdHandler(pool, "off", srv2.URL), body, fwdSigned(body), "")
	if code != 200 || out != "ignored" {
		t.Errorf("mode off: got %d %q, want 200 ignored", code, out)
	}
	if py2.callCount() != 0 {
		t.Errorf("mode off forwarded")
	}
}
