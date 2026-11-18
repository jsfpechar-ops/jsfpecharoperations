package properties

import (
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// Brief 1702: POST /apartments/{id}/door-codes, against the world of the 1701
// page tests (adWorld, adLockWorld). The expected Locations are written by
// hand from admin.py apartment_door_codes and the English and Czech catalogs.

const dcHere = "/apartments/130201?view=settings&section=lock#sec-lock"

func dcMux(pool *pgxpool.Pool, extra map[string]string) *http.ServeMux {
	mux := http.NewServeMux()
	RegisterApartmentDoorCodes(mux, noWrap, pool, adEnv(extra), testClock)
	return mux
}

// dcPost posts mode to path as user (0: signed out); csrf false leaves the token out.
func dcPost(t *testing.T, mux http.Handler, path, mode string, user int64, lang string, csrf bool) *httptest.ResponseRecorder {
	t.Helper()
	form := url.Values{"mode": {mode}, "return_to": {"/apartments/130201?view=settings&section=lock#sec-lock"}}
	const nonce = "door-codes-nonce"
	if csrf {
		sum := sha256.Sum256([]byte(nonce))
		token, err := secure.NewTimedSerializer(apartmentNewSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, testNow)
		if err != nil {
			t.Fatal(err)
		}
		form.Set("_csrf", token)
	}
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: nonce})
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	if user != 0 {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(apartmentNewSecret, map[string]any{"uid": user, "sv": 1}, testNow)})
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

// dcLock is the stored lock_provider and lock_id of a property.
func dcLock(t *testing.T, pool *pgxpool.Pool, id int64) string {
	t.Helper()
	var provider, lock string
	if err := pool.QueryRow(t.Context(), `SELECT COALESCE(lock_provider, '-'), COALESCE(lock_id, '-') FROM apartment WHERE id = $1`, id).Scan(&provider, &lock); err != nil {
		t.Fatal(err)
	}
	return provider + "/" + lock
}

// dcAudit is every audit row as "action detail owner actor".
func dcAudit(t *testing.T, pool *pgxpool.Pool) []string {
	t.Helper()
	rows, err := pool.Query(t.Context(), `SELECT action || ' ' || detail || ' ' || COALESCE(owner_user_id::text, '-') || ' ' || actor FROM audit ORDER BY id`)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var s string
		if err := rows.Scan(&s); err != nil {
			t.Fatal(err)
		}
		out = append(out, s)
	}
	return out
}

func dcExpect(t *testing.T, name string, rec *httptest.ResponseRecorder, location string) {
	t.Helper()
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != location {
		t.Errorf("%s: %d %q, want 303 %q", name, rec.Code, rec.Header().Get("Location"), location)
	}
}

