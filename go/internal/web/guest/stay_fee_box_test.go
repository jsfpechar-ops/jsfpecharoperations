package guest

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"strings"
	"testing"
	"time"
)

// renderFeeBox seeds a fee-collecting apartment with an IBAN payout, a
// reservation claimed for `declared` guests, and one complete CZE guest. It
// renders the stay page with UBYHOST_STAY_FEE_GUEST_PAY set to guestPay and
// returns the body.
func renderFeeBox(t *testing.T, declared int, guestPay string) string {
	t.Helper()
	pool := testPool(t)
	if pool == nil {
		t.Skip("UBYHOST_TEST_DATABASE_URL")
	}
	ctx := context.Background()
	var schemaOK int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'apartment' AND column_name = 'stay_fee_guest_rails'`).Scan(&schemaOK); err != nil || schemaOK == 0 {
		t.Skip("needs migrated Postgres schema")
	}
	var buf bytes.Buffer
	img := image.NewRGBA(image.Rect(0, 0, 2, 2))
	img.Set(0, 0, color.Black)
	if err := png.Encode(&buf, img); err != nil {
		t.Fatal(err)
	}
	sig := "data:image/png;base64," + base64.StdEncoding.EncodeToString(buf.Bytes())

	now := func() time.Time { return time.Date(2026, 6, 2, 12, 0, 0, 0, time.UTC) }
	stamp := isoNow(now())
	const ownerID, aptID, entityID, resID = int64(206301), int64(206301), int64(206301), int64(206302)
	const tok = "feebox-206301"
	mustExec(t, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, 'feebox-owner', 'x', 'host', 1, $2) ON CONFLICT (id) DO NOTHING`, ownerID, stamp)
	mustExec(t, pool, `INSERT INTO legal_entity (id, name, iban, created_at, owner_user_id)
		VALUES ($1, 'Fee Operator', 'CZ6508000000192000145399', $2, $3) ON CONFLICT (id) DO NOTHING`, entityID, stamp, ownerID)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, permalink_token, active, created_at, city_en,
		legal_entity_id, stay_fee_collect, stay_fee_rate_czk, stay_fee_guest_rails)
		VALUES ($1, $2, 'Flat', $3, 1, $4, 'Prague', $5, 1, 100, 'iban')
		ON CONFLICT (id) DO UPDATE SET legal_entity_id = EXCLUDED.legal_entity_id, stay_fee_collect = 1,
			stay_fee_rate_czk = 100, stay_fee_guest_rails = 'iban'`,
		aptID, ownerID, tok, stamp, entityID)
	mustExec(t, pool, `INSERT INTO stay_fee_rate (apartment_id, rate_czk, effective_from, created_at)
		VALUES ($1, 100, '2026-01-01', $2) ON CONFLICT (apartment_id, effective_from) DO UPDATE SET rate_czk = 100`, aptID, stamp)
	mustExec(t, pool, `INSERT INTO reservation (id, uid, apartment_id, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, 'feebox-206302', $2, 'active', 'ical', '2026-06-01', '2026-06-05', $3, $3) ON CONFLICT (id) DO NOTHING`, resID, aptID, stamp)
	mustExec(t, pool, `INSERT INTO reservation_claim (reservation_id, state, token_version, declared_guests, created_at, updated_at)
		VALUES ($1, $2, 1, $3, $4, $4) ON CONFLICT (reservation_id) DO UPDATE SET state = EXCLUDED.state, token_version = 1, declared_guests = EXCLUDED.declared_guests`,
		resID, claimStateClaimed, declared, stamp)
	mustExec(t, pool, `UPDATE reservation SET declared_guests = $1 WHERE id = $2`, declared, resID)
	mustExec(t, pool, `DELETE FROM guest WHERE reservation_id = $1`, resID)
	mustExec(t, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality,
		doc_number, res_street, res_city, res_country, purpose, is_lead, signature_png)
		VALUES ($1, $2, $3, $3, 'Fee', 'Guest', '01011990', 'CZE', 'FB123456', 'Street 1', 'City', 'CZE', '03', 0, $4)`,
		resID*10, resID, stamp, sig)

	getenv := func(k string) string {
		switch k {
		case "UBYHOST_SECRET_KEY":
			return strings.Repeat("c", 32)
		case "UBYHOST_GUEST_PIN":
			return "0"
		case "UBYHOST_STAY_FEE_GUEST_PAY":
			return guestPay
		}
		return ""
	}
	d := stayClaimDeps{pool: pool, getenv: getenv, now: now}
	req := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/l/%s/%d?lang=en", tok, resID), nil)
	req.SetPathValue("token", tok)
	req.SetPathValue("reservation_id", fmt.Sprintf("%d", resID))
	rec := httptest.NewRecorder()
	d.stayOverview(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d body %q", rec.Code, rec.Body.String())
	}
	return rec.Body.String()
}

// TestStayPageFeeBox checks the fee box on the claimed stay page: shown with
// guest pay on and every declared guest in, hidden with guest pay off, and
// hidden while a declared guest is still missing.
func TestStayPageFeeBox(t *testing.T) {
	t.Run("on_all_in", func(t *testing.T) {
		body := renderFeeBox(t, 1, "on")
		i := strings.Index(body, `id="fee-pay"`)
		if i < 0 {
			t.Fatalf("fee box missing with guest pay on")
		}
		// 4 nights at 100 CZK for one guest.
		if !strings.Contains(body[i:], "400") {
			t.Errorf("fee box does not show the 400 CZK amount")
		}
		if !strings.Contains(body[i:], "g-fee-qr-img") || !strings.Contains(body[i:], "data:image/png;base64,") {
			t.Errorf("fee box has no QR image")
		}
	})
	t.Run("off", func(t *testing.T) {
		body := renderFeeBox(t, 1, "off")
		if strings.Contains(body, `id="fee-pay"`) {
			t.Errorf("fee box shown with guest pay off")
		}
	})
	t.Run("guest_missing", func(t *testing.T) {
		body := renderFeeBox(t, 2, "on")
		if strings.Contains(body, `id="fee-pay"`) {
			t.Errorf("fee box shown while a declared guest is missing")
		}
	})
}

// TestFeeKeysAllLanguages checks that every fee_* key the fee box template
// prints has a non-empty string in each supported language.
func TestFeeKeysAllLanguages(t *testing.T) {
	tmpl, err := os.ReadFile("templates/fee_pay.tmpl")
	if err != nil {
		t.Fatal(err)
	}
	var cat map[string]map[string]string
	if err := json.Unmarshal(catalogJSON, &cat); err != nil {
		t.Fatal(err)
	}
	keyRE := regexp.MustCompile(`\.T "(fee_[a-z0-9_]+)"`)
	keys := map[string]bool{}
	for _, m := range keyRE.FindAllStringSubmatch(string(tmpl), -1) {
		keys[m[1]] = true
	}
	if len(keys) == 0 {
		t.Fatal("no fee_* keys found in templates/fee_pay.tmpl")
	}
	for _, lang := range []string{"en", "cs", "de", "es", "fr", "uk"} {
		values, ok := cat[lang]
		if !ok {
			t.Errorf("language %q missing from i18n.json", lang)
			continue
		}
		for key := range keys {
			if strings.TrimSpace(values[key]) == "" {
				t.Errorf("%s: %q missing or empty", lang, key)
			}
		}
	}
}
