package properties

// Tests of POST /apartments/{id} (brief 1702c1). The golden cases are what
// App/scripts/go_apartment_update_golden.py recorded from the real Python
// route, in order: the answer and, after it, the property row, the password,
// the dated rates, the guest slug, the open alerts and the audit rows added.

import (
	"context"
	"encoding/base64"
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

// apartmentRefusedPages are lines of the page a refused save draws again
// (brief 1702c2), per golden case: want, then lines that must be absent. Every
// line is written by hand from apartment_form.html and its includes, as the
// 1702b tests of apartment_detail_refused_test.go are.
var apartmentRefusedPages = map[string][2][]string{
	"hour that is not a number": {{
		`data-property-settings-form data-unsaved-guard>`,
		`<details class="prop-sec" id="sec-basics" open>`,
		`<p class="err-text" role="alert" data-field-error>Choose the check-in and check-out hour.</p>`,
		`data-first-error="checkin_hour"><span class="grow">Not saved: fix 1 field. Nothing was changed.</span>`,
		`<textarea id="notes" name="notes" aria-describedby="notes-help">must not be saved</textarea>`,
		`class="airbnb-actions"`,
	}, {`<option value="15" selected>`, `data-dirty-start`}},
	"hour 24": {{
		`<details class="prop-sec" id="sec-basics" open>`,
		`data-first-error="checkin_hour"><span class="grow">Not saved: fix 1 field. Nothing was changed.</span>`,
		`<option value="15" selected>15:00`,
	}, {`<option value="10" selected>`, `data-dirty-start`}},
	"door codes need both times": {{
		`<details class="prop-sec" id="sec-lock" open>`,
		`<p class="err-text" id="door-code-times-error" role="alert" data-field-error>Check-in and check-out times are missing, so door codes cannot work yet. Set them first.</p>`,
		`id="lock_checkin_hour" name="lock_checkin_hour" data-hour-twin="checkin_hour" aria-invalid="true" aria-describedby="door-code-times-error">`,
		`data-first-error="lock_checkin_hour"><span class="grow">Not saved: fix 1 field. Nothing was changed.</span>`,
		`value="L1" selected>`,
	}, {`<details class="prop-sec" id="sec-basics" open>`, `data-dirty-start`}},
	"operator refresh": {{
		`data-property-settings-form data-unsaved-guard>`,
		`<textarea id="notes" name="notes" aria-describedby="notes-help">must not be saved</textarea>`,
	}, {`data-save-summary`, `aria-invalid="true"`, `data-field-error>`, `data-dirty-start`}},
	"another host's operator": {{
		`data-unsaved-guard data-dirty-start="1">`,
		`<select id="legal_entity_id" name="legal_entity_id" required aria-describedby="operator-message" aria-invalid="true">`,
		`<p class="err-text" id="operator-message" role="alert">Choose the operator for this property.</p>`,
		`data-first-error="legal_entity_id"><span class="grow">Not saved: fix 1 field. Nothing was changed.</span>`,
	}, {`<option value="21" selected>`, `<option value="31"`}},
	"archived operator": {{
		`data-unsaved-guard data-dirty-start="1">`,
		`<p class="err-text" id="operator-message" role="alert">Choose the operator for this property.</p>`,
		`data-first-error="legal_entity_id">`,
	}, {`<option value="21" selected>`}},
	"another host's controller": {{
		`data-unsaved-guard data-dirty-start="1">`,
		`<select id="data_controller_entity_id" name="data_controller_entity_id" aria-describedby="controller-message" aria-invalid="true">`,
		`<p class="err-text" id="controller-message" role="alert" data-field-error>That data controller no longer exists.</p>`,
		`data-first-error="data_controller_entity_id"><span class="grow">Not saved: fix 1 field. Nothing was changed.</span>`,
		`<option value="21" selected>Alpha s.r.o.`,
	}, {`id="operator-message" role="alert"`, `<option value="31"`}},
	"broken address": {{
		`data-property-settings-form data-unsaved-guard>`,
		`<p class="err-text" id="addr_zip-error" role="alert">PSČ má přesně 5 číslic.</p>`,
		`<p class="err-text" id="addr_street-error" role="alert">Vyplňte ulici.</p>`,
		`data-first-error="addr_zip"><span class="grow">Neuloženo: opravte 2 pole. Nic se nezměnilo.</span> <a href="#addr_zip">`,
	}, {`data-dirty-start`, `Sokolovská`}},
	"council account that does not check": {{
		`<details class="prop-sec" id="sec-fee" open>`,
		`<div class="toast err" data-toast data-toast-kind="error" data-toast-sticky>
            <span class="grow">This account number does not add up.`,
		`value="19-2000145399/0800" aria-invalid="true">`,
		`<p class="err-text small" id="stay-fee-account-error" role="alert" data-field-error>This account number does not add up.`,
		`data-first-error="stay_fee_council_account"><span class="grow">Not saved: fix 1 field. Nothing was changed.</span>`,
	}, {`<details class="prop-sec" id="sec-basics" open>`, `data-dirty-start`, `fee-return-note`}},
}

// TestApartmentUpdateMatchesPython sends the golden requests in order and
// compares each answer and what it wrote. A refused save Python answers with
// the page drawn again: the same status, the lines of apartmentRefusedPages,
// and neither side writes anything.
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
			if rec.Code != c.Status || rec.Header().Get("Location") != "" {
				t.Errorf("%s: %d %q, Python %d", c.Name, rec.Code, rec.Header().Get("Location"), c.Status)
			}
			if !reflect.DeepEqual(got, before) || len(audit) != 0 {
				t.Errorf("%s: a refused save wrote something", c.Name)
			}
			lines, ok := apartmentRefusedPages[c.Name]
			if !ok {
				t.Errorf("%s: no expected lines", c.Name)
			}
			adCheck(t, c.Name, rec.Body.String(), lines[0], lines[1])
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

// TestApartmentUpdateNotPorted: unported branches redirect with an interim flash or 404.
func TestApartmentUpdateNotPorted(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, pool, apartmentUpdateGetenv, testClock)
	ctx := context.Background()
	base := g.Cases[3].Form
	redirectCases := map[string]map[string]string{
		"calendar wizard step":   {"setup_step": "calendar"},
		"guest link wizard step": {"setup_step": "guest_link"},
		"not a wizard step":      {"setup_step": "calendar_sync"},
		"wizard return_to":       {"return_to": "/apartments/201/setup/police"},
		"quoted wizard return":   {"return_to": "%2Fapartments%2F201%2Fsetup%2Fpolice"},
		"guest pay block":        {"stay_fee_guest_form": "1"},
		"Arabic-Indic PIN":       {"permalink_pin": "١٢٣٤٥٦"},
		"superscript hour":       {"checkin_hour": "1²"},
		"basic ISO rate day":     {"stay_fee_rate_from": "20261201"},
	}
	for name, extra := range redirectCases {
		form := map[string]string{}
		for k, v := range base {
			form[k] = v
		}
		for k, v := range extra {
			form[k] = v
		}
		before := apartmentUpdateRead(t, ctx, pool, g, 201)
		rec := apartmentFormPost(t, mux, "/apartments/201", g.CSRFNonce, 2, 0, "en", true, form)
		if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") == "" {
			t.Errorf("%s: %d, want 303 with Location", name, rec.Code)
		}
		if !strings.Contains(rec.Header().Get("Location"), "err=") {
			t.Errorf("%s: Location %q missing err flash", name, rec.Header().Get("Location"))
		}
		if rec.Header().Get("X-Ubyhost-Not-Ported") == "1" {
			t.Errorf("%s: fallback header set", name)
		}
		if after := apartmentUpdateRead(t, ctx, pool, g, 201); !reflect.DeepEqual(after, before) {
			t.Errorf("%s: the property was written", name)
		}
	}
	for name, extra := range map[string]map[string]string{
		"full-width operator": {"legal_entity_id": "２１"},
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
		if rec.Code != http.StatusNotFound {
			t.Errorf("%s: %d, want 404", name, rec.Code)
		}
		if !strings.Contains(rec.Body.String(), "Page not found") {
			t.Errorf("%s: body lacks branded 404", name)
		}
		if rec.Header().Get("X-Ubyhost-Not-Ported") == "1" {
			t.Errorf("%s: fallback header set", name)
		}
		if after := apartmentUpdateRead(t, ctx, pool, g, 201); !reflect.DeepEqual(after, before) {
			t.Errorf("%s: the property was written", name)
		}
	}
}


