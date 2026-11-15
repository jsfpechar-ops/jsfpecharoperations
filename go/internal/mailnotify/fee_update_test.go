package mailnotify

import (
	"encoding/json"
	"os"
	"testing"
)

type feeGolden struct {
	PublicBaseURL string `json:"public_base_url"`
	Cases         []struct {
		Name           string         `json:"name"`
		GuestLanguages string         `json:"guest_languages"`
		Input          FeeUpdateInput `json:"input"`
		Output         struct {
			Subject string `json:"subject"`
			Text    string `json:"text"`
			HTML    string `json:"html"`
		} `json:"output"`
	} `json:"cases"`
}

// TestFeeUpdateGoldenByteForByte replays testdata/fee_update_golden.json, which
// App/scripts/go_mailnotify_fee_golden.py wrote from the real build_fee_update.
func TestFeeUpdateGoldenByteForByte(t *testing.T) {
	raw, err := os.ReadFile("testdata/fee_update_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g feeGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) == 0 {
		t.Fatal("golden has no cases")
	}
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			SetGuestLanguages(c.GuestLanguages)
			defer SetGuestLanguages("en,cs")
			got := BuildFeeUpdate(g.PublicBaseURL, c.Input)
			if got.Subject != c.Output.Subject {
				t.Errorf("subject\n got: %q\nwant: %q", got.Subject, c.Output.Subject)
			}
			if got.Text != c.Output.Text {
				t.Errorf("text differs\n got: %q\nwant: %q", got.Text, c.Output.Text)
			}
			if got.HTML != c.Output.HTML {
				t.Errorf("html differs (len got %d, want %d)", len(got.HTML), len(c.Output.HTML))
			}
		})
	}
}
