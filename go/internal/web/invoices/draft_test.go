package invoices

import (
	"encoding/json"
	"net/url"
	"os"
	"reflect"
	"testing"
	"time"
)

// goldenDraft is one case of testdata/draft_golden.json, written by
// App/scripts/invoices_golden.py from the real App/app/invoices.py.
type goldenDraft struct {
	Name   string          `json:"name"`
	Entity map[string]any  `json:"entity"`
	Stay   goldenStay      `json:"stay"`
	Today  string          `json:"today"`
	Form   [][2]string     `json:"form"`
	Draft  goldenDraftBody `json:"draft"`
	Issues [][2]string     `json:"issues"`
}

type goldenStay struct {
	Reservation map[string]any `json:"reservation"`
	Property    string         `json:"property_name"`
	EntityID    *int64         `json:"entity_id"`
}

type goldenDraftBody struct {
	Kind          string            `json:"kind"`
	Lang          string            `json:"lang"`
	VATStatus     string            `json:"vat_status"`
	IssueDate     string            `json:"issue_date"`
	DUZP          *string           `json:"duzp"`
	DueDate       *string           `json:"due_date"`
	PaidOn        *string           `json:"paid_on"`
	PaidVia       *string           `json:"paid_via"`
	Note          string            `json:"note"`
	TotalHaler    int64             `json:"total_haler"`
	TotalBase     *int64            `json:"total_base_haler"`
	TotalVAT      *int64            `json:"total_vat_haler"`
	StayLabel     string            `json:"stay_label"`
	StayFrom      string            `json:"stay_from"`
	StayTo        string            `json:"stay_to"`
	ReservationID int64             `json:"reservation_id"`
	ApartmentID   int64             `json:"apartment_id"`
	Seller        map[string]string `json:"seller"`
	Buyer         map[string]string `json:"buyer"`
	Items         []struct {
		Kind         string `json:"kind"`
		ExtraKind    string `json:"extra_kind"`
		Description  string `json:"description"`
		Quantity     int64  `json:"quantity"`
		Unit         string `json:"unit"`
		VATRate      *int64 `json:"vat_rate"`
		Base         *int64 `json:"base_haler"`
		VAT          *int64 `json:"vat_haler"`
		Gross        int64  `json:"gross_haler"`
		PriceInvalid bool   `json:"price_invalid"`
	} `json:"items"`
}

type goldenFile struct {
	Cases        []goldenDraft `json:"cases"`
	StayProblems []struct {
		Name        string         `json:"name"`
		Reservation map[string]any `json:"reservation"`
		Today       string         `json:"today"`
		Key         *string        `json:"key"`
	} `json:"stay_problems"`
}

