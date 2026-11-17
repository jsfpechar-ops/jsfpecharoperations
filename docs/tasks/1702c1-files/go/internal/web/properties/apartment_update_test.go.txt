package properties

// Tests of POST /apartments/{id} (brief 1702c1). The golden cases are what
// App/scripts/go_apartment_update_golden.py recorded from the real Python
// route, in order: the answer and, after it, the property row, the password,
// the dated rates, the guest slug, the open alerts and the audit rows added.

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// apartmentUpdateGetenv is the golden script's environment: its secret key,
// door codes on with made-up TTLock app credentials, billing off.
func apartmentUpdateGetenv(k string) string {
	return map[string]string{"UBYHOST_SECRET_KEY": apartmentCreateSecret, "UBYHOST_DOOR_CODES": "1",
		"UBYHOST_TTLOCK_CLIENT_ID": "golden-client", "UBYHOST_TTLOCK_CLIENT_SECRET": "golden-secret"}[k]
}

type apartmentUpdateState struct {
	Row      map[string]*string `json:"row"`
	Password *string            `json:"password"`
	Rates    [][]any            `json:"rates"`
	Slug     *string            `json:"slug"`
	Alerts   []string           `json:"alerts"`
}

type apartmentUpdateGolden struct {
	CSRFNonce string `json:"csrf_nonce"`
	Seed      []struct {
		Table   string   `json:"table"`
		Columns []string `json:"columns"`
		Rows    [][]any  `json:"rows"`
	} `json:"seed"`
	Columns []string `json:"columns"`
	Cases   []struct {
		Name      string               `json:"name"`
		User      int64                `json:"user"`
		Workspace int64                `json:"workspace"`
		Lang      string               `json:"lang"`
		CSRF      bool                 `json:"csrf"`
		ID        int64                `json:"id"`
		Form      map[string]string    `json:"form"`
		Status    int                  `json:"status"`
		Location  *string              `json:"location"`
		After     apartmentUpdateState `json:"after"`
		Changed   bool                 `json:"changed"`
		Page      bool                 `json:"page"`
		Audit     []map[string]any     `json:"audit"`
	} `json:"cases"`
}

func loadApartmentUpdateGolden(t *testing.T) apartmentUpdateGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/apartment_update_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	var g apartmentUpdateGolden
	if err := dec.Decode(&g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 25 || len(g.Columns) < 40 {
		t.Fatal("apartment update golden file is too small")
	}
	return g
}

// apartmentUpdateText is a golden JSON value as the text PostgreSQL gives back.
func apartmentUpdateText(v any) any {
	if v == nil {
		return nil
	}
	return fmt.Sprint(v)
}

// apartmentUpdateNormal makes a recorded state comparable with a read one.
func apartmentUpdateNormal(s apartmentUpdateState) apartmentUpdateState {
	rates := [][]any{}
	for _, r := range s.Rates {
		rates = append(rates, []any{apartmentUpdateText(r[0]), apartmentUpdateText(r[1])})
	}
	s.Rates = rates
	if s.Alerts == nil {
		s.Alerts = []string{}
	}
	return s
}

