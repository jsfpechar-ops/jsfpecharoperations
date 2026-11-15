package ttlock

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"
)

// Every value here is invented. No test reaches the real TTLock API: the client
// points at an httptest server, and the account store and budget are in-memory fakes.

var fixedNow = time.Date(2026, 11, 15, 10, 0, 0, 0, time.UTC)

const thirtyDays = 2592000 // expires_in TTLock sends for a month-long token

// fakeTTLock records every form POST and answers with reply(path, form).
type fakeTTLock struct {
	srv  *httptest.Server
	mu   sync.Mutex
	reqs []recorded
}

type recorded struct {
	path string
	form url.Values
}

func newFakeTTLock(t *testing.T, reply func(path string, form url.Values) string) *fakeTTLock {
	t.Helper()
	f := &fakeTTLock{}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := r.ParseForm(); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		f.mu.Lock()
		f.reqs = append(f.reqs, recorded{path: r.URL.Path, form: r.PostForm})
		f.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, reply(r.URL.Path, r.PostForm))
	}))
	t.Cleanup(f.srv.Close)
	return f
}

func (f *fakeTTLock) forms(path string) []url.Values {
	f.mu.Lock()
	defer f.mu.Unlock()
	var out []url.Values
	for _, r := range f.reqs {
		if r.path == path {
			out = append(out, r.form)
		}
	}
	return out
}

func (f *fakeTTLock) hits(path string) int { return len(f.forms(path)) }

func (f *fakeTTLock) total() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return len(f.reqs)
}

func respond(v any) string {
	b, _ := json.Marshal(v)
	return string(b)
}

// memStore is the lock_account table in memory.
type memStore struct {
	mu   sync.Mutex
	next int64
	rows map[int64]*Account
}

func newMemStore() *memStore { return &memStore{rows: map[int64]*Account{}} }

// row returns a copy of the stored row, or nil.
func (s *memStore) row(id int64) *Account {
	s.mu.Lock()
	defer s.mu.Unlock()
	r, ok := s.rows[id]
	if !ok {
		return nil
	}
	cp := *r
	return &cp
}

func (s *memStore) Load(_ context.Context, id int64) (*Account, error) { return s.row(id), nil }

func (s *memStore) ForOwner(_ context.Context, owner int64) (*Account, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, r := range s.rows {
		if r.OwnerUserID == owner {
			cp := *r
			return &cp, nil
		}
	}
	return nil, nil
}

func (s *memStore) Insert(_ context.Context, owner int64, username, password string, _ time.Time) (int64, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.next++
	s.rows[s.next] = &Account{ID: s.next, OwnerUserID: owner, Username: username, Password: password, Status: AccountStatusOK}
	return s.next, nil
}

func setTokens(r *Account, rec TokenRecord) {
	r.AccessToken = rec.AccessToken
	r.RefreshToken = rec.RefreshToken
	r.ExpiresAt = rec.ExpiresAt
}

func (s *memStore) SaveLogin(_ context.Context, id int64, rec TokenRecord, _ time.Time) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	r, ok := s.rows[id]
	if !ok {
		return errors.New("no row")
	}
	setTokens(r, rec)
	r.TokenVersion++
	return nil
}

func (s *memStore) SaveRefresh(_ context.Context, id, expect int64, rec TokenRecord, _ time.Time) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	r, ok := s.rows[id]
	if !ok {
		return false, errors.New("no row")
	}
	if r.TokenVersion != expect {
		return false, nil
	}
	setTokens(r, rec)
	r.TokenVersion++
	return true, nil
}

func (s *memStore) SetStatus(_ context.Context, id int64, status string, _ time.Time) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	r, ok := s.rows[id]
	if !ok {
		return errors.New("no row")
	}
	r.Status = status
	return nil
}

func (s *memStore) SaveLocks(_ context.Context, id int64, raw []byte, _ time.Time) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	r, ok := s.rows[id]
	if !ok {
		return errors.New("no row")
	}
	r.LocksJSON = append([]byte(nil), raw...)
	return nil
}

func (s *memStore) Delete(_ context.Context, id int64) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.rows, id)
	return nil
}

// seedToken puts a row with a 30-day token into the store and returns its id.
func seedToken(s *memStore, accessToken string) int64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.next++
	s.rows[s.next] = &Account{
		ID:           s.next,
		OwnerUserID:  7,
		Username:     "ttlock-test-user",
		Password:     "invented-password",
		Status:       AccountStatusOK,
		AccessToken:  accessToken,
		RefreshToken: "invented-refresh",
		ExpiresAt:    fixedNow.Add(30 * 24 * time.Hour),
		TokenVersion: 1,
	}
	return s.next
}

