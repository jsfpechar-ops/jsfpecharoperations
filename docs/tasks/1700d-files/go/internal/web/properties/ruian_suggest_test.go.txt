package properties

// Tests of GET /apartments/ruian-suggest (brief 1700d). The rows are made up
// and every expected body is written by hand; there is no golden file (the
// Python route needs the network).

import (
	"bytes"
	"log"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"reflect"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ruian"
)

const (
	ruianHostA = 130001
	ruianHostB = 130002
	ruianAdmin = 130003
)

// ruianSeed inserts one made-up row; the folded search text is ruian.SearchText,
// as the 1700c import writes it.
func ruianSeed(t *testing.T, pool *pgxpool.Pool, code int64, street, house, orient string, evid bool, zip, obec string, obecCode int, part, district, okres string) {
	t.Helper()
	mustExec(t, pool, `INSERT INTO ruian_address (code, street, house_no, orient_no, is_evid, zip, obec, obec_code, part, district, okres, search)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)`,
		code, street, house, orient, evid, zip, obec, obecCode, part, district, okres,
		ruian.SearchText(street, house, orient, part, obec, zip))
}

// ruianWorld: two Prague rows on one street, a village row, an evidence-number
// row, a street whose part equals the town, and eight rows for the six-row cap.
func ruianWorld(t *testing.T) (*pgxpool.Pool, *http.ServeMux) {
	t.Helper()
	pool := testPool(t)
	seedHosts(t, pool)
	ruianSeed(t, pool, 9001, "Václavské náměstí", "1306", "12", false, "11000", "Praha", 554782, "Nové Město", "Praha 1", "Hlavní město Praha")
	ruianSeed(t, pool, 9002, "Václavské náměstí", "832", "5A", false, "11000", "Praha", 554782, "Nové Město", "Praha 1", "Hlavní město Praha")
	ruianSeed(t, pool, 9003, "", "45", "", false, "78701", "Malá Ves", 500001, "Horní Ves", "", "Šumperk")
	ruianSeed(t, pool, 9004, "", "12", "", true, "78701", "Malá Ves", 500001, "Horní Ves", "", "Šumperk")
	ruianSeed(t, pool, 9005, "Lipová", "7", "", false, "77900", "Olomouc", 500002, "Olomouc", "", "Olomouc")
	for i := int64(1); i <= 8; i++ {
		ruianSeed(t, pool, 9100+i, "Capova", string(rune('0'+i)), "", false, "10001", "Testov", 500003, "Testov", "", "Testov okres")
	}
	return pool, ruianMux(pool, nil)
}

func ruianMux(pool *pgxpool.Pool, extra map[string]string) *http.ServeMux {
	mux := http.NewServeMux()
	RegisterRuianSuggest(mux, noWrap, pool, moreEnv(extra), testClock)
	return mux
}

func ruianGet(t *testing.T, mux http.Handler, q string, uid, as int64) *httptest.ResponseRecorder {
	t.Helper()
	return getAs(t, mux, "/apartments/ruian-suggest?q="+url.QueryEscape(q), uid, as, nil)
}

func ruianRecorded(t *testing.T, pool *pgxpool.Pool, owner string) int64 {
	t.Helper()
	return oneInt(t, pool, `SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'ruian' AND key = $1`, owner)
}

func ruianWant(t *testing.T, rec *httptest.ResponseRecorder, status int, body string) {
	t.Helper()
	if rec.Code != status || rec.Body.String() != body {
		t.Fatalf("got %d %q, want %d %q", rec.Code, rec.Body.String(), status, body)
	}
	if got := rec.Header().Get("Content-Type"); got != "application/json" {
		t.Fatalf("content type %q", got)
	}
}

const (
	ruianPrague1306 = `{"label":"Václavské náměstí 1306/12, Nové Město, 11000 Praha 1","fields":{"addr_street":"Václavské náměstí","addr_house_no":"1306","addr_orient_no":"12","addr_zip":"11000","addr_obec":"Praha","addr_obec_cast":"Nové Město","addr_okres":"Hlavní město Praha"}}`
	ruianPrague832  = `{"label":"Václavské náměstí 832/5A, Nové Město, 11000 Praha 1","fields":{"addr_street":"Václavské náměstí","addr_house_no":"832","addr_orient_no":"5A","addr_zip":"11000","addr_obec":"Praha","addr_obec_cast":"Nové Město","addr_okres":"Hlavní město Praha"}}`
)

