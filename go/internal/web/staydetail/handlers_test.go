package staydetail

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stays"
)

// fixedView is an active stay 7 with three expected guests, one registered.
func fixedView() View {
	expected := 3
	return View{
		Reservation: Stay{Reservation: stays.Reservation{
			ID: 7, ApartmentID: 3, DateFrom: "2026-11-20", DateTo: "2026-11-23",
			Status: "active", Source: "manual", InternalName: "Flat A",
			PermalinkToken: "tok", AutomationMode: "manual",
		}},
		Progress: stays.Progress{Filled: 1, Expected: &expected, Status: "incomplete", Guests: make([]stays.Guest, 1)},
		GuestRows: []GuestRow{{Guest: Guest{StayGuest: stays.StayGuest{
			ID: 11, SubmitState: "pending", IsLead: true,
			Row: validation.GuestRow{FirstName: "Test", Surname: "Guest"},
		}}}},
		ReturnTo:  "/reservations",
		GuestLink: "https://example.test/l/key/7",
		StayClaim: StayClaim{State: "unclaimed"},
	}
}

func renderStay(t *testing.T, v View) string {
	t.Helper()
	w := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/reservations/7?lang=en", nil)
	env := layout.Env{Getenv: func(string) string { return "golden-secret-key-not-for-real-use" }, Now: time.Date(2026, 11, 19, 12, 0, 0, 0, time.UTC)}
	page := layout.Page{Title: "Flat A · 20.11.2026", Nav: "reservations", BodyKind: "detail", V2: true, HowKey: "stay", BodyAlerts: true}
	if err := layout.RenderPinnedCSRF(w, r, env, nil, page, pages, "stay_detail", pageData{View: v}); err != nil {
		t.Fatal(err)
	}
	return w.Body.String()
}

func TestStayDetailAnchors(t *testing.T) {
	out := renderStay(t, fixedView())
	for _, want := range []string{`id="now"`, `id="guests"`, `id="reports"`, `id="stay-quick-edit"`, `action="/reservations/7"`} {
		if !strings.Contains(out, want) {
			t.Errorf("missing %s", want)
		}
	}
	for _, absent := range []string{`action="/reservations/7/submit"`, `id="file-by-hand"`, `id="filed-by-hand"`} {
		if strings.Contains(out, absent) {
			t.Errorf("unexpected %s", absent)
		}
	}
}

func TestStayDetailSendForm(t *testing.T) {
	v := fixedView()
	v.SendControls.SendEnabled = true
	if out := renderStay(t, v); !strings.Contains(out, `action="/reservations/7/submit"`) {
		t.Error("send enabled: no /submit form")
	}
}

func TestStayDetailFileByHand(t *testing.T) {
	v := fixedView()
	v.HandFiling.Candidates = 2
	if out := renderStay(t, v); !strings.Contains(out, `id="file-by-hand"`) {
		t.Error("active stay with candidates: no file-by-hand panel")
	}
	v.Reservation.Status = "cancelled"
	if out := renderStay(t, v); strings.Contains(out, `id="file-by-hand"`) {
		t.Error("cancelled stay: file-by-hand panel shown")
	}
}

func TestStayDetailFiledByHand(t *testing.T) {
	v := fixedView()
	filed := time.Date(2026, 11, 19, 10, 0, 0, 0, time.UTC)
	v.HandFiling = HandFiling{Count: 1, FiledAt: &filed}
	if out := renderStay(t, v); !strings.Contains(out, `id="filed-by-hand"`) {
		t.Error("hand-filed guest: no filed-by-hand panel")
	}
}

func TestStayDetailTemplateAddsNoScript(t *testing.T) {
	src, err := templateFS.ReadFile("templates/stay_detail.tmpl")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(src), "<script") {
		t.Error("stay_detail.tmpl adds a <script>; only layout may")
	}
}
