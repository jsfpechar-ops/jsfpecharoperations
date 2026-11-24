package ai

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
)

func accessPath(w *guideCardWorld) string {
	return "/apartments/" + itoa64(w.apt) + "/access"
}

func accessPost(t *testing.T, w *guideCardWorld, form url.Values) *httptest.ResponseRecorder {
	t.Helper()
	return guideTestDo(t, w.mux, http.MethodPost, accessPath(w), w.host, form)
}

func TestAccessSaveTypesAndSecrecy(t *testing.T) {
	w := newGuideCardWorld(t)
	seed := "Z7*p"
	for _, typ := range []string{"gate", "building_entrance", "garage", "bike_room", "other"} {
		form := url.Values{"action": {"save"}, "position": {"1"}, "code_type": {typ}, "code": {seed + "-" + typ}}
		if typ == "other" {
			form.Set("custom_label", "Roof")
		}
		rec := accessPost(t, w, form)
		if rec.Code != 303 {
			t.Fatalf("%s save: %d", typ, rec.Code)
		}
	}
	var enc string
	if err := w.pool.QueryRow(context.Background(), `SELECT code_enc FROM apartment_entry_code WHERE apartment_id=$1 AND position=1`, w.apt).Scan(&enc); err != nil {
		t.Fatal(err)
	}
	if enc == seed+"-gate" || strings.Contains(enc, seed) {
		t.Fatal("ciphertext equals plaintext")
	}
	page := guideTestDo(t, w.mux, http.MethodGet, accessPath(w), w.host, nil).Body.String()
	for _, typ := range []string{"gate", "building_entrance", "garage", "bike_room", "other"} {
		if strings.Contains(page, seed+"-"+typ) {
			t.Fatal("response leaks code")
		}
	}
}

func TestAccessValidation(t *testing.T) {
	w := newGuideCardWorld(t)
	bad := []url.Values{
		{"action": {"save"}, "code_type": {"other"}, "code": {"abc"}},
		{"action": {"save"}, "code_type": {"other"}, "custom_label": {strings.Repeat("x", 61)}, "code": {"abc"}},
		{"action": {"save"}, "code_type": {"gate"}, "code": {"has space"}},
		{"action": {"save"}, "code_type": {"gate"}, "code": {"ok1"}, "valid_until": {"2020-01-01"}},
	}
	for _, form := range bad {
		rec := accessPost(t, w, form)
		if rec.Code != 303 {
			t.Fatalf("expected redirect, got %d", rec.Code)
		}
		if strings.Contains(location(rec), "GATE") || strings.Contains(location(rec), form.Get("code")) {
			t.Fatal("code in redirect URL")
		}
	}
	var n int64
	_ = w.pool.QueryRow(context.Background(), `SELECT COUNT(*) FROM apartment_entry_code WHERE apartment_id=$1`, w.apt).Scan(&n)
	if n != 0 {
		t.Fatal("validation wrote rows")
	}
}

func TestAccessFourthRowForeignCSRF(t *testing.T) {
	w := newGuideCardWorld(t)
	for i := 0; i < 3; i++ {
		accessPost(t, w, url.Values{"action": {"save"}, "code_type": {"gate"}, "code": {"C" + itoa64(int64(i))}})
	}
	if rec := accessPost(t, w, url.Values{"action": {"save"}, "code_type": {"gate"}, "code": {"C4"}}); location(rec) == "" {
		t.Fatal("expected redirect")
	}
	if rec := guideTestDo(t, w.mux, http.MethodGet, accessPath(w), w.stranger, nil); rec.Code != 404 {
		t.Fatalf("foreign apt: %d", rec.Code)
	}
	req := httptest.NewRequest(http.MethodPost, accessPath(w), strings.NewReader("action=save&code_type=gate&code=x"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: "en"})
	rec := httptest.NewRecorder()
	w.mux.ServeHTTP(rec, req)
	if rec.Code == http.StatusSeeOther && strings.Contains(rec.Header().Get("Location"), "access") {
		t.Fatal("POST without CSRF should not succeed")
	}
}

