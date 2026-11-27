package guest

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/dococr"
)

func TestFormLockedHelpersMatchPython(t *testing.T) {
	if formPagesGuestLocked(nil, formResRow{}) {
		t.Fatal("nil guest should not be locked")
	}
	if formPagesGuestLocked(&formGuestRow{submitState: "READY"}, formResRow{}) {
		t.Fatal("READY unrestricted guest should be editable")
	}
	if !formPagesGuestLocked(&formGuestRow{submitState: formSubmitSent}, formResRow{}) {
		t.Fatal("SENT guest must be locked")
	}
	if !formPagesGuestLocked(&formGuestRow{submitState: "READY", restrictedAt: "2026-06-01T10:00:00Z"}, formResRow{}) {
		t.Fatal("restricted guest must be locked")
	}
	if guestFormLocked(nil) {
		t.Fatal("nil save row should not be locked")
	}
	if guestFormLocked(&guestSaveRow{submitState: "READY"}) {
		t.Fatal("READY unrestricted save row should be editable")
	}
	if !guestFormLocked(&guestSaveRow{submitState: guestSubmitSent}) {
		t.Fatal("SENT save row must be locked")
	}
	if !guestFormLocked(&guestSaveRow{submitState: "READY", restrictedAt: "2026-06-01T10:00:00Z"}) {
		t.Fatal("restricted save row must be locked")
	}
}

func TestDraftIsSentGuestNormalisesBirthDate(t *testing.T) {
	guests := []map[string]string{{
		"first_name": "JANA",
		"surname":    "NOVAKOVA",
		"birth_date": "05031992",
		"doc_number": "AB123456",
	}}
	at := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	if !draftIsSentGuestAt(map[string]string{
		"first_name": "jana",
		"surname":    "novakova",
		"birth_date": "05.03.1992",
	}, guests, at) {
		t.Fatal("typed dotted birth date should match normalised stored birth date")
	}
	if !draftIsSentGuestAt(map[string]string{"doc_number": " ab123456 "}, guests, at) {
		t.Fatal("case-insensitive doc_number should match")
	}
}

