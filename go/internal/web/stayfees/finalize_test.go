package stayfees

// Brief 1585: POST /stay-fees/{apartment_id}/finalize on PostgreSQL. The
// fixture is the made-up seed of the stay_fee_mail job golden (@example.test,
// test keys); the renderer is a fake that returns fixed bytes.

import (
	"context"
	"encoding/json"
	"errors"
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

	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/stayfee"
)

var finalizeFakePDF = []byte("%PDF-fake-finalize")

type finalizeRenderer struct{ calls int }

func (f *finalizeRenderer) Render(stayfee.Hlaseni) ([]byte, error) {
	f.calls++
	return finalizeFakePDF, nil
}

func finalizeEnv() func(string) string {
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

// finalizeInsert writes one seed row. encrypt maps a seed key to the column
// that gets its Fernet token.
func finalizeInsert(t *testing.T, pool *pgxpool.Pool, keys *secure.MultiFernet, table string, row, extra map[string]any, encrypt map[string]string) {
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

// finalizeSeed loads the job golden seed: hosts 1 (host1) and 2 (optout), an
// admin, and apartments 1 to 13. Apartment 1 has a clean month 2026-09,
// apartment 2 an unsigned guest, apartment 3 a sealed 2026-09 filing.
func finalizeSeed(t *testing.T, pool *pgxpool.Pool) *secure.MultiFernet {
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
	keys, err := secure.LoadDataKeys(finalizeEnv())
	if err != nil {
		t.Fatal(err)
	}
	old := "2026-09-01T00:00:00+00:00"
	stamp := map[string]any{"created_at": old}
	both := map[string]any{"created_at": old, "updated_at": old}
	for _, r := range g.Seed["users"] {
		finalizeInsert(t, pool, keys, "user_account", r, stamp, nil)
	}
	for _, r := range g.Seed["legal_entities"] {
		finalizeInsert(t, pool, keys, "legal_entity", r, stamp, nil)
	}
	for _, r := range g.Seed["apartments"] {
		finalizeInsert(t, pool, keys, "apartment", r, stamp, nil)
	}
	for _, r := range g.Seed["reservations"] {
		finalizeInsert(t, pool, keys, "reservation", r, map[string]any{"uid": fmt.Sprintf("uid-%v", r["id"]),
			"created_at": old, "updated_at": old}, nil)
	}
	for _, r := range g.Seed["guests"] {
		finalizeInsert(t, pool, keys, "guest", r, both, nil)
	}
	for _, r := range g.Seed["adjustments"] {
		finalizeInsert(t, pool, keys, "stay_fee_adjustment", r, nil, map[string]string{"reason": "reason_enc"})
	}
	for _, r := range g.Seed["filings"] {
		finalizeInsert(t, pool, keys, "stay_fee_filing", r, nil, nil)
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

type finalizeRig struct {
	t    *testing.T
	pool *pgxpool.Pool
	keys *secure.MultiFernet
	at   time.Time
	r    *finalizeRenderer
	mux  *http.ServeMux
}

func newFinalizeRig(t *testing.T, withRenderer bool) *finalizeRig {
	t.Helper()
	pool := testPool(t)
	rig := &finalizeRig{t: t, pool: pool, keys: finalizeSeed(t, pool), r: &finalizeRenderer{},
		at: time.Date(2026, 10, 5, 5, 0, 0, 0, time.UTC)}
	var renderer stayfee.PDFRenderer
	if withRenderer {
		renderer = rig.r
	}
	rig.mux = http.NewServeMux()
	rig.mux.Handle("POST /stay-fees/{apartment_id}/finalize",
		FinalizeHandler(pool, finalizeEnv(), func() time.Time { return rig.at }, renderer))
	return rig
}

// post sends the form as the signed-in host1 ("" sends it signed out).
func (g *finalizeRig) post(path, who string, form url.Values) *httptest.ResponseRecorder {
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

func (g *finalizeRig) count(sql string, args ...any) int {
	g.t.Helper()
	var n int
	if err := g.pool.QueryRow(context.Background(), sql, args...).Scan(&n); err != nil {
		g.t.Fatal(err)
	}
	return n
}

// wrote is the number of filings and audit rows: the two tables a seal writes.
func (g *finalizeRig) wrote() [2]int {
	return [2]int{g.count(`SELECT COUNT(*) FROM stay_fee_filing`), g.count(`SELECT COUNT(*) FROM audit`)}
}

// answer is the Location split into path and the msg/err texts.
func finalizeAnswer(t *testing.T, rec *httptest.ResponseRecorder) (path, msg, errText string) {
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

func finalizeText(key string) string {
	if t := finalizeCatalog.T("en", key, nil); t != key {
		return t
	}
	return catalog.T("en", key, nil)
}

func finalizeForm(kv ...string) url.Values {
	v := url.Values{}
	for i := 0; i+1 < len(kv); i += 2 {
		v.Set(kv[i], kv[i+1])
	}
	return v
}

func TestFinalizeSealsPeriod(t *testing.T) {
	g := newFinalizeRig(t, true)
	// Confirmation missing: nothing is sealed.
	rec := g.post("/stay-fees/1/finalize", "host1", finalizeForm("month", "2026-09"))
	path, _, errText := finalizeAnswer(t, rec)
	if path != "/stay-fees/1?month=2026-09" || errText != finalizeText("flash.stay_fees.confirm_collected") {
		t.Fatalf("no confirmation: %q err %q", path, errText)
	}
	if w := g.wrote(); w != [2]int{3, 0} {
		t.Fatalf("a refused request wrote: %v", w)
	}
	// A collected amount that is not a number: blocked, nothing sealed.
	rec = g.post("/stay-fees/1/finalize", "host1", finalizeForm("month", "2026-09", "confirm_collected", "1", "collected_101", "abc"))
	if _, _, errText = finalizeAnswer(t, rec); errText != finalizeText("flash.stay_fees.report_blocked") {
		t.Fatalf("bad amount: err %q", errText)
	}
	if w := g.wrote(); w != [2]int{3, 0} {
		t.Fatalf("a refused request wrote: %v", w)
	}
	// The figures the page would show, to pick an amount to override.
	ap, err := stayfee.LoadApartment(context.Background(), g.pool, 1)
	if err != nil {
		t.Fatal(err)
	}
	dec := stayfee.FernetDecrypter(g.keys)
	month := time.Date(2026, 9, 1, 0, 0, 0, 0, time.UTC)
	checked, err := stayfee.Check(context.Background(), g.pool, dec, ap, month, pragueDay(g.at),
		stayfee.Opts{ScheduleToday: time.Date(2026, 10, 5, 0, 0, 0, 0, time.UTC)})
	if err != nil || len(checked.Issues) > 0 || len(checked.Period.Lines) == 0 {
		t.Fatalf("fixture is not clean: %v %v", err, checked)
	}
	first := checked.Period.Lines[0]
	want := 0
	for _, l := range checked.Period.Lines {
		want += l.AmountCZK
	}
	want += 1000 - first.AmountCZK
	form := finalizeForm("month", "2026-09", "confirm_collected", "1", fmt.Sprintf("collected_%d", first.GuestID), "1000")
	rec = g.post("/stay-fees/1/finalize", "host1", form)
	path, msg, errText := finalizeAnswer(t, rec)
	if path != "/stay-fees/1?month=2026-09" || errText != "" || msg != finalizeText("flash.stay_fees.period_saved") {
		t.Fatalf("seal: %q msg %q err %q", path, msg, errText)
	}
	if g.r.calls != 1 {
		t.Fatalf("renderer called %d times, want 1", g.r.calls)
	}
	var key, pdfEnc, payloadEnc string
	var version, collected, due int
	var superseded *string
	err = g.pool.QueryRow(context.Background(), `SELECT period_key, version, total_collected_czk, total_due_czk, superseded_at,
		convert_from(pdf_enc, 'UTF8'), payload_enc FROM stay_fee_filing WHERE apartment_id = 1`).
		Scan(&key, &version, &collected, &due, &superseded, &pdfEnc, &payloadEnc)
	if err != nil {
		t.Fatal(err)
	}
	if key != "2026-09" || version != 1 || superseded != nil || collected != want {
		t.Errorf("filing %q v%d collected %d (want %d) superseded %v", key, version, collected, want, superseded)
	}
	plain, err := g.keys.Decrypt(pdfEnc, 0, g.at)
	if err != nil || string(plain) != string(finalizeFakePDF) {
		t.Errorf("pdf %q err %v", plain, err)
	}
	payload, err := g.keys.Decrypt(payloadEnc, 0, g.at)
	if err != nil || !strings.Contains(string(payload), fmt.Sprintf(`"%d": 1000`, first.GuestID)) {
		t.Errorf("payload %q err %v", payload, err)
	}
	var actor, action, detail string
	var owner, actorID int64
	err = g.pool.QueryRow(context.Background(), `SELECT actor, action, detail, owner_user_id, actor_user_id FROM audit`).
		Scan(&actor, &action, &detail, &owner, &actorID)
	if err != nil || actor != "host1" || action != "stay_fee_finalize" || detail != "apartment_id=1 period=2026-09" ||
		owner != 1 || actorID != 1 {
		t.Errorf("audit %q %q %q %d %d err %v", actor, action, detail, owner, actorID, err)
	}
	// The same period again: already saved, nothing new.
	rec = g.post("/stay-fees/1/finalize", "host1", finalizeForm("month", "2026-09", "confirm_collected", "1"))
	if _, _, errText = finalizeAnswer(t, rec); errText != finalizeText("flash.stay_fees.already_saved") {
		t.Fatalf("repeat: err %q", errText)
	}
	if w := g.wrote(); w != [2]int{4, 1} {
		t.Fatalf("after repeat: %v", w)
	}
}

func TestFinalizeReturnTo(t *testing.T) {
	g := newFinalizeRig(t, true)
	rec := g.post("/stay-fees/1/finalize", "host1", finalizeForm("month", "2026-09", "confirm_collected", "1", "return_to", "/stay-fees?month=2026-09"))
	u, _ := url.Parse(rec.Header().Get("Location"))
	if u.Path != "/stay-fees" || u.Query().Get("month") != "2026-09" || u.Query().Get("msg") == "" {
		t.Fatalf("Location %q", rec.Header().Get("Location"))
	}
	rec = g.post("/stay-fees/2/finalize", "host1", finalizeForm("month", "2026-09", "return_to", "//evil.example/x"))
	if !strings.HasPrefix(rec.Header().Get("Location"), "/stay-fees/2?month=2026-09") {
		t.Fatalf("foreign return_to: %q", rec.Header().Get("Location"))
	}
}

func TestFinalizeRefusals(t *testing.T) {
	g := newFinalizeRig(t, true)
	before := g.wrote()
	notFound := finalizeText("flash.error.no_such_apartment")
	blocked := finalizeText("flash.stay_fees.report_blocked")
	cases := []struct {
		name, path, who string
		form            url.Values
		wantPath        string
		wantErr         string
	}{
		{"foreign apartment", "/stay-fees/10/finalize", "host1", finalizeForm("month", "2026-09"), "/stay-fees", notFound},
		{"missing apartment", "/stay-fees/999/finalize", "host1", finalizeForm("month", "2026-09"), "/stay-fees", notFound},
		{"huge apartment id", "/stay-fees/99999999999999999999/finalize", "host1", finalizeForm("month", "2026-09"), "/stay-fees", notFound},
		{"no stay fee", "/stay-fees/9/finalize", "host1", finalizeForm("month", "2026-09"), "/stay-fees", notFound},
		{"blocked (unsigned guest)", "/stay-fees/2/finalize", "host1", finalizeForm("month", "2026-09", "confirm_collected", "1"), "/stay-fees/2?month=2026-09", blocked},
		{"already saved", "/stay-fees/3/finalize", "host1", finalizeForm("month", "2026-09", "confirm_collected", "1"), "/stay-fees/3?month=2026-09", finalizeText("flash.stay_fees.already_saved")},
		{"correction of nothing", "/stay-fees/1/finalize", "host1", finalizeForm("month", "2026-09", "correct", "1", "confirm_collected", "1"), "/stay-fees/1?month=2026-09", blocked},
		// No month: the current month, whose period is not over yet.
		{"no month", "/stay-fees/1/finalize", "host1", finalizeForm("confirm_collected", "1"), "/stay-fees/1?month=2026-10", blocked},
		{"bad month", "/stay-fees/1/finalize", "host1", finalizeForm("month", "nonsense", "confirm_collected", "1"), "/stay-fees/1?month=2026-10", blocked},
	}
	for _, c := range cases {
		path, _, errText := finalizeAnswer(t, g.post(c.path, c.who, c.form))
		if path != c.wantPath || errText != c.wantErr {
			t.Errorf("%s: %q err %q, want %q err %q", c.name, path, errText, c.wantPath, c.wantErr)
		}
	}
	if after := g.wrote(); after != before {
		t.Errorf("refusals wrote rows: %v -> %v", before, after)
	}
	if g.r.calls != 0 {
		t.Errorf("renderer ran %d times for refusals", g.r.calls)
	}
}

func TestFinalizeNeedsLoginAndCSRF(t *testing.T) {
	g := newFinalizeRig(t, true)
	before := g.wrote()
	rec := g.post("/stay-fees/1/finalize", "", finalizeForm("month", "2026-09", "confirm_collected", "1"))
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/login") {
		t.Fatalf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	req := httptest.NewRequest(http.MethodPost, "/stay-fees/1/finalize", strings.NewReader("month=2026-09&confirm_collected=1"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Origin", "https://evil.example")
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: sessionFor("host1", g.at)})
	rec = httptest.NewRecorder()
	g.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusForbidden {
		t.Fatalf("bad CSRF: %d", rec.Code)
	}
	if after := g.wrote(); after != before {
		t.Errorf("rows written: %v -> %v", before, after)
	}
}

// A nil renderer refuses with the blocked flash and writes nothing.
func TestFinalizeNilRenderer(t *testing.T) {
	g := newFinalizeRig(t, false)
	before := g.wrote()
	_, _, errText := finalizeAnswer(t, g.post("/stay-fees/1/finalize", "host1", finalizeForm("month", "2026-09", "confirm_collected", "1")))
	if errText != finalizeText("flash.stay_fees.report_blocked") {
		t.Fatalf("err %q", errText)
	}
	if after := g.wrote(); after != before {
		t.Errorf("rows written: %v -> %v", before, after)
	}
}

// A correction supersedes the sealed filing and seals the next version.
func TestFinalizeCorrection(t *testing.T) {
	g := newFinalizeRig(t, true)
	rec := g.post("/stay-fees/3/finalize", "host1", finalizeForm("month", "2026-09", "correct", "1", "confirm_collected", "1"))
	path, msg, errText := finalizeAnswer(t, rec)
	if path != "/stay-fees/3?month=2026-09" || errText != "" || msg != finalizeText("flash.stay_fees.period_saved") {
		t.Fatalf("correction: %q msg %q err %q", path, msg, errText)
	}
	if n := g.count(`SELECT COUNT(*) FROM stay_fee_filing WHERE apartment_id = 3 AND period_key = '2026-09' AND version = 2 AND superseded_at IS NULL`); n != 1 {
		t.Errorf("version 2 live: %d", n)
	}
	if n := g.count(`SELECT COUNT(*) FROM stay_fee_filing WHERE id = 1 AND superseded_at IS NOT NULL`); n != 1 {
		t.Errorf("version 1 superseded: %d", n)
	}
	if n := g.count(`SELECT COUNT(*) FROM audit WHERE action = 'stay_fee_finalize' AND detail = 'apartment_id=3 period=2026-09'`); n != 1 {
		t.Errorf("audit rows: %d", n)
	}
}

// Overlap, changed and duplicate cannot be reached in one request (they need
// a concurrent writer), so the mapping from Save's errors is tested directly.
func TestFinalizeSaveErrorMapping(t *testing.T) {
	for _, c := range []struct {
		err  error
		want string
	}{
		{stayfee.ErrInactive, "blocked"},
		{stayfee.ErrOverlap, "blocked"},
		{stayfee.ErrChanged, "blocked"},
		{fmt.Errorf("wrapped: %w", stayfee.ErrOverlap), "blocked"},
		{stayfee.ErrDuplicate, "already_saved"},
		{&pgconn.PgError{Code: "23505"}, "already_saved"},
		{&pgconn.PgError{Code: "23503"}, "already_saved"},
		{errors.New("boom"), ""},
		{&pgconn.PgError{Code: "40001"}, ""},
	} {
		if got := finalizeSaveOutcome(c.err); got != c.want {
			t.Errorf("%v: %q, want %q", c.err, got, c.want)
		}
	}
}
