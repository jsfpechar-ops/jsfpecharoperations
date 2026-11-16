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
