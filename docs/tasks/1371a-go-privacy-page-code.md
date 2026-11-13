# 1371a: code for brief 1371

Extracted by brief 1371 step 1 with a python3 command; never read, retype or edit by hand. Each block is the whole file.

## go/internal/web/privacy/handler.go

edit (full file): path id beyond int64 is no_such_dsr after the login check

````go path=go/internal/web/privacy/handler.go
package privacy

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the keys in i18n_keys.txt, generated from host_i18n.py.
// App/tests/test_go_privacy_requests.py fails when it is stale.
var catalog = hostweb.Load(catalogJSON)

// listPath is where both routes send the host back to.
const listPath = "/privacy-requests"

// dateOnly is the re.fullmatch the create route uses before it adds midnight UTC.
var dateOnly = regexp.MustCompile(`^[0-9]{4}-[0-9]{2}-[0-9]{2}$`)

// pathInt is what pydantic's lax int accepts from a path string once
// surrounding whitespace is gone: a sign, digit groups joined by single
// underscores, and an optional .0... tail.
var pathInt = regexp.MustCompile(`^[+-]?[0-9]+(?:_[0-9]+)*(?:\.0+)?$`)

func flash(lang, key string) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(lang, key, nil), Key: key}
}

func fail(w http.ResponseWriter, err error) {
	log.Printf("privacy request route failed: %v", err)
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusInternalServerError)
	_, _ = io.WriteString(w, "Internal Server Error")
}

// pySpace is str.isspace for one rune: Go's unicode.IsSpace plus the
// separators U+001C to U+001F, which Python also strips.
func pySpace(r rune) bool {
	return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
}

// parseForm is request.form(): a urlencoded or multipart body; any other
// content type is an empty form.
func parseForm(r *http.Request) error {
	if strings.HasPrefix(strings.ToLower(r.Header.Get("Content-Type")), "multipart/form-data") {
		return r.ParseMultipartForm(1 << 20)
	}
	return r.ParseForm()
}

// formStr is admin_helpers.form_str: the last value posted under key,
// stripped, or "" when there is none or it is a file.
func formStr(r *http.Request, key string) string {
	vals := r.PostForm[key]
	if len(vals) == 0 {
		return ""
	}
	return strings.TrimFunc(vals[len(vals)-1], pySpace)
}

// formHas is `key in form`.
func formHas(r *http.Request, key string) bool {
	if _, ok := r.PostForm[key]; ok {
		return true
	}
	if r.MultipartForm != nil {
		if _, ok := r.MultipartForm.File[key]; ok {
			return true
		}
	}
	return false
}

func isASCIIDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

// actorOf is the db.set_current_actor and db.set_current_owner pair that
// require_login leaves for db.audit.
func actorOf(h *session.Host) Actor {
	return Actor{
		AccountID:     h.Account.ID,
		Username:      h.Account.Username,
		WorkspaceID:   h.Workspace.ID,
		Impersonating: h.Impersonating,
	}
}

// login runs the router's CSRF dependency first and require_login second, as
// FastAPI does. A nil host means the response is written.
func login(w http.ResponseWriter, r *http.Request, pool *pgxpool.Pool, getenv func(string) string, at time.Time, beforeLogin func() bool) *session.Host {
	if !hostweb.CSRF(w, r, getenv, at) {
		return nil
	}
	if beforeLogin != nil && !beforeLogin() {
		return nil
	}
	h, err := hostweb.Login(w, r, pool, getenv, at)
	if err != nil {
		fail(w, err)
		return nil
	}
	return h
}

// CreateHandler is POST /privacy-requests (privacy_request_create).
func CreateHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h := login(w, r, pool, getenv, at, nil)
		if h == nil {
			return
		}
		if err := parseForm(r); err != nil {
			fail(w, err)
			return
		}
		lang := hostweb.Lang(r)
		channel := formStr(r, "channel")
		requestType := formStr(r, "request_type")
		subjectKind := formStr(r, "subject_kind")
		if !In(Channels, channel) || !In(RequestTypes, requestType) || !In(SubjectKinds, subjectKind) {
			hostweb.Back(w, r, listPath, hostweb.Flash{}, flash(lang, "flash.error.bad_dsr"))
			return
		}
		var guestID *int64
		// Python's isdigit also takes non-ASCII digits; only ASCII counts here.
		if guestRaw := formStr(r, "guest_id"); isASCIIDigits(guestRaw) {
			id, err := strconv.ParseInt(guestRaw, 10, 64)
			if err != nil {
				// Python passes the big int on and Postgres refuses it: a 500.
				fail(w, err)
				return
			}
			guestID = &id
		}
		owner := h.Workspace.ID
		stamp := Stamp(at)
		received := formStr(r, "received_at")
		if dateOnly.MatchString(received) {
			received += "T00:00:00+00:00"
		}
		if received == "" {
			received = stamp
		}
		id, err := Create(r.Context(), pool, NewRequest{
			OwnerUserID: &owner,
			ReceivedAt:  received,
			Channel:     channel,
			RequestType: requestType,
			SubjectKind: subjectKind,
			GuestID:     guestID,
			HandledBy:   &owner,
		}, stamp)
		if err != nil {
			// A received_at fromisoformat refuses, or a guest_id with no guest
			// row: Python raises and answers 500 too, having written nothing.
			fail(w, err)
			return
		}
		if err := Audit(r.Context(), pool, actorOf(h), "dsr_created",
			fmt.Sprintf("request=%d type=%s", id, requestType), stamp); err != nil {
			fail(w, err)
			return
		}
		hostweb.Back(w, r, listPath, flash(lang, "flash.dsr.created"), hostweb.Flash{})
	}
}

// unprocessable is FastAPI's 422 for a {request_id} that is not an int.
func unprocessable(w http.ResponseWriter, raw string) {
	// A struct, not a map: the fields keep pydantic's order.
	type detail struct {
		Type  string   `json:"type"`
		Loc   []string `json:"loc"`
		Msg   string   `json:"msg"`
		Input string   `json:"input"`
	}
	body := struct {
		Detail []detail `json:"detail"`
	}{[]detail{{
		Type:  "int_parsing",
		Loc:   []string{"path", "request_id"},
		Msg:   "Input should be a valid integer, unable to parse string as an integer",
		Input: raw,
	}}}
	var buf strings.Builder
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(body)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnprocessableEntity)
	_, _ = io.WriteString(w, strings.TrimSuffix(buf.String(), "\n"))
}

// UpdateHandler is POST /privacy-requests/{id} (privacy_request_update).
func UpdateHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		raw := r.PathValue("id")
		var id int64
		beyond := false
		h := login(w, r, pool, getenv, at, func() bool {
			clean := strings.TrimFunc(raw, pySpace)
			if !pathInt.MatchString(clean) {
				unprocessable(w, raw)
				return false
			}
			clean, _, _ = strings.Cut(clean, ".")
			n, err := strconv.ParseInt(strings.ReplaceAll(clean, "_", ""), 10, 64)
			if err != nil {
				// pydantic takes the big int; on PostgreSQL dsr.get compares
				// bigint with numeric and finds no row, so it is no_such_dsr
				// after the login check (brief 1371).
				beyond = true
				return true
			}
			id = n
			return true
		})
		if h == nil {
			return
		}
		ctx := r.Context()
		lang := hostweb.Lang(r)
		if beyond {
			hostweb.Back(w, r, listPath, hostweb.Flash{}, flash(lang, "flash.error.no_such_dsr"))
			return
		}
		row, found, err := Get(ctx, pool, id)
		if err != nil {
			fail(w, err)
			return
		}
		owner := h.Workspace.ID
		if !found || row.OwnerUserID != owner {
			hostweb.Back(w, r, listPath, hostweb.Flash{}, flash(lang, "flash.error.no_such_dsr"))
			return
		}
		if err := parseForm(r); err != nil {
			fail(w, err)
			return
		}
		stamp := Stamp(at)
		var c Change
		if status := formStr(r, "status"); In(Statuses, status) {
			c.Status = &status
			if In(Closed, status) {
				c.ClosedAt = &stamp
			}
		}
		if formHas(r, "outcome_note") {
			note := formStr(r, "outcome_note")
			c.OutcomeNote = &note
		}
		if formHas(r, "identity_checked") {
			c.IdentityCheckedAt = &stamp
		}
		if !c.Empty() {
			if err := Update(ctx, pool, id, c, stamp); err != nil {
				fail(w, err)
				return
			}
			if c.Status != nil && In(Closed, *c.Status) {
				if err := ResolveAlert(ctx, pool, fmt.Sprintf("dsr_due:%d", id), stamp); err != nil {
					fail(w, err)
					return
				}
			}
		}
		if err := Audit(ctx, pool, actorOf(h), "dsr_updated", fmt.Sprintf("request=%d", id), stamp); err != nil {
			fail(w, err)
			return
		}
		hostweb.Back(w, r, listPath, flash(lang, "flash.dsr.updated"), hostweb.Flash{})
	}
}
````

