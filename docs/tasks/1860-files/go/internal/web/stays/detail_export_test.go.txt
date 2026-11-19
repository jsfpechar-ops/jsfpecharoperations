package stays

import (
	"reflect"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

func detailFixture() (Reservation, []progGuest) {
	two := int64(2)
	res := Reservation{ID: 7, ApartmentID: 3, DateFrom: "2026-12-01", DateTo: "2026-12-04",
		Status: "active", AutomationMode: "manual", Declared: &two}
	guests := []progGuest{
		{id: 1, nationality: "DEU", submitState: "error", firstName: "A", surname: "B", isLead: true,
			row: validation.GuestRow{FirstName: "A", Surname: "B", Nationality: "DEU", StayFrom: "2026-12-01", StayTo: "2026-12-04"}},
		{id: 2, nationality: "CZE", firstName: "C", surname: "D",
			row: validation.GuestRow{FirstName: "C", Surname: "D", Nationality: "CZE"}},
	}
	return res, guests
}

func TestStayDetailEqualsListHelpers(t *testing.T) {
	res, guests := detailFixture()
	at := time.Date(2026, 11, 19, 10, 0, 0, 0, time.UTC)
	got := stayDetail(res, guests, at)
	st := listStay{id: res.ID, dateFrom: res.DateFrom, dateTo: res.DateTo,
		declared: res.Declared, override: res.Override, reduced: res.Reduced}
	today := time.Date(2026, 11, 19, 0, 0, 0, 0, time.UTC)
	if want := buildProgress(st, guests, at); !reflect.DeepEqual(got.Progress, want) {
		t.Fatalf("progress differs from buildProgress")
	}
	if want := sendControls(res, res.AutomationMode, listProgress(st, guests, today), guests); got.Controls != want {
		t.Fatalf("controls differ from sendControls")
	}
	if len(got.Guests) != 2 || got.Guests[0].ID != 1 || !got.Guests[0].IsLead || got.Guests[1].Row.Nationality != "CZE" {
		t.Fatalf("guests not in progress order")
	}
}

func TestSendHint(t *testing.T) {
	one := 1
	foreignSigned := progGuest{nationality: "DEU", row: validation.GuestRow{Nationality: "DEU", SignaturePNG: "imported"}}
	foreignUnsigned := progGuest{nationality: "DEU", row: validation.GuestRow{Nationality: "DEU", BirthDate: "1980-01-01"}}
	czech := progGuest{nationality: "CZE", row: validation.GuestRow{Nationality: "CZE"}}
	base := Reservation{DateFrom: "2026-12-01", AutomationMode: "manual"}
	demo := base
	demo.Source = "demo"
	preview := base
	preview.InternalName = "Flat (demo)"
	immediate := base
	immediate.AutomationMode = "immediate"
	cases := []struct {
		name    string
		res     Reservation
		p       listProg
		guests  []progGuest
		missing *int
		key     string
		pending int
	}{
		{"demo stay", demo, listProg{status: "ready"}, nil, nil, "hint.demo_stay", 0},
		{"demo property", preview, listProg{status: "ready"}, nil, nil, "hint.demo_preview", 0},
		{"failed", base, listProg{status: "failed", reportable: []progGuest{foreignSigned}}, []progGuest{foreignSigned}, nil, "hint.failed", 1},
		{"immediate", immediate, listProg{status: "ready"}, []progGuest{czech}, nil, "hint.auto_immediate", 0},
		{"all reported", base, listProg{status: "reported"}, []progGuest{czech}, nil, "hint.all_reported", 0},
		{"nothing duty", base, listProg{status: "not_required"}, []progGuest{czech}, nil, "hint.nothing_duty", 0},
		{"no guests", base, listProg{status: "awaiting_guest"}, nil, nil, "hint.awaiting_guest", 0},
		{"missing guests", base, listProg{status: "incomplete"}, []progGuest{czech}, &one, "hint.missing_guests", 0},
		{"need signature", base, listProg{status: "incomplete"}, []progGuest{foreignUnsigned}, nil, "hint.need_signature", 0},
		{"nothing left", base, listProg{status: "incomplete"}, []progGuest{czech}, nil, "hint.nothing_left", 0},
		{"not ready", base, listProg{status: "incomplete", reportable: []progGuest{foreignSigned}}, []progGuest{foreignSigned}, nil, "hint.not_ready", 1},
		{"id optional", base, listProg{status: "awaiting_verification", reportable: []progGuest{foreignSigned}}, []progGuest{foreignSigned}, nil, "hint.ready_id_optional", 1},
		{"ready", base, listProg{status: "ready", reportable: []progGuest{foreignSigned}}, []progGuest{foreignSigned}, nil, "hint.ready_to_send", 1},
	}
	for _, c := range cases {
		key, pending := sendHint(c.res, c.p, c.guests, c.missing)
		if key != c.key || pending != c.pending {
			t.Errorf("%s: got %s/%d, want %s/%d", c.name, key, pending, c.key, c.pending)
		}
	}
}
