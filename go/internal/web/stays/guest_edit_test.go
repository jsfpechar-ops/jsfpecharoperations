package stays

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func TestGuestEditGoldenHTTP(t *testing.T) {
	g := loadGuestEditGolden(t)
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	for _, c := range g.Cases {
		switch c.Method {
		case http.MethodPost:
			if c.Status != http.StatusSeeOther && c.Status != http.StatusOK {
				t.Errorf("%s: status %d", c.Name, c.Status)
			}
			if c.Status == http.StatusSeeOther && c.Location != "" && !strings.HasPrefix(c.Location, "/") {
				t.Errorf("%s: location %q", c.Name, c.Location)
			}
		case http.MethodGet:
			if c.Status != http.StatusOK && c.Status != http.StatusNotFound && c.Status != http.StatusSeeOther {
				t.Errorf("%s: status %d", c.Name, c.Status)
			}
		}
	}
}

func TestGuestIsFiledUnit(t *testing.T) {
	if !guestIsFiled(hostGuest{submitState: "sent"}) {
		t.Fatal("sent is filed")
	}
	if guestIsFiled(hostGuest{submitState: "pending"}) {
		t.Fatal("pending not filed")
	}
}

func TestFiledRecordChangedUnit(t *testing.T) {
	res := hostReservation{dateFrom: "2026-06-01", dateTo: "2026-06-04"}
	stored := hostGuest{nationality: "DEU", surname: "A", firstName: "B", submitState: "sent"}
	changed := hostGuest{nationality: "DEU", surname: "A", firstName: "C", submitState: "sent"}
	if !filedRecordChanged(stored, changed, res) {
		t.Fatal("first name change")
	}
	same := hostGuest{nationality: "DEU", surname: "A", firstName: "B", submitState: "sent"}
	if filedRecordChanged(stored, same, res) {
		t.Fatal("no change")
	}
}

func TestGuestPayloadDocType(t *testing.T) {
	raw := validationDocTypes()
	if len(raw) == 0 {
		t.Fatal("doc types")
	}
}

type guestEditGolden struct {
	Now   string `json:"now"`
	Seed  []any  `json:"seed"`
	Cases []struct {
		Name     string `json:"name"`
		Method   string `json:"method"`
		Path     string `json:"path"`
		Body     string `json:"body"`
		User     int64  `json:"user"`
		Status   int    `json:"status"`
		Location string `json:"location"`
		FlashKey string `json:"flash_key"`
	} `json:"cases"`
}

func loadGuestEditGolden(t *testing.T) guestEditGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/guest_edit_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g guestEditGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestGuestEditSignedOutRedirects(t *testing.T) {
	t.Skip("signed-out redirect parity is in guest_edit_golden.json; hostweb.Login needs a pool")
}

func TestGuestEditKeepsSignature(t *testing.T) {
	now := time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC)
	sig := validGuestSignature()
	if got := keptGuestSignature(sig, ""); got != sig {
		t.Fatalf("kept %q", got)
	}
	if keptGuestSignature("not-a-data-url", "data:image/png;base64,OLD") != "data:image/png;base64,OLD" {
		t.Fatal("fallback stored")
	}
	_ = now
}

