package properties

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/policyletter"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const spNonce = "small-posts-nonce"

func spMux(t *testing.T, pool *pgxpool.Pool, extra map[string]string, mockURL string) *http.ServeMux {
	t.Helper()
	mux := http.NewServeMux()
	getenv := adEnv(extra)
	if mockURL != "" {
		prev := getenv
		getenv = func(k string) string {
			switch k {
			case "UBYHOST_UBYPORT_ENV":
				return "mock"
			case "UBYHOST_MOCK_URL":
				return mockURL
			}
			return prev(k)
		}
	}
	RegisterApartmentSmallPosts(mux, noWrap, pool, getenv, testClock, nil)
	return mux
}

func spPost(t *testing.T, mux http.Handler, path string, form url.Values, user int64, lang string, csrf bool, accept string) *httptest.ResponseRecorder {
	t.Helper()
	if csrf {
		sum := sha256.Sum256([]byte(spNonce))
		token, err := secure.NewTimedSerializer(apartmentNewSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, testNow)
		if err != nil {
			t.Fatal(err)
		}
		form.Set("_csrf", token)
	} else {
		form.Del("_csrf")
	}
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if accept != "" {
		req.Header.Set("Accept", accept)
	}
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: spNonce})
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	if user != 0 {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(apartmentNewSecret, map[string]any{"uid": user, "sv": 1}, testNow)})
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func spExpect303(t *testing.T, name string, rec *httptest.ResponseRecorder, location string) {
	t.Helper()
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != location {
		t.Errorf("%s: %d %q, want 303 %q", name, rec.Code, rec.Header().Get("Location"), location)
	}
}

func TestApartmentAutomationTiming(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mux := spMux(t, pool, nil, "")
	base := "/apartments/130201/automation-timing"
	form := url.Values{"return_to": {propertySummaries}, "automation_mode": {"scheduled"}, "submit_after_hours": {"12"}}
	spExpect303(t, "ok", spPost(t, mux, base, form, 130001, "en", true, ""), "/apartments?msg=Reporting%20timing%20saved.#property-summaries")
	if mode, hours := mustTiming(t, pool, adLoft); mode != "scheduled" || hours != 12 {
		t.Errorf("db: %q %d", mode, hours)
	}
	form.Set("automation_mode", "nope")
	spExpect303(t, "invalid", spPost(t, mux, base, form, 130001, "en", true, ""), "/apartments?err=Choose%20when%20to%20send%20to%20UbyPort.%20Nothing%20was%20saved.#property-summaries")
	form.Set("automation_mode", "scheduled")
	form.Set("submit_after_hours", "0")
	spExpect303(t, "hours", spPost(t, mux, base, form, 130001, "en", true, ""), "/apartments?err=Enter%20the%20delay%20in%20whole%20hours%2C%20from%201%20to%2048.%20Nothing%20was%20saved.#property-summaries")
	rec := spPost(t, mux, base, form, 130001, "en", true, "application/json")
	if rec.Code != http.StatusBadRequest {
		t.Errorf("json refuse: %d", rec.Code)
	}
	form.Set("submit_after_hours", "6")
	rec = spPost(t, mux, base, form, 130001, "en", true, "application/json")
	var body map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &body)
	if rec.Code != http.StatusOK || body["ok"] != true || body["automation_mode"] != "scheduled" {
		t.Errorf("json ok: %d %+v", rec.Code, body)
	}
}

func mustTiming(t *testing.T, pool *pgxpool.Pool, id int64) (string, int64) {
	t.Helper()
	var mode string
	var hours int64
	if err := pool.QueryRow(t.Context(), `SELECT automation_mode, submit_after_hours FROM apartment WHERE id = $1`, id).Scan(&mode, &hours); err != nil {
		t.Fatal(err)
	}
	return mode, hours
}