func TestAccessReplaceClearRenumber(t *testing.T) {
	w := newGuideCardWorld(t)
	accessPost(t, w, url.Values{"action": {"save"}, "code_type": {"gate"}, "code": {"A1"}})
	accessPost(t, w, url.Values{"action": {"save"}, "code_type": {"garage"}, "code": {"B2"}})
	accessPost(t, w, url.Values{"action": {"save"}, "position": {"1"}, "code_type": {"gate"}, "code": {"A9"}})
	accessPost(t, w, url.Values{"action": {"clear"}, "position": {"1"}})
	got := accessPositions(t, w)
	if len(got) != 1 || got[0] != 1 {
		t.Fatalf("renumber got %v", got)
	}
}

func TestAccessClearMiddleOfThreeRenumber(t *testing.T) {
	w := newGuideCardWorld(t)
	accessPost(t, w, url.Values{"action": {"save"}, "code_type": {"gate"}, "code": {"A1"}})
	accessPost(t, w, url.Values{"action": {"save"}, "code_type": {"building_entrance"}, "code": {"B2"}})
	accessPost(t, w, url.Values{"action": {"save"}, "code_type": {"garage"}, "code": {"C3"}})
	rec := accessPost(t, w, url.Values{"action": {"clear"}, "position": {"2"}})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("clear middle of three: %d", rec.Code)
	}
	got := accessPositions(t, w)
	if len(got) != 2 || got[0] != 1 || got[1] != 2 {
		t.Fatalf("after clearing position 2 got %v, want [1 2]", got)
	}
}

func TestAccessClearThreeCodesRenumber(t *testing.T) {
	w := newGuideCardWorld(t)
	accessPost(t, w, url.Values{"action": {"save"}, "code_type": {"gate"}, "code": {"A1"}})
	accessPost(t, w, url.Values{"action": {"save"}, "code_type": {"building_entrance"}, "code": {"B2"}})
	accessPost(t, w, url.Values{"action": {"save"}, "code_type": {"garage"}, "code": {"C3"}})
	rec := accessPost(t, w, url.Values{"action": {"clear"}, "position": {"1"}})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("clear first of three: %d", rec.Code)
	}
	got := accessPositions(t, w)
	if len(got) != 2 || got[0] != 1 || got[1] != 2 {
		t.Fatalf("after clearing position 1 got %v, want [1 2]", got)
	}
	rec = accessPost(t, w, url.Values{"action": {"clear"}, "position": {"1"}})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("clear first of two: %d", rec.Code)
	}
	got = accessPositions(t, w)
	if len(got) != 1 || got[0] != 1 {
		t.Fatalf("after second clear got %v, want [1]", got)
	}
}

func accessPositions(t *testing.T, w *guideCardWorld) []int {
	t.Helper()
	rows, err := w.pool.Query(context.Background(), `SELECT position FROM apartment_entry_code WHERE apartment_id=$1 ORDER BY position`, w.apt)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	var pos []int
	for rows.Next() {
		var p int
		if err := rows.Scan(&p); err != nil {
			t.Fatal(err)
		}
		pos = append(pos, p)
	}
	if err := rows.Err(); err != nil {
		t.Fatal(err)
	}
	return pos
}

func TestAccessLockPreview(t *testing.T) {
	w := newGuideCardWorld(t)
	guideTestExec(t, w.pool, `UPDATE apartment SET lock_id='lock-1' WHERE id=$1`, w.apt)
	body := guideTestDo(t, w.mux, http.MethodGet, accessPath(w), w.host, nil).Body.String()
	if !strings.Contains(body, "Apartment door code") && !strings.Contains(body, "Sent by the smart lock") {
		t.Fatal("missing lock card")
	}
}
