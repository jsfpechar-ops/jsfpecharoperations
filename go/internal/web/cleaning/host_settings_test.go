package cleaning

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// TestHostPropertySettingsPage mirrors routes/cleaning.property_settings and
// _settings (lines 250-279).
func TestHostPropertySettingsPage(t *testing.T) {
	e := newHostEnv(t)
	// 11 Alfa: manual code 4711, hours 10:00 and 15:00, instructions with markup.
	rec := e.get(i64(1), "/cleaning/properties/11", "")
	if rec.Code != 200 {
		t.Fatalf("status %d: %.300s", rec.Code, rec.Body.String())
	}
	mustPrivate(t, "settings", rec)
	body := rec.Body.String()
	mustContain(t, "alfa", body,
		`<title>Alfa · Cleaning</title>`, `<h1 class="airbnb-title">Alfa</h1>`, `action="/cleaning/properties/11"`,
		`Vyměnit ručníky &amp; &lt;povlečení&gt;</textarea>`, `Checkout: <strong>10:00</strong>`, `Next check-in: <strong>15:00</strong>`,
		`<strong class="cleaning-pin" translate="no">4711</strong>`, `action="/cleaning/properties/11/code/manual"`,
		`action="/cleaning/properties/11/code/ttlock"`, `action="/cleaning/properties/11/code/remove"`,
		`href="/apartments/11?view=settings&amp;section=property#arrival-departure"`)
	mustLack(t, "alfa", body, `success-notice`, `cleaning-warning`, `data-confirm-message="A different manual code`)
	// 12 Beta: a TTLock code (shown with the keypad #), a pending one, no hours.
	body = e.get(i64(1), "/cleaning/properties/12", "notice=saved").Body.String()
	mustContain(t, "beta", body, `translate="no">9090#</strong>`, `TTLock code is being prepared.`, `Checkout: <strong>—</strong>`,
		`data-success-notice`, `data-confirm-message="A different manual code replaces`, `Saved.`)
	// 14 Delta: no code at all, so no remove panel.
	body = e.get(i64(1), "/cleaning/properties/14", "").Body.String()
	mustLack(t, "delta", body, `cleaning-pin`, `code/remove`, `cleaning-warning`)
	// Another owner's property shows its failed revocation.
	body = e.get(i64(2), "/cleaning/properties/21", "").Body.String()
	mustContain(t, "owner 2", body, `A previous TTLock code could not be revoked.`)
	for _, c := range []struct {
		name, path string
		user       *int64
		status     int
	}{
		{"foreign", "/cleaning/properties/21", i64(1), 404},
		{"archived", "/cleaning/properties/13", i64(1), 404},
		{"missing", "/cleaning/properties/999", i64(1), 404},
		{"text id", "/cleaning/properties/abc", i64(1), 422},
		{"signed out", "/cleaning/properties/11", nil, 303},
	} {
		if got := e.get(c.user, c.path, "").Code; got != c.status {
			t.Errorf("%s: status %d, want %d", c.name, got, c.status)
		}
	}
}

