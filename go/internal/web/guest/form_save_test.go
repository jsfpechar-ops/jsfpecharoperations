package guest

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"image"
	"image/jpeg"
	"image/png"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/textproto"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/passportphotos"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
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
	ins, err := insertGuestSaveRow(ctx, d, payload, resID, guestResMeta{apartmentID: aptID, dateFrom: "2026-06-20", dateTo: "2026-06-22", declaredGuests: &one}, 0)
	guestID := ins.id
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

// TestGuestSaveNoticeAndHeadcount covers the first-form count and guest insert
// as one transaction (brief 2071), on synthetic rows.
func TestGuestSaveNoticeAndHeadcount(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := context.Background()
	baseID := time.Now().UnixNano()%1000000000 + 7500000
	userID, aptID := baseID, baseID+1
	stamp := "2026-01-01T00:00:00Z"
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3)`, userID, fmt.Sprintf("hc%d@example.test", userID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
		VALUES ($1, $2, 'Synthetic', 'Prague', 1, $3, $4)`, aptID, userID, fmt.Sprintf("guestheads%d", aptID), stamp)
	var resIDs []int64
	newRes := func(id int64, declared, override *int64) int64 {
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, declared_guests, expected_guests_override, created_at, updated_at)
			VALUES ($1, $2, $3, 'active', 'manual', '2026-06-20', '2026-06-22', $4, $5, $6, $6)`,
			id, aptID, fmt.Sprintf("hc-%d", id), declared, override, stamp)
		resIDs = append(resIDs, id)
		return id
	}
	t.Cleanup(func() {
		bg := context.Background()
		for _, id := range resIDs {
			_, _ = pool.Exec(bg, `DELETE FROM guest WHERE reservation_id = $1`, id)
			_, _ = pool.Exec(bg, `DELETE FROM audit WHERE detail LIKE $1`, fmt.Sprintf("id=%d %%", id))
			_, _ = pool.Exec(bg, `DELETE FROM reservation WHERE id = $1`, id)
		}
		_, _ = pool.Exec(bg, `DELETE FROM apartment WHERE id = $1`, aptID)
		_, _ = pool.Exec(bg, `DELETE FROM user_account WHERE id = $1`, userID)
	})
	d := saveDeps{pool: pool, getenv: testDataEnv, now: func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }}
	meta := guestResMeta{apartmentID: aptID, dateFrom: "2026-06-20", dateTo: "2026-06-22"}
	payloadFor := func() map[string]any {
		return map[string]any{
			"surname": "Synthetic", "first_name": "Guest", "birth_date": "1990-01-02", "nationality": "",
			"doc_number": "SYNTHETIC-DOC", "visa_number": "", "res_street": "Test Street", "res_city": "Test City",
			"res_country": "CZ", "purpose": "tourism", "note": "", "stay_from": "2026-06-20", "stay_to": "2026-06-22",
			"signature_png": "data:image/png;base64,AAAA", "notice_version": "v1", "notice_lang": "en", "notice_ack_at": stamp,
			"filled_at": stamp, "entered_by": "guest", "updated_at": stamp, "signed_at": stamp, "submit_state": guestSubmitPending,
		}
	}
	countGuests := func(resID int64) int {
		var n int
		if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM guest WHERE reservation_id = $1`, resID).Scan(&n); err != nil {
			t.Fatalf("guest count: %v", err)
		}
		return n
	}
	declaredOf := func(resID int64) *int64 {
		var v *int64
		if err := pool.QueryRow(ctx, `SELECT declared_guests FROM reservation WHERE id = $1`, resID).Scan(&v); err != nil {
			t.Fatalf("declared read: %v", err)
		}
		return v
	}

	t.Run("first guest with party size 3 saves count and guest", func(t *testing.T) {
		id := newRes(baseID+10, nil, nil)
		ins, err := insertGuestSaveRow(ctx, d, payloadFor(), id, meta, 3)
		if err != nil || ins.id == 0 || !ins.countSaved || ins.countCode != codeSaved {
			t.Fatalf("insert: id=%d code=%q saved=%v err=%v", ins.id, ins.countCode, ins.countSaved, err)
		}
		if v := declaredOf(id); v == nil || *v != 3 {
			t.Fatalf("declared_guests = %v, want 3", v)
		}
		if n := countGuests(id); n != 1 {
			t.Fatalf("guests = %d, want 1", n)
		}
		if err := auditHeadcountCount(ctx, pool, d.now, id, ins.countCode, ins.countOld, 3, userID); err != nil {
			t.Fatalf("audit: %v", err)
		}
		var rows int
		if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM audit WHERE action = 'reservation_declared_guests_set' AND detail = $1`,
			fmt.Sprintf("id=%d from=None to=3 source=first_form", id)).Scan(&rows); err != nil || rows != 1 {
			t.Fatalf("audit rows = %d, err = %v", rows, err)
		}
	})

	t.Run("out-of-range party size writes nothing", func(t *testing.T) {
		for _, size := range []int{0, 61} {
			id := newRes(baseID+20+int64(size), nil, nil)
			ins, err := insertGuestSaveRow(ctx, d, payloadFor(), id, meta, size)
			if err != nil || ins.id != 0 || ins.countSaved {
				t.Fatalf("size %d: id=%d saved=%v err=%v", size, ins.id, ins.countSaved, err)
			}
			if v := declaredOf(id); v != nil {
				t.Fatalf("size %d: declared_guests = %d, want NULL", size, *v)
			}
			if n := countGuests(id); n != 0 {
				t.Fatalf("size %d: guests = %d, want 0", size, n)
			}
		}
	})

	t.Run("valid count in an already full group commits count only", func(t *testing.T) {
		id := newRes(baseID+40, nil, nil)
		first, err := insertGuestSaveRow(ctx, d, payloadFor(), id, meta, 1)
		if err != nil || first.id == 0 {
			t.Fatalf("first insert: id=%d err=%v", first.id, err)
		}
		if _, err := pool.Exec(ctx, `UPDATE reservation SET declared_guests = NULL WHERE id = $1`, id); err != nil {
			t.Fatal(err)
		}
		ins, err := insertGuestSaveRow(ctx, d, payloadFor(), id, meta, 1)
		if err != nil || ins.id != 0 || !ins.countSaved {
			t.Fatalf("full group: id=%d saved=%v err=%v", ins.id, ins.countSaved, err)
		}
		if v := declaredOf(id); v == nil || *v != 1 {
			t.Fatalf("declared_guests = %v, want 1", v)
		}
		if n := countGuests(id); n != 1 {
			t.Fatalf("guests = %d, want 1", n)
		}
	})

	t.Run("host override is kept and no count is written", func(t *testing.T) {
		two := int64(2)
		id := newRes(baseID+50, nil, &two)
		ins, err := insertGuestSaveRow(ctx, d, payloadFor(), id, meta, 5)
		if err != nil || ins.id == 0 || ins.countCode != "" {
			t.Fatalf("override: id=%d code=%q err=%v", ins.id, ins.countCode, err)
		}
		if v := declaredOf(id); v != nil {
			t.Fatalf("declared_guests = %d, want NULL", *v)
		}
	})

	t.Run("two concurrent final-slot saves insert one guest", func(t *testing.T) {
		id := newRes(baseID+60, nil, nil)
		first, err := insertGuestSaveRow(ctx, d, payloadFor(), id, meta, 2)
		if err != nil || first.id == 0 {
			t.Fatalf("first insert: id=%d err=%v", first.id, err)
		}
		var wg sync.WaitGroup
		results := make([]guestInsert, 2)
		errs := make([]error, 2)
		for i := range results {
			wg.Add(1)
			go func(i int) {
				defer wg.Done()
				results[i], errs[i] = insertGuestSaveRow(ctx, d, payloadFor(), id, meta, 0)
			}(i)
		}
		wg.Wait()
		inserted := 0
		for i := range results {
			if errs[i] != nil {
				t.Fatalf("concurrent save %d: %v", i, errs[i])
			}
			if results[i].id != 0 {
				inserted++
			}
		}
		if inserted != 1 {
			t.Fatalf("concurrent saves inserted %d guests, want exactly 1", inserted)
		}
		if n := countGuests(id); n != 2 {
			t.Fatalf("guests = %d, want 2 (first guest plus one final slot)", n)
		}
		if v := declaredOf(id); v == nil || *v != 2 {
			t.Fatalf("declared_guests = %v, want 2", v)
		}
	})
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

// synthJPEGSeed is a synthetic 64x64 JPEG parameterized by pixel multiplier; no real passport image is used.
func synthJPEGSeed(t *testing.T, mult uint8) []byte {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 64, 64))
	for i := range img.Pix {
		img.Pix[i] = uint8(i) * mult
	}
	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, img, &jpeg.Options{Quality: 80}); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

// synthJPEG is a synthetic 64x64 JPEG; no real passport image is used.
func synthJPEG(t *testing.T) []byte {
	t.Helper()
	return synthJPEGSeed(t, 7)
}

func TestPassportRequired(t *testing.T) {
	cases := []struct {
		name, policy, nationality, enteredBy, verifiedAt string
		want                                             bool
	}{
		{"policy off", "off", "DEU", "guest", "", false},
		{"empty policy", "", "DEU", "guest", "", false},
		{"case and space", " Required_Foreign ", "DEU", "guest", "", true},
		{"czech", "required_foreign", "CZE", "guest", "", false},
		{"czech lower case", "required_foreign", "cze", "guest", "", false},
		{"empty nationality", "required_foreign", "", "guest", "", false},
		{"host entered", "required_foreign", "DEU", "host", "", false},
		{"empty entered_by counts as guest", "required_foreign", "DEU", "", "", true},
		{"identity verified", "required_foreign", "DEU", "guest", "2026-01-01T00:00:00Z", false},
		{"new guest foreign", "required_foreign", "DEU", "guest", "", true},
	}
	for _, c := range cases {
		if got := passportRequired(c.policy, c.nationality, c.enteredBy, c.verifiedAt); got != c.want {
			t.Errorf("%s: passportRequired = %v, want %v", c.name, got, c.want)
		}
	}
}

func TestGuestSavePassportPhoto(t *testing.T) {
	keys, err := secure.LoadDataKeys(testDataEnv)
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	body, ext, err := passportphotos.Prepare(synthJPEG(t), "image/jpeg")
	if err != nil {
		t.Fatalf("prepare: %v", err)
	}
	if err := passportphotos.SavePrepared(dir, keys, 4242, body, ext); err != nil {
		t.Fatalf("save: %v", err)
	}
	encPath := filepath.Join(passportphotos.PhotosDir(dir), "4242"+ext+".enc")
	info, err := os.Stat(encPath)
	if err != nil {
		t.Fatalf("stat encrypted file: %v", err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("mode = %v, want 0600", info.Mode().Perm())
	}
	raw, err := os.ReadFile(encPath)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.HasPrefix(raw, []byte{0xFF, 0xD8, 0xFF}) {
		t.Fatal("stored file is a plaintext JPEG")
	}
	plain, _, ok := passportphotos.Read(dir, keys, 4242)
	if !ok || !bytes.HasPrefix(plain, []byte{0xFF, 0xD8, 0xFF}) {
		t.Fatalf("decrypt: ok=%v", ok)
	}
	if !passportphotos.Has(dir, 4242) || passportphotos.Has(dir, 4243) {
		t.Fatal("Has: want true for 4242 and false for 4243")
	}
	// A replacement that cannot be written keeps the prior photo (temp path blocked by a directory).
	if err := os.Mkdir(filepath.Join(passportphotos.PhotosDir(dir), "4242"+ext+".enc.tmp"), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := passportphotos.SavePrepared(dir, keys, 4242, body, ext); err == nil {
		t.Fatal("replacement with blocked temp path: want error")
	}
	if _, _, ok := passportphotos.Read(dir, keys, 4242); !ok {
		t.Fatal("prior photo lost after failed replacement")
	}
}

func TestPassportUploadTextAllLanguages(t *testing.T) {
	msgs := []string{
		"Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).",
		"The uploaded file looks empty.",
		"The PDF is too large. Use a file under 15 MB.",
		"The file does not look like a valid PDF.",
		"The photo is too large. Use a file under 5 MB.",
		"The file does not look like a valid image.",
		"The photo has too many pixels. Take it again at the normal camera setting.",
	}
	for _, lang := range []string{"en", "cs", "de", "es", "fr", "uk"} {
		for _, msg := range msgs {
			got := passportUploadText(lang, msg)
			if got == "" || (lang != "en" && got == msg) {
				t.Errorf("%s: %q not translated (got %q)", lang, msg, got)
			}
		}
	}
}

type passportHookCount struct {
	onComplete int
	notify     int
}

func (h *passportHookCount) OnRegistrationComplete(context.Context, int64) { h.onComplete++ }

func (h *passportHookCount) MaybeNotifyCompletion(context.Context, int64, int64, bool) error {
	h.notify++
	return nil
}

// TestGuestSavePassportPhotoHTTP posts a real multipart form through the mux with
// the CSRF token and cookie from the claim page, as the browser does.
func TestGuestSavePassportPhotoHTTP(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	keys, err := secure.LoadDataKeys(testDataEnv)
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	wrap := func(_ string, h http.HandlerFunc) http.Handler { return h }
	var sigPNG bytes.Buffer
	if err := png.Encode(&sigPNG, image.NewRGBA(image.Rect(0, 0, 8, 8))); err != nil {
		t.Fatal(err)
	}
	signature := "data:image/png;base64," + base64.StdEncoding.EncodeToString(sigPNG.Bytes())
	jpg := synthJPEG(t)
	oversized := append([]byte{0xFF, 0xD8, 0xFF}, make([]byte, 5<<20)...)
	cases := []struct {
		name, policy, nationality, ctype string
		file                             []byte
		wantStatus, wantRows             int
		wantPhoto, wantHook              bool
		wantBodySub                      string
	}{
		{"required, no file", "required_foreign", "DEU", "", nil, http.StatusUnprocessableEntity, 0, false, false, stringsCatalog.T("en", "passport_photo_missing", nil)},
		{"required, text file", "required_foreign", "DEU", "text/plain", []byte("not a photo"), http.StatusUnprocessableEntity, 0, false, false, passportUploadText("en", "Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).")},
		{"required, oversized jpeg", "required_foreign", "DEU", "image/jpeg", oversized, http.StatusUnprocessableEntity, 0, false, false, passportUploadText("en", "The photo is too large. Use a file under 5 MB.")},
		{"required, valid jpeg", "required_foreign", "DEU", "image/jpeg", jpg, http.StatusSeeOther, 1, true, true, ""},
		{"off, file ignored", "off", "DEU", "image/jpeg", jpg, http.StatusSeeOther, 1, false, true, ""},
		{"czech, no file", "required_foreign", "CZE", "", nil, http.StatusSeeOther, 1, false, true, ""},
	}
	for i, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			base := time.Now().UnixNano()%1000000000 + 9300000 + int64(i)*10
			userID, aptID, resID := base, base+1, base+2
			tok := fmt.Sprintf("passporthttp%d", base)
			mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
				VALUES ($1, $2, 'x', 'host', 1, $3)`, userID, fmt.Sprintf("ph%d@example.test", base), stamp)
			mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at, passport_photo_policy)
				VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4, $5)`, aptID, userID, tok, stamp, c.policy)
			mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
				VALUES ($1, $2, $3, 'active', 'manual', '2026-06-20', '2026-06-22', $4, $4)`, resID, aptID, fmt.Sprintf("ph-%d", resID), stamp)
			mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
				VALUES ($1, 'claimed', '', 1, $2, $2)`, resID, stamp)
			t.Cleanup(func() {
				bg := context.Background()
				_, _ = pool.Exec(bg, `DELETE FROM guest WHERE reservation_id = $1`, resID)
				_, _ = pool.Exec(bg, `DELETE FROM reservation_claim WHERE reservation_id = $1`, resID)
				_, _ = pool.Exec(bg, `DELETE FROM reservation WHERE id = $1`, resID)
				_, _ = pool.Exec(bg, `DELETE FROM apartment WHERE id = $1`, aptID)
				_, _ = pool.Exec(bg, `DELETE FROM user_account WHERE id = $1`, userID)
			})
			dir := t.TempDir()
			getenv := func(k string) string {
				switch k {
				case "UBYHOST_DATA_DIR":
					return dir
				case "UBYHOST_GUEST_PIN":
					return "0"
				case "UBYHOST_MAIL_BACKEND":
					return "console"
				}
				return testDataEnv(k)
			}
			hooks := &passportHookCount{}
			mux := http.NewServeMux()
			RegisterStayClaim(mux, pool, getenv, now, wrap, nil)
			RegisterFormSave(mux, pool, getenv, now, wrap, hooks)
			getRec := httptest.NewRecorder()
			mux.ServeHTTP(getRec, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/claim?lang=en", tok, resID), nil))
			csrf := extractPageCSRF(getRec.Body.String())
			cookie := csrfCookie(getRec.Result().Cookies())
			if csrf == "" || cookie == "" {
				t.Fatalf("csrf token %q, cookie %q, GET status %d", csrf, cookie, getRec.Code)
			}
			var buf bytes.Buffer
			mw := multipart.NewWriter(&buf)
			for k, v := range map[string]string{
				"_csrf": csrf, "surname": "Synthetic", "first_name": "Guest", "birth_date": "02.01.1990",
				"nationality": c.nationality, "doc_number": "SYNTHETIC-DOC", "res_street": "Test Street",
				"res_city": "Test City", "res_country": "CZE", "purpose": "99", "signature": signature,
				"legal_ack": "1", "party_size": "2",
			} {
				if err := mw.WriteField(k, v); err != nil {
					t.Fatal(err)
				}
			}
			if c.file != nil {
				part, err := mw.CreatePart(textproto.MIMEHeader{
					"Content-Disposition": {`form-data; name="passport_photo"; filename="passport"`},
					"Content-Type":        {c.ctype},
				})
				if err != nil {
					t.Fatal(err)
				}
				if _, err := part.Write(c.file); err != nil {
					t.Fatal(err)
				}
			}
			if err := mw.Close(); err != nil {
				t.Fatal(err)
			}
			req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/l/%s/%d/save?lang=en", tok, resID), &buf)
			req.Header.Set("Content-Type", mw.FormDataContentType())
			req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: cookie})
			rec := httptest.NewRecorder()
			mux.ServeHTTP(rec, req)
			if rec.Code != c.wantStatus {
				body := rec.Body.String()
				if len(body) > 200 {
					body = body[:200] + "..."
				}
				t.Fatalf("status = %d, want %d; body: %s", rec.Code, c.wantStatus, body)
			}
			if c.wantBodySub != "" && !strings.Contains(rec.Body.String(), c.wantBodySub) {
				t.Fatalf("response body missing expected refusal %q", c.wantBodySub)
			}
			var rows, guestID int64
			var stampAt string
			if err := pool.QueryRow(ctx, `SELECT COUNT(*), COALESCE(MIN(id), 0), COALESCE(MIN(passport_photo_at::text), '') FROM guest WHERE reservation_id = $1`, resID).Scan(&rows, &guestID, &stampAt); err != nil {
				t.Fatal(err)
			}
			if rows != int64(c.wantRows) {
				t.Fatalf("guest rows = %d, want %d", rows, c.wantRows)
			}
			if (stampAt != "") != c.wantPhoto {
				t.Fatalf("passport_photo_at = %q, want set=%v", stampAt, c.wantPhoto)
			}
			if passportphotos.Has(dir, guestID) != c.wantPhoto {
				t.Fatalf("photo on disk = %v, want %v", !c.wantPhoto, c.wantPhoto)
			}
			if c.wantPhoto {
				encPath := filepath.Join(passportphotos.PhotosDir(dir), fmt.Sprintf("%d.jpg.enc", guestID))
				fi, err := os.Stat(encPath)
				if err != nil {
					t.Fatal(err)
				}
				if fi.Mode().Perm() != 0o600 {
					t.Fatalf("photo file mode = %04o, want 0600", fi.Mode().Perm())
				}
				diskBytes, err := os.ReadFile(encPath)
				if err != nil {
					t.Fatal(err)
				}
				if bytes.HasPrefix(diskBytes, []byte{0xFF, 0xD8, 0xFF}) {
					t.Fatal("stored photo on disk has plaintext JPEG header")
				}
				plain, _, ok := passportphotos.Read(dir, keys, guestID)
				if !ok || !bytes.HasPrefix(plain, []byte{0xFF, 0xD8, 0xFF}) {
					t.Fatalf("stored photo does not decrypt to a JPEG (ok=%v)", ok)
				}
			}
			// 2096: individual guest form save defers completion hooks until confirm-registration.
			if hooks.onComplete != 0 || hooks.notify != 0 {
				t.Fatalf("completion hooks = (%d, %d), want (0, 0)", hooks.onComplete, hooks.notify)
			}
		})
	}
}

func TestGuestSavePassportPhotoExistingGuestHTTP(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	keys, err := secure.LoadDataKeys(testDataEnv)
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	prevPhotoStamp := "2026-06-15T10:00:00Z"
	hostVerifiedStamp := "2026-06-15T09:00:00Z"
	nowTime := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	nowS := nowTime.Format(time.RFC3339)
	now := func() time.Time { return nowTime }
	wrap := func(_ string, h http.HandlerFunc) http.Handler { return h }
	var sigPNG bytes.Buffer
	if err := png.Encode(&sigPNG, image.NewRGBA(image.Rect(0, 0, 8, 8))); err != nil {
		t.Fatal(err)
	}
	signature := "data:image/png;base64," + base64.StdEncoding.EncodeToString(sigPNG.Bytes())
	origJPG := synthJPEGSeed(t, 7)
	newJPG := synthJPEGSeed(t, 13)

	seedAndPost := func(t *testing.T, offset int64, photoAt, verifiedAt *string, seedPhoto bool, postNat string, upload []byte) (*httptest.ResponseRecorder, string, int64, []byte, []byte, *passportHookCount) {
		t.Helper()
		base := time.Now().UnixNano()%1000000000 + 9400000 + offset*10
		userID, aptID, resID, guestID := base, base+1, base+2, base+3
		tok := fmt.Sprintf("passportexist%d", base)
		mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
			VALUES ($1, $2, 'x', 'host', 1, $3)`, userID, fmt.Sprintf("pe%d@example.test", base), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at, passport_photo_policy)
			VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4, 'required_foreign')`, aptID, userID, tok, stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
			VALUES ($1, $2, $3, 'active', 'manual', '2026-06-20', '2026-06-22', $4, $4)`, resID, aptID, fmt.Sprintf("pe-%d", resID), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
			VALUES ($1, 'claimed', '', 1, $2, $2)`, resID, stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, nationality,
			res_country, purpose, is_lead, entered_by, submit_state, stay_from, stay_to, passport_photo_at, identity_verified_at)
			VALUES ($1, $2, $3, $3, 'Guest', 'Synthetic', 'DEU', 'CZE', '99', 1, 'guest', 'pending', '2026-06-20', '2026-06-22', $4, $5)`,
			guestID, resID, stamp, photoAt, verifiedAt)
		t.Cleanup(func() {
			bg := context.Background()
			_, _ = pool.Exec(bg, `DELETE FROM guest WHERE reservation_id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM reservation_claim WHERE reservation_id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM reservation WHERE id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM apartment WHERE id = $1`, aptID)
			_, _ = pool.Exec(bg, `DELETE FROM user_account WHERE id = $1`, userID)
		})
		dir := t.TempDir()
		var origDiskBytes, origPlain []byte
		if seedPhoto {
			body, ext, err := passportphotos.Prepare(origJPG, "image/jpeg")
			if err != nil {
				t.Fatal(err)
			}
			if err := passportphotos.SavePrepared(dir, keys, guestID, body, ext); err != nil {
				t.Fatal(err)
			}
			origPlain = body
			origDiskBytes, err = os.ReadFile(filepath.Join(passportphotos.PhotosDir(dir), fmt.Sprintf("%d%s.enc", guestID, ext)))
			if err != nil {
				t.Fatal(err)
			}
		}
		getenv := func(k string) string {
			switch k {
			case "UBYHOST_DATA_DIR":
				return dir
			case "UBYHOST_GUEST_PIN":
				return "0"
			case "UBYHOST_MAIL_BACKEND":
				return "console"
			}
			return testDataEnv(k)
		}
		hooks := &passportHookCount{}
		mux := http.NewServeMux()
		RegisterStayClaim(mux, pool, getenv, now, wrap, nil)
		RegisterFormSave(mux, pool, getenv, now, wrap, hooks)
		getRec := httptest.NewRecorder()
		mux.ServeHTTP(getRec, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/claim?lang=en", tok, resID), nil))
		csrf := extractPageCSRF(getRec.Body.String())
		csrfCook := csrfCookie(getRec.Result().Cookies())
		if csrf == "" || csrfCook == "" {
			t.Fatalf("csrf token %q, cookie %q, GET status %d", csrf, csrfCook, getRec.Code)
		}
		ownRec := httptest.NewRecorder()
		rememberOwnedGuestIDs(ownRec, getenv, []int64{guestID})

		var buf bytes.Buffer
		mw := multipart.NewWriter(&buf)
		for k, v := range map[string]string{
			"_csrf": csrf, "guest_id": fmt.Sprintf("%d", guestID),
			"surname": "Synthetic", "first_name": "Guest", "birth_date": "02.01.1990",
			"nationality": postNat, "doc_number": "SYNTHETIC-DOC", "res_street": "Test Street",
			"res_city": "Test City", "res_country": "CZE", "purpose": "99", "signature": signature,
			"legal_ack": "1",
		} {
			if err := mw.WriteField(k, v); err != nil {
				t.Fatal(err)
			}
		}
		if upload != nil {
			part, err := mw.CreatePart(textproto.MIMEHeader{
				"Content-Disposition": {`form-data; name="passport_photo"; filename="passport.jpg"`},
				"Content-Type":        {"image/jpeg"},
			})
			if err != nil {
				t.Fatal(err)
			}
			if _, err := part.Write(upload); err != nil {
				t.Fatal(err)
			}
		}
		if err := mw.Close(); err != nil {
			t.Fatal(err)
		}
		req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/l/%s/%d/save?lang=en", tok, resID), &buf)
		req.Header.Set("Content-Type", mw.FormDataContentType())
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfCook})
		for _, ck := range ownRec.Result().Cookies() {
			req.AddCookie(ck)
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		return rec, dir, guestID, origDiskBytes, origPlain, hooks
	}

	t.Run("stamped with file on disk and no new upload", func(t *testing.T) {
		rec, dir, guestID, origDiskBytes, _, hooks := seedAndPost(t, 1, &prevPhotoStamp, nil, true, "DEU", nil)
		if rec.Code != http.StatusSeeOther {
			body := rec.Body.String()
			if len(body) > 200 {
				body = body[:200] + "..."
			}
			t.Fatalf("status = %d, want 303; body: %s", rec.Code, body)
		}
		diskBytes, err := os.ReadFile(filepath.Join(passportphotos.PhotosDir(dir), fmt.Sprintf("%d.jpg.enc", guestID)))
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(diskBytes, origDiskBytes) {
			t.Fatal("existing photo bytes changed on edit without upload")
		}
		var stampAt string
		if err := pool.QueryRow(ctx, `SELECT COALESCE(passport_photo_at::text, '') FROM guest WHERE id = $1`, guestID).Scan(&stampAt); err != nil {
			t.Fatal(err)
		}
		if stampAt != prevPhotoStamp {
			t.Fatalf("passport_photo_at = %q, want %q", stampAt, prevPhotoStamp)
		}
		if hooks.onComplete != 0 || hooks.notify != 0 {
			t.Fatalf("completion hooks = (%d, %d), want (0, 0)", hooks.onComplete, hooks.notify)
		}
	})

	t.Run("stamped with file deleted on disk and CZE posted", func(t *testing.T) {
		rec, _, _, _, _, hooks := seedAndPost(t, 2, &prevPhotoStamp, nil, false, "CZE", nil)
		if rec.Code != http.StatusUnprocessableEntity {
			body := rec.Body.String()
			if len(body) > 200 {
				body = body[:200] + "..."
			}
			t.Fatalf("status = %d, want 422; body: %s", rec.Code, body)
		}
		wantMsg := stringsCatalog.T("en", "passport_photo_missing", nil)
		if !strings.Contains(rec.Body.String(), wantMsg) {
			t.Fatalf("422 body missing %q", wantMsg)
		}
		if hooks.onComplete != 0 || hooks.notify != 0 {
			t.Fatalf("completion hooks = (%d, %d), want (0, 0)", hooks.onComplete, hooks.notify)
		}
	})

	t.Run("existing guest replaces photo with new valid jpeg", func(t *testing.T) {
		rec, dir, guestID, origDiskBytes, origPlain, hooks := seedAndPost(t, 3, &prevPhotoStamp, nil, true, "DEU", newJPG)
		if rec.Code != http.StatusSeeOther {
			body := rec.Body.String()
			if len(body) > 200 {
				body = body[:200] + "..."
			}
			t.Fatalf("status = %d, want 303; body: %s", rec.Code, body)
		}
		encPath := filepath.Join(passportphotos.PhotosDir(dir), fmt.Sprintf("%d.jpg.enc", guestID))
		fi, err := os.Stat(encPath)
		if err != nil {
			t.Fatal(err)
		}
		if fi.Mode().Perm() != 0o600 {
			t.Fatalf("photo file mode = %04o, want 0600", fi.Mode().Perm())
		}
		diskBytes, err := os.ReadFile(encPath)
		if err != nil {
			t.Fatal(err)
		}
		if bytes.HasPrefix(diskBytes, []byte{0xFF, 0xD8, 0xFF}) {
			t.Fatal("stored photo on disk has plaintext JPEG header")
		}
		if bytes.Equal(diskBytes, origDiskBytes) {
			t.Fatal("replacement photo bytes equal original bytes")
		}
		wantNewPlain, _, err := passportphotos.Prepare(newJPG, "image/jpeg")
		if err != nil {
			t.Fatal(err)
		}
		gotPlain, _, ok := passportphotos.Read(dir, keys, guestID)
		if !ok || !bytes.HasPrefix(gotPlain, []byte{0xFF, 0xD8, 0xFF}) {
			t.Fatalf("replaced photo does not decrypt to a JPEG (ok=%v)", ok)
		}
		if !bytes.Equal(gotPlain, wantNewPlain) {
			t.Fatal("decrypted replacement photo does not match prepared new JPEG")
		}
		if bytes.Equal(gotPlain, origPlain) {
			t.Fatal("decrypted replacement photo matches original JPEG")
		}
		var stampAt string
		if err := pool.QueryRow(ctx, `SELECT COALESCE(passport_photo_at::text, '') FROM guest WHERE id = $1`, guestID).Scan(&stampAt); err != nil {
			t.Fatal(err)
		}
		if stampAt != nowS {
			t.Fatalf("passport_photo_at = %q, want %q", stampAt, nowS)
		}
		if hooks.onComplete != 0 || hooks.notify != 0 {
			t.Fatalf("completion hooks = (%d, %d), want (0, 0)", hooks.onComplete, hooks.notify)
		}
	})

	t.Run("host-verified existing guest needs no photo", func(t *testing.T) {
		rec, dir, guestID, _, _, hooks := seedAndPost(t, 4, nil, &hostVerifiedStamp, false, "DEU", nil)
		if rec.Code != http.StatusSeeOther {
			body := rec.Body.String()
			if len(body) > 200 {
				body = body[:200] + "..."
			}
			t.Fatalf("status = %d, want 303; body: %s", rec.Code, body)
		}
		if passportphotos.Has(dir, guestID) {
			t.Fatal("host-verified guest unexpectedly has photo on disk")
		}
		if hooks.onComplete != 0 || hooks.notify != 0 {
			t.Fatalf("completion hooks = (%d, %d), want (0, 0)", hooks.onComplete, hooks.notify)
		}
	})
}

