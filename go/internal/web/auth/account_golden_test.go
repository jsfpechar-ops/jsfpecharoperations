package auth

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"reflect"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// The cases in testdata/account_setup.json (and brief 1506's
// account_email.json) are Python's answers, recorded by
// App/scripts/auth_account_golden.py. Each case is replayed on Postgres.

type acctWant struct {
	Status         int                    `json:"status"`
	Location       *string                `json:"location"`
	ContentType    *string                `json:"content_type"`
	CacheControl   *string                `json:"cache_control"`
	ReferrerPolicy *string                `json:"referrer_policy"`
	Body           *string                `json:"body"`
	Cookies        []cookieRec            `json:"cookies"`
	Sent           []int64                `json:"sent"`
	DB             map[string][][]*string `json:"db"`
}

type acctCase struct {
	Name    string            `json:"name"`
	Method  string            `json:"method"`
	Path    string            `json:"path"`
	Query   string            `json:"query"`
	Session map[string]int64  `json:"session"`
	CSRF    *bool             `json:"csrf"`
	Lang    string            `json:"lang"`
	Fresh   bool              `json:"fresh"`
	Headers map[string]string `json:"headers"`
	Form    [][2]string       `json:"form"`
	Seed    [][2]any          `json:"seed"`
	Want    acctWant          `json:"want"`
}

type acctGolden struct {
	Secret string            `json:"secret"`
	Nonce  string            `json:"nonce"`
	Env    map[string]string `json:"env"`
	Staged string            `json:"staged"`
	Seed   [][2]any          `json:"seed"`
	Cases  []acctCase        `json:"cases"`
}

// acctTables are emptied before each case, as the script deletes them.
var acctTables = []string{"email_outbox", "rate_limit_event", "audit", "login_token", "legal_acceptance", "user_account"}

// acctWatch is the script's WATCH: the same columns in the same order.
var acctWatch = map[string]string{
	"audit": `SELECT action, actor, detail, owner_user_id, actor_user_id, impersonator_user_id FROM audit ORDER BY id`,
	"user_account": `SELECT id, email, email_verified_at, session_version, totp_enabled,
		CASE WHEN totp_secret_enc IS NULL THEN 0 ELSE 1 END AS has_secret,
		CASE WHEN recovery_codes_hash IS NULL THEN 0 ELSE 1 END AS has_codes FROM user_account ORDER BY id`,
	"legal_acceptance": `SELECT user_account_id, document, version, accepted_at, method, ip, user_agent
		FROM legal_acceptance ORDER BY id`,
	"rate_limit_event": `SELECT scope, key FROM rate_limit_event ORDER BY id`,
	"login_token": `SELECT user_account_id, purpose, email, remember, next_path, created_at, expires_at, used_at
		FROM login_token ORDER BY id`,
	"email_outbox": `SELECT idempotency_key, kind, owner_user_id, to_email, subject, state, payload
		FROM email_outbox ORDER BY id`,
}

// The script's SCRUB and ANY_STAMP: what changes from run to run.
var (
	acctScrubEnc   = regexp.MustCompile(`"claim_secret_enc": "[^"]*"`)
	acctScrubKey   = regexp.MustCompile(`:[0-9a-f]{24}$`)
	acctScrubStamp = regexp.MustCompile(`\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(\+00:00|Z)?`)
)

func acctNorm(v any) *string {
	p := norm(v)
	if p == nil || *p == "<now>" {
		return p
	}
	s := acctScrubEnc.ReplaceAllString(*p, `"claim_secret_enc": "<enc>"`)
	s = acctScrubKey.ReplaceAllString(s, ":<h>")
	s = acctScrubStamp.ReplaceAllStringFunc(s, func(m string) string {
		if strings.HasPrefix(m, "2001-") || strings.HasPrefix(m, "2099-") {
			return m
		}
		return "<now>"
	})
	return &s
}

func acctDump(t *testing.T, ctx context.Context, pool *pgxpool.Pool) map[string][][]*string {
	t.Helper()
	out := map[string][][]*string{}
	for name, sql := range acctWatch {
		rows, err := pool.Query(ctx, sql)
		if err != nil {
			t.Fatal(err)
		}
		out[name] = [][]*string{}
		for rows.Next() {
			vals, err := rows.Values()
			if err != nil {
				t.Fatal(err)
			}
			row := make([]*string, len(vals))
			for i, v := range vals {
				row[i] = acctNorm(v)
			}
			out[name] = append(out[name], row)
		}
		rows.Close()
	}
	return out
}