func TestApartmentSmallPostsAccess(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mux := spMux(t, pool, nil, "")
	form := url.Values{"return_to": {"/apartments"}}
	if rec := spPost(t, mux, "/apartments/130201/automation-timing", form, 0, "en", true, ""); rec.Code != http.StatusSeeOther ||
		rec.Header().Get("Location") != "/login?next=/apartments/130201/automation-timing" {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if rec := spPost(t, mux, "/apartments/130201/automation-timing", form, 130001, "en", false, ""); rec.Code != http.StatusSeeOther ||
		rec.Header().Get("Location") != "/login?notice=form_expired" {
		t.Errorf("no csrf: %d %q", rec.Code, rec.Header().Get("Location"))
	}
}

func TestApartmentPoliceLetterJSON(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mux := spMux(t, pool, nil, "")
	form := url.Values{"letter_text": {""}}
	rec := spPost(t, mux, "/apartments/130201/police-letter", form, 130001, "en", true, "application/json")
	if rec.Code != http.StatusOK || rec.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("empty: %d cache %q", rec.Code, rec.Header().Get("Cache-Control"))
	}
	var body map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &body)
	if body["status"] != "empty" {
		t.Errorf("status %v", body["status"])
	}
	sample := policyletter.ParseLetter(`Přihlašovací jméno: UBY-WS_DEMO1` + "\nPřístupové heslo: Uk@zKa-H3sl0-FAKE\nIDUB: 209988776655\n")
	if sample.Status != "ok" {
		t.Fatalf("sample parse %q", sample.Status)
	}
	form.Set("letter_text", `Přihlašovací jméno: UBY-WS_DEMO1
Přístupové heslo: Uk@zKa-H3sl0-FAKE
IDUB: 209988776655
`)
	rec = spPost(t, mux, "/apartments/130201/police-letter", form, 130001, "en", true, "application/json")
	_ = json.Unmarshal(rec.Body.Bytes(), &body)
	if body["status"] != "ok" {
		t.Errorf("ok status %v", body["status"])
	}
	fields := body["fields"].(map[string]any)
	pw := fields["uby_ws_password"].(map[string]any)
	if pw["value"] == "" {
		t.Error("password value missing in json")
	}
}

func TestApartmentRefreshCodelists(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		action := strings.TrimPrefix(r.Header.Get("SOAPAction"), "http://UBY.pcr.cz/WS_UBY/IWS_UBY/")
		switch action {
		case "DejMiCiselnik":
			_, _ = io.WriteString(w, apartmentLetterResponse(action, `<a:CiselnikType xmlns:a="x"><a:Kod3>CZE</a:Kod3></a:CiselnikType>`))
		default:
			_, _ = io.WriteString(w, apartmentLetterResponse(action, "true"))
		}
	}))
	defer srv.Close()
	mux := spMux(t, pool, nil, srv.URL)
	form := url.Values{"return_to": {"/apartments/130201?view=settings"}}
	keys, err := secure.LoadDataKeys(adEnv(nil))
	if err != nil {
		t.Fatal(err)
	}
	tok, err := keys.Encrypt([]byte("fake-pass"))
	if err != nil {
		t.Fatal(err)
	}
	mustExec(t, pool, `UPDATE apartment SET uby_ws_user = 'UBY-WS_DEMO1', uby_ws_password_enc = $1 WHERE id = $2`, tok, adLoft)
	rec := spPost(t, mux, "/apartments/130201/refresh-codelists", form, 130001, "en", true, "")
	loc := rec.Header().Get("Location")
	if rec.Code != http.StatusSeeOther || !strings.Contains(loc, "msg=") {
		t.Errorf("refresh ok: %d %q", rec.Code, loc)
	}
}

func TestCalendarPlatformValues(t *testing.T) {
	if _, _, errs := calendarPlatformValues("", "", ""); errs["label"] != "calendar.error.platform_required" {
		t.Fatalf("missing platform: %v", errs)
	}
	label, own, errs := calendarPlatformValues("airbnb", "", "")
	if len(errs) != 0 || label != "Airbnb" || own != "Airbnb" {
		t.Fatalf("airbnb: label=%q own=%q errs=%v", label, own, errs)
	}
	label, _, errs = calendarPlatformValues("other", "My OTA", "")
	if len(errs) != 0 || label != "My OTA" {
		t.Fatalf("other custom: label=%q errs=%v", label, errs)
	}
	if _, _, errs = calendarPlatformValues("other", "", ""); errs["label_other"] != "calendar.error.other_required" {
		t.Fatalf("other blank: %v", errs)
	}
	long := strings.Repeat("x", platformOtherMax+1)
	if _, _, errs = calendarPlatformValues("other", long, ""); errs["label_other"] != "calendar.error.other_invalid" {
		t.Fatalf("other long: %v", errs)
	}
	if _, _, errs = calendarPlatformValues("airbnb", "", "\x00bad"); errs["own_name"] != "calendar.error.name_invalid" {
		t.Fatalf("control char own_name: %v", errs)
	}
}