// apartmentUpdateRead is what the golden script records after each request.
func apartmentUpdateRead(t *testing.T, ctx context.Context, pool *pgxpool.Pool, g apartmentUpdateGolden, id int64) apartmentUpdateState {
	t.Helper()
	casts := make([]string, len(g.Columns))
	vals := make([]*string, len(g.Columns))
	dest := make([]any, len(g.Columns))
	for i, c := range g.Columns {
		casts[i], dest[i] = c+"::text", &vals[i]
	}
	var enc *string
	if err := pool.QueryRow(ctx, "SELECT "+strings.Join(casts, ", ")+", uby_ws_password_enc FROM apartment WHERE id = $1", id).
		Scan(append(dest, &enc)...); err != nil {
		t.Fatal(err)
	}
	s := apartmentUpdateState{Row: map[string]*string{}, Rates: [][]any{}, Alerts: []string{}}
	for i, c := range g.Columns {
		s.Row[c] = vals[i]
	}
	if enc != nil && *enc != "" {
		keys, err := secure.LoadDataKeys(apartmentUpdateGetenv)
		if err != nil {
			t.Fatal(err)
		}
		plain, err := keys.Decrypt(*enc, 0, time.Now())
		if err != nil {
			t.Fatal(err)
		}
		text := string(plain)
		s.Password = &text
	}
	rows, err := pool.Query(ctx, `SELECT rate_czk::text, effective_from FROM stay_fee_rate WHERE apartment_id = $1 ORDER BY effective_from`, id)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var rate, from string
		if err := rows.Scan(&rate, &from); err != nil {
			t.Fatal(err)
		}
		s.Rates = append(s.Rates, []any{rate, from})
	}
	rows.Close()
	var slug string
	if err := pool.QueryRow(ctx, `SELECT slug FROM apartment_slug WHERE apartment_id = $1 AND is_current = 1`, id).Scan(&slug); err == nil {
		s.Slug = &slug
	}
	rows, err = pool.Query(ctx, `SELECT dedupe_key FROM alert WHERE apartment_id = $1 AND resolved_at IS NULL ORDER BY id`, id)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var key string
		if err := rows.Scan(&key); err != nil {
			t.Fatal(err)
		}
		s.Alerts = append(s.Alerts, key)
	}
	rows.Close()
	return s
}

func apartmentUpdateAudit(t *testing.T, ctx context.Context, pool *pgxpool.Pool, after int64) ([]map[string]any, int64) {
	t.Helper()
	rows, err := pool.Query(ctx, `SELECT id, action, detail, actor, owner_user_id::text, actor_user_id::text,
		impersonator_user_id::text FROM audit WHERE id > $1 ORDER BY id`, after)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	out, last := []map[string]any{}, after
	for rows.Next() {
		var action, detail, actor string
		var owner, actorID, impersonator *string
		if err := rows.Scan(&last, &action, &detail, &actor, &owner, &actorID, &impersonator); err != nil {
			t.Fatal(err)
		}
		row := map[string]any{"action": action, "detail": detail, "actor": actor}
		for k, v := range map[string]*string{"owner_user_id": owner, "actor_user_id": actorID, "impersonator_user_id": impersonator} {
			row[k] = nil
			if v != nil {
				row[k] = *v
			}
		}
		out = append(out, row)
	}
	return out, last
}

// TestApartmentUpdateMatchesPython sends the golden requests in order and
// compares each answer and what it wrote. A refused save Python answers with
// the page drawn again answers 501 here until brief 1702c2, and neither side
// writes anything.
func TestApartmentUpdateMatchesPython(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, pool, apartmentUpdateGetenv, testClock)
	ctx := context.Background()
	_, auditMark := apartmentUpdateAudit(t, ctx, pool, 0)
	pages := 0
	for _, c := range g.Cases {
		before := apartmentUpdateRead(t, ctx, pool, g, c.ID)
		rec := apartmentFormPost(t, mux, fmt.Sprintf("/apartments/%d", c.ID), g.CSRFNonce, c.User, c.Workspace, c.Lang, c.CSRF, c.Form)
		got := apartmentUpdateRead(t, ctx, pool, g, c.ID)
		var audit []map[string]any
		audit, auditMark = apartmentUpdateAudit(t, ctx, pool, auditMark)
		if c.Page {
			pages++
			if c.Changed {
				t.Fatalf("%s: the golden file says Python wrote before drawing the page", c.Name)
			}
			if rec.Code != http.StatusNotImplemented || rec.Header().Get("X-Ubyhost-Not-Ported") != "1" {
				t.Errorf("%s: %d, want 501 with the fallback header (Python %d)", c.Name, rec.Code, c.Status)
			}
			if !reflect.DeepEqual(got, before) || len(audit) != 0 {
				t.Errorf("%s: wrote something before leaving the page to Python", c.Name)
			}
			continue
		}
		want := ""
		if c.Location != nil {
			want = *c.Location
		}
		if rec.Code != c.Status || rec.Header().Get("Location") != want {
			t.Errorf("%s: %d %q\n Python %d %q", c.Name, rec.Code, rec.Header().Get("Location"), c.Status, want)
		}
		if exp := apartmentUpdateNormal(c.After); !reflect.DeepEqual(got, exp) {
			gj, _ := json.Marshal(got)
			ej, _ := json.Marshal(exp)
			t.Errorf("%s: after the request\n go %s\n py %s", c.Name, gj, ej)
		}
		exp := []map[string]any{}
		for _, row := range c.Audit {
			norm := map[string]any{}
			for k, v := range row {
				norm[k] = apartmentUpdateText(v)
			}
			exp = append(exp, norm)
		}
		if !reflect.DeepEqual(audit, exp) {
			t.Errorf("%s: audit\n go %v\n py %v", c.Name, audit, exp)
		}
	}
	if pages < 8 {
		t.Errorf("only %d refused-page cases", pages)
	}
}