// TestHostSaveProperty mirrors routes/cleaning.save_property (lines 282-294)
// and cleaning.save_settings.
func TestHostSaveProperty(t *testing.T) {
	e := newHostEnv(t)
	instructions := func(id int64) (string, bool) {
		var s string
		err := e.pool.QueryRow(context.Background(), `SELECT instructions FROM cleaning_property WHERE apartment_id = $1`, id).Scan(&s)
		return s, err == nil
	}
	rec := e.post(i64(1), "/cleaning/properties/11", map[string]string{"instructions": "  Neue Anweisung \n"})
	if rec.Code != 303 || rec.Header().Get("Location") != "/cleaning/properties/11?notice=saved" {
		t.Fatalf("save: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	mustPrivate(t, "save", rec)
	if got, _ := instructions(11); got != "Neue Anweisung" {
		t.Errorf("instructions = %q", got)
	}
	// 14 has no cleaning_property row yet: it is created.
	if _, ok := instructions(14); ok {
		t.Fatal("seed changed: 14 has a row")
	}
	e.post(i64(1), "/cleaning/properties/14", map[string]string{"instructions": "Novy"})
	if got, ok := instructions(14); !ok || got != "Novy" {
		t.Errorf("14 = %q %v", got, ok)
	}
	// Too long: 422 with the typed text and the error, nothing stored.
	long := strings.Repeat("ž", 10001)
	rec = e.post(i64(1), "/cleaning/properties/11", map[string]string{"instructions": long})
	if rec.Code != 422 {
		t.Fatalf("long: %d", rec.Code)
	}
	mustContain(t, "long", rec.Body.String(), `<p class="cleaning-warning" role="alert">The instructions are too long.</p>`, long+`</textarea>`)
	if got, _ := instructions(11); got != "Neue Anweisung" {
		t.Errorf("a failed save changed the text to %q", got[:10])
	}
	// Exactly 10000 characters pass (counted in characters, not bytes).
	if rec = e.post(i64(1), "/cleaning/properties/11", map[string]string{"instructions": strings.Repeat("ž", 10000)}); rec.Code != 303 {
		t.Errorf("10000 characters: %d", rec.Code)
	}
	for _, c := range []struct {
		name, path string
		user       *int64
		status     int
	}{
		{"foreign", "/cleaning/properties/21", i64(1), 404},
		{"archived", "/cleaning/properties/13", i64(1), 404},
		{"text id", "/cleaning/properties/abc", i64(1), 422},
		{"signed out", "/cleaning/properties/11", nil, 303},
	} {
		if got := e.post(c.user, c.path, map[string]string{"instructions": "x"}).Code; got != c.status {
			t.Errorf("%s: status %d, want %d", c.name, got, c.status)
		}
	}
	if got, _ := instructions(21); got != "Cizí pokyny" {
		t.Errorf("a foreign property changed to %q", got)
	}
	rec = e.call(goldenCase{Method: http.MethodPost, Path: "/cleaning/properties/11", User: i64(1), Form: map[string]string{"instructions": "x"}})
	if rec.Code != 303 {
		t.Errorf("no CSRF: %d", rec.Code)
	}
	if got, _ := instructions(11); strings.HasPrefix(got, "x") {
		t.Error("a post without a CSRF token was saved")
	}
}

var shareLinkRE = regexp.MustCompile(`href="http://127\.0\.0\.1:8080/cleaning/shared/([A-Za-z0-9_-]{43})"`)

// TestHostShares mirrors routes/cleaning.share_settings and create_share
// (lines 318-351) and cleaning.new_share.
func TestHostShares(t *testing.T) {
	e := newHostEnv(t)
	e.mux.Handle("GET /cleaning/shared/{token}/schedule", SharedScheduleHandler(e.pool, goldenEnv(e.g), func() time.Time { return goldenNow }))
	rec := e.get(i64(1), "/cleaning/shares", "")
	if rec.Code != 200 {
		t.Fatalf("status %d: %.300s", rec.Code, rec.Body.String())
	}
	mustPrivate(t, "shares", rec)
	body := rec.Body.String()
	// Live shares of owner 1, newest first: 5 and 1 (2 revoked, 3 expired, 4 is owner 2's).
	i5, i1 := strings.Index(body, `action="/cleaning/shares/5/revoke"`), strings.Index(body, `action="/cleaning/shares/1/revoke"`)
	if i5 < 0 || i1 < 0 || i5 > i1 {
		t.Errorf("share rows: 5 at %d, 1 at %d", i5, i1)
	}
	mustLack(t, "shares", body, `/cleaning/shares/2/revoke`, `/cleaning/shares/3/revoke`, `/cleaning/shares/4/revoke`, `Cizi`, `Gama`, `cleaning-share-url`)
	mustContain(t, "shares", body, `<title>Share schedule · UbyHost</title>`, `name="properties" value="11"`, `2099-01-01 01:00`)

	before := e.count(`SELECT COUNT(*) FROM cleaning_share`)
	rec = e.post(i64(1), "/cleaning/shares", map[string]string{"properties": "11"})
	if rec.Code != 200 {
		t.Fatalf("create: %d %.200s", rec.Code, rec.Body.String())
	}
	mustPrivate(t, "create", rec)
	m := shareLinkRE.FindStringSubmatch(rec.Body.String())
	if m == nil {
		t.Fatal("no share link in the page")
	}
	token := m[1]
	sum := sha256.Sum256([]byte(token))
	var id int64
	var expires, created string
	if err := e.pool.QueryRow(context.Background(), `SELECT id, expires_at, created_at FROM cleaning_share WHERE token_hash = $1 AND owner_user_id = 1 AND revoked_at IS NULL`,
		hex.EncodeToString(sum[:])).Scan(&id, &expires, &created); err != nil {
		t.Fatal(err)
	}
	if expires != "2026-06-09T10:00:00+00:00" || created != "2026-05-10T10:00:00+00:00" {
		t.Errorf("expires %q created %q", expires, created)
	}
	if e.count(`SELECT COUNT(*) FROM cleaning_share`) != before+1 || e.count(`SELECT COUNT(*) FROM cleaning_share_property WHERE share_id = $1 AND apartment_id = 11`, id) != 1 {
		t.Error("share rows are wrong")
	}
	// The token works on the cleaner's page (the existing Go handler).
	rec = httptest.NewRecorder()
	e.mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/cleaning/shared/"+token+"/schedule", nil))
	if rec.Code != 200 {
		t.Errorf("new link: %d", rec.Code)
	}
	// Bad ids create nothing.
	for _, c := range []struct {
		name  string
		props []string
	}{
		{"none", nil}, {"foreign", []string{"21"}}, {"archived", []string{"13"}}, {"text", []string{"abc"}},
		{"one foreign among own", []string{"11", "21"}}, {"empty value", []string{""}},
	} {
		n := e.count(`SELECT COUNT(*) FROM cleaning_share`)
		rec := e.postList(i64(1), "/cleaning/shares", c.props)
		if rec.Code != 422 || !strings.Contains(rec.Body.String(), `<p class="cleaning-warning" role="alert">Choose an available property.</p>`) {
			t.Errorf("%s: %d", c.name, rec.Code)
		}
		if e.count(`SELECT COUNT(*) FROM cleaning_share`) != n {
			t.Errorf("%s: a share was created", c.name)
		}
	}
	rec = e.postList(i64(1), "/cleaning/shares", []string{"11", "12", "11"})
	if rec.Code != 200 || shareLinkRE.FindStringSubmatch(rec.Body.String()) == nil {
		t.Fatalf("two properties: %d", rec.Code)
	}
	if got := e.count(`SELECT COUNT(*) FROM cleaning_share_property WHERE share_id = (SELECT MAX(id) FROM cleaning_share)`); got != 2 {
		t.Errorf("share_property rows = %d, want 2", got)
	}
	if got := e.post(nil, "/cleaning/shares", map[string]string{"properties": "11"}).Code; got != 303 {
		t.Errorf("signed out: %d", got)
	}
	if got := e.call(goldenCase{Method: http.MethodPost, Path: "/cleaning/shares", User: i64(1), Form: map[string]string{"properties": "11"}}).Code; got != 303 {
		t.Errorf("no CSRF: %d", got)
	}
}

// postList posts the "properties" field once per value, with a CSRF token.
func (e *hostEnv) postList(user *int64, path string, values []string) *httptest.ResponseRecorder {
	e.t.Helper()
	form := "_csrf=" + e.csrfToken()
	for _, v := range values {
		form += "&properties=" + v
	}
	req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(form))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if user != nil {
		req.AddCookie(sessionCookie(*user))
	}
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: e.g.CSRFNonce})
	rec := httptest.NewRecorder()
	e.mux.ServeHTTP(rec, req)
	return rec
}

// sessionCookie is the signed session cookie of a golden user.
func sessionCookie(user int64) *http.Cookie {
	return &http.Cookie{Name: session.CookieName,
		Value: session.Sign(goldenSecret, map[string]any{"uid": user, "sv": 1, "iat": goldenNow.Unix()}, goldenNow)}
}