// The script's PAGE and FRESH steps, then folded whitespace.
var (
	acctPageSteps = []struct {
		re   *regexp.Regexp
		repl string
	}{
		{regexp.MustCompile(`<meta name="csrf-token" content="[^"]*">`), `<meta name="csrf-token" content="<csrf>">`},
		{regexp.MustCompile(`name="_csrf" value="[^"]*"`), `name="_csrf" value="<csrf>"`},
		{regexp.MustCompile(`data:image/png;base64,[A-Za-z0-9+/=]+`), `<qr>`},
		{regexp.MustCompile(`<code>[0-9A-F]{4}-[0-9A-F]{4}</code>`), `<code>R</code>`},
	}
	acctFreshSteps = []struct {
		re   *regexp.Regexp
		repl string
	}{
		{regexp.MustCompile(`secret=[A-Z2-7]{32}&amp;`), `secret=<s>&amp;`},
		{regexp.MustCompile(`<code id="totp-setup-key">[A-Z2-7 ]{39}</code>`), `<code id="totp-setup-key"><s></code>`},
	}
	acctSpace = regexp.MustCompile(`\s+`)
)

func acctPageNorm(s string, fresh bool) string {
	for _, st := range acctPageSteps {
		s = st.re.ReplaceAllString(s, st.repl)
	}
	if fresh {
		for _, st := range acctFreshSteps {
			s = st.re.ReplaceAllString(s, st.repl)
		}
	}
	return strings.TrimSpace(strings.ReplaceAll(acctSpace.ReplaceAllString(s, " "), "> <", "><"))
}

func acctLoadSeed(t *testing.T, ctx context.Context, pool *pgxpool.Pool, seed [][2]any, now time.Time) {
	t.Helper()
	if _, err := pool.Exec(ctx, "TRUNCATE "+strings.Join(acctTables, ", ")+" RESTART IDENTITY CASCADE"); err != nil {
		t.Fatal(err)
	}
	for _, item := range seed {
		table := item[0].(string)
		row := item[1].(map[string]any)
		cols := make([]string, 0, len(row))
		for c := range row {
			cols = append(cols, c)
		}
		sort.Strings(cols)
		marks := make([]string, len(cols))
		vals := make([]any, len(cols))
		for i, c := range cols {
			marks[i] = "$" + strconv.Itoa(i+1)
			vals[i] = seedValue(row[c], now)
		}
		if _, err := pool.Exec(ctx, "INSERT INTO "+table+" ("+strings.Join(cols, ", ")+") VALUES ("+strings.Join(marks, ", ")+")", vals...); err != nil {
			t.Fatalf("seed %s: %v", table, err)
		}
	}
	for _, table := range acctTables {
		if _, err := pool.Exec(ctx, fmt.Sprintf(`SELECT setval(pg_get_serial_sequence('%s', 'id'), COALESCE((SELECT MAX(id) FROM %s), 0) + 1, false)`, table, table)); err != nil {
			t.Fatal(err)
		}
	}
}

// acctFormValue is the script's form_pairs: <totp> is the staged secret's
// code at request time, <totp-spaced> the same as " 123 456 ".
func acctFormValue(t *testing.T, staged, v string, now time.Time) string {
	t.Helper()
	if v != "<totp>" && v != "<totp-spaced>" {
		return v
	}
	code, err := acctTOTPAt(staged, now.Unix()/30)
	if err != nil {
		t.Fatal(err)
	}
	if v == "<totp-spaced>" {
		return " " + code[:3] + " " + code[3:] + " "
	}
	return code
}