// Brief 1703: blocked calendar URLs must fail before any ical_feed row is written.
func TestApartmentAddFeedRefusesInternalURL(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mux := spMux(t, pool, nil, "")
	before := oneInt(t, pool, `SELECT COUNT(*) FROM ical_feed WHERE apartment_id = $1`, adLoft)
	form := url.Values{
		"return_to": {"/apartments/130201?view=bookings#calendars"},
		"label":     {"airbnb"},
		"url":       {"http://127.0.0.1/calendar.ics"},
	}
	rec := spPost(t, mux, "/apartments/130201/feeds", form, 130001, "en", true, "")
	if rec.Code != http.StatusNotImplemented {
		t.Errorf("status %d want 501", rec.Code)
	}
	if rec.Header().Get("X-Ubyhost-Not-Ported") != "1" {
		t.Error("missing not-ported header")
	}
	if after := oneInt(t, pool, `SELECT COUNT(*) FROM ical_feed WHERE apartment_id = $1`, adLoft); after != before {
		t.Errorf("feed count %d -> %d", before, after)
	}
}

func TestApartmentAddFeedDuplicateURL(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mux := spMux(t, pool, nil, "")
	form := url.Values{
		"return_to": {"/apartments/130201?view=bookings#calendars"},
		"label":     {"airbnb"},
		"url":       {"https://www.airbnb.com/calendar/ical/1.ics"},
	}
	rec := spPost(t, mux, "/apartments/130201/feeds", form, 130001, "en", true, "")
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d", rec.Code)
	}
	if loc := rec.Header().Get("Location"); !strings.Contains(loc, "err=") {
		t.Errorf("duplicate flash: %q", loc)
	}
}

func TestApartmentAddFeedInsertsAndSyncs(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	mustExec(t, pool, `SELECT setval(pg_get_serial_sequence('ical_feed', 'id'), (SELECT max(id) FROM ical_feed))`)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/calendar")
		_, _ = io.WriteString(w, "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:sp-feed-1\r\nDTSTART;VALUE=DATE:20261210\r\nDTEND;VALUE=DATE:20261212\r\nSUMMARY:Reserved\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
	}))
	defer srv.Close()
	mux := http.NewServeMux()
	RegisterApartmentSmallPosts(mux, noWrap, pool, adEnv(nil), testClock, &ical.FetchOptions{
		Resolver: net.DefaultResolver, AllowPrivate: true,
	})
	before := oneInt(t, pool, `SELECT COUNT(*) FROM ical_feed WHERE apartment_id = $1 AND url = $2`, adLoft, srv.URL)
	form := url.Values{
		"return_to": {"/apartments/130201?view=bookings#calendars"},
		"label":     {"airbnb"},
		"url":       {srv.URL},
	}
	rec := spPost(t, mux, "/apartments/130201/feeds", form, 130001, "en", true, "")
	if rec.Code != http.StatusSeeOther || !strings.Contains(rec.Header().Get("Location"), "msg=") {
		t.Fatalf("add feed: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if after := oneInt(t, pool, `SELECT COUNT(*) FROM ical_feed WHERE apartment_id = $1 AND url = $2`, adLoft, srv.URL); after != before+1 {
		t.Errorf("feed rows %d want %d", after, before+1)
	}
}

// Changing only the letter-picked login without a password must not run the live UbyPort test.
func TestApartmentTestConnectionNewLoginNeedsPassword(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	hits := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
	}))
	defer srv.Close()
	mux := spMux(t, pool, nil, srv.URL)
	mustExec(t, pool, `UPDATE apartment SET uby_ws_user = 'UBY-WS_OLD', uby_idub = '209988776655' WHERE id = $1`, adLoft)
	form := url.Values{
		"return_to":     {"/apartments/130201?view=settings&section=police"},
		"uby_idub":      {"209988776655"},
		"uby_ws_user":   {"UBY-WS_NEW"},
		"letter_fields": {"uby_ws_user"},
	}
	rec := spPost(t, mux, "/apartments/130201/test-connection", form, 130001, "en", true, "")
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d", rec.Code)
	}
	if loc := rec.Header().Get("Location"); !strings.Contains(loc, "Type%20the%20password") {
		t.Errorf("flash: %q", loc)
	}
	if hits != 0 {
		t.Errorf("UbyPort mock hit %d times", hits)
	}
}
