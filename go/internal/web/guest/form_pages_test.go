package guest

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/passportphotos"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

type formPagesGolden struct {
	Now       string                `json:"now"`
	Token     string                `json:"token"`
	PinToken  string                `json:"pin_token"`
	StayID    int64                 `json:"stay_id"`
	StayPinID int64                 `json:"stay_pin_id"`
	AdultID   int64                 `json:"adult_id"`
	MinorID   int64                 `json:"minor_id"`
	ForeignID int64                 `json:"foreign_id"`
	Cases     []formPagesGoldenCase `json:"cases"`
}

type formPagesGoldenCase struct {
	Name     string   `json:"name"`
	Method   string   `json:"method"`
	Path     string   `json:"path"`
	Lang     string   `json:"lang"`
	Status   int      `json:"status"`
	Location string   `json:"location"`
	Lines    []string `json:"lines"`
}

func loadFormPagesGolden(t *testing.T) formPagesGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/form_pages_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g formPagesGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestFormPagesGoldenFile(t *testing.T) {
	g := loadFormPagesGolden(t)
	if len(g.Cases) != 8 {
		t.Fatalf("cases: got %d want 8", len(g.Cases))
	}
	for _, c := range g.Cases {
		if c.Method == "" || c.Name == "" {
			t.Fatalf("case shape: %+v", c)
		}
	}
}

func TestFormPagesGoldenShape(t *testing.T) {
	g := loadFormPagesGolden(t)
	wantGET := map[string]int{
		"new_en": 200, "new_cs": 200, "edit_adult": 200, "edit_minor": 200,
		"edit_foreigner": 200, "remove_confirm": 200,
	}
	for _, c := range g.Cases {
		if exp, ok := wantGET[c.Name]; ok {
			if c.Status != exp {
				t.Errorf("%s status %d want %d", c.Name, c.Status, exp)
			}
			if len(c.Lines) < 30 {
				t.Errorf("%s lines %d", c.Name, len(c.Lines))
			}
		}
		if c.Name == "remove_post" || c.Name == "relang_cs" {
			if c.Status == 0 {
				t.Errorf("%s missing status", c.Name)
			}
		}
	}
}

func TestFormPagesRoutePattern(t *testing.T) {
	mux := http.NewServeMux()
	RegisterFormPages(mux, nil, nil, nil, func(_ string, h http.HandlerFunc) http.Handler { return h })
	cases := []struct{ method, path, pattern string }{
		{http.MethodGet, "/l/tok/1/new", "GET /l/{token}/{reservation_id}/new"},
		{http.MethodGet, "/l/tok/1/edit/2", "GET /l/{token}/{reservation_id}/edit/{guest_id}"},
		{http.MethodGet, "/l/tok/1/remove/2", "GET /l/{token}/{reservation_id}/remove/{guest_id}"},
		{http.MethodPost, "/l/tok/1/remove/2", "POST /l/{token}/{reservation_id}/remove/{guest_id}"},
		{http.MethodPost, "/l/tok/1/relang", "POST /l/{token}/{reservation_id}/relang"},
	}
	for _, c := range cases {
		req := httptest.NewRequest(c.method, c.path, nil)
		req.SetPathValue("token", "tok")
		req.SetPathValue("reservation_id", "1")
		req.SetPathValue("guest_id", "2")
		_, pattern := mux.Handler(req)
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q", c.method, c.path, pattern)
		}
	}
}

// formPagesVisibleLines must stay aligned with visible_lines() in App/scripts/go_form_pages_golden.py.
func formPagesVisibleLines(page string) []string {
	idx := strings.Index(page, `class="g-wrap`)
	start := strings.LastIndex(page[:idx+1], "<div")
	if idx < 0 || start < 0 {
		return nil
	}
	page = page[start:]
	if end := strings.Index(page, `<div class="g-page-skeleton"`); end >= 0 {
		page = page[:end]
	}
	// Minimal normaliser: keep tags with class= and form fields for parity tests.
	var out []string
	for _, line := range strings.Split(page, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if strings.Contains(line, "class=") || strings.Contains(line, "<form") || strings.Contains(line, "g-checkin") {
			out = append(out, line)
		}
	}
	return out
}