// runAccountGolden replays every case of file through Routes.
func runAccountGolden(t *testing.T, file string) {
	raw, err := os.ReadFile(file)
	if err != nil {
		t.Fatal(err)
	}
	var g acctGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	pool := testPool(t)
	ctx := context.Background()
	sum := sha256.Sum256([]byte(g.Nonce))
	csrfToken, err := secure.NewTimedSerializer(g.Secret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, time.Now())
	if err != nil {
		t.Fatal(err)
	}
	var mu sync.Mutex
	var sent []int64
	savedSend, savedBackground := acctSendNow, acctBackground
	acctSendNow = func(_ context.Context, _ *pgxpool.Pool, _ func(string) string, id int64) error {
		mu.Lock()
		sent = append(sent, id)
		mu.Unlock()
		return nil
	}
	acctBackground = func(f func()) { f() }
	t.Cleanup(func() { acctSendNow, acctBackground = savedSend, savedBackground })
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			now := time.Now()
			acctLoadSeed(t, ctx, pool, append(append([][2]any{}, g.Seed...), c.Seed...), now)
			sent = nil
			getenv := func(k string) string { return g.Env[k] }
			mux := http.NewServeMux()
			for _, r := range Routes(pool, getenv, time.Now) {
				h := r.Handler
				// main.go's metrics.wrap sets hardenHeaders first.
				mux.Handle(r.Pattern, http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
					w.Header().Set("Cache-Control", "no-store, private")
					w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
					h(w, req)
				}))
			}
			csrf := c.CSRF == nil || *c.CSRF
			var pairs []string
			for _, p := range c.Form {
				pairs = append(pairs, url.QueryEscape(p[0])+"="+url.QueryEscape(acctFormValue(t, g.Staged, p[1], now)))
			}
			if csrf && c.Method == http.MethodPost {
				pairs = append(pairs, "_csrf="+url.QueryEscape(csrfToken))
			}
			target := "http://testserver" + c.Path
			if c.Query != "" {
				target += "?" + c.Query
			}
			req := httptest.NewRequest(c.Method, target, strings.NewReader(strings.Join(pairs, "&")))
			req.RemoteAddr = "testclient:50000" // Starlette TestClient's request.client
			req.Header.Set("User-Agent", "testclient")
			if c.Method == http.MethodPost {
				req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
			}
			var cookies []string
			if c.Session != nil {
				cookies = append(cookies, "ubyhost_session="+sessionToken(t, g.Secret, c.Session, now))
			}
			if csrf {
				cookies = append(cookies, "ubyhost_csrf="+g.Nonce)
			}
			if c.Lang != "" {
				cookies = append(cookies, "ubyhost_lang="+c.Lang)
			}
			if len(cookies) > 0 {
				req.Header.Set("Cookie", strings.Join(cookies, "; "))
			}
			for k, v := range c.Headers {
				req.Header.Set(k, v)
			}
			rec := httptest.NewRecorder()
			mux.ServeHTTP(rec, req)
			res := rec.Result()
			w := c.Want
			if res.StatusCode != w.Status {
				t.Fatalf("status %d, want %d (body %q)", res.StatusCode, w.Status, rec.Body.String())
			}
			for _, h := range []struct {
				name string
				want *string
			}{{"Location", w.Location}, {"Content-Type", w.ContentType}, {"Cache-Control", w.CacheControl}, {"Referrer-Policy", w.ReferrerPolicy}} {
				if got := header(res.Header, h.name); str(got) != str(h.want) {
					t.Errorf("%s %q, want %q", h.name, str(got), str(h.want))
				}
			}
			if w.Body != nil {
				got := rec.Body.String()
				if strings.HasPrefix(res.Header.Get("Content-Type"), "text/html") {
					got = acctPageNorm(got, c.Fresh)
				}
				if got != *w.Body {
					t.Errorf("body differs at %d:\n got  %s\n want %s", acctFirstDiff(got, *w.Body), acctAround(got, acctFirstDiff(got, *w.Body)), acctAround(*w.Body, acctFirstDiff(got, *w.Body)))
				}
			} else if rec.Body.Len() != 0 {
				t.Errorf("body %q, want none", rec.Body.String())
			}
			var got []cookieRec
			for _, line := range res.Header["Set-Cookie"] {
				got = append(got, parseCookie(t, g.Secret, line, now))
			}
			sort.SliceStable(got, func(i, j int) bool { return got[i].Name < got[j].Name })
			if len(got) != len(w.Cookies) {
				t.Fatalf("cookies %+v, want %+v", got, w.Cookies)
			}
			for i := range got {
				wc := w.Cookies[i]
				if got[i].Name != wc.Name || got[i].Empty != wc.Empty || !reflect.DeepEqual(got[i].Attrs, wc.Attrs) ||
					(wc.Payload != nil && !samePayload(got[i].Payload, wc.Payload)) {
					t.Errorf("cookie %d: %+v, want %+v", i, got[i], wc)
				}
			}
			mu.Lock()
			gotSent := append([]int64{}, sent...)
			mu.Unlock()
			if len(gotSent) != len(w.Sent) || (len(w.Sent) > 0 && !reflect.DeepEqual(gotSent, w.Sent)) {
				t.Errorf("send_now %v, want %v", gotSent, w.Sent)
			}
			if db := acctDump(t, ctx, pool); !reflect.DeepEqual(db, w.DB) {
				for name := range w.DB {
					if !reflect.DeepEqual(db[name], w.DB[name]) {
						gj, _ := json.Marshal(db[name])
						wj, _ := json.Marshal(w.DB[name])
						t.Errorf("table %s:\n got  %s\n want %s", name, gj, wj)
					}
				}
			}
		})
	}
}

func acctFirstDiff(a, b string) int {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	for i := 0; i < n; i++ {
		if a[i] != b[i] {
			return i
		}
	}
	return n
}

func acctAround(s string, i int) string {
	lo, hi := i-80, i+80
	if lo < 0 {
		lo = 0
	}
	if hi > len(s) {
		hi = len(s)
	}
	return s[lo:hi]
}

func TestAccountSetupGoldenDatabase(t *testing.T) {
	runAccountGolden(t, "testdata/account_setup.json")
}
