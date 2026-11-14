package invoices

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

func TestMarkPaid(t *testing.T) {
	app, seed := newTestApp(t)
	id, _ := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	path := "/invoices/" + itoa(id) + "/paid"
	if rec := app.do(http.MethodPost, path, url.Values{}, &host2); rec.Code != 303 || !strings.HasPrefix(rec.Header().Get("Location"), "/invoices?err=") {
		t.Fatalf("another host: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if app.count(`SELECT COUNT(*) FROM invoice WHERE id = $1 AND marked_paid_at IS NOT NULL`, id) != 0 {
		t.Fatal("another host must not mark it")
	}
	rec := app.do(http.MethodPost, path, url.Values{}, &host1)
	loc := rec.Header().Get("Location")
	if rec.Code != 303 || !strings.HasPrefix(loc, "/invoices/"+itoa(id)+"?msg=") {
		t.Fatalf("mark paid: %d %q", rec.Code, loc)
	}
	var at string
	if err := app.pool.QueryRow(context.Background(), `SELECT marked_paid_at FROM invoice WHERE id = $1`, id).Scan(&at); err != nil || at != "2026-11-13T10:00:00+00:00" {
		t.Fatalf("marked_paid_at %q %v", at, err)
	}
	if app.count(`SELECT COUNT(*) FROM audit WHERE action = 'invoice_marked_paid' AND detail = $1 AND actor = 'host1' AND owner_user_id = 1`, "id="+itoa(id)) != 1 {
		t.Error("audit line")
	}
	if !strings.Contains(app.get("/invoices?status=paid", &host1).Body.String(), "p-ok") {
		t.Error("the list now shows it paid")
	}
	// CSRF and bad id come before the login check
	if rec := app.do(http.MethodPost, path, url.Values{}, &host1, true); rec.Code == 303 && strings.HasPrefix(rec.Header().Get("Location"), "/invoices/") {
		t.Error("a POST without a CSRF token must not act")
	}
	if rec := app.do(http.MethodPost, "/invoices/x/paid", url.Values{}, nil); rec.Code != 422 {
		t.Errorf("bad id: %d", rec.Code)
	}
}

func TestCancelAction(t *testing.T) {
	app, seed := newTestApp(t)
	id, _ := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	path := "/invoices/" + itoa(id) + "/cancel"
	short := app.do(http.MethodPost, path, url.Values{"reason": {"ne"}}, &host1)
	if short.Code != 303 || !strings.HasPrefix(short.Header().Get("Location"), "/invoices/"+itoa(id)+"?err=") {
		t.Fatalf("short reason: %d %q", short.Code, short.Header().Get("Location"))
	}
	if loc, _ := url.QueryUnescape(short.Header().Get("Location")); !strings.Contains(loc, "důvod") && !strings.Contains(loc, "reason") && !strings.Contains(loc, "Důvod") {
		t.Errorf("the reason message is shown: %q", loc)
	}
	if app.count(`SELECT COUNT(*) FROM invoice WHERE kind = 'storno'`) != 0 {
		t.Fatal("nothing was issued")
	}
	if rec := app.do(http.MethodPost, path, url.Values{"reason": {"Hostovi se změnily plány"}}, &host2); rec.Code != 303 || !strings.HasPrefix(rec.Header().Get("Location"), "/invoices?err=") {
		t.Fatalf("another host: %d", rec.Code)
	}
	rec := app.do(http.MethodPost, path, url.Values{"reason": {"  Hostovi se změnily plány  "}}, &host1)
	loc := rec.Header().Get("Location")
	if rec.Code != 303 || !strings.HasPrefix(loc, "/invoices/") || !strings.Contains(loc, "?msg=") || strings.HasPrefix(loc, "/invoices/"+itoa(id)+"?") {
		t.Fatalf("cancel: %d %q (it goes to the new storno)", rec.Code, loc)
	}
	var kind, reason string
	if err := app.pool.QueryRow(context.Background(), `SELECT kind, correction_reason FROM invoice WHERE corrects_invoice_id = $1`, id).Scan(&kind, &reason); err != nil || kind != "storno" || reason != "Hostovi se změnily plány" {
		t.Fatalf("storno: %s %q %v", kind, reason, err)
	}
	// cancelling the original again says it cannot be done
	again := app.do(http.MethodPost, path, url.Values{"reason": {"Hostovi se změnily plány"}}, &host1)
	if again.Code != 303 || !strings.HasPrefix(again.Header().Get("Location"), "/invoices/"+itoa(id)+"?err=") {
		t.Fatalf("again: %d %q", again.Code, again.Header().Get("Location"))
	}
}

// ---- the public link ----

func (a *testApp) token(id int64, at time.Time) string {
	a.t.Helper()
	var sha string
	if err := a.pool.QueryRow(context.Background(), `SELECT pdf_sha256 FROM invoice WHERE id = $1`, id).Scan(&sha); err != nil {
		a.t.Fatal(err)
	}
	tok, err := downloadTokenFor(testSecret, id, sha, at)
	if err != nil {
		a.t.Fatal(err)
	}
	return tok
}

func (a *testApp) publicGet(token, ip string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, "/invoice/d/"+token, nil)
	req.Header.Set("CF-Connecting-IP", ip)
	rec := httptest.NewRecorder()
	a.mux.ServeHTTP(rec, req)
	return rec
}

