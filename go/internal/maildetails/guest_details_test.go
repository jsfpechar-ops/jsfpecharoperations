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

type gdGoldenGuest struct {
	ID            int64   `json:"id"`
	ReservationID int64   `json:"reservation_id"`
	FirstName     string  `json:"first_name"`
	Surname       string  `json:"surname"`
	Nationality   string  `json:"nationality"`
	SubmitState   string  `json:"submit_state"`
	DocType       string  `json:"doc_type"`
	DocNumber     string  `json:"doc_number"`
	DocNumberEnc  string  `json:"doc_number_enc"`
	BirthDate     string  `json:"birth_date"`
	BirthDateEnc  string  `json:"birth_date_enc"`
	ResStreet     string  `json:"res_street"`
	ResStreetEnc  string  `json:"res_street_enc"`
	ResCity       string  `json:"res_city"`
	ResCityEnc    string  `json:"res_city_enc"`
	ResCountry    string  `json:"res_country"`
	IsLead        int     `json:"is_lead"`
	ArchivedAt    *string `json:"archived_at"`
}

type gdGoldenCase struct {
	Name             string          `json:"name"`
	ReservationID    int64           `json:"reservation_id"`
	Lang             string          `json:"lang"`
	Seeded           bool            `json:"seeded"`
	GuestDetailsMail int             `json:"guest_details_mail"`
	DPAVersions      []string        `json:"dpa_versions"`
	Guests           []gdGoldenGuest `json:"guests"`
	ExpectText       string          `json:"expect_text"`
	ExpectHTML       string          `json:"expect_html"`
}

type gdGolden struct {
	FernetKey string         `json:"fernet_key"`
	Cases     []gdGoldenCase `json:"cases"`
}

func loadGuestDetailsGolden(t *testing.T) gdGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/guest_details_golden.json")
	if err != nil {
		t.Fatalf("read guest details golden: %v", err)
	}
	var g gdGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatalf("parse guest details golden: %v", err)
	}
	return g
}

func cleanupGuestDetailsStay(t *testing.T, pool *pgxpool.Pool, resID int64) {
	t.Helper()
	apt := 900000 + resID
	for _, q := range []string{
		`DELETE FROM guest WHERE reservation_id = $1`,
		`DELETE FROM reservation_claim WHERE reservation_id = $1`,
		`DELETE FROM reservation WHERE id = $1`,
	} {
		seedExec(t, pool, q, resID)
	}
	seedExec(t, pool, `DELETE FROM legal_acceptance WHERE user_account_id = $1`, apt)
	seedExec(t, pool, `DELETE FROM stay_fee_rate WHERE apartment_id = $1`, apt)
	seedExec(t, pool, `DELETE FROM apartment WHERE id = $1`, apt)
	seedExec(t, pool, `DELETE FROM legal_entity WHERE id = $1`, apt)
	seedExec(t, pool, `DELETE FROM user_account WHERE id = $1`, apt)
}