func TestApartmentUpdateStayFeeAuthorityDatabox(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, pool, apartmentUpdateGetenv, testClock)

	const key = "stay_fee_authority_databox"
	ctx := context.Background()
	for _, tc := range []struct {
		name  string
		post  bool
		value string
		want  string
	}{
		{"normalized", true, " AbC1234 ", "abc1234"},
		{"blank", true, " ", "<null>"},
		{"invalid", true, "abc-123", "<null>"},
		{"Unicode lowercase expansion", true, "İBC1234", "<null>"},
		{"omitted", false, "", "old1234"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if _, err := pool.Exec(ctx, "UPDATE apartment SET stay_fee_authority_databox = $1 WHERE id = 201", "old1234"); err != nil {
				t.Fatal(err)
			}
			form := map[string]string{}
			for k, v := range g.Cases[3].Form {
				form[k] = v
			}
			if tc.post {
				form[key] = tc.value
			} else {
				delete(form, key)
			}
			rec := apartmentFormPost(t, mux, "/apartments/201", g.CSRFNonce, 2, 0, "en", true, form)
			if rec.Code != http.StatusSeeOther {
				t.Fatalf("save returned %d, want %d", rec.Code, http.StatusSeeOther)
			}
			var got string
			if err := pool.QueryRow(ctx, "SELECT COALESCE(stay_fee_authority_databox, '<null>') FROM apartment WHERE id = 201").Scan(&got); err != nil {
				t.Fatal(err)
			}
			if got != tc.want {
				t.Errorf("authority databox = %q, want %q", got, tc.want)
			}
		})
	}
}