func TestGuestSavePassportPhotoIOFailure(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	if os.Geteuid() == 0 {
		t.Skip("running as root bypasses 0500 directory permissions")
	}
	keys, err := secure.LoadDataKeys(testDataEnv)
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	prevPhotoStamp := "2026-06-15T10:00:00Z"
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	wrap := func(_ string, h http.HandlerFunc) http.Handler { return h }
	var sigPNG bytes.Buffer
	if err := png.Encode(&sigPNG, image.NewRGBA(image.Rect(0, 0, 8, 8))); err != nil {
		t.Fatal(err)
	}
	signature := "data:image/png;base64," + base64.StdEncoding.EncodeToString(sigPNG.Bytes())
	origJPG := synthJPEGSeed(t, 7)
	newJPG := synthJPEGSeed(t, 13)

	t.Run("new guest photo write failure", func(t *testing.T) {
		base := time.Now().UnixNano()%1000000000 + 9500000
		userID, aptID, resID := base, base+1, base+2
		tok := fmt.Sprintf("passportio%d", base)
		mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
			VALUES ($1, $2, 'x', 'host', 1, $3)`, userID, fmt.Sprintf("pio%d@example.test", base), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at, passport_photo_policy)
			VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4, 'required_foreign')`, aptID, userID, tok, stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
			VALUES ($1, $2, $3, 'active', 'manual', '2026-06-20', '2026-06-22', $4, $4)`, resID, aptID, fmt.Sprintf("pio-%d", resID), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
			VALUES ($1, 'claimed', '', 1, $2, $2)`, resID, stamp)
		t.Cleanup(func() {
			bg := context.Background()
			_, _ = pool.Exec(bg, `DELETE FROM guest WHERE reservation_id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM reservation_claim WHERE reservation_id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM reservation WHERE id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM apartment WHERE id = $1`, aptID)
			_, _ = pool.Exec(bg, `DELETE FROM user_account WHERE id = $1`, userID)
		})
		dir := t.TempDir()
		photosDir := passportphotos.PhotosDir(dir)
		if err := os.MkdirAll(photosDir, 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.Chmod(photosDir, 0o500); err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { _ = os.Chmod(photosDir, 0o700) })

		getenv := func(k string) string {
			switch k {
			case "UBYHOST_DATA_DIR":
				return dir
			case "UBYHOST_GUEST_PIN":
				return "0"
			case "UBYHOST_MAIL_BACKEND":
				return "console"
			}
			return testDataEnv(k)
		}
		hooks := &passportHookCount{}
		mux := http.NewServeMux()
		RegisterStayClaim(mux, pool, getenv, now, wrap, nil)
		RegisterFormSave(mux, pool, getenv, now, wrap, hooks)
		getRec := httptest.NewRecorder()
		mux.ServeHTTP(getRec, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/claim?lang=en", tok, resID), nil))
		csrf := extractPageCSRF(getRec.Body.String())
		csrfCook := csrfCookie(getRec.Result().Cookies())
		if csrf == "" || csrfCook == "" {
			t.Fatalf("csrf token %q, cookie %q, GET status %d", csrf, csrfCook, getRec.Code)
		}
		var buf bytes.Buffer
		mw := multipart.NewWriter(&buf)
		for k, v := range map[string]string{
			"_csrf": csrf, "surname": "Synthetic", "first_name": "Guest", "birth_date": "02.01.1990",
			"nationality": "DEU", "doc_number": "SYNTHETIC-DOC", "res_street": "Test Street",
			"res_city": "Test City", "res_country": "CZE", "purpose": "99", "signature": signature,
			"legal_ack": "1", "party_size": "2",
		} {
			if err := mw.WriteField(k, v); err != nil {
				t.Fatal(err)
			}
		}
		part, err := mw.CreatePart(textproto.MIMEHeader{
			"Content-Disposition": {`form-data; name="passport_photo"; filename="passport.jpg"`},
			"Content-Type":        {"image/jpeg"},
		})
		if err != nil {
			t.Fatal(err)
		}
		if _, err := part.Write(origJPG); err != nil {
			t.Fatal(err)
		}
		if err := mw.Close(); err != nil {
			t.Fatal(err)
		}
		req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/l/%s/%d/save?lang=en", tok, resID), &buf)
		req.Header.Set("Content-Type", mw.FormDataContentType())
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfCook})
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)

		if rec.Code != http.StatusInternalServerError {
			body := rec.Body.String()
			if len(body) > 200 {
				body = body[:200] + "..."
			}
			t.Fatalf("status = %d, want 500; body: %s", rec.Code, body)
		}
		if hooks.onComplete != 0 || hooks.notify != 0 {
			t.Fatalf("completion hooks = (%d, %d), want (0, 0)", hooks.onComplete, hooks.notify)
		}
		var rows int64
		var photoAt, verifiedAt string
		if err := pool.QueryRow(ctx, `SELECT COUNT(*), COALESCE(MIN(passport_photo_at::text), ''), COALESCE(MIN(identity_verified_at::text), '') FROM guest WHERE reservation_id = $1`, resID).Scan(&rows, &photoAt, &verifiedAt); err != nil {
			t.Fatal(err)
		}
		if rows != 1 {
			t.Fatalf("guest rows = %d, want 1", rows)
		}
		if photoAt != "" || verifiedAt != "" {
			t.Fatalf("stamps = (passport_photo_at=%q, identity_verified_at=%q), want both empty", photoAt, verifiedAt)
		}
	})

	t.Run("existing guest replacement photo write failure preserves prior photo", func(t *testing.T) {
		base := time.Now().UnixNano()%1000000000 + 9500100
		userID, aptID, resID, guestID := base, base+1, base+2, base+3
		tok := fmt.Sprintf("passportio%d", base)
		mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
			VALUES ($1, $2, 'x', 'host', 1, $3)`, userID, fmt.Sprintf("pio%d@example.test", base), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at, passport_photo_policy)
			VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4, 'required_foreign')`, aptID, userID, tok, stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
			VALUES ($1, $2, $3, 'active', 'manual', '2026-06-20', '2026-06-22', $4, $4)`, resID, aptID, fmt.Sprintf("pio-%d", resID), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
			VALUES ($1, 'claimed', '', 1, $2, $2)`, resID, stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, nationality,
			res_country, purpose, is_lead, entered_by, submit_state, stay_from, stay_to, passport_photo_at)
			VALUES ($1, $2, $3, $3, 'Guest', 'Synthetic', 'DEU', 'CZE', '99', 1, 'guest', 'pending', '2026-06-20', '2026-06-22', $4)`,
			guestID, resID, stamp, prevPhotoStamp)
		t.Cleanup(func() {
			bg := context.Background()
			_, _ = pool.Exec(bg, `DELETE FROM guest WHERE reservation_id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM reservation_claim WHERE reservation_id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM reservation WHERE id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM apartment WHERE id = $1`, aptID)
			_, _ = pool.Exec(bg, `DELETE FROM user_account WHERE id = $1`, userID)
		})
		dir := t.TempDir()
		body, ext, err := passportphotos.Prepare(origJPG, "image/jpeg")
		if err != nil {
			t.Fatal(err)
		}
		if err := passportphotos.SavePrepared(dir, keys, guestID, body, ext); err != nil {
			t.Fatal(err)
		}
		encPath := filepath.Join(passportphotos.PhotosDir(dir), fmt.Sprintf("%d%s.enc", guestID, ext))
		origDiskBytes, err := os.ReadFile(encPath)
		if err != nil {
			t.Fatal(err)
		}
		photosDir := passportphotos.PhotosDir(dir)
		if err := os.Chmod(photosDir, 0o500); err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { _ = os.Chmod(photosDir, 0o700) })

		getenv := func(k string) string {
			switch k {
			case "UBYHOST_DATA_DIR":
				return dir
			case "UBYHOST_GUEST_PIN":
				return "0"
			case "UBYHOST_MAIL_BACKEND":
				return "console"
			}
			return testDataEnv(k)
		}
		hooks := &passportHookCount{}
		mux := http.NewServeMux()
		RegisterStayClaim(mux, pool, getenv, now, wrap, nil)
		RegisterFormSave(mux, pool, getenv, now, wrap, hooks)
		getRec := httptest.NewRecorder()
		mux.ServeHTTP(getRec, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/claim?lang=en", tok, resID), nil))
		csrf := extractPageCSRF(getRec.Body.String())
		csrfCook := csrfCookie(getRec.Result().Cookies())
		if csrf == "" || csrfCook == "" {
			t.Fatalf("csrf token %q, cookie %q, GET status %d", csrf, csrfCook, getRec.Code)
		}
		ownRec := httptest.NewRecorder()
		rememberOwnedGuestIDs(ownRec, getenv, []int64{guestID})

		var buf bytes.Buffer
		mw := multipart.NewWriter(&buf)
		for k, v := range map[string]string{
			"_csrf": csrf, "guest_id": fmt.Sprintf("%d", guestID),
			"surname": "Synthetic", "first_name": "Guest", "birth_date": "02.01.1990",
			"nationality": "DEU", "doc_number": "SYNTHETIC-DOC", "res_street": "Test Street",
			"res_city": "Test City", "res_country": "CZE", "purpose": "99", "signature": signature,
			"legal_ack": "1",
		} {
			if err := mw.WriteField(k, v); err != nil {
				t.Fatal(err)
			}
		}
		part, err := mw.CreatePart(textproto.MIMEHeader{
			"Content-Disposition": {`form-data; name="passport_photo"; filename="passport.jpg"`},
			"Content-Type":        {"image/jpeg"},
		})
		if err != nil {
			t.Fatal(err)
		}
		if _, err := part.Write(newJPG); err != nil {
			t.Fatal(err)
		}
		if err := mw.Close(); err != nil {
			t.Fatal(err)
		}
		req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/l/%s/%d/save?lang=en", tok, resID), &buf)
		req.Header.Set("Content-Type", mw.FormDataContentType())
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: csrfCook})
		for _, ck := range ownRec.Result().Cookies() {
			req.AddCookie(ck)
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)

		if rec.Code != http.StatusInternalServerError {
			body := rec.Body.String()
			if len(body) > 200 {
				body = body[:200] + "..."
			}
			t.Fatalf("status = %d, want 500; body: %s", rec.Code, body)
		}
		if hooks.onComplete != 0 || hooks.notify != 0 {
			t.Fatalf("completion hooks = (%d, %d), want (0, 0)", hooks.onComplete, hooks.notify)
		}
		var stampAt string
		if err := pool.QueryRow(ctx, `SELECT COALESCE(passport_photo_at::text, '') FROM guest WHERE id = $1`, guestID).Scan(&stampAt); err != nil {
			t.Fatal(err)
		}
		if stampAt != prevPhotoStamp {
			t.Fatalf("passport_photo_at = %q, want %q", stampAt, prevPhotoStamp)
		}
		diskBytes, err := os.ReadFile(encPath)
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(diskBytes, origDiskBytes) {
			t.Fatal("prior photo bytes changed after failed replacement write")
		}
	})
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
	issues := guestSaveValidateIssues(form, res, values, raw, "2026-06-01", "2026-06-05", form["signature"], false, existing, time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC), "en")
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
	issues := guestSaveValidateIssues(form, res, values, raw, "2026-06-01", "2026-06-05", form["signature"], false, nil, time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC), "en")
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

func TestCertainlyAtLeastAge(t *testing.T) {
	arrival := time.Date(2026, 6, 20, 0, 0, 0, 0, time.UTC)
	cases := []struct {
		name  string
		birth string
		when  *time.Time
		years int
		want  bool
	}{
		{"nil when", "01012000", nil, 18, false},
		{"exact 18th birthday", "20062008", &arrival, 18, true},
		{"day before 18th birthday", "21062008", &arrival, 18, false},
		{"partial unknown month and day 00002008 -> 31.12.2008 (17)", "00002008", &arrival, 18, false},
		{"partial unknown month and day 00002007 -> 31.12.2007 (18)", "00002007", &arrival, 18, true},
		{"partial unknown day 00062008 -> 30.06.2008 (17)", "00062008", &arrival, 18, false},
		{"partial unknown day 00052008 -> 31.05.2008 (18)", "00052008", &arrival, 18, true},
		{"leap-day partial 00022008 -> 29.02.2008 (18)", "00022008", &arrival, 18, true},
		{"leap-day exact 29022008 (18)", "29022008", &arrival, 18, true},
		{"leap-day non-leap 29022007 invalid", "29022007", &arrival, 18, false},
		{"invalid empty", "", &arrival, 18, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := validation.CertainlyAtLeastAge(c.birth, c.when, c.years); got != c.want {
				t.Fatalf("CertainlyAtLeastAge(%q, %v, %d) = %v, want %v", c.birth, c.when, c.years, got, c.want)
			}
		})
	}
}

func TestIsValidSignature(t *testing.T) {
	var sigPNG bytes.Buffer
	if err := png.Encode(&sigPNG, image.NewRGBA(image.Rect(0, 0, 8, 8))); err != nil {
		t.Fatal(err)
	}
	valid := "data:image/png;base64," + base64.StdEncoding.EncodeToString(sigPNG.Bytes())
	if !validation.IsValidSignature(valid) {
		t.Fatal("expected valid PNG data URL to pass IsValidSignature")
	}
	for _, bad := range []string{"", "   ", "imported", "data:image/png;base64,!!!notbase64!!!", "data:text/plain;base64,aGVsbG8="} {
		if validation.IsValidSignature(bad) {
			t.Fatalf("expected %q to fail IsValidSignature", bad)
		}
	}
}

func TestSignForWhoMissingAllLanguages(t *testing.T) {
	want := map[string]string{
		"en": "Choose the adult who is signing.",
		"cs": "Vyberte dospělého, který podepisuje.",
		"de": "Wählen Sie die unterschreibende erwachsene Person.",
		"es": "Elija al adulto que firma.",
		"fr": "Choisissez l'adulte signataire.",
		"uk": "Виберіть дорослого, що підписує.",
	}
	for lang, exp := range want {
		if got := signForWhoMissingText(lang); got != exp {
			t.Fatalf("lang %s: got %q want %q", lang, got, exp)
		}
	}
	if got := signForWhoMissingText("zz"); got != want["en"] {
		t.Fatalf("fallback lang: got %q want %q", got, want["en"])
	}
}

func TestGuestSaveChildSigner(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	keys, err := secure.LoadDataKeys(testDataEnv)
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	wrap := func(_ string, h http.HandlerFunc) http.Handler { return h }

	var sigPNG bytes.Buffer
	if err := png.Encode(&sigPNG, image.NewRGBA(image.Rect(0, 0, 8, 8))); err != nil {
		t.Fatal(err)
	}
	validSig := "data:image/png;base64," + base64.StdEncoding.EncodeToString(sigPNG.Bytes())

	type signCols struct {
		guestID     sql.NullInt64
		role        sql.NullString
		at          sql.NullString
		wording     sql.NullString
		submitState string
		attempts    int
		lastErrors  sql.NullString
		signedAt    sql.NullString
		sigEnc      sql.NullString
	}
	readSignCols := func(t *testing.T, id int64) signCols {
		t.Helper()
		var c signCols
		if err := pool.QueryRow(ctx, `SELECT signed_for_guest_id, signed_for_role, signed_for_at, signed_for_wording,
			submit_state, submit_attempts, last_errors, signed_at, signature_png_enc
			FROM guest WHERE id = $1`, id).Scan(
			&c.guestID, &c.role, &c.at, &c.wording,
			&c.submitState, &c.attempts, &c.lastErrors, &c.signedAt, &c.sigEnc,
		); err != nil {
			t.Fatalf("readSignCols(%d): %v", id, err)
		}
		return c
	}

	type stayEnv struct {
		userID, aptID, resID int64
		tok                  string
		getenv               func(string) string
		mux                  *http.ServeMux
		hooks                *passportHookCount
		csrf                 string
		csrfCookie           string
	}
	newStay := func(t *testing.T, offset int64) stayEnv {
		t.Helper()
		base := time.Now().UnixNano()%1000000000 + 8100000 + offset*100
		userID, aptID, resID := base, base+1, base+2
		tok := fmt.Sprintf("childsig%d", base)
		mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
			VALUES ($1, $2, 'x', 'host', 1, $3)`, userID, fmt.Sprintf("cs%d@example.test", base), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at, passport_photo_policy)
			VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4, 'off')`, aptID, userID, tok, stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
			VALUES ($1, $2, $3, 'active', 'manual', '2026-06-20', '2026-06-22', $4, $4)`, resID, aptID, fmt.Sprintf("cs-%d", resID), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
			VALUES ($1, 'claimed', '', 1, $2, $2)`, resID, stamp)
		t.Cleanup(func() {
			bg := context.Background()
			_, _ = pool.Exec(bg, `DELETE FROM guest WHERE reservation_id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM reservation_claim WHERE reservation_id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM reservation WHERE id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM apartment WHERE id = $1`, aptID)
			_, _ = pool.Exec(bg, `DELETE FROM user_account WHERE id = $1`, userID)
		})
		getenv := func(k string) string {
			switch k {
			case "UBYHOST_GUEST_PIN":
				return "0"
			case "UBYHOST_MAIL_BACKEND":
				return "disabled"
			}
			return testDataEnv(k)
		}
		hooks := &passportHookCount{}
		mux := http.NewServeMux()
		RegisterStayClaim(mux, pool, getenv, now, wrap, nil)
		RegisterFormPages(mux, pool, getenv, now, wrap)
		RegisterFormSave(mux, pool, getenv, now, wrap, hooks)
		getRec := httptest.NewRecorder()
		mux.ServeHTTP(getRec, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/claim?lang=en", tok, resID), nil))
		csrf := extractPageCSRF(getRec.Body.String())
		cookie := csrfCookie(getRec.Result().Cookies())
		if csrf == "" || cookie == "" {
			t.Fatalf("csrf %q cookie %q status %d", csrf, cookie, getRec.Code)
		}
		return stayEnv{userID, aptID, resID, tok, getenv, mux, hooks, csrf, cookie}
	}

	seedGuest := func(t *testing.T, resID int64, first, surname, birth, sig, state string, attempts int, lastErr string, archived bool, signedForID *int64, signedForRole, signedForAt, signedForWording string) int64 {
		t.Helper()
		enc, err := secure.GuestWriteValues(keys, map[string]any{
			"birth_date": birth, "doc_number": "DOC12345", "visa_number": "",
			"res_street": "Main 1", "res_city": "Berlin", "signature_png": sig,
		})
		if err != nil {
			t.Fatal(err)
		}
		var arch any
		if archived {
			arch = stamp
		}
		var sfID, sfRole, sfAt, sfWord any
		if signedForID != nil {
			sfID, sfRole, sfAt, sfWord = *signedForID, signedForRole, signedForAt, signedForWording
		}
		var le any
		if lastErr != "" {
			le = lastErr
		}
		var id int64
		if err := pool.QueryRow(ctx, `INSERT INTO guest (
			reservation_id, is_lead, surname, first_name, nationality, res_country, purpose, note,
			stay_from, stay_to, submit_state, submit_attempts, last_errors, created_at, updated_at,
			birth_date_enc, doc_number_enc, visa_number_enc, res_street_enc, res_city_enc, signature_png_enc,
			archived_at, signed_for_guest_id, signed_for_role, signed_for_at, signed_for_wording
		) VALUES ($1,0,$2,$3,'DEU','DEU','99','','2026-06-20','2026-06-22',$4,$5,$6,$7,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
		RETURNING id`,
			resID, surname, first, state, attempts, le, stamp,
			enc["birth_date_enc"], enc["doc_number_enc"], enc["visa_number_enc"],
			enc["res_street_enc"], enc["res_city_enc"], enc["signature_png_enc"],
			arch, sfID, sfRole, sfAt, sfWord,
		).Scan(&id); err != nil {
			t.Fatalf("seedGuest: %v", err)
		}
		return id
	}

	postForm := func(t *testing.T, se stayEnv, lang string, owned []int64, vals url.Values) *httptest.ResponseRecorder {
		t.Helper()
		vals.Set("_csrf", se.csrf)
		req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/l/%s/%d/save?lang=%s", se.tok, se.resID, lang), strings.NewReader(vals.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: se.csrfCookie})
		if len(owned) > 0 {
			ownRec := httptest.NewRecorder()
			rememberOwnedGuestIDs(ownRec, se.getenv, owned)
			for _, c := range ownRec.Result().Cookies() {
				req.AddCookie(c)
			}
		}
		rec := httptest.NewRecorder()
		se.mux.ServeHTTP(rec, req)
		return rec
	}

	baseChildForm := func() url.Values {
		return url.Values{
			"surname":     {"Novak"},
			"first_name":  {"Lukas"},
			"birth_date":  {"10.05.2016"},
			"nationality": {"DEU"},
			"doc_number":  {"CHILD123"},
			"res_street":  {"Main 1"},
			"res_city":    {"Berlin"},
			"res_country": {"DEU"},
			"purpose":     {"99"},
			"legal_ack":   {"1"},
			"party_size":  {"10"},
		}
	}

	baseAdultForm := func() url.Values {
		return url.Values{
			"surname":     {"Novak"},
			"first_name":  {"Anna"},
			"birth_date":  {"10.05.1990"},
			"nationality": {"DEU"},
			"doc_number":  {"ADULT123"},
			"res_street":  {"Main 1"},
			"res_city":    {"Berlin"},
			"res_country": {"DEU"},
			"purpose":     {"99"},
			"signature":   {validSig},
			"legal_ack":   {"1"},
			"party_size":  {"10"},
		}
	}

	latestGuestID := func(t *testing.T, resID int64) int64 {
		t.Helper()
		var id int64
		if err := pool.QueryRow(ctx, `SELECT id FROM guest WHERE reservation_id = $1 ORDER BY id DESC LIMIT 1`, resID).Scan(&id); err != nil {
			t.Fatalf("latestGuestID: %v", err)
		}
		return id
	}

	t.Run("1_zero_eligible_signers", func(t *testing.T) {
		se := newStay(t, 1)
		rec := postForm(t, se, "en", nil, baseChildForm())
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("want 303, got %d: %s", rec.Code, rec.Body.String())
		}
		cid := latestGuestID(t, se.resID)
		c := readSignCols(t, cid)
		if c.submitState != "pending" || c.guestID.Valid || c.role.Valid || c.at.Valid || c.wording.Valid || c.signedAt.Valid {
			t.Fatalf("unexpected cols: %+v", c)
		}
		// With child_sign_role=parent and no signed_by when 0 signers -> still saves with NULL link.
		f2 := baseChildForm()
		f2.Set("first_name", "Mila")
		f2.Set("child_sign_role", "parent")
		rec2 := postForm(t, se, "en", []int64{cid}, f2)
		if rec2.Code != http.StatusSeeOther {
			t.Fatalf("want 303, got %d", rec2.Code)
		}
		c2 := readSignCols(t, latestGuestID(t, se.resID))
		if c2.guestID.Valid || c2.role.Valid || c2.at.Valid || c2.wording.Valid {
			t.Fatalf("expected NULL link with 0 signers: %+v", c2)
		}
	})

	t.Run("2_one_eligible_adult_signer", func(t *testing.T) {
		se := newStay(t, 2)
		adultID := seedGuest(t, se.resID, "Anna", "Novak", "10051990", validSig, "pending", 0, "", false, nil, "", "", "")

		f := baseChildForm()
		f.Set("signed_by", fmt.Sprintf("%d", adultID))
		f.Set("child_sign_role", "parent")
		rec := postForm(t, se, "en", []int64{adultID}, f)
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("want 303, got %d: %s", rec.Code, rec.Body.String())
		}
		childID := latestGuestID(t, se.resID)
		c := readSignCols(t, childID)
		if !c.guestID.Valid || c.guestID.Int64 != adultID || c.role.String != "parent" || c.at.String == "" || c.wording.String != signForWordingVersion || c.submitState != "pending" {
			t.Fatalf("unexpected linked child cols: %+v", c)
		}
		sigPlain, _ := decryptGuestField(se.getenv, now, c.sigEnc.String, "")
		if sigPlain != "" {
			t.Fatalf("expected empty child signature, got %q", sigPlain)
		}

		// Child edit without signed_by / child_sign_role preserves existing 4 columns.
		edit := baseChildForm()
		edit.Set("guest_id", fmt.Sprintf("%d", childID))
		edit.Set("first_name", "LukasEdited")
		recEdit := postForm(t, se, "en", []int64{adultID, childID}, edit)
		if recEdit.Code != http.StatusSeeOther {
			t.Fatalf("edit want 303, got %d: %s", recEdit.Code, recEdit.Body.String())
		}
		cEdit := readSignCols(t, childID)
		if !cEdit.guestID.Valid || cEdit.guestID.Int64 != adultID || cEdit.role.String != "parent" || cEdit.at.String != c.at.String || cEdit.wording.String != signForWordingVersion {
			t.Fatalf("edit lost link: got %+v, want %+v", cEdit, c)
		}

		// 1 eligible signer with child_sign_role=parent and empty signed_by -> saves with NULL link (no 422).
		f3 := baseChildForm()
		f3.Set("first_name", "Ema")
		f3.Set("child_sign_role", "parent")
		rec3 := postForm(t, se, "en", []int64{adultID, childID}, f3)
		if rec3.Code != http.StatusSeeOther {
			t.Fatalf("want 303 with 1 signer and empty signed_by, got %d", rec3.Code)
		}
		c3 := readSignCols(t, latestGuestID(t, se.resID))
		if c3.guestID.Valid || c3.role.Valid || c3.at.Valid || c3.wording.Valid {
			t.Fatalf("expected NULL link: %+v", c3)
		}
	})

	t.Run("3_multiple_eligible_adult_signers", func(t *testing.T) {
		se := newStay(t, 3)
		adult1 := seedGuest(t, se.resID, "Anna", "Novak", "10051990", validSig, "pending", 0, "", false, nil, "", "", "")
		adult2 := seedGuest(t, se.resID, "Petr", "Novak", "15081988", validSig, "pending", 0, "", false, nil, "", "", "")
		owned := []int64{adult1, adult2}

		// Missing signed_by with role=parent -> 422 EN.
		f := baseChildForm()
		f.Set("child_sign_role", "parent")
		rec := postForm(t, se, "en", owned, f)
		if rec.Code != http.StatusUnprocessableEntity {
			t.Fatalf("want 422, got %d", rec.Code)
		}
		body := rec.Body.String()
		for _, want := range []string{
			`id="signed_by-error"`,
			`Choose the adult who is signing.`,
			`id="signed_by"`,
			`aria-invalid="true"`,
			`name="child_sign_role" value="parent" checked`,
			`<div id="u15-block">`,
			`<div id="sig-block" hidden>`,
		} {
			if !strings.Contains(body, want) {
				t.Fatalf("422 body missing %q", want)
			}
		}
		var count int
		if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM guest WHERE reservation_id = $1`, se.resID).Scan(&count); err != nil || count != 2 {
			t.Fatalf("expected 2 rows (child not inserted), got %d (err %v)", count, err)
		}

		// Same request in Czech -> Czech message.
		recCS := postForm(t, se, "cs", owned, f)
		if recCS.Code != http.StatusUnprocessableEntity || !strings.Contains(recCS.Body.String(), "Vyberte dospělého, který podepisuje.") {
			t.Fatalf("want 422 with Czech message, got %d", recCS.Code)
		}

		// Bogus echo values on 422 are NOT echoed.
		fBogus := baseChildForm()
		fBogus.Set("surname", "") // force 422
		fBogus.Set("signed_by", "1 OR 1")
		fBogus.Set("child_sign_role", "boss")
		fBogus.Set("sign_for_role", "boss")
		recBogus := postForm(t, se, "en", owned, fBogus)
		if recBogus.Code != http.StatusUnprocessableEntity {
			t.Fatalf("want 422 for bogus echo, got %d", recBogus.Code)
		}
		bb := recBogus.Body.String()
		if strings.Contains(bb, "1 OR 1") || strings.Contains(bb, `value="boss" checked`) {
			t.Fatalf("bogus echo values leaked into 422 HTML")
		}

		// Empty child_sign_role and empty signed_by -> 303, NULL link.
		fNone := baseChildForm()
		fNone.Set("first_name", "NoRole")
		recNone := postForm(t, se, "en", owned, fNone)
		if recNone.Code != http.StatusSeeOther {
			t.Fatalf("want 303, got %d", recNone.Code)
		}
		cNone := readSignCols(t, latestGuestID(t, se.resID))
		if cNone.guestID.Valid {
			t.Fatalf("expected NULL link, got %+v", cNone)
		}

		// Valid signed_by=adult2 + child_sign_role=responsible_adult -> 303, linked to adult2.
		fOK := baseChildForm()
		fOK.Set("first_name", "LinkedTwo")
		fOK.Set("signed_by", fmt.Sprintf("%d", adult2))
		fOK.Set("child_sign_role", "responsible_adult")
		recOK := postForm(t, se, "en", owned, fOK)
		if recOK.Code != http.StatusSeeOther {
			t.Fatalf("want 303, got %d", recOK.Code)
		}
		cOK := readSignCols(t, latestGuestID(t, se.resID))
		if !cOK.guestID.Valid || cOK.guestID.Int64 != adult2 || cOK.role.String != "responsible_adult" || cOK.wording.String != signForWordingVersion {
			t.Fatalf("unexpected linked cols: %+v", cOK)
		}
	})

	t.Run("4_ineligible_signers_silently_dropped", func(t *testing.T) {
		se := newStay(t, 4)
		other := newStay(t, 5)
		otherAdult := seedGuest(t, other.resID, "Other", "Stay", "10051990", validSig, "pending", 0, "", false, nil, "", "", "")
		unownedAdult := seedGuest(t, se.resID, "Unowned", "Adult", "10051990", validSig, "pending", 0, "", false, nil, "", "", "")
		teen17 := seedGuest(t, se.resID, "Teen", "Seventeen", "21062008", validSig, "pending", 0, "", false, nil, "", "", "")
		archivedAdult := seedGuest(t, se.resID, "Arch", "Adult", "10051990", validSig, "pending", 0, "", true, nil, "", "", "")
		importedAdult := seedGuest(t, se.resID, "Imp", "Adult", "10051990", "imported", "pending", 0, "", false, nil, "", "", "")
		validAdult := seedGuest(t, se.resID, "Valid", "Adult", "10051990", validSig, "pending", 0, "", false, nil, "", "", "")
		owned := []int64{otherAdult, teen17, archivedAdult, importedAdult, validAdult}

		badCases := []struct {
			name, signer, role string
		}{
			{"other reservation", fmt.Sprintf("%d", otherAdult), "parent"},
			{"unowned adult", fmt.Sprintf("%d", unownedAdult), "parent"},
			{"17yo signed", fmt.Sprintf("%d", teen17), "parent"},
			{"archived adult", fmt.Sprintf("%d", archivedAdult), "parent"},
			{"imported sig", fmt.Sprintf("%d", importedAdult), "parent"},
			{"invalid role", fmt.Sprintf("%d", validAdult), "boss"},
			{"non-numeric", "abc", "parent"},
		}
		for i, bc := range badCases {
			f := baseChildForm()
			f.Set("first_name", fmt.Sprintf("Child%d", i))
			f.Set("signed_by", bc.signer)
			f.Set("child_sign_role", bc.role)
			rec := postForm(t, se, "en", owned, f)
			if rec.Code != http.StatusSeeOther {
				t.Fatalf("%s: want 303, got %d", bc.name, rec.Code)
			}
			c := readSignCols(t, latestGuestID(t, se.resID))
			if c.guestID.Valid || c.role.Valid || c.at.Valid || c.wording.Valid {
				t.Fatalf("%s: expected NULL link, got %+v", bc.name, c)
			}
		}
	})

	t.Run("5_child_ages_out_on_birth_date_correction", func(t *testing.T) {
		se := newStay(t, 6)
		adultID := seedGuest(t, se.resID, "Anna", "Novak", "10051990", validSig, "pending", 0, "", false, nil, "", "", "")
		childID := seedGuest(t, se.resID, "Lukas", "Novak", "10052016", "", "pending", 0, "", false, &adultID, "parent", stamp, signForWordingVersion)
		owned := []int64{adultID, childID}

		// Edit to age 16 without signature -> 422, prior link remains intact.
		f422 := baseChildForm()
		f422.Set("guest_id", fmt.Sprintf("%d", childID))
		f422.Set("birth_date", "10.05.2010")
		rec422 := postForm(t, se, "en", owned, f422)
		if rec422.Code != http.StatusUnprocessableEntity {
			t.Fatalf("want 422 when aging out without signature, got %d", rec422.Code)
		}
		cStill := readSignCols(t, childID)
		if !cStill.guestID.Valid || cStill.guestID.Int64 != adultID || cStill.role.String != "parent" {
			t.Fatalf("422 mutated prior link: %+v", cStill)
		}

		// Same edit with valid drawn signature -> 303, signature + signed_at saved, 4 signed_for_* cleared.
		fOK := baseChildForm()
		fOK.Set("guest_id", fmt.Sprintf("%d", childID))
		fOK.Set("birth_date", "10.05.2010")
		fOK.Set("signature", validSig)
		recOK := postForm(t, se, "en", owned, fOK)
		if recOK.Code != http.StatusSeeOther {
			t.Fatalf("want 303 with signature, got %d: %s", recOK.Code, recOK.Body.String())
		}
		cCleared := readSignCols(t, childID)
		if cCleared.guestID.Valid || cCleared.role.Valid || cCleared.at.Valid || cCleared.wording.Valid {
			t.Fatalf("expected signed_for_* cleared to NULL, got %+v", cCleared)
		}
		if !cCleared.signedAt.Valid || cCleared.signedAt.String == "" {
			t.Fatalf("expected signed_at populated, got %+v", cCleared)
		}
		sigPlain, _ := decryptGuestField(se.getenv, now, cCleared.sigEnc.String, "")
		if sigPlain != validSig {
			t.Fatalf("expected stored signature to match validSig")
		}
	})

	t.Run("6_adult_signs_for_selected_children", func(t *testing.T) {
		se := newStay(t, 7)
		firstAdult := seedGuest(t, se.resID, "First", "Adult", "10051985", validSig, "pending", 0, "", false, nil, "", "", "")
		unsignedChild := seedGuest(t, se.resID, "Unsigned", "Child", "10052016", "", "pending", 0, "", false, nil, "", "", "")
		filedChild := seedGuest(t, se.resID, "Filed", "Child", "10052017", "", "sent", 2, "kept", false, nil, "", "", "")
		teen16 := seedGuest(t, se.resID, "Teen", "Sixteen", "10052010", validSig, "pending", 0, "", false, nil, "", "", "")
		unownedChild := seedGuest(t, se.resID, "Unowned", "Child", "10052016", "", "pending", 0, "", false, nil, "", "", "")
		archivedChild := seedGuest(t, se.resID, "Archived", "Child", "10052016", "", "pending", 0, "", true, nil, "", "", "")
		alreadyLinked := seedGuest(t, se.resID, "Linked", "Child", "10052016", "", "pending", 0, "", false, &firstAdult, "parent", "then", "old")

		owned := []int64{unsignedChild, filedChild, teen16, archivedChild, alreadyLinked}

		// GET /new with pending child and 0 owned adults renders #sign-for-children WITHOUT hidden.
		getNew := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/new?lang=en", se.tok, se.resID), nil)
		ownRec := httptest.NewRecorder()
		rememberOwnedGuestIDs(ownRec, se.getenv, []int64{unsignedChild})
		for _, c := range ownRec.Result().Cookies() {
			getNew.AddCookie(c)
		}
		newRec := httptest.NewRecorder()
		se.mux.ServeHTTP(newRec, getNew)
		if newRec.Code != http.StatusOK {
			t.Fatalf("GET /new want 200, got %d", newRec.Code)
		}
		if !strings.Contains(newRec.Body.String(), `<div class="g-field" id="sign-for-children" role="radiogroup" aria-labelledby="sign-for-children-text">`) {
			t.Fatalf("GET /new did not render visible #sign-for-children")
		}

		// 17-year-old posting sign_for_ids + role=parent links nobody.
		f17 := baseAdultForm()
		f17.Set("first_name", "Seventeen")
		f17.Set("birth_date", "21.06.2008")
		f17["sign_for_ids"] = []string{fmt.Sprintf("%d", unsignedChild)}
		f17.Set("sign_for_role", "parent")
		rec17 := postForm(t, se, "en", owned, f17)
		if rec17.Code != http.StatusSeeOther {
			t.Fatalf("17yo want 303, got %d", rec17.Code)
		}
		if c := readSignCols(t, unsignedChild); c.guestID.Valid {
			t.Fatalf("17yo should not link child: %+v", c)
		}

		// Adult posting sign_for_ids with empty sign_for_role links nobody.
		fNoRole := baseAdultForm()
		fNoRole.Set("first_name", "NoRoleAdult")
		fNoRole["sign_for_ids"] = []string{fmt.Sprintf("%d", unsignedChild)}
		recNoRole := postForm(t, se, "en", owned, fNoRole)
		if recNoRole.Code != http.StatusSeeOther {
			t.Fatalf("adult no role want 303, got %d", recNoRole.Code)
		}
		if c := readSignCols(t, unsignedChild); c.guestID.Valid {
			t.Fatalf("empty role should not link child: %+v", c)
		}

		// Adult posting all IDs (+ duplicate + "x") with role=responsible_adult.
		se.hooks.onComplete = 0
		fAdult := baseAdultForm()
		fAdult.Set("first_name", "SignerAdult")
		fAdult["sign_for_ids"] = []string{
			fmt.Sprintf("%d", unsignedChild),
			fmt.Sprintf("%d", unsignedChild),
			"x",
			fmt.Sprintf("%d", filedChild),
			fmt.Sprintf("%d", teen16),
			fmt.Sprintf("%d", unownedChild),
			fmt.Sprintf("%d", archivedChild),
			fmt.Sprintf("%d", alreadyLinked),
		}
		fAdult.Set("sign_for_role", "responsible_adult")
		recAdult := postForm(t, se, "en", owned, fAdult)
		if recAdult.Code != http.StatusSeeOther {
			t.Fatalf("adult want 303, got %d: %s", recAdult.Code, recAdult.Body.String())
		}
		adultID := latestGuestID(t, se.resID)
		if se.hooks.onComplete != 0 {
			t.Fatalf("expected runCompletion hook deferred until confirm-registration, got %d", se.hooks.onComplete)
		}

		// Unsigned owned active child linked.
		cU := readSignCols(t, unsignedChild)
		if !cU.guestID.Valid || cU.guestID.Int64 != adultID || cU.role.String != "responsible_adult" || cU.at.String == "" || cU.wording.String != signForWordingVersion {
			t.Fatalf("unsignedChild not linked properly: %+v", cU)
		}
		// Filed owned child linked WITHOUT touching filing columns.
		cF := readSignCols(t, filedChild)
		if !cF.guestID.Valid || cF.guestID.Int64 != adultID || cF.role.String != "responsible_adult" || cF.at.String == "" || cF.wording.String != signForWordingVersion {
			t.Fatalf("filedChild not linked properly: %+v", cF)
		}
		if cF.submitState != "sent" || cF.attempts != 2 || cF.lastErrors.String != "kept" {
			t.Fatalf("filedChild filing columns mutated: %+v", cF)
		}
		// 16yo, unowned, archived stay NULL.
		for name, id := range map[string]int64{"teen16": teen16, "unownedChild": unownedChild, "archivedChild": archivedChild} {
			if c := readSignCols(t, id); c.guestID.Valid {
				t.Fatalf("%s should stay NULL, got %+v", name, c)
			}
		}
		// Already-linked keeps (firstAdult, 'parent', 'then', 'old').
		cA := readSignCols(t, alreadyLinked)
		if !cA.guestID.Valid || cA.guestID.Int64 != firstAdult || cA.role.String != "parent" || cA.at.String != "then" || cA.wording.String != "old" {
			t.Fatalf("alreadyLinked mutated: %+v", cA)
		}
	})
}

