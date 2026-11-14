package cleaning

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// csrfToken is the token goldenRequest puts in a form (same nonce and secret).
func (e *hostEnv) csrfToken() string {
	e.t.Helper()
	sum := sha256.Sum256([]byte(e.g.CSRFNonce))
	tok, err := secure.NewTimedSerializer(goldenSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, goldenNow)
	if err != nil {
		e.t.Fatal(err)
	}
	return tok
}

// post sends a url-encoded form with a valid CSRF token as user (nil: signed out).
func (e *hostEnv) post(user *int64, path string, form map[string]string, headers ...string) *httptest.ResponseRecorder {
	return e.call(goldenCase{Method: http.MethodPost, Path: path, User: user, Form: form, CSRF: true}, headers...)
}

// postMultipart sends FormData the way dashboard-calendar.js does: multipart
// body, the token in the x-csrf-token header, Accept: application/json.
func (e *hostEnv) postMultipart(user int64, path string, fields map[string]string) *httptest.ResponseRecorder {
	e.t.Helper()
	var body bytes.Buffer
	mw := multipart.NewWriter(&body)
	for k, v := range fields {
		if err := mw.WriteField(k, v); err != nil {
			e.t.Fatal(err)
		}
	}
	mw.Close()
	req := httptest.NewRequest(http.MethodPost, path, &body)
	req.Header.Set("Content-Type", mw.FormDataContentType())
	req.Header.Set("Accept", "application/json")
	req.Header.Set("x-csrf-token", e.csrfToken())
	req.AddCookie(&http.Cookie{Name: session.CookieName,
		Value: session.Sign(goldenSecret, map[string]any{"uid": user, "sv": 1, "iat": goldenNow.Unix()}, goldenNow)})
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: e.g.CSRFNonce})
	rec := httptest.NewRecorder()
	e.mux.ServeHTTP(rec, req)
	return rec
}

// notesOf decrypts a stored cleaning note with the golden data key.
func notesOf(t *testing.T, token *string) string {
	t.Helper()
	if token == nil {
		return ""
	}
	mf, err := secure.NewMultiFernet([]byte(goldenDataKey()))
	if err != nil {
		t.Fatal(err)
	}
	b, err := mf.Decrypt(*token, 0, goldenNow)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}

func (e *hostEnv) event(id int64) eventFull {
	e.t.Helper()
	ev, err := eventFor(context.Background(), e.pool, i64(1), id)
	if err != nil || ev == nil {
		// owner 2's event
		if ev, err = eventFor(context.Background(), e.pool, i64(2), id); err != nil || ev == nil {
			e.t.Fatalf("event %d: %v", id, err)
		}
	}
	return *ev
}

func (e *hostEnv) count(sql string, args ...any) int {
	e.t.Helper()
	var n int
	if err := e.pool.QueryRow(context.Background(), sql, args...).Scan(&n); err != nil {
		e.t.Fatal(err)
	}
	return n
}

func eventCount(e *hostEnv) int { return e.count(`SELECT COUNT(*) FROM cleaning_event`) }

