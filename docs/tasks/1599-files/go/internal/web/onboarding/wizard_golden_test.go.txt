package onboarding

// The setup wizard goldens (brief 1599 and after): testdata/wizard_golden_<part>.json
// is written by App/scripts/onboarding_wizard_golden*.py from the real Python
// routes. wizardRunGolden seeds PostgreSQL from the file, sends the same
// requests, in order, to the Go routes and compares each answer, then the rows
// the wizard wrote. A part's test is one call (TestWizardEntryMatchesPython
// here; the later briefs add their own files).

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"reflect"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const wizardGoldenSecret = "wizard-test-secret-key-0123456789abcdef"

// wizardGoldenNow is 12:00 in Prague on the golden TODAY (2026-05-10).
var wizardGoldenNow = time.Date(2026, 5, 10, 10, 0, 0, 0, time.UTC)

type wizardGoldenTable struct {
	Table   string   `json:"table"`
	Columns []string `json:"columns"`
	Secret  []string `json:"secret"`
	Rows    [][]any  `json:"rows"`
}

type wizardGoldenCase struct {
	Name        string            `json:"name"`
	Method      string            `json:"method"`
	Path        string            `json:"path"`
	User        *int64            `json:"user"`
	LangCookie  *string           `json:"lang_cookie"`
	Form        map[string]string `json:"form"`
	CSRF        bool              `json:"csrf"`
	Status      int               `json:"status"`
	Location    *string           `json:"location"`
	ContentType *string           `json:"content_type"`
	Title       string            `json:"title"`
	Fragment    string            `json:"fragment"`
	Body        string            `json:"body"`
}

type wizardGoldenFile struct {
	Today     string              `json:"today"`
	Base      string              `json:"base"`
	CSRFNonce string              `json:"csrf_nonce"`
	Versions  map[string]string   `json:"versions"`
	Seed      []wizardGoldenTable `json:"seed"`
	Cases     []wizardGoldenCase  `json:"cases"`
	Final     json.RawMessage     `json:"final"`
}

func wizardGoldenDataKey() string {
	return base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{7}, 32))
}

func wizardGoldenEnv(g wizardGoldenFile) func(string) string {
	env := map[string]string{
		"UBYHOST_SECRET_KEY":           wizardGoldenSecret,
		"UBYHOST_DATA_KEYS":            wizardGoldenDataKey(),
		"UBYHOST_DATA_KEY_LEGACY":      "0",
		"UBYHOST_TERMS_VERSION":        g.Versions["terms"],
		"UBYHOST_PRIVACY_VERSION":      g.Versions["privacy"],
		"UBYHOST_DPA_VERSION":          g.Versions["dpa"],
		"UBYHOST_PUBLIC_BASE_URL":      g.Base,
		"UBYHOST_DOOR_CODES":           "1",
		"UBYHOST_TTLOCK_CLIENT_ID":     "golden-id",
		"UBYHOST_TTLOCK_CLIENT_SECRET": "golden-secret",
		"UBYHOST_UBYPORT_ENV":          "mock",
	}
	return func(k string) string { return env[k] }
}

func wizardLoadGolden(t *testing.T, path string) wizardGoldenFile {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	var g wizardGoldenFile
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) == 0 || len(g.Seed) == 0 {
		t.Fatal("golden file has no cases or no seed")
	}
	return g
}

func wizardSeedValue(t *testing.T, v any) any {
	t.Helper()
	switch x := v.(type) {
	case nil:
		return nil
	case json.Number:
		n, err := x.Int64()
		if err != nil {
			t.Fatalf("seed number %v", x)
		}
		return n
	case string:
		return x
	case bool:
		return x
	}
	t.Fatalf("seed value %T", v)
	return nil
}

// wizardGoldenSeed inserts the golden rows (a "secret" column is encrypted with
// the test data key, as db.encrypt_secret does in Python) and moves the id
// sequences past the seeded ids.
func wizardGoldenSeed(t *testing.T, pool *pgxpool.Pool, g wizardGoldenFile) {
	t.Helper()
	ctx := context.Background()
	mf, err := secure.NewMultiFernet([]byte(wizardGoldenDataKey()))
	if err != nil {
		t.Fatal(err)
	}
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := "INSERT INTO " + table.Table + " (" + strings.Join(table.Columns, ", ") + ") VALUES (" + strings.Join(marks, ", ") + ")"
		secret := map[int]bool{}
		for _, c := range table.Secret {
			for i, col := range table.Columns {
				if col == c {
					secret[i] = true
				}
			}
		}
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = wizardSeedValue(t, v)
				if s, ok := args[i].(string); ok && secret[i] {
					if args[i], err = mf.EncryptString(s); err != nil {
						t.Fatal(err)
					}
				}
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
		if table.Columns[0] == "id" {
			if _, err := pool.Exec(ctx, "SELECT setval(pg_get_serial_sequence('"+table.Table+"', 'id'), (SELECT MAX(id) FROM "+table.Table+"))"); err != nil {
				t.Fatalf("setval %s: %v", table.Table, err)
			}
		}
	}
}

