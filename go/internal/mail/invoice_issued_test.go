package mail

import (
	"encoding/json"
	"os"
	"testing"
)

type invoiceIssuedGolden struct {
	PublicBase string `json:"public_base_url"`
	Cases      []struct {
		Name  string `json:"name"`
		Input struct {
			Lang         string       `json:"lang"`
			Issuer       string       `json:"issuer"`
			Number       string       `json:"number"`
			Total        string       `json:"total"`
			DownloadURL  string       `json:"download_url"`
			Host         *HostDetails `json:"host"`
			StayProperty string       `json:"stay_property"`
		} `json:"input"`
		Subject string `json:"subject"`
		Text    string `json:"text"`
		HTML    string `json:"html"`
	} `json:"cases"`
}

func TestBuildInvoiceIssuedGolden(t *testing.T) {
	SetGuestLanguages("en,cs,de,es,fr")
	raw, err := os.ReadFile("testdata/invoice_issued_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g invoiceIssuedGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			host := HostDetails{}
			if c.Input.Host != nil {
				host = *c.Input.Host
			}
			got := BuildInvoiceIssued(g.PublicBase, c.Input.Lang, c.Input.Issuer, c.Input.Number,
				c.Input.Total, c.Input.DownloadURL, host, c.Input.StayProperty)
			if got.Subject != c.Subject || got.Text != c.Text || got.HTML != c.HTML {
				if got.Subject != c.Subject {
					t.Errorf("subject\n--- got\n%s\n--- want\n%s", got.Subject, c.Subject)
				}
				if got.Text != c.Text {
					t.Errorf("text\n--- got\n%s\n--- want\n%s", got.Text, c.Text)
				}
				if got.HTML != c.HTML {
					t.Errorf("html length got %d want %d", len(got.HTML), len(c.HTML))
				}
			}
		})
	}
}