// memBudget is a budget that answers from a fixed flag and records what it was asked.
type memBudget struct {
	allow      bool
	counted    int
	priorities []string
}

func (b *memBudget) Allows(_ context.Context, priority string) (bool, error) {
	b.priorities = append(b.priorities, priority)
	return b.allow, nil
}

func (b *memBudget) Count(_ context.Context) error {
	b.counted++
	return nil
}

func buildClient(f *fakeTTLock, store AccountStore, budget Budget, enabled bool) *Client {
	cfg := Config{
		DoorCodesEnabled: enabled,
		APIBase:          f.srv.URL,
		ClientID:         "test-client",
		ClientSecret:     "test-secret",
		MonthlyCalls:     30000,
	}
	return New(cfg, Options{
		HTTP:     f.srv.Client(),
		Accounts: store,
		Budget:   budget,
		Now:      func() time.Time { return fixedNow },
	})
}

func newTestClient(f *fakeTTLock, store AccountStore) *Client {
	return buildClient(f, store, &memBudget{allow: true}, true)
}

func entries(from, to int, name string) []any {
	var out []any
	for i := from; i <= to; i++ {
		out = append(out, map[string]any{"keyboardPwdName": name, "keyboardPwdId": i, "startDate": 0, "endDate": 0})
	}
	return out
}

func TestMD5PasswordIsLowercaseHex(t *testing.T) {
	if got := md5Password("abc"); got != "900150983cd24fb0d6963f7d28e17f72" {
		t.Fatalf("md5 = %s", got)
	}
}

func TestSignedRequestsCarryClientFieldsAndDate(t *testing.T) {
	f := newFakeTTLock(t, func(string, url.Values) string { return respond(map[string]any{"errcode": 0}) })
	c := newTestClient(f, newMemStore())
	ctx := context.Background()
	wantDate := strconv.FormatInt(fixedNow.UnixMilli(), 10)
	cases := []struct {
		path       string
		wantSecret bool
		wantDate   bool
	}{
		{"/oauth2/token", true, false},
		{"/v3/user/register", true, true},
		{"/v3/user/delete", true, true},
		{"/v3/key/list", false, true},
	}
	for _, tc := range cases {
		if _, err := c.post(context.Background(), tc.path, map[string]any{"pageNo": 1}, PriorityLow); err != nil {
			t.Fatalf("%s: %v", tc.path, err)
		}
		form := f.forms(tc.path)[0]
		if form.Get("clientId") != "test-client" {
			t.Errorf("%s: clientId = %q", tc.path, form.Get("clientId"))
		}
		if form.Has("clientSecret") != tc.wantSecret || (tc.wantSecret && form.Get("clientSecret") != "test-secret") {
			t.Errorf("%s: clientSecret presence wrong", tc.path)
		}
		if form.Has("date") != tc.wantDate || (tc.wantDate && form.Get("date") != wantDate) {
			t.Errorf("%s: date = %q", tc.path, form.Get("date"))
		}
		if form.Get("pageNo") != "1" {
			t.Errorf("%s: caller field lost", tc.path)
		}
	}
	_ = ctx
}

func TestCreateAccountRegistersWithMD5AndLogsIn(t *testing.T) {
	f := newFakeTTLock(t, func(path string, _ url.Values) string {
		switch path {
		case "/v3/user/register":
			return respond(map[string]any{"errcode": 0, "username": "ttlock-test-user"})
		case "/oauth2/token":
			return respond(map[string]any{"errcode": 0, "access_token": "acc-1", "refresh_token": "ref-1", "expires_in": thirtyDays})
		}
		return respond(map[string]any{"errcode": 0})
	})
	store := newMemStore()
	c := newTestClient(f, store)
	ctx := context.Background()

	id, err := c.CreateAccount(ctx, 7)
	if err != nil {
		t.Fatal(err)
	}
	row := store.row(id)
	if row.Username != "ttlock-test-user" || row.TokenVersion != 1 || row.AccessToken != "acc-1" {
		t.Fatalf("row after create: %+v", row)
	}
	if len(row.Password) != 24 {
		t.Fatalf("password length %d, want 24 (token_urlsafe(18))", len(row.Password))
	}
	if !row.ExpiresAt.Equal(fixedNow.Add(30 * 24 * time.Hour)) {
		t.Fatalf("expires_at = %s", row.ExpiresAt)
	}
	reg := f.forms("/v3/user/register")[0]
	if name := reg.Get("username"); !strings.HasPrefix(name, "uh") || len(name) != 18 {
		t.Fatalf("register username %q, want uh + 16 hex", name)
	}
	if reg.Get("password") != md5Password(row.Password) || strings.Contains(reg.Get("password"), row.Password) {
		t.Fatal("register must send the md5 of the password, never the password")
	}
	login := f.forms("/oauth2/token")[0]
	if login.Get("username") != "ttlock-test-user" || login.Get("password") != md5Password(row.Password) {
		t.Fatalf("login form %v", login)
	}

	again, err := c.CreateAccount(ctx, 7)
	if err != nil || again != id || f.hits("/v3/user/register") != 1 {
		t.Fatalf("second create must reuse the row: id=%d err=%v registers=%d", again, err, f.hits("/v3/user/register"))
	}
}

