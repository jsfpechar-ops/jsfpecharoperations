package billingweb

import (
	"archive/zip"
	"bytes"
	"io"
	"net/url"
	"sort"
	"strings"
	"testing"
)

// Parity: routes/admin_billing.py billing_admin_storno, billing_admin_export_all and
// billing_admin_export (lines 104-143), billing_admin.export_zip (103-110).

func zipFiles(t *testing.T, blob []byte) map[string]string {
	t.Helper()
	zr, err := zip.NewReader(bytes.NewReader(blob), int64(len(blob)))
	if err != nil {
		t.Fatal(err)
	}
	out := map[string]string{}
	for _, f := range zr.File {
		rc, err := f.Open()
		if err != nil {
			t.Fatal(err)
		}
		b, _ := io.ReadAll(rc)
		rc.Close()
		out[f.Name] = string(b)
	}
	return out
}

func TestStorno(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	t.Setenv("UBYHOST_OPERATOR_NAME", "Operator s.r.o.")
	t.Setenv("UBYHOST_BILLING_IBAN", "CZ6508000000192000145399")
	t.Setenv("UBYHOST_BILLING_BANK_ACCOUNT", "19-2000145399/0800")
	seedAccount(t, pool, 1, "active", "standard", "year")
	mustExec(t, pool, `UPDATE billing_account SET buyer_name = 'Buyer s.r.o.', buyer_street = 'Hlavní 1', buyer_city = 'Praha', buyer_zip = '11000' WHERE owner_user_id = 1`)
	seedInvoice(t, pool, 31, 1, "UBY-2026-0031", "invoice", 119000)
	seedInvoice(t, pool, 32, 1, "UBY-2026-0032", "invoice", 119000)
	mustExec(t, pool, `UPDATE platform_invoice SET paid_on = '2026-11-02' WHERE id = 32`)
	seedInvoice(t, pool, 33, nil, "UBY-2026-0033", "invoice", 119000)
	seedInvoice(t, pool, 34, 2, "UBY-2026-0034", "invoice", 119000) // host 2 has no billing row: no buyer
	mux := testMux(pool, testEnvMap(nil))
	post := func(id string, reason string) string {
		rec := do(t, mux, "POST", "/admin/fakturace/"+id+"/storno", url.Values{"reason": {reason}}, "admin1", false)
		if rec.Code != 303 {
			t.Fatalf("storno %s: %d", id, rec.Code)
		}
		loc := location(t, rec)
		if e := loc.Query().Get("err"); e != "" {
			return "err:" + e
		}
		return "msg:" + loc.Query().Get("msg")
	}
	refused := func(code string) string {
		return "err:" + catalog.T("en", "billing.admin.storno.refused_"+code, nil)
	}
	if got := post("31", "  "); got != "err:"+catalog.T("en", "billing.admin.storno.reason_missing", nil) {
		t.Errorf("empty reason: %s", got)
	}
	long := strings.Repeat("ž", 250)
	if got := post("31", " "+long+" "); got != "msg:"+catalog.T("en", "billing.admin.storno.done", nil) {
		t.Fatalf("storno: %s", got)
	}
	for sql, want := range map[string]string{
		`SELECT voided::text FROM platform_invoice WHERE id = 31`: "1",
		// The storno: a new document that corrects 31 with the negated total, issued today.
		`SELECT kind || ' ' || total_haler || ' ' || corrects_id || ' ' || issue_date || ' ' || due_date FROM platform_invoice WHERE kind = 'storno'`: "storno -119000 31 2026-11-13 2026-11-13",
		`SELECT length(snapshot_json::json->'invoice'->>'correction_reason')::text FROM platform_invoice WHERE kind = 'storno'`:                       "200",
	} {
		if got := queryString(t, pool, sql); got != want {
			t.Errorf("%s\n got: %s\nwant: %s", sql, got, want)
		}
	}
	for id, want := range map[string]string{
		"31": refused("already_voided"), "32": refused("paid"), "33": refused("workspace_deleted"), "99": refused("not_an_invoice"),
		"34": refused("buyer_missing"),
	} {
		if got := post(id, "again"); got != want {
			t.Errorf("storno %s: %s, want %s", id, got, want)
		}
	}
	// A storno cannot be cancelled.
	stornoID := queryString(t, pool, `SELECT id::text FROM platform_invoice WHERE kind = 'storno'`)
	if got := post(stornoID, "x"); got != refused("not_an_invoice") {
		t.Errorf("storno of a storno: %s", got)
	}
	// A host is refused; abc is a 422.
	if rec := do(t, mux, "POST", "/admin/fakturace/32/storno", url.Values{"reason": {"x"}}, "host1", false); rec.Code != 403 {
		t.Errorf("host: %d", rec.Code)
	}
	if rec := do(t, mux, "POST", "/admin/fakturace/abc/storno", url.Values{}, "admin1", false); rec.Code != 422 {
		t.Errorf("abc: %d", rec.Code)
	}
	if rec := do(t, mux, "POST", "/admin/fakturace/32/storno", url.Values{"reason": {"x"}}, "admin1", true); rec.Code != 303 ||
		!strings.Contains(rec.Header().Get("Location"), "/") {
		t.Errorf("no token: %d", rec.Code)
	}
}