func TestRuianSuggestResults(t *testing.T) {
	_, mux := ruianWorld(t)
	cases := []struct{ name, q, body string }{
		{"street and number, diacritics folded", "vaclavske 12", "[" + ruianPrague1306 + "]"},
		{"typed with diacritics and capitals", "  Václavské   NÁMĚSTÍ 1306 ", "[" + ruianPrague1306 + "]"},
		{"letter after the orient number", "vaclavske 5a", "[" + ruianPrague832 + "]"},
		{"village without a street", "horni ves 45", `[{"label":"Horní Ves 45, 78701 Malá Ves","fields":{"addr_house_no":"45","addr_zip":"78701","addr_obec":"Malá Ves","addr_obec_cast":"Horní Ves","addr_okres":"Šumperk"}}]`},
		{"evidence number", "horni ves 12", `[{"label":"Horní Ves č.ev. 12, 78701 Malá Ves","fields":{"addr_house_no":"12","addr_zip":"78701","addr_obec":"Malá Ves","addr_obec_cast":"Horní Ves","addr_okres":"Šumperk"}}]`},
		{"part equals the town: no addr_obec_cast", "lipova 7", `[{"label":"Lipová 7, 77900 Olomouc","fields":{"addr_street":"Lipová","addr_house_no":"7","addr_zip":"77900","addr_obec":"Olomouc","addr_okres":"Olomouc"}}]`},
		{"no match is [] and not null", "zzzzzz", "[]"},
		{"every token must match", "vaclavske lipova", "[]"},
		{"only the first eight words count", "vaclavske namesti 1306 12 nove mesto praha 11000 x y z", "[" + ruianPrague1306 + "]"},
		{"percent is not a wildcard", "%%%", "[]"},
		{"underscore is not a wildcard", "va_laske", "[]"},
		{"a lone percent word does not match everything", "vaclavske %", "[]"},
		{"backslash is literal", `\\\`, "[]"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ruianWant(t, ruianGet(t, mux, c.q, ruianHostA, 0), 200, c.body)
		})
	}
}

func TestRuianSuggestTwoRowsAndCap(t *testing.T) {
	_, mux := ruianWorld(t)
	rec := ruianGet(t, mux, "václavské", ruianHostA, 0)
	if rec.Code != 200 {
		t.Fatalf("status %d", rec.Code)
	}
	got := strings.Count(rec.Body.String(), `"label":`)
	if got != 2 || !strings.Contains(rec.Body.String(), ruianPrague1306) || !strings.Contains(rec.Body.String(), ruianPrague832) {
		t.Fatalf("two Václavské rows expected, got %s", rec.Body.String())
	}
	rec = ruianGet(t, mux, "capova", ruianHostA, 0)
	if n := strings.Count(rec.Body.String(), `"label":"Capova `); n != 6 || strings.Count(rec.Body.String(), `"label":`) != 6 {
		t.Fatalf("eight rows match, six expected: %s", rec.Body.String())
	}
}

func TestRuianSuggestSignedOutAndSwitches(t *testing.T) {
	pool, mux := ruianWorld(t)
	ruianWant(t, ruianGet(t, mux, "vaclavske 12", 0, 0), 401, "[]")
	if n := oneInt(t, pool, `SELECT COUNT(*) FROM rate_limit_event`); n != 0 {
		t.Fatalf("a signed-out request recorded %d events", n)
	}
	for _, v := range []string{"0", "false", "no", "off", " OFF ", "False"} {
		off := ruianMux(pool, map[string]string{"UBYHOST_RUIAN_ENABLED": v})
		ruianWant(t, ruianGet(t, off, "vaclavske 12", ruianHostA, 0), 200, "[]")
	}
	on := ruianMux(pool, map[string]string{"UBYHOST_RUIAN_ENABLED": "1"})
	ruianWant(t, ruianGet(t, on, "vaclavske 12", ruianHostA, 0), 200, "["+ruianPrague1306+"]")
	if n := ruianRecorded(t, pool, "130001"); n != 1 {
		t.Fatalf("only the enabled lookup is recorded, got %d", n)
	}
}

func TestRuianSuggestShortQuery(t *testing.T) {
	pool, mux := ruianWorld(t)
	for _, q := range []string{"", "ab", "  ab  ", "a "} {
		ruianWant(t, ruianGet(t, mux, q, ruianHostA, 0), 200, "[]")
	}
	if n := ruianRecorded(t, pool, "130001"); n != 0 {
		t.Fatalf("a short query was recorded %d times", n)
	}
	// "a b" is three characters after the white space is collapsed: usable.
	if rec := ruianGet(t, mux, "a  b", ruianHostA, 0); rec.Code != 200 {
		t.Fatalf("status %d", rec.Code)
	}
	if n := ruianRecorded(t, pool, "130001"); n != 1 {
		t.Fatalf("a usable query is recorded once, got %d", n)
	}
}

func TestRuianSuggestRateLimit(t *testing.T) {
	pool, mux := ruianWorld(t)
	add := func(key string, n int, at float64) {
		mustExec(t, pool, `INSERT INTO rate_limit_event (scope, key, at) SELECT 'ruian', $1, $2 FROM generate_series(1, $3::int)`, key, at, n)
	}
	now := float64(testNow.Unix())
	// 59 events: the 60th lookup is answered and recorded, the 61st is [].
	add("130001", 59, now-10)
	ruianWant(t, ruianGet(t, mux, "vaclavske 12", ruianHostA, 0), 200, "["+ruianPrague1306+"]")
	if n := ruianRecorded(t, pool, "130001"); n != 60 {
		t.Fatalf("60 events expected, got %d", n)
	}
	ruianWant(t, ruianGet(t, mux, "vaclavske 12", ruianHostA, 0), 200, "[]")
	if n := ruianRecorded(t, pool, "130001"); n != 60 {
		t.Fatalf("a limited request must not be recorded, got %d", n)
	}
	// Another host has its own count.
	ruianWant(t, ruianGet(t, mux, "vaclavske 12", ruianHostB, 0), 200, "["+ruianPrague1306+"]")
	// An admin previewing host B counts under host B's id (the workspace owner), not the admin's.
	add("130002", 59, now-10)
	ruianWant(t, ruianGet(t, mux, "vaclavske 12", ruianAdmin, ruianHostB), 200, "[]")
	if n := ruianRecorded(t, pool, "130003"); n != 0 {
		t.Fatalf("the admin's own id must stay unused, got %d", n)
	}
	// Events older than the hour are pruned, so they do not block.
	add("130099", 60, now-3601)
	mustExec(t, pool, `INSERT INTO user_account (id, username, password_hash, role, active, must_change_password, session_version, created_at)
		VALUES (130099, 'ruian-old', 'x', 'host', 1, 0, 1, $1)`, stamp0)
	for j, doc := range []struct{ name, version string }{{"terms", "t1"}, {"privacy", "p1"}, {"dpa", "d1"}} {
		mustExec(t, pool, `INSERT INTO legal_acceptance (id, user_account_id, document, version, accepted_at, method)
			VALUES ($1, 130099, $2, $3, NOW(), 'clickwrap')`, 1300990+int64(j), doc.name, doc.version)
	}
	ruianWant(t, ruianGet(t, mux, "vaclavske 12", 130099, 0), 200, "["+ruianPrague1306+"]")
	if n := ruianRecorded(t, pool, "130099"); n != 1 {
		t.Fatalf("old events are pruned and the new one recorded, got %d", n)
	}
}

func TestRuianSuggestDatabaseErrorIsQuietAndPrivate(t *testing.T) {
	pool, mux := ruianWorld(t)
	mustExec(t, pool, `DROP TABLE ruian_address`)
	var logged bytes.Buffer
	log.SetOutput(&logged)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })
	ruianWant(t, ruianGet(t, mux, "vaclavske 12", ruianHostA, 0), 200, "[]")
	if !strings.Contains(logged.String(), "ruian suggest: lookup failed") {
		t.Fatalf("the failure is logged: %q", logged.String())
	}
	if strings.Contains(strings.ToLower(logged.String()), "vaclavske") {
		t.Fatalf("the typed text is in the log: %q", logged.String())
	}
}

