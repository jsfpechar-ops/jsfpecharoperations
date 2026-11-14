package cleaning

import (
	"context"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
	"time"
)

// codeEnv is the golden database with door codes switched on for the lock
// actions: UBYHOST_DOOR_CODES, the app's TTLock credentials, no billing.
func codeEnv(t *testing.T, extra map[string]string) *hostEnv {
	t.Helper()
	g := loadGolden(t)
	pool := testPool(t)
	goldenSeed(t, pool, g)
	base := goldenEnv(g)
	getenv := func(k string) string {
		if v, ok := extra[k]; ok {
			return v
		}
		return base(k)
	}
	return hostEnvOn(t, g, pool, getenv)
}

type codeRow struct {
	ID                                    int64
	Source, State, Pin, Ref, LockID, Next string
	Attempts                              int64
	LockAccount                           *int64
}

func (e *hostEnv) code(id int64) codeRow {
	e.t.Helper()
	var r codeRow
	var pin, lock, next *string
	err := e.pool.QueryRow(context.Background(),
		`SELECT id, source, state, pin_enc, operation_ref, lock_id, next_attempt_at, attempts, lock_account_id FROM cleaning_code WHERE id = $1`, id).
		Scan(&r.ID, &r.Source, &r.State, &pin, &r.Ref, &lock, &next, &r.Attempts, &r.LockAccount)
	if err != nil {
		e.t.Fatalf("code %d: %v", id, err)
	}
	r.Pin, r.LockID, r.Next = "", str(lock), str(next)
	if pin != nil {
		r.Pin = notesOf(e.t, pin)
	}
	return r
}

func (e *hostEnv) property(apartment int64) (code, pending *int64) {
	e.t.Helper()
	if err := e.pool.QueryRow(context.Background(), `SELECT code_id, pending_code_id FROM cleaning_property WHERE apartment_id = $1`, apartment).Scan(&code, &pending); err != nil {
		e.t.Fatal(err)
	}
	return
}

func (e *hostEnv) maxCode() int64 {
	var id int64
	_ = e.pool.QueryRow(context.Background(), `SELECT MAX(id) FROM cleaning_code`).Scan(&id)
	return id
}

func (e *hostEnv) codePost(user *int64, apartment, action string, form map[string]string) *httptest.ResponseRecorder {
	return e.post(user, "/cleaning/properties/"+apartment+"/code/"+action, form)
}

