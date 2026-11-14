package cleaning

import (
	"context"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

// hostEnv is the golden database with every host route of this package on a
// mux. The seed (testdata/cleaning_golden.json): owner 1 has apartments 11
// Alfa, 12 Beta, 13 Gama (archived), 14 Delta; owner 2 has 21 Cizi.
type hostEnv struct {
	t    *testing.T
	pool *pgxpool.Pool
	g    goldenFile
	mux  *http.ServeMux
}

func newHostEnv(t *testing.T) *hostEnv {
	t.Helper()
	g := loadGolden(t)
	pool := testPool(t)
	goldenSeed(t, pool, g)
	return hostEnvOn(t, g, pool, goldenEnv(g))
}

func hostEnvOn(t *testing.T, g goldenFile, pool *pgxpool.Pool, getenv func(string) string) *hostEnv {
	t.Helper()
	mux := http.NewServeMux()
	wrap := func(_ string, h http.HandlerFunc) http.Handler { return h }
	RegisterHost(mux, wrap, pool, getenv, func() time.Time { return goldenNow })
	return &hostEnv{t: t, pool: pool, g: g, mux: mux}
}

func i64(n int64) *int64 { return &n }

// call sends one request as a golden case does (owner 1 is user 1).
func (e *hostEnv) call(c goldenCase, headers ...string) *httptest.ResponseRecorder {
	e.t.Helper()
	req := goldenRequest(e.t, e.g, c)
	for i := 0; i+1 < len(headers); i += 2 {
		req.Header.Set(headers[i], headers[i+1])
	}
	rec := httptest.NewRecorder()
	e.mux.ServeHTTP(rec, req)
	return rec
}

func (e *hostEnv) get(user *int64, path, query string) *httptest.ResponseRecorder {
	return e.call(goldenCase{Method: http.MethodGet, Path: path, Query: query, User: user})
}

func (e *hostEnv) exec(sql string, args ...any) {
	e.t.Helper()
	if _, err := e.pool.Exec(context.Background(), sql, args...); err != nil {
		e.t.Fatal(err)
	}
}

func mustContain(t *testing.T, name, body string, want ...string) {
	t.Helper()
	for _, w := range want {
		if !strings.Contains(body, w) {
			t.Errorf("%s: body lacks %q", name, w)
		}
	}
}

func mustLack(t *testing.T, name, body string, bad ...string) {
	t.Helper()
	for _, w := range bad {
		if strings.Contains(body, w) {
			t.Errorf("%s: body holds %q", name, w)
		}
	}
}

func mustPrivate(t *testing.T, name string, rec *httptest.ResponseRecorder) {
	t.Helper()
	for k, v := range map[string]string{"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow"} {
		if got := rec.Header().Get(k); got != v {
			t.Errorf("%s: %s %q, want %q", name, k, got, v)
		}
	}
}

// TestHostIndexPage mirrors routes/cleaning.index (lines 128-144).
func TestHostIndexPage(t *testing.T) {
	e := newHostEnv(t)
	rec := e.get(i64(1), "/cleaning", "")
	if rec.Code != 200 {
		t.Fatalf("status %d: %.300s", rec.Code, rec.Body.String())
	}
	mustPrivate(t, "index", rec)
	body := rec.Body.String()
	mustContain(t, "index", body,
		`data-calendar-date="2026-05-10"`, `data-range-from="2026-05-10"`, `data-range-to="2026-06-09"`,
		`data-readonly="false"`, `data-cleaning="true"`, `data-source="/cleaning/schedule"`,
		`<form action="/reservations" method="post" data-cal-form>`, `data-cal-type-choice="cleaning"`,
		`href="/cleaning/new"`, `href="/cleaning/shares"`, `href="/cleaning/properties"`,
		`/cleaning/events/501/edit`, `data-cleaning-labels`, `/static/cleaning.js`,
		`"name": "Alfa"`, `"name": "Delta"`, `<title>Cleaning · UbyHost</title>`)
	mustLack(t, "index", body, `Cizi`, `Gama`, `cleaning-skip`, `Klíč je u sousedky`, `visually-hidden">Schedule`)
	if !strings.Contains(body, `name="_csrf" value="`) || strings.Contains(body, `name="_csrf" value=""`) {
		t.Error("index: the calendar form carries no CSRF token")
	}
	// A notice key is shown through ct (a missing key is its own text, escaped).
	rec = e.get(i64(1), "/cleaning", "notice=removed")
	mustContain(t, "notice", rec.Body.String(), `<p class="cleaning-notice" role="status">`)
	rec = e.get(i64(1), "/cleaning", "notice=%3Cb%3E")
	mustContain(t, "notice escaped", rec.Body.String(), `&lt;b&gt;`)
	// cal_date moves the window; to falls back to +30 days.
	rec = e.get(i64(1), "/cleaning", "cal_date=2026-05-20")
	mustContain(t, "cal_date", rec.Body.String(), `data-calendar-date="2026-05-20"`, `data-range-to="2026-06-19"`)
	// Czech from the language cookie.
	lc := "cs"
	rec = e.call(goldenCase{Method: http.MethodGet, Path: "/cleaning", User: i64(1), LangCookie: &lc})
	mustContain(t, "cs", rec.Body.String(), `<html lang="cs"`)
}

func TestHostIndexErrors(t *testing.T) {
	e := newHostEnv(t)
	for _, c := range []struct {
		name, query string
		status      int
		detail      string
	}{
		{"foreign property", "property=21", 404, "Not Found"},
		{"archived property", "property=13", 404, "Not Found"},
		{"bad property", "property=abc", 422, "Invalid cleaning range"},
		{"bad from", "from=2026-5-1", 422, "Invalid cleaning range"},
		{"impossible date", "from=2026-02-30", 422, "Invalid cleaning range"},
		{"empty range", "from=2026-05-10&to=2026-05-10", 422, "Invalid cleaning range"},
		{"too long", "from=2026-05-10&to=2027-06-01", 422, "Invalid cleaning range"},
	} {
		rec := e.get(i64(1), "/cleaning", c.query)
		if rec.Code != c.status || !strings.Contains(rec.Body.String(), c.detail) {
			t.Errorf("%s: %d %.120s, want %d %q", c.name, rec.Code, rec.Body.String(), c.status, c.detail)
		}
	}
	rec := e.get(nil, "/cleaning", "")
	if rec.Code != 303 || rec.Header().Get("Location") != "/login?next=/cleaning" {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	// Another owner sees only its own property.
	rec = e.get(i64(2), "/cleaning", "")
	mustContain(t, "owner 2", rec.Body.String(), `"name": "Cizi"`)
	mustLack(t, "owner 2", rec.Body.String(), `"name": "Alfa"`, `/cleaning/events/501/edit`)
}

// TestHostNewEvent mirrors routes/cleaning.new_event (lines 165-173).
func TestHostNewEvent(t *testing.T) {
	e := newHostEnv(t)
	rec := e.get(i64(1), "/cleaning/new", "date=2026-05-20&property=12")
	if rec.Code != 200 {
		t.Fatalf("status %d", rec.Code)
	}
	mustPrivate(t, "new", rec)
	body := rec.Body.String()
	mustContain(t, "new", body,
		`action="/cleaning/events"`, `value="2026-05-20"`, `<option value="12" selected>Beta</option>`,
		`<option value="11" >Alfa</option>`, `<title>Add cleaning · UbyHost</title>`,
		`href="/apartments/12?view=settings&amp;section=property#arrival-departure"`)
	mustLack(t, "new", body, `name="revision"`, `Cizi`, `Gama`, `cleaning-remove`)
	rec = e.get(i64(1), "/cleaning/new", "")
	mustContain(t, "new default", rec.Body.String(), `value="2026-05-10"`, `href="/apartments/"`)
	if e.get(nil, "/cleaning/new", "").Code != 303 {
		t.Error("signed out: want 303")
	}
}

// TestHostEditEvent mirrors routes/cleaning.edit_event (lines 204-213).
func TestHostEditEvent(t *testing.T) {
	e := newHostEnv(t)
	// 501: from a booking, has a note.
	rec := e.get(i64(1), "/cleaning/events/501/edit", "")
	if rec.Code != 200 {
		t.Fatalf("status %d: %.200s", rec.Code, rec.Body.String())
	}
	mustPrivate(t, "edit", rec)
	body := rec.Body.String()
	mustContain(t, "edit 501", body,
		`action="/cleaning/events/501"`, `name="revision" value="1"`, `name="apartment_id" value="11"`,
		`<p class="cleaning-readonly">Alfa</p>`, `Klíč je u sousedky &lt;b&gt;</textarea>`,
		`value="2026-05-10"`, `action="/cleaning/events/501/delete"`, `clean-auto-help`, `<title>Edit cleaning · UbyHost</title>`)
	mustLack(t, "edit 501", body, `<select id="clean-property"`)
	// 507: entered by hand, so the property can change.
	body = e.get(i64(1), "/cleaning/events/507/edit", "").Body.String()
	mustContain(t, "edit 507", body, `<select id="clean-property"`, `<option value="11" selected>Alfa</option>`, `name="revision" value="3"`)
	mustLack(t, "edit 507", body, `clean-auto-help`)
	for _, c := range []struct {
		name, path string
		user       *int64
		status     int
	}{
		{"foreign", "/cleaning/events/509/edit", i64(1), 404},
		{"owner 2 own", "/cleaning/events/509/edit", i64(2), 200},
		{"missing", "/cleaning/events/9999/edit", i64(1), 404},
		{"text id", "/cleaning/events/abc/edit", i64(1), 422},
		{"signed out", "/cleaning/events/501/edit", nil, 303},
	} {
		if got := e.get(c.user, c.path, "").Code; got != c.status {
			t.Errorf("%s: status %d, want %d", c.name, got, c.status)
		}
	}
	e.exec(`UPDATE cleaning_event SET state = 'dismissed' WHERE id = 507`)
	if got := e.get(i64(1), "/cleaning/events/507/edit", "").Code; got != 404 {
		t.Errorf("dismissed: status %d, want 404", got)
	}
	e.exec(`UPDATE apartment SET archived_at = '2026-05-01' WHERE id = 14`)
	if got := e.get(i64(1), "/cleaning/events/512/edit", "").Code; got != 404 {
		t.Errorf("archived apartment: status %d, want 404", got)
	}
}

// TestHostChooseProperty mirrors routes/cleaning.choose_property (lines 265-271).
func TestHostChooseProperty(t *testing.T) {
	e := newHostEnv(t)
	rec := e.get(i64(1), "/cleaning/properties", "")
	if rec.Code != 200 {
		t.Fatalf("status %d", rec.Code)
	}
	mustPrivate(t, "properties", rec)
	body := rec.Body.String()
	mustContain(t, "properties", body, `href="/cleaning/properties/11"`, `href="/cleaning/properties/12"`, `href="/cleaning/properties/14"`, `<title>Property instructions &amp; codes · UbyHost</title>`)
	mustLack(t, "properties", body, `/cleaning/properties/13`, `/cleaning/properties/21`, `Cizi`)
	e.exec(`UPDATE apartment SET archived_at = '2026-05-01' WHERE owner_user_id = 1`)
	mustContain(t, "empty", e.get(i64(1), "/cleaning/properties", "").Body.String(), `<p>Add a property to start scheduling cleanings.</p>`)
}

func TestPyHelpers(t *testing.T) {
	if got := pyStrip("\x1f   x 　\n"); got != "x" {
		t.Errorf("pyStrip = %q", got)
	}
	if runeLen("Klíč") != 4 {
		t.Error("runeLen counts bytes")
	}
}

var (
	ctKeyRE = regexp.MustCompile(`ct \$\.Lang "([^"]+)"`)
	tKeyRE  = regexp.MustCompile(`[ ({]t "([^"]+)"`)
)

// TestHostTemplatesUseKnownKeys: every key a host template asks for exists in
// all three languages (ct: i18n.json "words"; t: "host" or the layout catalog).
func TestHostTemplatesUseKnownKeys(t *testing.T) {
	files, err := hostFiles.ReadDir("hosttemplates")
	if err != nil || len(files) == 0 {
		t.Fatal("no host templates")
	}
	langs := []string{"en", "cs", "vi"}
	for _, f := range files {
		raw, err := hostFiles.ReadFile("hosttemplates/" + f.Name())
		if err != nil {
			t.Fatal(err)
		}
		for _, m := range ctKeyRE.FindAllStringSubmatch(string(raw), -1) {
			for _, lang := range langs {
				if _, ok := texts.Words[lang][m[1]]; !ok {
					t.Errorf("%s: ct key %q missing in %s", f.Name(), m[1], lang)
				}
			}
		}
		for _, m := range tKeyRE.FindAllStringSubmatch(string(raw), -1) {
			for _, lang := range langs {
				_, inPage := texts.Host[lang][m[1]]
				_, inLayout := layout.Strings[lang][m[1]]
				if !inPage && !inLayout {
					t.Errorf("%s: t key %q missing in %s", f.Name(), m[1], lang)
				}
			}
		}
	}
	// The keys errText and the editors build at run time.
	for _, key := range []string{"dates", "times", "notes_error", "property_error", "changed", "code_error", "login_required", "lock_setup", "pending",
		"saved", "removed", "title", "settings", "add", "edit"} {
		for _, lang := range langs {
			if _, ok := texts.Words[lang][key]; !ok {
				t.Errorf("ct key %q missing in %s", key, lang)
			}
		}
	}
}
