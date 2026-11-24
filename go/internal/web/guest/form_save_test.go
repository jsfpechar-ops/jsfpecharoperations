package guest

import (
	"bytes"
	"context"
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
	}{
		{"required, no file", "required_foreign", "DEU", "", nil, http.StatusUnprocessableEntity, 0, false, false},
		{"required, text file", "required_foreign", "DEU", "text/plain", []byte("not a photo"), http.StatusUnprocessableEntity, 0, false, false},
		{"required, oversized jpeg", "required_foreign", "DEU", "image/jpeg", oversized, http.StatusUnprocessableEntity, 0, false, false},
		{"required, valid jpeg", "required_foreign", "DEU", "image/jpeg", jpg, http.StatusSeeOther, 1, true, true},
		{"off, file ignored", "off", "DEU", "image/jpeg", jpg, http.StatusSeeOther, 1, false, true},
		{"czech, no file", "required_foreign", "CZE", "", nil, http.StatusSeeOther, 1, false, true},
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
				t.Fatalf("status = %d, want %d; body: %s", rec.Code, c.wantStatus, rec.Body.String())
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
				plain, _, ok := passportphotos.Read(dir, keys, guestID)
				if !ok || !bytes.HasPrefix(plain, []byte{0xFF, 0xD8, 0xFF}) {
					t.Fatalf("stored photo does not decrypt to a JPEG (ok=%v)", ok)
				}
			}
			if c.wantHook {
				if hooks.onComplete != 1 || hooks.notify != 1 {
					t.Fatalf("completion hooks = (%d, %d), want (1, 1)", hooks.onComplete, hooks.notify)
				}
			} else if hooks.onComplete != 0 || hooks.notify != 0 {
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
		if hooks.onComplete != 1 || hooks.notify != 1 {
			t.Fatalf("completion hooks = (%d, %d), want (1, 1)", hooks.onComplete, hooks.notify)
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
		if hooks.onComplete != 1 || hooks.notify != 1 {
			t.Fatalf("completion hooks = (%d, %d), want (1, 1)", hooks.onComplete, hooks.notify)
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
		if hooks.onComplete != 1 || hooks.notify != 1 {
			t.Fatalf("completion hooks = (%d, %d), want (1, 1)", hooks.onComplete, hooks.notify)
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
