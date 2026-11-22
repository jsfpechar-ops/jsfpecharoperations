package properties

// Tests of POST /apartments (brief 1700b2). The golden cases are what
// App/scripts/go_apartment_create_golden.py recorded from the real Python
// route: the answer, the written row and the refused page's error fragments.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"reflect"
	"regexp"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// apartmentCreateSecret is the golden script's UBYHOST_SECRET_KEY.
const apartmentCreateSecret = "golden-secret-key-not-for-real-use"

func apartmentCreateGetenv(k string) string {
	return map[string]string{"UBYHOST_SECRET_KEY": apartmentCreateSecret}[k]
}

type apartmentCreateWritten struct {
	Row            map[string]*string `json:"row"`
	TokenLength    int                `json:"token_length"`
	PIN            bool               `json:"pin"`
	Password       *string            `json:"password"`
	Rates          [][]any            `json:"rates"`
	Setup          *string            `json:"setup"`
	SlugReadable   string             `json:"slug_readable"`
	SlugCodeLength int                `json:"slug_code_length"`
	Audit          map[string]any     `json:"audit"`
}

type apartmentCreateGolden struct {
	CSRFNonce string `json:"csrf_nonce"`
	Seed      []struct {
		Table   string   `json:"table"`
		Columns []string `json:"columns"`
		Rows    [][]any  `json:"rows"`
	} `json:"seed"`
	Columns   []string `json:"columns"`
	Fragments []string `json:"fragments"`
	Cases     []struct {
		Name      string                  `json:"name"`
		User      int64                   `json:"user"`
		Workspace int64                   `json:"workspace"`
		Lang      string                  `json:"lang"`
		CSRF      bool                    `json:"csrf"`
		Form      map[string]string       `json:"form"`
		Status    int                     `json:"status"`
		Location  *string                 `json:"location"`
		Created   *apartmentCreateWritten `json:"created"`
		Fragments [][]string              `json:"fragments"`
	} `json:"cases"`
	Apartments []json.Number `json:"apartments"`
}

func loadApartmentCreateGolden(t *testing.T) apartmentCreateGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/apartment_create_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	var g apartmentCreateGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 20 || len(g.Columns) < 30 {
		t.Fatal("apartment create golden file is too small")
	}
	return g
}

// apartmentCreateSeed writes the golden seed rows and moves the apartment id
// sequence past them, so new ids follow SQLite's max(id) + 1 as in Python.
func apartmentCreateSeed(t *testing.T, pool *pgxpool.Pool, g apartmentCreateGolden) {
	t.Helper()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = "$" + strconv.Itoa(i+1)
		}
		sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table.Table, strings.Join(table.Columns, ", "), strings.Join(marks, ", "))
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = v
				if n, ok := v.(json.Number); ok {
					args[i], _ = n.Int64()
				}
			}
			mustExec(t, pool, sql, args...)
		}
	}
	mustExec(t, pool, `SELECT setval(pg_get_serial_sequence('apartment', 'id'), (SELECT max(id) FROM apartment))`)
}

// apartmentCreatePost sends POST /apartments as user (0: signed out),
// previewing workspace when it is not 0, with a valid CSRF token when csrf is true.
func apartmentCreatePost(t *testing.T, h http.Handler, nonce string, user, workspace int64, lang string, csrf bool,
	fields map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	return apartmentFormPost(t, h, "/apartments", nonce, user, workspace, lang, csrf, fields)
}