func TestGuestSaveFilingCorrection(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	keys, err := secure.LoadDataKeys(testDataEnv)
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	stamp := "2026-01-01T00:00:00Z"
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	wrap := func(_ string, h http.HandlerFunc) http.Handler { return h }

	makeSig := func(w, h int) string {
		var buf bytes.Buffer
		if err := png.Encode(&buf, image.NewRGBA(image.Rect(0, 0, w, h))); err != nil {
			t.Fatal(err)
		}
		return "data:image/png;base64," + base64.StdEncoding.EncodeToString(buf.Bytes())
	}
	sigA := makeSig(8, 8)
	sigB := makeSig(12, 12)

	type guestState struct {
		surname     string
		firstName   string
		nationality string
		note        string
		noticeLang  string
		submitState string
		attempts    int
		lastErrors  sql.NullString
		submittedAt sql.NullString
		birthDate   string
		docNumber   string
		docEnc      string
	}
	readState := func(t *testing.T, getenv func(string) string, id int64) guestState {
		t.Helper()
		var st guestState
		var birthPlain, birthEnc, docPlain string
		if err := pool.QueryRow(ctx, `SELECT COALESCE(surname,''), COALESCE(first_name,''),
			COALESCE(nationality,''), COALESCE(note,''), COALESCE(notice_lang,''),
			submit_state, submit_attempts, last_errors, submitted_at,
			COALESCE(birth_date,''), COALESCE(birth_date_enc,''),
			COALESCE(doc_number,''), COALESCE(doc_number_enc,'')
			FROM guest WHERE id = $1`, id).Scan(
			&st.surname, &st.firstName, &st.nationality, &st.note, &st.noticeLang,
			&st.submitState, &st.attempts, &st.lastErrors, &st.submittedAt,
			&birthPlain, &birthEnc, &docPlain, &st.docEnc,
		); err != nil {
			t.Fatalf("readState(%d): %v", id, err)
		}
		bd, err := decryptGuestField(getenv, now, birthEnc, birthPlain)
		if err != nil {
			t.Fatalf("decrypt birth_date(%d): %v", id, err)
		}
		dn, err := decryptGuestField(getenv, now, st.docEnc, docPlain)
		if err != nil {
			t.Fatalf("decrypt doc_number(%d): %v", id, err)
		}
		st.birthDate = bd
		st.docNumber = dn
		return st
	}

	type stayEnv struct {
		userID, aptID, resID int64
		tok                  string
		getenv               func(string) string
		mux                  *http.ServeMux
		csrf                 string
		csrfCookie           string
	}
	newStay := func(t *testing.T, offset int64) stayEnv {
		t.Helper()
		base := time.Now().UnixNano()%1000000000 + 8200000 + offset*100
		userID, aptID, resID := base, base+1, base+2
		tok := fmt.Sprintf("fcorr%d", base)
		mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
			VALUES ($1, $2, 'x', 'host', 1, $3)`, userID, fmt.Sprintf("fc%d@example.test", base), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at, passport_photo_policy)
			VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4, 'off')`, aptID, userID, tok, stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
			VALUES ($1, $2, $3, 'active', 'manual', '2026-06-20', '2026-06-22', $4, $4)`, resID, aptID, fmt.Sprintf("fc-%d", resID), stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO reservation_claim (reservation_id, state, token_hash, token_version, created_at, updated_at)
			VALUES ($1, 'claimed', '', 1, $2, $2)`, resID, stamp)
		t.Cleanup(func() {
			bg := context.Background()
			_, _ = pool.Exec(bg, `DELETE FROM submission_claim WHERE guest_id IN (SELECT id FROM guest WHERE reservation_id = $1)`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM guest WHERE reservation_id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM reservation_claim WHERE reservation_id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM reservation WHERE id = $1`, resID)
			_, _ = pool.Exec(bg, `DELETE FROM apartment WHERE id = $1`, aptID)
			_, _ = pool.Exec(bg, `DELETE FROM user_account WHERE id = $1`, userID)
		})
		getenv := func(k string) string {
			switch k {
			case "UBYHOST_GUEST_PIN":
				return "0"
			case "UBYHOST_MAIL_BACKEND":
				return "disabled"
			}
			return testDataEnv(k)
		}
		mux := http.NewServeMux()
		RegisterStayClaim(mux, pool, getenv, now, wrap, nil)
		RegisterFormPages(mux, pool, getenv, now, wrap)
		RegisterFormSave(mux, pool, getenv, now, wrap, &passportHookCount{})
		getRec := httptest.NewRecorder()
		mux.ServeHTTP(getRec, httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/claim?lang=en", tok, resID), nil))
		csrf := extractPageCSRF(getRec.Body.String())
		cookie := csrfCookie(getRec.Result().Cookies())
		if csrf == "" || cookie == "" {
			t.Fatalf("csrf %q cookie %q status %d", csrf, cookie, getRec.Code)
		}
		return stayEnv{userID, aptID, resID, tok, getenv, mux, csrf, cookie}
	}

	type seedOpt struct {
		surname      string
		firstName    string
		birthDate    string
		nationality  string
		docNumber    string
		note         string
		stayFrom     string
		stayTo       string
		submitState  string
		attempts     int
		lastErrors   string
		submittedAt  string
		restrictedAt string
	}
	seedGuest := func(t *testing.T, resID int64, o seedOpt) int64 {
		t.Helper()
		if o.surname == "" {
			o.surname = "SMITH"
		}
		if o.firstName == "" {
			o.firstName = "JOHN"
		}
		if o.birthDate == "" {
			o.birthDate = "10051990"
		}
		if o.nationality == "" {
			o.nationality = "DEU"
		}
		if o.docNumber == "" {
			o.docNumber = "DOC12345"
		}
		enc, err := secure.GuestWriteValues(keys, map[string]any{
			"birth_date": o.birthDate, "doc_number": o.docNumber, "visa_number": "",
			"res_street": "Main 1", "res_city": "Berlin", "signature_png": sigA,
		})
		if err != nil {
			t.Fatal(err)
		}
		var le, subAt, restAt any
		if o.lastErrors != "" {
			le = o.lastErrors
		}
		if o.submittedAt != "" {
			subAt = o.submittedAt
		}
		if o.restrictedAt != "" {
			restAt = o.restrictedAt
		}
		var id int64
		if err := pool.QueryRow(ctx, `INSERT INTO guest (
			reservation_id, is_lead, surname, first_name, nationality, res_country, purpose, note,
			stay_from, stay_to, submit_state, submit_attempts, last_errors, submitted_at, restricted_at,
			notice_lang, created_at, updated_at,
			birth_date_enc, doc_number_enc, visa_number_enc, res_street_enc, res_city_enc, signature_png_enc
		) VALUES ($1,0,$2,$3,$4,'DEU','99',$5,$6,$7,$8,$9,$10,$11,$12,'en',$13,$13,$14,$15,$16,$17,$18,$19)
		RETURNING id`,
			resID, o.surname, o.firstName, o.nationality, o.note,
			o.stayFrom, o.stayTo, o.submitState, o.attempts, le, subAt, restAt,
			stamp,
			enc["birth_date_enc"], enc["doc_number_enc"], enc["visa_number_enc"],
			enc["res_street_enc"], enc["res_city_enc"], enc["signature_png_enc"],
		).Scan(&id); err != nil {
			t.Fatalf("seedGuest: %v", err)
		}
		return id
	}

	postForm := func(t *testing.T, se stayEnv, lang string, owned []int64, vals url.Values) *httptest.ResponseRecorder {
		t.Helper()
		vals.Set("_csrf", se.csrf)
		req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/l/%s/%d/save?lang=%s", se.tok, se.resID, lang), strings.NewReader(vals.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: se.csrfCookie})
		if len(owned) > 0 {
			ownRec := httptest.NewRecorder()
			rememberOwnedGuestIDs(ownRec, se.getenv, owned)
			for _, c := range ownRec.Result().Cookies() {
				req.AddCookie(c)
			}
		}
		rec := httptest.NewRecorder()
		se.mux.ServeHTTP(rec, req)
		return rec
	}

	baseEditForm := func(guestID int64) url.Values {
		return url.Values{
			"guest_id":    {fmt.Sprintf("%d", guestID)},
			"surname":     {"SMITH"},
			"first_name":  {"JOHN"},
			"birth_date":  {"10.05.1990"},
			"nationality": {"DEU"},
			"doc_number":  {"DOC12345"},
			"res_street":  {"Main 1"},
			"res_city":    {"Berlin"},
			"res_country": {"DEU"},
			"purpose":     {"99"},
			"note":        {""},
			"signature":   {sigA},
			"legal_ack":   {"1"},
		}
	}

	t.Run("blocked_duplicate_unchanged_fields_stays_blocked", func(t *testing.T) {
		SetGuestLanguages("en,cs,de")
		t.Cleanup(func() { SetGuestLanguages("en,cs") })
		se := newStay(t, 1)
		gid := seedGuest(t, se.resID, seedOpt{
			submitState: "blocked",
			lastErrors:  "150: Duplicate record",
			attempts:    3,
			stayFrom:    "",
			stayTo:      "",
		})
		f := baseEditForm(gid)
		f.Set("surname", " smith ")
		f.Set("first_name", " john ")
		f.Set("birth_date", "10.05.1990")
		f.Set("signature", sigB)
		rec := postForm(t, se, "de", []int64{gid}, f)
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("want 303, got %d: %s", rec.Code, rec.Body.String())
		}
		st := readState(t, se.getenv, gid)
		if st.submitState != "blocked" || !st.lastErrors.Valid || st.lastErrors.String != "150: Duplicate record" || st.attempts != 3 || st.noticeLang != "de" {
			t.Fatalf("duplicate block should be preserved while non-filing columns update: %+v", st)
		}
	})

	t.Run("blocked_duplicate_czech_wording_stays_blocked", func(t *testing.T) {
		se := newStay(t, 2)
		gid := seedGuest(t, se.resID, seedOpt{
			submitState: "blocked",
			lastErrors:  "105: Jiná chyba | Duplicitní záznam",
			attempts:    2,
			stayFrom:    "2026-06-20",
			stayTo:      "2026-06-22",
		})
		rec := postForm(t, se, "en", []int64{gid}, baseEditForm(gid))
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("want 303, got %d: %s", rec.Code, rec.Body.String())
		}
		st := readState(t, se.getenv, gid)
		if st.submitState != "blocked" || !st.lastErrors.Valid || st.lastErrors.String != "105: Jiná chyba | Duplicitní záznam" || st.attempts != 2 {
			t.Fatalf("Czech duplicate wording should stay blocked: %+v", st)
		}
	})

	t.Run("blocked_duplicate_changed_field_resets", func(t *testing.T) {
		cases := []struct {
			name   string
			field  string
			val    string
			verify func(t *testing.T, st guestState)
		}{
			{"doc_number", "doc_number", "DOC99999", func(t *testing.T, st guestState) {
				if st.docNumber != "DOC99999" {
					t.Fatalf("want docNumber DOC99999, got %q", st.docNumber)
				}
			}},
			{"birth_date", "birth_date", "11.05.1990", func(t *testing.T, st guestState) {
				if st.birthDate != "11051990" {
					t.Fatalf("want birthDate 11051990, got %q", st.birthDate)
				}
			}},
			{"surname", "surname", "JONES", func(t *testing.T, st guestState) {
				if st.surname != "JONES" {
					t.Fatalf("want surname JONES, got %q", st.surname)
				}
			}},
			{"note", "note", "Late arrival", func(t *testing.T, st guestState) {
				if st.note != "Late arrival" {
					t.Fatalf("want note Late arrival, got %q", st.note)
				}
			}},
		}
		for i, tc := range cases {
			t.Run(tc.name, func(t *testing.T) {
				se := newStay(t, int64(10+i))
				gid := seedGuest(t, se.resID, seedOpt{
					submitState: "blocked",
					lastErrors:  "150: Duplicate record",
					attempts:    3,
					stayFrom:    "2026-06-20",
					stayTo:      "2026-06-22",
				})
				f := baseEditForm(gid)
				f.Set(tc.field, tc.val)
				rec := postForm(t, se, "en", []int64{gid}, f)
				if rec.Code != http.StatusSeeOther {
					t.Fatalf("want 303, got %d: %s", rec.Code, rec.Body.String())
				}
				st := readState(t, se.getenv, gid)
				if st.submitState != "pending" || st.lastErrors.Valid || st.attempts != 0 {
					t.Fatalf("changed %s should reset to pending/0/NULL: %+v", tc.name, st)
				}
				tc.verify(t, st)
			})
		}
	})

	t.Run("non_duplicate_error_and_blocked_at_attempt_cap_reset", func(t *testing.T) {
		for i, state := range []string{"error", "blocked"} {
			t.Run(state, func(t *testing.T) {
				se := newStay(t, int64(20+i))
				gid := seedGuest(t, se.resID, seedOpt{
					submitState: state,
					lastErrors:  "104: Invalid birth date",
					attempts:    3,
					stayFrom:    "2026-06-20",
					stayTo:      "2026-06-22",
				})
				rec := postForm(t, se, "en", []int64{gid}, baseEditForm(gid))
				if rec.Code != http.StatusSeeOther {
					t.Fatalf("want 303, got %d: %s", rec.Code, rec.Body.String())
				}
				st := readState(t, se.getenv, gid)
				if st.submitState != "pending" || st.lastErrors.Valid || st.attempts != 0 {
					t.Fatalf("non-duplicate %s should reset to pending/0/NULL: %+v", state, st)
				}
			})
		}
	})

	t.Run("pending_edit_preserves_submit_attempts", func(t *testing.T) {
		se := newStay(t, 30)
		gid := seedGuest(t, se.resID, seedOpt{
			submitState: "pending",
			lastErrors:  "transient",
			attempts:    2,
			stayFrom:    "2026-06-20",
			stayTo:      "2026-06-22",
		})
		f := baseEditForm(gid)
		f.Set("surname", "MILLER")
		rec := postForm(t, se, "en", []int64{gid}, f)
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("want 303, got %d: %s", rec.Code, rec.Body.String())
		}
		st := readState(t, se.getenv, gid)
		if st.submitState != "pending" || st.lastErrors.Valid || st.attempts != 2 || st.surname != "MILLER" {
			t.Fatalf("pending edit must preserve submit_attempts: %+v", st)
		}
	})

	t.Run("nationality_transitions", func(t *testing.T) {
		cases := []struct {
			name        string
			seedNat     string
			seedState   string
			seedErr     string
			seedAttempt int
			newNat      string
			wantState   string
		}{
			{"blocked_dup_deu_to_cze", "DEU", "blocked", "150: Duplicate record", 3, "CZE", "not_required"},
			{"error_deu_to_cze", "DEU", "error", "104: Invalid birth date", 3, "CZE", "not_required"},
			{"not_required_cze_to_deu", "CZE", "not_required", "", 2, "DEU", "pending"},
		}
		for i, tc := range cases {
			t.Run(tc.name, func(t *testing.T) {
				se := newStay(t, int64(40+i))
				gid := seedGuest(t, se.resID, seedOpt{
					nationality: tc.seedNat,
					submitState: tc.seedState,
					lastErrors:  tc.seedErr,
					attempts:    tc.seedAttempt,
					stayFrom:    "2026-06-20",
					stayTo:      "2026-06-22",
				})
				f := baseEditForm(gid)
				f.Set("nationality", tc.newNat)
				rec := postForm(t, se, "en", []int64{gid}, f)
				if rec.Code != http.StatusSeeOther {
					t.Fatalf("want 303, got %d: %s", rec.Code, rec.Body.String())
				}
				st := readState(t, se.getenv, gid)
				if st.submitState != tc.wantState || st.lastErrors.Valid || st.attempts != 0 || st.nationality != tc.newNat {
					t.Fatalf("nationality transition %s failed: %+v", tc.name, st)
				}
			})
		}
	})

	t.Run("sent_restricted_claimed_and_cas_protected", func(t *testing.T) {
		t.Run("sent_refused_403", func(t *testing.T) {
			se := newStay(t, 50)
			gid := seedGuest(t, se.resID, seedOpt{
				submitState: "sent",
				submittedAt: stamp,
				attempts:    1,
				stayFrom:    "2026-06-20",
				stayTo:      "2026-06-22",
			})
			before := readState(t, se.getenv, gid)
			f := baseEditForm(gid)
			f.Set("surname", "CHANGED")
			f.Set("doc_number", "NEWDOC99")
			rec := postForm(t, se, "en", []int64{gid}, f)
			if rec.Code != http.StatusForbidden {
				t.Fatalf("want 403 for sent guest, got %d", rec.Code)
			}
			after := readState(t, se.getenv, gid)
			if after.surname != "SMITH" || after.docEnc != before.docEnc || after.submitState != "sent" || after.attempts != 1 || !after.submittedAt.Valid || after.submittedAt.String != stamp {
				t.Fatalf("sent guest was mutated: before=%+v after=%+v", before, after)
			}
		})

		t.Run("restricted_redirects_without_update", func(t *testing.T) {
			se := newStay(t, 51)
			gid := seedGuest(t, se.resID, seedOpt{
				submitState:  "error",
				restrictedAt: stamp,
				attempts:     2,
				stayFrom:     "2026-06-20",
				stayTo:       "2026-06-22",
			})
			f := baseEditForm(gid)
			f.Set("surname", "CHANGED")
			rec := postForm(t, se, "en", []int64{gid}, f)
			if rec.Code != http.StatusSeeOther {
				t.Fatalf("want 303 for restricted guest, got %d", rec.Code)
			}
			after := readState(t, se.getenv, gid)
			if after.surname != "SMITH" || after.submitState != "error" || after.attempts != 2 {
				t.Fatalf("restricted guest was mutated: %+v", after)
			}
		})

		t.Run("active_submission_claim_refused_403", func(t *testing.T) {
			se := newStay(t, 52)
			gid := seedGuest(t, se.resID, seedOpt{
				submitState: "error",
				attempts:    2,
				stayFrom:    "2026-06-20",
				stayTo:      "2026-06-22",
			})
			mustExecGuest(t, ctx, pool, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'tok-active', $2)`,
				gid, float64(now().Unix())-60)
			f := baseEditForm(gid)
			f.Set("surname", "CHANGED")
			rec := postForm(t, se, "en", []int64{gid}, f)
			if rec.Code != http.StatusForbidden {
				t.Fatalf("want 403 for actively claimed guest, got %d", rec.Code)
			}
			after := readState(t, se.getenv, gid)
			if after.surname != "SMITH" || after.submitState != "error" || after.attempts != 2 {
				t.Fatalf("actively claimed guest was mutated: %+v", after)
			}
		})

		t.Run("expired_submission_claim_allows_save", func(t *testing.T) {
			se := newStay(t, 53)
			gid := seedGuest(t, se.resID, seedOpt{
				submitState: "error",
				lastErrors:  "104: Invalid birth date",
				attempts:    2,
				stayFrom:    "2026-06-20",
				stayTo:      "2026-06-22",
			})
			mustExecGuest(t, ctx, pool, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'tok-expired', $2)`,
				gid, float64(now().Unix())-600)
			f := baseEditForm(gid)
			f.Set("surname", "UPDATED")
			rec := postForm(t, se, "en", []int64{gid}, f)
			if rec.Code != http.StatusSeeOther {
				t.Fatalf("want 303 for expired claim, got %d: %s", rec.Code, rec.Body.String())
			}
			after := readState(t, se.getenv, gid)
			if after.surname != "UPDATED" || after.submitState != "pending" || after.lastErrors.Valid || after.attempts != 0 {
				t.Fatalf("expired claim should allow save and reset attempts: %+v", after)
			}
		})

		t.Run("concurrent_cas_state_flip", func(t *testing.T) {
			se := newStay(t, 54)
			gid := seedGuest(t, se.resID, seedOpt{
				submitState: "sent",
				submittedAt: stamp,
				attempts:    1,
				stayFrom:    "2026-06-20",
				stayTo:      "2026-06-22",
			})
			stale := &guestSaveRow{id: gid, submitState: "error"}
			updated, err := updateGuestSaveRow(ctx, saveDeps{pool: pool, getenv: se.getenv, now: now}, stale, map[string]any{
				"surname":         "STALE",
				"submit_state":    "pending",
				"submit_attempts": 0,
			})
			if err != nil {
				t.Fatalf("expected nil error on CAS miss, got %v", err)
			}
			if updated {
				t.Fatalf("expected updated=false on CAS miss")
			}
			after := readState(t, se.getenv, gid)
			if after.surname != "SMITH" || after.submitState != "sent" || after.attempts != 1 {
				t.Fatalf("sent row mutated despite CAS miss: %+v", after)
			}
		})
	})
}