func TestPublicDownloadLink(t *testing.T) {
	app, seed := newTestApp(t)
	id, _ := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	rec := app.publicGet(app.token(id, testNow), "203.0.113.5")
	if rec.Code != 200 || rec.Header().Get("Content-Disposition") != "attachment" || rec.Header().Get("Cache-Control") != "no-store" ||
		rec.Header().Get("X-Robots-Tag") != "noindex" || rec.Header().Get("Content-Type") != "application/pdf" || !strings.HasPrefix(rec.Body.String(), "%PDF") {
		t.Fatalf("download: %d %v", rec.Code, rec.Header())
	}
	// the token Python made for this invoice reads the same: same salt, same payload order
	secret := testSecret
	var data downloadToken
	tok := app.token(id, testNow)
	if err := secure.NewTimedSerializer(secret, "ubyhost-invoice-download").Loads(tok, time.Hour, testNow, &data); err != nil || data.I != id || len(data.H) != 16 {
		t.Fatalf("token payload: %+v %v", data, err)
	}
	for name, token := range map[string]string{
		"garbage":    "not-a-token",
		"expired":    app.token(id, testNow.Add(-31*24*time.Hour)),
		"wrong salt": mustDump(t, "other-salt", downloadToken{I: id, H: data.H}),
		"stale hash": mustDump(t, "ubyhost-invoice-download", downloadToken{I: id, H: "0000000000000000"}),
		"no invoice": mustDump(t, "ubyhost-invoice-download", downloadToken{I: 9999, H: data.H}),
	} {
		if rec := app.publicGet(token, "203.0.113.6"); rec.Code != 404 || rec.Body.String() != "Not found" {
			t.Errorf("%s: %d %q", name, rec.Code, rec.Body.String())
		}
	}
	// a token still in its 30 days works
	if rec := app.publicGet(app.token(id, testNow.Add(-29*24*time.Hour)), "203.0.113.7"); rec.Code != 200 {
		t.Errorf("29 days old: %d", rec.Code)
	}
}

func mustDump(t *testing.T, salt string, v any) string {
	t.Helper()
	tok, err := secure.NewTimedSerializer(testSecret, salt).Dumps(v, testNow)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

func TestPublicDownloadRateLimit(t *testing.T) {
	app, seed := newTestApp(t)
	id, _ := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	token := app.token(id, testNow)
	for i := 1; i <= 30; i++ {
		if rec := app.publicGet(token, "198.51.100.1"); rec.Code != 200 {
			t.Fatalf("request %d: %d", i, rec.Code)
		}
	}
	if rec := app.publicGet(token, "198.51.100.1"); rec.Code != 429 || rec.Body.String() != "Too many requests" {
		t.Fatalf("31st request: %d %q", rec.Code, rec.Body.String())
	}
	if rec := app.publicGet(token, "198.51.100.2"); rec.Code != 200 {
		t.Errorf("another visitor: %d", rec.Code)
	}
	// every attempt counts, a bad token too: the key is "<ip>:invoice_download"
	if app.count(`SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'invoice_download' AND key = '198.51.100.1:invoice_download'`) != 30 {
		t.Error("rate_limit_event rows")
	}
}
