package exports

import (
	"testing"
	"time"
)

// wantRoutes is every method and path of App/app/routes/exports.py that
// briefs 1320, 1321 and 1605 to 1607 have ported (11 of 13; 13 when 1609 is done).
var wantRoutes = []string{
	"GET /reservations.csv",
	"GET /submissions/receipts.zip",
	"GET /submissions/{id}/receipt.pdf",
	"GET /submissions/{id}/errors.pdf",
	"GET /submissions/{id}/{file}",
	"GET /reservations/{id}/dorucenka.zip",
	"GET /housebook.csv",
	"GET /guests/{id}/export.json",
	"GET /guests/{id}/form.pdf",
	"GET /housebook/pdfs.zip",
	"POST /settings/workspace-export",
}

// TestExportRoutesInventory: Routes builds without a pool, and its patterns
// are exactly wantRoutes.
func TestExportRoutesInventory(t *testing.T) {
	got := map[string]bool{}
	for _, r := range Routes(nil, func(string) string { return "" }, time.Now) {
		if got[r.Pattern] {
			t.Errorf("pattern twice: %s", r.Pattern)
		}
		got[r.Pattern] = true
	}
	for _, w := range wantRoutes {
		if !got[w] {
			t.Errorf("missing route %s", w)
		}
		delete(got, w)
	}
	for extra := range got {
		t.Errorf("unexpected route %s", extra)
	}
}
