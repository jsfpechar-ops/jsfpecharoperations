package guest

import (
	"bytes"
	"context"
	"encoding/base64"
	"image"
	"image/color"
	"image/png"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// TestStayPeopleSignatureCompleteness: a guest with every field but no
// signature is not complete (Python guest_is_complete); with a drawn
// signature the same guest is complete.
func TestStayPeopleSignatureCompleteness(t *testing.T) {
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
	stamp := isoNow(time.Now().UTC())
	resID := int64(172301)
	mustExec(t, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES (172301, 'pinsig-owner', 'x', 'host', 1, $1) ON CONFLICT (id) DO NOTHING`, stamp)
	mustExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, permalink_token, active, created_at)
		VALUES (172301, 172301, 'Flat', 'pinsig', 1, $1) ON CONFLICT (id) DO NOTHING`, stamp)
	mustExec(t, pool, `INSERT INTO reservation (id, uid, apartment_id, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, 'pinsig-172301', 172301, 'active', 'ical', '2026-06-01', '2026-06-05', $2, $2) ON CONFLICT (id) DO NOTHING`, resID, stamp)
	mustExec(t, pool, `DELETE FROM guest WHERE reservation_id = $1`, resID)
	for i, s := range []string{"", sig} {
		mustExec(t, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality,
			doc_number, res_street, res_city, res_country, purpose, is_lead, signature_png)
			VALUES ($1, $2, $3, $3, 'Test', 'Guest', '01011990', 'CZE', 'AB123456', 'Street 1', 'City', 'CZE', '03', 0, $4)`,
			resID*10+int64(i), resID, stamp, s)
	}
	d := stayClaimDeps{pool: pool, getenv: func(string) string { return "" }, now: func() time.Time { return time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC) }}
	stay := &scStay{id: resID, status: "active", dateFrom: "2026-06-01", dateTo: "2026-06-05"}
	people, filled, err := d.stayPeople(ctx, httptest.NewRequest("GET", "/", nil), stay, "en")
	if err != nil {
		t.Fatal(err)
	}
	if len(people) != 2 {
		t.Fatalf("want 2 people, got %d", len(people))
	}
	if people[0].Complete {
		t.Errorf("guest without signature reported complete")
	}
	if !people[1].Complete {
		t.Errorf("guest with signature reported incomplete: %v", validation.GuestIssues(validation.GuestRow{
			Surname: "Guest", FirstName: "Test", BirthDate: "01011990", Nationality: "CZE", DocNumber: "AB123456",
			ResStreet: "Street 1", ResCity: "City", ResCountry: "CZE", Purpose: "03", SignaturePNG: sig,
		}, "2026-06-01", "2026-06-05", d.now()))
	}
	if filled != 1 {
		t.Errorf("filled = %d, want 1", filled)
	}
}