func TestDraftAutoSaveRestoreAndDeleteOnSave(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	secret := strings.Repeat("d", 32)
	baseGetenv := guestTestGetenv(t, secret)
	t.Setenv("UBYHOST_MAIL_BACKEND", "disabled")
	fernetKey := testDataEnv("UBYHOST_DATA_KEYS")
	getenv := func(k string) string {
		if k == "UBYHOST_DATA_KEYS" {
			return fernetKey
		}
		return baseGetenv(k)
	}
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	ctx := context.Background()
	stamp := "2026-06-01T00:00:00+00:00"

	aptID := time.Now().UnixNano()%8000000000 + 7200000
	userID := aptID
	resID := aptID + 1
	tok := fmt.Sprintf("drafttok%d", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, email, password_hash, role, active, created_at)
		VALUES ($1, $2, $3, 'x', 'host', 1, $4) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("dr%d", aptID), fmt.Sprintf("dr%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
		VALUES ($1, $2, 'Draft Flat', 'Prague', 1, $3, $4)`, aptID, userID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, declared_guests, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', '2026-06-15', '2026-06-18', 2, $4, $4)`, resID, aptID, fmt.Sprintf("drstay-%d", resID), stamp)

	mux := http.NewServeMux()
	wrap := func(_ string, h http.HandlerFunc) http.Handler { return h }
	RegisterFormPages(mux, pool, getenv, now, wrap)
	RegisterDraftScan(mux, pool, getenv, now, wrap)

	// 1. Open GET /new: verify draft autosave attributes + controller_missing alert raised (non-blocking) + canPick DatesLink.
	req1 := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/new?lang=en", tok, resID), nil)
	rec1 := httptest.NewRecorder()
	mux.ServeHTTP(rec1, req1)
	if rec1.Code != http.StatusOK {
		t.Fatalf("GET /new status %d loc=%q", rec1.Code, rec1.Header().Get("Location"))
	}
	body1 := rec1.Body.String()
	wantDraftURL := fmt.Sprintf(`data-draft-url="/l/%s/%d/draft?lang=en"`, tok, resID)
	if !strings.Contains(body1, wantDraftURL) {
		t.Fatalf("missing %s in form HTML", wantDraftURL)
	}
	if !strings.Contains(body1, `data-draft-fields="party_size first_name surname`) {
		t.Fatal("missing data-draft-fields attribute")
	}
	if !strings.Contains(body1, `data-draft-owned="0"`) {
		t.Fatal("missing data-draft-owned attribute")
	}
	if strings.Contains(body1, `id="draft-welcome"`) {
		t.Fatal("draft-welcome should not appear before saving a draft")
	}
	if !strings.Contains(body1, `class="g-dates-link"`) {
		t.Fatal("expected DatesLink when visible reservation exists in picker window")
	}
	var alertCount int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM alert WHERE dedupe_key = $1`, fmt.Sprintf("controller_missing:%d", aptID)).Scan(&alertCount); err != nil || alertCount != 1 {
		t.Fatalf("controller_missing alert count=%d err=%v, want 1", alertCount, err)
	}

	// Grab CSRF cookie & token to POST /draft.
	var csrfCookie *http.Cookie
	for _, c := range rec1.Result().Cookies() {
		if c.Name == "ubyhost_csrf" {
			csrfCookie = c
		}
	}
	if csrfCookie == nil {
		t.Fatal("missing ubyhost_csrf cookie")
	}
	csrfToken := extractInputValue(t, body1, "_csrf")

	// 2. POST /draft with typed values.
	form := url.Values{
		"_csrf":       {csrfToken},
		"first_name":  {"Jana"},
		"surname":     {"Novakova"},
		"birth_date":  {"05.03.1992"},
		"purpose":     {"10"},
		"draft_owned": {"0"},
	}
	reqDraft := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/l/%s/%d/draft?lang=en", tok, resID), strings.NewReader(form.Encode()))
	reqDraft.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	reqDraft.AddCookie(csrfCookie)
	recDraft := httptest.NewRecorder()
	mux.ServeHTTP(recDraft, reqDraft)
	if recDraft.Code != http.StatusNoContent {
		t.Fatalf("POST /draft status %d body=%s", recDraft.Code, recDraft.Body.String())
	}
	var draftCookie *http.Cookie
	for _, c := range recDraft.Result().Cookies() {
		if c.Name == draftCookieName {
			draftCookie = c
		}
	}
	if draftCookie == nil {
		t.Fatal("POST /draft did not set ubyhost_draft cookie")
	}

	// 3. Re-open GET /new with draft cookie: restored values + #draft-welcome.
	req2 := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/new?lang=en", tok, resID), nil)
	req2.AddCookie(draftCookie)
	rec2 := httptest.NewRecorder()
	mux.ServeHTTP(rec2, req2)
	if rec2.Code != http.StatusOK {
		t.Fatalf("GET /new restore status %d", rec2.Code)
	}
	body2 := rec2.Body.String()
	if !strings.Contains(body2, `id="draft-welcome"`) {
		t.Fatal("expected #draft-welcome when draft restored")
	}
	if !strings.Contains(body2, `value="Novakova"`) || !strings.Contains(body2, `value="Jana"`) {
		t.Fatal("expected restored surname/first_name in form inputs")
	}

	// 4. Restricted guest cannot open GET /edit/{gid} (formPagesGuestLocked -> 403).
	gid := aptID + 2
	mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, first_name, surname, submit_state, restricted_at, created_at, updated_at)
		VALUES ($1, $2, 'Locked', 'Guest', 'READY', $3, $3, $3)`, gid, resID, stamp)
	ow := httptest.NewRecorder()
	rememberOwnedGuestIDs(ow, getenv, []int64{gid})
	reqEdit := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/edit/%d?lang=en", tok, resID, gid), nil)
	for _, c := range ow.Result().Cookies() {
		reqEdit.AddCookie(c)
	}
	recEdit := httptest.NewRecorder()
	mux.ServeHTTP(recEdit, reqEdit)
	if recEdit.Code != http.StatusForbidden {
		t.Fatalf("restricted guest GET /edit status = %d, want 403", recEdit.Code)
	}
}