// TestApartmentUpdateRefusedDraft: what the host typed is escaped by
// html/template, the error lines come from Go keys only, and fee_return_to
// comes from the query on a refused save but not on a refused fee account
// (refuse_fee_save's extra), as in Python.
func TestApartmentUpdateRefusedDraft(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, pool, apartmentUpdateGetenv, testClock)
	ctx := context.Background()
	post := func(path string, extra map[string]string) string {
		t.Helper()
		form := map[string]string{}
		for k, v := range g.Cases[3].Form {
			form[k] = v
		}
		for k, v := range extra {
			form[k] = v
		}
		before := apartmentUpdateRead(t, ctx, pool, g, 201)
		rec := apartmentFormPost(t, mux, path, g.CSRFNonce, 2, 0, "en", true, form)
		if rec.Code != http.StatusBadRequest {
			t.Errorf("%s %v: %d, want 400", path, extra, rec.Code)
		}
		if after := apartmentUpdateRead(t, ctx, pool, g, 201); !reflect.DeepEqual(after, before) {
			t.Errorf("%s %v: the property was written", path, extra)
		}
		return rec.Body.String()
	}
	body := post("/apartments/201", map[string]string{"checkin_hour": "x", "internal_name": `<b>"Loft"</b>`,
		"notes": "</textarea><script>alert(1)</script>", "operator_error": "flash.apartments.saved_ready",
		"shared_time_error": "flash.apartments.saved_ready", "address_errors": "x", "lock_times_error": "1"})
	adCheck(t, "escaped", body, []string{
		`<h1 class="airbnb-title">&lt;b&gt;&#34;Loft&#34;&lt;/b&gt;</h1>`,
		`aria-describedby="notes-help">&lt;/textarea&gt;&lt;script&gt;alert(1)&lt;/script&gt;</textarea>`,
		`data-first-error="checkin_hour"><span class="grow">Not saved: fix 1 field. Nothing was changed.</span>`,
	}, []string{`<script>alert(1)`, `<b>"Loft"`, `This property is ready to report`, `data-dirty-start`, `door-code-times-error" role="alert"`})
	body = post("/apartments/201?return_to=%2Fstay-fees%3Fmonth%3D2026-10", map[string]string{"checkout_hour": "24"})
	adCheck(t, "return_to kept", body, []string{`<input type="hidden" name="fee_return_to" value="/stay-fees?month=2026-10">`}, nil)
	body = post("/apartments/201?return_to=%2Fstay-fees%3Fmonth%3D2026-10", map[string]string{
		"account_number": "124", "account_prefix": "", "stay_fee_authority_databox": " AbC1234 ",
	})
	adCheck(t, "refused fee draft", body, []string{`data-first-error="stay_fee_council_account"`, `value="abc1234"`}, []string{`name="fee_return_to"`, `fee-return-note`})
	// The guest-pay draft of refuse_fee_save is not ported.
	form := map[string]string{}
	for k, v := range g.Cases[3].Form {
		form[k] = v
	}
	form["account_number"], form["account_prefix"], form["stay_fee_guest_operator_account"] = "124", "", "19-2000145399/0800"
	rec := apartmentFormPost(t, mux, "/apartments/201", g.CSRFNonce, 2, 0, "en", true, form)
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") == "" {
		t.Errorf("guest-pay draft: %d, want 303 with Location", rec.Code)
	}
	if !strings.Contains(rec.Header().Get("Location"), "err=") {
		t.Errorf("guest-pay draft: Location %q missing err flash", rec.Header().Get("Location"))
	}
}