func loadDraftGolden(t *testing.T) goldenFile {
	t.Helper()
	raw, err := os.ReadFile("testdata/draft_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g goldenFile
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func str(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

func num(m map[string]any, key string) *int64 {
	if v, ok := m[key].(float64); ok {
		n := int64(v)
		return &n
	}
	return nil
}

func entityOf(m map[string]any) entity {
	e := entity{
		ID: *num(m, "id"), Name: str(m, "name"), Seat: str(m, "seat"), ICO: str(m, "ico"), DIC: str(m, "dic"),
		ContactEmail: str(m, "contact_email"), ContactPhone: str(m, "contact_phone"),
		BankAccount: str(m, "bank_account"), IBAN: str(m, "iban"), BIC: str(m, "bic"),
		VATStatus: str(m, "vat_status"), RegistryEntry: str(m, "registry_entry"),
		InvoicePrefix: str(m, "invoice_prefix"), NextNumber: num(m, "invoice_next_number"),
		NextNumberYear: num(m, "invoice_next_number_year"), DueDays: *num(m, "invoice_due_days"),
	}
	if e.VATStatus == "" {
		e.VATStatus = "non_payer"
	}
	return e
}

func stayOf(g goldenStay) *stay {
	r := g.Reservation
	return &stay{
		ReservationID: *num(r, "id"), ApartmentID: *num(r, "apartment_id"),
		DateFrom: str(r, "date_from"), DateTo: str(r, "date_to"), Status: str(r, "status"),
		Source: str(r, "source"), GuestEmail: str(r, "guest_email"), PropertyName: g.Property, EntityID: g.EntityID,
	}
}

func day(t *testing.T, s string) time.Time {
	t.Helper()
	d, err := time.Parse("2006-01-02", s)
	if err != nil {
		t.Fatal(err)
	}
	return d
}

func orEmpty(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

func eqPtr(a, b *int64) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

// TestBuildDraftMatchesPython builds every golden case in Go and compares
// every amount, text, flag and issue key with the Python draft.
func TestBuildDraftMatchesPython(t *testing.T) {
	g := loadDraftGolden(t)
	if len(g.Cases) < 40 {
		t.Fatalf("golden has %d cases", len(g.Cases))
	}
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			form := url.Values{}
			for _, p := range c.Form {
				form.Add(p[0], p[1])
			}
			st := stayOf(c.Stay)
			d := buildDraft(entityOf(c.Entity), form, day(t, c.Today), st)
			w := c.Draft
			if d.Kind != w.Kind || d.Lang != w.Lang || d.VATStatus != w.VATStatus || d.IssueDate != w.IssueDate {
				t.Fatalf("header: got %q %q %q %q, want %q %q %q %q", d.Kind, d.Lang, d.VATStatus, d.IssueDate, w.Kind, w.Lang, w.VATStatus, w.IssueDate)
			}
			for _, f := range []struct {
				name      string
				got, want string
			}{
				{"duzp", d.DUZP, orEmpty(w.DUZP)}, {"due_date", d.DueDate, orEmpty(w.DueDate)},
				{"paid_on", d.PaidOn, orEmpty(w.PaidOn)}, {"paid_via", d.PaidVia, orEmpty(w.PaidVia)},
				{"note", d.Note, w.Note}, {"stay_label", d.StayLabel, w.StayLabel},
				{"stay_from", d.StayFrom, w.StayFrom}, {"stay_to", d.StayTo, w.StayTo},
			} {
				if f.got != f.want {
					t.Errorf("%s: got %q, want %q", f.name, f.got, f.want)
				}
			}
			if d.TotalHaler != w.TotalHaler || !eqPtr(d.TotalBase, w.TotalBase) || !eqPtr(d.TotalVAT, w.TotalVAT) {
				t.Errorf("totals: got %d %v %v, want %d %v %v", d.TotalHaler, d.TotalBase, d.TotalVAT, w.TotalHaler, w.TotalBase, w.TotalVAT)
			}
			if *d.ReservationID != w.ReservationID || *d.ApartmentID != w.ApartmentID {
				t.Errorf("ids: got %d %d", *d.ReservationID, *d.ApartmentID)
			}
			gotSeller := map[string]string{"name": d.Seller.Name, "seat": d.Seller.Seat, "ico": d.Seller.ICO, "dic": d.Seller.DIC,
				"registry": d.Seller.Registry, "bank_account": d.Seller.BankAccount, "iban": d.Seller.IBAN, "bic": d.Seller.BIC,
				"email": d.Seller.Email, "phone": d.Seller.Phone}
			if !reflect.DeepEqual(gotSeller, w.Seller) {
				t.Errorf("seller: got %v, want %v", gotSeller, w.Seller)
			}
			gotBuyer := map[string]string{"name": d.Buyer.Name, "street": d.Buyer.Street, "city": d.Buyer.City, "zip": d.Buyer.Zip,
				"country": d.Buyer.Country, "ico": d.Buyer.ICO, "dic": d.Buyer.DIC, "email": d.Buyer.Email}
			if !reflect.DeepEqual(gotBuyer, w.Buyer) {
				t.Errorf("buyer: got %v, want %v", gotBuyer, w.Buyer)
			}
			if len(d.Items) != len(w.Items) {
				t.Fatalf("items: got %d, want %d", len(d.Items), len(w.Items))
			}
			for i, it := range d.Items {
				wi := w.Items[i]
				if it.Kind != wi.Kind || it.ExtraKind != wi.ExtraKind || it.Description != wi.Description ||
					it.Quantity != wi.Quantity || it.Unit != wi.Unit || it.Gross != wi.Gross ||
					it.PriceInvalid != wi.PriceInvalid || !eqPtr(it.VATRate, wi.VATRate) ||
					!eqPtr(it.Base, wi.Base) || !eqPtr(it.VAT, wi.VAT) {
					t.Errorf("item %d: got %+v, want %+v", i, it, wi)
				}
			}
			var got [][2]string
			for _, is := range validateForIssue(d) {
				got = append(got, [2]string{is.Field, is.Message})
			}
			if !reflect.DeepEqual(got, c.Issues) && !(len(got) == 0 && len(c.Issues) == 0) {
				t.Errorf("issues: got %v, want %v", got, c.Issues)
			}
		})
	}
}

func TestStayProblemMatchesPython(t *testing.T) {
	g := loadDraftGolden(t)
	for _, c := range g.StayProblems {
		t.Run(c.Name, func(t *testing.T) {
			st := &stay{DateFrom: str(c.Reservation, "date_from"), DateTo: str(c.Reservation, "date_to"),
				Status: str(c.Reservation, "status"), Source: str(c.Reservation, "source")}
			if got := stayProblem(st, day(t, c.Today)); got != orEmpty(c.Key) {
				t.Errorf("got %q, want %q", got, orEmpty(c.Key))
			}
		})
	}
	if stayProblem(nil, time.Now()) != "invoice.err.no_stay" {
		t.Error("nil stay")
	}
}