## go/internal/web/privacy/handler_test.go

edit (full file): signed-out steps (account 0) and the _csrf body token

````go path=go/internal/web/privacy/handler_test.go
package privacy

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const (
	testSecret     = "privacy-test-secret-key-0123456789abcdef"
	testCSRFCookie = "privacy-test-csrf-cookie" // CSRF_COOKIE_VALUE in the golden script
	csrfMark       = "@CSRF@"                   // CSRF_MARK in the golden script
)

func testEnv(k string) string {
	return map[string]string{
		"UBYHOST_SECRET_KEY":      testSecret,
		"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example",
		"UBYHOST_TERMS_VERSION":   "t1",
		"UBYHOST_PRIVACY_VERSION": "p1",
		"UBYHOST_DPA_VERSION":     "d1",
	}[k]
}

// csrfToken mints a token bound to the CSRF cookie value, as csrf_token does.
func csrfToken(t *testing.T, cookie string, at time.Time) string {
	t.Helper()
	sum := sha256.Sum256([]byte(cookie))
	tok, err := secure.NewTimedSerializer(testSecret, "ubyhost-csrf").
		Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, at)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

func TestFormStr(t *testing.T) {
	req := httptest.NewRequest(http.MethodPost, "/privacy-requests",
		strings.NewReader("channel=fax&channel=+email%1F+&outcome_note=&empty"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if err := parseForm(req); err != nil {
		t.Fatal(err)
	}
	if got := formStr(req, "channel"); got != "email" {
		t.Errorf("channel = %q, want the last value stripped", got)
	}
	if got := formStr(req, "missing"); got != "" || formHas(req, "missing") {
		t.Errorf("missing key: %q", got)
	}
	if !formHas(req, "outcome_note") || !formHas(req, "empty") {
		t.Error("a posted empty key must count as present")
	}
}

func TestPathInt(t *testing.T) {
	for raw, ok := range map[string]bool{
		"5": true, "+5": true, "-5": true, "05": true, "5.00": true, "1_0.0": true,
		"5.": false, "5.5": false, "_5": false, "5_": false, "1__0": false, "0x10": false, "": false,
	} {
		if got := pathInt.MatchString(raw); got != ok {
			t.Errorf("pathInt(%q) = %v, want %v", raw, got, ok)
		}
	}
}

func TestBadCSRFNeverTouchesThePool(t *testing.T) {
	at := time.Date(2026, 11, 13, 9, 30, 0, 0, time.UTC)
	now := func() time.Time { return at }
	mux := http.NewServeMux()
	mux.Handle("POST /privacy-requests", CreateHandler(nil, testEnv, now))
	mux.Handle("POST /privacy-requests/{id}", UpdateHandler(nil, testEnv, now))
	for _, path := range []string{"/privacy-requests", "/privacy-requests/5", "/privacy-requests/abc"} {
		req := httptest.NewRequest(http.MethodPost, path, strings.NewReader("status=fulfilled"))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("x-csrf-token", "not-a-token")
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: testCSRFCookie})
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req) // a nil pool would panic if it were used
		if rec.Code != http.StatusForbidden && rec.Code != http.StatusSeeOther {
			t.Errorf("%s: code %d", path, rec.Code)
		}
		if loc := rec.Header().Get("Location"); strings.HasPrefix(loc, "/privacy-requests") {
			t.Errorf("%s: bad CSRF reached the route, Location %q", path, loc)
		}
	}
}

// seedValue turns a JSON number into the int64 the seed columns hold.
func seedValue(v any) any {
	if f, ok := v.(float64); ok && f == math.Trunc(f) {
		return int64(f)
	}
	return v
}

func TestPrivacyRequestsGolden(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	ctx := context.Background()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table.Table,
			strings.Join(table.Columns, ", "), strings.Join(marks, ", "))
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = seedValue(v)
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
	// The seed wrote ids by hand; SQLite's next id is MAX(id) + 1, so move the
	// Postgres identity there too.
	if _, err := pool.Exec(ctx, `SELECT setval(pg_get_serial_sequence('data_subject_request', 'id'),
		(SELECT MAX(id) FROM data_subject_request))`); err != nil {
		t.Fatal(err)
	}
	at, err := time.Parse(time.RFC3339, g.Now)
	if err != nil {
		t.Fatal(err)
	}
	now := func() time.Time { return at }
	mux := http.NewServeMux()
	mux.Handle("POST /privacy-requests", CreateHandler(pool, testEnv, now))
	mux.Handle("POST /privacy-requests/{id}", UpdateHandler(pool, testEnv, now))

	read := func(sql string) []map[string]any {
		rows, err := pool.Query(ctx, sql)
		if err != nil {
			t.Fatal(err)
		}
		defer rows.Close()
		out := []map[string]any{}
		for rows.Next() {
			var raw []byte
			if err := rows.Scan(&raw); err != nil {
				t.Fatal(err)
			}
			var m map[string]any
			if err := json.Unmarshal(raw, &m); err != nil {
				t.Fatal(err)
			}
			out = append(out, m)
		}
		if err := rows.Err(); err != nil {
			t.Fatal(err)
		}
		return out
	}
	queries := map[string]string{
		"data_subject_request": `SELECT to_jsonb(t)::text FROM data_subject_request t ORDER BY id`,
		"audit":                `SELECT (to_jsonb(t) - 'id')::text FROM audit t ORDER BY id`,
		"alert": `SELECT jsonb_build_object('id', id, 'dedupe_key', dedupe_key,
			'resolved_at', resolved_at)::text FROM alert ORDER BY id`,
	}
	for _, step := range g.Steps {
		// A body with csrfMark carries the token as the _csrf form field (the
		// no-JS browser path); every other step sends it in the header.
		body := strings.ReplaceAll(step.Body, csrfMark, csrfToken(t, testCSRFCookie, at))
		req := httptest.NewRequest(http.MethodPost, step.Path, strings.NewReader(body))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		if !strings.Contains(step.Body, csrfMark) {
			req.Header.Set("x-csrf-token", csrfToken(t, testCSRFCookie, at))
		}
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: testCSRFCookie})
		if step.Account != 0 { // account 0 is signed out: no session cookie
			payload := map[string]any{"uid": step.Account, "sv": int64(1), "iat": at.Unix()}
			if step.Account != step.Workspace {
				payload["as"] = step.Workspace
				payload["ast"] = at.Unix()
			}
			req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, at)})
		}
		if step.Lang != "" {
			req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: step.Lang})
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		if rec.Code != step.Status {
			t.Errorf("%s: status %d, Python %d (body %q)", step.Name, rec.Code, step.Status, rec.Body.String())
		}
		if got := rec.Header().Get("Location"); got != step.Location {
			t.Errorf("%s: Location %q, Python %q", step.Name, got, step.Location)
		}
		if step.Status != http.StatusSeeOther && rec.Body.String() != step.Response {
			t.Errorf("%s: body %q, Python %q", step.Name, rec.Body.String(), step.Response)
		}
		for table, sql := range queries {
			got, want := read(sql), step.State[table]
			if !reflect.DeepEqual(got, want) {
				gj, _ := json.Marshal(got)
				wj, _ := json.Marshal(want)
				t.Errorf("%s: %s\n got  %s\n want %s", step.Name, table, gj, wj)
			}
		}
		if t.Failed() {
			t.Fatalf("stopped after step %s", step.Name)
		}
	}
	for key, want := range g.ListForOwner {
		var owner *int64
		if key != "None" {
			var id int64
			fmt.Sscan(key, &id)
			owner = &id
		}
		rows, err := ListForOwner(ctx, pool, owner)
		if err != nil {
			t.Fatal(err)
		}
		got := []int64{}
		for _, r := range rows {
			got = append(got, r.ID)
		}
		if !reflect.DeepEqual(got, want) {
			t.Errorf("ListForOwner(%s) = %v, Python %v", key, got, want)
		}
	}
}
````

