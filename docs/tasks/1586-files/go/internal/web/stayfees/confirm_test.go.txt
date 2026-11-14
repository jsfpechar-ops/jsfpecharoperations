package stayfees

// Brief 1586: POST /stay-fees/confirm-ready on PostgreSQL. The
// fixture is the made-up seed of the stay_fee_mail job golden (@example.test,
// test keys); the renderer is a fake that returns fixed bytes.

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

var confirmFakePDF = []byte("%PDF-fake-confirm")

type confirmRenderer struct{ calls int }

func (f *confirmRenderer) Render(stayfee.Hlaseni) ([]byte, error) {
	f.calls++
	return confirmFakePDF, nil
}

func confirmEnv() func(string) string {
	base := goldenEnv()
	extra := map[string]string{
		"UBYHOST_STAY_FEE_GUEST_PAY": "on",
		"UBYHOST_MAIL_BACKEND":       "console",
		"UBYHOST_UBYPORT_ENV":        "mock",
		"UBYHOST_APP_BASE_URL":       "https://app.example.test",
		"UBYHOST_PUBLIC_BASE_URL":    "https://www.example.test",
	}
	return func(k string) string {
		if v, ok := extra[k]; ok {
			return v
		}
		return base(k)
	}
}

// confirmInsert writes one seed row. encrypt maps a seed key to the column
// that gets its Fernet token.
func confirmInsert(t *testing.T, pool *pgxpool.Pool, keys *secure.MultiFernet, table string, row, extra map[string]any, encrypt map[string]string) {
	t.Helper()
	merged := map[string]any{}
	for k, v := range row {
		merged[k] = v
	}
	for k, v := range extra {
		merged[k] = v
	}
	names := make([]string, 0, len(merged))
	for k := range merged {
		names = append(names, k)
	}
	sort.Strings(names)
	var cols, marks []string
	var args []any
	for _, k := range names {
		v, col := merged[k], k
		if enc, ok := encrypt[k]; ok {
			col = enc
			if s, _ := v.(string); s != "" {
				token, err := keys.EncryptString(s)
				if err != nil {
					t.Fatal(err)
				}
				v = token
			} else {
				v = nil
			}
		}
		if f, ok := v.(float64); ok {
			v = int64(f)
		}
		cols = append(cols, col)
		args = append(args, v)
		marks = append(marks, "$"+strconv.Itoa(len(args)))
	}
	sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table, strings.Join(cols, ", "), strings.Join(marks, ", "))
	if _, err := pool.Exec(context.Background(), sql, args...); err != nil {
		t.Fatalf("%s: %v", table, err)
	}
}

// confirmSeed loads the job golden seed: hosts 1 (host1) and 2 (optout), an
// admin, and apartments 1 to 13. Apartment 1 has a clean month 2026-09,
// apartment 2 an unsigned guest, apartment 3 a sealed 2026-09 filing.
func confirmSeed(t *testing.T, pool *pgxpool.Pool) *secure.MultiFernet {
	t.Helper()
	raw, err := os.ReadFile("../../stayfeemail/testdata/stay_fee_job_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g struct {
		Seed map[string][]map[string]any `json:"seed"`
	}
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	keys, err := secure.LoadDataKeys(confirmEnv())
	if err != nil {
		t.Fatal(err)
	}
	old := "2026-09-01T00:00:00+00:00"
	stamp := map[string]any{"created_at": old}
	both := map[string]any{"created_at": old, "updated_at": old}
	for _, r := range g.Seed["users"] {
		confirmInsert(t, pool, keys, "user_account", r, stamp, nil)
	}
	for _, r := range g.Seed["legal_entities"] {
		confirmInsert(t, pool, keys, "legal_entity", r, stamp, nil)
	}
	for _, r := range g.Seed["apartments"] {
		confirmInsert(t, pool, keys, "apartment", r, stamp, nil)
	}
	for _, r := range g.Seed["reservations"] {
		confirmInsert(t, pool, keys, "reservation", r, map[string]any{"uid": fmt.Sprintf("uid-%v", r["id"]),
			"created_at": old, "updated_at": old}, nil)
	}
	for _, r := range g.Seed["guests"] {
		confirmInsert(t, pool, keys, "guest", r, both, nil)
	}
	for _, r := range g.Seed["adjustments"] {
		confirmInsert(t, pool, keys, "stay_fee_adjustment", r, nil, map[string]string{"reason": "reason_enc"})
	}
	for _, r := range g.Seed["filings"] {
		confirmInsert(t, pool, keys, "stay_fee_filing", r, nil, nil)
	}
	for _, table := range []string{"user_account", "legal_entity", "apartment", "reservation", "guest",
		"stay_fee_adjustment", "stay_fee_filing", "audit"} {
		if _, err := pool.Exec(context.Background(), fmt.Sprintf(
			`SELECT setval(pg_get_serial_sequence('%[1]s', 'id'), COALESCE((SELECT MAX(id) FROM %[1]s), 0) + 1, false)`,
			table)); err != nil {
			t.Fatalf("setval %s: %v", table, err)
		}
	}
	for _, uid := range []int{1, 2, 5} {
		for _, doc := range []string{"terms", "privacy", "dpa"} {
			if _, err := pool.Exec(context.Background(),
				`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, '2026-01-01', 'clickwrap')`,
				uid, doc, acceptedVersion); err != nil {
				t.Fatal(err)
			}
		}
	}
	return keys
}