func TestCachedTokenUsedUntilSevenDaysBeforeExpiry(t *testing.T) {
	f := newFakeTTLock(t, func(path string, _ url.Values) string {
		return respond(map[string]any{"errcode": 0, "list": []any{}, "pages": 1})
	})
	store := newMemStore()
	id := seedToken(store, "cached")
	c := newTestClient(f, store)
	if _, _, err := c.CheckLocks(context.Background(), id); err != nil {
		t.Fatal(err)
	}
	if got := f.forms("/v3/key/list")[0].Get("accessToken"); got != "cached" {
		t.Fatalf("accessToken = %q", got)
	}
	if f.hits("/oauth2/token") != 0 {
		t.Fatal("a token 30 days from expiry must not be refreshed")
	}
}

func TestTokenRefreshedNearExpiry(t *testing.T) {
	f := newFakeTTLock(t, func(path string, form url.Values) string {
		switch path {
		case "/oauth2/token":
			return respond(map[string]any{"errcode": 0, "access_token": "new-acc", "refresh_token": "new-ref", "expires_in": thirtyDays})
		}
		return respond(map[string]any{"errcode": 0, "list": []any{}, "pages": 1})
	})
	store := newMemStore()
	id := seedToken(store, "old")
	store.rows[id].ExpiresAt = fixedNow.Add(3 * 24 * time.Hour)
	store.rows[id].RefreshToken = "old-ref"
	c := newTestClient(f, store)

	if _, _, err := c.CheckLocks(context.Background(), id); err != nil {
		t.Fatal(err)
	}
	tok := f.forms("/oauth2/token")[0]
	if tok.Get("grant_type") != "refresh_token" || tok.Get("refresh_token") != "old-ref" || tok.Has("password") {
		t.Fatalf("refresh form %v", tok)
	}
	if got := f.forms("/v3/key/list")[0].Get("accessToken"); got != "new-acc" {
		t.Fatalf("list used %q, want the refreshed token", got)
	}
	row := store.row(id)
	if row.TokenVersion != 2 || row.RefreshToken != "new-ref" || row.Password != "invented-password" {
		t.Fatalf("row after refresh: %+v", row)
	}
}

func TestRefreshReauthFallsBackToPasswordLogin(t *testing.T) {
	f := newFakeTTLock(t, func(path string, form url.Values) string {
		switch {
		case path == "/oauth2/token" && form.Get("grant_type") == "refresh_token":
			return respond(map[string]any{"errcode": 10011, "errmsg": "invented"})
		case path == "/oauth2/token":
			return respond(map[string]any{"errcode": 0, "access_token": "login-acc", "refresh_token": "login-ref", "expires_in": thirtyDays})
		}
		return respond(map[string]any{"errcode": 0, "list": []any{}, "pages": 1})
	})
	store := newMemStore()
	id := seedToken(store, "old")
	store.rows[id].ExpiresAt = fixedNow.Add(time.Hour)
	c := newTestClient(f, store)
	if _, _, err := c.CheckLocks(context.Background(), id); err != nil {
		t.Fatal(err)
	}
	toks := f.forms("/oauth2/token")
	if len(toks) != 2 || !toks[1].Has("password") {
		t.Fatalf("expected refresh then password login, got %d token calls", len(toks))
	}
	if got := f.forms("/v3/key/list")[0].Get("accessToken"); got != "login-acc" {
		t.Fatalf("list used %q", got)
	}
}

func TestFailedLoginMarksAccountReauthNeeded(t *testing.T) {
	f := newFakeTTLock(t, func(path string, form url.Values) string {
		if path == "/oauth2/token" {
			if form.Get("grant_type") == "refresh_token" {
				return respond(map[string]any{"errcode": 10011})
			}
			return respond(map[string]any{"errcode": 10007, "errmsg": "invented"})
		}
		return respond(map[string]any{"errcode": 0})
	})
	store := newMemStore()
	id := seedToken(store, "old")
	store.rows[id].ExpiresAt = fixedNow.Add(time.Hour)
	c := newTestClient(f, store)
	ctx := context.Background()

	if _, _, err := c.CheckLocks(ctx, id); !IsKind(err, KindLogin) {
		t.Fatalf("first call: %v", err)
	}
	if store.row(id).Status != AccountStatusReauthNeeded {
		t.Fatal("status must become reauth_needed")
	}
	if _, _, err := c.CheckLocks(ctx, id); !IsKind(err, KindReauth) {
		t.Fatalf("second call: %v", err)
	}
	if f.hits("/v3/key/list") != 0 {
		t.Fatal("no lock call may go out once the account needs a new login")
	}
}