// TestHostCreateEvent mirrors routes/cleaning.create_event (lines 176-201).
func TestHostCreateEvent(t *testing.T) {
	e := newHostEnv(t)
	before := eventCount(e)
	rec := e.post(i64(1), "/cleaning/events", map[string]string{"apartment_id": "11", "scheduled_date": "2026-06-01", "notes": "  New note  "})
	if rec.Code != 303 || rec.Header().Get("Location") != "/cleaning?notice=saved" {
		t.Fatalf("create: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	mustPrivate(t, "create", rec)
	if eventCount(e) != before+1 {
		t.Fatal("no row was added")
	}
	var id int64
	if err := e.pool.QueryRow(context.Background(), `SELECT MAX(id) FROM cleaning_event`).Scan(&id); err != nil {
		t.Fatal(err)
	}
	ev := e.event(id)
	if ev.ApartmentID != 11 || ev.Date != "2026-06-01" || ev.State != "scheduled" || ev.Revision != 1 || ev.Overridden != 1 ||
		ev.Source != nil || ev.Start != nil || ev.End != nil || notesOf(t, ev.NotesEnc) != "New note" {
		t.Errorf("row = %+v notes %q", ev, notesOf(t, ev.NotesEnc))
	}
	// No note: no ciphertext. Times posted together are kept.
	e.post(i64(1), "/cleaning/events", map[string]string{"apartment_id": "12", "scheduled_date": "2026-06-02", "start_time": "09:00", "end_time": "10:30"})
	_ = e.pool.QueryRow(context.Background(), `SELECT MAX(id) FROM cleaning_event`).Scan(&id)
	ev = e.event(id)
	if ev.NotesEnc != nil || str(ev.Start) != "09:00" || str(ev.End) != "10:30" {
		t.Errorf("second row = %+v", ev)
	}
}

// TestHostCreateEventJSON is what the calendar sends: multipart FormData with
// the token in a header and Accept: application/json.
func TestHostCreateEventJSON(t *testing.T) {
	e := newHostEnv(t)
	rec := e.postMultipart(1, "/cleaning/events", map[string]string{"apartment_id": "11", "scheduled_date": "2026-06-03", "notes": "Okno"})
	if rec.Code != 201 {
		t.Fatalf("status %d: %.200s", rec.Code, rec.Body.String())
	}
	mustPrivate(t, "json", rec)
	var id int64
	_ = e.pool.QueryRow(context.Background(), `SELECT MAX(id) FROM cleaning_event`).Scan(&id)
	want := `{"id":` + itoa(id) + `,"url":"/cleaning?cal_date=2026-06-03&property=11#cleaning-` + itoa(id) + `"}`
	if rec.Body.String() != want {
		t.Errorf("body %s, want %s", rec.Body.String(), want)
	}
	if notesOf(t, e.event(id).NotesEnc) != "Okno" {
		t.Error("multipart note not stored")
	}
	rec = e.postMultipart(1, "/cleaning/events", map[string]string{"apartment_id": "11", "scheduled_date": "2026-6-3"})
	if rec.Code != 422 || rec.Body.String() != `{"errors":{"scheduled_date":"Enter valid dates, no more than 370 days apart."}}` {
		t.Errorf("bad date: %d %s", rec.Code, rec.Body.String())
	}
}

func itoa(n int64) string { return strconv.FormatInt(n, 10) }

func TestHostCreateEventErrors(t *testing.T) {
	e := newHostEnv(t)
	before := eventCount(e)
	long := strings.Repeat("x", 5001)
	for _, c := range []struct {
		name  string
		form  map[string]string
		field string
		html  string
	}{
		{"bad date", map[string]string{"apartment_id": "11", "scheduled_date": "2026-6-1"}, "scheduled_date", "Enter valid dates"},
		{"year 1899", map[string]string{"apartment_id": "11", "scheduled_date": "1899-12-31"}, "scheduled_date", "Enter valid dates"},
		{"impossible date is property", map[string]string{"apartment_id": "11", "scheduled_date": "2026-02-30"}, "apartment_id", "Choose an available property."},
		{"one time", map[string]string{"apartment_id": "11", "scheduled_date": "2026-06-01", "start_time": "09:00"}, "scheduled_date", "Enter both times"},
		{"end before start", map[string]string{"apartment_id": "11", "scheduled_date": "2026-06-01", "start_time": "10:00", "end_time": "10:00"}, "scheduled_date", "Enter both times"},
		{"bad time", map[string]string{"apartment_id": "11", "scheduled_date": "2026-06-01", "start_time": "9:00", "end_time": "10:00"}, "scheduled_date", "Enter both times"},
		{"long notes", map[string]string{"apartment_id": "11", "scheduled_date": "2026-06-01", "notes": long}, "notes", "The instructions are too long."},
		{"text property", map[string]string{"apartment_id": "abc", "scheduled_date": "2026-06-01"}, "apartment_id", "Choose an available property."},
		{"empty property", map[string]string{"apartment_id": "", "scheduled_date": "2026-06-01"}, "apartment_id", "Choose an available property."},
	} {
		rec := e.post(i64(1), "/cleaning/events", c.form, "Accept", "application/json")
		if rec.Code != 422 || !strings.Contains(rec.Body.String(), `"errors":{"`+c.field+`":`) {
			t.Errorf("%s json: %d %s", c.name, rec.Code, rec.Body.String())
		}
		rec = e.post(i64(1), "/cleaning/events", c.form)
		if rec.Code != 422 || !strings.Contains(rec.Body.String(), `<p class="cleaning-warning" role="alert">`) {
			t.Errorf("%s html: %d", c.name, rec.Code)
		}
		mustPrivate(t, c.name, rec)
	}
	for _, c := range []struct {
		name string
		user *int64
		form map[string]string
		code int
	}{
		{"foreign property", i64(1), map[string]string{"apartment_id": "21", "scheduled_date": "2026-06-01"}, 404},
		{"archived property", i64(1), map[string]string{"apartment_id": "13", "scheduled_date": "2026-06-01"}, 404},
		{"missing property", i64(1), map[string]string{"scheduled_date": "2026-06-01"}, 404},
		{"signed out", nil, map[string]string{"apartment_id": "11", "scheduled_date": "2026-06-01"}, 303},
	} {
		if got := e.post(c.user, "/cleaning/events", c.form).Code; got != c.code {
			t.Errorf("%s: status %d, want %d", c.name, got, c.code)
		}
	}
	rec := e.call(goldenCase{Method: http.MethodPost, Path: "/cleaning/events", User: i64(1), Form: map[string]string{"apartment_id": "11", "scheduled_date": "2026-06-01"}})
	if rec.Code != 303 || !strings.HasPrefix(rec.Header().Get("Location"), "/login") && !strings.Contains(rec.Header().Get("Location"), "err=") {
		t.Errorf("no CSRF: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if eventCount(e) != before {
		t.Errorf("a failed request added %d rows", eventCount(e)-before)
	}
	// The typed values come back in the form.
	body := e.post(i64(1), "/cleaning/events", map[string]string{"apartment_id": "11", "scheduled_date": "2026-6-1", "notes": "Keep <me>"}).Body.String()
	mustContain(t, "values", body, `value="2026-6-1"`, `Keep &lt;me&gt;</textarea>`, `<option value="11" selected>Alfa</option>`)
}

// TestHostUpdateEvent mirrors routes/cleaning.update_event (lines 216-234).
func TestHostUpdateEvent(t *testing.T) {
	e := newHostEnv(t)
	// 507: by hand, revision 3. A new day makes it overridden.
	rec := e.post(i64(1), "/cleaning/events/507", map[string]string{"apartment_id": "12", "scheduled_date": "2026-05-14", "notes": "Neu", "revision": "3"})
	if rec.Code != 303 || rec.Header().Get("Location") != "/cleaning?notice=saved" {
		t.Fatalf("update: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	ev := e.event(507)
	if ev.ApartmentID != 12 || ev.Date != "2026-05-14" || ev.Revision != 4 || ev.Overridden != 1 || notesOf(t, ev.NotesEnc) != "Neu" || ev.Start != nil {
		t.Errorf("507 = %+v", ev)
	}
	// 501: from a booking. Same day keeps overridden 0; the old text stays when the field is empty? No: empty clears it.
	rec = e.post(i64(1), "/cleaning/events/501", map[string]string{"apartment_id": "11", "scheduled_date": "2026-05-10", "notes": "", "revision": "1"})
	ev = e.event(501)
	if rec.Code != 303 || ev.Overridden != 0 || ev.Revision != 2 || ev.NotesEnc != nil {
		t.Errorf("501 = %d %+v", rec.Code, ev)
	}
	// 502 holds a malformed legacy start; times not posted keep it byte for byte.
	// Opening the editor first lets reconcile move it to its booking's date (and bump the revision).
	e.get(i64(1), "/cleaning/events/502/edit", "")
	ev = e.event(502)
	rev := itoa(ev.Revision)
	rec = e.post(i64(1), "/cleaning/events/502", map[string]string{"scheduled_date": ev.Date, "notes": "n", "revision": rev})
	after := e.event(502)
	if rec.Code != 303 || str(after.Start) != "x9:00" || str(after.End) != "10:00" || after.ApartmentID != 11 || after.Revision != ev.Revision+1 {
		t.Errorf("502 = %d %+v", rec.Code, after)
	}
	// Times posted are validated and stored.
	rec = e.post(i64(1), "/cleaning/events/502", map[string]string{"scheduled_date": ev.Date, "start_time": "08:00", "end_time": "09:00", "revision": itoa(after.Revision)})
	ev = e.event(502)
	if rec.Code != 303 || str(ev.Start) != "08:00" || str(ev.End) != "09:00" {
		t.Errorf("502 times = %d %+v", rec.Code, ev)
	}
	// JSON answers.
	rec = e.postMultipart(1, "/cleaning/events/503", map[string]string{"apartment_id": "11", "scheduled_date": "2026-06-21", "revision": "1"})
	if rec.Code != 200 || rec.Body.String() != `{"ok":true}` {
		t.Errorf("json ok: %d %s", rec.Code, rec.Body.String())
	}
	mustPrivate(t, "json ok", rec)
}

func TestHostUpdateEventErrors(t *testing.T) {
	e := newHostEnv(t)
	base := func(extra map[string]string) map[string]string {
		m := map[string]string{"apartment_id": "11", "scheduled_date": "2026-05-14", "revision": "3"}
		for k, v := range extra {
			m[k] = v
		}
		return m
	}
	for _, c := range []struct {
		name   string
		id     string
		form   map[string]string
		status int
		key    string
	}{
		{"stale revision", "507", base(map[string]string{"revision": "2"}), 409, "changed"},
		{"missing revision", "507", map[string]string{"apartment_id": "11", "scheduled_date": "2026-05-14"}, 409, "changed"},
		{"text revision", "507", base(map[string]string{"revision": "x"}), 409, "changed"},
		{"impossible date", "507", base(map[string]string{"scheduled_date": "2026-02-30"}), 409, "changed"},
		{"text apartment", "507", base(map[string]string{"apartment_id": "abc"}), 409, "changed"},
		{"bad date", "507", base(map[string]string{"scheduled_date": "tomorrow"}), 422, "dates"},
		{"one time", "507", base(map[string]string{"end_time": "10:00"}), 422, "times"},
		{"long notes", "507", base(map[string]string{"notes": strings.Repeat("y", 5001)}), 422, "notes"},
		{"auto cleaning cannot move", "501", map[string]string{"apartment_id": "12", "scheduled_date": "2026-05-10", "revision": "1"}, 422, "property"},
	} {
		before := e.event(mustInt(c.id))
		rec := e.post(i64(1), "/cleaning/events/"+c.id, c.form, "Accept", "application/json")
		want := `{"error":"` + c.key + `"}`
		if rec.Code != c.status || rec.Body.String() != want {
			t.Errorf("%s json: %d %s, want %d %s", c.name, rec.Code, rec.Body.String(), c.status, want)
		}
		rec = e.post(i64(1), "/cleaning/events/"+c.id, c.form)
		if rec.Code != c.status || !strings.Contains(rec.Body.String(), `role="alert"`) {
			t.Errorf("%s html: %d", c.name, rec.Code)
		}
		if after := e.event(mustInt(c.id)); rowKey(after) != rowKey(before) {
			t.Errorf("%s: the row changed: %s -> %s", c.name, rowKey(before), rowKey(after))
		}
	}
	for _, c := range []struct {
		name, id string
		user     *int64
		form     map[string]string
		status   int
	}{
		{"foreign event", "509", i64(1), base(nil), 404},
		{"missing event", "9999", i64(1), base(nil), 404},
		{"text id", "abc", i64(1), base(nil), 422},
		{"foreign target property", "507", i64(1), base(map[string]string{"apartment_id": "21"}), 404},
		{"signed out", "507", nil, base(nil), 303},
	} {
		if got := e.post(c.user, "/cleaning/events/"+c.id, c.form).Code; got != c.status {
			t.Errorf("%s: status %d, want %d", c.name, got, c.status)
		}
	}
	// A dismissed cleaning cannot be saved again: 409.
	e.exec(`UPDATE cleaning_event SET state = 'dismissed' WHERE id = 507`)
	if got := e.post(i64(1), "/cleaning/events/507", base(nil)).Code; got != 409 {
		t.Errorf("dismissed: status %d, want 409", got)
	}
	// The editor of a 409 shows the stored revision for the delete form.
	e.exec(`UPDATE cleaning_event SET revision = 9 WHERE id = 503`)
	body := e.post(i64(1), "/cleaning/events/503", base(map[string]string{"revision": "1"})).Body.String()
	mustContain(t, "409 page", body, `name="revision" value="1"`, `action="/cleaning/events/503/delete"`)
}

func mustInt(s string) int64 { n, _ := pyInt(s); return n }

func rowKey(ev eventFull) string {
	return fmt.Sprintf("%d|%d|%d|%d|%s|%s|%s|%s|%s", ev.ID, ev.ApartmentID, ev.Overridden, ev.Revision, ev.Date, ev.State, str(ev.Start), str(ev.End), str(ev.NotesEnc))
}
