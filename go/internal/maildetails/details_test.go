package maildetails_test

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"testing"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/maildetails"
)

// goldenGuest, goldenCase and golden mirror testdata/receipt_golden.json, which
// App/scripts/mail_details_golden.py writes from the real Python renderer.
type goldenGuest struct {
	ID            int64  `json:"id"`
	ReservationID int64  `json:"reservation_id"`
	FirstName     string `json:"first_name"`
	Surname       string `json:"surname"`
	DocNumber     string `json:"doc_number"`
	DocNumberEnc  string `json:"doc_number_enc"`
	EnteredBy     string `json:"entered_by"`
	CreatedAt     string `json:"created_at"`
	IsLead        int    `json:"is_lead"`
}

type goldenCase struct {
	Name          string        `json:"name"`
	ReservationID int64         `json:"reservation_id"`
	Lang          string        `json:"lang"`
	ClaimedAt     *string       `json:"claimed_at"`
	Seeded        bool          `json:"seeded"`
	Guests        []goldenGuest `json:"guests"`
	ExpectText    string        `json:"expect_text"`
	ExpectHTML    string        `json:"expect_html"`
}

type golden struct {
	FernetKey string       `json:"fernet_key"`
	Cases     []goldenCase `json:"cases"`
}

func loadGolden(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/receipt_golden.json")
	if err != nil {
		t.Fatalf("read golden: %v", err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatalf("parse golden: %v", err)
	}
	return g
}

// goldenEnv gives the renderer the invented test data key the Python oracle used.
func goldenEnv(key string) func(string) string {
	env := map[string]string{"UBYHOST_DATA_KEYS": key, "UBYHOST_DATA_KEY_LEGACY": "0"}
	return func(k string) string { return env[k] }
}

// testPool connects to UBYHOST_TEST_DATABASE_URL and skips when the migrated schema is missing.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	url := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if url == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, url)
	if err != nil {
		t.Fatalf("pool: %v", err)
	}
	t.Cleanup(pool.Close)
	var schemaOK int
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'apartment' AND column_name = 'stay_fee_guest_rails'`).Scan(&schemaOK); err != nil || schemaOK == 0 {
		t.Skip("needs migrated Postgres schema")
	}
	return pool
}

const seedStamp = "2026-06-02T12:00:00+00:00"

func seedExec(t *testing.T, pool *pgxpool.Pool, q string, args ...any) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), q, args...); err != nil {
		t.Fatalf("seed: %v", err)
	}
}

// cleanupStay removes everything seedStay creates for one reservation, child rows first.
func cleanupStay(t *testing.T, pool *pgxpool.Pool, resID int64) {
	t.Helper()
	apt := 900000 + resID
	for _, q := range []string{
		`DELETE FROM guest WHERE reservation_id = $1`,
		`DELETE FROM reservation_claim WHERE reservation_id = $1`,
		`DELETE FROM reservation WHERE id = $1`,
	} {
		seedExec(t, pool, q, resID)
	}
	seedExec(t, pool, `DELETE FROM stay_fee_rate WHERE apartment_id = $1`, apt)
	seedExec(t, pool, `DELETE FROM apartment WHERE id = $1`, apt)
	seedExec(t, pool, `DELETE FROM legal_entity WHERE id = $1`, apt)
	seedExec(t, pool, `DELETE FROM user_account WHERE id = $1`, apt)
}

// seedStay writes one reservation with the given claim and guests. Encrypted
// document numbers are stored as tokens only, as the app stores them.
func seedStay(t *testing.T, pool *pgxpool.Pool, c goldenCase) {
	t.Helper()
	apt := 900000 + c.ReservationID
	tok := fmt.Sprintf("maildetails-%d", c.ReservationID)
	cleanupStay(t, pool, c.ReservationID)
	t.Cleanup(func() { cleanupStay(t, pool, c.ReservationID) })

	seedExec(t, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at)
		VALUES ($1, $2, 'x', 'host', 1, $3)`, apt, tok+"-owner", seedStamp)
	seedExec(t, pool, `INSERT INTO legal_entity (id, name, iban, created_at, owner_user_id)
		VALUES ($1, 'Maildetails Operator', 'CZ6508000000192000145399', $2, $1)`, apt, seedStamp)
	seedExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, permalink_token, active, created_at, city_en,
		legal_entity_id, stay_fee_collect, stay_fee_rate_czk, stay_fee_guest_rails)
		VALUES ($1, $1, 'Flat', $2, 1, $3, 'Prague', $1, 1, 100, 'iban')`, apt, tok, seedStamp)
	seedExec(t, pool, `INSERT INTO reservation (id, uid, apartment_id, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'ical', '2026-06-01', '2026-06-05', $4, $4)`, c.ReservationID, tok+"-res", apt, seedStamp)
	if c.ClaimedAt != nil {
		seedExec(t, pool, `INSERT INTO reservation_claim (reservation_id, state, email, lang, token_version, declared_guests, claimed_at, created_at, updated_at)
			VALUES ($1, 'claimed', 'guest@example.test', 'en', 1, $2, $3, $4, $4)`,
			c.ReservationID, len(c.Guests), *c.ClaimedAt, seedStamp)
	}
	for _, g := range c.Guests {
		plain := g.DocNumber
		if g.DocNumberEnc != "" {
			plain = ""
		}
		seedExec(t, pool, `INSERT INTO guest (id, reservation_id, created_at, updated_at, first_name, surname, birth_date, nationality,
			doc_number, doc_number_enc, res_street, res_city, res_country, purpose, is_lead, entered_by)
			VALUES ($1, $2, $3, $3, $4, $5, '01011990', 'CZE', $6, NULLIF($7, ''), 'Street 1', 'City', 'CZE', '03', $8, $9)`,
			g.ID, g.ReservationID, g.CreatedAt, g.FirstName, g.Surname, plain, g.DocNumberEnc, g.IsLead, g.EnteredBy)
	}
}

func TestReceiptDetailsMatchesPythonGolden(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	r := maildetails.Renderer{Getenv: goldenEnv(g.FernetKey)}
	ctx := context.Background()
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			if c.Seeded {
				seedStay(t, pool, c)
			}
			text, err := r.ReceiptDetails(ctx, pool, c.ReservationID, c.Lang, false)
			if err != nil {
				t.Fatalf("text: %v", err)
			}
			if text != c.ExpectText {
				t.Fatalf("text mismatch\n got: %q\nwant: %q", text, c.ExpectText)
			}
			html, err := r.ReceiptDetails(ctx, pool, c.ReservationID, c.Lang, true)
			if err != nil {
				t.Fatalf("html: %v", err)
			}
			if html != c.ExpectHTML {
				t.Fatalf("html mismatch\n got: %q\nwant: %q", html, c.ExpectHTML)
			}
		})
	}
}

func TestReceiptUndecryptableTokenIsErrDecryption(t *testing.T) {
	g := loadGolden(t)
	pool := testPool(t)
	const resID = 120
	claimed := "2026-11-13T09:00:00Z"
	seedStay(t, pool, goldenCase{
		Name: "bad_token", ReservationID: resID, Lang: "en", ClaimedAt: &claimed, Seeded: true,
		Guests: []goldenGuest{{ID: resID * 10, ReservationID: resID, FirstName: "Hal", Surname: "Bad",
			DocNumberEnc: "not-a-fernet-token", EnteredBy: "guest", CreatedAt: "2026-11-13T10:00:00Z", IsLead: 1}},
	})
	r := maildetails.Renderer{Getenv: goldenEnv(g.FernetKey)}
	_, err := r.ReceiptDetails(context.Background(), pool, resID, "en", false)
	if !errors.Is(err, mail.ErrDecryption) {
		t.Fatalf("want ErrDecryption, got %v", err)
	}
}