## go/internal/web/privacy/page.go

create: ListHandler, pageData, dateCZ, parsed templates

````go path=go/internal/web/privacy/page.go
package privacy

import (
	"embed"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

//go:embed templates/*.tmpl
var templateFS embed.FS

// pages is templates/privacy_requests.tmpl on the shared host layout.
var pages = layout.MustParse(catalog, templateFS, "templates/*.tmpl")

// pageName is the {{define}} of the page body.
const pageName = "privacy_requests"

// pageRow is one request as privacy_requests.html prints it. ReceivedCZ is
// the date_cz filter, which the layout has no func for.
type pageRow struct {
	Request
	ReceivedCZ string
}

// pageData is the context privacy_requests_list gives the template.
type pageData struct {
	Requests     []pageRow
	Channels     []string
	RequestTypes []string
	SubjectKinds []string
	Statuses     []string
}

// isoDate is the regexp strptime builds for "%Y-%m-%d": four digits, a month
// 1-12 with an optional leading zero, a day 1-31 with an optional leading
// zero or space.
var isoDate = regexp.MustCompile(`^([0-9]{4})-(1[0-2]|0[1-9]|[1-9])-(3[01]|[12][0-9]|0[1-9]|[1-9]| [1-9])$`)

// dateCZ is validation.fmt_date (the date_cz filter): the first ten
// characters read as an ISO date and printed DD.MM.YYYY; anything else is
// shown as stored.
func dateCZ(value string) string {
	r := []rune(value)
	if len(r) > 10 {
		r = r[:10]
	}
	m := isoDate.FindStringSubmatch(string(r))
	if m == nil {
		return value
	}
	y, _ := strconv.Atoi(m[1])
	mo, _ := strconv.Atoi(m[2])
	d, _ := strconv.Atoi(strings.TrimPrefix(m[3], " "))
	t := time.Date(y, time.Month(mo), d, 0, 0, 0, 0, time.UTC)
	if y < 1 || t.Day() != d || t.Month() != time.Month(mo) {
		return value
	}
	return t.Format("02.01.2006")
}

// ListHandler is GET /privacy-requests (privacy_requests_list).
func ListHandler(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		at := now()
		h, err := hostweb.Login(w, r, pool, getenv, at)
		if err != nil {
			fail(w, err)
			return
		}
		if h == nil {
			return
		}
		owner := h.Workspace.ID
		list, err := ListForOwner(r.Context(), pool, &owner)
		if err != nil {
			fail(w, err)
			return
		}
		data := pageData{
			Requests:     make([]pageRow, 0, len(list)),
			Channels:     Channels,
			RequestTypes: RequestTypes,
			SubjectKinds: SubjectKinds,
			Statuses:     Statuses,
		}
		for _, row := range list {
			data.Requests = append(data.Requests, pageRow{Request: row, ReceivedCZ: dateCZ(row.ReceivedAt)})
		}
		page := layout.Page{
			Title:    catalog.T(hostweb.Lang(r), "privacy_requests.title", nil),
			Nav:      "privacy_requests",
			BodyKind: "list",
			V2:       true,
		}
		if err := layout.Render(w, r, layout.Env{Pool: pool, Getenv: getenv, Now: at}, h, page, pages, pageName, data); err != nil {
			fail(w, err)
		}
	}
}
````

## go/internal/web/privacy/templates/privacy_requests.tmpl

create: the page body

````text path=go/internal/web/privacy/templates/privacy_requests.tmpl
{{- /* Port of App/app/templates/privacy_requests.html (brief 1371). The h1 slot is
empty, as page_title is there; the settings back header is in the body. */ -}}
{{define "privacy_requests.title"}}{{end}}
{{define "privacy_requests"}}
<div class="airbnb-header">
  <a class="airbnb-back" href="/settings" aria-label="{{t "common.back"}}">{{icon "arrow-left" 20}}</a>
  <h1 class="airbnb-title">{{t "privacy_requests.title"}}</h1>
</div>
<div class="pr-lane">

<details class="card" {{if not .Requests}}open{{end}}>
  <summary>{{t "privacy_requests.create_title"}}</summary>
  <form method="post" action="/privacy-requests">
    <input type="hidden" name="_csrf" value="{{csrf}}">
    <div class="ui-pair">
      <div class="ui-field"><label for="received_at">{{t "privacy_requests.received"}}</label>
        <input type="date" id="received_at" name="received_at" value=""></div>
      <div class="ui-field"><label for="channel">{{t "privacy_requests.channel"}}</label>
        <select id="channel" name="channel">
          {{range .Channels}}<option value="{{.}}">{{t (printf "privacy_requests.channel.%s" .)}}</option>{{end}}
        </select>
      </div>
      <div class="ui-field"><label for="request_type">{{t "privacy_requests.type"}}</label>
        <select id="request_type" name="request_type">
          {{range .RequestTypes}}<option value="{{.}}">{{t (printf "privacy_requests.type.%s" .)}}</option>{{end}}
        </select>
      </div>
      <div class="ui-field"><label for="subject_kind">{{t "privacy_requests.subject"}}</label>
        <select id="subject_kind" name="subject_kind">
          {{range .SubjectKinds}}<option value="{{.}}">{{t (printf "privacy_requests.subject.%s" .)}}</option>{{end}}
        </select>
      </div>
      <div class="ui-field"><label for="guest_id">{{t "privacy_requests.guest_id"}}</label>
        <input id="guest_id" name="guest_id" inputmode="numeric"></div>
    </div>
    <div class="ui-form-actions"><button class="ui-btn ui-btn-primary" type="submit">{{t "privacy_requests.create"}}</button></div>
  </form>
</details>