type confirmRig struct {
	t    *testing.T
	pool *pgxpool.Pool
	keys *secure.MultiFernet
	at   time.Time
	r    *confirmRenderer
	mux  *http.ServeMux
}

func newConfirmRig(t *testing.T, withRenderer bool) *confirmRig {
	t.Helper()
	pool := testPool(t)
	rig := &confirmRig{t: t, pool: pool, keys: confirmSeed(t, pool), r: &confirmRenderer{},
		at: time.Date(2026, 10, 5, 5, 0, 0, 0, time.UTC)}
	var renderer stayfee.PDFRenderer
	if withRenderer {
		renderer = rig.r
	}
	rig.mux = http.NewServeMux()
	rig.mux.Handle("POST /stay-fees/confirm-ready",
		ConfirmReadyHandler(pool, confirmEnv(), func() time.Time { return rig.at }, renderer))
	return rig
}

// post sends the form as the signed-in host1 ("" sends it signed out).
func (g *confirmRig) post(path, who string, form url.Values) *httptest.ResponseRecorder {
	g.t.Helper()
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	ck, token := csrfPair(g.t, g.at)
	req.AddCookie(ck)
	req.Header.Set("X-CSRF-Token", token)
	if who != "" {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor(who, g.at)})
	}
	rec := httptest.NewRecorder()
	g.mux.ServeHTTP(rec, req)
	return rec
}

func (g *confirmRig) count(sql string, args ...any) int {
	g.t.Helper()
	var n int
	if err := g.pool.QueryRow(context.Background(), sql, args...).Scan(&n); err != nil {
		g.t.Fatal(err)
	}
	return n
}

// wrote is the number of filings and audit rows: the two tables a seal writes.
func (g *confirmRig) wrote() [2]int {
	return [2]int{g.count(`SELECT COUNT(*) FROM stay_fee_filing`), g.count(`SELECT COUNT(*) FROM audit`)}
}

// answer is the Location split into path and the msg/err texts.
func confirmAnswer(t *testing.T, rec *httptest.ResponseRecorder) (path, msg, errText string) {
	t.Helper()
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d, want 303 (%s)", rec.Code, rec.Body.String())
	}
	u, err := url.Parse(rec.Header().Get("Location"))
	if err != nil {
		t.Fatal(err)
	}
	q := u.Query()
	if m := q.Get("month"); m != "" {
		return u.Path + "?month=" + m, q.Get("msg"), q.Get("err")
	}
	return u.Path, q.Get("msg"), q.Get("err")
}

func confirmText(key string) string {
	if t := confirmCatalog.T("en", key, nil); t != key {
		return t
	}
	return catalog.T("en", key, nil)
}