func TestAuthErrorRefreshesAndRetriesOnce(t *testing.T) {
	f := newFakeTTLock(t, func(path string, form url.Values) string {
		switch path {
		case "/oauth2/token":
			return respond(map[string]any{"errcode": 0, "access_token": "fresh-acc", "refresh_token": "fresh-ref", "expires_in": thirtyDays})
		case "/v3/key/list":
			if form.Get("accessToken") == "stale" {
				return respond(map[string]any{"errcode": 10003, "errmsg": "invented"})
			}
			return respond(map[string]any{"errcode": 0, "list": []any{}, "pages": 1})
		}
		return respond(map[string]any{"errcode": 0})
	})
	store := newMemStore()
	id := seedToken(store, "stale")
	c := newTestClient(f, store)
	if _, _, err := c.CheckLocks(context.Background(), id); err != nil {
		t.Fatal(err)
	}
	lists := f.forms("/v3/key/list")
	if len(lists) != 2 || lists[1].Get("accessToken") != "fresh-acc" {
		t.Fatalf("expected one retry with the fresh token, got %d list calls", len(lists))
	}
	if store.row(id).AccessToken != "fresh-acc" {
		t.Fatal("fresh token not stored")
	}
}

func TestErrorKindsAndRetryFlags(t *testing.T) {
	cases := []struct {
		code  int
		kind  string
		retry bool
	}{
		{10003, KindAuth, false},
		{10011, KindReauth, false},
		{30007, KindBudget, true},
		{-1007, KindCodeMissing, true},
		{-1026, KindPeriodTaken, false},
		{-4037, KindLockSetup, true},
		{-2012, KindOffline, true},
		{-3, KindBug, false},
		{80000, KindClock, false},
		{-4063, KindConfig, false},
		{999999, KindTransient, true},
	}
	for _, tc := range cases {
		t.Run(strconv.Itoa(tc.code), func(t *testing.T) {
			f := newFakeTTLock(t, func(string, url.Values) string {
				return respond(map[string]any{"errcode": tc.code, "errmsg": "invented"})
			})
			c := newTestClient(f, newMemStore())
			_, err := c.post(context.Background(), "/v3/key/list", nil, PriorityLow)
			te, ok := AsError(err)
			if !ok {
				t.Fatalf("not a TTLockError: %v", err)
			}
			if te.Code != tc.code || te.Kind != tc.kind || te.Retryable() != tc.retry || te.Unknown {
				t.Fatalf("got code=%d kind=%s retry=%v unknown=%v", te.Code, te.Kind, te.Retryable(), te.Unknown)
			}
		})
	}
}

func TestErrorMessageIsCutTo200Characters(t *testing.T) {
	f := newFakeTTLock(t, func(string, url.Values) string {
		return respond(map[string]any{"errcode": 10000, "errmsg": strings.Repeat("e", 300)})
	})
	_, err := newTestClient(f, newMemStore()).post(context.Background(), "/v3/key/list", nil, PriorityLow)
	te, _ := AsError(err)
	if te == nil || len([]rune(te.Message)) != 200 {
		t.Fatalf("message length: %+v", te)
	}
}

func TestNetworkDropIsUnknownResult(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if conn, _, err := w.(http.Hijacker).Hijack(); err == nil {
			_ = conn.Close()
		}
	}))
	t.Cleanup(srv.Close)
	cfg := Config{DoorCodesEnabled: true, APIBase: srv.URL, ClientID: "test-client", ClientSecret: "test-secret"}
	c := New(cfg, Options{HTTP: srv.Client(), Budget: &memBudget{allow: true}})
	_, err := c.post(context.Background(), "/v3/key/list", nil, PriorityLow)
	te, ok := AsError(err)
	if !ok || te.Kind != KindNetwork || !te.Unknown || !te.Retryable() {
		t.Fatalf("dropped connection: %+v", te)
	}
}