func wizardGoldenRequest(t *testing.T, g wizardGoldenFile, c wizardGoldenCase) *http.Request {
	t.Helper()
	var body io.Reader
	form := url.Values{}
	for k, v := range c.Form {
		form.Set(k, v)
	}
	if c.CSRF {
		sum := sha256.Sum256([]byte(g.CSRFNonce))
		tok, err := secure.NewTimedSerializer(wizardGoldenSecret, "ubyhost-csrf").Dumps(
			map[string]any{"nonce": hex.EncodeToString(sum[:])}, wizardGoldenNow)
		if err != nil {
			t.Fatal(err)
		}
		form.Set("_csrf", tok)
	}
	if c.Method == http.MethodPost {
		body = strings.NewReader(form.Encode())
	}
	req := httptest.NewRequest(c.Method, c.Path, body)
	if c.Method == http.MethodPost {
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	}
	if c.User != nil {
		req.AddCookie(&http.Cookie{Name: session.CookieName,
			Value: session.Sign(wizardGoldenSecret, map[string]any{"uid": *c.User, "sv": 1, "iat": wizardGoldenNow.Unix()}, wizardGoldenNow)})
	}
	if c.LangCookie != nil {
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: *c.LangCookie})
	}
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: g.CSRFNonce})
	return req
}

var (
	wizardSpaceRE = regexp.MustCompile(`\s+`)
	wizardTagRE   = regexp.MustCompile(`\s*([<>])\s*`)
	wizardCSRFRE  = regexp.MustCompile(`name="_csrf" value="[^"]*"`)
	wizardQRRE    = regexp.MustCompile(`src="data:image/png;base64,[^"]*"`)
	wizardDivRE   = regexp.MustCompile(`<(/?)div\b`)
)

// wizardFragment is wizard_fragment of the golden script.
func wizardFragment(page string) string {
	start := strings.Index(page, `<div class="setup-wizard wiz-page"`)
	if start < 0 {
		return ""
	}
	depth := 0
	for _, m := range wizardDivRE.FindAllStringSubmatchIndex(page[start:], -1) {
		if m[3] > m[2] {
			depth--
		} else {
			depth++
		}
		if depth == 0 {
			end := start + m[1] + strings.Index(page[start+m[1]:], ">") + 1
			return page[start:end]
		}
	}
	return "unbalanced"
}

// wizardNormalise compares markup, not formatting: entities are decoded (Jinja
// and html/template escape different characters), white space is collapsed
// and dropped next to tag brackets, the CSRF value is blanked, and an inline
// QR image is one token (the PNG encoders differ; wizard_more_test.go checks
// the Go image).
func wizardNormalise(s string) string {
	s = wizardCSRFRE.ReplaceAllString(s, `name="_csrf" value=""`)
	s = wizardQRRE.ReplaceAllString(s, `src="data:image/png;base64,QR"`)
	s = html.UnescapeString(s)
	s = wizardSpaceRE.ReplaceAllString(s, " ")
	return strings.TrimSpace(wizardTagRE.ReplaceAllString(s, "$1"))
}

func wizardTextDiff(got, want string) string {
	i := 0
	for i < len(got) && i < len(want) && got[i] == want[i] {
		i++
	}
	from := i - 160
	if from < 0 {
		from = 0
	}
	cut := func(s string) string {
		if i+240 < len(s) {
			return s[from : i+240]
		}
		return s[from:]
	}
	return fmt.Sprintf("byte %d:\n got: …%s\nwant: …%s", i, cut(got), cut(want))
}