{{$statuses := .Statuses}}
{{range .Requests}}{{$row := .}}
<div class="card">
  <h2>
    {{t (printf "privacy_requests.type.%s" .RequestType)}} &middot; {{t (printf "privacy_requests.status.%s" .Status)}}
  </h2>
  <p class="ui-sub">
    {{t "privacy_requests.received"}}: {{.ReceivedCZ}}
    &middot; {{t "privacy_requests.due"}}: {{datetime_local .DueAt}}
    {{if .GuestID}}&middot; {{t "privacy_requests.guest_id"}}: {{.GuestID}}{{end}}
  </p>
  <form method="post" action="/privacy-requests/{{.ID}}">
    <input type="hidden" name="_csrf" value="{{csrf}}">
    <div class="ui-pair">
      <div class="ui-field"><label for="status-{{.ID}}">{{t "privacy_requests.status_label"}}</label>
        <select id="status-{{.ID}}" name="status">
          {{range $statuses}}<option value="{{.}}" {{if eq . $row.Status}}selected{{end}}>{{t (printf "privacy_requests.status.%s" .)}}</option>{{end}}
        </select>
      </div>
      <div class="ui-field"><label for="outcome-{{.ID}}">{{t "privacy_requests.outcome"}}</label>
        <input id="outcome-{{.ID}}" name="outcome_note" value="{{.OutcomeNote}}"></div>
      {{if not .IdentityCheckedAt}}
      <div class="ui-field"><label class="checkline"><input type="checkbox" name="identity_checked"> {{t "privacy_requests.identity_checked"}}</label></div>
      {{end}}
    </div>
    <div class="ui-form-actions"><button class="ui-btn ui-btn-secondary" type="submit">{{t "privacy_requests.save"}}</button></div>
  </form>
</div>
{{else}}
<p class="ui-sub">{{t "privacy_requests.empty"}}</p>
{{end}}
</div>
{{end}}
````

## go/internal/web/privacy/page_test.go

create: dateCZ vs Python, content extractor, page golden on Postgres

````go path=go/internal/web/privacy/page_test.go
package privacy

import (
	"context"
	"encoding/json"
	"fmt"
	"html"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// pageGolden is testdata/privacy_requests_page_golden.json, written by
// App/scripts/privacy_requests_page_golden.py.
type pageGolden struct {
	Seed []struct {
		Table   string   `json:"table"`
		Columns []string `json:"columns"`
		Rows    [][]any  `json:"rows"`
	} `json:"seed"`
	Cases []struct {
		Name      string `json:"name"`
		Account   int64  `json:"account"`
		Workspace int64  `json:"workspace"`
		Lang      string `json:"lang"`
		Status    int    `json:"status"`
		Title     string `json:"title"`
		Region    string `json:"region"`
	} `json:"cases"`
	DateCZ [][2]string `json:"date_cz"`
}

func loadPageGolden(t *testing.T) pageGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/privacy_requests_page_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g pageGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

var (
	pageTag   = regexp.MustCompile(`(?s)<!--.*?-->|<(/?)([a-zA-Z][a-zA-Z0-9-]*)((?:[^>"]|"[^"]*")*)>`)
	pageAttr  = regexp.MustCompile(`([^\s=/>"]+)(?:\s*=\s*"([^"]*)")?`)
	pageCSRF  = regexp.MustCompile(`(name="_csrf" value=")[^"]*(")`)
	pageTitle = regexp.MustCompile(`(?s)<title>(.*?)</title>`)
)

// pageRegion is the golden script's REGION: from <div class="ui-page" up to
// the page skeleton, with every _csrf value replaced by CSRF.
func pageRegion(doc string) string {
	start := strings.Index(doc, `<div class="ui-page"`)
	if start < 0 {
		return ""
	}
	end := strings.Index(doc[start:], `<div class="page-skeleton"`)
	if end < 0 {
		return ""
	}
	return pageCSRF.ReplaceAllString(doc[start:start+end], "${1}CSRF${2}")
}

// pageContent is what the comparison reads from a region: each text run
// (unescaped, whitespace collapsed), each start tag with its attributes
// sorted and unescaped, and each end tag. Inside an <svg> only the <svg> tag
// itself counts (the icon paths are brief 1380's).
func pageContent(region string) []string {
	var out []string
	text := func(s string) {
		if s = strings.Join(strings.Fields(html.UnescapeString(s)), " "); s != "" {
			out = append(out, "text "+s)
		}
	}
	svg, last := 0, 0
	for _, m := range pageTag.FindAllStringSubmatchIndex(region, -1) {
		if svg == 0 {
			text(region[last:m[0]])
		}
		last = m[1]
		if m[4] < 0 { // a comment
			continue
		}
		closing := m[3] > m[2]
		name := strings.ToLower(region[m[4]:m[5]])
		if svg > 0 && name != "svg" {
			continue
		}
		if closing {
			if name == "svg" {
				svg--
			}
			out = append(out, "/"+name)
			continue
		}
		var attrs []string
		for _, a := range pageAttr.FindAllStringSubmatch(region[m[6]:m[7]], -1) {
			if a[0] == "" {
				continue
			}
			if strings.Contains(a[0], "=") {
				attrs = append(attrs, a[1]+"="+html.UnescapeString(a[2]))
			} else {
				attrs = append(attrs, a[1])
			}
		}
		sort.Strings(attrs)
		out = append(out, strings.TrimSpace("<"+name+" "+strings.Join(attrs, " ")))
		if name == "svg" {
			svg++
		}
	}
	if svg == 0 {
		text(region[last:])
	}
	return out
}

func TestDateCZMatchesPython(t *testing.T) {
	g := loadPageGolden(t)
	if len(g.DateCZ) < 10 {
		t.Fatalf("only %d date_cz cases", len(g.DateCZ))
	}
	for _, c := range g.DateCZ {
		if got := dateCZ(c[0]); got != c[1] {
			t.Errorf("dateCZ(%q) = %q, Python %q", c[0], got, c[1])
		}
	}
}

func TestPageContentReadsTagsAndText(t *testing.T) {
	got := pageContent(`<div class="ui-page" data-body-kind="list"><details class="card" open>` +
		`<summary>A &amp; B</summary><svg data-icon="x"><path d="M1"/></svg>` +
		`<input value="&lt;b&gt; &#43;1" name="n"></details></div>`)
	want := []string{
		`<div class=ui-page data-body-kind=list`, `<details class=card open`, `<summary`,
		`text A & B`, `/summary`, `<svg data-icon=x`, `/svg`, `<input name=n value=<b> +1`,
		`/details`, `/div`,
	}
	if strings.Join(got, "\n") != strings.Join(want, "\n") {
		t.Errorf("pageContent:\n%s\nwant\n%s", strings.Join(got, "\n"), strings.Join(want, "\n"))
	}
}

func TestPrivacyRequestsPageGolden(t *testing.T) {
	g := loadPageGolden(t)
	pool := testPool(t)
	ctx := context.Background()
	for _, table := range g.Seed {
		marks := make([]string, len(table.Columns))
		for i := range marks {
			marks[i] = fmt.Sprintf("$%d", i+1)
		}
		sql := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", table.Table,
			strings.Join(table.Columns, ", "), strings.Join(marks, ", "))
		for _, row := range table.Rows {
			args := make([]any, len(row))
			for i, v := range row {
				args[i] = seedValue(v)
			}
			if _, err := pool.Exec(ctx, sql, args...); err != nil {
				t.Fatalf("seed %s: %v", table.Table, err)
			}
		}
	}
	at := time.Date(2026, 11, 13, 9, 30, 0, 0, time.UTC)
	mux := http.NewServeMux()
	mux.Handle("GET /privacy-requests", ListHandler(pool, testEnv, func() time.Time { return at }))
	if len(g.Cases) < 3 {
		t.Fatalf("only %d cases", len(g.Cases))
	}
	for _, c := range g.Cases {
		req := httptest.NewRequest(http.MethodGet, "/privacy-requests", nil)
		payload := map[string]any{"uid": c.Account, "sv": int64(1), "iat": at.Unix()}
		if c.Account != c.Workspace {
			payload["as"] = c.Workspace
			payload["ast"] = at.Unix()
		}
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, at)})
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: c.Lang})
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		doc := rec.Body.String()
		if rec.Code != c.Status {
			t.Fatalf("%s: status %d, Python %d (Location %q, body %.300q)", c.Name, rec.Code, c.Status,
				rec.Header().Get("Location"), doc)
		}
		title := ""
		if m := pageTitle.FindStringSubmatch(doc); m != nil {
			title = strings.TrimSpace(m[1])
		}
		if html.UnescapeString(title) != html.UnescapeString(c.Title) {
			t.Errorf("%s: title %q, Python %q", c.Name, title, c.Title)
		}
		got, want := pageContent(pageRegion(doc)), pageContent(c.Region)
		if len(want) < 40 {
			t.Fatalf("%s: the Python region has only %d items", c.Name, len(want))
		}
		gj, wj := strings.Join(got, "\n"), strings.Join(want, "\n")
		if gj != wj {
			for i := 0; i < len(got) || i < len(want); i++ {
				var a, b string
				if i < len(got) {
					a = got[i]
				}
				if i < len(want) {
					b = want[i]
				}
				if a != b {
					t.Errorf("%s: item %d differs\n Go     %q\n Python %q", c.Name, i, a, b)
					break
				}
			}
		}
		open := strings.Contains(wj, "<details class=card open")
		if open != (c.Name == "empty_vi") {
			t.Errorf("%s: details open = %v in the Python region", c.Name, open)
		}
	}
}
````