func TestNonJSONAnswerIsUnknownResult(t *testing.T) {
	f := newFakeTTLock(t, func(string, url.Values) string { return "<html>maintenance</html>" })
	_, err := newTestClient(f, newMemStore()).post(context.Background(), "/v3/key/list", nil, PriorityLow)
	te, ok := AsError(err)
	if !ok || te.Kind != KindNetwork || !te.Unknown {
		t.Fatalf("non-json: %+v", te)
	}
}

func TestDisabledAndBudgetRefuseBeforeSending(t *testing.T) {
	f := newFakeTTLock(t, func(string, url.Values) string { return respond(map[string]any{"errcode": 0}) })
	ctx := context.Background()

	off := buildClient(f, newMemStore(), &memBudget{allow: true}, false)
	if _, err := off.post(ctx, "/v3/key/list", nil, PriorityLow); !IsKind(err, KindDisabled) {
		t.Fatalf("disabled: %v", err)
	}
	if off.Enabled() {
		t.Fatal("Enabled must be false when door codes are off")
	}

	budget := &memBudget{allow: false}
	refused := buildClient(f, newMemStore(), budget, true)
	if _, err := refused.post(ctx, "/v3/key/list", nil, PriorityCritical); !IsKind(err, KindBudget) {
		t.Fatalf("budget: %v", err)
	}
	if budget.counted != 0 || f.total() != 0 {
		t.Fatalf("a refused call must not be counted or sent (counted=%d sent=%d)", budget.counted, f.total())
	}

	allowed := &memBudget{allow: true}
	ok := buildClient(f, newMemStore(), allowed, true)
	if _, err := ok.post(ctx, "/v3/key/list", nil, PriorityLow); err != nil {
		t.Fatal(err)
	}
	if allowed.counted != 1 || allowed.priorities[0] != PriorityLow || !ok.Enabled() {
		t.Fatalf("a sent call is counted once with its priority: %+v", allowed)
	}
}

func TestPathWhitelistAndTimeouts(t *testing.T) {
	f := newFakeTTLock(t, func(string, url.Values) string { return respond(map[string]any{"errcode": 0}) })
	_, err := newTestClient(f, newMemStore()).post(context.Background(), "/v3/lock/unlock", nil, PriorityLow)
	if !errors.Is(err, ErrPathNotAllowed) || f.total() != 0 {
		t.Fatalf("path guard: %v sent=%d", err, f.total())
	}
	want := map[string]time.Duration{
		"/v3/keyboardPwd/add":      35 * time.Second,
		"/v3/keyboardPwd/change":   35 * time.Second,
		"/v3/keyboardPwd/delete":   35 * time.Second,
		"/v3/lock/queryDate":       35 * time.Second,
		"/v3/lock/updateDate":      35 * time.Second,
		"/v3/keyboardPwd/get":      5 * time.Second,
		"/v3/lock/listKeyboardPwd": 5 * time.Second,
		"/v3/key/list":             5 * time.Second,
		"/oauth2/token":            5 * time.Second,
	}
	for path, d := range want {
		if got := timeoutFor(path); got != d {
			t.Errorf("%s: timeout %s, want %s", path, got, d)
		}
	}
}

func TestConfigFromEnvNames(t *testing.T) {
	env := map[string]string{
		"UBYHOST_DOOR_CODES":           "yes",
		"UBYHOST_TTLOCK_CLIENT_ID":     " test-client ",
		"UBYHOST_TTLOCK_CLIENT_SECRET": "test-secret",
		"UBYHOST_TTLOCK_API_BASE":      "https://api.example.test/",
		"UBYHOST_TTLOCK_MONTHLY_CALLS": "1000",
	}
	cfg, err := ConfigFromEnv(func(k string) string { return env[k] })
	if err != nil {
		t.Fatal(err)
	}
	if !cfg.DoorCodesEnabled || cfg.ClientID != "test-client" || cfg.APIBase != "https://api.example.test" || cfg.MonthlyCalls != 1000 {
		t.Fatalf("config %+v", cfg)
	}
	if _, err := ConfigFromEnv(func(k string) string {
		if k == "UBYHOST_TTLOCK_MONTHLY_CALLS" {
			return "lots"
		}
		return ""
	}); err == nil {
		t.Fatal("a non-number call limit must fail")
	}
	def, _ := ConfigFromEnv(func(string) string { return "" })
	if def.DoorCodesEnabled || def.APIBase != defaultAPIBase || def.MonthlyCalls != 30000 {
		t.Fatalf("defaults %+v", def)
	}
}