// TestApartmentDoorCodes: Turn off, a mode that is neither, Turn on, and each
// refusal of the Turn on branch, with the rows and audit lines they leave.
func TestApartmentDoorCodes(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	env := adLockWorld(t, pool)
	mux := dcMux(pool, env)
	path := "/apartments/130201/door-codes"

	dcExpect(t, "off", dcPost(t, mux, path, " off ", 130001, "en", true), dcHere)
	if got := dcLock(t, pool, adLoft); got != "-/7001" {
		t.Errorf("off keeps the lock: %q", got)
	}
	dcExpect(t, "neither", dcPost(t, mux, path, "maybe", 130001, "en", true), dcHere)
	dcExpect(t, "on", dcPost(t, mux, path, "on", 130001, "en", true), dcHere)
	if got := dcLock(t, pool, adLoft); got != "ttlock/7001" {
		t.Errorf("on: %q", got)
	}
	if got, want := dcAudit(t, pool), []string{"door_codes_off apartment=130201 130001 props-host-a", "door_codes_on apartment=130201 130001 props-host-a"}; strings.Join(got, "|") != strings.Join(want, "|") {
		t.Errorf("audit: %q, want %q", got, want)
	}

	// a lock that serves another property, a lock the account does not list, no lock and no default
	mustExec(t, pool, `UPDATE apartment SET lock_provider = NULL, lock_id = '7002' WHERE id = $1`, adLoft)
	dcExpect(t, "taken", dcPost(t, mux, path, "on", 130001, "en", true),
		"/apartments/130201?view=settings&section=lock&err=This%20lock%20already%20sends%20codes%20for%20another%20property.%20A%20lock%20serves%20one%20property%3A%20choose%20another%20lock%2C%20or%20switch%20it%20off%20on%20the%20other%20property%20first.#sec-lock")
	mustExec(t, pool, `UPDATE apartment SET lock_id = '9999' WHERE id = $1`, adLoft)
	dcExpect(t, "unknown", dcPost(t, mux, path, "on", 130001, "en", true),
		"/apartments/130201?view=settings&section=lock&err=Choose%20a%20lock%20from%20the%20list.#sec-lock")
	dcExpect(t, "unknown cs", dcPost(t, mux, path, "on", 130001, "cs", true),
		"/apartments/130201?view=settings&section=lock&err=Vyberte%20z%C3%A1mek%20ze%20seznamu.#sec-lock")
	// no lock chosen: the one free lock (7001; 7002 is Plain's) is the default
	mustExec(t, pool, `UPDATE apartment SET lock_id = NULL, checkout_hour = NULL WHERE id = $1`, adLoft)
	dcExpect(t, "times", dcPost(t, mux, path, "on", 130001, "en", true),
		"/apartments/130201?view=settings&section=lock&err=Check-in%20and%20check-out%20times%20are%20missing%2C%20so%20door%20codes%20cannot%20work%20yet.%20Set%20them%20first.#sec-lock")
	if got := dcLock(t, pool, adLoft); got != "-/-" {
		t.Errorf("a refusal writes nothing: %q", got)
	}
	mustExec(t, pool, `UPDATE apartment SET checkout_hour = 10 WHERE id = $1`, adLoft)
	dcExpect(t, "default lock", dcPost(t, mux, path, "on", 130001, "en", true), dcHere)
	if got := dcLock(t, pool, adLoft); got != "ttlock/7001" {
		t.Errorf("default lock: %q", got)
	}
	// two free locks: no default
	mustExec(t, pool, `UPDATE apartment SET lock_provider = NULL, lock_id = NULL WHERE id IN ($1, $2)`, adLoft, adPlain)
	dcExpect(t, "no default", dcPost(t, mux, path, "on", 130001, "en", true),
		"/apartments/130201?view=settings&section=lock&err=Choose%20a%20lock%20from%20the%20list.#sec-lock")
	if n := len(dcAudit(t, pool)); n != 3 {
		t.Errorf("audit rows: %d, want 3", n)
	}
}

// TestApartmentDoorCodesAccess: the gate (CSRF, login, the path id), another
// host's property and door codes that are not offered all leave the rows alone.
func TestApartmentDoorCodesAccess(t *testing.T) {
	pool := testPool(t)
	adWorld(t, pool)
	env := adLockWorld(t, pool)
	mux := dcMux(pool, env)
	const refused = "/apartments?err=Smart%20locks%20are%20not%20switched%20on."
	if rec := dcPost(t, mux, "/apartments/130201/door-codes", "off", 130001, "en", false); rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?notice=form_expired" {
		t.Errorf("no csrf: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if rec := dcPost(t, mux, "/apartments/130201/door-codes", "off", 0, "en", true); rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/apartments/130201/door-codes" {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if rec := dcPost(t, mux, "/apartments/x/door-codes", "off", 130001, "en", true); rec.Code != http.StatusUnprocessableEntity {
		t.Errorf("bad id: %d", rec.Code)
	}
	dcExpect(t, "foreign", dcPost(t, mux, "/apartments/130204/door-codes", "off", 130001, "en", true), refused)
	dcExpect(t, "missing", dcPost(t, mux, "/apartments/999999/door-codes", "off", 130001, "en", true), refused)
	dcExpect(t, "switched off", dcPost(t, dcMux(pool, nil), "/apartments/130201/door-codes", "off", 130001, "en", true), refused)
	mustExec(t, pool, `INSERT INTO billing_account (owner_user_id, status, plan, addon_ttlock, updated_at) VALUES (130001, 'active', 'standard', 0, $1)`, stamp0)
	billed := map[string]string{"UBYHOST_BILLING_ENABLED": "1"}
	for k, v := range env {
		billed[k] = v
	}
	dcExpect(t, "no add-on", dcPost(t, dcMux(pool, billed), "/apartments/130201/door-codes", "off", 130001, "en", true), refused)
	if got := dcLock(t, pool, adLoft); got != "ttlock/7001" {
		t.Errorf("refused requests write nothing: %q", got)
	}
	if got := dcAudit(t, pool); len(got) != 0 {
		t.Errorf("audit: %q", got)
	}
}