// TestHostManualCode mirrors cleaning_codes.save_manual and _activate.
func TestHostManualCode(t *testing.T) {
	e := newHostEnv(t)
	// 14 has no cleaning_property row: it is created, the code is stored encrypted.
	rec := e.codePost(i64(1), "14", "manual", map[string]string{"code": "  A-1*#  "})
	if rec.Code != 303 || rec.Header().Get("Location") != "/cleaning/properties/14?notice=saved" {
		t.Fatalf("manual: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	mustPrivate(t, "manual", rec)
	first := e.maxCode()
	c := e.code(first)
	if c.Source != "manual" || c.State != "active" || c.Pin != "A-1*#" || !regexp.MustCompile(`^[0-9a-f]{32}$`).MatchString(c.Ref) {
		t.Errorf("code = %+v", c)
	}
	if code, pending := e.property(14); code == nil || *code != first || pending != nil {
		t.Errorf("property 14 = %v %v", code, pending)
	}
	// The page shows it.
	mustContain(t, "page", e.get(i64(1), "/cleaning/properties/14", "").Body.String(), `translate="no">A-1*#</strong>`)
	// A second manual code revokes the first one at once (a manual code holds no provider state).
	e.codePost(i64(1), "14", "manual", map[string]string{"code": "B2"})
	if old := e.code(first); old.State != "revoked" || old.Pin != "" {
		t.Errorf("replaced manual code = %+v", old)
	}
	// 12: an active TTLock code 2 (PIN 9090) and a pending TTLock code 3. Typing the same PIN
	// (the keypad shows a final #) takes it over: code 2 is detached, not deleted from the lock.
	e.codePost(i64(1), "12", "manual", map[string]string{"code": "9090#"})
	if c2 := e.code(2); c2.State != "detached" || c2.Pin != "" {
		t.Errorf("takeover: code 2 = %+v", c2)
	}
	if c3 := e.code(3); c3.State != "revoke_pending" || c3.Attempts != 0 || c3.Next == "" {
		t.Errorf("pending code 3 = %+v", c3)
	}
	if code, pending := e.property(12); code == nil || *code != e.maxCode() || pending != nil {
		t.Errorf("property 12 = %v %v", code, pending)
	}
	// A different PIN on top of a TTLock code queues that code for revocation and keeps its PIN for the worker.
	e.exec(`UPDATE cleaning_code SET state = 'active', pin_enc = (SELECT pin_enc FROM cleaning_code WHERE id = 1) WHERE id = 2`)
	e.exec(`UPDATE cleaning_property SET code_id = 2 WHERE apartment_id = 12`)
	e.codePost(i64(1), "12", "manual", map[string]string{"code": "1111"})
	if c2 := e.code(2); c2.State != "revoke_pending" || c2.Pin != "4711" || c2.Attempts != 0 {
		t.Errorf("revoke_pending code 2 = %+v", c2)
	}
}

func TestHostManualCodeErrors(t *testing.T) {
	e := newHostEnv(t)
	before := e.maxCode()
	for _, code := range []string{"", "   ", "a b", "é", strings.Repeat("1", 33), "12;3"} {
		rec := e.codePost(i64(1), "11", "manual", map[string]string{"code": code})
		if rec.Code != 422 || !strings.Contains(rec.Body.String(), `<p class="cleaning-warning" role="alert">Use 1–32 letters, digits, #, * or hyphens.</p>`) {
			t.Errorf("code %q: %d", code, rec.Code)
		}
	}
	// The longest PIN is 32 characters.
	if rec := e.codePost(i64(1), "11", "manual", map[string]string{"code": strings.Repeat("9", 32)}); rec.Code != 303 {
		t.Errorf("32 characters: %d", rec.Code)
	}
	if e.maxCode() != before+1 {
		t.Errorf("rows added: %d", e.maxCode()-before)
	}
	// A lock operation in flight blocks the change; nothing is written.
	e.exec(`UPDATE cleaning_code SET state = 'issuing' WHERE id = 3`)
	n := e.maxCode()
	rec := e.codePost(i64(1), "12", "manual", map[string]string{"code": "5555"})
	if rec.Code != 422 || !strings.Contains(rec.Body.String(), `A lock operation is running.`) {
		t.Errorf("issuing: %d", rec.Code)
	}
	if e.maxCode() != n || e.code(3).State != "issuing" || e.code(2).State != "active" {
		t.Error("the blocked change wrote rows")
	}
}

// TestHostRemoveCode mirrors cleaning_codes.remove.
func TestHostRemoveCode(t *testing.T) {
	e := newHostEnv(t)
	rec := e.codePost(i64(1), "11", "remove", nil)
	if rec.Code != 303 || rec.Header().Get("Location") != "/cleaning/properties/11?notice=saved" {
		t.Fatalf("remove: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if c := e.code(1); c.State != "revoked" || c.Pin != "" {
		t.Errorf("manual code = %+v", c)
	}
	if code, pending := e.property(11); code != nil || pending != nil {
		t.Errorf("property 11 = %v %v", code, pending)
	}
	// 12: the TTLock code and the pending one both go to the worker; the PIN stays for it.
	e.codePost(i64(1), "12", "remove", nil)
	if c := e.code(2); c.State != "revoke_pending" || c.Pin != "9090" || c.Next == "" {
		t.Errorf("code 2 = %+v", c)
	}
	if c := e.code(3); c.State != "revoke_pending" || c.Pin != "" {
		t.Errorf("code 3 = %+v", c)
	}
	if code, pending := e.property(12); code != nil || pending != nil {
		t.Errorf("property 12 = %v %v", code, pending)
	}
	// Nothing to remove still works (and creates the row).
	if rec := e.codePost(i64(1), "14", "remove", nil); rec.Code != 303 {
		t.Errorf("empty remove: %d", rec.Code)
	}
}

func TestHostRemoveCodeBusy(t *testing.T) {
	e := newHostEnv(t)
	e.exec(`UPDATE cleaning_code SET state = 'revoking' WHERE id = 3`)
	rec := e.codePost(i64(1), "12", "remove", nil)
	if rec.Code != 422 || !strings.Contains(rec.Body.String(), `A lock operation is running.`) {
		t.Errorf("busy: %d", rec.Code)
	}
	// Code 2 was handled before code 3 failed: the whole change is rolled back.
	if c := e.code(2); c.State != "active" || c.Pin != "9090" {
		t.Errorf("code 2 = %+v", c)
	}
	if code, pending := e.property(12); code == nil || *code != 2 || pending == nil || *pending != 3 {
		t.Errorf("property 12 = %v %v", code, pending)
	}
}

// TestHostQueuePermanentCode mirrors cleaning_codes.queue_permanent.
func TestHostQueuePermanentCode(t *testing.T) {
	on := map[string]string{"UBYHOST_DOOR_CODES": "1", "UBYHOST_TTLOCK_CLIENT_ID": "id", "UBYHOST_TTLOCK_CLIENT_SECRET": "secret"}
	e := codeEnv(t, on)
	e.exec(`UPDATE lock_account SET locks_json = '[{"lock_id": "L12", "name": "x"}, {"lock_id": 77}]' WHERE id = 1`)
	// 12 already has a pending code that is not failed: nothing changes.
	rec := e.codePost(i64(1), "12", "ttlock", nil)
	if rec.Code != 303 || rec.Header().Get("Location") != "/cleaning/properties/12?notice=saved" {
		t.Fatalf("ttlock: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	if c := e.code(3); c.State != "pending" || e.maxCode() != 4 {
		t.Errorf("pending code touched: %+v", c)
	}
	// A failed one is retried at once.
	e.exec(`UPDATE cleaning_code SET state = 'failed', attempts = 5 WHERE id = 3`)
	e.codePost(i64(1), "12", "ttlock", nil)
	if c := e.code(3); c.State != "retrying" || c.Attempts != 1 || c.Next == "" {
		t.Errorf("retry = %+v", c)
	}
	// No pending code: a new one is queued for the worker.
	e.exec(`UPDATE cleaning_property SET pending_code_id = NULL WHERE apartment_id = 12`)
	e.codePost(i64(1), "12", "ttlock", nil)
	id := e.maxCode()
	c := e.code(id)
	if id != 5 || c.Source != "ttlock" || c.State != "pending" || c.LockID != "L12" || c.LockAccount == nil || *c.LockAccount != 1 ||
		!regexp.MustCompile(`^UH Cleaning [0-9a-f]{16}$`).MatchString(c.Ref) || !regexp.MustCompile(`^[1-9][0-9]{6}$`).MatchString(c.Pin) || c.Next != "2026-05-10T10:00:00+00:00" {
		t.Errorf("queued code = %+v", c)
	}
	if code, pending := e.property(12); code == nil || *code != 2 || pending == nil || *pending != id {
		t.Errorf("property 12 = %v %v", code, pending)
	}
	// The queued code is shown as pending, the current one stays.
	mustContain(t, "page", e.get(i64(1), "/cleaning/properties/12", "").Body.String(), `TTLock code is being prepared.`, `9090#`)
}

func TestHostQueuePermanentCodeRefused(t *testing.T) {
	on := map[string]string{"UBYHOST_DOOR_CODES": "1", "UBYHOST_TTLOCK_CLIENT_ID": "id", "UBYHOST_TTLOCK_CLIENT_SECRET": "secret"}
	merge := func(extra map[string]string) map[string]string {
		m := map[string]string{}
		for k, v := range on {
			m[k] = v
		}
		for k, v := range extra {
			m[k] = v
		}
		return m
	}
	lockList := `UPDATE lock_account SET locks_json = '[{"lock_id": "L12"}]' WHERE id = 1`
	for _, c := range []struct {
		name  string
		env   map[string]string
		setup string
		apt   string
	}{
		{"door codes off", map[string]string{}, lockList, "12"},
		{"no client secret", merge(map[string]string{"UBYHOST_TTLOCK_CLIENT_SECRET": " "}), lockList, "12"},
		{"property without a lock", on, lockList, "11"},
		{"no lock list", on, `UPDATE lock_account SET locks_json = NULL WHERE id = 1`, "12"},
		{"lock not in the list", on, `UPDATE lock_account SET locks_json = '[{"lock_id": "OTHER"}]' WHERE id = 1`, "12"},
		{"account not ok", on, lockList + `; UPDATE lock_account SET status = 'error' WHERE id = 1`, "12"},
		{"billing: standard without add-on", merge(map[string]string{"UBYHOST_BILLING_ENABLED": "1"}), lockList + `; INSERT INTO billing_account (owner_user_id, status, plan, updated_at) VALUES (1, 'active', 'standard', 'x')`, "12"},
	} {
		e := codeEnv(t, c.env)
		for _, sql := range strings.Split(c.setup, "; ") {
			e.exec(sql)
		}
		e.exec(`UPDATE cleaning_property SET pending_code_id = NULL WHERE apartment_id = 12`)
		before := e.maxCode()
		rec := e.codePost(i64(1), c.apt, "ttlock", nil)
		if rec.Code != 422 || !strings.Contains(rec.Body.String(), `Connect an authorized TTLock lock in property settings first.`) {
			t.Errorf("%s: %d", c.name, rec.Code)
		}
		if e.maxCode() != before {
			t.Errorf("%s: a code was queued", c.name)
		}
	}
	// A paused account never gets that far: the login gate redirects every POST (hostweb.Login).
	e := codeEnv(t, merge(map[string]string{"UBYHOST_BILLING_ENABLED": "1"}))
	e.exec(lockList)
	e.exec(`INSERT INTO billing_account (owner_user_id, status, plan, updated_at) VALUES (1, 'paused', 'max', 'x')`)
	e.exec(`UPDATE cleaning_property SET pending_code_id = NULL WHERE apartment_id = 12`)
	if rec := e.codePost(i64(1), "12", "ttlock", nil); rec.Code != 303 || rec.Header().Get("Location") != "/predplatne?paused=1" || e.maxCode() != 4 {
		t.Errorf("paused: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	// The same setups pass with the plan that allows it.
	e = codeEnv(t, merge(map[string]string{"UBYHOST_BILLING_ENABLED": "1"}))
	e.exec(lockList)
	e.exec(`INSERT INTO billing_account (owner_user_id, status, plan, addon_ttlock, updated_at) VALUES (1, 'active', 'standard', 1, 'x')`)
	e.exec(`UPDATE cleaning_property SET pending_code_id = NULL WHERE apartment_id = 12`)
	if rec := e.codePost(i64(1), "12", "ttlock", nil); rec.Code != 303 {
		t.Errorf("add-on: %d", rec.Code)
	}
	e.exec(`UPDATE billing_account SET addon_ttlock = 0, plan = 'max'`)
	e.exec(`UPDATE cleaning_property SET pending_code_id = NULL WHERE apartment_id = 12`)
	if rec := e.codePost(i64(1), "12", "ttlock", nil); rec.Code != 303 {
		t.Errorf("max plan: %d", rec.Code)
	}
}

func TestHostCodeActionAccess(t *testing.T) {
	e := newHostEnv(t)
	for _, c := range []struct {
		name, apt, action string
		user              *int64
		status            int
	}{
		{"unknown action", "11", "wipe", i64(1), 404},
		{"foreign property", "21", "manual", i64(1), 404},
		{"archived property", "13", "remove", i64(1), 404},
		{"missing property", "999", "remove", i64(1), 404},
		{"text id", "abc", "remove", i64(1), 422},
		{"signed out", "11", "remove", nil, 303},
	} {
		if got := e.codePost(c.user, c.apt, c.action, map[string]string{"code": "1"}).Code; got != c.status {
			t.Errorf("%s: status %d, want %d", c.name, got, c.status)
		}
	}
	rec := e.call(goldenCase{Method: http.MethodPost, Path: "/cleaning/properties/11/code/remove", User: i64(1)})
	if rec.Code != 303 || e.code(1).State != "active" {
		t.Errorf("no CSRF: %d, code state %s", rec.Code, e.code(1).State)
	}
	if e.code(4).State != "revoke_failed" {
		t.Error("a foreign code changed")
	}
}

// TestHostCodesStagingNoLogin: staging without login never stores or queues a code.
func TestHostCodesStagingNoLogin(t *testing.T) {
	e := codeEnv(t, map[string]string{"UBYHOST_DEPLOYMENT": "staging", "UBYHOST_STAGING_NO_LOGIN": "1",
		"UBYHOST_DOOR_CODES": "1", "UBYHOST_TTLOCK_CLIENT_ID": "id", "UBYHOST_TTLOCK_CLIENT_SECRET": "s"})
	s := &hostServer{pool: e.pool, getenv: func(k string) string {
		return map[string]string{"UBYHOST_DEPLOYMENT": "staging", "UBYHOST_STAGING_NO_LOGIN": "1"}[k]
	}, now: func() time.Time { return goldenNow }}
	before := e.maxCode()
	if key, err := s.saveManual(context.Background(), 11, "1234", goldenNow); err != nil || key != "login_required" {
		t.Errorf("saveManual: %q %v", key, err)
	}
	if key, err := s.queuePermanent(context.Background(), home{ID: 12}, i64(1), goldenNow); err != nil || key != "login_required" {
		t.Errorf("queuePermanent: %q %v", key, err)
	}
	if e.maxCode() != before {
		t.Error("a code was written")
	}
}
