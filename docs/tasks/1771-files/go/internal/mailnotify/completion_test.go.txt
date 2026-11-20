package mailnotify

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

// completionGolden is testdata/completion_golden.json (App/scripts/go_mailnotify_completion_golden.py).
type completionGolden struct {
	PublicBaseURL string           `json:"public_base_url"`
	Cases         []completionCase `json:"cases"`
}

type completionCase struct {
	Name   string          `json:"name"`
	Input  completionInput `json:"input"`
	Output struct {
		Subject string `json:"subject"`
		Text    string `json:"text"`
		HTML    string `json:"html"`
		QRSpayd string `json:"qr_spayd"`
	} `json:"output"`
}

type completionInput struct {
	Lang         string              `json:"lang"`
	PropertyName string              `json:"property_name"`
	Dates        string              `json:"dates"`
	Host         *Host               `json:"host"`
	DoorCode     *CompletionDoorCode `json:"door_code"`
	Filled       int                 `json:"filled"`
	Expected     *int                `json:"expected"`
	Checkin      string              `json:"checkin"`
	Checkout     string              `json:"checkout"`
	HostURL      string              `json:"host_url"`
	Fee          *DoorCodeFee        `json:"fee"`
	SentDetails  bool                `json:"sent_details"`
}

// TestBuildCompletionGolden replays every case of the Python build_completion and compares
// subject, text, HTML and SPAYD byte for byte.
func TestBuildCompletionGolden(t *testing.T) {
	SetGuestLanguages("en,cs,de,es,fr,uk")
	defer SetGuestLanguages(strings.Join(catalogue.GuestDefaultLanguages, ","))
	raw, err := os.ReadFile("testdata/completion_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g completionGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) == 0 {
		t.Fatal("no golden cases")
	}
	for _, c := range g.Cases {
		in := c.Input
		got := BuildCompletion(g.PublicBaseURL, CompletionInput{
			Lang:         in.Lang,
			PropertyName: in.PropertyName,
			Dates:        in.Dates,
			Host:         in.Host,
			DoorCode:     in.DoorCode,
			Filled:       in.Filled,
			Expected:     in.Expected,
			Checkin:      in.Checkin,
			Checkout:     in.Checkout,
			HostURL:      in.HostURL,
			Fee:          in.Fee,
			SentDetails:  in.SentDetails,
		})
		if got.Subject != c.Output.Subject {
			t.Errorf("%s: subject\n got %q\nwant %q", c.Name, got.Subject, c.Output.Subject)
		}
		if got.Text != c.Output.Text {
			t.Errorf("%s: text differs", c.Name)
		}
		if got.HTML != c.Output.HTML {
			t.Errorf("%s: html differs", c.Name)
		}
		if got.QRSpayd != c.Output.QRSpayd {
			t.Errorf("%s: qr_spayd\n got %q\nwant %q", c.Name, got.QRSpayd, c.Output.QRSpayd)
		}
	}
}

// TestCompletionFactsAndDates pins the check-in text and the date range of the stay panel.
func TestCompletionFactsAndDates(t *testing.T) {
	SetGuestLanguages("en,cs,de,es,fr,uk")
	defer SetGuestLanguages(strings.Join(catalogue.GuestDefaultLanguages, ","))
	h14, h10 := int64(14), int64(10)
	ci, co := CompletionFacts("cs", "2026-11-16", "2026-11-18", &h14, &h10)
	if ci != "16.11.2026 od 14:00" || co != "18.11.2026 do 10:00" {
		t.Fatalf("facts: %q %q", ci, co)
	}
	if ci, co := CompletionFacts("en", "2026-11-16", "", nil, &h10); ci != "16.11.2026" || co != "" {
		t.Fatalf("facts without hour or date: %q %q", ci, co)
	}
	if got := CompletionDateRange("2026-11-16", "2026-11-18"); got != "16.11.2026 – 18.11.2026" {
		t.Fatalf("range: %q", got)
	}
	if got := CompletionDateRange("2026-11-16", ""); got != "16.11.2026" {
		t.Fatalf("range with no end: %q", got)
	}
}
