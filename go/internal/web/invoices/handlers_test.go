package invoices

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

const (
	testSecret      = "invoices-test-secret-key-not-for-real-use"
	acceptedVersion = "test-accepted"
)

// testNow is the clock of every test: Friday 13 Nov 2026, 11:00 in Prague.
var testNow = time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC)

func testEnv() func(string) string {
	env := map[string]string{
		"UBYHOST_SECRET_KEY":      testSecret,
		"UBYHOST_TERMS_VERSION":   acceptedVersion,
		"UBYHOST_PRIVACY_VERSION": acceptedVersion,
		"UBYHOST_DPA_VERSION":     acceptedVersion,
	}
	return func(k string) string { return env[k] }
}

func nilDeps() deps {
	return deps{getenv: testEnv(), now: func() time.Time { return testNow }}
}

func TestBadIDIs422BeforeLoginAndCSRFComesFirst(t *testing.T) {
	d := nilDeps()
	// a nil pool is fine: neither answer reaches the database
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/invoices/abc.pdf", nil)
	if c, _ := d.enterID(rec, req, "abc"); c != nil || rec.Code != 422 || rec.Header().Get("Content-Type") != "application/json" ||
		rec.Body.String() != `{"detail":[{"type":"int_parsing","loc":["path","invoice_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"abc"}]}` {
		t.Errorf("bad id: %d %s", rec.Code, rec.Body.String())
	}
	// a POST without a CSRF token is refused whatever the id is
	rec = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodPost, "/invoices/abc/paid", strings.NewReader(""))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if c, _ := d.enterID(rec, req, "abc"); c != nil || rec.Code == 422 || rec.Code == 200 {
		t.Errorf("no CSRF: %d", rec.Code)
	}
}

func TestEnterIDParsing(t *testing.T) {
	for _, tc := range []struct {
		raw string
		ok  bool
	}{{"12", true}, {"007", true}, {"+7", true}, {"-3", true}, {"1_0", false}, {"", false}, {"1.5", false}, {" 7", false}, {"٣", false}} {
		if got := intPath.MatchString(tc.raw); got != tc.ok {
			t.Errorf("%q: %v", tc.raw, got)
		}
	}
}

func TestStaticAnswers(t *testing.T) {
	rec := httptest.NewRecorder()
	notFound(rec)
	if rec.Code != 404 || rec.Body.String() != `{"detail":"Not Found"}` {
		t.Error("404")
	}
	rec = httptest.NewRecorder()
	methodNotAllowed(rec, "POST")
	if rec.Code != 405 || rec.Header().Get("Allow") != "POST" || rec.Body.String() != `{"detail":"Method Not Allowed"}` {
		t.Error("405")
	}
	rec = httptest.NewRecorder()
	plain(rec, 429, "Too many requests")
	if rec.Code != 429 || rec.Header().Get("Content-Type") != "" || rec.Body.String() != "Too many requests" {
		t.Errorf("plain: %q", rec.Header().Get("Content-Type"))
	}
}

func TestPragueDayAndStamp(t *testing.T) {
	late := time.Date(2026, 12, 31, 23, 30, 0, 0, time.UTC) // already 1 Jan in Prague
	if got := pragueDay(late).Format("2006-01-02"); got != "2027-01-01" {
		t.Errorf("prague day %s", got)
	}
	if got := stamp(time.Date(2026, 11, 13, 10, 0, 0, 999, time.UTC)); got != "2026-11-13T10:00:00+00:00" {
		t.Errorf("stamp %s", got)
	}
}
