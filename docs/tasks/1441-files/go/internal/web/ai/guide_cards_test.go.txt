package ai

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

func TestGuideCardPageRenders(t *testing.T) {
	w := newGuideCardWorld(t)
	rec := guideTestDo(t, w.mux, "GET", w.path("/", intString(w.checkin)), w.host, nil)
	if rec.Code != 200 {
		t.Fatalf("status %d: %s", rec.Code, rec.Body.String())
	}
	body := rec.Body.String()
	for _, want := range []string{
		"<title>Check-in and arrival · Guest guide · UbyHost", `name="then" value="next"`, `action="/apartments/` + itoa64(w.apt) + `/guide/` + itoa64(w.checkin) + `"`,
		`id="card-photos"`, `name="visibility"`, `<option value="everyone" selected>`, `action="/apartments/` + itoa64(w.apt) + `/guide/` + itoa64(w.checkin) + `/skip"`,
		`enctype="multipart/form-data"`, `name="_csrf"`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("page lacks %q", want)
		}
	}
	if strings.Contains(body, `/delete"`) || strings.Contains(body, "/discard") {
		t.Error("a built-in card that is not a draft shows delete or discard")
	}
	if got := rec.Header().Get("Cache-Control"); got != "no-store" {
		t.Errorf("Cache-Control = %q", got)
	}
}

func TestGuideCardAccessRules(t *testing.T) {
	w := newGuideCardWorld(t)
	foreignCard := w.s
	_ = foreignCard
	rows, _ := w.s.items(context.Background(), w.otherApt)
	theirs := rows[0].ID
	cases := []struct {
		name, method, path string
		uid                int64
		want               int
	}{
		{"signed out goes to login", "GET", w.path("/", intString(w.checkin)), 0, 303},
		{"foreign property", "GET", "/apartments/" + itoa64(w.otherApt) + "/guide/" + itoa64(theirs), w.host, 404},
		{"another property's card on my property", "GET", w.path("/", intString(theirs)), w.host, 404},
		{"missing card", "GET", w.path("/999999"), w.host, 404},
		{"id is not an int", "GET", w.path("/abc"), w.host, 422},
		{"foreign save", "POST", "/apartments/" + itoa64(w.otherApt) + "/guide/" + itoa64(theirs), w.host, 404},
		{"foreign add", "POST", "/apartments/" + itoa64(w.otherApt) + "/guide/cards", w.host, 404},
		{"unknown action is the router's 404", "POST", w.path("/", intString(w.checkin), "/explode"), w.host, 404},
		{"skip of another property's card", "POST", w.path("/", intString(theirs), "/skip"), w.host, 404},
		{"HEAD is not allowed", "HEAD", w.path("/", intString(w.checkin)), w.host, 405},
	}
	for _, c := range cases {
		rec := guideTestDo(t, w.mux, c.method, c.path, c.uid, url.Values{})
		if rec.Code != c.want {
			t.Errorf("%s: status %d, want %d", c.name, rec.Code, c.want)
		}
	}
	if rec := guideTestDo(t, w.mux, "GET", w.path("/", intString(w.checkin)), w.stranger, nil); rec.Code != 404 {
		t.Errorf("another account reading my card: %d", rec.Code)
	}
	// An archived property is a 404 too.
	guideTestExec(t, w.s.pool, `UPDATE apartment SET archived_at = '2026-02-01T00:00:00+00:00' WHERE id = $1`, w.apt)
	if rec := guideTestDo(t, w.mux, "GET", w.path("/", intString(w.checkin)), w.host, nil); rec.Code != 404 {
		t.Errorf("archived property: %d", rec.Code)
	}
}

func TestGuideCardSaveFlow(t *testing.T) {
	w := newGuideCardWorld(t)
	form := url.Values{"location": {"Key box"}, "steps": {"Code 1234"}, "visibility": {"booked"}, "then": {"next"}}
	rec := guideTestDo(t, w.mux, "POST", w.path("/", intString(w.checkin)), w.host, form)
	if rec.Code != 303 {
		t.Fatalf("save: %d %s", rec.Code, rec.Body.String())
	}
	next, _ := w.s.nextOpen(context.Background(), w.apt, w.checkin)
	if want := w.path("/", intString(next)); !strings.HasPrefix(location(rec), want+"?msg=") {
		t.Errorf("Location = %q, want prefix %q", location(rec), want+"?msg=")
	}
	item, _ := w.s.getItem(context.Background(), w.apt, w.checkin)
	if item.State != "done" || item.Visibility != "booked" || item.Steps != "Code 1234" || item.Source != "host" {
		t.Errorf("item after save = %+v", item)
	}
	// plain save returns to the list
	rec = guideTestDo(t, w.mux, "POST", w.path("/", intString(w.wifi)), w.host, url.Values{"steps": {"Password on the fridge"}})
	if !strings.HasPrefix(location(rec), w.path()+"?msg=") {
		t.Errorf("Location = %q", location(rec))
	}
	if it, _ := w.s.getItem(context.Background(), w.apt, w.wifi); it.Visibility != "everyone" {
		t.Errorf("a save without a visibility field changed it to %q", it.Visibility)
	}
	// a rejected save shows the form again with 422 and what was typed
	rec = guideTestDo(t, w.mux, "POST", w.path("/", intString(w.wifi)), w.host, url.Values{"steps": {"typed text"}, "video_url": {"http://x.example"}})
	if rec.Code != 422 {
		t.Fatalf("rejected save: %d", rec.Code)
	}
	if body := rec.Body.String(); !strings.Contains(body, "typed text") || !strings.Contains(body, "ui-banner-attention") {
		t.Error("rejected save does not show the typed text and an attention banner")
	}
	// from the Leon wizard
	rec = guideTestDo(t, w.mux, "POST", w.path("/", intString(w.wifi)), w.host, url.Values{"steps": {"x"}, "from": {"leon"}, "then": {"next"}})
	if loc := location(rec); !strings.Contains(loc, "?from=leon") || strings.Contains(loc, "msg=") {
		t.Errorf("leon save Location = %q", loc)
	}
	rec = guideTestDo(t, w.mux, "POST", w.path("/", intString(w.wifi)), w.host, url.Values{"steps": {"x"}, "from": {"leon"}})
	if loc := location(rec); loc != "/apartments/"+itoa64(w.apt)+"/leon/setup/cards" {
		t.Errorf("leon save without next Location = %q", loc)
	}
	// a signed-in POST without a CSRF token is stopped by the gate before anything is read or written
	for _, tok := range []string{"", "not-a-token"} {
		form := url.Values{"steps": {"hacked"}, "_csrf": {tok}}
		req := httptest.NewRequest("POST", w.path("/", intString(w.wifi)), strings.NewReader(form.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: guideTestCSRFCookie})
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(guideTestSecret, map[string]any{"uid": w.host, "sv": int64(1), "iat": guideTestNow.Unix()}, guideTestNow)})
		rec2 := httptest.NewRecorder()
		w.mux.ServeHTTP(rec2, req)
		if rec2.Code != 303 || strings.HasPrefix(location(rec2), w.path()) {
			t.Errorf("token %q: %d %q", tok, rec2.Code, location(rec2))
		}
		if it, _ := w.s.getItem(context.Background(), w.apt, w.wifi); it.Steps == "hacked" {
			t.Errorf("token %q: a POST without CSRF changed data", tok)
		}
	}
}