// TestApartmentUpdateSignatureFeeLetter (brief 1702d1): the tail of
// apartment_update (admin.py 2544-2601). Expected values are written by hand
// from the Python code: the signature goes to the property's own operator
// only, a refused signature keeps the saved row, a fee page gets the save
// back, and police-letter values without a typed password are not tested.
func TestApartmentUpdateSignatureFeeLetter(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	mux := http.NewServeMux()
	RegisterApartmentUpdate(mux, noWrap, pool, apartmentUpdateGetenv, testClock)
	ctx := context.Background()
	post := func(extra map[string]string, drop ...string) (int, string) {
		t.Helper()
		form := map[string]string{}
		for k, v := range g.Cases[3].Form {
			form[k] = v
		}
		for k, v := range extra {
			form[k] = v
		}
		for _, k := range drop {
			delete(form, k)
		}
		rec := apartmentFormPost(t, mux, "/apartments/201", g.CSRFNonce, 2, 0, "en", true, form)
		return rec.Code, rec.Header().Get("Location")
	}
	signature := func(id int64) (string, string) {
		t.Helper()
		var name, enc string
		if err := pool.QueryRow(ctx, `SELECT COALESCE(signature_name, ''), COALESCE(signature_png_enc, '') FROM legal_entity WHERE id = $1`, id).Scan(&name, &enc); err != nil {
			t.Fatal(err)
		}
		return name, enc
	}
	saved := "/apartments/201?view=settings&section=police&saved=1&msg=Saved.%20This%20property%20is%20ready%20to%20report.&toast_kind=success"

	// 0209: the name and a drawn PNG go to operator 21, encrypted at rest.
	png := "data:image/png;base64," + base64.StdEncoding.EncodeToString([]byte("\x89PNG\r\n\x1a\nsig"))
	code, loc := post(map[string]string{"fee_signature_section": "1", "signature_name": "  A. Host  ", "signature_drawn": png})
	if code != http.StatusSeeOther || loc != saved {
		t.Errorf("signature: %d %q, want 303 %q", code, loc, saved)
	}
	if name, enc := signature(21); name != "A. Host" || enc == "" || strings.Contains(enc, "PNG") {
		t.Errorf("signature of 21: name %q, enc %q", name, enc)
	}
	// Without fee_signature_section the signature fields are ignored.
	if _, loc = post(map[string]string{"signature_name": "Other"}); loc != saved {
		t.Errorf("no section: %q", loc)
	}
	if name, _ := signature(21); name != "A. Host" {
		t.Errorf("no section: the signature name became %q", name)
	}
	// A drawn value that is not a PNG or JPEG: the row is already saved, the
	// signature is not, and the host lands on the stay-fee settings.
	if _, err := pool.Exec(ctx, `UPDATE apartment SET internal_name = 'Before' WHERE id = 201`); err != nil {
		t.Fatal(err)
	}
	code, loc = post(map[string]string{"fee_signature_section": "1", "signature_name": "Bad", "signature_drawn": "data:text/plain;base64,QQ=="})
	want := "/apartments/201?view=settings&section=reporting&err=The%20signature%20must%20be%20a%20PNG%20or%20JPEG%20image%20up%20to%20300%20KB.#stay-fee-settings"
	if code != http.StatusSeeOther || loc != want {
		t.Errorf("bad signature: %d %q, want 303 %q", code, loc, want)
	}
	var internal string
	if err := pool.QueryRow(ctx, `SELECT internal_name FROM apartment WHERE id = 201`).Scan(&internal); err != nil || internal == "Before" {
		t.Errorf("bad signature: the property was not saved (%q, %v)", internal, err)
	}
	if name, _ := signature(21); name != "A. Host" {
		t.Errorf("bad signature: the name became %q", name)
	}
	// access.entity: another workspace's operator is never written.
	if _, err := pool.Exec(ctx, `UPDATE apartment SET legal_entity_id = 31 WHERE id = 201`); err != nil {
		t.Fatal(err)
	}
	post(map[string]string{"fee_signature_section": "1", "signature_name": "Intruder"}, "legal_entity_id")
	var operator int64
	if err := pool.QueryRow(ctx, `SELECT COALESCE(legal_entity_id, 0) FROM apartment WHERE id = 201`).Scan(&operator); err != nil || operator != 31 {
		t.Fatalf("other operator: legal_entity_id %d (%v), want 31 kept for the check", operator, err)
	}
	if name, _ := signature(31); name != "" {
		t.Errorf("other operator: entity 31 got the name %q", name)
	}
	if _, err := pool.Exec(ctx, `UPDATE apartment SET legal_entity_id = 21 WHERE id = 201`); err != nil {
		t.Fatal(err)
	}

	// fee_return_after_save: back to the fee page with "Saved.", no toast.
	for raw, want := range map[string]string{
		"/stay-fees?month=2026-10":     "/stay-fees?month=2026-10&msg=Saved.",
		"/stay-fees/201?month=2026-10": "/stay-fees/201?month=2026-10&msg=Saved.",
		"/stay-fees/202?month=2026-10": saved,
		"https://evil.example/x":       saved,
		"/apartments":                  saved,
	} {
		if code, loc := post(map[string]string{"fee_return_to": raw}); code != http.StatusSeeOther || loc != want {
			t.Errorf("fee_return_to %q: %d %q, want %q", raw, code, loc, want)
		}
	}

	// 1085: letter values saved without a typed password: not tested, #ubyport.
	untested := "/apartments/201?view=settings&section=police&saved=1&msg=Saved.%20Not%20tested%20yet%2C%20because%20no%20password%20was%20typed.%20Type%20it%20and%20test%20the%20connection.#ubyport"
	for letter, want := range map[string]string{" uby_mark ,x": untested, "uby_ws_user": untested, "uby_name, x": saved, ",": saved} {
		if code, loc := post(map[string]string{"letter_fields": letter, "uby_ws_password": ""}); code != http.StatusSeeOther || loc != want {
			t.Errorf("letter_fields %q: %d %q, want %q", letter, code, loc, want)
		}
	}
	// A letter-page fee return wins over the letter message (Python order).
	if _, loc := post(map[string]string{"letter_fields": "uby_mark", "uby_ws_password": "", "fee_return_to": "/stay-fees"}); loc != "/stay-fees?msg=Saved." {
		t.Errorf("letter with fee return: %q", loc)
	}
}

