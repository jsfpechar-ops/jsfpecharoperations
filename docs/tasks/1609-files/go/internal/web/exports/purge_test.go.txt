package exports

// Brief 1609: POST /settings/purge-expired. It deletes data, so the Python
// cases pin every audit row and, after each request, the guest, photo,
// envelope, invoice and reservation state; the tests below pin the refusals
// that delete nothing.

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

// TestPurgeExpiredMatchesPython replays the purge_ cases: signed out, no
// CSRF (both delete nothing), workspace 2 (one envelope), workspace 1 (2
// guests of 2019 and their reservation, 2 photos, 2 envelopes), workspace 1
// again in Czech (nothing left), workspace 5 (nothing), and the supporting
// admin (the run row carries the admin as actor and impersonator).
func TestPurgeExpiredMatchesPython(t *testing.T) {
	if n := replayRoutes(t, "purge_"); n != 7 {
		t.Errorf("ran %d purge_ cases, want 7", n)
	}
}

// purgeState is what the purge may delete: guests, photo marks, envelopes,
// reservations, invoices, photo files, audit rows.
func purgeState(t *testing.T, w *world) []int {
	t.Helper()
	files, err := os.ReadDir(filepath.Join(w.dataDir, "passport_photos"))
	if err != nil {
		t.Fatal(err)
	}
	return []int{
		w.count(`SELECT COUNT(*) FROM guest`),
		w.count(`SELECT COUNT(*) FROM guest WHERE passport_photo_at IS NOT NULL`),
		w.count(`SELECT COUNT(*) FROM submission WHERE request_xml IS NOT NULL OR request_xml_enc IS NOT NULL OR response_xml IS NOT NULL`),
		w.count(`SELECT COUNT(*) FROM reservation`),
		w.count(`SELECT COUNT(*) FROM invoice`),
		len(files),
		int(w.auditMax()),
	}
}

// TestPurgeExpiredRefusals: a GET, a signed-out POST, a POST without CSRF
// and a POST with UBYHOST_DATA_DIR unset change nothing at all.
func TestPurgeExpiredRefusals(t *testing.T) {
	w, _ := newRoutesWorld(t)
	before := purgeState(t, w)
	check := func(name string) {
		t.Helper()
		if got := purgeState(t, w); fmt.Sprint(got) != fmt.Sprint(before) {
			t.Errorf("%s: state %v, want %v", name, got, before)
		}
	}
	if rec := w.do("GET", "/settings/purge-expired", asOwner, nil, false); rec.Code != 405 {
		t.Errorf("GET: %d, want 405", rec.Code)
	}
	check("GET")
	redirectsTo(t, "signed out", w.do("POST", "/settings/purge-expired", nil, nil, false), "/login?next=/settings/purge-expired")
	check("signed out")
	redirectsTo(t, "no CSRF", w.do("POST", "/settings/purge-expired", asOwner, nil, true), "/login?notice=form_expired")
	check("no CSRF")
	w.env["UBYHOST_DATA_DIR"] = ""
	if rec := w.do("POST", "/settings/purge-expired", asOwner, nil, false); rec.Code != 500 {
		t.Errorf("no data dir: %d, want 500", rec.Code)
	}
	check("no data dir")
}

// TestPurgeExpiredPausedWorkspace: Python exempts /settings from the
// paused-workspace POST redirect (finding F1), so a paused workspace can
// still delete its expired records.
func TestPurgeExpiredPausedWorkspace(t *testing.T) {
	w, _ := newRoutesWorld(t)
	w.env["UBYHOST_BILLING_ENABLED"] = "1"
	w.exec(`INSERT INTO billing_account (owner_user_id, status, updated_at) VALUES (1, 'paused', '2026-11-01')`)
	redirectsTo(t, "paused", w.do("POST", "/settings/purge-expired", asOwner, nil, false), "/settings?msg=Deleted%202%20guest")
	if n := w.count(`SELECT COUNT(*) FROM guest WHERE id IN (30, 31)`); n != 0 {
		t.Errorf("%d guests of 2019 left, want 0", n)
	}
}
