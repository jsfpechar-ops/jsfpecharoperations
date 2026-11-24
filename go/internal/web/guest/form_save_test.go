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

func TestGuestWriteEncryption(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := context.Background()
	baseID := time.Now().UnixNano()%1000000000 + 7400000
	userID, aptID, resID := baseID, baseID+1, baseID+2
	stamp := "2026-01-01T00:00:00Z"
	tok := fmt.Sprintf("guestwrite%d", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3)`, userID, fmt.Sprintf("gw%d@example.test", userID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
		VALUES ($1, $2, 'Synthetic', 'Prague', 1, $3, $4)`, aptID, userID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, declared_guests, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', '2026-06-20', '2026-06-22', 1, $4, $4)`, resID, aptID, fmt.Sprintf("gw-%d", resID), stamp)
	t.Cleanup(func() {
		_, _ = pool.Exec(context.Background(), `DELETE FROM guest WHERE reservation_id = $1`, resID)
		_, _ = pool.Exec(context.Background(), `DELETE FROM reservation WHERE id = $1`, resID)
		_, _ = pool.Exec(context.Background(), `DELETE FROM apartment WHERE id = $1`, aptID)
		_, _ = pool.Exec(context.Background(), `DELETE FROM user_account WHERE id = $1`, userID)
	})
	one := int64(1)
	d := saveDeps{pool: pool, getenv: testDataEnv, now: func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }}
	signature := "data:image/png;base64,AAAA"
	payload := map[string]any{
		"surname": "Synthetic", "first_name": "Guest", "birth_date": "1990-01-02", "nationality": "",
		"doc_number": "SYNTHETIC-DOC", "visa_number": "SYNTHETIC-VISA", "res_street": "Test Street", "res_city": "Test City",
		"res_country": "CZ", "purpose": "tourism", "note": "", "stay_from": "2026-06-20", "stay_to": "2026-06-22",
		"signature_png": signature, "notice_version": "v1", "notice_lang": "en", "notice_ack_at": stamp,
		"filled_at": stamp, "entered_by": "guest", "updated_at": stamp, "signed_at": stamp, "submit_state": guestSubmitPending,
	}
	guestID, err := insertGuestSaveRow(ctx, d, payload, resID, guestResMeta{apartmentID: aptID, dateFrom: "2026-06-20", dateTo: "2026-06-22", declaredGuests: &one})
	if err != nil || guestID == 0 {
		t.Fatalf("guest self-save insert failed: %v", err)
	}
	var birth, birthEnc, doc, docEnc, visa, visaEnc, street, streetEnc, city, cityEnc, sig, sigEnc string
	if err := pool.QueryRow(ctx, `SELECT COALESCE(birth_date,''), COALESCE(birth_date_enc,''), COALESCE(doc_number,''), COALESCE(doc_number_enc,''),
		COALESCE(visa_number,''), COALESCE(visa_number_enc,''), COALESCE(res_street,''), COALESCE(res_street_enc,''),
		COALESCE(res_city,''), COALESCE(res_city_enc,''), COALESCE(signature_png,''), COALESCE(signature_png_enc,'') FROM guest WHERE id = $1`, guestID).Scan(
		&birth, &birthEnc, &doc, &docEnc, &visa, &visaEnc, &street, &streetEnc, &city, &cityEnc, &sig, &sigEnc); err != nil {
		t.Fatal("raw guest field read failed")
	}
	if birth != "" || doc != "" || visa != "" || street != "" || city != "" || sig != "" ||
		birthEnc == "" || docEnc == "" || visaEnc == "" || streetEnc == "" || cityEnc == "" || sigEnc == "" {
		t.Fatal("guest insert did not place the field in ciphertext only")
	}
	for token, want := range map[string]string{
		birthEnc: "1990-01-02", docEnc: "SYNTHETIC-DOC", visaEnc: "SYNTHETIC-VISA",
		streetEnc: "Test Street", cityEnc: "Test City", sigEnc: signature,
	} {
		if got, err := decryptGuestField(testDataEnv, d.now, token, ""); err != nil || got != want {
			t.Fatal("guest insert ciphertext did not hydrate")
		}
	}
	mustExecGuest(t, ctx, pool, `UPDATE guest SET birth_date='legacy-birth', birth_date_enc=NULL,
		doc_number='legacy-doc', doc_number_enc=NULL, visa_number='legacy-visa', visa_number_enc=NULL,
		res_city='legacy-city', res_city_enc=NULL, res_street='untouched-legacy', res_street_enc=NULL,
		signature_png='untouched-signature', signature_png_enc=NULL WHERE id = $1`, guestID)
	existing := &guestSaveRow{id: guestID, submitState: guestSubmitPending}
	updated, err := updateGuestSaveRow(ctx, d, existing, map[string]any{
		"birth_date": "1992-03-04", "doc_number": "REPLACED-DOC", "visa_number": "", "res_city": "Replacement City",
	})
	if err != nil || !updated {
		t.Fatal("guest self-save update failed")
	}
	var birthPlain, docPlain, visaPlain, cityPlain, streetPlain, sigPlain string
	if err := pool.QueryRow(ctx, `SELECT COALESCE(birth_date,''), COALESCE(birth_date_enc,''), COALESCE(doc_number,''), COALESCE(doc_number_enc,''),
		COALESCE(visa_number,''), COALESCE(visa_number_enc,''), COALESCE(res_city,''), COALESCE(res_city_enc,''),
		COALESCE(res_street,''), COALESCE(signature_png,'') FROM guest WHERE id = $1`, guestID).Scan(
		&birthPlain, &birthEnc, &docPlain, &docEnc, &visaPlain, &visaEnc, &cityPlain, &cityEnc, &streetPlain, &sigPlain); err != nil {
		t.Fatal("raw guest update read failed")
	}
	if birthPlain != "" || docPlain != "" || visaPlain != "" || cityPlain != "" || birthEnc == "" || docEnc == "" || cityEnc == "" || visaEnc != "" || streetPlain != "untouched-legacy" || sigPlain != "untouched-signature" {
		t.Fatal("guest update did not clear only the touched legacy fields")
	}
	for token, want := range map[string]string{birthEnc: "1992-03-04", docEnc: "REPLACED-DOC", cityEnc: "Replacement City"} {
		if got, err := decryptGuestField(testDataEnv, d.now, token, ""); err != nil || got != want {
			t.Fatal("guest replacement ciphertext did not hydrate")
		}
	}
	if got, err := decryptGuestField(testDataEnv, d.now, visaEnc, visaPlain); err != nil || got != "" {
		t.Fatal("explicit empty guest field did not clear")
	}
	if _, err := updateGuestSaveRow(ctx, d, existing, map[string]any{"doc_number": 123}); err == nil {
		t.Fatal("wrong protected field type must fail before writing")
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
		"birth_date": "1990-01-01", "surname": "Novak", "signature_png": "", "fee_host_reason": "synthetic reason",
	})
	if err != nil {
		t.Fatal(err)
	}
	if value, ok := out["birth_date"]; !ok || value != nil {
		t.Fatal("legacy birth_date must be cleared on write")
	}
	if tok, _ := out["birth_date_enc"].(string); tok == "" {
		t.Fatal("birth_date_enc missing")
	}
	if value, ok := out["signature_png"]; !ok || value != nil {
		t.Fatal("legacy signature_png must be cleared on write")
	}
	if out["signature_png_enc"] != nil {
		t.Fatal("empty signature must store nil enc, not wipe later reads")
	}
	if value, ok := out["fee_host_reason"]; !ok || value != nil {
		t.Fatal("legacy fee_host_reason must be cleared on write")
	}
	if tok, _ := out["fee_host_reason_enc"].(string); tok == "" {
		t.Fatal("fee_host_reason_enc missing")
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
