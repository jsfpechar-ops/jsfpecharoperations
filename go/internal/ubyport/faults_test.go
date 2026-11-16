package ubyport

import (
	"encoding/json"
	"os"
	"reflect"
	"strings"
	"testing"
)

// TestFaultTableSameAsPython reads the golden JSON written by
// App/scripts/ubyport_fault_golden.py and compares it with FaultRows (A1b P2).
func TestFaultTableSameAsPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/fault_table.json")
	if err != nil {
		t.Fatal(err)
	}
	var golden []struct {
		Key     string `json:"key"`
		Match   string `json:"match"`
		TextKey string `json:"text_key"`
	}
	if err := json.Unmarshal(raw, &golden); err != nil {
		t.Fatal(err)
	}
	if len(golden) != len(FaultRows) {
		t.Fatalf("rows: golden %d, go %d", len(golden), len(FaultRows))
	}
	for i, row := range golden {
		want := FaultRow{row.Key, row.Match, row.TextKey}
		if !reflect.DeepEqual(FaultRows[i], want) {
			t.Fatalf("row %d: go %+v, python %+v", i, FaultRows[i], want)
		}
	}
}

func TestFaultCodeForRowsAndUnknown(t *testing.T) {
	if got := FaultCodeFor("fault", "x Chyba běhu programu y"); got != "uby_runtime" {
		t.Fatalf("runtime row: %q", got)
	}
	if got := FaultCodeFor("fault", "Length cannot be less than zero"); got != "" {
		t.Fatalf("unknown fault must have no code: %q", got)
	}
	if got := FaultCodeFor("http4xx", "HTTP 404"); got != "http_404" {
		t.Fatalf("http: %q", got)
	}
	if got := FaultHostKey("fault", "CHYBA BĚHU PROGRAMU"); got != "ubyport.fault.uby_runtime" {
		t.Fatalf("host key: %q", got)
	}
}

func TestFaultHostDetailCapped(t *testing.T) {
	long := strings.Repeat("x", 500)
	if got := FaultHostDetail(long); len([]rune(got)) != faultDetailCap {
		t.Fatalf("cap: %d", len([]rune(got)))
	}
}

func TestFaultAlertParamsCarryTextKey(t *testing.T) {
	if p := FaultAlertParams("fault", "Chyba běhu programu"); p["fault_text_key"] != "ubyport.fault.uby_runtime" {
		t.Fatalf("row: %v", p)
	}
	if u := FaultAlertParams("fault", "other"); u["fault_text_key"] != FaultUnknownKey || u["detail"] != "other" {
		t.Fatalf("unknown: %v", u)
	}
	if len(FaultAlertParams("dial", "x")) != 0 {
		t.Fatal("dial must carry no fault key")
	}
}

// TestFaultMailCopySameAsPython checks the English fault copy against the golden
// JSON written by App/scripts/ubyport_fault_golden.py from the Python catalogue.
func TestFaultMailCopySameAsPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/fault_copy_en.json")
	if err != nil {
		t.Fatal(err)
	}
	var golden map[string]string
	if err := json.Unmarshal(raw, &golden); err != nil {
		t.Fatal(err)
	}
	if len(golden) != len(faultCopyEN) {
		t.Fatalf("keys: golden %d, go %d", len(golden), len(faultCopyEN))
	}
	for key, text := range golden {
		if faultCopyEN[key] != text {
			t.Fatalf("%s: go %q, python %q", key, faultCopyEN[key], text)
		}
	}
}

// TestFaultBothMatchStringsSpecificRowFirst: a detail holding both match strings
// takes the no-errors row, which comes first in the table, in Go as in Python.
func TestFaultBothMatchStringsSpecificRowFirst(t *testing.T) {
	detail := "Chyba běhu programu and Odpověď neobsahuje záznamy o chybách"
	if got := FaultCodeFor("fault", detail); got != "uby_runtime_no_errors" {
		t.Fatalf("code: %q", got)
	}
	if got := FaultHostKey("fault", detail); got != "ubyport.fault.uby_runtime_no_errors" {
		t.Fatalf("key: %q", got)
	}
}

// TestHeaderCodesOnceInSubmissionRejectedParams is the Go twin of the Python
// header test: the codes travel once, in header_codes, for the presenter to word.
func TestHeaderCodesOnceInSubmissionRejectedParams(t *testing.T) {
	p := submissionRejectedParams("Flat", 2, 1, 1, "", "112;5")
	if p["header_codes"] != "112;5" {
		t.Fatalf("header_codes: %v", p["header_codes"])
	}
	if p["count"] != 2 || p["property"] != "Flat" {
		t.Fatalf("params: %v", p)
	}
}
