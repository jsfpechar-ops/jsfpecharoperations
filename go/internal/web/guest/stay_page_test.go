package guest

import (
	"bytes"
	"context"
	"encoding/base64"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// TestStayPageClaimedDeclaredTwoOneDone renders the stay page for a claimed
// stay with 2 declared guests and 1 complete guest. It checks the stepper,
// the saved and not-filled rows, the duplicate-document warning, and that the
// door-code card stays hidden until every declared guest is in.
func TestStayPageClaimedDeclaredTwoOneDone(t *testing.T) {
	pool := testPool(t)
	if pool == nil {
		t.Skip("UBYHOST_TEST_DATABASE_URL")
	}
	ctx := context.Background()
	var schemaOK int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'guest'`).Scan(&schemaOK); err != nil || schemaOK == 0 {
		t.Skip("needs migrated Postgres schema")
	}
	var buf bytes.Buffer
	img := image.NewRGBA(image.Rect(0, 0, 2, 2))
	img.Set(0, 0, color.Black)
	if err := png.Encode(&buf, img); err != nil {
		t.Fatal(err)
	}
	sig := "data:image/png;base64," + base64.StdEncoding.EncodeToString(buf.Bytes())

	now := func() time.Time { return time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC) }
	stamp := isoNow(now())
	const ownerID, aptID, resID = int64(172401), int64(172401), int64(172402)
	const tok = "stayp-172401"
	mustExec(t, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, 'stayp-owner', 'x', 'host', 1, $2) ON CONFLICT (id) DO NOTHING`, ownerID, stamp)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, permalink_token, active, created_at)
		VALUES ($1, $2, 'Flat', $3, 1, $4) ON CONFLICT (id) DO NOTHING`, aptID, ownerID, tok, stamp)
	mustExec(t, pool, `INSERT INTO reservation (id, uid, apartment_id, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, 'stayp-172402', $2, 'active', 'ical', '2026-06-01', '2026-06-05', $3, $3) ON CONFLICT (id) DO NOTHING`, resID, aptID, stamp)
	mustExec(t, pool, `INSERT INTO reservation_claim (reservation_id, state, token_version, declared_guests, created_at, updated_at)
		VALUES ($1, $2, 1, 2, $3, $3) ON CONFLICT (reservation_id) DO UPDATE SET state = EXCLUDED.state, token_version = 1, declared_guests = 2`,
		resID, claimStateClaimed, stamp)
	mustExec(t, pool, `DELETE FROM guest WHERE reservation_id = $1`, resID)
	// Both guests share a document number, so the duplicate warning must show.
	for i, s := range []string{sig, ""} {
		mustExec(t, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality,
			doc_number, res_street, res_city, res_country, purpose, is_lead, signature_png)
			VALUES ($1, $2, $3, $3, 'Test', 'Guest', '01011990', 'CZE', 'AB123456', 'Street 1', 'City', 'CZE', '03', 0, $4)`,
			resID*10+int64(i), resID, stamp, s)
	}

	getenv := func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return strings.Repeat("c", 32)
		}
		if k == "UBYHOST_GUEST_PIN" {
			return "0"
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
	body := rec.Body.String()
	for _, want := range []string{"data-guest-stepper", "saved", "not filled in", "data-dup-warning"} {
		if !strings.Contains(body, want) {
			t.Errorf("stay page missing %q", want)
		}
	}
	if strings.Contains(body, `id="door-code"`) || strings.Contains(body, "g-door-code") {
		t.Errorf("door-code card shown before all declared guests are in")
	}
}
