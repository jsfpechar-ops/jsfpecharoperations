package guest

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

// The 30 guest keys added to i18n.json by brief 2056 step a, in all six guest languages.
var fixes2056Keys = strings.Fields(`leon_error leon_error_reload leon_host_answered leon_host_answered_plain leon_intro leon_label leon_name leon_needs_js leon_other_prompt leon_placeholder leon_queued leon_role leon_see_card leon_send leon_sending leon_sit_emergency_help leon_sit_other leon_tag leon_waiting leon_welcome leon_you passport_photo_bad_type passport_photo_selected passport_photo_too_large_image passport_photo_too_large_pdf remove_help remove_keep remove_title remove_yes sign_for_who`)

func loadGuestCatalogue2056(t *testing.T) map[string]map[string]string {
	t.Helper()
	raw, err := os.ReadFile("i18n.json")
	if err != nil {
		t.Fatal(err)
	}
	var cat map[string]map[string]string
	if err := json.Unmarshal(raw, &cat); err != nil {
		t.Fatal(err)
	}
	return cat
}

func TestI18nFixes2056KeysInAllLanguages(t *testing.T) {
	cat := loadGuestCatalogue2056(t)
	for _, lang := range []string{"en", "cs", "de", "es", "fr", "uk"} {
		for _, k := range fixes2056Keys {
			if cat[lang][k] == "" {
				t.Errorf("language %s: key %s missing or empty", lang, k)
			}
		}
	}
}

func TestRemovePageFixes2056ShowsFooterAndNoRawKeys(t *testing.T) {
	cat := loadGuestCatalogue2056(t)
	for _, lang := range []string{"en", "cs"} {
		v := formView{
			Page: Page{
				Lang:       lang,
				Token:      "tok2056",
				PrivacyURL: "/l/tok2056/privacy?lang=" + lang,
				CSRFToken:  "csrf",
			},
			ReservationID: 1,
			GuestID:       2,
			PersonName:    "Test Person",
			BackURL:       "/l/tok2056/1?lang=" + lang,
		}
		rec := httptest.NewRecorder()
		writeRemovePage(rec, httptest.NewRequest("GET", "/", nil), v)
		if rec.Code != 200 {
			t.Fatalf("%s: status %d", lang, rec.Code)
		}
		body := rec.Body.String()
		if strings.Contains(body, "remove_") {
			t.Errorf("%s: raw remove key visible", lang)
		}
		if want := cat[lang]["privacy_link"]; want == "" || !strings.Contains(body, want) {
			t.Errorf("%s: privacy footer link %q missing", lang, want)
		}
		if !strings.Contains(body, `href="/l/tok2056/privacy?lang=`+lang+`"`) {
			t.Errorf("%s: privacy href missing", lang)
		}
	}
}

func TestHubPageFixes2056ShowsHostCard(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	t.Setenv("UBYHOST_SECRET_KEY", strings.Repeat("z", 32))
	t.Setenv("UBYHOST_GUEST_PIN", "0")
	t.Setenv("UBYHOST_MAIL_BACKEND", "disabled")
	getenv := func(k string) string { return os.Getenv(k) }
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	ctx := t.Context()
	stamp := "2026-01-01T00:00:00Z"
	aptID := int64(79000000 + time.Now().UnixNano()%1000000)
	tok := fmt.Sprintf("hubhost2056%d", aptID)
	resID := aptID + 1
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, aptID, fmt.Sprintf("h%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO legal_entity (id, owner_user_id, name, contact_email, created_at)
		VALUES ($1, $1, 'Hub Host Co 2056', 'hub2056@example.test', $2)`, aptID, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, legal_entity_id, internal_name, city_en, active, permalink_token, permalink_pin, created_at)
		VALUES ($1, $1, $1, 'Flat', 'Prague', 1, $2, '123456', $3)`, aptID, tok, stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', $4, $5, $6, $6)`, resID, aptID, fmt.Sprintf("hub-%d", resID), "2026-06-10", "2026-06-12", stamp)

	d := shellDeps{pool: pool, getenv: getenv, now: now}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /l/{token}", d.pickStay)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/l/"+tok+"?lang=en", nil))
	body := rec.Body.String()
	for _, want := range []string{"Hub Host Co 2056", "hub2056@example.test"} {
		if !strings.Contains(body, want) {
			t.Errorf("hub page missing host %q (status %d)", want, rec.Code)
		}
	}
}

func TestPersonNumberFixes2056CountsCompleteGuestsOnly(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := t.Context()
	stamp := "2026-01-01T00:00:00Z"
	aptID := int64(80000000 + time.Now().UnixNano()%1000000)
	resID := aptID + 1
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, aptID, fmt.Sprintf("p%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, permalink_pin, created_at)
		VALUES ($1, $1, 'Flat', 'Prague', 1, $2, '123456', $3)`, aptID, fmt.Sprintf("person2056%d", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', $4, $5, $6, $6)`, resID, aptID, fmt.Sprintf("pn-%d", resID), "2026-06-10", "2026-06-12", stamp)
	// Two partial guests: no complete guest, so the next person is number 1.
	for i := int64(1); i <= 2; i++ {
		mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, nationality)
			VALUES ($1, $2, $3, $3, 'Partial', 'CZE')`, resID*10+i, resID, stamp)
	}
	res := formResRow{id: resID, dateFrom: "2026-06-10", dateTo: "2026-06-12"}
	if n := completeFormGuests(ctx, pool, func(string) string { return "" }, time.Now, res, time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)); n != 0 {
		t.Fatalf("two partial guests: complete count %d want 0", n)
	}
}

func TestGuideLiveFixes2056NeedsAllMustHaveKinds(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := t.Context()
	stamp := "2026-01-01T00:00:00Z"
	aptID := int64(81000000 + time.Now().UnixNano()%1000000)
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, aptID, fmt.Sprintf("g%d@example.test", aptID), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, created_at)
		VALUES ($1, $1, 'Guide Flat', 'Prague', 1, $2)`, aptID, stamp)
	s := &lqServer{pool: pool, lookupEnv: func(string) (string, bool) { return "", false }}
	add := func(id int64, kind, state string) {
		mustExecGuest(t, ctx, pool, `INSERT INTO guide_item (id, apartment_id, topic, kind, title, steps, visibility, state, source, sort_order, created_at, updated_at)
			VALUES ($1, $2, 'custom', $3, $3, '[]', 'everyone', $4, 'host', $1, $5, $5) ON CONFLICT DO NOTHING`, id, aptID, kind, state, stamp)
	}
	add(aptID*10+1, "checkin", "done")
	add(aptID*10+2, "wifi", "done")
	add(aptID*10+3, "house_rules", "done")
	live, err := s.guideLive(ctx, aptID)
	if err != nil {
		t.Fatal(err)
	}
	if live {
		t.Fatal("three cards done but heating, checkout and emergency missing: want not live")
	}
	add(aptID*10+4, "heating", "skipped")
	add(aptID*10+5, "checkout", "done")
	add(aptID*10+6, "emergency", "done")
	if live, err = s.guideLive(ctx, aptID); err != nil {
		t.Fatal(err)
	} else if !live {
		t.Fatal("all five must-have kinds done or skipped: want live")
	}
}