func TestRuianSuggestPureHelpers(t *testing.T) {
	for in, want := range map[string]string{"": "", "ab": "", " a b ": "a b", "  Šumperk  12 ": "Šumperk 12", "žžž": "žžž", "čč": ""} {
		if got := ruianUsableQuery(in); got != want {
			t.Errorf("usable(%q) = %q, want %q", in, got, want)
		}
	}
	if got := ruianLikeEscape(`a%b_c\d`); got != `a\%b\_c\\d` {
		t.Errorf("escape: %q", got)
	}
	sql, args := ruianSearchSQL("vaclavske 12", []string{"vaclavske", "12"})
	wantSQL := `SELECT street, house_no, orient_no, zip, obec, part, district, okres, is_evid FROM ruian_address WHERE search LIKE $2 AND search LIKE $3 ORDER BY similarity(search, $1::text) DESC, code LIMIT 6`
	if sql != wantSQL || !reflect.DeepEqual(args, []any{"vaclavske 12", "%vaclavske%", "%12%"}) {
		t.Errorf("sql %q args %v", sql, args)
	}
	for _, v := range []string{"", "1", "yes", "on", "garbage"} {
		if !ruianEnabled(func(string) string { return v }) {
			t.Errorf("%q must leave the lookup on", v)
		}
	}
}

func TestRuianSuggestRegisterDoesNotTouchThePool(t *testing.T) {
	mux := http.NewServeMux()
	RegisterRuianSuggest(mux, noWrap, nil, moreEnv(nil), testClock)
	_, pattern := mux.Handler(httptest.NewRequest(http.MethodGet, "/apartments/ruian-suggest", nil))
	if pattern != "GET /apartments/ruian-suggest" {
		t.Fatalf("pattern %q", pattern)
	}
}

// TestRuianSuggestSource: no outbound request in the route, and the credit
// line stays in its one place (ruian/attribution.go).
func TestRuianSuggestSource(t *testing.T) {
	raw, err := os.ReadFile("ruian_suggest.go")
	if err != nil {
		t.Fatal(err)
	}
	src := string(raw)
	for _, banned := range []string{"http.Client", "http.Get(", "http.Post(", "http.NewRequest", "net/http/httputil", "Adresní data"} {
		if strings.Contains(src, banned) {
			t.Errorf("ruian_suggest.go must not contain %q", banned)
		}
	}
}