func confirmForm(kv ...string) url.Values {
	v := url.Values{}
	for i := 0; i+1 < len(kv); i += 2 {
		v.Set(kv[i], kv[i+1])
	}
	return v
}

func confirmCount(n int) string {
	return confirmCatalog.T("en", "flash.stay_fees.bulk_saved", map[string]any{"count": n})
}

func TestConfirmReadySealsCleanPeriods(t *testing.T) {
	g := newConfirmRig(t, true)
	form := url.Values{"month": {"2026-09"}, "apartment_id": {"1", "2", "3", "5", "9", "10", "1", " 1 ", "abc", "-4", "999", "99999999999999999999"}}
	path, msg, errText := confirmAnswer(t, g.post("/stay-fees/confirm-ready", "host1", form))
	if path != "/stay-fees" || errText != "" {
		t.Fatalf("answer %q err %q", path, errText)
	}
	// Apartment 1 is clean; 2 has an unsigned guest; 3 is sealed; 5 is archived;
	// 9 has no stay fee; 10 belongs to another host.
	if n := g.count(`SELECT COUNT(*) FROM stay_fee_filing WHERE apartment_id = 1 AND period_key = '2026-09' AND superseded_at IS NULL`); n != 1 {
		t.Fatalf("apartment 1 sealed %d times", n)
	}
	for _, id := range []int{2, 3, 5, 9, 10} {
		want := 0
		if id == 3 {
			want = 1 // the seeded filing
		}
		if n := g.count(`SELECT COUNT(*) FROM stay_fee_filing WHERE apartment_id = $1`, id); n != want {
			t.Errorf("apartment %d has %d filings, want %d", id, n, want)
		}
	}
	sealed := g.count(`SELECT COUNT(*) FROM stay_fee_filing`) - 3
	if sealed != 1 || msg != confirmCount(sealed) {
		t.Errorf("sealed %d, msg %q", sealed, msg)
	}
	if g.r.calls != sealed {
		t.Errorf("renderer ran %d times for %d filings", g.r.calls, sealed)
	}
	var actor, action, detail string
	var owner, actorID int64
	err := g.pool.QueryRow(context.Background(), `SELECT actor, action, detail, owner_user_id, actor_user_id FROM audit`).
		Scan(&actor, &action, &detail, &owner, &actorID)
	if err != nil || actor != "host1" || action != "stay_fee_finalize" || detail != "apartment_id=1 period=2026-09" ||
		owner != 1 || actorID != 1 {
		t.Errorf("audit %q %q %q %d %d err %v", actor, action, detail, owner, actorID, err)
	}
	// The sealed file is the fake PDF.
	var pdf string
	if err := g.pool.QueryRow(context.Background(), `SELECT convert_from(pdf_enc, 'UTF8') FROM stay_fee_filing WHERE apartment_id = 1`).Scan(&pdf); err != nil {
		t.Fatal(err)
	}
	if plain, err := g.keys.Decrypt(pdf, 0, g.at); err != nil || string(plain) != string(confirmFakePDF) {
		t.Errorf("pdf %q err %v", plain, err)
	}
	// Again: nothing is ready any more.
	_, _, errText = confirmAnswer(t, g.post("/stay-fees/confirm-ready", "host1", form))
	if errText != confirmCatalog.T("en", "flash.stay_fees.bulk_none", nil) {
		t.Errorf("repeat: err %q", errText)
	}
	if n := g.count(`SELECT COUNT(*) FROM audit`); n != 1 {
		t.Errorf("audit rows %d, want 1", n)
	}
}