func TestGuideCardAddSkipDiscardDelete(t *testing.T) {
	w := newGuideCardWorld(t)
	ctx := context.Background()
	// add
	rec := guideTestDo(t, w.mux, "POST", w.path("/cards"), w.host, url.Values{"topic": {"area"}, "title": {"Bakery"}})
	var custom int64
	if err := w.s.pool.QueryRow(ctx, `SELECT id FROM guide_item WHERE apartment_id = $1 AND kind = 'custom'`, w.apt).Scan(&custom); err != nil {
		t.Fatal(err)
	}
	if location(rec) != w.path("/", intString(custom)) {
		t.Errorf("add Location = %q", location(rec))
	}
	rec = guideTestDo(t, w.mux, "POST", w.path("/cards"), w.host, url.Values{"topic": {"area"}, "title": {" "}})
	if loc := location(rec); !strings.HasPrefix(loc, w.path()+"?err=") {
		t.Errorf("add without a title Location = %q", loc)
	}
	// skip and bring back
	rec = guideTestDo(t, w.mux, "POST", w.path("/", intString(custom), "/skip"), w.host, url.Values{"skip": {"1"}})
	if location(rec) != w.path() {
		t.Errorf("skip Location = %q", location(rec))
	}
	if it, _ := w.s.getItem(ctx, w.apt, custom); it.State != "skipped" {
		t.Errorf("state after skip = %q", it.State)
	}
	guideTestDo(t, w.mux, "POST", w.path("/", intString(custom), "/skip"), w.host, url.Values{"skip": {"0"}})
	if it, _ := w.s.getItem(ctx, w.apt, custom); it.State != "missing" {
		t.Errorf("state after unskip = %q", it.State)
	}
	// discard: only a draft
	if rec := guideTestDo(t, w.mux, "POST", w.path("/", intString(custom), "/discard"), w.host, nil); rec.Code != 404 {
		t.Errorf("discard of a non-draft: %d", rec.Code)
	}
	guideTestExec(t, w.s.pool, `UPDATE guide_item SET steps = 'Imported', state = 'check', source = 'airbnb' WHERE id = $1`, custom)
	page := guideTestDo(t, w.mux, "GET", w.path("/", intString(custom)), w.host, nil).Body.String()
	if !strings.Contains(page, "/discard") || !strings.Contains(page, "/delete") {
		t.Error("a custom draft card shows no discard and delete forms")
	}
	rec = guideTestDo(t, w.mux, "POST", w.path("/", intString(custom), "/discard"), w.host, nil)
	if !strings.HasPrefix(location(rec), w.path("/", intString(custom))+"?msg=") {
		t.Errorf("discard Location = %q", location(rec))
	}
	// delete: a built-in card is refused, a custom card goes with its photo rows and files
	if rec := guideTestDo(t, w.mux, "POST", w.path("/", intString(w.checkin), "/delete"), w.host, nil); rec.Code != 404 {
		t.Errorf("delete of a built-in card: %d", rec.Code)
	}
	dir := filepath.Join(w.dataDir, "guide_photos")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "p1.jpg"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	guideTestExec(t, w.s.pool, `INSERT INTO guide_photo (item_id, file_name, sort_order, created_at) VALUES ($1, 'p1.jpg', 1, 'x')`, custom)
	rec = guideTestDo(t, w.mux, "POST", w.path("/", intString(custom), "/delete"), w.host, nil)
	if !strings.HasPrefix(location(rec), w.path()+"?msg=") {
		t.Errorf("delete Location = %q", location(rec))
	}
	if n := guideTestCount(t, w.s.pool, `SELECT COUNT(*) FROM guide_item WHERE id = $1`, custom); n != 0 {
		t.Error("the custom card is still there")
	}
	if n := guideTestCount(t, w.s.pool, `SELECT COUNT(*) FROM guide_photo`); n != 0 {
		t.Error("the photo row is still there")
	}
	if _, err := os.Stat(filepath.Join(dir, "p1.jpg")); !os.IsNotExist(err) {
		t.Errorf("the photo file is still there: %v", err)
	}
}
