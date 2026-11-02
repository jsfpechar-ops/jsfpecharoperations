package ubyport

import (
	"encoding/json"
	"os"
	"reflect"
	"testing"
)

// The golden outcome cases are shared with the Python oracle, which wrote
// expected.json from reporting.plan_outcome.
const (
	outcomeCasesPath    = "../../../App/tests/golden/ubyport/outcome/cases.json"
	outcomeExpectedPath = "../../../App/tests/golden/ubyport/outcome/expected.json"
	outcomeSubmissionID = 900
	outcomeNow          = "2026-11-01T10:00:00+00:00"
)

type outcomeCase struct {
	Name         string            `json:"name"`
	Guests       []OutcomeGuest    `json:"guests"`
	Result       outcomeResult     `json:"result"`
	Codebook     map[string]string `json:"codebook"`
	Severities   map[string]int    `json:"severities"`
	ReceiptsHeld []int64           `json:"receipts_held"`
}

type outcomeResult struct {
	HeaderErrors string   `json:"header_errors"`
	RecordErrors []string `json:"record_errors"`
	ReceiptPDF   string   `json:"receipt_pdf"`
}

func TestPlanOutcomeMatchesGolden(t *testing.T) {
	casesRaw, err := os.ReadFile(outcomeCasesPath)
	if err != nil {
		t.Fatal(err)
	}
	expectedRaw, err := os.ReadFile(outcomeExpectedPath)
	if err != nil {
		t.Fatal(err)
	}
	var cases []outcomeCase
	if err := json.Unmarshal(casesRaw, &cases); err != nil {
		t.Fatal(err)
	}
	var expected map[string]any
	if err := json.Unmarshal(expectedRaw, &expected); err != nil {
		t.Fatal(err)
	}
	for _, c := range cases {
		want, ok := expected[c.Name]
		if !ok {
			t.Errorf("case %s has no entry in expected.json", c.Name)
			continue
		}
		held := map[int64]bool{}
		for _, id := range c.ReceiptsHeld {
			held[id] = true
		}
		// Mirrors the Python oracle: a falsy id gives None, a held id gives itself.
		lookup := func(id *int64) *int64 {
			if id == nil || *id == 0 || !held[*id] {
				return nil
			}
			v := *id
			return &v
		}
		res := SubmitResult{
			HeaderErrors: c.Result.HeaderErrors,
			RecordErrors: c.Result.RecordErrors,
			ReceiptPDF:   c.Result.ReceiptPDF,
		}
		plan := PlanOutcome(c.Guests, res, outcomeSubmissionID, outcomeNow, c.Codebook, c.Severities, lookup)
		gotRaw, err := json.Marshal(plan)
		if err != nil {
			t.Fatal(err)
		}
		var got any
		if err := json.Unmarshal(gotRaw, &got); err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(got, want) {
			t.Errorf("case %s\nwant: %v\ngot:  %v", c.Name, want, got)
		}
	}
}