// apartmentFormPost is apartmentCreatePost to any path (POST /apartments/{id} of brief 1702c1 too).
func apartmentFormPost(t *testing.T, h http.Handler, path, nonce string, user, workspace int64, lang string, csrf bool,
	fields map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	form := url.Values{}
	for k, v := range fields {
		form.Set(k, v)
	}
	if csrf {
		sum := sha256.Sum256([]byte(nonce))
		token, err := secure.NewTimedSerializer(apartmentCreateSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, testNow)
		if err != nil {
			t.Fatal(err)
		}
		form.Set("_csrf", token)
	}
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(form.Encode()))
	req.Header.Set("Accept", "text/html")
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: nonce})
	if user != 0 {
		payload := map[string]any{"uid": user, "sv": 1}
		if workspace != 0 {
			payload["as"] = workspace
			payload["ast"] = testNow.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(apartmentCreateSecret, payload, testNow)})
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func apartmentCreateMaxID(t *testing.T, pool *pgxpool.Pool) int64 {
	t.Helper()
	var n int64
	if err := pool.QueryRow(context.Background(), `SELECT COALESCE(max(id), 0) FROM apartment`).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

// apartmentCreateRead is what the golden script records for a written property.
func apartmentCreateRead(t *testing.T, pool *pgxpool.Pool, columns []string, id int64) apartmentCreateWritten {
	t.Helper()
	ctx := context.Background()
	casts := make([]string, len(columns))
	vals := make([]*string, len(columns))
	dest := make([]any, len(columns))
	for i, c := range columns {
		casts[i], dest[i] = c+"::text", &vals[i]
	}
	var token, pin, enc *string
	dest = append(dest, &token, &pin, &enc)
	if err := pool.QueryRow(ctx, "SELECT "+strings.Join(casts, ", ")+", permalink_token, permalink_pin, uby_ws_password_enc FROM apartment WHERE id = $1",
		id).Scan(dest...); err != nil {
		t.Fatal(err)
	}
	w := apartmentCreateWritten{Row: map[string]*string{}, Rates: [][]any{}}
	for i, c := range columns {
		w.Row[c] = vals[i]
	}
	if token != nil {
		w.TokenLength = len(*token)
	}
	w.PIN = pin != nil && regexp.MustCompile(`^[0-9]{6}$`).MatchString(*pin)
	if enc != nil && *enc != "" {
		keys, err := secure.LoadDataKeys(apartmentCreateGetenv)
		if err != nil {
			t.Fatal(err)
		}
		plain, err := keys.Decrypt(*enc, 0, time.Now())
		if err != nil {
			t.Fatal(err)
		}
		text := string(plain)
		w.Password = &text
	}
	rows, err := pool.Query(ctx, `SELECT rate_czk::text, effective_from::text FROM stay_fee_rate WHERE apartment_id = $1 ORDER BY effective_from`, id)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var rate, from string
		if err := rows.Scan(&rate, &from); err != nil {
			t.Fatal(err)
		}
		w.Rates = append(w.Rates, []any{rate, from})
	}
	rows.Close()
	var setup string
	err = pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, fmt.Sprintf("property_setup:%d", id)).Scan(&setup)
	if err == nil {
		w.Setup = &setup
	} else if !errors.Is(err, pgx.ErrNoRows) {
		t.Fatal(err)
	}
	var slug string
	if err := pool.QueryRow(ctx, `SELECT slug FROM apartment_slug WHERE apartment_id = $1 AND is_current = 1`, id).Scan(&slug); err != nil {
		t.Fatal(err)
	}
	i := strings.LastIndex(slug, "-")
	w.SlugReadable, w.SlugCodeLength = slug[:i], len(slug)-i-1
	var action, detail, actor string
	var owner, actorID, impersonator *int64
	if err := pool.QueryRow(ctx, `SELECT action, detail, actor, owner_user_id, actor_user_id, impersonator_user_id FROM audit
		WHERE action = 'apartment_created' AND detail = $1`, fmt.Sprintf("id=%d", id)).Scan(&action, &detail, &actor, &owner, &actorID, &impersonator); err != nil {
		t.Fatal(err)
	}
	w.Audit = map[string]any{"action": action, "detail": detail, "actor": actor, "owner_user_id": owner,
		"actor_user_id": actorID, "impersonator_user_id": impersonator}
	return w
}