func TestStayWindowUsesPragueWallClock(t *testing.T) {
	start, end, err := StayWindow("2026-11-15", "2026-11-16", 14, 10, 0)
	if err != nil {
		t.Fatal(err)
	}
	if start != time.Date(2026, 11, 15, 13, 0, 0, 0, time.UTC).UnixMilli() ||
		end != time.Date(2026, 11, 16, 9, 0, 0, 0, time.UTC).UnixMilli() {
		t.Fatalf("window %d..%d", start, end)
	}
	start, end, err = StayWindow("2026-11-15", "2026-11-16", 14, 10, 2)
	if err != nil {
		t.Fatal(err)
	}
	if start != time.Date(2026, 11, 15, 11, 0, 0, 0, time.UTC).UnixMilli() ||
		end != time.Date(2026, 11, 16, 11, 0, 0, 0, time.UTC).UnixMilli() {
		t.Fatalf("buffered window %d..%d", start, end)
	}
	if _, _, err := StayWindow("2026-11-15", "2026-11-16", 14, 10, -1); !errors.Is(err, ErrBufferHours) {
		t.Fatalf("negative buffer: %v", err)
	}
	if _, _, err := StayWindow("2026-11-15", "2026-11-16", 24, 10, 0); !errors.Is(err, ErrHour) {
		t.Fatalf("hour 24: %v", err)
	}
	if _, _, err := StayWindow("2026-11-15", "2026-11-15", 14, 9, 0); !errors.Is(err, ErrWindow) {
		t.Fatalf("empty window: %v", err)
	}
}

func TestWholeHourAndPermanentPIN(t *testing.T) {
	if !errors.Is(wholeHour(1000), ErrWholeHour) || wholeHour(3_600_000) != nil {
		t.Fatal("whole hour check")
	}
	f := newFakeTTLock(t, func(string, url.Values) string { return respond(map[string]any{"errcode": 0, "keyboardPwdId": 77}) })
	c := newTestClient(f, newMemStore())
	ctx := context.Background()
	for _, bad := range []string{"12a4", "123", "1234567890", ""} {
		if _, err := c.AddPermanentCode(ctx, 1, "123", bad, "invented"); !errors.Is(err, ErrInvalidPermanentPIN) {
			t.Fatalf("pin %q: %v", bad, err)
		}
	}
	if f.total() != 0 {
		t.Fatal("an invalid PIN must not be sent")
	}
	store := newMemStore()
	id := seedToken(store, "tok")
	c = newTestClient(f, store)
	got, err := c.AddPermanentCode(ctx, id, "123", "4321", "invented")
	if err != nil || got != "77" {
		t.Fatalf("permanent: %q %v", got, err)
	}
	form := f.forms("/v3/keyboardPwd/add")[0]
	if form.Get("keyboardPwdType") != "2" || form.Get("addType") != "2" || form.Get("keyboardPwd") != "4321" || form.Get("accessToken") != "tok" {
		t.Fatalf("permanent form %v", form)
	}
}

func TestAddCustomCodeRedrawsRefusedPIN(t *testing.T) {
	var mu sync.Mutex
	n := 0
	f := newFakeTTLock(t, func(path string, _ url.Values) string {
		mu.Lock()
		defer mu.Unlock()
		n++
		if n == 1 {
			return respond(map[string]any{"errcode": -3007, "errmsg": "invented"})
		}
		return respond(map[string]any{"errcode": 0, "keyboardPwdId": 501})
	})
	store := newMemStore()
	id := seedToken(store, "tok")
	c := newTestClient(f, store)
	pin, codeID, err := c.AddCustomCode(context.Background(), id, "123", 1_800_000_000_000, 1_800_086_400_000, "invented", PriorityNormal)
	if err != nil || codeID != "501" {
		t.Fatalf("add: %q %q %v", pin, codeID, err)
	}
	adds := f.forms("/v3/keyboardPwd/add")
	if len(adds) != 2 {
		t.Fatalf("want 2 add calls, got %d", len(adds))
	}
	first, second := adds[0].Get("keyboardPwd"), adds[1].Get("keyboardPwd")
	if first == second || pin != second {
		t.Fatalf("pins %q %q (returned %q)", first, second, pin)
	}
	for _, p := range []string{first, second} {
		v, err := strconv.Atoi(p)
		if err != nil || v < 1_000_000 || v > 9_999_999 {
			t.Fatalf("pin %q is not a 7-digit number", p)
		}
	}
	if adds[0].Get("addType") != "2" || adds[0].Get("keyboardPwdType") != "3" {
		t.Fatalf("add form %v", adds[0])
	}
}