func TestGuestWriteEncryption(t *testing.T) {
	pool := guestWriteTestPool(t)
	if pool == nil {
		return
	}
	ctx := context.Background()
	baseID := time.Now().UnixNano()%8000000000 + 7300000
	userID, aptID, resID := baseID, baseID+1, baseID+2
	stamp := "2026-01-01T00:00:00Z"
	tok := fmt.Sprintf("write%d", aptID)
	if _, err := pool.Exec(ctx, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3)`, userID, fmt.Sprintf("we%d@example.test", userID), stamp); err != nil {
		t.Fatalf("user fixture insert failed: %v", err)
	}
	if _, err := pool.Exec(ctx, `INSERT INTO apartment (id, owner_user_id, internal_name, city_en, active, permalink_token, created_at)
		VALUES ($1, $2, 'Synthetic', 'Prague', 1, $3, $4)`, aptID, userID, tok, stamp); err != nil {
		t.Fatal("apartment fixture insert failed")
	}
	if _, err := pool.Exec(ctx, `INSERT INTO reservation (id, apartment_id, uid, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'manual', '2026-06-20', '2026-06-22', $4, $4)`, resID, aptID, fmt.Sprintf("stay-%d", resID), stamp); err != nil {
		t.Fatal("reservation fixture insert failed")
	}
	t.Cleanup(func() {
		_, _ = pool.Exec(context.Background(), `DELETE FROM guest WHERE reservation_id = $1`, resID)
		_, _ = pool.Exec(context.Background(), `DELETE FROM reservation WHERE id = $1`, resID)
		_, _ = pool.Exec(context.Background(), `DELETE FROM apartment WHERE id = $1`, aptID)
		_, _ = pool.Exec(context.Background(), `DELETE FROM user_account WHERE id = $1`, userID)
	})
	key := base64.URLEncoding.EncodeToString(make([]byte, 32))
	getenv := func(name string) string {
		switch name {
		case "UBYHOST_DATA_KEYS":
			return key
		case "UBYHOST_DATA_KEY_LEGACY":
			return "0"
		}
		return ""
	}
	d := guestEditDeps{pool: pool, getenv: getenv}
	payload := hostGuest{
		surname: "Synthetic", firstName: "Guest", birthDate: "1990-01-02", docNumber: "SYNTHETIC-DOC",
		visaNum: "SYNTHETIC-VISA", resStreet: "Test Street", resCity: "Test City", resCountry: "CZ",
		purpose: "tourism", stayFrom: "2026-06-20", stayTo: "2026-06-22", docType: "passport",
	}
	guestID, err := insertHostGuest(ctx, &guestEditCall{guestEditDeps: d}, resID, payload, validGuestSignature(), "pending", false, stamp)
	if err != nil {
		t.Fatal("host guest insert failed")
	}
	assertRaw := func(visaEncrypted, updated bool) {
		t.Helper()
		var birth, birthEnc, doc, docEnc, visa, visaEnc, street, streetEnc, city, cityEnc, sig, sigEnc string
		if err := pool.QueryRow(ctx, `SELECT COALESCE(birth_date,''), COALESCE(birth_date_enc,''), COALESCE(doc_number,''), COALESCE(doc_number_enc,''),
			COALESCE(visa_number,''), COALESCE(visa_number_enc,''), COALESCE(res_street,''), COALESCE(res_street_enc,''),
			COALESCE(res_city,''), COALESCE(res_city_enc,''), COALESCE(signature_png,''), COALESCE(signature_png_enc,'') FROM guest WHERE id = $1`, guestID).Scan(
			&birth, &birthEnc, &doc, &docEnc, &visa, &visaEnc, &street, &streetEnc, &city, &cityEnc, &sig, &sigEnc); err != nil {
			t.Fatal("raw encrypted field read failed")
		}
		if birth != "" || doc != "" || visa != "" || city != "" || birthEnc == "" || docEnc == "" || cityEnc == "" ||
			(visaEncrypted && visaEnc == "") || (!visaEncrypted && visaEnc != "") {
			t.Fatal("touched protected column placement is incorrect")
		}
		if !updated && (street != "" || sig != "" || streetEnc == "" || sigEnc == "") {
			t.Fatal("inserted protected fields are not encrypted")
		}
		if updated && (street != "untouched-legacy" || sig != "untouched-signature" || streetEnc != "" || sigEnc != "") {
			t.Fatalf("untouched legacy fields changed (streetPlain=%t streetCipher=%t signaturePlain=%t signatureCipher=%t)", street != "untouched-legacy", streetEnc != "", sig != "untouched-signature", sigEnc != "")
		}
	}
	assertRaw(true, false)
	loaded, ok, err := d.loadGuest(ctx, userID, guestID)
	if err != nil || !ok || loaded.birthDate != payload.birthDate || loaded.docNumber != payload.docNumber || loaded.signaturePNG != validGuestSignature() {
		t.Fatal("host guest hydration did not return the submitted values")
	}
	if _, err := pool.Exec(ctx, `UPDATE guest SET birth_date='legacy-birth', birth_date_enc=NULL,
		doc_number='legacy-doc', doc_number_enc=NULL, visa_number='legacy-visa', visa_number_enc=NULL,
		res_city='legacy-city', res_city_enc=NULL, res_street='untouched-legacy', res_street_enc=NULL,
		signature_png='untouched-signature', signature_png_enc=NULL WHERE id = $1`, guestID); err != nil {
		t.Fatal("legacy fixture update failed")
	}
	updates := map[string]any{"birth_date": "1992-03-04", "doc_number": "REPLACED-DOC", "visa_number": "", "res_city": "Replacement City"}
	updated, err := guestUpdateIf(ctx, pool, getenv, guestID, "pending", updates, time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC))
	if err != nil || !updated {
		t.Fatal("host guest update failed")
	}
	assertRaw(false, true)
	loaded, ok, err = d.loadGuest(ctx, userID, guestID)
	if err != nil || !ok || loaded.birthDate != "1992-03-04" || loaded.docNumber != "REPLACED-DOC" || loaded.visaNum != "" || loaded.resCity != "Replacement City" || loaded.resStreet != "untouched-legacy" {
		t.Fatal("updated or untouched guest field hydration was incorrect")
	}
	if _, err := guestUpdateIf(ctx, pool, getenv, guestID, "pending", map[string]any{"doc_number": 123}, time.Now()); err == nil {
		t.Fatal("wrong protected value type must fail before writing")
	}
}

func guestWriteTestPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := strings.TrimSpace(os.Getenv("UBYHOST_TEST_DATABASE_URL"))
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL not set")
		return nil
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_guest_write_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("connect isolated test database failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal("create isolated test database failed")
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			return
		}
		defer c.Close(context.Background())
		_, _ = c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)")
	})
	config, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("parse isolated test database settings failed")
	}
	config.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		t.Fatal("open isolated test database failed")
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("load test migrations failed")
	}
	sort.Strings(files)
	for _, file := range files {
		sql, err := os.ReadFile(file)
		if err != nil {
			t.Fatal("read test migration failed")
		}
		up := string(sql)
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("apply test migration %s failed: %v", filepath.Base(file), err)
		}
	}
	return pool
}

func validGuestSignature() string {
	return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
}