// apartmentCreateNormal turns golden JSON values (json.Number, *int64) into text for comparing.
func apartmentCreateNormal(w apartmentCreateWritten) apartmentCreateWritten {
	text := func(v any) any {
		switch x := v.(type) {
		case nil:
			return nil
		case *int64:
			if x == nil {
				return nil
			}
			return strconv.FormatInt(*x, 10)
		}
		return fmt.Sprint(v)
	}
	audit := map[string]any{}
	for k, v := range w.Audit {
		audit[k] = text(v)
	}
	rates := [][]any{}
	for _, r := range w.Rates {
		rates = append(rates, []any{text(r[0]), text(r[1])})
	}
	w.Audit, w.Rates = audit, rates
	return w
}

// apartmentCreateFragments applies the golden patterns to a page, skipping the CSRF field.
func apartmentCreateFragments(patterns []string, body string) [][]string {
	found := [][]string{}
	for _, p := range patterns {
		for _, m := range regexp.MustCompile(p).FindAllStringSubmatch(body, -1) {
			if m[1] == "_csrf" {
				continue
			}
			parts := make([]string, len(m)-1)
			for i, part := range m[1:] {
				parts[i] = strings.Join(strings.Fields(part), " ") // the golden script's " ".join(part.split())
			}
			found = append(found, parts)
		}
	}
	return found
}

