package guest

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

type formSaveGolden struct {
	Now   string `json:"now"`
	Seed  []any  `json:"seed"`
	Cases []struct {
		Name     string `json:"name"`
		Method   string `json:"method"`
		Path     string `json:"path"`
		Body     string `json:"body"`
		Status   int    `json:"status"`
		Location string `json:"location"`
	} `json:"cases"`
}

func loadFormSaveGolden(t *testing.T) formSaveGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/form_save_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g formSaveGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestFormSaveGoldenShape(t *testing.T) {
	g := loadFormSaveGolden(t)
	if len(g.Cases) < 15 {
		t.Fatalf("want >= 15 cases, got %d", len(g.Cases))
	}
	for _, c := range g.Cases {
		if c.Method != http.MethodPost {
			t.Errorf("%s method", c.Name)
		}
		if !strings.Contains(c.Path, "/save") && c.Status == 422 {
			continue
		}
		if c.Status == 0 {
			t.Errorf("%s status", c.Name)
		}
	}
}

func TestFormSaveRoutePattern(t *testing.T) {
	mux := http.NewServeMux()
	RegisterFormSave(mux, nil, nil, nil, func(_ string, h http.HandlerFunc) http.Handler { return h }, nil)
	_, pattern := mux.Handler(mustRequest("POST", "/l/tok/9/save"))
	if pattern != "POST /l/{token}/{reservation_id}/save" {
		t.Fatalf("pattern %q", pattern)
	}
}

func TestFormSaveAccess(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	getenv := guestTestGetenv(t, strings.Repeat("q", 32))
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	aptID := time.Now().UnixNano()%8000000000 + 7100000
	userID, resID := aptID, aptID+1
	tok := fmt.Sprintf("saveaccess%d", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3)`, userID, fmt.Sprintf("sa%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
		VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4)`, aptID, userID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', '2026-06-20', '2026-06-22', $4, $4)`, resID, aptID, fmt.Sprintf("save-%d", resID), stamp)
	d := saveDeps{pool: pool, getenv: getenv, now: now}
	req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/l/%s/%d/save?lang=en", tok, resID), strings.NewReader(""))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.SetPathValue("token", tok)
	req.SetPathValue("reservation_id", fmt.Sprint(resID))
	rec := httptest.NewRecorder()
	if err := handleGuestFormSave(ctx, d, rec, req); err != nil {
		t.Fatalf("save handler: %v", err)
	}
	if rec.Code != http.StatusSeeOther || !strings.Contains(rec.Header().Get("Location"), fmt.Sprintf("/l/%s/%d", tok, resID)) {
		t.Fatalf("missing email claim: status=%d location=%q", rec.Code, rec.Header().Get("Location"))
	}
	var guestRows int
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM guest WHERE reservation_id = $1`, resID).Scan(&guestRows); err != nil {
		t.Fatal(err)
	}
	if guestRows != 0 {
		t.Fatalf("claim refusal wrote %d guest rows", guestRows)
	}

	newStay := func(id int64, from, to, source string) {
		t.Helper()
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, declared_guests, created_at, updated_at)
			VALUES ($1, $2, $3, 'active', $4, $5, $6, 1, $7, $7)`, id, aptID, fmt.Sprintf("save-%d", id), source, from, to, stamp)
	}
	newStay(resID+1, "2026-06-20", "2026-06-22", "manual")
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_version, guest_access_locked_at, created_at, updated_at)
		VALUES ($1, 'unclaimed', 0, $2, $3, $3)`, resID+1, stamp, stamp)
	newStay(resID+2, "2026-06-20", "2026-06-22", "demo")
	newStay(resID+3, "2025-06-10", "2025-06-14", "manual")
	newStay(resID+4, "2025-06-10", "2025-06-15", "manual")
	otherApt := aptID + 20
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
		VALUES ($1, $2, 'Other', 'Prague', 1, $3, $4)`, otherApt, userID, fmt.Sprintf("other%d", aptID), stamp)
	newStay(resID+5, "2026-06-20", "2026-06-22", "manual")
	mustExecGuest(t, ctx, pool, `UPDATE reservation SET apartment_id = $1 WHERE id = $2`, otherApt, resID+5)
	for name, id := range map[string]int64{"wrong apartment": resID + 5, "locked access": resID + 1, "outsider demo": resID + 2, "past reachback": resID + 3, "unknown stay": resID + 99} {
		_, _, _, ok, err := guestSaveReservation(ctx, d, req, &Apartment{ID: aptID, PermalinkToken: tok}, id, tok)
		if err != nil {
			t.Fatalf("%s lookup: %v", name, err)
		}
		if ok {
			t.Errorf("%s was eligible", name)
		}
	}
	if _, _, _, ok, err := guestSaveReservation(ctx, d, req, &Apartment{ID: aptID, PermalinkToken: tok}, resID+4, tok); err != nil || !ok {
		t.Errorf("inclusive reachback boundary: ok=%v err=%v", ok, err)
	}
}

