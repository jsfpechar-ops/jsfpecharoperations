package ubyport

import (
	"reflect"
	"testing"
)

func TestTablesMatchPythonOracle(t *testing.T) {
	doc := loadGolden(t)
	check := func(name string, want, got any) {
		t.Helper()
		if !reflect.DeepEqual(want, got) {
			t.Errorf("%s: want %v, got %v", name, want, got)
		}
	}
	check("known_codes", doc.Tables.KnownCodes, KnownCodes)
	check("known_severity", doc.Tables.KnownSeverity, KnownSeverity)
	check("fallback_text", doc.Tables.FallbackText, FallbackText)
	check("accepted_max_severity", doc.Tables.AcceptedMaxSeverity, AcceptedMaxSeverity)
	check("max_pdf_bytes", doc.Tables.MaxPDFBytes, MaxPDFBytes)
}