func TestFormPagesVisibleLinesHelper(t *testing.T) {
	sample := "<div class=\"g-wrap x\">\n<div class=\"g-checkin-main\">\n<form id=\"guest-form\" method=\"post\"></form>\n</div>\n<div class=\"g-page-skeleton\"></div>"
	lines := formPagesVisibleLines(sample)
	if len(lines) < 2 {
		t.Fatalf("lines %v", lines)
	}
}

func TestFormPagesDefaultPurpose(t *testing.T) {
	if got := formPagesDefaultPurpose(nil); got != "99" {
		t.Fatalf("nil apt: %q", got)
	}
	if got := formPagesDefaultPurpose(&Apartment{}); got != "99" {
		t.Fatalf("empty: %q", got)
	}
	if got := formPagesDefaultPurpose(&Apartment{DefaultPurpose: "10"}); got != "10" {
		t.Fatalf("apartment default: %q", got)
	}
}

func TestFormPagesOwnedIDsFromCookie(t *testing.T) {
	r := httptest.NewRequest(http.MethodGet, "/l/tok/9/edit/42", nil)
	if formPagesOwnedIDs(r, testGuestEnv)[42] {
		t.Fatal("no cookie must not own 42")
	}
	w := httptest.NewRecorder()
	formPagesSetOwnedCookie(w, testGuestEnv, []int64{42})
	res := w.Result()
	defer res.Body.Close()
	for _, c := range res.Cookies() {
		r.AddCookie(c)
	}
	if !formPagesOwnedIDs(r, testGuestEnv)[42] {
		t.Fatal("cookie should own 42")
	}
}

func TestFormPagesRegisterNilPool(t *testing.T) {
	mux := http.NewServeMux()
	RegisterFormPages(mux, nil, func(string) string { return "" }, nil, func(_ string, h http.HandlerFunc) http.Handler { return h })
	req := httptest.NewRequest(http.MethodGet, "/l/tok/9/new", nil)
	req.SetPathValue("token", "tok")
	req.SetPathValue("reservation_id", "9")
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("nil pool: status %d", rec.Code)
	}
}