// TestApartmentCreateMatchesPython sends the golden requests in order and
// compares each answer, each written row and each refused page.
func TestApartmentCreateMatchesPython(t *testing.T) {
	g := loadApartmentCreateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, g)
	mux := http.NewServeMux()
	RegisterApartmentCreate(mux, noWrap, pool, apartmentCreateGetenv, testClock)
	for _, c := range g.Cases {
		before := apartmentCreateMaxID(t, pool)
		rec := apartmentCreatePost(t, mux, g.CSRFNonce, c.User, c.Workspace, c.Lang, c.CSRF, c.Form)
		want := ""
		if c.Location != nil {
			want = *c.Location
		}
		if rec.Code != c.Status || rec.Header().Get("Location") != want {
			t.Errorf("%s: %d %q, Python %d %q", c.Name, rec.Code, rec.Header().Get("Location"), c.Status, want)
		}
		after := apartmentCreateMaxID(t, pool)
		switch {
		case c.Created != nil:
			if after == before {
				t.Errorf("%s: nothing written", c.Name)
				continue
			}
			got := apartmentCreateNormal(apartmentCreateRead(t, pool, g.Columns, after))
			if exp := apartmentCreateNormal(*c.Created); !reflect.DeepEqual(got, exp) {
				gj, _ := json.Marshal(got)
				ej, _ := json.Marshal(exp)
				t.Errorf("%s: written\n go %s\n py %s", c.Name, gj, ej)
			}
		case after != before:
			t.Errorf("%s: wrote apartment %d, Python wrote nothing", c.Name, after)
		case c.Fragments != nil:
			if got := apartmentCreateFragments(g.Fragments, rec.Body.String()); !reflect.DeepEqual(got, c.Fragments) {
				t.Errorf("%s: page fragments\n go %q\n py %q", c.Name, got, c.Fragments)
			}
		}
	}
	var ids []json.Number
	rows, err := pool.Query(context.Background(), `SELECT id::text FROM apartment ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			t.Fatal(err)
		}
		ids = append(ids, json.Number(id))
	}
	rows.Close()
	if !reflect.DeepEqual(ids, g.Apartments) {
		t.Errorf("apartments %v, Python %v", ids, g.Apartments)
	}
}

// TestApartmentCreateNotPorted: unported branches return 404 or an interim redirect.
func TestApartmentCreateNotPorted(t *testing.T) {
	g := loadApartmentCreateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, g)
	mux := http.NewServeMux()
	RegisterApartmentCreate(mux, noWrap, pool, apartmentCreateGetenv, testClock)
	base := map[string]string{"internal_name": "X", "legal_entity_id": "21", "addr_street": "A", "addr_house_no": "1",
		"addr_zip": "12000", "addr_obec": "Brno"}
	for name, extra := range map[string]map[string]string{
		"guest pay block": {"stay_fee_guest_form": "1"},
	} {
		form := map[string]string{}
		for k, v := range base {
			form[k] = v
		}
		for k, v := range extra {
			form[k] = v
		}
		before := apartmentCreateMaxID(t, pool)
		rec := apartmentCreatePost(t, mux, g.CSRFNonce, 2, 0, "en", true, form)
		if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") == "" {
			t.Errorf("%s: %d, want 303 with Location", name, rec.Code)
		}
		if loc := rec.Header().Get("Location"); !strings.Contains(loc, "err=") {
			t.Errorf("%s: Location %q missing err flash", name, loc)
		}
		if rec.Header().Get("X-Ubyhost-Not-Ported") == "1" {
			t.Errorf("%s: fallback header set", name)
		}
		if apartmentCreateMaxID(t, pool) != before {
			t.Errorf("%s: a row was written", name)
		}
	}
	for name, extra := range map[string]map[string]string{
		"full-width id":        {"legal_entity_id": "２１"},
		"id past 64 bits":      {"copy_from": "99999999999999999999"},
		"superscript postcode": {"addr_zip": "12000²"},
		"Arabic-Indic rate":    {"stay_fee_rate_czk": "٥٠"},
	} {
		form := map[string]string{}
		for k, v := range base {
			form[k] = v
		}
		for k, v := range extra {
			form[k] = v
		}
		before := apartmentCreateMaxID(t, pool)
		rec := apartmentCreatePost(t, mux, g.CSRFNonce, 2, 0, "en", true, form)
		if rec.Code != http.StatusNotFound {
			t.Errorf("%s: %d, want 404", name, rec.Code)
		}
		if !strings.Contains(rec.Body.String(), "Page not found") {
			t.Errorf("%s: body lacks branded 404", name)
		}
		if rec.Header().Get("X-Ubyhost-Not-Ported") == "1" {
			t.Errorf("%s: fallback header set", name)
		}
		if apartmentCreateMaxID(t, pool) != before {
			t.Errorf("%s: a row was written", name)
		}
	}
}

// TestApartmentCreateHelpers: values written by hand from property_setup.guest_city and admin._form_int.
func TestApartmentCreateHelpers(t *testing.T) {
	for in, want := range map[string]string{"Praha 10": "Prague", " PRAHA": "Prague", "plzeň": "Pilsen", " PLZEŇ ": "Pilsen",
		"Brno \t  město": "Brno město", "": "", "Plzeň 3": "Plzeň 3"} {
		if got := guestCity(in); got != want {
			t.Errorf("guestCity(%q) = %q, want %q", in, got, want)
		}
	}
	for raw, want := range map[string]string{"": "nil", " 7 ": "7", "+5": "5", "1_000": "1000", "-3": "-3", "1__0": "nil", "x": "nil", "1.0": "nil"} {
		r := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(url.Values{"k": {raw}}.Encode()))
		r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		_ = r.ParseForm()
		n, ok := apartmentFormInt(r, "k")
		got := "nil"
		if n != nil {
			got = strconv.FormatInt(*n, 10)
		}
		if !ok || got != want {
			t.Errorf("apartmentFormInt(%q) = %s %v, want %s", raw, got, ok, want)
		}
	}
}

// TestApartmentCreateRegisterDoesNotTouchThePool: building the route uses no
// pool, and only POST is mounted.
func TestApartmentCreateRegisterDoesNotTouchThePool(t *testing.T) {
	mux := http.NewServeMux()
	RegisterApartmentCreate(mux, noWrap, nil, apartmentCreateGetenv, testClock)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/apartments", nil))
	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET /apartments: code %d, want 405", rec.Code)
	}
}