func TestCreatePeriodCodeAndFindByName(t *testing.T) {
	const start, end = int64(1_800_000_000_000), int64(1_800_086_400_000)
	f := newFakeTTLock(t, func(path string, _ url.Values) string {
		switch path {
		case "/v3/keyboardPwd/get":
			return respond(map[string]any{"errcode": 0, "keyboardPwd": "123456", "keyboardPwdId": 9})
		case "/v3/lock/listKeyboardPwd":
			return respond(map[string]any{"errcode": 0, "pages": 1, "list": []any{
				map[string]any{"keyboardPwdName": "UH-70", "startDate": start, "endDate": end, "keyboardPwd": "111111", "keyboardPwdId": 4},
				map[string]any{"keyboardPwdName": "UH-7", "startDate": start, "endDate": end, "keyboardPwd": "654321", "keyboardPwdId": 6},
			}})
		}
		return respond(map[string]any{"errcode": 0})
	})
	store := newMemStore()
	id := seedToken(store, "tok")
	c := newTestClient(f, store)
	ctx := context.Background()

	pin, codeID, err := c.CreatePeriodCode(ctx, id, "123", start, end, "UH-7", PriorityNormal)
	if err != nil || pin != "123456" || codeID != "9" {
		t.Fatalf("create: %q %q %v", pin, codeID, err)
	}
	if f.forms("/v3/keyboardPwd/get")[0].Get("keyboardPwdType") != "3" {
		t.Fatal("period code must be type 3")
	}
	if _, _, err := c.CreatePeriodCode(ctx, id, "123", start+1, end, "UH-7", PriorityNormal); !errors.Is(err, ErrWholeHour) {
		t.Fatalf("non-whole start: %v", err)
	}

	pin, codeID, found, err := c.FindCodeByName(ctx, id, "123", "UH-7", start, end)
	if err != nil || !found || pin != "654321" || codeID != "6" {
		t.Fatalf("find: %q %q %v %v", pin, codeID, found, err)
	}
	_, _, found, err = c.FindCodeByName(ctx, id, "123", "UH-7", start, end+3_600_000)
	if err != nil || found {
		t.Fatalf("wrong window must not match: found=%v err=%v", found, err)
	}
}

func TestCodeIsListedPagesAndUnknowns(t *testing.T) {
	ctx := context.Background()
	run := func(t *testing.T, reply func(page int) string) (TriState, int, *fakeTTLock) {
		t.Helper()
		f := newFakeTTLock(t, func(path string, form url.Values) string {
			page, _ := strconv.Atoi(form.Get("pageNo"))
			return reply(page)
		})
		store := newMemStore()
		id := seedToken(store, "tok")
		c := newTestClient(f, store)
		state, err := c.CodeIsListed(ctx, id, "123", "UH-7", "42")
		if err != nil {
			t.Fatal(err)
		}
		return state, f.hits("/v3/lock/listKeyboardPwd"), f
	}

	// Page 1 is full with other ids; page 2 is short and holds id 42.
	page2 := append(entries(101, 102, "UH-7"), map[string]any{"keyboardPwdName": "UH-7", "keyboardPwdId": 42})
	state, calls, _ := run(t, func(page int) string {
		if page == 1 {
			return respond(map[string]any{"errcode": 0, "list": entries(1, 20, "UH-7")})
		}
		return respond(map[string]any{"errcode": 0, "list": page2})
	})
	if state != TriYes || calls != 2 {
		t.Fatalf("found on page 2: state=%d calls=%d", state, calls)
	}

	// Short first page without the id: the whole list was read, so it is a definite no.
	state, _, _ = run(t, func(int) string {
		return respond(map[string]any{"errcode": 0, "list": entries(1, 3, "UH-7")})
	})
	if state != TriNo {
		t.Fatalf("complete list without the id: state=%d", state)
	}

	// Five full pages and still no end: the list is incomplete, so the answer is unknown.
	state, calls, _ = run(t, func(int) string {
		return respond(map[string]any{"errcode": 0, "list": entries(1, 20, "UH-7")})
	})
	if state != TriUnknown || calls != ListMaxPages {
		t.Fatalf("page limit: state=%d calls=%d", state, calls)
	}

	// -1007 on any page is unknown, never empty.
	state, _, _ = run(t, func(int) string {
		return respond(map[string]any{"errcode": NoPasscodeDataCode, "errmsg": "invented"})
	})
	if state != TriUnknown {
		t.Fatalf("-1007 must be unknown: state=%d", state)
	}
}

func TestCodesNamedKeepsExactNames(t *testing.T) {
	f := newFakeTTLock(t, func(string, url.Values) string {
		list := append(entries(1, 2, "UH-7"), entries(3, 3, "UH-70")...)
		return respond(map[string]any{"errcode": 0, "list": list})
	})
	store := newMemStore()
	id := seedToken(store, "tok")
	kept, complete, err := newTestClient(f, store).CodesNamed(context.Background(), id, "123", "UH-7")
	if err != nil || !complete || len(kept) != 2 {
		t.Fatalf("codes named: %d complete=%v err=%v", len(kept), complete, err)
	}
}