## go/internal/web/privacy/i18n_keys.txt

edit (full file): plus the privacy_requests.* page keys

````text path=go/internal/web/privacy/i18n_keys.txt
# Host strings read by go/internal/web/privacy (privacy_requests.py routes and privacy_requests.html)
flash.dsr.created
flash.dsr.updated
flash.error.bad_dsr
flash.error.no_such_dsr
privacy_requests.channel
privacy_requests.channel.email
privacy_requests.channel.in_person
privacy_requests.channel.other
privacy_requests.channel.post
privacy_requests.channel.support
privacy_requests.create
privacy_requests.create_title
privacy_requests.due
privacy_requests.empty
privacy_requests.guest_id
privacy_requests.identity_checked
privacy_requests.outcome
privacy_requests.received
privacy_requests.save
privacy_requests.status.extended
privacy_requests.status.fulfilled
privacy_requests.status.open
privacy_requests.status.refused
privacy_requests.status.withdrawn
privacy_requests.status_label
privacy_requests.subject
privacy_requests.subject.guest
privacy_requests.subject.host_user
privacy_requests.subject.other
privacy_requests.title
privacy_requests.type
privacy_requests.type.access
privacy_requests.type.erasure
privacy_requests.type.objection
privacy_requests.type.other
privacy_requests.type.portability
privacy_requests.type.rectification
privacy_requests.type.restriction
````

## go/internal/web/privacy/i18n.json

edit (full file): generated by App/scripts/go_host_i18n.py

````json path=go/internal/web/privacy/i18n.json
{
 "cs": {
  "flash.dsr.created": "Žádost zaznamenána.",
  "flash.dsr.updated": "Žádost aktualizována.",
  "flash.error.bad_dsr": "Zvolte platný kanál, typ žádosti a subjekt.",
  "flash.error.no_such_dsr": "Tato žádost neexistuje.",
  "privacy_requests.channel": "Kanál",
  "privacy_requests.channel.email": "E-mail",
  "privacy_requests.channel.in_person": "Osobně",
  "privacy_requests.channel.other": "Jiné",
  "privacy_requests.channel.post": "Pošta",
  "privacy_requests.channel.support": "Podpora",
  "privacy_requests.create": "Zaznamenat žádost",
  "privacy_requests.create_title": "Zaznamenat žádost",
  "privacy_requests.due": "Termín",
  "privacy_requests.empty": "Nejsou zaznamenány žádné žádosti.",
  "privacy_requests.guest_id": "ID hosta",
  "privacy_requests.identity_checked": "Totožnost ověřena",
  "privacy_requests.outcome": "Poznámka k výsledku",
  "privacy_requests.received": "Přijato",
  "privacy_requests.save": "Uložit",
  "privacy_requests.status.extended": "Prodloužená",
  "privacy_requests.status.fulfilled": "Vyřízená",
  "privacy_requests.status.open": "Otevřená",
  "privacy_requests.status.refused": "Zamítnutá",
  "privacy_requests.status.withdrawn": "Stažená",
  "privacy_requests.status_label": "Stav",
  "privacy_requests.subject": "Subjekt",
  "privacy_requests.subject.guest": "Host",
  "privacy_requests.subject.host_user": "Účet ubytovatele",
  "privacy_requests.subject.other": "Jiné",
  "privacy_requests.title": "Žádosti subjektů údajů",
  "privacy_requests.type": "Žádost",
  "privacy_requests.type.access": "Přístup",
  "privacy_requests.type.erasure": "Výmaz",
  "privacy_requests.type.objection": "Námitka",
  "privacy_requests.type.other": "Jiné",
  "privacy_requests.type.portability": "Přenositelnost",
  "privacy_requests.type.rectification": "Oprava",
  "privacy_requests.type.restriction": "Omezení"
 },
 "en": {
  "flash.dsr.created": "Request recorded.",
  "flash.dsr.updated": "Request updated.",
  "flash.error.bad_dsr": "Choose a valid channel, request type and subject.",
  "flash.error.no_such_dsr": "No such request.",
  "privacy_requests.channel": "Channel",
  "privacy_requests.channel.email": "E-mail",
  "privacy_requests.channel.in_person": "In person",
  "privacy_requests.channel.other": "Other",
  "privacy_requests.channel.post": "Post",
  "privacy_requests.channel.support": "Support",
  "privacy_requests.create": "Record request",
  "privacy_requests.create_title": "Record a request",
  "privacy_requests.due": "Due",
  "privacy_requests.empty": "No requests recorded.",
  "privacy_requests.guest_id": "Guest id",
  "privacy_requests.identity_checked": "Identity checked",
  "privacy_requests.outcome": "Outcome note",
  "privacy_requests.received": "Received",
  "privacy_requests.save": "Save",
  "privacy_requests.status.extended": "Extended",
  "privacy_requests.status.fulfilled": "Fulfilled",
  "privacy_requests.status.open": "Open",
  "privacy_requests.status.refused": "Refused",
  "privacy_requests.status.withdrawn": "Withdrawn",
  "privacy_requests.status_label": "Status",
  "privacy_requests.subject": "Subject",
  "privacy_requests.subject.guest": "Guest",
  "privacy_requests.subject.host_user": "Host account",
  "privacy_requests.subject.other": "Other",
  "privacy_requests.title": "Data-subject requests",
  "privacy_requests.type": "Request",
  "privacy_requests.type.access": "Access",
  "privacy_requests.type.erasure": "Erasure",
  "privacy_requests.type.objection": "Objection",
  "privacy_requests.type.other": "Other",
  "privacy_requests.type.portability": "Portability",
  "privacy_requests.type.rectification": "Rectification",
  "privacy_requests.type.restriction": "Restriction"
 },
 "vi": {
  "flash.dsr.created": "Đã ghi nhận yêu cầu.",
  "flash.dsr.updated": "Đã cập nhật yêu cầu.",
  "flash.error.bad_dsr": "Chọn kênh, loại yêu cầu và chủ thể hợp lệ.",
  "flash.error.no_such_dsr": "Không có yêu cầu này.",
  "privacy_requests.channel": "Kênh",
  "privacy_requests.channel.email": "Email",
  "privacy_requests.channel.in_person": "Trực tiếp",
  "privacy_requests.channel.other": "Khác",
  "privacy_requests.channel.post": "Bưu điện",
  "privacy_requests.channel.support": "Hỗ trợ",
  "privacy_requests.create": "Ghi nhận yêu cầu",
  "privacy_requests.create_title": "Ghi nhận yêu cầu",
  "privacy_requests.due": "Hạn",
  "privacy_requests.empty": "Chưa ghi nhận yêu cầu nào.",
  "privacy_requests.guest_id": "ID khách",
  "privacy_requests.identity_checked": "Đã kiểm tra danh tính",
  "privacy_requests.outcome": "Ghi chú kết quả",
  "privacy_requests.received": "Ngày nhận",
  "privacy_requests.save": "Lưu",
  "privacy_requests.status.extended": "Đã gia hạn",
  "privacy_requests.status.fulfilled": "Đã đáp ứng",
  "privacy_requests.status.open": "Đang mở",
  "privacy_requests.status.refused": "Đã từ chối",
  "privacy_requests.status.withdrawn": "Đã rút lại",
  "privacy_requests.status_label": "Trạng thái",
  "privacy_requests.subject": "Chủ thể",
  "privacy_requests.subject.guest": "Khách",
  "privacy_requests.subject.host_user": "Tài khoản chủ nhà",
  "privacy_requests.subject.other": "Khác",
  "privacy_requests.title": "Yêu cầu của chủ thể dữ liệu",
  "privacy_requests.type": "Yêu cầu",
  "privacy_requests.type.access": "Truy cập",
  "privacy_requests.type.erasure": "Xóa",
  "privacy_requests.type.objection": "Phản đối",
  "privacy_requests.type.other": "Khác",
  "privacy_requests.type.portability": "Chuyển dữ liệu",
  "privacy_requests.type.rectification": "Sửa đổi",
  "privacy_requests.type.restriction": "Hạn chế"
 }
}
````

