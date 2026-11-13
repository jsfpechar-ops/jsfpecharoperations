package stayfeemail

import (
	"encoding/json"
	"os"
	"testing"
)

const stayFeeGolden = "testdata/stay_fee_cases.json"

type stayFeeCase struct {
	Name         string   `json:"name"`
	Lang         string   `json:"lang"`
	Cadence      string   `json:"cadence"`
	Year         int      `json:"year"`
	Month        int      `json:"month"`
	Label        string   `json:"label"`
	Period       string   `json:"period"`
	PropertyName string   `json:"property_name"`
	Amount       string   `json:"amount"`
	TotalCZK     int      `json:"total_czk"`
	Authority    string   `json:"authority"`
	Databox      string   `json:"databox"`
	Account      string   `json:"account"`
	VS           string   `json:"vs"`
	HasQR        bool     `json:"has_qr"`
	ReportURL    string   `json:"report_url"`
	Issues       []string `json:"issues"`
	Subject      string   `json:"subject"`
	Text         string   `json:"text"`
	HTML         string   `json:"html"`
}

type stayFeeFile struct {
	AppBase    string        `json:"app_base"`
	PublicBase string        `json:"public_base"`
	Periods    []stayFeeCase `json:"periods"`
	Reports    []stayFeeCase `json:"reports"`
	Blocked    []stayFeeCase `json:"blocked"`
}

func loadStayFee(t *testing.T) stayFeeFile {
	t.Helper()
	raw, err := os.ReadFile(stayFeeGolden)
	if err != nil {
		t.Fatal(err)
	}
	var f stayFeeFile
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatal(err)
	}
	if len(f.Periods) == 0 || len(f.Reports) == 0 || len(f.Blocked) == 0 {
		t.Fatal("empty stay fee golden")
	}
	return f
}

func compareStayFee(t *testing.T, c stayFeeCase, got Content) {
	t.Helper()
	if got.Subject != c.Subject {
		t.Errorf("%s: subject\n got %q\nwant %q", c.Name, got.Subject, c.Subject)
	}
	if got.Text != c.Text {
		t.Errorf("%s: text\n got %q\nwant %q", c.Name, got.Text, c.Text)
	}
	if got.HTML != c.HTML {
		t.Errorf("%s: html differs from Python", c.Name)
	}
}

func TestPeriodLabelMatchesPython(t *testing.T) {
	for _, c := range loadStayFee(t).Periods {
		if got := PeriodLabel(c.Lang, c.Cadence, c.Year, c.Month); got != c.Label {
			t.Errorf("%q %s %d: got %q want %q", c.Lang, c.Cadence, c.Month, got, c.Label)
		}
	}
}

func TestBuildStayFeeReportMatchesPython(t *testing.T) {
	f := loadStayFee(t)
	for _, c := range f.Reports {
		if got := PeriodLabel(c.Lang, c.Cadence, c.Year, c.Month); got != c.Period {
			t.Errorf("%s: period got %q want %q", c.Name, got, c.Period)
		}
		got := BuildStayFeeReport(f.AppBase, f.PublicBase, c.Lang, StayFeeReport{
			PropertyName: c.PropertyName, Period: c.Period, Amount: c.Amount, TotalCZK: c.TotalCZK,
			Authority: c.Authority, Databox: c.Databox, Account: c.Account, VS: c.VS,
			HasQR: c.HasQR, ReportURL: c.ReportURL,
		})
		compareStayFee(t, c, got)
	}
}

func TestBuildStayFeeBlockedMatchesPython(t *testing.T) {
	f := loadStayFee(t)
	for _, c := range f.Blocked {
		got := BuildStayFeeBlocked(f.AppBase, f.PublicBase, c.Lang, c.PropertyName, c.Period, c.Issues, c.ReportURL)
		compareStayFee(t, c, got)
	}
}
