package properties

// Test of the police-letter connection test on save (brief 1702d2). The
// UbyPort answers come from a local httptest server named by
// UBYHOST_MOCK_URL; nothing reaches the network. Expected Locations and audit
// rows are written by hand from admin.py 2585-2600 and 3506-3549.

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/onboarding"
)

// apartmentLetterResponse is a UbyPort answer for one read-only method.
func apartmentLetterResponse(method, inner string) string {
	return `<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><` + method + `Response xmlns="http://UBY.pcr.cz/WS_UBY"><` +
		method + `Result>` + inner + `</` + method + `Result></` + method + `Response></s:Body></s:Envelope>`
}

// TestApartmentUpdateLetterTest: letter values saved with the password typed
// run the read-only test once: ok, a code list that fails after a passed
// test, a refused login, nothing listening; no password or no listed field
// sends nothing.
func TestApartmentUpdateLetterTest(t *testing.T) {
	g := loadApartmentUpdateGolden(t)
	pool := testPool(t)
	apartmentCreateSeed(t, pool, apartmentCreateGolden{Seed: g.Seed})
	ctx := context.Background()
	mode := "ok"
	var actions []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.ReadAll(r.Body)
		action := strings.TrimPrefix(r.Header.Get("SOAPAction"), "http://UBY.pcr.cz/WS_UBY/IWS_UBY/")
		actions = append(actions, action)
		switch {
		case mode == "auth":
			w.WriteHeader(http.StatusUnauthorized)
		case action == "TestDostupnosti":
			_, _ = io.WriteString(w, apartmentLetterResponse(action, "true"))
		case action == "MaximalniDelkaSeznamu":
			_, _ = io.WriteString(w, apartmentLetterResponse(action, "50"))
		case mode == "codelist":
			w.WriteHeader(http.StatusBadRequest)
		default:
			_, _ = io.WriteString(w, apartmentLetterResponse(action,
				`<a:CiselnikType xmlns:a="x"><a:Kod2>ERR_CZE_112</a:Kod2><a:Kod3>Chybné datum</a:Kod3><a:TextKratkyCZ>2</a:TextKratkyCZ></a:CiselnikType>`))
		}
	}))
	defer srv.Close()
	gone := httptest.NewServer(http.NotFoundHandler())
	goneURL := gone.URL
	gone.Close()
	post := func(mockURL string, extra map[string]string) string {
		t.Helper()
		getenv := func(k string) string {
			switch k {
			case "UBYHOST_UBYPORT_ENV":
				return "mock"
			case "UBYHOST_MOCK_URL":
				return mockURL
			}
			return apartmentUpdateGetenv(k)
		}
		mux := http.NewServeMux()
		RegisterApartmentUpdate(mux, noWrap, pool, getenv, testClock)
		form := map[string]string{}
		for k, v := range g.Cases[3].Form { // types uby_ws_password
			form[k] = v
		}
		for k, v := range extra {
			form[k] = v
		}
		rec := apartmentFormPost(t, mux, "/apartments/201", g.CSRFNonce, 2, 0, "en", true, form)
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("%v: %d, want 303", extra, rec.Code)
		}
		return rec.Header().Get("Location")
	}
	audits := func() []string {
		t.Helper()
		rows, err := pool.Query(ctx, `SELECT action || ' ' || detail FROM audit WHERE action LIKE 'ubyport_%' ORDER BY id`)
		if err != nil {
			t.Fatal(err)
		}
		defer rows.Close()
		var out []string
		for rows.Next() {
			var line string
			if err := rows.Scan(&line); err != nil {
				t.Fatal(err)
			}
			out = append(out, line)
		}
		return out
	}
	verified := func() string {
		t.Helper()
		var at string
		if err := pool.QueryRow(ctx, `SELECT COALESCE(ubyport_verified_at, '') FROM apartment WHERE id = 201`).Scan(&at); err != nil {
			t.Fatal(err)
		}
		return at
	}
	setVerified := func(v any) {
		t.Helper()
		if _, err := pool.Exec(ctx, `UPDATE apartment SET ubyport_verified_at = $1 WHERE id = 201`, v); err != nil {
			t.Fatal(err)
		}
	}
	letter := map[string]string{"letter_fields": "uby_idub, uby_mark"}
	base := "/apartments/201?view=settings&section=police&saved=1"
	okAudit := "ubyport_connection_ok apartment=201 endpoint=" + srv.URL + " available=True max_batch=50"

	// ok: three calls, the audit row, verified, tested, the error list stored.
	setVerified(nil)
	if loc, want := post(srv.URL, letter), base+"&msg=Saved.%20UbyPort%20accepted%20the%20login.%20The%20test%20files%20no%20report%2C%20so%20it%20does%20not%20prove%20filing%20works.#ubyport"; loc != want {
		t.Errorf("ok: %q, want %q", loc, want)
	}
	if want := []string{"TestDostupnosti", "MaximalniDelkaSeznamu", "DejMiCiselnik"}; !reflect.DeepEqual(actions, want) {
		t.Errorf("ok: actions %v", actions)
	}
	if got := audits(); !reflect.DeepEqual(got, []string{okAudit}) {
		t.Errorf("ok: audit %q", got)
	}
	if verified() == "" {
		t.Error("ok: ubyport_verified_at not set")
	}
	if st, err := onboarding.Load(ctx, onboarding.PoolSettings(pool), 201); err != nil || st == nil || !(st.Tested || st.Finished) {
		t.Errorf("ok: setup state %+v (%v), want tested", st, err)
	}
	var text string
	if err := pool.QueryRow(ctx, `SELECT text_cs || '|' || extra FROM codelist WHERE kind = 'chyby' AND code = 'ERR_CZE_112'`).Scan(&text); err != nil || text != "Chybné datum|2" {
		t.Errorf("ok: codelist %q (%v)", text, err)
	}

	// The code list fails after a passed test: still ok, one more audit row;
	// mark_verified only fills an empty time.
	setVerified("kept")
	mode, actions = "codelist", nil
	if loc := post(srv.URL, letter); !strings.Contains(loc, "&msg=Saved.%20UbyPort%20accepted") {
		t.Errorf("codelist failure: %q", loc)
	}
	if got := audits(); !reflect.DeepEqual(got, []string{okAudit, okAudit, "ubyport_codebook_refresh_failed apartment=201 error=UbyPort returned HTTP 400."}) {
		t.Errorf("codelist failure: audit %q", got)
	}
	if v := verified(); v != "kept" {
		t.Errorf("codelist failure: ubyport_verified_at %q, want kept", v)
	}

	// 401: the login was refused; one call, an error message, nothing verified.
	setVerified(nil)
	mode, actions = "auth", nil
	if loc, want := post(srv.URL, letter), base+"&err=Saved%2C%20but%20the%20police%20refused%20the%20login.%20Check%20the%20login%20and%20the%20password%2C%20then%20test%20again.#ubyport"; loc != want {
		t.Errorf("auth: %q, want %q", loc, want)
	}
	if !reflect.DeepEqual(actions, []string{"TestDostupnosti"}) {
		t.Errorf("auth: actions %v", actions)
	}
	if got := audits(); len(got) != 4 || !strings.HasPrefix(got[3], "ubyport_connection_failed apartment=201 endpoint="+srv.URL+" error=UbyPort rejected the credentials (HTTP 401).") {
		t.Errorf("auth: audit %q", got)
	}
	if v := verified(); v != "" {
		t.Errorf("auth: ubyport_verified_at %q", v)
	}

	// Nothing listens: unreachable.
	if loc, want := post(goneURL, letter), base+"&err=Saved.%20The%20police%20service%20could%20not%20be%20reached%20just%20now%2C%20so%20the%20login%20was%20not%20checked.%20Test%20again%20later.#ubyport"; loc != want {
		t.Errorf("unreachable: %q, want %q", loc, want)
	}
	if got := audits(); len(got) != 5 || !strings.HasPrefix(got[4], "ubyport_connection_failed apartment=201 endpoint="+goneURL+" error=Could not reach UbyPort at "+goneURL) {
		t.Errorf("unreachable: audit %q", got)
	}

	// Without a typed password, or with no listed field, nothing is sent.
	mode, actions = "ok", nil
	post(srv.URL, map[string]string{"letter_fields": "uby_mark", "uby_ws_password": ""})
	post(srv.URL, map[string]string{"letter_fields": "uby_name"})
	if len(actions) != 0 {
		t.Errorf("no password or no letter field: sent %v", actions)
	}
}