func TestExports(t *testing.T) {
	pool := testPool(t)
	seedUsers(t, pool)
	b1 := seedInvoice(t, pool, 31, 1, "UBY-2026-0031", "invoice", 119000)
	b2 := seedInvoice(t, pool, 32, 2, "UBY-2026-0032", "invoice", 14900)
	mustExec(t, pool, `UPDATE platform_invoice SET issue_date = '2026-10-31' WHERE id = 32`)
	mux := testMux(pool, testEnvMap(nil))

	// No month: the current one (2026-11) holds invoice 31 only.
	rec := do(t, mux, "GET", "/admin/fakturace/export", nil, "admin1", false)
	if rec.Code != 200 || rec.Header().Get("Content-Type") != "application/zip" ||
		rec.Header().Get("Content-Disposition") != `attachment; filename="ubyhost-faktury-2026-11.zip"` {
		t.Fatalf("export: %d %v", rec.Code, rec.Header())
	}
	files := zipFiles(t, rec.Body.Bytes())
	var names []string
	for n := range files {
		names = append(names, n)
	}
	sort.Strings(names)
	if strings.Join(names, ",") != "faktury-2026-11.csv,pdf/UBY-2026-0031.pdf" || files["pdf/UBY-2026-0031.pdf"] != string(b1) {
		t.Errorf("zip: %v", names)
	}
	if !strings.HasPrefix(files["faktury-2026-11.csv"], "\ufeffČíslo;Druh;") || !strings.Contains(files["faktury-2026-11.csv"], "UBY-2026-0031;faktura;;2026-11-01;") {
		t.Errorf("csv: %q", files["faktury-2026-11.csv"])
	}
	// A given month, and a bad one falls back to the current one.
	rec = do(t, mux, "GET", "/admin/fakturace/export?mesic=2026-10", nil, "admin1", false)
	if files = zipFiles(t, rec.Body.Bytes()); files["pdf/UBY-2026-0032.pdf"] != string(b2) || rec.Header().Get("Content-Disposition") != `attachment; filename="ubyhost-faktury-2026-10.zip"` {
		t.Errorf("october: %v", rec.Header())
	}
	rec = do(t, mux, "GET", "/admin/fakturace/export?mesic=nope", nil, "admin1", false)
	if rec.Header().Get("Content-Disposition") != `attachment; filename="ubyhost-faktury-2026-11.zip"` {
		t.Errorf("bad month: %v", rec.Header())
	}
	// A stored PDF that is gone is an error, not an empty file.
	mustExec(t, pool, `UPDATE platform_invoice SET pdf_blob = NULL WHERE id = 31`)
	if rec = do(t, mux, "GET", "/admin/fakturace/export", nil, "admin1", false); rec.Code != 500 {
		t.Errorf("missing pdf: %d", rec.Code)
	}
	// The bulk export: the three CSV files, never a PDF.
	rec = do(t, mux, "GET", "/admin/fakturace/export-vse", nil, "admin1", false)
	if rec.Code != 200 || rec.Header().Get("Content-Disposition") != `attachment; filename="ubyhost-billing-all.zip"` {
		t.Fatalf("export-vse: %d", rec.Code)
	}
	files = zipFiles(t, rec.Body.Bytes())
	if len(files) != 3 {
		t.Errorf("bulk files: %d", len(files))
	}
	for n := range files {
		if strings.HasSuffix(n, ".pdf") {
			t.Errorf("pdf in the bulk export: %s", n)
		}
	}
	// Hosts and visitors get nothing.
	for _, p := range []string{"/admin/fakturace/export", "/admin/fakturace/export-vse"} {
		if rec = do(t, mux, "GET", p, nil, "host1", false); rec.Code != 403 {
			t.Errorf("%s host: %d", p, rec.Code)
		}
		if rec = do(t, mux, "GET", p, nil, "", false); rec.Code != 303 {
			t.Errorf("%s visitor: %d", p, rec.Code)
		}
	}
}