func TestGuestRemovalCleanup(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := t.Context()

	fixedNow := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	nowFn := func() time.Time { return fixedNow }
	stamp := isoNow(fixedNow)

	secret := strings.Repeat("r", 32)
	dataKey := base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{7}, 32))
	dataDir := t.TempDir()
	currentDataDir := dataDir
	getenv := func(k string) string {
		switch k {
		case "UBYHOST_SECRET_KEY":
			return secret
		case "UBYHOST_DATA_KEYS":
			return dataKey
		case "UBYHOST_DATA_KEY_LEGACY":
			return "0"
		case "UBYHOST_GUEST_PIN":
			return "0"
		case "UBYHOST_MAIL_BACKEND":
			return "disabled"
		case "UBYHOST_DATA_DIR":
			return currentDataDir
		default:
			return ""
		}
	}
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		t.Fatalf("LoadDataKeys: %v", err)
	}

	base := int64(2076000)
	ownerID := base
	aptID := base + 100
	resID := base + 200
	otherResID := base + 201
	otherGuestID := base + 300
	if ownerID == aptID {
		t.Fatalf("ownerID and aptID must be distinct")
	}
	tok := "rmcleanup2076"

	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, 'rmcleanup2076@example.test', 'x', 'host', 1, $2)`, ownerID, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at, automation_mode, uby_idub, uby_name)
		VALUES ($1, $2, 'Flat', 'Prague', 1, $3, $4, 'immediate', 'UBY123', 'Flat')`, aptID, ownerID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, declared_guests, registration_completed_at, created_at, updated_at)
		VALUES ($1, $2, 'rm2076-main', 'active', 'manual', '2026-06-10', '2026-06-12', 2, NULL, $3, $3)`, resID, aptID, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, declared_guests, registration_completed_at, created_at, updated_at)
		VALUES ($1, $2, 'rm2076-other', 'active', 'manual', '2026-06-10', '2026-06-12', 1, NULL, $3, $3)`, otherResID, aptID, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, doc_number, res_street, res_city, res_country, purpose, stay_from, stay_to, is_lead)
		VALUES ($1, $2, $3, $3, 'Other', 'StayGuest', '04031988', 'DEU', 'SYNTH9001', 'Other St 1', 'Munich', 'DEU', '99', '2026-06-10', '2026-06-12', 1)`,
		otherGuestID, otherResID, stamp)

	var (
		calls   int
		gotApt  int64
		gotOpts ubyport.CollectOptions
		gotMode string
	)
	prevOpts := formPagesSubmitCompletedStayOpts
	t.Cleanup(func() { formPagesSubmitCompletedStayOpts = prevOpts })
	formPagesSubmitCompletedStayOpts = &ubyport.SubmitCompletedStayOptions{
		Submit: func(_ context.Context, _ ubyport.SweepDeps, aID int64, o ubyport.CollectOptions, mode string) ([]ubyport.BatchResult, error) {
			calls++
			gotApt = aID
			gotOpts = o
			gotMode = mode
			return nil, nil
		},
	}

	mux := http.NewServeMux()
	RegisterFormPages(mux, pool, getenv, nowFn, func(_ string, h http.HandlerFunc) http.Handler { return h })

	postRemove := func(t *testing.T, targetResID, guestID int64, lang string, owned []int64) *httptest.ResponseRecorder {
		t.Helper()
		seedReq := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d/remove/%d", tok, targetResID, guestID), nil)
		seedRec := httptest.NewRecorder()
		csrfTok, err := mintGuestPageCSRF(seedRec, seedReq, getenv, fixedNow)
		if err != nil {
			t.Fatalf("mintGuestPageCSRF: %v", err)
		}
		if len(owned) > 0 {
			rememberOwnedGuestIDs(seedRec, getenv, owned)
		}
		form := url.Values{"_csrf": {csrfTok}}
		req := httptest.NewRequest(http.MethodPost,
			fmt.Sprintf("/l/%s/%d/remove/%d?lang=%s", tok, targetResID, guestID, lang),
			strings.NewReader(form.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		for _, c := range seedRec.Result().Cookies() {
			req.AddCookie(c)
		}
		if csrfCookie(req.Cookies()) == "" {
			t.Fatal("missing csrf cookie on removal POST")
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		return rec
	}

	guestExists := func(t *testing.T, id int64) bool {
		t.Helper()
		var n int
		if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM guest WHERE id = $1`, id).Scan(&n); err != nil {
			t.Fatalf("count guest %d: %v", id, err)
		}
		return n == 1
	}

	auditCountFor := func(t *testing.T, detail string) int {
		t.Helper()
		var n int
		if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM audit WHERE action = 'guest_removed_by_guest' AND detail = $1`, detail).Scan(&n); err != nil {
			t.Fatalf("count audit: %v", err)
		}
		return n
	}

	validSig := stayCompletePNG(t)

	t.Run("allowed removal cleans photo, clears child signer, audits owner, updates cookie, redirects, and triggers stay-scoped filing", func(t *testing.T) {
		calls = 0
		stayAdultID := base + 401
		removedID := base + 402
		childID := base + 403

		mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, doc_number, res_street, res_city, res_country, purpose, stay_from, stay_to, is_lead, signature_png, signed_at, filled_at)
			VALUES ($1, $2, $3, $3, 'Anna', 'Adult', '10011990', 'DEU', 'SYNTH1001', 'Test St 1', 'Berlin', 'DEU', '99', '2026-06-10', '2026-06-12', 1, $4, $3, $3)`,
			stayAdultID, resID, stamp, validSig)
		mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead)
			VALUES ($1, $2, $3, $3, 'Extra', 'Incomplete', '11021991', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0)`,
			removedID, resID, stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, doc_number, res_street, res_city, res_country, purpose, stay_from, stay_to, is_lead, signature_png, signed_at, filled_at, signed_for_guest_id, signed_for_role, signed_for_at, signed_for_wording)
			VALUES ($1, $2, $3, $3, 'Mila', 'Child', '10052016', 'DEU', 'SYNTH1002', 'Test St 1', 'Berlin', 'DEU', '99', '2026-06-10', '2026-06-12', 0, $4, $3, $3, $5, 'parent', '2026-06-15T11:00:00Z', 'u15-2026-11-10')`,
			childID, resID, stamp, validSig, removedID)

		if err := passportphotos.Save(dataDir, keys, removedID, synthJPEG(t), "image/jpeg"); err != nil {
			t.Fatalf("Save photo: %v", err)
		}
		if !passportphotos.Has(dataDir, removedID) {
			t.Fatal("expected photo to exist before removal")
		}

		rec := postRemove(t, resID, removedID, "cs", []int64{stayAdultID, removedID})
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("status = %d, want 303; body=%s", rec.Code, rec.Body.String())
		}
		wantLoc := fmt.Sprintf("/l/%s/%d?lang=cs&removed=1", tok, resID)
		if got := rec.Header().Get("Location"); got != wantLoc {
			t.Fatalf("Location = %q, want %q", got, wantLoc)
		}

		var gotLang string
		checkReq := httptest.NewRequest(http.MethodGet, "/", nil)
		for _, c := range rec.Result().Cookies() {
			checkReq.AddCookie(c)
			if c.Name == LangCookie {
				gotLang = c.Value
			}
		}
		if gotLang != "cs" {
			t.Fatalf("ubyhost_lang = %q, want cs", gotLang)
		}
		gotOwned := ownedGuestIDs(checkReq, getenv)
		wantOwned := []int64{stayAdultID}
		if !reflect.DeepEqual(gotOwned, wantOwned) {
			t.Fatalf("owned cookie = %v, want %v", gotOwned, wantOwned)
		}

		if guestExists(t, removedID) {
			t.Fatal("removed guest still in DB")
		}
		if !guestExists(t, stayAdultID) || !guestExists(t, childID) {
			t.Fatal("remaining guests should still exist")
		}
		if passportphotos.Has(dataDir, removedID) {
			t.Fatal("encrypted photo file should be deleted after removal")
		}

		var signedForID sql.NullInt64
		var signedForRole, signedForAt, signedForWording sql.NullString
		if err := pool.QueryRow(ctx, `SELECT signed_for_guest_id, signed_for_role, signed_for_at, signed_for_wording FROM guest WHERE id = $1`, childID).
			Scan(&signedForID, &signedForRole, &signedForAt, &signedForWording); err != nil {
			t.Fatalf("query child signer: %v", err)
		}
		if signedForID.Valid || signedForRole.Valid || signedForAt.Valid || signedForWording.Valid {
			t.Fatalf("child signer columns not cleared: id=%v role=%v at=%v wording=%v", signedForID, signedForRole, signedForAt, signedForWording)
		}

		wantDetail := fmt.Sprintf("guest=%d reservation=%d", removedID, resID)
		var auditCount int
		var auditActor string
		var auditOwner int64
		if err := pool.QueryRow(ctx, `SELECT COUNT(*), MIN(actor), MIN(owner_user_id) FROM audit WHERE action = 'guest_removed_by_guest' AND detail = $1`, wantDetail).
			Scan(&auditCount, &auditActor, &auditOwner); err != nil {
			t.Fatalf("query audit: %v", err)
		}
		if auditCount != 1 || auditActor != "guest" || auditOwner != ownerID || auditOwner == aptID {
			t.Fatalf("audit = (count=%d actor=%q owner=%d), want (1, guest, %d != %d)", auditCount, auditActor, auditOwner, ownerID, aptID)
		}

		if calls != 1 {
			t.Fatalf("submit calls = %d, want 1", calls)
		}
		if gotApt != aptID {
			t.Fatalf("submit apt = %d, want %d", gotApt, aptID)
		}
		if gotMode != "completion_immediate" {
			t.Fatalf("submit mode = %q, want completion_immediate", gotMode)
		}
		if gotOpts.IgnoreSchedule == nil || !*gotOpts.IgnoreSchedule {
			t.Fatalf("submit IgnoreSchedule = %v, want true", gotOpts.IgnoreSchedule)
		}
		gotIDs := append([]int64(nil), gotOpts.OnlyGuestIDs...)
		sort.Slice(gotIDs, func(i, j int) bool { return gotIDs[i] < gotIDs[j] })
		wantIDs := []int64{stayAdultID, childID}
		if !reflect.DeepEqual(gotIDs, wantIDs) {
			t.Fatalf("OnlyGuestIDs = %v, want %v", gotIDs, wantIDs)
		}

		var completedAt sql.NullString
		if err := pool.QueryRow(ctx, `SELECT registration_completed_at FROM reservation WHERE id = $1`, resID).Scan(&completedAt); err != nil {
			t.Fatalf("query registration_completed_at: %v", err)
		}
		if !completedAt.Valid || strings.TrimSpace(completedAt.String) == "" {
			t.Fatalf("registration_completed_at = %v, want non-empty", completedAt)
		}
	})

	t.Run("missing photo file succeeds cleanly", func(t *testing.T) {
		calls = 0
		gID := base + 410
		mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead)
			VALUES ($1, $2, $3, $3, 'NoPhoto', 'Guest', '05041992', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0)`,
			gID, resID, stamp)
		if passportphotos.Has(dataDir, gID) {
			t.Fatal("expected no photo file")
		}
		rec := postRemove(t, resID, gID, "en", []int64{gID})
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("status = %d, want 303", rec.Code)
		}
		if guestExists(t, gID) {
			t.Fatal("guest should be deleted")
		}
		wantDetail := fmt.Sprintf("guest=%d reservation=%d", gID, resID)
		var auditOwner int64
		if err := pool.QueryRow(ctx, `SELECT owner_user_id FROM audit WHERE action = 'guest_removed_by_guest' AND detail = $1`, wantDetail).Scan(&auditOwner); err != nil {
			t.Fatalf("query audit: %v", err)
		}
		if auditOwner != ownerID {
			t.Fatalf("audit owner_user_id = %d, want %d", auditOwner, ownerID)
		}
		if calls != 1 {
			t.Fatalf("filing check calls = %d, want 1", calls)
		}
	})

	t.Run("photo delete io error logs safely without failing committed removal", func(t *testing.T) {
		calls = 0
		gID := base + 420
		keepID := base + 401
		mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead)
			VALUES ($1, $2, $3, $3, 'IOErr', 'Guest', '06051993', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0)`,
			gID, resID, stamp)

		blocker := filepath.Join(t.TempDir(), "not-a-dir")
		if err := os.WriteFile(blocker, []byte("x"), 0o600); err != nil {
			t.Fatalf("write blocker file: %v", err)
		}
		currentDataDir = blocker
		t.Cleanup(func() { currentDataDir = dataDir })

		rec := postRemove(t, resID, gID, "en", []int64{keepID, gID})
		currentDataDir = dataDir
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("status = %d, want 303", rec.Code)
		}
		if guestExists(t, gID) {
			t.Fatal("guest should be deleted despite photo I/O error")
		}
		wantDetail := fmt.Sprintf("guest=%d reservation=%d", gID, resID)
		var auditOwner int64
		if err := pool.QueryRow(ctx, `SELECT owner_user_id FROM audit WHERE action = 'guest_removed_by_guest' AND detail = $1`, wantDetail).Scan(&auditOwner); err != nil {
			t.Fatalf("query audit: %v", err)
		}
		if auditOwner != ownerID {
			t.Fatalf("audit owner_user_id = %d, want %d", auditOwner, ownerID)
		}
		checkReq := httptest.NewRequest(http.MethodGet, "/", nil)
		for _, c := range rec.Result().Cookies() {
			checkReq.AddCookie(c)
		}
		if got := ownedGuestIDs(checkReq, getenv); !reflect.DeepEqual(got, []int64{keepID}) {
			t.Fatalf("owned cookie = %v, want [%d]", got, keepID)
		}
	})

	t.Run("expired filing lease allows removal", func(t *testing.T) {
		calls = 0
		gID := base + 430
		mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead)
			VALUES ($1, $2, $3, $3, 'ExpiredLease', 'Guest', '07061994', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0)`,
			gID, resID, stamp)
		mustExecGuest(t, ctx, pool, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'expired-tok', $2)`,
			gID, float64(fixedNow.Unix())-360)
		if err := passportphotos.Save(dataDir, keys, gID, synthJPEG(t), "image/jpeg"); err != nil {
			t.Fatalf("Save photo: %v", err)
		}

		rec := postRemove(t, resID, gID, "en", []int64{gID})
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("status = %d, want 303; body=%s", rec.Code, rec.Body.String())
		}
		if guestExists(t, gID) {
			t.Fatal("guest with expired lease should be deleted")
		}
		if passportphotos.Has(dataDir, gID) {
			t.Fatal("photo should be deleted for expired-lease removal")
		}
		wantDetail := fmt.Sprintf("guest=%d reservation=%d", gID, resID)
		var auditOwner int64
		if err := pool.QueryRow(ctx, `SELECT owner_user_id FROM audit WHERE action = 'guest_removed_by_guest' AND detail = $1`, wantDetail).Scan(&auditOwner); err != nil {
			t.Fatalf("query audit: %v", err)
		}
		if auditOwner != ownerID {
			t.Fatalf("audit owner_user_id = %d, want %d", auditOwner, ownerID)
		}
	})

	t.Run("refusals have zero side effects", func(t *testing.T) {
		type refusalCase struct {
			name       string
			guestID    int64
			childID    int64
			seed       func(t *testing.T, gID, cID int64)
			owned      func(gID int64) []int64
			wantStatus int
		}
		cases := []refusalCase{
			{
				name:    "another stay's guest",
				guestID: otherGuestID,
				seed: func(t *testing.T, gID, _ int64) {
					if err := passportphotos.Save(dataDir, keys, gID, synthJPEG(t), "image/jpeg"); err != nil {
						t.Fatalf("Save photo: %v", err)
					}
				},
				owned:      func(gID int64) []int64 { return []int64{gID} },
				wantStatus: http.StatusNotFound,
			},
			{
				name:    "restricted guest",
				guestID: base + 501,
				childID: base + 601,
				seed: func(t *testing.T, gID, cID int64) {
					mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead, restricted_at)
						VALUES ($1, $2, $3, $3, 'Restr', 'Guest', '01011990', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0, '2026-06-15T10:00:00Z')`,
						gID, resID, stamp)
					mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead, signed_for_guest_id, signed_for_role, signed_for_at, signed_for_wording)
						VALUES ($1, $2, $3, $3, 'KidR', 'Child', '10052016', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0, $4, 'parent', '2026-06-15T11:00:00Z', 'u15-2026-11-10')`,
						cID, resID, stamp, gID)
					if err := passportphotos.Save(dataDir, keys, gID, synthJPEG(t), "image/jpeg"); err != nil {
						t.Fatalf("Save photo: %v", err)
					}
				},
				owned:      func(gID int64) []int64 { return []int64{gID} },
				wantStatus: http.StatusForbidden,
			},
			{
				name:    "filed (sent) guest",
				guestID: base + 502,
				childID: base + 602,
				seed: func(t *testing.T, gID, cID int64) {
					mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead, submit_state)
						VALUES ($1, $2, $3, $3, 'Sent', 'Guest', '01011990', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0, 'sent')`,
						gID, resID, stamp)
					mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead, signed_for_guest_id, signed_for_role, signed_for_at, signed_for_wording)
						VALUES ($1, $2, $3, $3, 'KidS', 'Child', '10052016', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0, $4, 'parent', '2026-06-15T11:00:00Z', 'u15-2026-11-10')`,
						cID, resID, stamp, gID)
					if err := passportphotos.Save(dataDir, keys, gID, synthJPEG(t), "image/jpeg"); err != nil {
						t.Fatalf("Save photo: %v", err)
					}
				},
				owned:      func(gID int64) []int64 { return []int64{gID} },
				wantStatus: http.StatusForbidden,
			},
			{
				name:    "active filing lease",
				guestID: base + 503,
				childID: base + 603,
				seed: func(t *testing.T, gID, cID int64) {
					mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead)
						VALUES ($1, $2, $3, $3, 'Lease', 'Guest', '01011990', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0)`,
						gID, resID, stamp)
					mustExecGuest(t, ctx, pool, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'active-tok', $2)`,
						gID, float64(fixedNow.Unix())-60)
					mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead, signed_for_guest_id, signed_for_role, signed_for_at, signed_for_wording)
						VALUES ($1, $2, $3, $3, 'KidL', 'Child', '10052016', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0, $4, 'parent', '2026-06-15T11:00:00Z', 'u15-2026-11-10')`,
						cID, resID, stamp, gID)
					if err := passportphotos.Save(dataDir, keys, gID, synthJPEG(t), "image/jpeg"); err != nil {
						t.Fatalf("Save photo: %v", err)
					}
				},
				owned:      func(gID int64) []int64 { return []int64{gID} },
				wantStatus: http.StatusForbidden,
			},
			{
				name:    "unowned guest",
				guestID: base + 504,
				childID: base + 604,
				seed: func(t *testing.T, gID, cID int64) {
					mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead)
						VALUES ($1, $2, $3, $3, 'Unowned', 'Guest', '01011990', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0)`,
						gID, resID, stamp)
					mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality, res_country, purpose, stay_from, stay_to, is_lead, signed_for_guest_id, signed_for_role, signed_for_at, signed_for_wording)
						VALUES ($1, $2, $3, $3, 'KidU', 'Child', '10052016', 'DEU', 'DEU', '99', '2026-06-10', '2026-06-12', 0, $4, 'parent', '2026-06-15T11:00:00Z', 'u15-2026-11-10')`,
						cID, resID, stamp, gID)
					if err := passportphotos.Save(dataDir, keys, gID, synthJPEG(t), "image/jpeg"); err != nil {
						t.Fatalf("Save photo: %v", err)
					}
				},
				owned:      func(_ int64) []int64 { return []int64{base + 401} },
				wantStatus: http.StatusForbidden,
			},
		}

		for _, tc := range cases {
			t.Run(tc.name, func(t *testing.T) {
				tc.seed(t, tc.guestID, tc.childID)
				calls = 0
				detail := fmt.Sprintf("guest=%d reservation=%d", tc.guestID, resID)
				beforeAudit := auditCountFor(t, detail)

				rec := postRemove(t, resID, tc.guestID, "en", tc.owned(tc.guestID))
				if rec.Code != tc.wantStatus {
					t.Fatalf("status = %d, want %d; body=%s", rec.Code, tc.wantStatus, rec.Body.String())
				}
				if !guestExists(t, tc.guestID) {
					t.Fatal("refused target guest was deleted")
				}
				if !passportphotos.Has(dataDir, tc.guestID) {
					t.Fatal("refused target photo was deleted")
				}
				if tc.childID != 0 {
					var gotSigner sql.NullInt64
					if err := pool.QueryRow(ctx, `SELECT signed_for_guest_id FROM guest WHERE id = $1`, tc.childID).Scan(&gotSigner); err != nil {
						t.Fatalf("query child signer: %v", err)
					}
					if !gotSigner.Valid || gotSigner.Int64 != tc.guestID {
						t.Fatalf("child signed_for_guest_id = %v, want %d", gotSigner, tc.guestID)
					}
				}
				if afterAudit := auditCountFor(t, detail); afterAudit != beforeAudit {
					t.Fatalf("audit rows changed from %d to %d", beforeAudit, afterAudit)
				}
				if calls != 0 {
					t.Fatalf("submit calls = %d, want 0", calls)
				}
			})
		}
	})
}