func seedGuestDetailsStay(t *testing.T, pool *pgxpool.Pool, c gdGoldenCase) {
	t.Helper()
	apt := 900000 + c.ReservationID
	tok := fmt.Sprintf("maildetails-gd-%d", c.ReservationID)
	cleanupGuestDetailsStay(t, pool, c.ReservationID)
	t.Cleanup(func() { cleanupGuestDetailsStay(t, pool, c.ReservationID) })

	seedExec(t, pool, `INSERT INTO user_account (id, username, password_hash, role, active, created_at, guest_details_mail)
		VALUES ($1, $2, 'x', 'host', 1, $3, $4)`, apt, tok+"-owner", seedStamp, c.GuestDetailsMail)
	for _, ver := range c.DPAVersions {
		seedExec(t, pool, `INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method)
			VALUES ($1, 'dpa', $2, $3, 'clickwrap')`, apt, ver, seedStamp)
	}
	seedExec(t, pool, `INSERT INTO legal_entity (id, name, iban, created_at, owner_user_id)
		VALUES ($1, 'Maildetails Operator', 'CZ6508000000192000145399', $2, $1)`, apt, seedStamp)
	seedExec(t, pool, `INSERT INTO apartment (id, owner_user_id, internal_name, permalink_token, active, created_at, city_en,
		legal_entity_id, stay_fee_collect, stay_fee_rate_czk, stay_fee_guest_rails)
		VALUES ($1, $1, 'Flat', $2, 1, $3, 'Prague', $1, 1, 100, 'iban')`, apt, tok, seedStamp)
	seedExec(t, pool, `INSERT INTO reservation (id, uid, apartment_id, status, source, date_from, date_to, created_at, updated_at)
		VALUES ($1, $2, $3, 'active', 'ical', '2026-06-01', '2026-06-05', $4, $4)`, c.ReservationID, tok+"-res", apt, seedStamp)

	for _, g := range c.Guests {
		plainDoc, plainBirth, plainStreet, plainCity := g.DocNumber, g.BirthDate, g.ResStreet, g.ResCity
		if g.DocNumberEnc != "" {
			plainDoc = ""
		}
		if g.BirthDateEnc != "" {
			plainBirth = ""
		}
		if g.ResStreetEnc != "" {
			plainStreet = ""
		}
		if g.ResCityEnc != "" {
			plainCity = ""
		}
		seedExec(t, pool, `INSERT INTO guest (
			id, reservation_id, created_at, updated_at, first_name, surname, nationality, submit_state,
			doc_type, doc_number, doc_number_enc, birth_date, birth_date_enc,
			res_street, res_street_enc, res_city, res_city_enc, res_country,
			purpose, is_lead, archived_at)
			VALUES ($1, $2, $3, $3, $4, $5, $6, $7, $8, $9, NULLIF($10, ''), $11, NULLIF($12, ''),
			        $13, NULLIF($14, ''), $15, NULLIF($16, ''), $17, '03', $18, $19)`,
			g.ID, g.ReservationID, seedStamp, g.FirstName, g.Surname, g.Nationality, g.SubmitState,
			g.DocType, plainDoc, g.DocNumberEnc, plainBirth, g.BirthDateEnc,
			plainStreet, g.ResStreetEnc, plainCity, g.ResCityEnc, g.ResCountry,
			g.IsLead, g.ArchivedAt)
	}
}

func TestGuestDetailsMatchesPythonGolden(t *testing.T) {
	g := loadGuestDetailsGolden(t)
	pool := testPool(t)
	r := maildetails.Renderer{Getenv: goldenEnv(g.FernetKey)}

	for _, c := range g.Cases {
		c := c
		t.Run(c.Name, func(t *testing.T) {
			if c.Seeded {
				seedGuestDetailsStay(t, pool, c)
			} else {
				cleanupGuestDetailsStay(t, pool, c.ReservationID)
			}
			gotText, err := r.GuestDetails(context.Background(), pool, c.ReservationID, c.Lang, false)
			if err != nil {
				t.Fatalf("text: %v", err)
			}
			if gotText != c.ExpectText {
				t.Errorf("text mismatch:\n got: %q\nwant: %q", gotText, c.ExpectText)
			}
			gotHTML, err := r.GuestDetails(context.Background(), pool, c.ReservationID, c.Lang, true)
			if err != nil {
				t.Fatalf("html: %v", err)
			}
			if gotHTML != c.ExpectHTML {
				t.Errorf("html mismatch:\n got: %q\nwant: %q", gotHTML, c.ExpectHTML)
			}
		})
	}
}

func TestGuestDetailsDecryptionError(t *testing.T) {
	g := loadGuestDetailsGolden(t)
	pool := testPool(t)
	var target gdGoldenCase
	for _, c := range g.Cases {
		if c.Name == "full_on_dpa_1_8_en" {
			target = c
			break
		}
	}
	seedGuestDetailsStay(t, pool, target)
	bad := maildetails.Renderer{Getenv: func(string) string { return "" }}
	_, err := bad.GuestDetails(context.Background(), pool, target.ReservationID, "en", false)
	if !errors.Is(err, mail.ErrDecryption) {
		t.Fatalf("want ErrDecryption, got %v", err)
	}
}
