package billingweb

import "testing"

// wantRoutes is every method and path of routes/billing.py and routes/admin_billing.py
// that the briefs 1555 to 1559 have ported so far (13 when 1560 is done).
var wantRoutes = []string{
	"GET /predplatne/faktury/{file}",
	"POST /predplatne/zrusit",
	"POST /predplatne/obnovit",
	"GET /admin/fakturace/{file}",
	"GET /predplatne",
	"POST /predplatne",
	"POST /predplatne/zmena",
	"POST /admin/fakturace/vypis",
	"POST /admin/fakturace/{invoice_id}/zaplaceno",
	"POST /admin/fakturace/{invoice_id}/storno",
	"GET /admin/fakturace/export-vse",
	"GET /admin/fakturace/export",
}

// TestRoutesNeedNoPool: Routes builds without a pool, and its patterns are exactly wantRoutes.
func TestRoutesNeedNoPool(t *testing.T) {
	got := map[string]bool{}
	for _, r := range Routes(nil, testEnvMap(nil), nil) {
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