// wizardFinal reads the rows the golden script records at the end.
func wizardFinal(t *testing.T, pool *pgxpool.Pool) map[string]any {
	t.Helper()
	ctx := context.Background()
	settings := map[string]any{}
	rows, err := pool.Query(ctx, `SELECT key, value FROM settings WHERE key LIKE 'property_setup:%' ORDER BY key`)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var k, v string
		if err := rows.Scan(&k, &v); err != nil {
			t.Fatal(err)
		}
		settings[k] = v
	}
	rows.Close()
	pins := map[string]any{}
	pinRE := regexp.MustCompile(`^\d{6}$`)
	rows, err = pool.Query(ctx, `SELECT id, COALESCE(permalink_pin, '') FROM apartment ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var id int64
		var pin string
		if err := rows.Scan(&id, &pin); err != nil {
			t.Fatal(err)
		}
		pins[fmt.Sprint(id)] = pinRE.MatchString(pin)
	}
	rows.Close()
	audit := []any{}
	rows, err = pool.Query(ctx, `SELECT actor, action, detail, owner_user_id, actor_user_id FROM audit
 WHERE action IN ('property_setup_step', 'apartment_updated') ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var actor, action, detail string
		var owner, actorID *int64
		if err := rows.Scan(&actor, &action, &detail, &owner, &actorID); err != nil {
			t.Fatal(err)
		}
		audit = append(audit, map[string]any{"actor": actor, "action": action, "detail": detail, "owner_user_id": owner, "actor_user_id": actorID})
	}
	rows.Close()
	demo := []any{}
	rows, err = pool.Query(ctx, `SELECT apartment_id, date_from, date_to, summary, status, expected_guests_override, uid
  FROM reservation WHERE source = 'demo' ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var apt int64
		var from, to string
		var summary, status, uid *string
		var override *int64
		if err := rows.Scan(&apt, &from, &to, &summary, &status, &override, &uid); err != nil {
			t.Fatal(err)
		}
		demo = append(demo, map[string]any{"apartment_id": apt, "date_from": from, "date_to": to, "summary": summary,
			"status": status, "expected_guests_override": override, "uid_demo": uid != nil && strings.HasPrefix(*uid, "demo-")})
	}
	rows.Close()
	timing := []any{}
	rows, err = pool.Query(ctx, `SELECT id, automation_mode, submit_after_hours FROM apartment ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var id, hours int64
		var mode string
		if err := rows.Scan(&id, &mode, &hours); err != nil {
			t.Fatal(err)
		}
		timing = append(timing, map[string]any{"id": id, "automation_mode": mode, "submit_after_hours": hours})
	}
	rows.Close()
	return map[string]any{"settings": settings, "pins": pins, "audit": audit, "demo_stays": demo, "timing": timing}
}

// wizardJSONRound makes a value comparable with a decoded golden value.
func wizardJSONRound(t *testing.T, v any) any {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var out any
	if err := json.Unmarshal(raw, &out); err != nil {
		t.Fatal(err)
	}
	return out
}

// wizardRunGolden runs one golden part against the Go routes.
func wizardRunGolden(t *testing.T, path string) {
	g := wizardLoadGolden(t, path)
	pool := testPool(t)
	wizardGoldenSeed(t, pool, g)
	mux := http.NewServeMux()
	RegisterWizard(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, wizardGoldenEnv(g),
		func() time.Time { return wizardGoldenNow })
	for _, c := range g.Cases {
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, wizardGoldenRequest(t, g, c))
		name := c.Name
		if rec.Code != c.Status {
			t.Fatalf("%s: status %d, want %d: %.400s", name, rec.Code, c.Status, rec.Body.String())
		}
		wantLoc := ""
		if c.Location != nil {
			wantLoc = *c.Location
		}
		if got := rec.Header().Get("Location"); got != wantLoc {
			t.Fatalf("%s: Location %q, want %q", name, got, wantLoc)
		}
		if c.Status >= 300 && c.Status < 400 {
			continue
		}
		body := rec.Body.String()
		if c.Fragment != "" || c.Title != "" {
			if !strings.HasPrefix(rec.Header().Get("Content-Type"), "text/html") {
				t.Fatalf("%s: Content-Type %q", name, rec.Header().Get("Content-Type"))
			}
			if m := regexp.MustCompile(`(?s)<title>(.*?)</title>`).FindStringSubmatch(body); m == nil ||
				html.UnescapeString(strings.TrimSpace(m[1])) != html.UnescapeString(c.Title) {
				t.Fatalf("%s: title %v, want %q", name, m, c.Title)
			}
			got, want := wizardNormalise(wizardFragment(body)), wizardNormalise(c.Fragment)
			if got != want {
				t.Fatalf("%s: wizard markup differs at %s", name, wizardTextDiff(got, want))
			}
			continue
		}
		if c.ContentType != nil && rec.Header().Get("Content-Type") != *c.ContentType {
			t.Fatalf("%s: Content-Type %q, want %q", name, rec.Header().Get("Content-Type"), *c.ContentType)
		}
		if body != c.Body {
			t.Fatalf("%s: body %q, want %q", name, body, c.Body)
		}
	}
	var want any
	if err := json.Unmarshal(g.Final, &want); err != nil {
		t.Fatal(err)
	}
	got := wizardJSONRound(t, wizardFinal(t, pool))
	if !reflect.DeepEqual(got, want) {
		gotRaw, _ := json.Marshal(got)
		wantRaw, _ := json.Marshal(want)
		t.Fatalf("final rows differ at %s", wizardTextDiff(string(gotRaw), string(wantRaw)))
	}
}

// TestWizardEntryMatchesPython: GET /apartments/{id}/setup, the step
// redirects and the calendar and guest link pages (brief 1599).
func TestWizardEntryMatchesPython(t *testing.T) {
	wizardRunGolden(t, "testdata/wizard_golden_entry.json")
}