func mustRequest(method, target string) *http.Request {
	r := httptest.NewRequest(method, target, nil)
	r.SetPathValue("token", "tok")
	r.SetPathValue("reservation_id", "9")
	return r
}

func TestGuestSaveInsertColsIncludeEncryptedPII(t *testing.T) {
	joined := strings.Join(guestSaveInsertCols, ",")
	for _, col := range []string{"birth_date_enc", "doc_number_enc", "visa_number_enc", "res_street_enc", "res_city_enc", "signature_png_enc"} {
		if !strings.Contains(joined, col) {
			t.Errorf("insert omits %s — guest identity would be dropped", col)
		}
	}
	for _, col := range []string{"birth_date", "doc_number", "signature_png"} {
		if strings.Contains(","+joined+",", ","+col+",") {
			t.Errorf("insert writes plaintext %s", col)
		}
	}
}

func testGuestEnv(k string) string {
	if k == "UBYHOST_SECRET_KEY" {
		return "guest-form-save-test-secret-key-32ch"
	}
	return ""
}

func TestOwnedGuestIDRequiresCookie(t *testing.T) {
	form := map[string]string{"guest_id": "42"}
	r := httptest.NewRequest(http.MethodPost, "/l/tok/9/save", nil)
	if got := ownedGuestID(r, testGuestEnv, form); got != 0 {
		t.Fatalf("unsigned guest_id: got %d want 0", got)
	}
	w := httptest.NewRecorder()
	rememberOwnedGuestIDs(w, testGuestEnv, []int64{42, 7})
	res := w.Result()
	defer res.Body.Close()
	var cookie *http.Cookie
	for _, c := range res.Cookies() {
		if c.Name == ownedCookieName {
			cookie = c
		}
	}
	if cookie == nil {
		t.Fatal("owned cookie not set")
	}
	r.AddCookie(cookie)
	if got := ownedGuestID(r, testGuestEnv, form); got != 42 {
		t.Fatalf("owned guest_id: got %d want 42", got)
	}
	if got := ownedGuestID(r, testGuestEnv, map[string]string{"guest_id": "99"}); got != 0 {
		t.Fatalf("foreign guest_id: got %d want 0", got)
	}
}

func testDataEnv(k string) string {
	if k == "UBYHOST_DATA_KEYS" {
		return base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{7}, 32))
	}
	if k == "UBYHOST_DATA_KEY_LEGACY" {
		return "0"
	}
	return testGuestEnv(k)
}

func TestEncryptSaveFieldsWritesEncColumns(t *testing.T) {
	out, err := encryptSaveFields(testDataEnv, map[string]any{
		"birth_date": "1990-01-01", "surname": "Novak", "signature_png": "",
	})
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := out["birth_date"]; ok {
		t.Fatal("plaintext birth_date must not be written")
	}
	if tok, _ := out["birth_date_enc"].(string); tok == "" {
		t.Fatal("birth_date_enc missing")
	}
	if out["signature_png_enc"] != nil {
		t.Fatal("empty signature must store nil enc, not wipe later reads")
	}
	if out["surname"] != "Novak" {
		t.Fatalf("surname: %v", out["surname"])
	}
}

func TestDecryptGuestFieldEmptyUsesPlain(t *testing.T) {
	got, err := decryptGuestField(testDataEnv, time.Now, "", "kept-sig")
	if err != nil || got != "kept-sig" {
		t.Fatalf("got %q err %v", got, err)
	}
	out, err := encryptSaveFields(testDataEnv, map[string]any{"signature_png": "data:image/png;base64,AAAA"})
	if err != nil {
		t.Fatal(err)
	}
	tok, _ := out["signature_png_enc"].(string)
	plain, err := decryptGuestField(testDataEnv, time.Now, tok, "")
	if err != nil || plain != "data:image/png;base64,AAAA" {
		t.Fatalf("round-trip %q err %v", plain, err)
	}
}
