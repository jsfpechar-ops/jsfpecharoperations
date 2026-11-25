package guest

import (
	"bytes"
	"encoding/base64"
	"image"
	"image/color"
	"image/png"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

func stayCompleteEnv() func(string) string {
	env := map[string]string{
		"UBYHOST_SECRET_KEY":      "kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk",
		"UBYHOST_DATA_KEYS":       base64.URLEncoding.EncodeToString(bytes.Repeat([]byte{7}, 32)),
		"UBYHOST_DATA_KEY_LEGACY": "0",
	}
	return func(k string) string { return env[k] }
}

func stayCompletePNG(t *testing.T) string {
	t.Helper()
	var buf bytes.Buffer
	img := image.NewRGBA(image.Rect(0, 0, 2, 2))
	img.Set(0, 0, color.Black)
	if err := png.Encode(&buf, img); err != nil {
		t.Fatal(err)
	}
	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(buf.Bytes())
}

// Python stores the personal fields only in the *_enc columns; the plain columns stay empty.
func TestStayCompleteEncryptedGuestAllPathsAgree(t *testing.T) {
	pool := testPoolOptional(t)
	if pool == nil {
		return
	}
	ctx := t.Context()
	getenv := stayCompleteEnv()
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		t.Fatal(err)
	}
	enc := func(s string) string {
		tok, err := keys.EncryptField(s)
		if err != nil {
			t.Fatal(err)
		}
		return tok
	}
	now := func() time.Time { return time.Date(2030, 1, 1, 0, 0, 0, 0, time.UTC) }
	stamp := "2026-01-01T00:00:00Z"
	aptID := int64(81000000 + time.Now().UnixNano()%1000000)
	resID := aptID + 1
	mustExecGuest(t, ctx, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3) ON CONFLICT DO NOTHING`, aptID, "enc2060"+time.Now().Format("150405")+"@example.test", stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, permalink_pin, created_at)
		VALUES ($1, $1, 'Flat', 'Prague', 1, $2, '123456', $3)`, aptID, "enc2060-"+time.Now().Format("150405"), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', '2030-01-10', '2030-01-13', $4, $4)`, resID, aptID, "enc2060-"+time.Now().Format("150405"), stamp)
	mustExecGuest(t, ctx, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, nationality,
		res_country, purpose, is_lead, birth_date_enc, doc_number_enc, res_street_enc, res_city_enc, signature_png_enc)
		VALUES ($1, $2, $3, $3, 'Test', 'Guest', 'DEU', 'CZE', '99', 1, $4, $5, $6, $7, $8)`,
		resID*10+1, resID, stamp, enc("01011990"), enc("E2E000000"), enc("Street 1"), enc("Prague"), enc(stayCompletePNG(t)))

	d := stayClaimDeps{pool: pool, getenv: getenv, now: now}
	stay := &scStay{id: resID, status: "active", dateFrom: "2030-01-10", dateTo: "2030-01-13"}
	people, _, err := d.stayPeople(ctx, httptest.NewRequest("GET", "/", nil), stay, "en")
	if err != nil {
		t.Fatal(err)
	}
	if len(people) != 1 || !people[0].Complete {
		t.Fatalf("stayPeople: want one complete guest, got %+v", people)
	}
	pick := pickReservation{ID: resID, DateFrom: "2030-01-10", DateTo: "2030-01-13"}
	if !registrationComplete(ctx, pool, getenv, now, pick, now()) {
		t.Error("registrationComplete: encrypted complete guest reported incomplete")
	}
	res := formResRow{id: resID, dateFrom: "2030-01-10", dateTo: "2030-01-13"}
	if n := completeFormGuests(ctx, pool, getenv, now, res, now()); n != 1 {
		t.Errorf("completeFormGuests: complete count %d want 1", n)
	}
}

func TestStayGuestColsValidationRow(t *testing.T) {
	getenv := stayCompleteEnv()
	now := func() time.Time { return time.Date(2030, 1, 1, 0, 0, 0, 0, time.UTC) }
	sig := stayCompletePNG(t)
	full := stayGuestCols{First: "Test", Surname: "Guest", Nat: "DEU", BirthP: "01011990", DocP: "E2E000000",
		StreetP: "Street 1", CityP: "Prague", Country: "CZE", Purpose: "99", StayFrom: "2030-01-10", StayTo: "2030-01-13", SigP: sig}

	row, err := full.validationRow(getenv, now)
	if err != nil {
		t.Fatalf("plain complete record: %v", err)
	}
	if !validation.GuestIsComplete(row, "2030-01-10", "2030-01-13", time.Now()) {
		t.Error("plain complete record reported incomplete")
	}

	noBirth := full
	noBirth.BirthP = ""
	row, err = noBirth.validationRow(getenv, now)
	if err != nil {
		t.Fatalf("empty birth date: %v", err)
	}
	if validation.GuestIsComplete(row, "2030-01-10", "2030-01-13", time.Now()) {
		t.Error("record without birth date reported complete")
	}

	badToken := full
	badToken.SigP = ""
	badToken.SigE = "not-a-token"
	if _, err := badToken.validationRow(getenv, now); err == nil {
		t.Error("invalid token: want error, got nil")
	}
}