func TestCheckLocksFiltersAndReadsAllPages(t *testing.T) {
	f := newFakeTTLock(t, func(_ string, form url.Values) string {
		if form.Get("pageNo") == "1" {
			return respond(map[string]any{"errcode": 0, "pages": 2, "list": []any{
				map[string]any{"keyStatus": "110401", "userType": "110301", "lockId": 111, "lockAlias": "Test door", "electricQuantity": 80, "timezoneRawOffset": 3600000, "endDate": 1900000000000},
				map[string]any{"keyStatus": "110401", "userType": "110201", "keyRight": 1, "lockId": 222, "lockName": "Gate"},
				map[string]any{"keyStatus": "110401", "userType": "110201", "keyRight": 0, "lockId": 333},
				map[string]any{"keyStatus": "110402", "userType": "110301", "lockId": 444},
			}})
		}
		return respond(map[string]any{"errcode": 0, "pages": 2, "list": []any{
			map[string]any{"keyStatus": "110401", "userType": "110301", "lockId": 555, "lockAlias": "", "lockName": "Back"},
		}})
	})
	store := newMemStore()
	id := seedToken(store, "tok")
	c := newTestClient(f, store)
	locks, plain, err := c.CheckLocks(context.Background(), id)
	if err != nil {
		t.Fatal(err)
	}
	if plain != 1 || len(locks) != 3 {
		t.Fatalf("plain=%d locks=%+v", plain, locks)
	}
	if locks[0].LockID != "111" || locks[0].Alias != "Test door" || locks[1].Alias != "Gate" || locks[2].Alias != "Back" {
		t.Fatalf("locks %+v", locks)
	}
	if f.hits("/v3/key/list") != 2 || f.forms("/v3/key/list")[0].Get("pageSize") != "1000" {
		t.Fatal("must read both pages with pageSize 1000")
	}
	stored, err := ParseLocks(store.row(id).LocksJSON)
	if err != nil || len(stored) != 3 || stored[0].LockID != "111" {
		t.Fatalf("stored locks %+v %v", stored, err)
	}
}

func TestChangeDeleteAndClockCarryTheirPriorities(t *testing.T) {
	f := newFakeTTLock(t, func(string, url.Values) string {
		return respond(map[string]any{"errcode": 0, "date": 1700000000000})
	})
	store := newMemStore()
	id := seedToken(store, "tok")
	budget := &memBudget{allow: true}
	c := buildClient(f, store, budget, true)
	ctx := context.Background()
	start, end := int64(1_800_000_000_000), int64(1_800_086_400_000)

	if err := c.ChangeCodePeriod(ctx, id, "123", "9", start, end, PriorityNormal); err != nil {
		t.Fatal(err)
	}
	if err := c.DeleteCode(ctx, id, "123", "9", PriorityCritical); err != nil {
		t.Fatal(err)
	}
	if ms, err := c.QueryLockTime(ctx, id, "123"); err != nil || ms != 1700000000000 {
		t.Fatalf("query time %d %v", ms, err)
	}
	if _, err := c.AdjustLockTime(ctx, id, "123"); err != nil {
		t.Fatal(err)
	}
	if got := f.forms("/v3/keyboardPwd/change")[0].Get("changeType"); got != "2" {
		t.Fatalf("changeType %q", got)
	}
	if got := f.forms("/v3/keyboardPwd/delete")[0].Get("deleteType"); got != "2" {
		t.Fatalf("deleteType %q", got)
	}
	want := []string{PriorityNormal, PriorityCritical, PriorityLow, PriorityNormal}
	if strings.Join(budget.priorities, ",") != strings.Join(want, ",") {
		t.Fatalf("priorities %v, want %v", budget.priorities, want)
	}
}

func TestDeleteAccountRemovesRowEvenWhenTTLockFails(t *testing.T) {
	f := newFakeTTLock(t, func(string, url.Values) string {
		return respond(map[string]any{"errcode": 10005, "errmsg": "invented"})
	})
	store := newMemStore()
	id := seedToken(store, "tok")
	c := newTestClient(f, store)
	ctx := context.Background()
	if err := c.DeleteAccount(ctx, id); !IsKind(err, KindPermission) {
		t.Fatalf("delete error: %v", err)
	}
	if store.row(id) != nil {
		t.Fatal("the row must go even when TTLock refuses the delete")
	}
	if err := c.DeleteAccount(ctx, id); err != nil {
		t.Fatalf("missing row is a no-op: %v", err)
	}
}