func TestOCRAvailableGatesAndScanEndpoint(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	secret := strings.Repeat("o", 32)
	baseGetenv := guestTestGetenv(t, secret)
	t.Setenv("UBYHOST_MAIL_BACKEND", "disabled")
	testEmails := ""
	getenv := func(k string) string {
		if k == "UBYHOST_AI_TEST_EMAILS" {
			return testEmails
		}
		return baseGetenv(k)
	}
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	ctx := context.Background()
	stamp := "2026-06-01T00:00:00+00:00"

	aptID := time.Now().UnixNano()%8000000000 + 7300000
	userID := aptID
	resID := aptID + 1
	tok := fmt.Sprintf("ocrtok%d", aptID)
	email := fmt.Sprintf("ocr%d@example.test", aptID)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, email, password_hash, role, active, created_at)
		VALUES ($1, $2, $3, 'x', 'host', 1, $4) ON CONFLICT DO NOTHING`, userID, fmt.Sprintf("ocr%d", aptID), email, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, ocr_scan, created_at)
		VALUES ($1, $2, 'OCR Flat', 'Prague', 1, $3, 1, $4)`, aptID, userID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO billing_account (owner_user_id, status, plan, updated_at)
		VALUES ($1, 'active', 'standard', $2) ON CONFLICT (owner_user_id) DO UPDATE SET status = 'active', plan = 'standard'`, userID, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, declared_guests, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', '2026-06-15', '2026-06-18', 2, $4, $4)`, resID, aptID, fmt.Sprintf("ocrstay-%d", resID), stamp)

	restore := dococr.SetEngineForTest(
		func(string) (string, error) { return "/usr/bin/tesseract", nil },
		func(context.Context, []byte) (string, error) {
			return "P<UTOSMITH<<JOHN<PAUL<<<<<<<<<<<<<<<<<<<<<<<\nP1234567<1GBR9001011M3001015<<<<<<<<<<<<<<00", nil
		},
	)
	t.Cleanup(restore)

	if ocrAvailableForApartment(ctx, pool, getenv, aptID) {
		t.Fatal("standard plan must not allow OCR")
	}
	mustExecGuest(t, ctx, pool, `UPDATE billing_account SET status = 'active', plan = 'max' WHERE owner_user_id = $1`, userID)
	if !ocrAvailableForApartment(ctx, pool, getenv, aptID) {
		t.Fatal("active max plan with ocr_scan=1 and tesseract must allow OCR")
	}
	testEmails = "other@example.test"
	if ocrAvailableForApartment(ctx, pool, getenv, aptID) {
		t.Fatal("UBYHOST_AI_TEST_EMAILS must exclude unlisted owner")
	}
	testEmails = strings.ToUpper(email)
	if !ocrAvailableForApartment(ctx, pool, getenv, aptID) {
		t.Fatal("UBYHOST_AI_TEST_EMAILS must allow listed owner case-insensitively")
	}

	mux := http.NewServeMux()
	wrap := func(_ string, h http.HandlerFunc) http.Handler { return h }
	RegisterFormPages(mux, pool, getenv, now, wrap)
	RegisterDraftScan(mux, pool, getenv, now, wrap)

	// GET /new renders #ocr-scan + script.
	reqForm := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/new?lang=en", tok, resID), nil)
	recForm := httptest.NewRecorder()
	mux.ServeHTTP(recForm, reqForm)
	if recForm.Code != http.StatusOK || !strings.Contains(recForm.Body.String(), `id="ocr-scan"`) || !strings.Contains(recForm.Body.String(), `ocr-scan-file`) {
		t.Fatalf("expected #ocr-scan in GET /new, status=%d", recForm.Code)
	}

	// POST /scan with a valid PNG returns parsed MRZ values.
	var csrfCookie *http.Cookie
	for _, c := range recForm.Result().Cookies() {
		if c.Name == "ubyhost_csrf" {
			csrfCookie = c
		}
	}
	csrfToken := extractInputValue(t, recForm.Body.String(), "_csrf")
	var pngBuf bytes.Buffer
	img := image.NewRGBA(image.Rect(0, 0, 80, 50))
	img.SetRGBA(10, 10, color.RGBA{A: 255})
	_ = png.Encode(&pngBuf, img)

	var body bytes.Buffer
	mw := multipart.NewWriter(&body)
	_ = mw.WriteField("_csrf", csrfToken)
	fw, _ := mw.CreateFormFile("passport_photo", "doc.png")
	_, _ = fw.Write(pngBuf.Bytes())
	_ = mw.Close()

	reqScan := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/l/%s/%d/scan?lang=en", tok, resID), &body)
	reqScan.Header.Set("Content-Type", mw.FormDataContentType())
	reqScan.AddCookie(csrfCookie)
	recScan := httptest.NewRecorder()
	mux.ServeHTTP(recScan, reqScan)
	if recScan.Code != http.StatusOK {
		t.Fatalf("POST /scan status %d body=%s", recScan.Code, recScan.Body.String())
	}
	var payload struct {
		Kind   string            `json:"kind"`
		Values map[string]string `json:"values"`
	}
	if err := json.Unmarshal(recScan.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode scan JSON: %v", err)
	}
	if payload.Kind != "values" || payload.Values["surname"] != "SMITH" || payload.Values["nationality"] != "GBR" {
		t.Fatalf("unexpected scan payload: %+v", payload)
	}
}

func extractInputValue(t *testing.T, html, name string) string {
	t.Helper()
	needle := `name="` + name + `" value="`
	idx := strings.Index(html, needle)
	if idx < 0 {
		t.Fatalf("input %q not found in HTML", name)
	}
	rest := html[idx+len(needle):]
	end := strings.IndexByte(rest, '"')
	if end < 0 {
		t.Fatalf("unterminated value for input %q", name)
	}
	return rest[:end]
}