// TestApartmentUpdateFeeReturn: stay_fees.fee_return_after_save, by hand.
func TestApartmentUpdateFeeReturn(t *testing.T) {
	active, off := &detailApt{ID: 7, StayFeeRateCZK: 30}, &detailApt{ID: 7}
	for _, c := range []struct {
		a         *detailApt
		raw, want string
	}{
		{active, "", ""},
		{active, "/stay-fees/7?month=2026-10", "/stay-fees/7?month=2026-10"},
		{active, "/stay-fees/8", ""},
		{active, "//evil.example/stay-fees", ""},
		{off, "/stay-fees?month=2026-10", "/stay-fees?month=2026-10"},
		{off, "/stay-fees/7?month=2026-10", "/stay-fees?month=2026-10"},
		{off, "/stay-fees/7?month=2026-10&month=", "/stay-fees?month=2026-10"},
		{off, "/stay-fees/7?month=2026-13", "/stay-fees"},
		{off, "/stay-fees/7?month=1999-12", "/stay-fees"},
		{off, "/stay-fees/7", "/stay-fees"},
	} {
		if got := apartmentFeeReturn(c.a, c.raw); got != c.want {
			t.Errorf("apartmentFeeReturn(rate %d, %q) = %q, want %q", c.a.StayFeeRateCZK, c.raw, got, c.want)
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
