package guest

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
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
	RegisterFormSave(mux, nil, nil, nil, func(_ string, h http.HandlerFunc) http.Handler { return h })
	_, pattern := mux.Handler(mustRequest("POST", "/l/tok/9/save"))
	if pattern != "POST /l/{token}/{reservation_id}/save" {
		t.Fatalf("pattern %q", pattern)
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

func TestReservationForGuestNilPool(t *testing.T) {
	cfg, res, ok := reservationForGuest(t.Context(), nil, &Apartment{ID: 1, PermalinkToken: "tok"}, 9, testGuestEnv)
	if ok || cfg.ownerUserID != 0 || res.apartmentID != 0 {
		t.Fatalf("nil pool must fail closed, got ok=%v cfg=%v res=%v", ok, cfg, res)
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

func TestGuestSaveValidateIssuesLegalAckOnEdit(t *testing.T) {
	cfg := guestFormCfg{defaultPurpose: "tourism"}
	res := guestResMeta{dateFrom: "2026-06-01", dateTo: "2026-06-05"}
	form := map[string]string{
		"surname": "Doe", "first_name": "Jan", "birth_date": "1990-01-01",
		"nationality": "CZE", "doc_number": "123", "purpose": "tourism",
		"stay_from": "2026-06-01", "stay_to": "2026-06-05", "signature": "data:image/png;base64,AAAA",
	}
	raw := validation.GuestFormRaw(form, cfg.defaultPurpose)
	values := validation.NormaliseGuest(raw, time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC))
	existing := &guestSaveRow{id: 1}
	issues := guestSaveValidateIssues(form, cfg, res, values, raw, "2026-06-01", "2026-06-05", form["signature"], false, existing, time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC))
	if len(validation.ErrorsOnly(issues)) == 0 {
		t.Fatal("edit save must require legal_ack")
	}
}

func TestGuestSaveValidateIssuesPartySizeOnNew(t *testing.T) {
	cfg := guestFormCfg{defaultPurpose: "tourism"}
	res := guestResMeta{dateFrom: "2026-06-01", dateTo: "2026-06-05"}
	form := map[string]string{
		"surname": "Doe", "first_name": "Jan", "birth_date": "1990-01-01",
		"nationality": "CZE", "doc_number": "123", "purpose": "tourism",
		"stay_from": "2026-06-01", "stay_to": "2026-06-05", "signature": "data:image/png;base64,AAAA",
		"legal_ack": "1",
	}
	raw := validation.GuestFormRaw(form, cfg.defaultPurpose)
	values := validation.NormaliseGuest(raw, time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC))
	issues := guestSaveValidateIssues(form, cfg, res, values, raw, "2026-06-01", "2026-06-05", form["signature"], false, nil, time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC))
	found := false
	for _, i := range issues {
		if i.Field == "party_size" {
			found = true
		}
	}
	if !found {
		t.Fatal("first guest save must require party_size when undeclared")
	}
}
