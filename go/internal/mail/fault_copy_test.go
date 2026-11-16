package mail

import (
	"encoding/json"
	"os"
	"testing"
)

// The English copy and match rows must equal the Python catalogue (App/app/host_i18n.py,
// App/app/ubyport/faults.py), through the golden JSON files in the ubyport package.
func TestFaultCopyMatchesPythonGolden(t *testing.T) {
	raw, err := os.ReadFile("../ubyport/testdata/fault_copy_en.json")
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

func TestFaultRowsMatchPythonGolden(t *testing.T) {
	raw, err := os.ReadFile("../ubyport/testdata/fault_table.json")
	if err != nil {
		t.Fatal(err)
	}
	var rows []struct {
		Match   string `json:"match"`
		TextKey string `json:"text_key"`
	}
	if err := json.Unmarshal(raw, &rows); err != nil {
		t.Fatal(err)
	}
	if len(rows) != len(faultCopyRows) {
		t.Fatalf("rows: golden %d, go %d", len(rows), len(faultCopyRows))
	}
	for i, row := range rows {
		if faultCopyRows[i].match != row.Match || faultCopyRows[i].textKey != row.TextKey {
			t.Fatalf("row %d differs from the Python table", i)
		}
	}
}
