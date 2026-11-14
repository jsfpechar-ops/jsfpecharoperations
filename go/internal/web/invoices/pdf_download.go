package invoices

// GET /invoices/{id}.pdf: routes/invoices.py invoice_pdf_download (883-899).
// The route is served by invoiceGet in pages_detail.go, which hands a
// "<n>.pdf" path to pdfDownload, because ServeMux wildcards are whole path
// segments.

import "net/http"

func writePDF(w http.ResponseWriter, blob []byte, headers map[string]string) {
	w.Header().Set("Content-Type", "application/pdf")
	for k, v := range headers {
		w.Header().Set(k, v)
	}
	_, _ = w.Write(blob)
}

// pdfDownload is invoice_pdf_download: GET /invoices/{id}.pdf.
func (d deps) pdfDownload(w http.ResponseWriter, r *http.Request, raw string) {
	c, id := d.enterID(w, r, raw)
	if c == nil {
		return
	}
	inv, err := loadInvoice(r.Context(), d.pool, c.owner, id)
	if err != nil {
		c.fail(err)
		return
	}
	if inv == nil {
		c.back("/invoices", noFlash, c.flash("flash.error.no_such_invoice", nil))
		return
	}
	blob, err := downloadPDF(r.Context(), d.pool, id)
	if err != nil {
		c.fail(err)
		return
	}
	writePDF(w, blob, map[string]string{
		"Content-Disposition": `attachment; filename="faktura-` + inv.Number + `.pdf"`,
		"Cache-Control":       "no-store",
	})
}