func TestConfirmReadyNothingToSeal(t *testing.T) {
	g := newConfirmRig(t, true)
	none := confirmCatalog.T("en", "flash.stay_fees.bulk_none", nil)
	for _, c := range []struct {
		name string
		form url.Values
		path string
	}{
		{"no apartments", url.Values{"month": {"2026-09"}}, "/stay-fees"},
		{"blocked", url.Values{"month": {"2026-09"}, "apartment_id": {"2"}}, "/stay-fees"},
		{"foreign", url.Values{"month": {"2026-09"}, "apartment_id": {"10"}}, "/stay-fees"},
		{"archived", url.Values{"month": {"2026-09"}, "apartment_id": {"5"}}, "/stay-fees"},
		{"no month: the current month is not over", url.Values{"apartment_id": {"1"}}, "/stay-fees"},
		{"future month falls back to the current one", url.Values{"month": {"2027-03"}, "apartment_id": {"1"}}, "/stay-fees"},
		{"return_to the list", url.Values{"month": {"2026-09"}, "apartment_id": {"2"}, "return_to": {"/stay-fees?month=2026-09"}}, "/stay-fees?month=2026-09"},
		{"foreign return_to", url.Values{"month": {"2026-09"}, "apartment_id": {"2"}, "return_to": {"//evil.example/x"}}, "/stay-fees"},
	} {
		path, _, errText := confirmAnswer(t, g.post("/stay-fees/confirm-ready", "host1", c.form))
		if path != c.path || errText != none {
			t.Errorf("%s: %q err %q", c.name, path, errText)
		}
	}
	if w := g.wrote(); w != [2]int{3, 0} {
		t.Errorf("rows written: %v", w)
	}
}

func TestConfirmReadyReturnTo(t *testing.T) {
	g := newConfirmRig(t, true)
	rec := g.post("/stay-fees/confirm-ready", "host1", url.Values{"month": {"2026-09"}, "apartment_id": {"1"}, "return_to": {"/stay-fees?month=2026-09"}})
	u, _ := url.Parse(rec.Header().Get("Location"))
	if u.Path != "/stay-fees" || u.Query().Get("month") != "2026-09" || u.Query().Get("msg") != confirmCount(1) {
		t.Fatalf("Location %q", rec.Header().Get("Location"))
	}
}

func TestConfirmReadyNeedsLoginAndCSRF(t *testing.T) {
	g := newConfirmRig(t, true)
	rec := g.post("/stay-fees/confirm-ready", "", url.Values{"month": {"2026-09"}, "apartment_id": {"1"}})
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/login") {
		t.Fatalf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	req := httptest.NewRequest(http.MethodPost, "/stay-fees/confirm-ready", strings.NewReader("month=2026-09&apartment_id=1"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Origin", "https://evil.example")
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor("host1", g.at)})
	rec = httptest.NewRecorder()
	g.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusForbidden {
		t.Fatalf("bad CSRF: %d", rec.Code)
	}
	if w := g.wrote(); w != [2]int{3, 0} {
		t.Errorf("rows written: %v", w)
	}
}

// A nil renderer seals nothing and answers like "nothing was ready".
func TestConfirmReadyNilRenderer(t *testing.T) {
	g := newConfirmRig(t, false)
	_, _, errText := confirmAnswer(t, g.post("/stay-fees/confirm-ready", "host1", url.Values{"month": {"2026-09"}, "apartment_id": {"1"}}))
	if errText != confirmCatalog.T("en", "flash.stay_fees.bulk_none", nil) {
		t.Fatalf("err %q", errText)
	}
	if w := g.wrote(); w != [2]int{3, 0} {
		t.Errorf("rows written: %v", w)
	}
}

// A live quarterly filing contains the month: nothing is sealed.
func TestConfirmReadyOverlap(t *testing.T) {
	g := newConfirmRig(t, true)
	if _, err := g.pool.Exec(context.Background(), `INSERT INTO stay_fee_filing (apartment_id, period_key, version, cadence,
		rate_czk, liable_days, exempt_days, total_due_czk, total_collected_czk, created_at)
		VALUES (1, '2026-Q3', 1, 'quarterly', 20, 1, 0, 20, 20, '2026-10-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	before := g.wrote()
	_, _, errText := confirmAnswer(t, g.post("/stay-fees/confirm-ready", "host1", url.Values{"month": {"2026-09"}, "apartment_id": {"1"}}))
	if errText != confirmCatalog.T("en", "flash.stay_fees.bulk_none", nil) {
		t.Fatalf("err %q", errText)
	}
	if after := g.wrote(); after != before {
		t.Errorf("rows written: %v -> %v", before, after)
	}
}
