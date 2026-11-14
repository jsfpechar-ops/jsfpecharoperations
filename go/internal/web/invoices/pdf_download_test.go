package invoices

import (
	"context"
	"strings"
	"testing"
)

func TestPDFDownload(t *testing.T) {
	app, seed := newTestApp(t)
	id, number := app.issueFor(app.entityRow(seed.Entity), seed.Stay, nil, 1)
	rec := app.get("/invoices/"+itoa(id)+".pdf", &host1)
	if rec.Code != 200 || rec.Header().Get("Content-Type") != "application/pdf" ||
		rec.Header().Get("Content-Disposition") != `attachment; filename="faktura-`+number+`.pdf"` ||
		rec.Header().Get("Cache-Control") != "no-store" || !strings.HasPrefix(rec.Body.String(), "%PDF") {
		t.Fatalf("download: %d %v", rec.Code, rec.Header())
	}
	var stored []byte
	if err := app.pool.QueryRow(context.Background(), `SELECT pdf_blob FROM invoice WHERE id = $1`, id).Scan(&stored); err != nil || string(stored) != rec.Body.String() {
		t.Error("the download is the stored PDF, never re-rendered")
	}
	// another host's invoice, and none at all: back to the list with the flash
	for _, p := range []string{"/invoices/" + itoa(id) + ".pdf", "/invoices/9999.pdf"} {
		who := &host2
		if strings.Contains(p, "9999") {
			who = &host1
		}
		if rec := app.get(p, who); rec.Code != 303 || !strings.HasPrefix(rec.Header().Get("Location"), "/invoices?err=") {
			t.Errorf("%s: %d %q", p, rec.Code, rec.Header().Get("Location"))
		}
	}
	if rec := app.get("/invoices/abc.pdf", nil); rec.Code != 422 || !strings.Contains(rec.Body.String(), `"type":"int_parsing"`) ||
		!strings.Contains(rec.Body.String(), `"input":"abc"`) {
		t.Errorf("bad id: %d %s (a bad id is a 422 before the login check)", rec.Code, rec.Body.String())
	}
	if rec := app.get("/invoices/"+itoa(id)+".pdf", nil); rec.Code != 303 || rec.Header().Get("Location") != "/login?next=/invoices/"+itoa(id)+".pdf" {
		t.Errorf("signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
}