// TestApartmentUpdateNotPorted: the branches left to Python (later briefs)
// answer 501 with the fallback header and write nothing.
func TestApartmentUpdateNotPorted(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, pool, apartmentUpdateGetenv, testClock)
	ctx := context.Background()
	base := g.Cases[3].Form // the full save of property 201
	for name, extra := range map[string]map[string]string{
		"wizard step":           {"setup_step": "property"},
		"retired wizard step":   {"setup_step": "calendar_sync"},
		"wizard return_to":      {"return_to": "/apartments/201/setup/police"},
		"quoted wizard return":  {"return_to": "%2Fapartments%2F201%2Fsetup%2Fpolice"},
		"fee signature section": {"fee_signature_section": "1", "signature_name": "A. Host"},
		"fee return":            {"fee_return_to": "/stay-fees?month=2026-10"},
		"police-letter fields":  {"letter_fields": "uby_idub, uby_mark"},
		"guest pay block":       {"stay_fee_guest_form": "1"},
		"data box":              {"stay_fee_authority_databox": "abcdefg"},
		"full-width operator":   {"legal_entity_id": "２１"},
		"Arabic-Indic PIN":      {"permalink_pin": "١٢٣٤٥٦"},
		"superscript hour":      {"checkin_hour": "1²"},
		"basic ISO rate day":    {"stay_fee_rate_from": "20261201"},
	} {
		form := map[string]string{}
		for k, v := range base {
			form[k] = v
		}
		for k, v := range extra {
			form[k] = v
		}
		before := apartmentUpdateRead(t, ctx, pool, g, 201)
		rec := apartmentFormPost(t, mux, "/apartments/201", g.CSRFNonce, 2, 0, "en", true, form)
		if rec.Code != http.StatusNotImplemented || rec.Header().Get("X-Ubyhost-Not-Ported") != "1" {
			t.Errorf("%s: %d, want 501 with the fallback header", name, rec.Code)
		}
		if after := apartmentUpdateRead(t, ctx, pool, g, 201); !reflect.DeepEqual(after, before) {
			t.Errorf("%s: the property was written", name)
		}
	}
}

// TestApartmentUpdateHelpers: values written by hand from admin._property_hour_changes.
func TestApartmentUpdateHelpers(t *testing.T) {
	for raw, want := range map[string]string{"0": "0", "23": "23", "+7": "7", "0_9": "9", "-0": "0", "24": "bad", "-1": "bad",
		"7.0": "bad", "x": "bad", "1__0": "bad", "99999999999999999999": "bad"} {
		got := "bad"
		if v, ok := apartmentHour(raw); ok {
			got = fmt.Sprint(v)
		}
		if got != want {
			t.Errorf("apartmentHour(%q) = %s, want %s", raw, got, want)
		}
	}
	cols := dropColumns([]column{{"a", 1}, {"b", 2}, {"c", 3}}, "b", "x")
	if !reflect.DeepEqual(cols, []column{{"a", 1}, {"c", 3}}) {
		t.Errorf("dropColumns = %v", cols)
	}
}

// TestApartmentUpdateRegisterDoesNotTouchThePool: building the route uses no
// pool, and only POST is mounted.
func TestApartmentUpdateRegisterDoesNotTouchThePool(t *testing.T) {
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, nil, apartmentUpdateGetenv, testClock)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/apartments/201", nil))
	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET /apartments/201: code %d, want 405", rec.Code)
	}
}