## go/cmd/ubyhost-web/register_web_privacy.go

edit (full file): plus GET /privacy-requests

````go path=go/cmd/ubyhost-web/register_web_privacy.go
package main

// Briefs 1370 and 1371: the data-subject request register
// (routes/privacy_requests.py), its GET page and both POST routes. Caddy
// sends a path here only when it is in UBYHOST_GO_PATHS, so these stay off
// until the owner adds them.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/privacy"
)

func init() {
	registerRoutes(func(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
		mux.Handle("GET /privacy-requests", m.wrap("/privacy-requests", privacy.ListHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /privacy-requests", m.wrap("/privacy-requests", privacy.CreateHandler(pool, os.Getenv, time.Now)))
		mux.Handle("POST /privacy-requests/{id}", m.wrap("/privacy-requests/{id}", privacy.UpdateHandler(pool, os.Getenv, time.Now)))
	})
}
````

## App/scripts/privacy_requests_golden.py

edit (full file): six new steps

````python path=App/scripts/privacy_requests_golden.py
"""Write go/internal/web/privacy/testdata/privacy_requests_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/privacy_requests_golden.py

It seeds a throwaway SQLite database with SEED, mounts the real
routes/privacy_requests.py router on a bare FastAPI app and posts each entry of
STEPS through it. The clock is fixed at NOW, so every timestamp a step writes
is NOW. Sign-in and CSRF are mostly not what this file pins: the CSRF
dependency is switched off and require_login is replaced by one that sets the
step's actor the way the real one does. Two exceptions (brief 1371): account 0
runs the real require_login with no session (the /login redirect), and a body
holding CSRF_MARK goes through the real CSRF dependency with a real token in
the _csrf form field and no header (the no-JS browser path). dsr.get answers
None for an id beyond int64, as PostgreSQL does (bigint = numeric finds no
row); SQLite raises OverflowError there instead. After each step it records the status, Location
and body of the answer and every data_subject_request, audit and alert row.
It also records dsr.one_month_later for each ONE_MONTH input ("error" when it
raises) and the ids dsr.list_for_owner returns for owners 1, 2 and None at the
end. go/internal/web/privacy/handler_test.go seeds PostgreSQL from the same
file, signs in for real, posts the same bodies and compares.
App/tests/test_go_privacy_requests.py fails when this file is stale.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "privacy" / "testdata" / "privacy_requests_golden.json"

NOW = "2026-11-13T09:30:00+00:00"
STAMP = "2026-09-01T00:00:00+00:00"
FORM = "application/x-www-form-urlencoded"

SEED = [
    {
        "table": "user_account",
        "columns": ["id", "username", "password_hash", "role", "active", "session_version", "created_at"],
        "rows": [
            [1, "owner@example.test", "x", "host", 1, 1, STAMP],
            [2, "other@example.test", "x", "host", 1, 1, STAMP],
            [3, "admin@example.test", "x", "admin", 1, 1, STAMP],
        ],
    },
    {
        "table": "legal_acceptance",
        "columns": ["id", "user_account_id", "document", "version", "accepted_at", "method"],
        "rows": [
            [101, 1, "terms", "t1", STAMP, "clickwrap"],
            [102, 1, "privacy", "p1", STAMP, "clickwrap"],
            [103, 1, "dpa", "d1", STAMP, "clickwrap"],
            [104, 3, "terms", "t1", STAMP, "clickwrap"],
            [105, 3, "privacy", "p1", STAMP, "clickwrap"],
            [106, 3, "dpa", "d1", STAMP, "clickwrap"],
        ],
    },
    {
        "table": "apartment",
        "columns": ["id", "owner_user_id", "internal_name", "created_at"],
        "rows": [[1, 1, "Byt A", STAMP]],
    },
    {
        "table": "reservation",
        "columns": ["id", "apartment_id", "source", "uid", "date_from", "date_to",
                    "status", "created_at", "updated_at"],
        "rows": [[1, 1, "manual", "r1", "2026-10-01", "2026-10-03", "active", STAMP, STAMP]],
    },
    {
        "table": "guest",
        "columns": ["id", "reservation_id", "created_at", "updated_at"],
        "rows": [[7, 1, STAMP, STAMP]],
    },
    {
        "table": "data_subject_request",
        "columns": ["id", "owner_user_id", "received_at", "due_at", "channel",
                    "request_type", "subject_kind", "status", "created_at", "updated_at"],
        "rows": [
            [49, None, STAMP, "2026-10-01T00:00:00+00:00", "other", "other", "other", "fulfilled", STAMP, STAMP],
            [50, 2, STAMP, "2026-10-01T00:00:00+00:00", "email", "access", "guest", "open", STAMP, STAMP],
            [51, 1, STAMP, "2026-10-01T00:00:00+00:00", "post", "erasure", "guest", "open", STAMP, STAMP],
        ],
    },
    {
        "table": "alert",
        "columns": ["id", "level", "kind", "owner_user_id", "dedupe_key", "message",
                    "created_at", "user_dismissed"],
        "rows": [
            [9001, "info", "dsr_due", 1, "dsr_due:51", "seeded", STAMP, 0],
            [9002, "info", "dsr_due", 2, "dsr_due:50", "seeded", STAMP, 0],
        ],
    },
]

OWNER = {"account": 1, "workspace": 1}
ADMIN_AS_OWNER = {"account": 3, "workspace": 1}
SIGNED_OUT = {"account": 0, "workspace": 0}

# A body holding this goes through the real CSRF dependency; each side puts its
# own valid token in its place (the Go test mints one for its CSRF cookie).
CSRF_MARK = "@CSRF@"
CSRF_COOKIE_VALUE = "privacy-test-csrf-cookie"
INT64_MAX = 2**63 - 1

# Each step: name, actor, language cookie ("" for none), path, raw form body.
# Created requests get ids 52, 53, ... in order.
STEPS = [
    ["create_date_only", OWNER, "",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=guest&received_at=2026-01-31&guest_id="],
    ["create_bad_channel", OWNER, "",
     "/privacy-requests", "channel=fax&request_type=access&subject_kind=guest"],
    ["create_bad_subject_cs", OWNER, "cs",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=robot"],
    ["create_received_empty_is_now", OWNER, "",
     "/privacy-requests", "channel=post&request_type=erasure&subject_kind=host_user&received_at="],
    ["create_guest_digits_offset_passthrough", OWNER, "",
     "/privacy-requests", "channel=in_person&request_type=objection&subject_kind=guest&guest_id=+7+&received_at=2026-03-31T23%3A15%3A00%2B02%3A00"],
    ["create_guest_not_digits_space_separator", OWNER, "",
     "/privacy-requests", "channel=support&request_type=portability&subject_kind=other&guest_id=12a&received_at=2026-12-31+08%3A00"],
    ["create_received_invalid_500", OWNER, "",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=guest&received_at=31.01.2026"],
    ["create_last_value_wins_cs_fraction", OWNER, "cs",
     "/privacy-requests", "channel=fax&channel=other&request_type=rectification&subject_kind=guest&received_at=2026-05-31T10%3A00%3A00.5Z"],
    ["create_impersonating", ADMIN_AS_OWNER, "",
     "/privacy-requests", "channel=email&request_type=restriction&subject_kind=guest&received_at=2024-01-31"],
    ["update_closed_resolves_alert", OWNER, "",
     "/privacy-requests/51", "status=fulfilled"],
    ["update_note_identity_unknown_status", OWNER, "",
     "/privacy-requests/52", "status=pending&outcome_note=+Sent+the+export+&identity_checked=on"],
    ["update_extended_keeps_alert", OWNER, "",
     "/privacy-requests/52", "status=extended&outcome_note="],
    ["update_nothing_still_audits", OWNER, "",
     "/privacy-requests/52", "status=bogus"],
    ["update_other_owner", OWNER, "",
     "/privacy-requests/50", "status=fulfilled"],
    ["update_missing_cs", OWNER, "cs",
     "/privacy-requests/999", "status=fulfilled"],
    ["update_path_int_forms", OWNER, "",
     "/privacy-requests/+5_2.00", "status=refused"],
    ["update_path_not_int_422", OWNER, "",
     "/privacy-requests/abc", "status=refused"],
    ["update_impersonating_withdrawn", ADMIN_AS_OWNER, "",
     "/privacy-requests/53", "status=withdrawn&outcome_note=Asked+to+stop"],
    ["update_beyond_int64_signed_out", SIGNED_OUT, "",
     "/privacy-requests/99999999999999999999", "status=refused"],
    ["update_beyond_int64", OWNER, "",
     "/privacy-requests/99999999999999999999", "status=refused"],
    ["update_below_int64_cs", OWNER, "cs",
     "/privacy-requests/-99999999999999999999", "status=refused"],
    ["update_int64_max", OWNER, "",
     "/privacy-requests/9223372036854775807", "status=refused"],
    ["update_csrf_in_body", OWNER, "",
     "/privacy-requests/52", "_csrf=" + CSRF_MARK + "&status=open&outcome_note=Body+token"],
    ["create_csrf_in_body", OWNER, "",
     "/privacy-requests", "_csrf=" + CSRF_MARK + "&channel=post&request_type=access&subject_kind=guest&received_at=2026-02-01"],
    # Last on purpose: on Postgres the refused INSERT still uses up an id,
    # on SQLite it does not, so no step may create a request after this one.
    ["create_guest_missing_row_500", OWNER, "",
     "/privacy-requests", "channel=email&request_type=access&subject_kind=guest&guest_id=999&received_at=2026-01-01"],
]

ONE_MONTH = [
    "2026-01-31", "2024-01-31", "2026-12-31", "2026-02-28", "2026-03-31T23:15:00+02:00",
    "2026-01-31T00:00:00+00:00", "2026-01-31T10:00", "2026-01-31T10", "2026-01-31 10:00:00Z",
    "2026-12-31T23:59:59.5+02:00", "2026-01-31T10:00:00,5", "2026-01-31T10:00:00.1234567",
    "2026-01-31T10:00:00.000000", "2026-01-31T10:00:00-00:00", "2026-01-31T10:00:00-05:30",
    "2026-01-31T10:00:00+05:30:15", "2026-01-31T10:00:00.123+05:30:15.25", "2026-01-31T10:00+01",
    "9999-11-30", "9999-12-01", "0000-01-01", "2026-13-01", "2026-02-30", "2026-01-31T24:00",
    "2026-01-31T23:59:60", "2026-01-31T10:00:00+24:00", "31.01.2026", "garbage", "",
]


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def _rows(db, sql: str) -> list:
    return [dict(row) for row in db.query(sql)]


def _state(db) -> dict:
    return {
        "data_subject_request": _rows(db, "SELECT * FROM data_subject_request ORDER BY id"),
        "audit": _rows(db, "SELECT at, actor, action, detail, owner_user_id, actor_user_id, "
                           "impersonator_user_id FROM audit ORDER BY id"),
        "alert": _rows(db, "SELECT id, dedupe_key, resolved_at FROM alert ORDER BY id"),
    }


def _one_month(dsr) -> list:
    out = []
    for value in ONE_MONTH:
        try:
            due = dsr.one_month_later(value)
        except ValueError:
            due = "error"
        out.append([value, due])
    return out


def render() -> str:
    """Seed a fresh database, post every step, and return the golden JSON text."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app import access, auth, db, dsr, security
    from app.routes import privacy_requests

    db.init_db()
    _seed(db)
    current = {}
    real_login, real_get = auth.require_login, dsr.get

    def fake_login(request):
        account, workspace = current["account"], current["workspace"]
        if account == 0:
            return real_login(request)
        username = db.query_one("SELECT username FROM user_account WHERE id = ?", (account,))[0]
        db.set_current_actor(account, username, impersonating=account != workspace)
        db.set_current_owner(workspace)
        return None

    def pg_get(request_id):
        if abs(request_id) > INT64_MAX:
            return None
        return real_get(request_id)

    saved = (db.utcnow, auth.require_login, access.owner_id, dsr.get)
    db.utcnow = lambda: NOW
    auth.require_login = fake_login
    access.owner_id = lambda request: current["workspace"]
    dsr.get = pg_get
    try:
        app = FastAPI()
        app.include_router(privacy_requests.router)
        app.dependency_overrides[security.protect_host_post] = lambda: None
        client = TestClient(app, raise_server_exceptions=False)
        strict = FastAPI()
        strict.include_router(privacy_requests.router)
        strict_client = TestClient(strict, raise_server_exceptions=False)
        steps = []
        for name, actor, lang, path, body in STEPS:
            current.update(actor)
            headers = {"Content-Type": FORM}
            cookies = [f"ubyhost_lang={lang}"] if lang else []
            sent, use = body, client
            if CSRF_MARK in body:
                token = security._csrf_serializer().dumps(
                    {"nonce": security._nonce_binding(CSRF_COOKIE_VALUE)})
                sent = body.replace(CSRF_MARK, token)
                cookies.append(f"{security.CSRF_COOKIE}={CSRF_COOKIE_VALUE}")
                use = strict_client
            if cookies:
                headers["Cookie"] = "; ".join(cookies)
            response = use.request(
                "POST", path, content=sent.encode("utf-8"), headers=headers, follow_redirects=False
            )
            steps.append({
                "name": name,
                "account": actor["account"],
                "workspace": actor["workspace"],
                "lang": lang,
                "path": path,
                "body": body,
                "status": response.status_code,
                "location": response.headers.get("location", ""),
                "response": "" if response.status_code == 303 else response.text,
                "state": _state(db),
            })
    finally:
        db.utcnow, auth.require_login, access.owner_id, dsr.get = saved
    listed = {
        str(owner): [row["id"] for row in dsr.list_for_owner(owner)] for owner in (1, 2, None)
    }
    golden = {
        "list_for_owner": listed,
        "now": NOW,
        "seed": SEED,
        "steps": steps,
        "one_month_later": _one_month(dsr),
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "privacy_requests_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
````

## App/scripts/privacy_requests_page_golden.py

create: the page golden

````python path=App/scripts/privacy_requests_page_golden.py
"""Write go/internal/web/privacy/testdata/privacy_requests_page_golden.json (brief 1371).

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/privacy_requests_page_golden.py

It seeds a throwaway SQLite database with SEED, mounts the real
routes/privacy_requests.py router on a bare FastAPI app and GETs
/privacy-requests once per CASES entry, with require_login replaced by one that
sets the case's actor and owner the way the real one does. Per case it records
the status, the <title> text and the page region: from <div class="ui-page"
up to the page skeleton, with every _csrf value replaced by CSRF. The shell
around it is brief 1380's golden. It also records validation.fmt_date (the
date_cz filter) for each DATE_CZ input. go/internal/web/privacy/page_test.go
seeds PostgreSQL from the same file, signs in for real, renders the Go page and
compares the text, tags and attributes of both regions.
App/tests/test_go_privacy_requests.py fails when this file is stale.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "privacy" / "testdata" / "privacy_requests_page_golden.json"

STAMP = "2026-09-01T00:00:00+00:00"
NOTE = "Sent <b>\"export\"</b> & 'zip' + 1"

SEED = [
    {
        "table": "user_account",
        "columns": ["id", "username", "password_hash", "role", "active", "session_version", "created_at"],
        "rows": [
            [1, "owner@example.test", "x", "host", 1, 1, STAMP],
            [2, "other@example.test", "x", "host", 1, 1, STAMP],
        ],
    },
    {
        "table": "legal_acceptance",
        "columns": ["id", "user_account_id", "document", "version", "accepted_at", "method"],
        "rows": [
            [101, 1, "terms", "t1", STAMP, "clickwrap"],
            [102, 1, "privacy", "p1", STAMP, "clickwrap"],
            [103, 1, "dpa", "d1", STAMP, "clickwrap"],
            [104, 2, "terms", "t1", STAMP, "clickwrap"],
            [105, 2, "privacy", "p1", STAMP, "clickwrap"],
            [106, 2, "dpa", "d1", STAMP, "clickwrap"],
        ],
    },
    {
        "table": "apartment",
        "columns": ["id", "owner_user_id", "internal_name", "created_at"],
        "rows": [[1, 1, "Byt A", STAMP]],
    },
    {
        "table": "reservation",
        "columns": ["id", "apartment_id", "source", "uid", "date_from", "date_to",
                    "status", "created_at", "updated_at"],
        "rows": [[1, 1, "manual", "r1", "2026-10-01", "2026-10-03", "active", STAMP, STAMP]],
    },
    {
        "table": "guest",
        "columns": ["id", "reservation_id", "created_at", "updated_at"],
        "rows": [[7, 1, STAMP, STAMP]],
    },
    {
        "table": "data_subject_request",
        "columns": ["id", "owner_user_id", "received_at", "due_at", "channel", "request_type",
                    "subject_kind", "guest_id", "identity_checked_at", "status", "closed_at",
                    "outcome_note", "created_at", "updated_at"],
        "rows": [
            [60, 1, "2026-01-31T00:00:00+00:00", "2026-02-28T00:00:00+00:00", "email", "access",
             "guest", 7, None, "open", None, None, STAMP, STAMP],
            [61, 1, "2026-03-31T23:15:00+02:00", "2026-04-30T23:15:00+02:00", "post", "erasure",
             "guest", None, STAMP, "fulfilled", STAMP, NOTE, STAMP, STAMP],
            [62, 1, "2026-12-31 08:00", "2027-01-31 08:00", "support", "portability",
             "other", None, None, "extended", None, "", STAMP, STAMP],
            [63, 1, "garbage", "nonsense-due", "other", "other", "host_user", None, None,
             "refused", STAMP, "Žádost zamítnuta", STAMP, STAMP],
            [64, 1, "2026-02-30T10:00:00+00:00", "2026-06-15T22:30:00Z", "in_person",
             "objection", "guest", None, STAMP, "withdrawn", STAMP, None, STAMP, STAMP],
            [65, None, STAMP, STAMP, "email", "access", "guest", None, None, "open", None,
             None, STAMP, STAMP],
        ],
    },
]

# Each case: name, account, workspace, language cookie.
CASES = [
    ["owner_en", 1, 1, "en"],
    ["owner_cs", 1, 1, "cs"],
    ["empty_vi", 2, 2, "vi"],
]

DATE_CZ = [
    "2026-01-31", "2026-01-31T00:00:00+00:00", "2026-1-5", "2026-01-5x", "2026-02-30",
    "2026-13-01", "0000-01-01", "2026-01- 5", "26-01-31", "garbage", "", "2026-12-31 08:00",
]

REGION = re.compile(r'<div class="ui-page".*?(?=<div class="page-skeleton")', re.S)
CSRF_VALUE = re.compile(r'(name="_csrf" value=")[^"]*(")')
TITLE = re.compile(r"<title>(.*?)</title>", re.S)


def _seed(db) -> None:
    for table in SEED:
        cols = ", ".join(table["columns"])
        marks = ", ".join("?" for _ in table["columns"])
        for row in table["rows"]:
            db.execute(f"INSERT INTO {table['table']} ({cols}) VALUES ({marks})", row)


def render() -> str:
    """Seed a fresh database, GET the page for every case, and return the golden JSON text."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app import access, auth, db, validation
    from app.routes import privacy_requests

    db.init_db()
    _seed(db)
    current = {}

    def fake_login(request):
        account, workspace = current["account"], current["workspace"]
        username = db.query_one("SELECT username FROM user_account WHERE id = ?", (account,))[0]
        db.set_current_actor(account, username, impersonating=account != workspace)
        db.set_current_owner(workspace)
        return None

    saved = (auth.require_login, access.owner_id)
    auth.require_login = fake_login
    access.owner_id = lambda request: current["workspace"]
    try:
        app = FastAPI()
        app.include_router(privacy_requests.router)
        client = TestClient(app, raise_server_exceptions=False)
        cases = []
        for name, account, workspace, lang in CASES:
            current.update(account=account, workspace=workspace)
            response = client.get("/privacy-requests", headers={"Cookie": f"ubyhost_lang={lang}"})
            region = REGION.search(response.text)
            title = TITLE.search(response.text)
            cases.append({
                "name": name,
                "account": account,
                "workspace": workspace,
                "lang": lang,
                "status": response.status_code,
                "title": title[1].strip() if title else "",
                "region": CSRF_VALUE.sub(r"\1CSRF\2", region[0]) if region else "",
            })
    finally:
        auth.require_login, access.owner_id = saved
    golden = {
        "seed": SEED,
        "cases": cases,
        "date_cz": [[value, validation.fmt_date(value)] for value in DATE_CZ],
    }
    return json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "privacy_requests_page_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main()
````

## App/tests/test_go_privacy_requests.py

edit (full file): plus the page golden freshness test

````python path=App/tests/test_go_privacy_requests.py
"""go/internal/web/privacy reads three generated files; each must match the Python."""

import importlib.util
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
PRIVACY_DIR = APP_DIR.parent / "go" / "internal" / "web" / "privacy"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, APP_DIR / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.sqlite_only
def test_privacy_requests_golden_matches_python_routes(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "privacy-requests-golden.sqlite3")
    generator = _load("privacy_requests_golden")
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"name"') >= 25


@pytest.mark.sqlite_only
def test_privacy_requests_page_golden_matches_python_page(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "privacy-requests-page-golden.sqlite3")
    generator = _load("privacy_requests_page_golden")
    committed = generator.OUT.read_bytes()
    assert generator.render().encode("utf-8") == committed
    assert committed.count(b'"region"') >= 3


def test_privacy_catalog_matches_host_i18n():
    # Also checked by go_host_i18n.py --check once it globs nested packages (brief 1380).
    generator = _load("go_host_i18n")
    keys = PRIVACY_DIR / "i18n_keys.txt"
    current = (PRIVACY_DIR / "i18n.json").read_text(encoding="utf-8")
    assert generator.render(generator.read_keys(keys)) == current
````
