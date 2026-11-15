package stayfee

import (
	"encoding/json"
	"os"
	"reflect"
	"testing"
)

// cfGolden mirrors testdata/completion_fee_golden.json, written by
// App/scripts/go_mailnotify_fee_golden.py from the real claim._completion_fee.
type cfGolden struct {
	Cases []struct {
		Name      string `json:"name"`
		GuestPay  bool   `json:"guest_pay"`
		Apartment struct {
			ID            int64  `json:"id"`
			LegalEntityID int64  `json:"legal_entity_id"`
			InternalName  string `json:"internal_name"`
			RateCZK       int    `json:"stay_fee_rate_czk"`
			Collect       int    `json:"stay_fee_collect"`
			GuestRails    string `json:"stay_fee_guest_rails"`
			DefaultRail   string `json:"stay_fee_guest_default_rail"`
			RevolutLink   string `json:"stay_fee_guest_revolut_link"`
			CashNote      string `json:"stay_fee_guest_cash_note"`
			ScopeRule     string `json:"stay_fee_scope_rule"`
			ScopeRef      string `json:"stay_fee_scope_reference"`
			Cadence       string `json:"stay_fee_cadence"`
			VS            string `json:"stay_fee_vs"`
			AddrObec      string `json:"addr_obec"`
			CityEN        string `json:"city_en"`
			AddrStreet    string `json:"addr_street"`
			AddrHouseNo   string `json:"addr_house_no"`
			AddrOrientNo  string `json:"addr_orient_no"`
			AddrZip       string `json:"addr_zip"`
		} `json:"apartment"`
		Entity *struct {
			Name        string `json:"name"`
			IBAN        string `json:"iban"`
			BankAccount string `json:"bank_account"`
		} `json:"entity"`
		Rates []struct {
			EffectiveFrom string `json:"effective_from"`
			RateCZK       int    `json:"rate_czk"`
		} `json:"rates"`
		Reservation struct {
			ID int64 `json:"id"`
		} `json:"reservation"`
		Nationalities []string `json:"nationalities"`
		Guests        []struct {
			ID              int64  `json:"id"`
			ReservationID   int64  `json:"reservation_id"`
			BirthDate       string `json:"birth_date"`
			Nationality     string `json:"nationality"`
			DocType         string `json:"doc_type"`
			DocNumber       string `json:"doc_number"`
			ResStreet       string `json:"res_street"`
			ResCity         string `json:"res_city"`
			ResCountry      string `json:"res_country"`
			StayFrom        string `json:"stay_from"`
			StayTo          string `json:"stay_to"`
			FeeHostDecision string `json:"fee_host_decision"`
			FeeHostReason   string `json:"fee_host_reason"`
			SignaturePNG    string `json:"signature_png"`
			RestrictedAt    string `json:"restricted_at"`
			ResFrom         string `json:"res_from"`
			ResTo           string `json:"res_to"`
		} `json:"guests"`
		Output *CompletionFee `json:"output"`
	} `json:"cases"`
}

// TestCompletionFeeGoldenFields replays every case of completion_fee_golden.json
// through the pure CompletionFeeOf and compares the whole fee block.
func TestCompletionFeeGoldenFields(t *testing.T) {
	raw, err := os.ReadFile("testdata/completion_fee_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g cfGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) == 0 {
		t.Fatal("golden has no cases")
	}
	withFee := 0
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			a := c.Apartment
			ap := &Apartment{
				ID: a.ID, LegalEntityID: a.LegalEntityID, InternalName: a.InternalName,
				StayFeeRateCZK: a.RateCZK, StayFeeCadence: a.Cadence, StayFeeVS: a.VS,
				ScopeRule: a.ScopeRule, ScopeReference: a.ScopeRef, Collect: a.Collect != 0,
				GuestRails: a.GuestRails, GuestDefaultRail: a.DefaultRail, RevolutLink: a.RevolutLink,
				CashNote: a.CashNote, AddrObec: a.AddrObec, CityEN: a.CityEN, AddrStreet: a.AddrStreet,
				AddrHouseNo: a.AddrHouseNo, AddrOrientNo: a.AddrOrientNo, AddrZip: a.AddrZip,
			}
			var entity *Entity
			if c.Entity != nil {
				entity = &Entity{Name: c.Entity.Name, IBAN: c.Entity.IBAN, BankAccount: c.Entity.BankAccount}
			}
			var rates []RateRow
			for _, r := range c.Rates {
				rates = append(rates, RateRow{EffectiveFrom: r.EffectiveFrom, RateCZK: r.RateCZK})
			}
			var guests []GuestRow
			for _, g := range c.Guests {
				guests = append(guests, GuestRow{
					ID: g.ID, ReservationID: g.ReservationID, BirthDate: g.BirthDate,
					Nationality: g.Nationality, DocType: g.DocType, DocNumber: g.DocNumber,
					ResStreet: g.ResStreet, ResCity: g.ResCity, ResCountry: g.ResCountry,
					StayFrom: g.StayFrom, StayTo: g.StayTo, FeeHostDecision: g.FeeHostDecision,
					FeeHostReason: g.FeeHostReason, SignaturePNG: g.SignaturePNG,
					Restricted: g.RestrictedAt != "", ResFrom: g.ResFrom, ResTo: g.ResTo,
				})
			}
			got, err := CompletionFeeOf(CompletionInput{
				Apartment: ap, Entity: entity, Rates: rates, Guests: guests,
				Nationalities: c.Nationalities, ReservationID: c.Reservation.ID,
				GuestPay: c.GuestPay, Today: Day(2026, 11, 15),
			})
			if err != nil {
				t.Fatal(err)
			}
			if c.Output == nil {
				if got != nil {
					t.Fatalf("want no fee, got %+v", *got)
				}
				return
			}
			withFee++
			if got == nil {
				t.Fatalf("want fee %+v, got none", *c.Output)
			}
			if !reflect.DeepEqual(*got, *c.Output) {
				t.Errorf("fee differs\n got: %+v\nwant: %+v", *got, *c.Output)
			}
		})
	}
	if withFee == 0 {
		t.Fatal("no golden case carries a fee; the replay proves nothing")
	}
}
