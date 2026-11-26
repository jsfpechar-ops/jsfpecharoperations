package properties

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

func TestApartmentUpdatePoliceUnderscoreMatch(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	env := adEnv(map[string]string{"UBYHOST_SECRET_KEY": apartmentCreateSecret})
	mux := http.NewServeMux()
	RegisterApartmentDetail(mux, noWrap, pool, env, testClock)
	RegisterApartmentUpdate(mux, noWrap, pool, env, testClock)

	// GET page has no letter-paste UI and keeps "where to find" collapsed.
	req := httptest.NewRequest(http.MethodGet, "/apartments/130201", nil)
	req.Header.Set("Accept", "text/html")
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "cs"})
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(apartmentCreateSecret, map[string]any{"uid": int64(130001), "sv": 1}, testNow)})
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	body := rec.Body.String()
	adCheck(t, "no paste UI", body, []string{
		`<details class="police-letter-find">`,
		`data-mark-mismatch="Zkratka musí odpovídat části za UBY-WS_ v přihlašovacím jménu."`,
	}, []string{
		`police-letter-paste`,
		`police-letter-form`,
		`data-letter-paste`,
		`<details class="police-letter-find" open>`,
	})

	post := func(lang string, vals map[string]string) (int, string, string) {
		t.Helper()
		form := map[string]string{
			"internal_name":   "Loft",
			"legal_entity_id": "130101",
			"uby_ws_user":     "UBY-WS_MLJNO",
			"uby_mark":        "MLJNO",
		}
		for k, v := range vals {
			form[k] = v
		}
		rec := apartmentFormPost(t, mux, "/apartments/130201", "test-nonce", 130001, 0, lang, true, form)
		return rec.Code, rec.Header().Get("Location"), rec.Body.String()
	}

	// Mismatched uby_mark is refused with 400 and inline Czech error; DB untouched.
	code, _, resp := post("cs", map[string]string{"uby_ws_user": "UBY-WS_MLJNO", "uby_mark": "WRONG"})
	if code != http.StatusBadRequest {
		t.Fatalf("mismatch status = %d, want 400", code)
	}
	adCheck(t, "mismatch error", resp, []string{
		`id="uby_mark-error"`,
		`Zkratka musí odpovídat části za UBY-WS_ v přihlašovacím jménu.`,
		`<details class="prop-sec" id="sec-police" open>`,
	}, nil)
	var savedMark string
	if err := pool.QueryRow(t.Context(), `SELECT uby_mark FROM apartment WHERE id = $1`, adLoft).Scan(&savedMark); err != nil {
		t.Fatal(err)
	}
	if savedMark != "AAKLI" {
		t.Fatalf("DB uby_mark changed on refusal: got %q, want AAKLI", savedMark)
	}

	// Blank uby_mark auto-fills from UBY-WS_ suffix and saves.
	code, _, _ = post("cs", map[string]string{"uby_ws_user": "UBY-WS_MLJNO", "uby_mark": ""})
	if code != http.StatusSeeOther {
		t.Fatalf("blank mark auto-fill status = %d, want 303", code)
	}
	if err := pool.QueryRow(t.Context(), `SELECT uby_mark FROM apartment WHERE id = $1`, adLoft).Scan(&savedMark); err != nil {
		t.Fatal(err)
	}
	if savedMark != "MLJNO" {
		t.Fatalf("DB uby_mark after auto-fill = %q, want MLJNO", savedMark)
	}

	// Matching lowercase uby_mark succeeds and uppercases.
	code, _, _ = post("en", map[string]string{"uby_ws_user": "UBY-WS_ZZTOP", "uby_mark": "zztop"})
	if code != http.StatusSeeOther {
		t.Fatalf("matching lowercase status = %d, want 303", code)
	}
	if err := pool.QueryRow(t.Context(), `SELECT uby_mark FROM apartment WHERE id = $1`, adLoft).Scan(&savedMark); err != nil {
		t.Fatal(err)
	}
	if savedMark != "ZZTOP" {
		t.Fatalf("DB uby_mark after match = %q, want ZZTOP", savedMark)
	}
}
